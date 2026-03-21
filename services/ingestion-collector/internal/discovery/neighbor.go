package discovery

import (
	"context"
	"fmt"
	"sync/atomic"
	"time"

	"github.com/neuranac/services/ingestion-collector/internal/publisher"
	"go.uber.org/zap"
)

// NeighborEntry represents a discovered CDP/LLDP neighbor.
type NeighborEntry struct {
	LocalDevice  string `json:"local_device"`
	LocalPort    string `json:"local_port"`
	RemoteDevice string `json:"remote_device"`
	RemotePort   string `json:"remote_port"`
	Platform     string `json:"platform"`
	IPAddress    string `json:"ip_address"`
	Protocol     string `json:"protocol"` // "cdp" or "lldp"
}

// NeighborDiscovery periodically polls NADs via SNMP to build topology.
type NeighborDiscovery struct {
	pollInterval time.Duration
	community    string
	pub          *publisher.Publisher
	logger       *zap.Logger
	siteID       string
	nodeID       string

	// Registry of NAD IPs to poll (loaded from DB or config)
	targets []string

	polled     atomic.Int64
	discovered atomic.Int64
}

// NewNeighborDiscovery creates a new neighbor discovery poller.
func NewNeighborDiscovery(pollIntervalSec int, community, siteID, nodeID string, pub *publisher.Publisher, logger *zap.Logger) *NeighborDiscovery {
	return &NeighborDiscovery{
		pollInterval: time.Duration(pollIntervalSec) * time.Second,
		community:    community,
		pub:          pub,
		logger:       logger,
		siteID:       siteID,
		nodeID:       nodeID,
		targets:      []string{},
	}
}

// SetTargets updates the list of NAD IPs to poll for neighbor data.
func (nd *NeighborDiscovery) SetTargets(targets []string) {
	nd.targets = targets
	nd.logger.Info("Updated neighbor discovery targets", zap.Int("count", len(targets)))
}

// Run starts the periodic polling loop. Blocks until ctx is cancelled.
func (nd *NeighborDiscovery) Run(ctx context.Context) error {
	nd.logger.Info("Neighbor discovery started",
		zap.Duration("interval", nd.pollInterval),
		zap.Int("targets", len(nd.targets)),
	)

	// Initial poll
	nd.pollAll(ctx)

	ticker := time.NewTicker(nd.pollInterval)
	defer ticker.Stop()

	for {
		select {
		case <-ticker.C:
			nd.pollAll(ctx)
		case <-ctx.Done():
			return nil
		}
	}
}

// pollAll queries all registered NADs for CDP/LLDP neighbor tables.
func (nd *NeighborDiscovery) pollAll(ctx context.Context) {
	if len(nd.targets) == 0 {
		return
	}

	nd.logger.Debug("Starting neighbor discovery poll", zap.Int("targets", len(nd.targets)))

	for _, target := range nd.targets {
		select {
		case <-ctx.Done():
			return
		default:
		}

		neighbors := nd.pollDevice(target)
		nd.polled.Add(1)

		for _, n := range neighbors {
			nd.discovered.Add(1)

			event := publisher.TelemetryEvent{
				ID:        fmt.Sprintf("neighbor-%s-%s-%d", target, n.RemoteDevice, time.Now().UnixNano()),
				Type:      "neighbor",
				Source:    target,
				Timestamp: time.Now().UTC(),
				SiteID:    nd.siteID,
				NodeID:    nd.nodeID,
				Data: map[string]interface{}{
					"local_device":  n.LocalDevice,
					"local_port":    n.LocalPort,
					"remote_device": n.RemoteDevice,
					"remote_port":   n.RemotePort,
					"platform":      n.Platform,
					"ip_address":    n.IPAddress,
					"protocol":      n.Protocol,
				},
			}

			nd.pub.Publish(event)
		}
	}
}

// pollDevice queries a single NAD for CDP/LLDP neighbor data via SNMP.
// This is a simplified implementation — production would use gosnmp library.
func (nd *NeighborDiscovery) pollDevice(target string) []NeighborEntry {
	// In production, this would:
	// 1. SNMP GET-BULK on cdpCacheDeviceId (1.3.6.1.4.1.9.9.23.1.2.1.1.6)
	// 2. SNMP GET-BULK on lldpRemSysName (1.0.8802.1.1.2.1.4.1.1.9)
	// 3. Correlate with interface index to get port names
	//
	// For now, we log the poll attempt and return empty.
	// The actual SNMP walk will be implemented when gosnmp is added as a dependency.

	nd.logger.Debug("Polling device for neighbors",
		zap.String("target", target),
		zap.String("community", nd.community),
	)

	// Placeholder: actual SNMP polling implementation
	// Uses SNMPv2c GET-BULK or SNMPv3 with credentials from config
	return []NeighborEntry{}
}

// Stats returns neighbor discovery statistics.
func (nd *NeighborDiscovery) Stats() map[string]int64 {
	return map[string]int64{
		"polled":     nd.polled.Load(),
		"discovered": nd.discovered.Load(),
		"targets":    int64(len(nd.targets)),
	}
}
