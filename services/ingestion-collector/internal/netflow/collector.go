package netflow

import (
	"context"
	"encoding/binary"
	"fmt"
	"net"
	"strings"
	"sync/atomic"
	"time"

	"github.com/neuranac/services/ingestion-collector/internal/publisher"
	"go.uber.org/zap"
)

// NetFlow v5 header size and record size
const (
	NFv5HeaderSize = 24
	NFv5RecordSize = 48
)

// Collector listens for NetFlow v5/v9 and IPFIX packets on UDP.
type Collector struct {
	port   int
	pub    *publisher.Publisher
	logger *zap.Logger
	siteID string
	nodeID string

	received atomic.Int64
	flows    atomic.Int64
}

// NewCollector creates a new NetFlow/IPFIX collector.
func NewCollector(port int, siteID, nodeID string, pub *publisher.Publisher, logger *zap.Logger) *Collector {
	return &Collector{
		port:   port,
		pub:    pub,
		logger: logger,
		siteID: siteID,
		nodeID: nodeID,
	}
}

// ListenAndServe starts the UDP NetFlow listener. Blocks until ctx is cancelled.
func (c *Collector) ListenAndServe(ctx context.Context) error {
	addr := fmt.Sprintf(":%d", c.port)
	conn, err := net.ListenPacket("udp", addr)
	if err != nil {
		return fmt.Errorf("listen UDP %s: %w", addr, err)
	}
	defer conn.Close()

	c.logger.Info("NetFlow/IPFIX collector started", zap.String("addr", addr))

	go func() {
		<-ctx.Done()
		conn.Close()
	}()

	buf := make([]byte, 65535)
	for {
		n, remoteAddr, err := conn.ReadFrom(buf)
		if err != nil {
			if ctx.Err() != nil {
				return nil
			}
			c.logger.Error("Read NetFlow packet", zap.Error(err))
			continue
		}
		c.received.Add(1)

		go c.handlePacket(buf[:n], remoteAddr)
	}
}

// handlePacket dispatches based on NetFlow version.
func (c *Collector) handlePacket(data []byte, remote net.Addr) {
	sourceIP := strings.Split(remote.String(), ":")[0]

	if len(data) < 4 {
		return
	}

	version := binary.BigEndian.Uint16(data[0:2])

	switch version {
	case 5:
		c.handleNetFlowV5(data, sourceIP)
	case 9:
		c.handleNetFlowV9(data, sourceIP)
	case 10:
		c.handleIPFIX(data, sourceIP)
	default:
		c.logger.Debug("Unknown NetFlow version", zap.Uint16("version", version), zap.String("source", sourceIP))
	}
}

// handleNetFlowV5 parses NetFlow v5 packets and publishes flow records.
func (c *Collector) handleNetFlowV5(data []byte, sourceIP string) {
	if len(data) < NFv5HeaderSize {
		return
	}

	count := int(binary.BigEndian.Uint16(data[2:4]))
	sysUptime := binary.BigEndian.Uint32(data[4:8])
	unixSecs := binary.BigEndian.Uint32(data[8:12])

	expectedLen := NFv5HeaderSize + count*NFv5RecordSize
	if len(data) < expectedLen {
		c.logger.Debug("Truncated NetFlow v5 packet",
			zap.Int("expected", expectedLen),
			zap.Int("got", len(data)),
		)
		return
	}

	for i := 0; i < count; i++ {
		offset := NFv5HeaderSize + i*NFv5RecordSize
		rec := data[offset : offset+NFv5RecordSize]

		srcIP := fmt.Sprintf("%d.%d.%d.%d", rec[0], rec[1], rec[2], rec[3])
		dstIP := fmt.Sprintf("%d.%d.%d.%d", rec[4], rec[5], rec[6], rec[7])
		nextHop := fmt.Sprintf("%d.%d.%d.%d", rec[8], rec[9], rec[10], rec[11])
		packets := binary.BigEndian.Uint32(rec[16:20])
		bytes := binary.BigEndian.Uint32(rec[20:24])
		srcPort := binary.BigEndian.Uint16(rec[32:34])
		dstPort := binary.BigEndian.Uint16(rec[34:36])
		proto := rec[38]
		tos := rec[39]

		c.flows.Add(1)

		event := publisher.TelemetryEvent{
			ID:        fmt.Sprintf("nf5-%s-%d-%d", sourceIP, time.Now().UnixNano(), i),
			Type:      "netflow",
			Source:    sourceIP,
			Timestamp: time.Unix(int64(unixSecs), 0).UTC(),
			SiteID:    c.siteID,
			NodeID:    c.nodeID,
			Data: map[string]interface{}{
				"version":    5,
				"src_ip":     srcIP,
				"dst_ip":     dstIP,
				"next_hop":   nextHop,
				"packets":    packets,
				"bytes":      bytes,
				"src_port":   srcPort,
				"dst_port":   dstPort,
				"protocol":   proto,
				"tos":        tos,
				"sys_uptime": sysUptime,
			},
		}

		c.pub.Publish(event)
	}

	c.logger.Debug("NetFlow v5 packet processed",
		zap.String("source", sourceIP),
		zap.Int("flows", count),
	)
}

// handleNetFlowV9 parses NetFlow v9 header and publishes a summary event.
func (c *Collector) handleNetFlowV9(data []byte, sourceIP string) {
	if len(data) < 20 {
		return
	}

	count := binary.BigEndian.Uint16(data[2:4])
	sourceID := binary.BigEndian.Uint32(data[16:20])
	c.flows.Add(int64(count))

	event := publisher.TelemetryEvent{
		ID:        fmt.Sprintf("nf9-%s-%d", sourceIP, time.Now().UnixNano()),
		Type:      "netflow",
		Source:    sourceIP,
		Timestamp: time.Now().UTC(),
		SiteID:    c.siteID,
		NodeID:    c.nodeID,
		Data: map[string]interface{}{
			"version":   9,
			"count":     count,
			"source_id": sourceID,
			"raw_bytes": len(data),
		},
	}

	c.pub.Publish(event)
}

// handleIPFIX parses IPFIX (NetFlow v10) header and publishes a summary event.
func (c *Collector) handleIPFIX(data []byte, sourceIP string) {
	if len(data) < 16 {
		return
	}

	length := binary.BigEndian.Uint16(data[2:4])
	exportTime := binary.BigEndian.Uint32(data[4:8])
	seqNum := binary.BigEndian.Uint32(data[8:12])
	domainID := binary.BigEndian.Uint32(data[12:16])
	c.flows.Add(1)

	event := publisher.TelemetryEvent{
		ID:        fmt.Sprintf("ipfix-%s-%d", sourceIP, time.Now().UnixNano()),
		Type:      "netflow",
		Source:    sourceIP,
		Timestamp: time.Unix(int64(exportTime), 0).UTC(),
		SiteID:    c.siteID,
		NodeID:    c.nodeID,
		Data: map[string]interface{}{
			"version":     10,
			"length":      length,
			"export_time": exportTime,
			"sequence":    seqNum,
			"domain_id":   domainID,
			"raw_bytes":   len(data),
		},
	}

	c.pub.Publish(event)
}

// Stats returns NetFlow collector statistics.
func (c *Collector) Stats() map[string]int64 {
	return map[string]int64{
		"received": c.received.Load(),
		"flows":    c.flows.Load(),
	}
}
