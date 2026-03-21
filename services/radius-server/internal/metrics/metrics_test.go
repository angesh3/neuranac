package metrics

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"
)

func TestMetricsCounters(t *testing.T) {
	m := Get()

	m.AuthRequestsTotal.Add(10)
	m.AuthAcceptsTotal.Add(7)
	m.AuthRejectsTotal.Add(2)
	m.AuthChallengesTotal.Add(1)
	m.AcctRequestsTotal.Add(5)
	m.CoASentTotal.Add(3)
	m.TacacsAuthTotal.Add(4)

	if m.AuthRequestsTotal.Load() != 10 {
		t.Errorf("expected 10 auth requests, got %d", m.AuthRequestsTotal.Load())
	}
	if m.AuthAcceptsTotal.Load() != 7 {
		t.Errorf("expected 7 accepts, got %d", m.AuthAcceptsTotal.Load())
	}
	if m.AuthRejectsTotal.Load() != 2 {
		t.Errorf("expected 2 rejects, got %d", m.AuthRejectsTotal.Load())
	}
}

func TestMetricsGauges(t *testing.T) {
	m := Get()
	m.ActiveEAPSessions.Store(5)
	m.ActiveRadSecConns.Store(2)

	if m.ActiveEAPSessions.Load() != 5 {
		t.Errorf("expected 5 active EAP sessions, got %d", m.ActiveEAPSessions.Load())
	}
	if m.ActiveRadSecConns.Load() != 2 {
		t.Errorf("expected 2 active RadSec conns, got %d", m.ActiveRadSecConns.Load())
	}
}

func TestRecordLatency(t *testing.T) {
	m := Get()
	m.RecordAuthLatency(10 * time.Millisecond)
	m.RecordAuthLatency(50 * time.Millisecond)
	m.RecordAcctLatency(5 * time.Millisecond)
	m.RecordPolicyLatency(2 * time.Millisecond)

	m.mu.Lock()
	if len(m.authLatencies) < 2 {
		t.Errorf("expected at least 2 auth latencies, got %d", len(m.authLatencies))
	}
	if len(m.acctLatencies) < 1 {
		t.Errorf("expected at least 1 acct latency, got %d", len(m.acctLatencies))
	}
	if len(m.policyLatencies) < 1 {
		t.Errorf("expected at least 1 policy latency, got %d", len(m.policyLatencies))
	}
	m.mu.Unlock()
}

func TestMetricsHandler(t *testing.T) {
	// Reset global for clean test output
	m := Get()
	m.AuthRequestsTotal.Store(100)
	m.AuthAcceptsTotal.Store(95)
	m.AuthRejectsTotal.Store(5)
	m.ActiveEAPSessions.Store(3)

	handler := Handler()
	req := httptest.NewRequest(http.MethodGet, "/metrics", nil)
	rec := httptest.NewRecorder()
	handler(rec, req)

	body := rec.Body.String()

	if rec.Code != http.StatusOK {
		t.Errorf("expected 200, got %d", rec.Code)
	}
	if !strings.Contains(body, "radius_auth_requests_total 100") {
		t.Error("missing radius_auth_requests_total")
	}
	if !strings.Contains(body, "radius_auth_accepts_total 95") {
		t.Error("missing radius_auth_accepts_total")
	}
	if !strings.Contains(body, "radius_auth_rejects_total 5") {
		t.Error("missing radius_auth_rejects_total")
	}
	if !strings.Contains(body, "radius_eap_sessions_active 3") {
		t.Error("missing radius_eap_sessions_active")
	}
	if !strings.Contains(body, "radius_auth_duration_seconds") {
		t.Error("missing radius_auth_duration_seconds histogram")
	}
	if !strings.Contains(body, "# TYPE radius_auth_requests_total counter") {
		t.Error("missing TYPE annotation for counter")
	}
	if !strings.Contains(body, "# TYPE radius_eap_sessions_active gauge") {
		t.Error("missing TYPE annotation for gauge")
	}
	contentType := rec.Header().Get("Content-Type")
	if !strings.Contains(contentType, "text/plain") {
		t.Errorf("expected text/plain content type, got %s", contentType)
	}
}

func TestHistogramLines(t *testing.T) {
	observations := []float64{0.001, 0.002, 0.01, 0.05, 0.1, 0.5}
	result := histogramLines("test_metric", "A test metric", observations)

	if !strings.Contains(result, "# HELP test_metric A test metric") {
		t.Error("missing HELP line")
	}
	if !strings.Contains(result, "# TYPE test_metric histogram") {
		t.Error("missing TYPE line")
	}
	if !strings.Contains(result, "test_metric_count 6") {
		t.Error("expected count of 6")
	}
	if !strings.Contains(result, `test_metric_bucket{le="+Inf"} 6`) {
		t.Error("missing +Inf bucket")
	}
}
