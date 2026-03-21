package metrics

import (
	"fmt"
	"net/http"
	"sync"
	"sync/atomic"
	"time"
)

// Metrics holds all RADIUS server Prometheus-style metrics
type Metrics struct {
	// Counters
	AuthRequestsTotal    atomic.Int64
	AuthAcceptsTotal     atomic.Int64
	AuthRejectsTotal     atomic.Int64
	AuthChallengesTotal  atomic.Int64
	AuthDroppedTotal     atomic.Int64
	AcctRequestsTotal    atomic.Int64
	AcctResponsesTotal   atomic.Int64
	CoASentTotal         atomic.Int64
	CoAAcksTotal         atomic.Int64
	CoANaksTotal         atomic.Int64
	TacacsAuthTotal      atomic.Int64
	TacacsAuthorTotal    atomic.Int64
	TacacsAcctTotal      atomic.Int64
	RadSecConnectionsTotal atomic.Int64
	EAPSessionsStarted   atomic.Int64
	EAPSessionsCompleted atomic.Int64
	EAPSessionsTimedOut  atomic.Int64
	PolicyEvalErrors     atomic.Int64

	// Gauges
	ActiveEAPSessions atomic.Int64
	ActiveRadSecConns atomic.Int64

	// Histogram buckets for auth latency (ms)
	mu             sync.Mutex
	authLatencies  []float64
	acctLatencies  []float64
	policyLatencies []float64
}

// Global singleton
var global = &Metrics{}

// Get returns the global metrics instance
func Get() *Metrics {
	return global
}

// RecordAuthLatency records the duration of an auth request
func (m *Metrics) RecordAuthLatency(d time.Duration) {
	m.mu.Lock()
	m.authLatencies = append(m.authLatencies, d.Seconds())
	if len(m.authLatencies) > 10000 {
		m.authLatencies = m.authLatencies[len(m.authLatencies)-5000:]
	}
	m.mu.Unlock()
}

// RecordAcctLatency records the duration of an accounting request
func (m *Metrics) RecordAcctLatency(d time.Duration) {
	m.mu.Lock()
	m.acctLatencies = append(m.acctLatencies, d.Seconds())
	if len(m.acctLatencies) > 10000 {
		m.acctLatencies = m.acctLatencies[len(m.acctLatencies)-5000:]
	}
	m.mu.Unlock()
}

// RecordPolicyLatency records the duration of a policy evaluation
func (m *Metrics) RecordPolicyLatency(d time.Duration) {
	m.mu.Lock()
	m.policyLatencies = append(m.policyLatencies, d.Seconds())
	if len(m.policyLatencies) > 10000 {
		m.policyLatencies = m.policyLatencies[len(m.policyLatencies)-5000:]
	}
	m.mu.Unlock()
}

// histogramLines produces Prometheus histogram output for a slice of observations
func histogramLines(name string, help string, observations []float64) string {
	buckets := []float64{0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0}
	counts := make([]int64, len(buckets))
	var sum float64
	var count int64

	for _, v := range observations {
		sum += v
		count++
		for i, b := range buckets {
			if v <= b {
				counts[i]++
			}
		}
	}

	out := fmt.Sprintf("# HELP %s %s\n# TYPE %s histogram\n", name, help, name)
	var cumulative int64
	for i, b := range buckets {
		cumulative += counts[i]
		out += fmt.Sprintf("%s_bucket{le=\"%g\"} %d\n", name, b, cumulative)
	}
	out += fmt.Sprintf("%s_bucket{le=\"+Inf\"} %d\n", name, count)
	out += fmt.Sprintf("%s_sum %f\n", name, sum)
	out += fmt.Sprintf("%s_count %d\n", name, count)
	return out
}

// Handler returns an http.HandlerFunc that serves Prometheus metrics
func Handler() http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		m := global
		w.Header().Set("Content-Type", "text/plain; version=0.0.4; charset=utf-8")

		// Counters
		fmt.Fprintf(w, "# HELP radius_auth_requests_total Total RADIUS authentication requests\n")
		fmt.Fprintf(w, "# TYPE radius_auth_requests_total counter\n")
		fmt.Fprintf(w, "radius_auth_requests_total %d\n", m.AuthRequestsTotal.Load())

		fmt.Fprintf(w, "# HELP radius_auth_accepts_total Total Access-Accept responses\n")
		fmt.Fprintf(w, "# TYPE radius_auth_accepts_total counter\n")
		fmt.Fprintf(w, "radius_auth_accepts_total %d\n", m.AuthAcceptsTotal.Load())

		fmt.Fprintf(w, "# HELP radius_auth_rejects_total Total Access-Reject responses\n")
		fmt.Fprintf(w, "# TYPE radius_auth_rejects_total counter\n")
		fmt.Fprintf(w, "radius_auth_rejects_total %d\n", m.AuthRejectsTotal.Load())

		fmt.Fprintf(w, "# HELP radius_auth_challenges_total Total Access-Challenge responses\n")
		fmt.Fprintf(w, "# TYPE radius_auth_challenges_total counter\n")
		fmt.Fprintf(w, "radius_auth_challenges_total %d\n", m.AuthChallengesTotal.Load())

		fmt.Fprintf(w, "# HELP radius_auth_dropped_total Total dropped auth requests\n")
		fmt.Fprintf(w, "# TYPE radius_auth_dropped_total counter\n")
		fmt.Fprintf(w, "radius_auth_dropped_total %d\n", m.AuthDroppedTotal.Load())

		fmt.Fprintf(w, "# HELP radius_acct_requests_total Total RADIUS accounting requests\n")
		fmt.Fprintf(w, "# TYPE radius_acct_requests_total counter\n")
		fmt.Fprintf(w, "radius_acct_requests_total %d\n", m.AcctRequestsTotal.Load())

		fmt.Fprintf(w, "# HELP radius_acct_responses_total Total RADIUS accounting responses\n")
		fmt.Fprintf(w, "# TYPE radius_acct_responses_total counter\n")
		fmt.Fprintf(w, "radius_acct_responses_total %d\n", m.AcctResponsesTotal.Load())

		fmt.Fprintf(w, "# HELP radius_coa_sent_total Total CoA requests sent\n")
		fmt.Fprintf(w, "# TYPE radius_coa_sent_total counter\n")
		fmt.Fprintf(w, "radius_coa_sent_total %d\n", m.CoASentTotal.Load())

		fmt.Fprintf(w, "# HELP radius_coa_acks_total Total CoA ACK responses\n")
		fmt.Fprintf(w, "# TYPE radius_coa_acks_total counter\n")
		fmt.Fprintf(w, "radius_coa_acks_total %d\n", m.CoAAcksTotal.Load())

		fmt.Fprintf(w, "# HELP radius_coa_naks_total Total CoA NAK responses\n")
		fmt.Fprintf(w, "# TYPE radius_coa_naks_total counter\n")
		fmt.Fprintf(w, "radius_coa_naks_total %d\n", m.CoANaksTotal.Load())

		fmt.Fprintf(w, "# HELP radius_tacacs_auth_total Total TACACS+ authentication requests\n")
		fmt.Fprintf(w, "# TYPE radius_tacacs_auth_total counter\n")
		fmt.Fprintf(w, "radius_tacacs_auth_total %d\n", m.TacacsAuthTotal.Load())

		fmt.Fprintf(w, "# HELP radius_tacacs_author_total Total TACACS+ authorization requests\n")
		fmt.Fprintf(w, "# TYPE radius_tacacs_author_total counter\n")
		fmt.Fprintf(w, "radius_tacacs_author_total %d\n", m.TacacsAuthorTotal.Load())

		fmt.Fprintf(w, "# HELP radius_tacacs_acct_total Total TACACS+ accounting requests\n")
		fmt.Fprintf(w, "# TYPE radius_tacacs_acct_total counter\n")
		fmt.Fprintf(w, "radius_tacacs_acct_total %d\n", m.TacacsAcctTotal.Load())

		fmt.Fprintf(w, "# HELP radius_radsec_connections_total Total RadSec connections accepted\n")
		fmt.Fprintf(w, "# TYPE radius_radsec_connections_total counter\n")
		fmt.Fprintf(w, "radius_radsec_connections_total %d\n", m.RadSecConnectionsTotal.Load())

		fmt.Fprintf(w, "# HELP radius_eap_sessions_started_total Total EAP sessions started\n")
		fmt.Fprintf(w, "# TYPE radius_eap_sessions_started_total counter\n")
		fmt.Fprintf(w, "radius_eap_sessions_started_total %d\n", m.EAPSessionsStarted.Load())

		fmt.Fprintf(w, "# HELP radius_eap_sessions_completed_total Total EAP sessions completed\n")
		fmt.Fprintf(w, "# TYPE radius_eap_sessions_completed_total counter\n")
		fmt.Fprintf(w, "radius_eap_sessions_completed_total %d\n", m.EAPSessionsCompleted.Load())

		fmt.Fprintf(w, "# HELP radius_eap_sessions_timedout_total Total EAP sessions timed out\n")
		fmt.Fprintf(w, "# TYPE radius_eap_sessions_timedout_total counter\n")
		fmt.Fprintf(w, "radius_eap_sessions_timedout_total %d\n", m.EAPSessionsTimedOut.Load())

		fmt.Fprintf(w, "# HELP radius_policy_eval_errors_total Total policy evaluation errors\n")
		fmt.Fprintf(w, "# TYPE radius_policy_eval_errors_total counter\n")
		fmt.Fprintf(w, "radius_policy_eval_errors_total %d\n", m.PolicyEvalErrors.Load())

		// Gauges
		fmt.Fprintf(w, "# HELP radius_eap_sessions_active Currently active EAP sessions\n")
		fmt.Fprintf(w, "# TYPE radius_eap_sessions_active gauge\n")
		fmt.Fprintf(w, "radius_eap_sessions_active %d\n", m.ActiveEAPSessions.Load())

		fmt.Fprintf(w, "# HELP radius_radsec_connections_active Active RadSec connections\n")
		fmt.Fprintf(w, "# TYPE radius_radsec_connections_active gauge\n")
		fmt.Fprintf(w, "radius_radsec_connections_active %d\n", m.ActiveRadSecConns.Load())

		// Histograms
		m.mu.Lock()
		authLat := make([]float64, len(m.authLatencies))
		copy(authLat, m.authLatencies)
		acctLat := make([]float64, len(m.acctLatencies))
		copy(acctLat, m.acctLatencies)
		policyLat := make([]float64, len(m.policyLatencies))
		copy(policyLat, m.policyLatencies)
		m.mu.Unlock()

		fmt.Fprint(w, histogramLines("radius_auth_duration_seconds",
			"RADIUS authentication request duration in seconds", authLat))
		fmt.Fprint(w, histogramLines("radius_acct_duration_seconds",
			"RADIUS accounting request duration in seconds", acctLat))
		fmt.Fprint(w, histogramLines("radius_policy_eval_duration_seconds",
			"Policy evaluation duration in seconds", policyLat))
	}
}
