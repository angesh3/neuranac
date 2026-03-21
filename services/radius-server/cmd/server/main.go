package main

import (
	"context"
	"fmt"
	"net/http"
	"os"
	"os/signal"
	"sync"
	"syscall"
	"time"

	"sync/atomic"

	"github.com/neuranac/services/radius-server/internal/coa"
	"github.com/neuranac/services/radius-server/internal/config"
	"github.com/neuranac/services/radius-server/internal/handler"
	radiusmetrics "github.com/neuranac/services/radius-server/internal/metrics"
	"github.com/neuranac/services/radius-server/internal/radius"
	"github.com/neuranac/services/radius-server/internal/radsec"
	"github.com/neuranac/services/radius-server/internal/store"
	"github.com/neuranac/services/radius-server/internal/tacacs"
	"go.uber.org/zap"
)

func main() {
	// Initialize logger
	logger, _ := zap.NewProduction()
	if os.Getenv("NeuraNAC_ENV") == "development" {
		logger, _ = zap.NewDevelopment()
	}
	defer logger.Sync()

	logger.Info("Starting NeuraNAC RADIUS/TACACS+ Server",
		zap.String("version", "1.0.0"),
		zap.String("node_id", os.Getenv("NEURANAC_NODE_ID")),
	)

	// Load configuration
	cfg, err := config.Load()
	if err != nil {
		logger.Fatal("Failed to load configuration", zap.Error(err))
	}

	// Initialize data stores
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	dataStore, err := store.New(ctx, cfg, logger)
	if err != nil {
		logger.Fatal("Failed to initialize data store", zap.Error(err))
	}
	defer dataStore.Close()

	// Initialize request handler (connects to policy engine via gRPC)
	reqHandler, err := handler.New(cfg, dataStore, logger)
	if err != nil {
		logger.Fatal("Failed to initialize request handler", zap.Error(err))
	}
	defer reqHandler.Close()

	// Wire up CoA sender for real UDP CoA packet delivery to NAS devices
	coaSender := coa.NewSender(logger)
	reqHandler.SetCoASender(coaSender)

	// Initialize IP allowlist and rate limiter
	allowList := radius.ParseAllowList(cfg.AllowedNASCIDRs)
	if cfg.AllowedNASCIDRs != "" {
		logger.Info("RADIUS IP allowlist configured", zap.String("cidrs", cfg.AllowedNASCIDRs))
	}
	rateLimiter := radius.NewIPRateLimiter(cfg.RadiusRateLimit)
	if cfg.RadiusRateLimit > 0 {
		logger.Info("RADIUS rate limiter configured", zap.Int("limit_per_sec", cfg.RadiusRateLimit))
	}
	defer rateLimiter.Close()

	var wg sync.WaitGroup

	// Start RADIUS Authentication listener (UDP 1812)
	wg.Add(1)
	go func() {
		defer wg.Done()
		authAddr := fmt.Sprintf(":%d", cfg.RadiusAuthPort)
		logger.Info("Starting RADIUS Authentication listener", zap.String("addr", authAddr))
		if err := radius.ListenAndServe(ctx, authAddr, reqHandler, logger, allowList, rateLimiter); err != nil {
			logger.Error("RADIUS auth listener error", zap.Error(err))
		}
	}()

	// Start RADIUS Accounting listener (UDP 1813)
	wg.Add(1)
	go func() {
		defer wg.Done()
		acctAddr := fmt.Sprintf(":%d", cfg.RadiusAcctPort)
		logger.Info("Starting RADIUS Accounting listener", zap.String("addr", acctAddr))
		if err := radius.ListenAndServeAcct(ctx, acctAddr, reqHandler, logger, allowList, rateLimiter); err != nil {
			logger.Error("RADIUS accounting listener error", zap.Error(err))
		}
	}()

	// Start RadSec listener (TLS 2083)
	wg.Add(1)
	go func() {
		defer wg.Done()
		radsecAddr := fmt.Sprintf(":%d", cfg.RadSecPort)
		logger.Info("Starting RadSec (RADIUS over TLS) listener", zap.String("addr", radsecAddr))
		if err := radsec.ListenAndServe(ctx, radsecAddr, cfg, reqHandler, logger); err != nil {
			logger.Error("RadSec listener error", zap.Error(err))
		}
	}()

	// Start TACACS+ listener (TCP 49)
	wg.Add(1)
	go func() {
		defer wg.Done()
		tacacsAddr := fmt.Sprintf(":%d", cfg.TacacsPort)
		logger.Info("Starting TACACS+ listener", zap.String("addr", tacacsAddr))
		if err := tacacs.ListenAndServe(ctx, tacacsAddr, cfg, reqHandler, logger); err != nil {
			logger.Error("TACACS+ listener error", zap.Error(err))
		}
	}()

	// Start CoA listener (for receiving CoA responses, UDP 3799)
	wg.Add(1)
	go func() {
		defer wg.Done()
		coaAddr := fmt.Sprintf(":%d", cfg.CoAPort)
		logger.Info("Starting CoA response listener", zap.String("addr", coaAddr))
		if err := coa.ListenForResponses(ctx, coaAddr, logger); err != nil {
			logger.Error("CoA listener error", zap.Error(err))
		}
	}()

	// Start health check endpoint
	wg.Add(1)
	go func() {
		defer wg.Done()
		healthAddr := ":9100"
		logger.Info("Starting health check endpoint", zap.String("addr", healthAddr))
		startHealthServer(ctx, healthAddr, dataStore, logger)
	}()

	// Wait for shutdown signal
	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, syscall.SIGINT, syscall.SIGTERM)
	sig := <-sigCh
	logger.Info("Received shutdown signal", zap.String("signal", sig.String()))

	// Graceful shutdown
	logger.Info("Starting graceful shutdown",
		zap.Int64("in_flight_requests", atomic.LoadInt64(&radius.InFlight)))
	cancel()
	shutdownCtx, shutdownCancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer shutdownCancel()

	done := make(chan struct{})
	go func() {
		wg.Wait()
		close(done)
	}()

	select {
	case <-done:
		logger.Info("All listeners stopped gracefully")
	case <-shutdownCtx.Done():
		logger.Warn("Shutdown timed out, forcing exit")
	}
}

func startHealthServer(ctx context.Context, addr string, ds *store.DataStore, logger *zap.Logger) {
	mux := http.NewServeMux()
	mux.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		if err := ds.Ping(ctx); err != nil {
			w.WriteHeader(http.StatusServiceUnavailable)
			fmt.Fprintf(w, `{"status":"unhealthy","error":"%s"}`, err.Error())
			return
		}
		w.WriteHeader(http.StatusOK)
		fmt.Fprint(w, `{"status":"healthy","service":"radius-server"}`)
	})
	mux.HandleFunc("/metrics", radiusmetrics.Handler())

	server := &http.Server{Addr: addr, Handler: mux}
	go func() {
		<-ctx.Done()
		server.Shutdown(context.Background())
	}()
	if err := server.ListenAndServe(); err != http.ErrServerClosed {
		logger.Error("Health server error", zap.Error(err))
	}
}
