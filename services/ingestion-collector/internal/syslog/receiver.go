package syslog

import (
	"context"
	"fmt"
	"net"
	"regexp"
	"strings"
	"sync/atomic"
	"time"

	"github.com/neuranac/services/ingestion-collector/internal/publisher"
	"go.uber.org/zap"
)

// Severity levels per RFC 5424
var severityNames = []string{
	"emergency", "alert", "critical", "error",
	"warning", "notice", "informational", "debug",
}

// Facility names per RFC 5424
var facilityNames = []string{
	"kern", "user", "mail", "daemon", "auth", "syslog", "lpr", "news",
	"uucp", "cron", "authpriv", "ftp", "ntp", "audit", "alert2", "clock",
	"local0", "local1", "local2", "local3", "local4", "local5", "local6", "local7",
}

// RFC 5424 pattern: <PRI>VERSION TIMESTAMP HOSTNAME APP-NAME PROCID MSGID MSG
var rfc5424Re = regexp.MustCompile(`^<(\d{1,3})>(\d?) ?(\S+) (\S+) (\S+) (\S+) (\S+) ?(.*)$`)

// RFC 3164 pattern: <PRI>TIMESTAMP HOSTNAME MSG
var rfc3164Re = regexp.MustCompile(`^<(\d{1,3})>(\w{3}\s+\d{1,2} \d{2}:\d{2}:\d{2}) (\S+) (.*)$`)

// Receiver listens for syslog messages on UDP.
type Receiver struct {
	port   int
	pub    *publisher.Publisher
	logger *zap.Logger
	siteID string
	nodeID string

	received atomic.Int64
	parsed   atomic.Int64
}

// NewReceiver creates a new syslog receiver.
func NewReceiver(port int, siteID, nodeID string, pub *publisher.Publisher, logger *zap.Logger) *Receiver {
	return &Receiver{
		port:   port,
		pub:    pub,
		logger: logger,
		siteID: siteID,
		nodeID: nodeID,
	}
}

// ListenAndServe starts the UDP syslog listener. Blocks until ctx is cancelled.
func (r *Receiver) ListenAndServe(ctx context.Context) error {
	addr := fmt.Sprintf(":%d", r.port)
	conn, err := net.ListenPacket("udp", addr)
	if err != nil {
		return fmt.Errorf("listen UDP %s: %w", addr, err)
	}
	defer conn.Close()

	r.logger.Info("Syslog receiver started", zap.String("addr", addr))

	go func() {
		<-ctx.Done()
		conn.Close()
	}()

	buf := make([]byte, 8192)
	for {
		n, remoteAddr, err := conn.ReadFrom(buf)
		if err != nil {
			if ctx.Err() != nil {
				return nil
			}
			r.logger.Error("Read syslog packet", zap.Error(err))
			continue
		}
		r.received.Add(1)

		go r.handleMessage(buf[:n], remoteAddr)
	}
}

// handleMessage parses a syslog message and publishes it.
func (r *Receiver) handleMessage(data []byte, remote net.Addr) {
	sourceIP := strings.Split(remote.String(), ":")[0]
	msg := strings.TrimSpace(string(data))

	parsed := r.parseSyslog(msg)
	if parsed == nil {
		// Unparseable — still publish as raw
		parsed = map[string]interface{}{
			"raw":      msg,
			"severity": "unknown",
			"facility": "unknown",
			"hostname": sourceIP,
			"message":  msg,
		}
	}
	r.parsed.Add(1)

	event := publisher.TelemetryEvent{
		ID:        fmt.Sprintf("syslog-%s-%d", sourceIP, time.Now().UnixNano()),
		Type:      "syslog",
		Source:    sourceIP,
		Timestamp: time.Now().UTC(),
		SiteID:    r.siteID,
		NodeID:    r.nodeID,
		Data:      parsed,
	}

	r.pub.Publish(event)
	r.logger.Debug("Syslog message received",
		zap.String("source", sourceIP),
		zap.String("severity", fmt.Sprintf("%v", parsed["severity"])),
	)
}

// parseSyslog attempts RFC 5424, then RFC 3164, then raw.
func (r *Receiver) parseSyslog(msg string) map[string]interface{} {
	// Try RFC 5424
	if m := rfc5424Re.FindStringSubmatch(msg); m != nil {
		pri := parsePRI(m[1])
		return map[string]interface{}{
			"format":   "rfc5424",
			"priority": m[1],
			"severity": pri["severity"],
			"facility": pri["facility"],
			"version":  m[2],
			"timestamp": m[3],
			"hostname": m[4],
			"app_name": m[5],
			"proc_id":  m[6],
			"msg_id":   m[7],
			"message":  m[8],
		}
	}

	// Try RFC 3164
	if m := rfc3164Re.FindStringSubmatch(msg); m != nil {
		pri := parsePRI(m[1])
		return map[string]interface{}{
			"format":    "rfc3164",
			"priority":  m[1],
			"severity":  pri["severity"],
			"facility":  pri["facility"],
			"timestamp": m[2],
			"hostname":  m[3],
			"message":   m[4],
		}
	}

	return nil
}

// parsePRI extracts facility and severity from syslog PRI value.
func parsePRI(priStr string) map[string]string {
	pri := 0
	for _, c := range priStr {
		pri = pri*10 + int(c-'0')
	}
	facility := pri / 8
	severity := pri % 8

	facName := "unknown"
	if facility < len(facilityNames) {
		facName = facilityNames[facility]
	}
	sevName := "unknown"
	if severity < len(severityNames) {
		sevName = severityNames[severity]
	}

	return map[string]string{
		"facility": facName,
		"severity": sevName,
	}
}

// Stats returns syslog receiver statistics.
func (r *Receiver) Stats() map[string]int64 {
	return map[string]int64{
		"received": r.received.Load(),
		"parsed":   r.parsed.Load(),
	}
}
