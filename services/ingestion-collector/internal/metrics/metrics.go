package metrics

import (
	"fmt"
	"net/http"
	"sync"
)

// Collector holds counters for all ingestion channels.
type Collector struct {
	mu       sync.RWMutex
	counters map[string]map[string]int64
}

// Global metrics collector
var Global = &Collector{
	counters: make(map[string]map[string]int64),
}

// Set updates a named counter for a channel.
func (c *Collector) Set(channel, key string, value int64) {
	c.mu.Lock()
	defer c.mu.Unlock()
	if c.counters[channel] == nil {
		c.counters[channel] = make(map[string]int64)
	}
	c.counters[channel][key] = value
}

// Inc increments a named counter for a channel by 1.
func (c *Collector) Inc(channel, key string) {
	c.mu.Lock()
	defer c.mu.Unlock()
	if c.counters[channel] == nil {
		c.counters[channel] = make(map[string]int64)
	}
	c.counters[channel][key]++
}

// Snapshot returns a copy of all counters.
func (c *Collector) Snapshot() map[string]map[string]int64 {
	c.mu.RLock()
	defer c.mu.RUnlock()
	snap := make(map[string]map[string]int64)
	for ch, kv := range c.counters {
		snap[ch] = make(map[string]int64)
		for k, v := range kv {
			snap[ch][k] = v
		}
	}
	return snap
}

// Handler returns an HTTP handler that serves Prometheus-style metrics.
func Handler() http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		snap := Global.Snapshot()
		w.Header().Set("Content-Type", "text/plain; charset=utf-8")
		for channel, kv := range snap {
			for key, value := range kv {
				fmt.Fprintf(w, "neuranac_ingestion_%s_%s %d\n", channel, key, value)
			}
		}
	}
}
