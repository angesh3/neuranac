// Package config provides typed configuration for the sync-engine,
// loaded from environment variables with sensible defaults.
package config

import (
	"fmt"
	"os"
	"strconv"
	"time"
)

// Config holds all sync-engine settings.
type Config struct {
	// Identity
	NodeID         string
	Env            string
	SiteType       string // "onprem" or "cloud"
	SiteID         string // UUID of this site in neuranac_sites
	DeploymentMode string // "standalone" or "hybrid"

	// gRPC
	GRPCPort       string
	PeerAddress    string
	MaxRecvMsgSize int // bytes
	MaxSendMsgSize int // bytes

	// Database
	DatabaseURL    string
	DBMaxOpenConns int
	DBMaxIdleConns int

	// HTTP health endpoint
	HealthPort string

	// Sync tuning
	JournalPollInterval time.Duration
	JournalBatchSize    int

	// Keepalive
	KeepaliveTime    time.Duration
	KeepaliveTimeout time.Duration
	MaxConnIdle      time.Duration
	MaxConnAge       time.Duration

	// TLS / mTLS
	TLSCertPath string
	TLSKeyPath  string
	TLSCAPath   string
	TLSEnabled  bool

	// Peer REST API (for hub-spoke site discovery)
	PeerAPIURL string

	// Hub-spoke replication
	HubReplicatorEnabled bool
	HubReplicatorPort    string
}

// Load reads configuration from environment variables.
func Load() *Config {
	c := &Config{
		NodeID:         getEnv("NEURANAC_NODE_ID", "twin-a"),
		Env:            getEnv("NeuraNAC_ENV", "development"),
		SiteType:       getEnv("NEURANAC_SITE_TYPE", "onprem"),
		SiteID:         getEnv("NEURANAC_SITE_ID", "00000000-0000-0000-0000-000000000001"),
		DeploymentMode: getEnv("DEPLOYMENT_MODE", "standalone"),

		GRPCPort:       getEnv("SYNC_GRPC_PORT", "9090"),
		PeerAddress:    getEnv("SYNC_PEER_ADDRESS", ""),
		MaxRecvMsgSize: getEnvInt("SYNC_MAX_RECV_MSG_SIZE", 10*1024*1024),
		MaxSendMsgSize: getEnvInt("SYNC_MAX_SEND_MSG_SIZE", 10*1024*1024),

		DBMaxOpenConns: getEnvInt("DB_MAX_OPEN_CONNS", 10),
		DBMaxIdleConns: getEnvInt("DB_MAX_IDLE_CONNS", 5),

		HealthPort: getEnv("SYNC_HEALTH_PORT", "9100"),

		JournalPollInterval: getEnvDuration("SYNC_JOURNAL_POLL_INTERVAL", 2*time.Second),
		JournalBatchSize:    getEnvInt("SYNC_JOURNAL_BATCH_SIZE", 100),

		KeepaliveTime:    getEnvDuration("SYNC_KEEPALIVE_TIME", 10*time.Second),
		KeepaliveTimeout: getEnvDuration("SYNC_KEEPALIVE_TIMEOUT", 3*time.Second),
		MaxConnIdle:      getEnvDuration("SYNC_MAX_CONN_IDLE", 5*time.Minute),
		MaxConnAge:       getEnvDuration("SYNC_MAX_CONN_AGE", 30*time.Minute),

		TLSCertPath: getEnv("SYNC_TLS_CERT", ""),
		TLSKeyPath:  getEnv("SYNC_TLS_KEY", ""),
		TLSCAPath:   getEnv("SYNC_TLS_CA", ""),
		TLSEnabled:  getEnvBool("SYNC_TLS_ENABLED", false),

		PeerAPIURL: getEnv("NEURANAC_PEER_API_URL", ""),

		HubReplicatorEnabled: getEnvBool("SYNC_HUB_REPLICATOR_ENABLED", false),
		HubReplicatorPort:    getEnv("SYNC_HUB_REPLICATOR_PORT", "9101"),
	}

	c.DatabaseURL = c.buildDatabaseURL()
	return c
}

func (c *Config) buildDatabaseURL() string {
	if url := os.Getenv("DATABASE_URL"); url != "" {
		return url
	}
	pgPass := getEnv("POSTGRES_PASSWORD", "")
	if pgPass == "" && c.Env != "development" {
		fmt.Println("[WARN] POSTGRES_PASSWORD not set — this is unsafe outside development")
	}
	return fmt.Sprintf("postgres://%s:%s@%s:%s/%s?sslmode=disable",
		getEnv("POSTGRES_USER", "neuranac"),
		pgPass,
		getEnv("POSTGRES_HOST", "postgres"),
		getEnv("POSTGRES_PORT", "5432"),
		getEnv("POSTGRES_DB", "neuranac"),
	)
}

// IsDevelopment returns true when running in dev mode.
func (c *Config) IsDevelopment() bool {
	return c.Env == "development"
}

// HasPeer returns true when a peer address is configured.
func (c *Config) HasPeer() bool {
	return c.PeerAddress != ""
}

// IsHybrid returns true when running in hybrid (multi-site) mode.
func (c *Config) IsHybrid() bool {
	return c.DeploymentMode == "hybrid"
}

// ShouldConnectPeer returns true only in hybrid mode with a peer address.
func (c *Config) ShouldConnectPeer() bool {
	return c.IsHybrid() && c.HasPeer()
}

// ── helpers ─────────────────────────────────────────────────────────────────

func getEnv(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}

func getEnvInt(key string, fallback int) int {
	s := os.Getenv(key)
	if s == "" {
		return fallback
	}
	v, err := strconv.Atoi(s)
	if err != nil {
		return fallback
	}
	return v
}

func getEnvBool(key string, fallback bool) bool {
	s := os.Getenv(key)
	if s == "" {
		return fallback
	}
	v, err := strconv.ParseBool(s)
	if err != nil {
		return fallback
	}
	return v
}

func getEnvDuration(key string, fallback time.Duration) time.Duration {
	s := os.Getenv(key)
	if s == "" {
		return fallback
	}
	v, err := time.ParseDuration(s)
	if err != nil {
		return fallback
	}
	return v
}
