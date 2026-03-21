package store

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/neuranac/services/radius-server/internal/config"
	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/nats-io/nats.go"
	"github.com/redis/go-redis/v9"
	"go.uber.org/zap"
)

// DataStore holds connections to PostgreSQL, Redis, and NATS
type DataStore struct {
	DB       *pgxpool.Pool
	Redis    *redis.Client
	NATS     *nats.Conn
	JS       nats.JetStreamContext
	Logger   *zap.Logger
	cacheKey string // AES-256 key for encrypting secrets in Redis cache
	SiteID   string // UUID of this NeuraNAC site (for hybrid session attribution)
}

// New creates a new DataStore with all connections initialized
func New(ctx context.Context, cfg *config.Config, logger *zap.Logger) (*DataStore, error) {
	// PostgreSQL connection pool
	poolCfg, err := pgxpool.ParseConfig(cfg.PostgresDSN())
	if err != nil {
		return nil, fmt.Errorf("parse postgres DSN: %w", err)
	}
	poolCfg.MaxConns = 50
	poolCfg.MinConns = 5
	poolCfg.MaxConnLifetime = 30 * time.Minute
	poolCfg.MaxConnIdleTime = 5 * time.Minute

	db, err := pgxpool.NewWithConfig(ctx, poolCfg)
	if err != nil {
		return nil, fmt.Errorf("connect to postgres: %w", err)
	}
	if err := db.Ping(ctx); err != nil {
		return nil, fmt.Errorf("ping postgres: %w", err)
	}
	logger.Info("Connected to PostgreSQL", zap.String("host", cfg.PostgresHost))

	// Redis connection
	rdb := redis.NewClient(&redis.Options{
		Addr:         cfg.RedisAddr(),
		Password:     cfg.RedisPass,
		DB:           0,
		PoolSize:     50,
		MinIdleConns: 5,
		DialTimeout:  5 * time.Second,
		ReadTimeout:  3 * time.Second,
		WriteTimeout: 3 * time.Second,
	})
	if err := rdb.Ping(ctx).Err(); err != nil {
		return nil, fmt.Errorf("connect to redis: %w", err)
	}
	logger.Info("Connected to Redis", zap.String("addr", cfg.RedisAddr()))

	// NATS connection with JetStream
	nc, err := nats.Connect(cfg.NatsURL,
		nats.MaxReconnects(-1),
		nats.ReconnectWait(2*time.Second),
		nats.DisconnectErrHandler(func(_ *nats.Conn, err error) {
			logger.Warn("NATS disconnected", zap.Error(err))
		}),
		nats.ReconnectHandler(func(_ *nats.Conn) {
			logger.Info("NATS reconnected")
		}),
	)
	if err != nil {
		return nil, fmt.Errorf("connect to NATS: %w", err)
	}

	js, err := nc.JetStream()
	if err != nil {
		return nil, fmt.Errorf("init JetStream: %w", err)
	}
	logger.Info("Connected to NATS JetStream")

	// Ensure streams exist
	if err := ensureStreams(js); err != nil {
		return nil, fmt.Errorf("ensure NATS streams: %w", err)
	}

	return &DataStore{
		DB:       db,
		Redis:    rdb,
		NATS:     nc,
		JS:       js,
		Logger:   logger,
		cacheKey: cfg.CacheEncryptionKey,
		SiteID:   cfg.SiteID,
	}, nil
}

func ensureStreams(js nats.JetStreamContext) error {
	streams := []struct {
		name     string
		subjects []string
	}{
		{"NeuraNAC_SESSIONS", []string{"neuranac.sessions.>"}},
		{"NeuraNAC_SYNC", []string{"neuranac.sync.>"}},
		{"NeuraNAC_CONTEXT", []string{"neuranac.context.>"}},
		{"NeuraNAC_AUDIT", []string{"neuranac.audit.>"}},
		{"NeuraNAC_AI", []string{"neuranac.ai.>"}},
	}

	for _, s := range streams {
		_, err := js.AddStream(&nats.StreamConfig{
			Name:      s.name,
			Subjects:  s.subjects,
			Retention: nats.LimitsPolicy,
			MaxAge:    7 * 24 * time.Hour,
			Storage:   nats.FileStorage,
			Replicas:  1,
		})
		if err != nil {
			return fmt.Errorf("create stream %s: %w", s.name, err)
		}
	}
	return nil
}

// Ping checks all connections are alive
func (ds *DataStore) Ping(ctx context.Context) error {
	if err := ds.DB.Ping(ctx); err != nil {
		return fmt.Errorf("postgres: %w", err)
	}
	if err := ds.Redis.Ping(ctx).Err(); err != nil {
		return fmt.Errorf("redis: %w", err)
	}
	if !ds.NATS.IsConnected() {
		return fmt.Errorf("nats: not connected")
	}
	return nil
}

// Close cleanly shuts down all connections
func (ds *DataStore) Close() {
	ds.DB.Close()
	ds.Redis.Close()
	ds.NATS.Close()
}

// --- NAD Registry Cache ---

type NADInfo struct {
	TenantID      string
	DeviceID      string
	SharedSecret  string
	Vendor        string
	Model         string
	CoAPort       int
	RadSecEnabled bool
}

// EndpointInfo holds profiled endpoint data
type EndpointInfo struct {
	ID         string
	MAC        string
	DeviceType string
	Vendor     string
	OS         string
	Status     string
	GroupID    string
}

// CreateSession records a new RADIUS session
func (ds *DataStore) CreateSession(ctx context.Context, tenantID, sessionID, mac, nasIP string) {
	_, err := ds.DB.Exec(ctx,
		`INSERT INTO sessions (tenant_id, session_id_radius, endpoint_mac, nas_ip, is_active, started_at, site_id)
		 VALUES ($1, $2, $3, $4, true, NOW(), NULLIF($5, '')::uuid)
		 ON CONFLICT (session_id_radius) DO NOTHING`,
		tenantID, sessionID, mac, nasIP, ds.SiteID)
	if err != nil {
		ds.Logger.Error("Create session failed", zap.String("session", sessionID), zap.Error(err))
	}
}

// UpdateSession updates accounting data for an active session
func (ds *DataStore) UpdateSession(ctx context.Context, sessionID string, pkt interface{}) {
	_, err := ds.DB.Exec(ctx,
		`UPDATE sessions SET accounting = jsonb_set(COALESCE(accounting,'{}'), '{last_interim}', to_jsonb(NOW()::text))
		 WHERE session_id_radius = $1`, sessionID)
	if err != nil {
		ds.Logger.Error("Update session failed", zap.String("session", sessionID), zap.Error(err))
	}
}

// EndSession marks a session as ended
func (ds *DataStore) EndSession(ctx context.Context, sessionID string) {
	_, err := ds.DB.Exec(ctx,
		`UPDATE sessions SET is_active = false, ended_at = NOW() WHERE session_id_radius = $1`, sessionID)
	if err != nil {
		ds.Logger.Error("End session failed", zap.String("session", sessionID), zap.Error(err))
	}
}

// GetEndpointByMAC looks up an endpoint by MAC address
func (ds *DataStore) GetEndpointByMAC(ctx context.Context, tenantID, mac string) (*EndpointInfo, error) {
	// Check Redis cache
	key := fmt.Sprintf("ep:%s:%s", tenantID, mac)
	cached, err := ds.Redis.HGetAll(ctx, key).Result()
	if err == nil && len(cached) > 0 {
		return &EndpointInfo{
			ID: cached["id"], MAC: mac, DeviceType: cached["device_type"],
			Vendor: cached["vendor"], OS: cached["os"], Status: cached["status"],
			GroupID: cached["group_id"],
		}, nil
	}

	var ep EndpointInfo
	ep.MAC = mac
	err = ds.DB.QueryRow(ctx,
		`SELECT id, device_type, vendor, os, status, COALESCE(group_id::text, '')
		 FROM endpoints WHERE tenant_id = $1 AND mac_address = $2`, tenantID, mac).
		Scan(&ep.ID, &ep.DeviceType, &ep.Vendor, &ep.OS, &ep.Status, &ep.GroupID)
	if err != nil {
		return nil, fmt.Errorf("endpoint not found for MAC %s: %w", mac, err)
	}

	// Cache for 2 minutes
	ds.Redis.HSet(ctx, key, map[string]interface{}{
		"id": ep.ID, "device_type": ep.DeviceType, "vendor": ep.Vendor,
		"os": ep.OS, "status": ep.Status, "group_id": ep.GroupID,
	})
	ds.Redis.Expire(ctx, key, 2*time.Minute)
	return &ep, nil
}

// InternalUser holds user identity data from internal_users table
type InternalUser struct {
	ID           string
	TenantID     string
	Username     string
	PasswordHash string
	Email        string
	Groups       []string
	Status       string
}

// GetUserByUsername looks up an internal user by username across all tenants (or within a tenant)
func (ds *DataStore) GetUserByUsername(ctx context.Context, tenantID, username string) (*InternalUser, error) {
	var user InternalUser
	var groupsJSON []byte
	var query string
	var args []interface{}

	if tenantID != "" {
		query = `SELECT id, tenant_id, username, password_hash, COALESCE(email,''), COALESCE(groups,'[]'), status
		         FROM internal_users WHERE tenant_id = $1 AND username = $2 AND status = 'active'`
		args = []interface{}{tenantID, username}
	} else {
		query = `SELECT id, tenant_id, username, password_hash, COALESCE(email,''), COALESCE(groups,'[]'), status
		         FROM internal_users WHERE username = $1 AND status = 'active' LIMIT 1`
		args = []interface{}{username}
	}

	err := ds.DB.QueryRow(ctx, query, args...).Scan(
		&user.ID, &user.TenantID, &user.Username, &user.PasswordHash,
		&user.Email, &groupsJSON, &user.Status,
	)
	if err != nil {
		return nil, fmt.Errorf("user not found: %s: %w", username, err)
	}

	// Parse groups JSON
	if len(groupsJSON) > 0 {
		json.Unmarshal(groupsJSON, &user.Groups)
	}

	return &user, nil
}

// AIAgentInfo holds AI agent identity data
type AIAgentInfo struct {
	ID         string
	TenantID   string
	AgentName  string
	AgentType  string
	Status     string
	AuthMethod string
	Runtime    string
}

// PolicyResult holds the result of a policy evaluation
type PolicyResult struct {
	Decision  string
	VLAN      string
	SGT       int
	RiskScore int
}

// GetAIAgent looks up an AI agent by ID
func (ds *DataStore) GetAIAgent(ctx context.Context, tenantID, agentID string) (*AIAgentInfo, error) {
	var agent AIAgentInfo
	err := ds.DB.QueryRow(ctx,
		`SELECT id, tenant_id, agent_name, agent_type, status, COALESCE(auth_method,''), COALESCE(runtime,'')
		 FROM ai_agents WHERE tenant_id = $1 AND id = $2`, tenantID, agentID).
		Scan(&agent.ID, &agent.TenantID, &agent.AgentName, &agent.AgentType,
			&agent.Status, &agent.AuthMethod, &agent.Runtime)
	if err != nil {
		return nil, fmt.Errorf("AI agent not found: %s: %w", agentID, err)
	}
	return &agent, nil
}

// EvaluatePolicy calls the policy engine (HTTP fallback) to get authorization attributes
func (ds *DataStore) EvaluatePolicy(ctx context.Context, tenantID, username, mac, eapType string) (*PolicyResult, error) {
	// Query authorization profile assigned to the first matching policy rule
	var vlanID, action string
	var sgtValue int
	err := ds.DB.QueryRow(ctx,
		`SELECT COALESCE(ap.vlan_id,''), COALESCE(ap.sgt_value,0), COALESCE(pr.action,'permit')
		 FROM policy_rules pr
		 JOIN policy_sets ps ON pr.policy_set_id = ps.id
		 LEFT JOIN authorization_profiles ap ON pr.auth_profile_id = ap.id
		 WHERE ps.tenant_id = $1 AND ps.status = 'active' AND pr.status = 'active'
		 ORDER BY ps.priority, pr.priority LIMIT 1`, tenantID).
		Scan(&vlanID, &sgtValue, &action)
	if err != nil {
		// No matching policy — use defaults
		return &PolicyResult{Decision: "permit"}, nil
	}
	return &PolicyResult{
		Decision: action,
		VLAN:     vlanID,
		SGT:      sgtValue,
	}, nil
}

// GetNADByIP looks up a Network Access Device by its IP address
func (ds *DataStore) GetNADByIP(ctx context.Context, nasIP string) (*NADInfo, error) {
	// Check Redis cache first
	key := fmt.Sprintf("nad:%s", nasIP)
	cached, err := ds.Redis.HGetAll(ctx, key).Result()
	if err == nil && len(cached) > 0 {
		coaPort := 3799
		fmt.Sscanf(cached["coa_port"], "%d", &coaPort)
		return &NADInfo{
			TenantID:      cached["tenant_id"],
			DeviceID:      cached["device_id"],
			SharedSecret:  decryptValue(cached["shared_secret"], ds.cacheKey),
			Vendor:        cached["vendor"],
			Model:         cached["model"],
			CoAPort:       coaPort,
			RadSecEnabled: cached["radsec"] == "true",
		}, nil
	}

	// Fall back to database
	var nad NADInfo
	err = ds.DB.QueryRow(ctx,
		`SELECT tenant_id, id, shared_secret_encrypted, vendor, model, coa_port, radsec_enabled
		 FROM network_devices WHERE ip_address = $1 AND status = 'active'`, nasIP).
		Scan(&nad.TenantID, &nad.DeviceID, &nad.SharedSecret, &nad.Vendor, &nad.Model, &nad.CoAPort, &nad.RadSecEnabled)
	if err != nil {
		return nil, fmt.Errorf("NAD not found for IP %s: %w", nasIP, err)
	}

	// Cache in Redis for 5 minutes (shared secret is encrypted at rest)
	ds.Redis.HSet(ctx, key, map[string]interface{}{
		"tenant_id":     nad.TenantID,
		"device_id":     nad.DeviceID,
		"shared_secret": encryptValue(nad.SharedSecret, ds.cacheKey),
		"vendor":        nad.Vendor,
		"model":         nad.Model,
		"coa_port":      fmt.Sprintf("%d", nad.CoAPort),
		"radsec":        fmt.Sprintf("%t", nad.RadSecEnabled),
	})
	ds.Redis.Expire(ctx, key, 5*time.Minute)

	return &nad, nil
}
