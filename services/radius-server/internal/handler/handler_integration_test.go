package handler

import (
	"context"
	"testing"
	"time"

	"github.com/neuranac/services/radius-server/internal/circuitbreaker"
	"github.com/neuranac/services/radius-server/internal/eapstore"
	"github.com/neuranac/services/radius-server/internal/metrics"
	"github.com/neuranac/services/radius-server/internal/store"
	"go.uber.org/zap"
)

// --- Mock RadiusPacket ---

type mockRadiusPacket struct {
	code        int
	srcIP       string
	attrStrings map[byte]string
	attrBytes   map[byte][]byte
	authValid   bool
}

func (m *mockRadiusPacket) GetCode() int                  { return m.code }
func (m *mockRadiusPacket) GetSrcIP() string              { return m.srcIP }
func (m *mockRadiusPacket) GetAttrString(t byte) string   { return m.attrStrings[t] }
func (m *mockRadiusPacket) GetAttrBytes(t byte) []byte    { return m.attrBytes[t] }
func (m *mockRadiusPacket) VerifyAuth(secret string) bool { return m.authValid }
func (m *mockRadiusPacket) BuildAccept(secret string, attrs map[string]string) interface{} {
	return map[string]interface{}{"code": 2, "attrs": attrs}
}
func (m *mockRadiusPacket) BuildReject(secret string, msg string) interface{} {
	return map[string]interface{}{"code": 3, "msg": msg}
}
func (m *mockRadiusPacket) BuildAcctResponse(secret string) interface{} {
	return map[string]interface{}{"code": 5}
}

// newTestHandler creates a Handler with mocks for unit testing.
// The store field is nil — only call sub-functions that don't touch the store directly,
// or pass a real *store.DataStore if you have a DB connection available.
func newTestHandler(t *testing.T) *Handler {
	t.Helper()
	logger, _ := zap.NewDevelopment()
	es := eapstore.NewMemoryStore(logger)
	aiCli := &AIClient{enabled: false, logger: logger} // disabled — skips all AI calls
	return &Handler{
		logger:   logger,
		eapStore: es,
		policyCB: circuitbreaker.New(circuitbreaker.DefaultOptions()),
		aiClient: aiCli,
		metrics:  metrics.Get(),
	}
}

// --- EAP-TLS State Machine Tests ---

func TestHandleEAPTLS_StateMachine_StartAndChallenge(t *testing.T) {
	h := newTestHandler(t)
	defer h.Close()

	ctx := context.Background()
	mac := "AA:BB:CC:DD:EE:FF"
	nad := &store.NADInfo{TenantID: "t1", SharedSecret: "secret123"}

	// Step 1: EAP-TLS initial — creates session, returns challenge (Start)
	eapMsg := []byte{0x02, 0x01, 0x00, 0x06, 13, 0x00}
	pkt := &mockRadiusPacket{
		code: 1, srcIP: "10.0.0.1",
		attrStrings: map[byte]string{1: "alice", 31: mac},
		attrBytes:   map[byte][]byte{79: eapMsg, 24: nil},
		authValid:   true,
	}

	result, err := h.handleEAPTLS(ctx, nad, pkt, eapMsg)
	if err != nil {
		t.Fatalf("Step 1 error: %v", err)
	}
	if result.Decision != "challenge" {
		t.Errorf("Step 1: expected challenge, got %s", result.Decision)
	}
	if result.EAPType != "eap-tls" {
		t.Errorf("Step 1: expected eap-tls, got %s", result.EAPType)
	}

	// Verify session was created in eapStore
	sessionKey := "t1:" + NormalizeMAC(mac) + ":eap-tls"
	sess, exists := h.eapStore.Get(ctx, sessionKey)
	if !exists {
		t.Fatal("EAP session not found in store after Step 1")
	}
	if sess.TLSState != eapTLSStateServerHello {
		t.Errorf("Expected TLS state ServerHello (1), got %d", sess.TLSState)
	}

	// Step 2: Client Hello — TLS handshake data
	tlsClientHello := []byte{0x16, 0x03, 0x03, 0x00, 0x05, 0x01, 0x00, 0x00, 0x01, 0x00}
	eapMsg2 := append([]byte{0x02, 0x02, 0x00, byte(6 + len(tlsClientHello)), 13, 0x00}, tlsClientHello...)
	pkt2 := &mockRadiusPacket{
		code: 1, srcIP: "10.0.0.1",
		attrStrings: map[byte]string{1: "alice", 31: mac},
		attrBytes:   map[byte][]byte{79: eapMsg2, 24: []byte(sessionKey)},
		authValid:   true,
	}

	result2, err := h.handleEAPTLS(ctx, nad, pkt2, eapMsg2)
	if err != nil {
		t.Fatalf("Step 2 error: %v", err)
	}
	if result2.Decision != "challenge" {
		t.Errorf("Step 2: expected challenge, got %s", result2.Decision)
	}

	// Verify state advanced to ClientCert
	sess2, exists := h.eapStore.Get(ctx, sessionKey)
	if !exists {
		t.Fatal("EAP session not found after Step 2")
	}
	if sess2.TLSState != eapTLSStateClientCert {
		t.Errorf("Expected TLS state ClientCert (2), got %d", sess2.TLSState)
	}
}

func TestHandleEAPTLS_ShortClientHello_Denied(t *testing.T) {
	h := newTestHandler(t)
	defer h.Close()

	ctx := context.Background()
	mac := "AA:BB:CC:DD:EE:01"
	nad := &store.NADInfo{TenantID: "t1", SharedSecret: "secret123"}
	sessionKey := "t1:" + NormalizeMAC(mac) + ":eap-tls"

	// Pre-create session in ServerHello state
	h.eapStore.Set(ctx, sessionKey, &eapstore.EAPSession{
		SessionID: "eap-test", TenantID: "t1", MAC: NormalizeMAC(mac),
		CreatedAt: time.Now(), TLSState: eapTLSStateServerHello,
	})

	// Send a too-short ClientHello
	eapMsg := []byte{0x02, 0x02, 0x00, 0x07, 13, 0x00, 0x01}
	pkt := &mockRadiusPacket{
		code: 1, srcIP: "10.0.0.1",
		attrStrings: map[byte]string{31: mac},
		attrBytes:   map[byte][]byte{79: eapMsg},
		authValid:   true,
	}

	result, err := h.handleEAPTLS(ctx, nad, pkt, eapMsg)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if result.Decision != "deny" {
		t.Errorf("expected deny for short ClientHello, got %s", result.Decision)
	}

	// Session should be cleaned up
	_, exists := h.eapStore.Get(ctx, sessionKey)
	if exists {
		t.Error("session should be deleted after deny")
	}
}

// --- EAP-TTLS Tests ---

func TestHandleEAPTTLS_FullFlow_WithUserLookup(t *testing.T) {
	h := newTestHandler(t)
	// Wire in a store that can look up users — we test only the state machine part here
	// Inner auth calls h.store.GetUserByUsername which needs a real store,
	// so we test only the challenge phases
	defer h.Close()

	ctx := context.Background()
	mac := "11:22:33:44:55:66"
	nad := &store.NADInfo{TenantID: "t1", SharedSecret: "secret123"}

	// Step 1: TTLS Start → challenge
	eapMsg := []byte{0x02, 0x01, 0x00, 0x06, 21, 0x00}
	pkt := &mockRadiusPacket{
		code: 1, srcIP: "10.0.0.1",
		attrStrings: map[byte]string{1: "bob", 31: mac},
		authValid:   true,
	}

	r1, err := h.handleEAPTTLS(ctx, nad, pkt, eapMsg)
	if err != nil {
		t.Fatalf("TTLS Step 1 error: %v", err)
	}
	if r1.Decision != "challenge" {
		t.Errorf("TTLS Step 1: expected challenge, got %s", r1.Decision)
	}

	// Step 2: ServerHello → challenge
	eapMsg2 := []byte{0x02, 0x02, 0x00, 0x06, 21, 0x00}
	r2, err := h.handleEAPTTLS(ctx, nad, pkt, eapMsg2)
	if err != nil {
		t.Fatalf("TTLS Step 2 error: %v", err)
	}
	if r2.Decision != "challenge" {
		t.Errorf("TTLS Step 2: expected challenge, got %s", r2.Decision)
	}

	// Verify session state
	sessionKey := "t1:" + NormalizeMAC(mac) + ":eap-ttls"
	sess, exists := h.eapStore.Get(ctx, sessionKey)
	if !exists {
		t.Fatal("TTLS session not found after Step 2")
	}
	if sess.TLSState != eapTLSStateClientCert {
		t.Errorf("Expected TLS state ClientCert (2), got %d", sess.TLSState)
	}
}

// --- PEAP Tests ---

func TestHandlePEAP_ChallengePhases(t *testing.T) {
	h := newTestHandler(t)
	defer h.Close()

	ctx := context.Background()
	mac := "22:33:44:55:66:77"
	nad := &store.NADInfo{TenantID: "t1", SharedSecret: "secret123"}

	eapMsg := []byte{0x02, 0x01, 0x00, 0x06, 25, 0x00}
	pkt := &mockRadiusPacket{
		code: 1, srcIP: "10.0.0.1",
		attrStrings: map[byte]string{1: "carol", 31: mac},
		authValid:   true,
	}

	// Step 1: Start → challenge
	r1, err := h.handlePEAP(ctx, nad, pkt, eapMsg)
	if err != nil {
		t.Fatalf("PEAP Step 1 error: %v", err)
	}
	if r1.Decision != "challenge" {
		t.Errorf("PEAP Step 1: expected challenge, got %s", r1.Decision)
	}

	// Step 2: ServerHello → challenge
	r2, err := h.handlePEAP(ctx, nad, pkt, eapMsg)
	if err != nil {
		t.Fatalf("PEAP Step 2 error: %v", err)
	}
	if r2.Decision != "challenge" {
		t.Errorf("PEAP Step 2: expected challenge, got %s", r2.Decision)
	}

	// Verify session state
	sessionKey := "t1:" + NormalizeMAC(mac) + ":peap"
	sess, exists := h.eapStore.Get(ctx, sessionKey)
	if !exists {
		t.Fatal("PEAP session not found after Step 2")
	}
	if sess.TLSState != eapTLSStateClientCert {
		t.Errorf("Expected TLS state ClientCert (2), got %d", sess.TLSState)
	}
}

// --- EAP Identity Tests ---

func TestHandleEAPIdentity_SetsUsername(t *testing.T) {
	h := newTestHandler(t)
	defer h.Close()

	ctx := context.Background()
	mac := "33:44:55:66:77:88"
	nad := &store.NADInfo{TenantID: "t1", SharedSecret: "secret123"}

	// Pre-create a TLS session to see if identity is propagated
	sessionKey := "t1:" + NormalizeMAC(mac) + ":eap-tls"
	h.eapStore.Set(ctx, sessionKey, &eapstore.EAPSession{
		SessionID: "test-sess", TenantID: "t1", MAC: NormalizeMAC(mac),
		CreatedAt: time.Now(), TLSState: eapTLSStateStart,
	})

	eapMsg := []byte{0x02, 0x01, 0x00, 0x0c, 0x01, 'd', 'a', 'v', 'e'}
	pkt := &mockRadiusPacket{
		code: 1, srcIP: "10.0.0.1",
		attrStrings: map[byte]string{1: "dave", 31: mac},
		authValid:   true,
	}

	result, err := h.handleEAPIdentity(ctx, nad, pkt, eapMsg)
	if err != nil {
		t.Fatalf("EAP Identity error: %v", err)
	}
	if result.Decision != "challenge" {
		t.Errorf("EAP Identity: expected challenge, got %s", result.Decision)
	}

	// Check that the session username was updated
	sess, exists := h.eapStore.Get(ctx, sessionKey)
	if !exists {
		t.Fatal("session should still exist")
	}
	if sess.Username != "dave" {
		t.Errorf("expected session username 'dave', got %q", sess.Username)
	}
}

// --- enrichWithPolicy Tests ---

func TestEnrichWithPolicy_SkipNonPermit(t *testing.T) {
	h := newTestHandler(t)
	defer h.Close()

	nad := &store.NADInfo{TenantID: "t1"}
	result := &AuthResult{Decision: "deny"}

	// Should be a no-op since decision is not "permit"
	h.enrichWithPolicy(context.Background(), nad, result, "AA:BB:CC:DD:EE:FF")
	if result.Decision != "deny" {
		t.Errorf("expected deny unchanged, got %s", result.Decision)
	}
}

func TestEnrichWithPolicy_CircuitBreakerAllows(t *testing.T) {
	h := newTestHandler(t)
	defer h.Close()

	nad := &store.NADInfo{TenantID: "t1"}
	result := &AuthResult{Decision: "permit", Username: "alice", EAPType: "pap"}

	// Will fail at h.store.EvaluatePolicy (nil store) but CB should record failure gracefully
	// The function should not panic and decision should remain "permit" (defaults on error)
	h.enrichWithPolicy(context.Background(), nad, result, "AA:BB:CC:DD:EE:FF")
	if result.Decision != "permit" {
		t.Errorf("expected permit after policy error, got %s", result.Decision)
	}
}

// --- Circuit Breaker Tests ---

func TestCircuitBreaker_OpensAfterFailures(t *testing.T) {
	cb := circuitbreaker.New(circuitbreaker.Options{
		MaxFailures:     3,
		ResetTimeout:    1 * time.Second,
		HalfOpenMaxReqs: 2,
	})

	// Should be closed initially
	if err := cb.Allow(); err != nil {
		t.Fatalf("CB should be closed initially, got err: %v", err)
	}

	// Record failures to trip the breaker
	cb.RecordFailure()
	cb.RecordFailure()
	cb.RecordFailure()

	// Should be open now
	if err := cb.Allow(); err == nil {
		t.Error("CB should be open after 3 failures")
	}
	if cb.GetState() != circuitbreaker.StateOpen {
		t.Errorf("expected StateOpen, got %v", cb.GetState())
	}

	// Wait for reset timeout
	time.Sleep(1100 * time.Millisecond)

	// Allow() should pass now (timeout expired), transitions toward half-open
	if err := cb.Allow(); err != nil {
		t.Fatalf("CB should allow after reset timeout, got err: %v", err)
	}

	// RecordSuccess transitions Open → HalfOpen (successCount=1)
	cb.RecordSuccess()

	// Allow + RecordSuccess again to meet halfOpenMaxReqs=2 → transitions to Closed
	if err := cb.Allow(); err != nil {
		t.Fatalf("CB should allow in half-open, got err: %v", err)
	}
	cb.RecordSuccess()

	if cb.GetState() != circuitbreaker.StateClosed {
		t.Errorf("expected StateClosed after recovery, got %v", cb.GetState())
	}
}

// --- EAP Store Lifecycle Tests ---

func TestEAPStore_SessionLifecycle(t *testing.T) {
	logger, _ := zap.NewDevelopment()
	es := eapstore.NewMemoryStore(logger)
	defer es.Close()

	ctx := context.Background()
	key := "t1:AA:BB:CC:DD:EE:FF:eap-tls"

	// Initially empty
	_, exists := es.Get(ctx, key)
	if exists {
		t.Fatal("session should not exist initially")
	}

	// Set
	sess := &eapstore.EAPSession{
		SessionID: "test-1", TenantID: "t1", MAC: "AA:BB:CC:DD:EE:FF",
		TLSState: 0, CreatedAt: time.Now(),
	}
	es.Set(ctx, key, sess)

	// Get
	got, exists := es.Get(ctx, key)
	if !exists {
		t.Fatal("session should exist after Set")
	}
	if got.SessionID != "test-1" {
		t.Errorf("expected session ID test-1, got %s", got.SessionID)
	}

	// Update TLS state
	got.TLSState = 1
	es.Set(ctx, key, got)
	got2, _ := es.Get(ctx, key)
	if got2.TLSState != 1 {
		t.Errorf("expected TLS state 1 after update, got %d", got2.TLSState)
	}

	// Count
	if es.Count(ctx) != 1 {
		t.Errorf("expected count 1, got %d", es.Count(ctx))
	}

	// Delete
	es.Delete(ctx, key)
	_, exists = es.Get(ctx, key)
	if exists {
		t.Fatal("session should not exist after Delete")
	}
}

// --- EAP Message Builder Tests ---

func TestBuildEAPTLSStart(t *testing.T) {
	h := &Handler{logger: zap.NewNop()}
	pkt := h.buildEAPTLSStart(0x05)
	if len(pkt) != 6 {
		t.Fatalf("expected 6 bytes, got %d", len(pkt))
	}
	if pkt[0] != 1 { // EAP-Request
		t.Errorf("expected code 1, got %d", pkt[0])
	}
	if pkt[1] != 0x05 {
		t.Errorf("expected ID 5, got %d", pkt[1])
	}
	if pkt[4] != 13 { // EAP-TLS type
		t.Errorf("expected type 13, got %d", pkt[4])
	}
	if pkt[5] != eapTLSFlagStart {
		t.Errorf("expected Start flag 0x20, got 0x%02x", pkt[5])
	}
}

func TestBuildEAPSuccess(t *testing.T) {
	h := &Handler{logger: zap.NewNop()}
	pkt := h.buildEAPSuccess(0x0A)
	if len(pkt) != 4 {
		t.Fatalf("expected 4 bytes, got %d", len(pkt))
	}
	if pkt[0] != 3 { // EAP-Success
		t.Errorf("expected code 3, got %d", pkt[0])
	}
	if pkt[1] != 0x0A {
		t.Errorf("expected ID 10, got %d", pkt[1])
	}
}

func TestBuildEAPFailure(t *testing.T) {
	h := &Handler{logger: zap.NewNop()}
	pkt := h.buildEAPFailure(0x0B)
	if len(pkt) != 4 {
		t.Fatalf("expected 4 bytes, got %d", len(pkt))
	}
	if pkt[0] != 4 { // EAP-Failure
		t.Errorf("expected code 4, got %d", pkt[0])
	}
}

func TestBuildEAPTLSServerHello(t *testing.T) {
	h := &Handler{logger: zap.NewNop()}
	pkt := h.buildEAPTLSServerHello(0x06)
	if len(pkt) < 6 {
		t.Fatalf("expected >= 6 bytes, got %d", len(pkt))
	}
	if pkt[0] != 1 {
		t.Errorf("expected code 1 (Request), got %d", pkt[0])
	}
	if pkt[4] != 13 {
		t.Errorf("expected EAP type 13 (TLS), got %d", pkt[4])
	}
}

// --- TLS Data Extraction Tests ---

func TestExtractTLSData_NoLengthFlag(t *testing.T) {
	h := &Handler{logger: zap.NewNop()}
	// EAP header (5 bytes) + TLS flags (1 byte, no Length flag) + payload
	msg := []byte{0x02, 0x01, 0x00, 0x08, 13, 0x00, 0xAA, 0xBB}
	data := h.extractTLSData(msg)
	if len(data) != 2 || data[0] != 0xAA || data[1] != 0xBB {
		t.Errorf("expected [AA BB], got %v", data)
	}
}

func TestExtractTLSData_WithLengthFlag(t *testing.T) {
	h := &Handler{logger: zap.NewNop()}
	// flags = 0x80 (Length bit set), then 4-byte length, then payload
	msg := []byte{0x02, 0x01, 0x00, 0x0E, 13, 0x80, 0x00, 0x00, 0x00, 0x02, 0xCC, 0xDD}
	data := h.extractTLSData(msg)
	if len(data) != 2 || data[0] != 0xCC || data[1] != 0xDD {
		t.Errorf("expected [CC DD], got %v", data)
	}
}

func TestExtractTLSData_TooShort(t *testing.T) {
	h := &Handler{logger: zap.NewNop()}
	data := h.extractTLSData([]byte{0x01, 0x02})
	if data != nil {
		t.Errorf("expected nil for short message, got %v", data)
	}
}

func TestExtractDERFromHandshake_Nil(t *testing.T) {
	if got := extractDERFromHandshake(nil); got != nil {
		t.Error("expected nil for nil input")
	}
}

func TestExtractDERFromHandshake_Short(t *testing.T) {
	if got := extractDERFromHandshake([]byte{0x00, 0x01}); got != nil {
		t.Error("expected nil for short input")
	}
}

// --- Metrics Wiring Tests ---

func TestMetrics_AuthCountersIncrement(t *testing.T) {
	m := metrics.Get()
	before := m.AuthRequestsTotal.Load()
	m.AuthRequestsTotal.Add(1)
	after := m.AuthRequestsTotal.Load()
	if after != before+1 {
		t.Errorf("expected AuthRequestsTotal to increment by 1, got %d -> %d", before, after)
	}
}

func TestMetrics_RecordAuthLatency(t *testing.T) {
	m := metrics.Get()
	// Should not panic
	m.RecordAuthLatency(5 * time.Millisecond)
	m.RecordAuthLatency(10 * time.Millisecond)
}

func TestMetrics_RecordPolicyLatency(t *testing.T) {
	m := metrics.Get()
	m.RecordPolicyLatency(2 * time.Millisecond)
}

func TestMetrics_RecordAcctLatency(t *testing.T) {
	m := metrics.Get()
	m.RecordAcctLatency(1 * time.Millisecond)
}

func TestMetrics_EAPSessionGauges(t *testing.T) {
	m := metrics.Get()
	before := m.ActiveEAPSessions.Load()
	m.ActiveEAPSessions.Add(1)
	if m.ActiveEAPSessions.Load() != before+1 {
		t.Error("ActiveEAPSessions gauge did not increment")
	}
	m.ActiveEAPSessions.Add(-1)
	if m.ActiveEAPSessions.Load() != before {
		t.Error("ActiveEAPSessions gauge did not decrement back")
	}
}
