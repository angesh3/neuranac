package publisher

import (
	"context"
	"encoding/json"
	"fmt"
	"sync"
	"time"

	"github.com/neuranac/services/ingestion-collector/internal/config"
	"github.com/nats-io/nats.go"
	"go.uber.org/zap"
)

// TelemetryEvent is the common envelope for all ingested telemetry.
type TelemetryEvent struct {
	ID        string                 `json:"id"`
	Type      string                 `json:"type"` // snmp_trap, syslog, netflow, dhcp, neighbor
	Source    string                 `json:"source"`
	Timestamp time.Time             `json:"timestamp"`
	SiteID    string                 `json:"site_id"`
	NodeID    string                 `json:"node_id"`
	Data      map[string]interface{} `json:"data"`
}

// Publisher batches and publishes telemetry events to NATS JetStream.
type Publisher struct {
	nc     *nats.Conn
	js     nats.JetStreamContext
	cfg    *config.Config
	logger *zap.Logger

	mu      sync.Mutex
	batch   []TelemetryEvent
	stopCh  chan struct{}
	stopped bool

	// Metrics
	Published int64
	Errors    int64
}

// New creates a Publisher connected to NATS JetStream.
func New(cfg *config.Config, logger *zap.Logger) (*Publisher, error) {
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
		nc.Close()
		return nil, fmt.Errorf("create JetStream context: %w", err)
	}

	// Ensure telemetry streams exist
	streams := []struct {
		name     string
		subjects []string
	}{
		{"NeuraNAC_TELEMETRY_SNMP", []string{"neuranac.telemetry.snmp.>"}},
		{"NeuraNAC_TELEMETRY_SYSLOG", []string{"neuranac.telemetry.syslog.>"}},
		{"NeuraNAC_TELEMETRY_NETFLOW", []string{"neuranac.telemetry.netflow.>"}},
		{"NeuraNAC_TELEMETRY_DHCP", []string{"neuranac.telemetry.dhcp.>"}},
		{"NeuraNAC_TELEMETRY_NEIGHBOR", []string{"neuranac.telemetry.neighbor.>"}},
	}

	for _, s := range streams {
		_, err := js.AddStream(&nats.StreamConfig{
			Name:       s.name,
			Subjects:   s.subjects,
			Retention:  nats.LimitsPolicy,
			MaxAge:     72 * time.Hour,
			MaxBytes:   10 * 1024 * 1024 * 1024, // 10 GB
			Replicas:   1,
			Discard:    nats.DiscardOld,
			Storage:    nats.FileStorage,
			Duplicates: 5 * time.Minute,
		})
		if err != nil {
			logger.Warn("Stream create/update", zap.String("stream", s.name), zap.Error(err))
		}
	}

	p := &Publisher{
		nc:     nc,
		js:     js,
		cfg:    cfg,
		logger: logger,
		batch:  make([]TelemetryEvent, 0, cfg.BatchSize),
		stopCh: make(chan struct{}),
	}

	go p.flushLoop()

	logger.Info("Publisher connected to NATS JetStream", zap.String("url", cfg.NatsURL))
	return p, nil
}

// Publish adds an event to the batch for async publishing.
func (p *Publisher) Publish(event TelemetryEvent) {
	p.mu.Lock()
	defer p.mu.Unlock()
	if p.stopped {
		return
	}
	p.batch = append(p.batch, event)
	if len(p.batch) >= p.cfg.BatchSize {
		p.flushLocked()
	}
}

// PublishDirect immediately publishes a single event (for high-priority items).
func (p *Publisher) PublishDirect(ctx context.Context, event TelemetryEvent) error {
	subject := fmt.Sprintf("neuranac.telemetry.%s.%s", event.Type, event.Source)
	data, err := json.Marshal(event)
	if err != nil {
		return fmt.Errorf("marshal event: %w", err)
	}
	_, err = p.js.Publish(subject, data, nats.MsgId(event.ID))
	if err != nil {
		p.Errors++
		return fmt.Errorf("publish to %s: %w", subject, err)
	}
	p.Published++
	return nil
}

func (p *Publisher) flushLoop() {
	ticker := time.NewTicker(time.Duration(p.cfg.FlushInterval) * time.Millisecond)
	defer ticker.Stop()
	for {
		select {
		case <-ticker.C:
			p.mu.Lock()
			p.flushLocked()
			p.mu.Unlock()
		case <-p.stopCh:
			return
		}
	}
}

// flushLocked sends all batched events to NATS. Must be called with mu held.
func (p *Publisher) flushLocked() {
	if len(p.batch) == 0 {
		return
	}
	for _, event := range p.batch {
		subject := fmt.Sprintf("neuranac.telemetry.%s.%s", event.Type, event.Source)
		data, err := json.Marshal(event)
		if err != nil {
			p.logger.Error("Marshal telemetry event", zap.Error(err))
			p.Errors++
			continue
		}
		_, err = p.js.Publish(subject, data, nats.MsgId(event.ID))
		if err != nil {
			p.logger.Error("Publish telemetry event", zap.String("subject", subject), zap.Error(err))
			p.Errors++
			continue
		}
		p.Published++
	}
	p.logger.Debug("Flushed telemetry batch", zap.Int("count", len(p.batch)))
	p.batch = p.batch[:0]
}

// Close flushes remaining events and disconnects from NATS.
func (p *Publisher) Close() {
	p.mu.Lock()
	p.stopped = true
	p.flushLocked()
	p.mu.Unlock()
	close(p.stopCh)
	p.nc.Drain()
}

// Stats returns current publish statistics.
func (p *Publisher) Stats() map[string]int64 {
	return map[string]int64{
		"published": p.Published,
		"errors":    p.Errors,
	}
}
