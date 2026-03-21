package snmp

import (
	"context"
	"encoding/hex"
	"fmt"
	"net"
	"strings"
	"sync/atomic"
	"time"

	"github.com/neuranac/services/ingestion-collector/internal/publisher"
	"go.uber.org/zap"
)

// Well-known SNMP trap OIDs
var knownOIDs = map[string]string{
	"1.3.6.1.6.3.1.1.5.3": "linkDown",
	"1.3.6.1.6.3.1.1.5.4": "linkUp",
	"1.3.6.1.4.1.9.9.599":  "dot1xAuthFail",
	"1.3.6.1.6.3.1.1.5.5": "authenticationFailure",
	"1.3.6.1.4.1.9.9.315":  "macNotification",
	"1.3.6.1.4.1.9.9.43":   "configChange",
	"1.3.6.1.6.3.1.1.5.1": "coldStart",
	"1.3.6.1.6.3.1.1.5.2": "warmStart",
}

// CDP/LLDP OIDs for neighbor discovery polling
var NeighborOIDs = map[string]string{
	"cdpCacheDeviceId":  "1.3.6.1.4.1.9.9.23.1.2.1.1.6",
	"cdpCachePlatform":  "1.3.6.1.4.1.9.9.23.1.2.1.1.8",
	"cdpCacheAddress":   "1.3.6.1.4.1.9.9.23.1.2.1.1.4",
	"lldpRemSysName":    "1.0.8802.1.1.2.1.4.1.1.9",
	"lldpRemPortId":     "1.0.8802.1.1.2.1.4.1.1.7",
	"lldpRemSysDesc":    "1.0.8802.1.1.2.1.4.1.1.10",
}

// TrapReceiver listens for SNMP v2c/v3 trap packets on UDP.
type TrapReceiver struct {
	port      int
	community string
	pub       *publisher.Publisher
	logger    *zap.Logger
	siteID    string
	nodeID    string
	received  atomic.Int64
	parsed    atomic.Int64
}

// NewTrapReceiver creates a new SNMP trap receiver.
func NewTrapReceiver(port int, community, siteID, nodeID string, pub *publisher.Publisher, logger *zap.Logger) *TrapReceiver {
	return &TrapReceiver{
		port:      port,
		community: community,
		pub:       pub,
		logger:    logger,
		siteID:    siteID,
		nodeID:    nodeID,
	}
}

// ListenAndServe starts the UDP trap listener. Blocks until ctx is cancelled.
func (t *TrapReceiver) ListenAndServe(ctx context.Context) error {
	addr := fmt.Sprintf(":%d", t.port)
	conn, err := net.ListenPacket("udp", addr)
	if err != nil {
		return fmt.Errorf("listen UDP %s: %w", addr, err)
	}
	defer conn.Close()

	t.logger.Info("SNMP Trap receiver started", zap.String("addr", addr))

	go func() {
		<-ctx.Done()
		conn.Close()
	}()

	buf := make([]byte, 65535)
	for {
		n, remoteAddr, err := conn.ReadFrom(buf)
		if err != nil {
			if ctx.Err() != nil {
				return nil // Context cancelled — clean shutdown
			}
			t.logger.Error("Read UDP packet", zap.Error(err))
			continue
		}
		t.received.Add(1)

		go t.handleTrap(buf[:n], remoteAddr)
	}
}

// handleTrap parses a raw SNMP trap packet and publishes a TelemetryEvent.
func (t *TrapReceiver) handleTrap(data []byte, remote net.Addr) {
	sourceIP := strings.Split(remote.String(), ":")[0]

	// Parse SNMPv2c trap (simplified BER/ASN.1 extraction)
	trapInfo := t.parseSNMPv2cTrap(data)
	if trapInfo == nil {
		t.logger.Debug("Unparseable SNMP packet", zap.String("source", sourceIP), zap.Int("bytes", len(data)))
		return
	}
	t.parsed.Add(1)

	eventType := "unknown"
	if name, ok := knownOIDs[trapInfo["trap_oid"]]; ok {
		eventType = name
	}

	event := publisher.TelemetryEvent{
		ID:        fmt.Sprintf("snmp-%s-%d", sourceIP, time.Now().UnixNano()),
		Type:      "snmp",
		Source:    sourceIP,
		Timestamp: time.Now().UTC(),
		SiteID:    t.siteID,
		NodeID:    t.nodeID,
		Data: map[string]interface{}{
			"trap_type":  eventType,
			"trap_oid":   trapInfo["trap_oid"],
			"community":  trapInfo["community"],
			"varbinds":   trapInfo["varbinds"],
			"raw_length": len(data),
		},
	}

	t.pub.Publish(event)
	t.logger.Debug("SNMP trap received",
		zap.String("source", sourceIP),
		zap.String("type", eventType),
	)
}

// parseSNMPv2cTrap performs minimal BER/ASN.1 parsing of an SNMPv2c trap PDU.
// Returns nil if the packet is not a valid SNMPv2c trap.
func (t *TrapReceiver) parseSNMPv2cTrap(data []byte) map[string]string {
	if len(data) < 20 {
		return nil
	}

	// SNMP messages start with SEQUENCE (0x30)
	if data[0] != 0x30 {
		return nil
	}

	result := map[string]string{
		"trap_oid":  "",
		"community": "",
		"varbinds":  "",
	}

	// Extract community string (simplified — skip version, read community)
	idx := 2
	if data[1] > 0x80 {
		lenBytes := int(data[1] & 0x7f)
		idx = 2 + lenBytes
	}

	// Version field: INTEGER (0x02)
	if idx < len(data) && data[idx] == 0x02 {
		vlen := int(data[idx+1])
		idx += 2 + vlen
	}

	// Community string: OCTET STRING (0x04)
	if idx < len(data) && data[idx] == 0x04 {
		clen := int(data[idx+1])
		idx += 2
		if idx+clen <= len(data) {
			result["community"] = string(data[idx : idx+clen])
			idx += clen
		}
	}

	// SNMPv2-Trap PDU type: 0xa7
	if idx < len(data) && data[idx] == 0xa7 {
		// This is an SNMPv2c trap — extract the snmpTrapOID from varbinds
		// For simplicity, scan for OID patterns in the remaining data
		remaining := data[idx:]
		result["trap_oid"] = extractFirstOID(remaining)
		result["varbinds"] = hex.EncodeToString(remaining[:min(64, len(remaining))])
	}

	if result["trap_oid"] == "" && result["community"] == "" {
		return nil
	}

	return result
}

// extractFirstOID scans bytes for an OID (tag 0x06) and returns a dotted string.
func extractFirstOID(data []byte) string {
	for i := 0; i < len(data)-2; i++ {
		if data[i] == 0x06 { // OID tag
			oidLen := int(data[i+1])
			if i+2+oidLen <= len(data) && oidLen > 0 {
				return decodeOID(data[i+2 : i+2+oidLen])
			}
		}
	}
	return ""
}

// decodeOID converts BER-encoded OID bytes to dotted notation.
func decodeOID(raw []byte) string {
	if len(raw) == 0 {
		return ""
	}
	parts := []string{
		fmt.Sprintf("%d", raw[0]/40),
		fmt.Sprintf("%d", raw[0]%40),
	}
	val := 0
	for _, b := range raw[1:] {
		val = val<<7 | int(b&0x7f)
		if b&0x80 == 0 {
			parts = append(parts, fmt.Sprintf("%d", val))
			val = 0
		}
	}
	return strings.Join(parts, ".")
}

// Stats returns trap receiver statistics.
func (t *TrapReceiver) Stats() map[string]int64 {
	return map[string]int64{
		"received": t.received.Load(),
		"parsed":   t.parsed.Load(),
	}
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}
