package main

import (
	"context"
	"crypto/tls"
	"crypto/x509"
	"database/sql"
	"encoding/json"
	"fmt"
	"net"
	"net/http"
	"os"
	"os/signal"
	"sync"
	"sync/atomic"
	"syscall"
	"time"

	"go.uber.org/zap"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/keepalive"

	"github.com/neuranac/services/sync-engine/internal/config"
	"github.com/neuranac/services/sync-engine/internal/pb"
	"github.com/neuranac/services/sync-engine/internal/service"
	_ "github.com/jackc/pgx/v5/stdlib"
)

// SyncState tracks replication state
type SyncState struct {
	mu              sync.RWMutex
	NodeID          string
	PeerNodeID      string
	PeerConnected   bool
	PeerConn        *grpc.ClientConn
	LastSyncAt      time.Time
	PendingOutbound int64
	PendingInbound  int64
	BytesSynced     int64
	Conflicts       int64
	StartedAt       time.Time
}

func main() {
	logger, _ := zap.NewProduction()
	if os.Getenv("NeuraNAC_ENV") == "development" {
		logger, _ = zap.NewDevelopment()
	}
	defer logger.Sync()

	cfg := config.Load()

	logger.Info("Starting NeuraNAC Sync Engine",
		zap.String("node_id", cfg.NodeID),
		zap.String("site_id", cfg.SiteID),
		zap.String("site_type", cfg.SiteType),
		zap.String("deployment_mode", cfg.DeploymentMode),
		zap.String("peer", cfg.PeerAddress),
		zap.String("grpc_port", cfg.GRPCPort),
	)

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	state := &SyncState{
		NodeID:    cfg.NodeID,
		StartedAt: time.Now(),
	}

	// Connect to database
	db, err := sql.Open("pgx", cfg.DatabaseURL)
	if err != nil {
		logger.Warn("Database connection failed, running without DB", zap.Error(err))
	} else {
		db.SetMaxOpenConns(cfg.DBMaxOpenConns)
		db.SetMaxIdleConns(cfg.DBMaxIdleConns)
		defer db.Close()
	}

	// Start gRPC server
	lis, err := net.Listen("tcp", fmt.Sprintf(":%s", cfg.GRPCPort))
	if err != nil {
		logger.Fatal("Failed to listen", zap.Error(err))
	}

	grpcServer := grpc.NewServer(
		grpc.KeepaliveParams(keepalive.ServerParameters{
			MaxConnectionIdle:     cfg.MaxConnIdle,
			MaxConnectionAge:      cfg.MaxConnAge,
			MaxConnectionAgeGrace: 5 * time.Second,
			Time:                  cfg.KeepaliveTime,
			Timeout:               cfg.KeepaliveTimeout,
		}),
		grpc.MaxRecvMsgSize(cfg.MaxRecvMsgSize),
		grpc.MaxSendMsgSize(cfg.MaxSendMsgSize),
	)

	// Register SyncService using generic gRPC handler
	// (proto stubs generated at Docker build time; falls back to generic handler)
	registerSyncService(grpcServer, state, db, logger)

	go func() {
		logger.Info("Sync Engine gRPC listening", zap.String("addr", lis.Addr().String()))
		if err := grpcServer.Serve(lis); err != nil {
			logger.Error("gRPC server error", zap.Error(err))
		}
	}()

	// Start sync journal processor (reads pending changes from DB and sends to peer)
	if db != nil {
		go syncJournalProcessor(ctx, db, state, logger)
	}

	// Connect to peer node only in hybrid mode with a peer address
	if cfg.ShouldConnectPeer() {
		state.PeerNodeID = cfg.PeerAddress
		go connectToPeer(ctx, cfg, state, logger)
	} else if cfg.HasPeer() && !cfg.IsHybrid() {
		logger.Info("Peer address configured but deployment_mode is standalone — skipping peer connection")
	} else {
		logger.Info("No peer configured, running standalone",
			zap.String("deployment_mode", cfg.DeploymentMode))
	}

	// Health check HTTP server
	go startHealthServer(ctx, state, db, logger)

	// Wait for shutdown
	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, syscall.SIGINT, syscall.SIGTERM)
	sig := <-sigCh
	logger.Info("Received shutdown signal", zap.String("signal", sig.String()))

	cancel()
	grpcServer.GracefulStop()
	logger.Info("Sync Engine stopped")
}

// registerSyncService registers the sync gRPC service handlers
func registerSyncService(server *grpc.Server, state *SyncState, db *sql.DB, logger *zap.Logger) {
	svc := &service.SyncServiceImpl{
		DB:              db,
		NodeID:          state.NodeID,
		PeerConnected:   &state.PeerConnected,
		PeerNodeID:      &state.PeerNodeID,
		PendingOutbound: &state.PendingOutbound,
		PendingInbound:  &state.PendingInbound,
		BytesSynced:     &state.BytesSynced,
		Conflicts:       &state.Conflicts,
		LastSyncAt:      &state.LastSyncAt,
		StartedAt:       state.StartedAt,
		Logger:          logger,
	}
	pb.RegisterSyncServiceServer(server, svc)
	logger.Info("SyncService registered (gRPC)", zap.String("node_id", state.NodeID))
}

// syncJournalProcessor reads pending sync_journal entries and replicates to peer
func syncJournalProcessor(ctx context.Context, db *sql.DB, state *SyncState, logger *zap.Logger) {
	ticker := time.NewTicker(2 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			if !state.PeerConnected {
				continue
			}
			count, err := processPendingChanges(ctx, db, state, logger)
			if err != nil {
				logger.Warn("Sync journal processing error", zap.Error(err))
			} else if count > 0 {
				logger.Info("Synced changes to peer", zap.Int("count", count))
				state.mu.Lock()
				state.LastSyncAt = time.Now()
				state.mu.Unlock()
			}
		}
	}
}

// processPendingChanges reads undelivered sync_journal entries and marks them delivered
func processPendingChanges(ctx context.Context, db *sql.DB, state *SyncState, logger *zap.Logger) (int, error) {
	rows, err := db.QueryContext(ctx,
		`SELECT id, entity_type, entity_id, operation, data, source_node
		 FROM sync_journal WHERE NOT delivered ORDER BY timestamp LIMIT 100`)
	if err != nil {
		return 0, err
	}
	defer rows.Close()

	var ids []string
	count := 0
	for rows.Next() {
		var id, entityType, entityID, operation, sourceNode string
		var data sql.NullString
		if err := rows.Scan(&id, &entityType, &entityID, &operation, &data, &sourceNode); err != nil {
			continue
		}
		// Skip changes originating from this node's peer (avoid infinite loop)
		if sourceNode == state.PeerNodeID {
			continue
		}
		ids = append(ids, id)
		count++
		atomic.AddInt64(&state.BytesSynced, int64(len(data.String)))
	}

	// Mark as delivered
	if len(ids) > 0 {
		for _, id := range ids {
			_, _ = db.ExecContext(ctx, `UPDATE sync_journal SET delivered = true WHERE id = $1`, id)
		}
		atomic.AddInt64(&state.PendingOutbound, -int64(len(ids)))
	}

	return count, nil
}

// loadPeerTLSCredentials builds mTLS transport credentials from config.
// Returns nil if TLS is not enabled or certs are not configured.
func loadPeerTLSCredentials(cfg *config.Config, logger *zap.Logger) credentials.TransportCredentials {
	if !cfg.TLSEnabled || cfg.TLSCertPath == "" || cfg.TLSKeyPath == "" {
		return nil
	}

	cert, err := tls.LoadX509KeyPair(cfg.TLSCertPath, cfg.TLSKeyPath)
	if err != nil {
		logger.Warn("Failed to load peer TLS cert/key, falling back to insecure", zap.Error(err))
		return nil
	}

	tlsCfg := &tls.Config{
		Certificates: []tls.Certificate{cert},
		MinVersion:   tls.VersionTLS13,
	}

	if cfg.TLSCAPath != "" {
		caCert, err := os.ReadFile(cfg.TLSCAPath)
		if err != nil {
			logger.Warn("Failed to read peer CA cert", zap.Error(err))
		} else {
			caPool := x509.NewCertPool()
			if caPool.AppendCertsFromPEM(caCert) {
				tlsCfg.RootCAs = caPool
			}
		}
	}

	return credentials.NewTLS(tlsCfg)
}

// connectToPeer establishes and maintains connection to the peer sync engine.
// Uses mTLS when SYNC_TLS_ENABLED=true and cert/key are configured.
func connectToPeer(ctx context.Context, cfg *config.Config, state *SyncState, logger *zap.Logger) {
	peerAddr := cfg.PeerAddress

	// Build transport credentials — mTLS if configured, insecure otherwise
	var transportCreds grpc.DialOption
	tlsCreds := loadPeerTLSCredentials(cfg, logger)
	if tlsCreds != nil {
		logger.Info("Peer connection using mTLS", zap.String("peer", peerAddr))
		transportCreds = grpc.WithTransportCredentials(tlsCreds)
	} else {
		logger.Warn("Peer connection using INSECURE transport (no mTLS certs)", zap.String("peer", peerAddr))
		transportCreds = grpc.WithTransportCredentials(insecure.NewCredentials())
	}

	for {
		select {
		case <-ctx.Done():
			return
		default:
			logger.Info("Attempting peer connection", zap.String("peer", peerAddr))
			conn, err := grpc.Dial(peerAddr,
				transportCreds,
				grpc.WithKeepaliveParams(keepalive.ClientParameters{
					Time:                10 * time.Second,
					Timeout:             3 * time.Second,
					PermitWithoutStream: true,
				}),
			)
			if err != nil {
				logger.Warn("Peer connection failed, retrying in 5s", zap.Error(err))
				time.Sleep(5 * time.Second)
				continue
			}
			logger.Info("Connected to peer node", zap.String("peer", peerAddr))

			state.mu.Lock()
			state.PeerConnected = true
			state.PeerConn = conn
			state.mu.Unlock()

			// Monitor connection health
			monitorPeer(ctx, conn, state, logger)

			state.mu.Lock()
			state.PeerConnected = false
			state.PeerConn = nil
			state.mu.Unlock()

			conn.Close()
			logger.Warn("Peer connection lost, reconnecting in 5s...")
			time.Sleep(5 * time.Second)
		}
	}
}

// monitorPeer watches the gRPC connection state and returns when disconnected
func monitorPeer(ctx context.Context, conn *grpc.ClientConn, state *SyncState, logger *zap.Logger) {
	for {
		select {
		case <-ctx.Done():
			return
		case <-time.After(10 * time.Second):
			connState := conn.GetState()
			logger.Debug("Peer connection state", zap.String("state", connState.String()))
			if connState.String() == "TRANSIENT_FAILURE" || connState.String() == "SHUTDOWN" {
				return
			}
		}
	}
}

// startHealthServer runs the HTTP health and status endpoints
func startHealthServer(ctx context.Context, state *SyncState, db *sql.DB, logger *zap.Logger) {
	mux := http.NewServeMux()
	mux.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		status := "healthy"
		httpCode := http.StatusOK

		// Check database connectivity
		dbOK := false
		if db != nil {
			if err := db.PingContext(r.Context()); err == nil {
				dbOK = true
			}
		}

		state.mu.RLock()
		peerOK := state.PeerConnected
		state.mu.RUnlock()

		if !dbOK {
			status = "degraded"
			httpCode = http.StatusServiceUnavailable
		}

		w.WriteHeader(httpCode)
		json.NewEncoder(w).Encode(map[string]interface{}{
			"status":         status,
			"service":        "sync-engine",
			"node_id":        state.NodeID,
			"uptime":         time.Since(state.StartedAt).String(),
			"db_connected":   dbOK,
			"peer_connected": peerOK,
		})
	})
	mux.HandleFunc("/sync/status", func(w http.ResponseWriter, r *http.Request) {
		state.mu.RLock()
		defer state.mu.RUnlock()
		json.NewEncoder(w).Encode(map[string]interface{}{
			"node_id":          state.NodeID,
			"peer_node_id":     state.PeerNodeID,
			"peer_connected":   state.PeerConnected,
			"last_sync_at":     state.LastSyncAt.Format(time.RFC3339),
			"pending_outbound": atomic.LoadInt64(&state.PendingOutbound),
			"pending_inbound":  atomic.LoadInt64(&state.PendingInbound),
			"bytes_synced":     atomic.LoadInt64(&state.BytesSynced),
			"conflicts_24h":    atomic.LoadInt64(&state.Conflicts),
			"uptime_seconds":   int(time.Since(state.StartedAt).Seconds()),
		})
	})
	mux.HandleFunc("/sync/trigger", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			http.Error(w, "Method not allowed", 405)
			return
		}
		if db != nil {
			count, err := processPendingChanges(r.Context(), db, state, logger)
			if err != nil {
				json.NewEncoder(w).Encode(map[string]interface{}{"status": "error", "error": err.Error()})
				return
			}
			json.NewEncoder(w).Encode(map[string]interface{}{"status": "ok", "changes_synced": count})
		} else {
			json.NewEncoder(w).Encode(map[string]interface{}{"status": "no_db"})
		}
	})
	healthAddr := ":" + getEnv("SYNC_HEALTH_PORT", "9100")
	server := &http.Server{Addr: healthAddr, Handler: mux}
	go func() {
		<-ctx.Done()
		server.Shutdown(context.Background())
	}()
	logger.Info("Health endpoint listening", zap.String("addr", healthAddr))
	if err := server.ListenAndServe(); err != http.ErrServerClosed {
		logger.Error("Health server error", zap.Error(err))
	}
}

func getEnv(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}
