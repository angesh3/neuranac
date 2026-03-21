package main

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"os/signal"
	"sync"
	"syscall"
	"time"

	"github.com/neuranac/services/ingestion-collector/internal/config"
	"github.com/neuranac/services/ingestion-collector/internal/dhcp"
	"github.com/neuranac/services/ingestion-collector/internal/discovery"
	collectormetrics "github.com/neuranac/services/ingestion-collector/internal/metrics"
	"github.com/neuranac/services/ingestion-collector/internal/netflow"
	"github.com/neuranac/services/ingestion-collector/internal/publisher"
	"github.com/neuranac/services/ingestion-collector/internal/snmp"
	"github.com/neuranac/services/ingestion-collector/internal/syslog"
	"go.uber.org/zap"
)

func main() {
	// Initialize logger
	logger, _ := zap.NewProduction()
	if os.Getenv("NeuraNAC_ENV") == "development" {
		logger, _ = zap.NewDevelopment()
	}
	defer logger.Sync()

	logger.Info("Starting NeuraNAC Ingestion Collector",
		zap.String("version", "1.0.0"),
		zap.String("node_id", os.Getenv("NEURANAC_NODE_ID")),
	)

	// Load configuration
	cfg, err := config.Load()
	if err != nil {
		logger.Fatal("Failed to load configuration", zap.Error(err))
	}

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	// Initialize NATS publisher
	pub, err := publisher.New(cfg, logger)
	if err != nil {
		logger.Fatal("Failed to initialize publisher", zap.Error(err))
	}
	defer pub.Close()

	var wg sync.WaitGroup

	// Start SNMP Trap Receiver (UDP 1162)
	trapReceiver := snmp.NewTrapReceiver(cfg.SNMPTrapPort, cfg.SNMPCommunity, cfg.SiteID, cfg.NodeID, pub, logger)
	wg.Add(1)
	go func() {
		defer wg.Done()
		logger.Info("Starting SNMP Trap receiver", zap.Int("port", cfg.SNMPTrapPort))
		if err := trapReceiver.ListenAndServe(ctx); err != nil {
			logger.Error("SNMP Trap receiver error", zap.Error(err))
		}
	}()

	// Start Syslog Receiver (UDP 1514)
	syslogReceiver := syslog.NewReceiver(cfg.SyslogPort, cfg.SiteID, cfg.NodeID, pub, logger)
	wg.Add(1)
	go func() {
		defer wg.Done()
		logger.Info("Starting Syslog receiver", zap.Int("port", cfg.SyslogPort))
		if err := syslogReceiver.ListenAndServe(ctx); err != nil {
			logger.Error("Syslog receiver error", zap.Error(err))
		}
	}()

	// Start NetFlow/IPFIX Collector (UDP 2055)
	netflowCollector := netflow.NewCollector(cfg.NetFlowPort, cfg.SiteID, cfg.NodeID, pub, logger)
	wg.Add(1)
	go func() {
		defer wg.Done()
		logger.Info("Starting NetFlow/IPFIX collector", zap.Int("port", cfg.NetFlowPort))
		if err := netflowCollector.ListenAndServe(ctx); err != nil {
			logger.Error("NetFlow collector error", zap.Error(err))
		}
	}()

	// Start DHCP Snooper (UDP 6767)
	dhcpSnooper := dhcp.NewSnooper(cfg.DHCPPort, cfg.SiteID, cfg.NodeID, pub, logger)
	wg.Add(1)
	go func() {
		defer wg.Done()
		logger.Info("Starting DHCP snooper", zap.Int("port", cfg.DHCPPort))
		if err := dhcpSnooper.ListenAndServe(ctx); err != nil {
			logger.Error("DHCP snooper error", zap.Error(err))
		}
	}()

	// Start CDP/LLDP Neighbor Discovery (SNMP polling)
	neighborDiscovery := discovery.NewNeighborDiscovery(
		cfg.SNMPPollInterval, cfg.SNMPCommunity, cfg.SiteID, cfg.NodeID, pub, logger,
	)
	wg.Add(1)
	go func() {
		defer wg.Done()
		logger.Info("Starting neighbor discovery", zap.Int("interval_sec", cfg.SNMPPollInterval))
		if err := neighborDiscovery.Run(ctx); err != nil {
			logger.Error("Neighbor discovery error", zap.Error(err))
		}
	}()

	// Start health + metrics endpoint
	wg.Add(1)
	go func() {
		defer wg.Done()
		healthAddr := fmt.Sprintf(":%d", cfg.HealthPort)
		logger.Info("Starting health/metrics endpoint", zap.String("addr", healthAddr))
		startHealthServer(ctx, healthAddr, pub, trapReceiver, syslogReceiver, netflowCollector, dhcpSnooper, neighborDiscovery, logger)
	}()

	// Wait for shutdown signal
	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, syscall.SIGINT, syscall.SIGTERM)
	sig := <-sigCh
	logger.Info("Received shutdown signal", zap.String("signal", sig.String()))

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
		logger.Info("All collectors stopped gracefully")
	case <-shutdownCtx.Done():
		logger.Warn("Shutdown timed out, forcing exit")
	}
}

func startHealthServer(
	ctx context.Context,
	addr string,
	pub *publisher.Publisher,
	trapRx *snmp.TrapReceiver,
	syslogRx *syslog.Receiver,
	nfCollector *netflow.Collector,
	dhcpSnoop *dhcp.Snooper,
	neighborDisc *discovery.NeighborDiscovery,
	logger *zap.Logger,
) {
	mux := http.NewServeMux()

	// Health endpoint
	mux.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		json.NewEncoder(w).Encode(map[string]interface{}{
			"status":  "healthy",
			"service": "ingestion-collector",
			"version": "1.0.0",
		})
	})

	// Detailed stats endpoint
	mux.HandleFunc("/stats", func(w http.ResponseWriter, r *http.Request) {
		stats := map[string]interface{}{
			"publisher": pub.Stats(),
			"snmp":      trapRx.Stats(),
			"syslog":    syslogRx.Stats(),
			"netflow":   nfCollector.Stats(),
			"dhcp":      dhcpSnoop.Stats(),
			"neighbor":  neighborDisc.Stats(),
		}

		// Update global metrics
		for channel, channelStats := range stats {
			if m, ok := channelStats.(map[string]int64); ok {
				for key, val := range m {
					collectormetrics.Global.Set(channel, key, val)
				}
			}
		}

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(stats)
	})

	// Prometheus-style metrics
	mux.HandleFunc("/metrics", collectormetrics.Handler())

	server := &http.Server{Addr: addr, Handler: mux}
	go func() {
		<-ctx.Done()
		server.Shutdown(context.Background())
	}()
	if err := server.ListenAndServe(); err != http.ErrServerClosed {
		logger.Error("Health server error", zap.Error(err))
	}
}
