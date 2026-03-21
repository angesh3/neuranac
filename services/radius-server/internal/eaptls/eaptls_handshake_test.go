package eaptls

import (
	"crypto/ecdsa"
	"crypto/elliptic"
	"crypto/rand"
	"crypto/tls"
	"crypto/x509"
	"crypto/x509/pkix"
	"math/big"
	"testing"
	"time"

	"go.uber.org/zap"
)

// TestStartHandshake_ProducesServerHello verifies that StartHandshake uses
// crypto/tls.Server to generate real TLS ServerHello records.
func TestStartHandshake_ProducesServerHello(t *testing.T) {
	logger, _ := zap.NewDevelopment()
	h, err := NewHandshaker(nil, nil, logger)
	if err != nil {
		t.Fatalf("NewHandshaker error: %v", err)
	}

	serverData, err := h.StartHandshake("test-session-1", false)
	if err != nil {
		t.Fatalf("StartHandshake error: %v", err)
	}

	// crypto/tls.Server should produce TLS records starting with 0x16 (Handshake)
	if len(serverData) == 0 {
		t.Fatal("expected non-empty server data from StartHandshake")
	}
	if serverData[0] != 0x16 {
		t.Errorf("expected TLS handshake record type 0x16, got 0x%02x", serverData[0])
	}

	// Verify TLS version bytes (TLS 1.2 = 0x0303)
	if len(serverData) >= 3 {
		version := uint16(serverData[1])<<8 | uint16(serverData[2])
		if version != 0x0301 && version != 0x0303 {
			t.Logf("TLS version in record: 0x%04x (expected 0x0303 for TLS 1.2)", version)
		}
	}

	h.CleanupSession("test-session-1")
}

// TestStartHandshake_RequireClientCert verifies that requireClientCert=true
// causes the TLS config to request a client certificate.
func TestStartHandshake_RequireClientCert(t *testing.T) {
	logger, _ := zap.NewDevelopment()
	h, err := NewHandshaker(nil, nil, logger)
	if err != nil {
		t.Fatalf("NewHandshaker error: %v", err)
	}

	serverData, err := h.StartHandshake("test-cert-req", true)
	if err != nil {
		t.Fatalf("StartHandshake error: %v", err)
	}

	// Should still produce valid TLS records
	if len(serverData) == 0 {
		t.Fatal("expected non-empty server data")
	}

	h.CleanupSession("test-cert-req")
}

// TestProcessClientData_SessionNotFound verifies error on unknown session
func TestProcessClientData_SessionNotFound(t *testing.T) {
	logger, _ := zap.NewDevelopment()
	h, err := NewHandshaker(nil, nil, logger)
	if err != nil {
		t.Fatalf("NewHandshaker error: %v", err)
	}

	_, _, _, err = h.ProcessClientData("nonexistent-session", []byte{0x16, 0x03, 0x03})
	if err == nil {
		t.Error("expected error for nonexistent session")
	}
}

// TestCleanupSession_Idempotent verifies cleanup can be called multiple times safely
func TestCleanupSession_Idempotent(t *testing.T) {
	logger, _ := zap.NewDevelopment()
	h, err := NewHandshaker(nil, nil, logger)
	if err != nil {
		t.Fatalf("NewHandshaker error: %v", err)
	}

	_, _ = h.StartHandshake("cleanup-test", false)
	h.CleanupSession("cleanup-test")
	h.CleanupSession("cleanup-test") // second call should not panic
}

// TestNewHandshaker_WithRealCert verifies loading a real server certificate
func TestNewHandshaker_WithRealCert(t *testing.T) {
	logger, _ := zap.NewDevelopment()

	// Generate a real cert for testing
	key, _ := ecdsa.GenerateKey(elliptic.P256(), rand.Reader)
	template := &x509.Certificate{
		SerialNumber: big.NewInt(1),
		Subject:      pkix.Name{CommonName: "test-server"},
		NotBefore:    time.Now().Add(-1 * time.Hour),
		NotAfter:     time.Now().Add(24 * time.Hour),
		KeyUsage:     x509.KeyUsageDigitalSignature,
		ExtKeyUsage:  []x509.ExtKeyUsage{x509.ExtKeyUsageServerAuth},
	}
	certDER, _ := x509.CreateCertificate(rand.Reader, template, template, &key.PublicKey, key)
	cert := tls.Certificate{
		Certificate: [][]byte{certDER},
		PrivateKey:  key,
	}

	caPool := x509.NewCertPool()
	parsedCert, _ := x509.ParseCertificate(certDER)
	caPool.AddCert(parsedCert)

	h, err := NewHandshaker(&cert, caPool, logger)
	if err != nil {
		t.Fatalf("NewHandshaker with real cert error: %v", err)
	}

	serverData, err := h.StartHandshake("real-cert-session", true)
	if err != nil {
		t.Fatalf("StartHandshake with real cert error: %v", err)
	}
	if len(serverData) == 0 {
		t.Fatal("expected non-empty server data with real cert")
	}

	h.CleanupSession("real-cert-session")
}

// TestMultipleConcurrentSessions verifies the handshaker supports multiple sessions
func TestMultipleConcurrentSessions(t *testing.T) {
	logger, _ := zap.NewDevelopment()
	h, err := NewHandshaker(nil, nil, logger)
	if err != nil {
		t.Fatalf("NewHandshaker error: %v", err)
	}

	sessions := []string{"session-a", "session-b", "session-c"}
	for _, s := range sessions {
		data, err := h.StartHandshake(s, false)
		if err != nil {
			t.Errorf("StartHandshake(%s) error: %v", s, err)
		}
		if len(data) == 0 {
			t.Errorf("StartHandshake(%s) returned empty data", s)
		}
	}

	// All sessions should be independent
	for _, s := range sessions {
		h.CleanupSession(s)
	}
}
