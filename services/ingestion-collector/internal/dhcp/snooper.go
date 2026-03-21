package dhcp

import (
	"context"
	"fmt"
	"net"
	"strings"
	"sync/atomic"
	"time"

	"github.com/neuranac/services/ingestion-collector/internal/publisher"
	"go.uber.org/zap"
)

// Common DHCP option numbers for fingerprinting
const (
	OptHostname    = 12
	OptVendorClass = 60
	OptParamList   = 55
	OptMsgType     = 53
	OptClientID    = 61
)

// DHCP message types
var msgTypes = map[byte]string{
	1: "DISCOVER", 2: "OFFER", 3: "REQUEST", 4: "DECLINE",
	5: "ACK", 6: "NAK", 7: "RELEASE", 8: "INFORM",
}

// Well-known DHCP fingerprints (option 55 parameter request list)
// Maps hex-encoded option 55 values to OS/device type
var knownFingerprints = map[string]string{
	"01,1c,02,03,0f,06,77,0c,2c,2f,1a,79,2a": "Windows 10/11",
	"01,03,06,0f,1f,21,2b,2c,2e,2f,79":       "macOS",
	"01,03,06,0c,0f,1c,28,29,2a":              "Linux (dhclient)",
	"01,03,06,0c,0f,1c":                        "Android",
	"01,03,06,0f,77,fc":                         "iOS/iPadOS",
	"01,03,06,0c,0f,2c,2e,2f":                  "Chrome OS",
	"01,03,06,0c,0f":                            "Cisco IP Phone",
	"01,03,06":                                   "Embedded/IoT",
}

// Snooper listens for DHCP packets and extracts fingerprinting data.
type Snooper struct {
	port   int
	pub    *publisher.Publisher
	logger *zap.Logger
	siteID string
	nodeID string

	received      atomic.Int64
	fingerprinted atomic.Int64
}

// NewSnooper creates a new DHCP snooper.
func NewSnooper(port int, siteID, nodeID string, pub *publisher.Publisher, logger *zap.Logger) *Snooper {
	return &Snooper{
		port:   port,
		pub:    pub,
		logger: logger,
		siteID: siteID,
		nodeID: nodeID,
	}
}

// ListenAndServe starts the UDP DHCP snooping listener. Blocks until ctx is cancelled.
func (s *Snooper) ListenAndServe(ctx context.Context) error {
	addr := fmt.Sprintf(":%d", s.port)
	conn, err := net.ListenPacket("udp", addr)
	if err != nil {
		return fmt.Errorf("listen UDP %s: %w", addr, err)
	}
	defer conn.Close()

	s.logger.Info("DHCP snooper started", zap.String("addr", addr))

	go func() {
		<-ctx.Done()
		conn.Close()
	}()

	buf := make([]byte, 1500)
	for {
		n, remoteAddr, err := conn.ReadFrom(buf)
		if err != nil {
			if ctx.Err() != nil {
				return nil
			}
			s.logger.Error("Read DHCP packet", zap.Error(err))
			continue
		}
		s.received.Add(1)

		go s.handlePacket(buf[:n], remoteAddr)
	}
}

// handlePacket parses a DHCP packet and extracts fingerprinting info.
func (s *Snooper) handlePacket(data []byte, remote net.Addr) {
	sourceIP := strings.Split(remote.String(), ":")[0]

	// DHCP packet minimum: 240 bytes (236 fixed + 4 magic cookie)
	if len(data) < 240 {
		return
	}

	// Validate DHCP magic cookie at offset 236
	if data[236] != 99 || data[237] != 130 || data[238] != 83 || data[239] != 99 {
		return
	}

	// Extract client MAC from offset 28 (chaddr, 6 bytes for Ethernet)
	mac := fmt.Sprintf("%02x:%02x:%02x:%02x:%02x:%02x",
		data[28], data[29], data[30], data[31], data[32], data[33])

	// Extract client IP (yiaddr) from offset 16
	clientIP := fmt.Sprintf("%d.%d.%d.%d", data[16], data[17], data[18], data[19])

	// Parse DHCP options starting at offset 240
	options := parseDHCPOptions(data[240:])

	hostname := ""
	if v, ok := options[OptHostname]; ok {
		hostname = string(v)
	}

	vendorClass := ""
	if v, ok := options[OptVendorClass]; ok {
		vendorClass = string(v)
	}

	fingerprint := ""
	osGuess := "Unknown"
	if v, ok := options[OptParamList]; ok {
		parts := make([]string, len(v))
		for i, b := range v {
			parts[i] = fmt.Sprintf("%02x", b)
		}
		fingerprint = strings.Join(parts, ",")

		// Match against known fingerprints
		for pattern, os := range knownFingerprints {
			if fingerprint == pattern {
				osGuess = os
				break
			}
		}
	}

	msgType := "UNKNOWN"
	if v, ok := options[OptMsgType]; ok && len(v) > 0 {
		if name, ok := msgTypes[v[0]]; ok {
			msgType = name
		}
	}

	s.fingerprinted.Add(1)

	event := publisher.TelemetryEvent{
		ID:        fmt.Sprintf("dhcp-%s-%d", mac, time.Now().UnixNano()),
		Type:      "dhcp",
		Source:    sourceIP,
		Timestamp: time.Now().UTC(),
		SiteID:    s.siteID,
		NodeID:    s.nodeID,
		Data: map[string]interface{}{
			"mac":          mac,
			"client_ip":    clientIP,
			"hostname":     hostname,
			"vendor_class": vendorClass,
			"fingerprint":  fingerprint,
			"os_guess":     osGuess,
			"msg_type":     msgType,
		},
	}

	s.pub.Publish(event)
	s.logger.Debug("DHCP fingerprint captured",
		zap.String("mac", mac),
		zap.String("os", osGuess),
		zap.String("hostname", hostname),
	)
}

// parseDHCPOptions extracts option code → value from DHCP options bytes.
func parseDHCPOptions(data []byte) map[byte][]byte {
	opts := make(map[byte][]byte)
	i := 0
	for i < len(data) {
		code := data[i]
		if code == 255 { // End option
			break
		}
		if code == 0 { // Padding
			i++
			continue
		}
		if i+1 >= len(data) {
			break
		}
		length := int(data[i+1])
		i += 2
		if i+length > len(data) {
			break
		}
		value := make([]byte, length)
		copy(value, data[i:i+length])
		opts[code] = value
		i += length
	}
	return opts
}

// Stats returns DHCP snooper statistics.
func (s *Snooper) Stats() map[string]int64 {
	return map[string]int64{
		"received":      s.received.Load(),
		"fingerprinted": s.fingerprinted.Load(),
	}
}
