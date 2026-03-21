package eaptls

import (
	"crypto/x509"
	"testing"

	"go.uber.org/zap"
)

func TestNewHandshakerEphemeral(t *testing.T) {
	logger, _ := zap.NewDevelopment()
	h, err := NewHandshaker(nil, nil, logger)
	if err != nil {
		t.Fatalf("NewHandshaker with ephemeral cert error: %v", err)
	}
	if h == nil {
		t.Fatal("expected non-nil handshaker")
	}
}

func TestGenerateEphemeralCert(t *testing.T) {
	cert, err := generateEphemeralCert()
	if err != nil {
		t.Fatalf("generateEphemeralCert error: %v", err)
	}
	if len(cert.Certificate) == 0 {
		t.Fatal("expected non-empty certificate chain")
	}
	if cert.PrivateKey == nil {
		t.Fatal("expected non-nil private key")
	}

	// Parse the DER cert
	parsed, err := x509.ParseCertificate(cert.Certificate[0])
	if err != nil {
		t.Fatalf("parse certificate: %v", err)
	}
	if parsed.Subject.CommonName != "neuranac-radius-eaptls" {
		t.Errorf("expected CN=neuranac-radius-eaptls, got %s", parsed.Subject.CommonName)
	}
	if parsed.Subject.Organization[0] != "NeuraNAC RADIUS Server" {
		t.Errorf("expected O=NeuraNAC RADIUS Server, got %s", parsed.Subject.Organization[0])
	}
}

func TestBuildEAPTLSMessage(t *testing.T) {
	tlsData := []byte{0x16, 0x03, 0x03, 0x00, 0x05, 0x01, 0x02, 0x03, 0x04, 0x05}

	// Non-start message
	msg := BuildEAPTLSMessage(1, 13, tlsData, false)
	if msg[0] != 1 { // EAP-Request
		t.Errorf("expected code 1, got %d", msg[0])
	}
	if msg[1] != 1 { // ID
		t.Errorf("expected id 1, got %d", msg[1])
	}
	if msg[4] != 13 { // EAP-TLS type
		t.Errorf("expected type 13, got %d", msg[4])
	}
	if msg[5]&0x20 != 0 { // Start flag should NOT be set
		t.Error("start flag should not be set")
	}

	// Start message
	startMsg := BuildEAPTLSMessage(2, 13, tlsData, true)
	if startMsg[5]&0x20 == 0 {
		t.Error("start flag should be set")
	}
	if startMsg[5]&0x80 == 0 {
		t.Error("length flag should be set for start message with data")
	}
}

func TestBuildEAPTLSMessageTypes(t *testing.T) {
	data := []byte{0x01, 0x02}

	// EAP-TTLS (type 21)
	msg := BuildEAPTLSMessage(1, 21, data, false)
	if msg[4] != 21 {
		t.Errorf("expected type 21, got %d", msg[4])
	}

	// PEAP (type 25)
	msg = BuildEAPTLSMessage(1, 25, data, false)
	if msg[4] != 25 {
		t.Errorf("expected type 25, got %d", msg[4])
	}
}

func TestExtractTLSPayload(t *testing.T) {
	// Build a message and extract payload
	tlsData := []byte{0xAA, 0xBB, 0xCC, 0xDD}
	msg := BuildEAPTLSMessage(1, 13, tlsData, false)

	extracted := ExtractTLSPayload(msg)
	if len(extracted) != len(tlsData) {
		t.Fatalf("expected %d bytes, got %d", len(tlsData), len(extracted))
	}
	for i, b := range extracted {
		if b != tlsData[i] {
			t.Errorf("byte %d: expected 0x%02X, got 0x%02X", i, tlsData[i], b)
		}
	}
}

func TestExtractTLSPayloadWithLength(t *testing.T) {
	// Start message has length field
	tlsData := []byte{0x11, 0x22, 0x33}
	msg := BuildEAPTLSMessage(1, 13, tlsData, true)

	extracted := ExtractTLSPayload(msg)
	if len(extracted) != len(tlsData) {
		t.Fatalf("expected %d bytes, got %d", len(tlsData), len(extracted))
	}
}

func TestExtractTLSPayloadShort(t *testing.T) {
	// Too short — should return nil
	result := ExtractTLSPayload([]byte{1, 2, 3})
	if result != nil {
		t.Error("expected nil for short message")
	}
}
