package radius

import (
	"testing"
)

func TestParseEAPPacket(t *testing.T) {
	tests := []struct {
		name     string
		data     []byte
		wantCode byte
		wantType byte
		wantNil  bool
	}{
		{"too short", []byte{1, 2}, 0, 0, true},
		{"identity response", []byte{2, 1, 0, 10, EAPTypeIdentity, 'u', 's', 'e', 'r', '1'}, EAPCodeResponse, EAPTypeIdentity, false},
		{"eap-tls request", []byte{1, 5, 0, 6, EAPTypeTLS, 0x20}, EAPCodeRequest, EAPTypeTLS, false},
		{"success", []byte{EAPCodeSuccess, 3, 0, 4}, EAPCodeSuccess, 0, false},
		{"failure", []byte{EAPCodeFailure, 4, 0, 4}, EAPCodeFailure, 0, false},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			pkt := ParseEAPPacket(tt.data)
			if tt.wantNil {
				if pkt != nil {
					t.Errorf("expected nil, got %+v", pkt)
				}
				return
			}
			if pkt == nil {
				t.Fatal("expected non-nil packet")
			}
			if pkt.Code != tt.wantCode {
				t.Errorf("code = %d, want %d", pkt.Code, tt.wantCode)
			}
			if pkt.Type != tt.wantType {
				t.Errorf("type = %d, want %d", pkt.Type, tt.wantType)
			}
		})
	}
}

func TestParseVSA(t *testing.T) {
	// Cisco VSA: Vendor-ID 9, Type 1, Value "test"
	data := []byte{0, 0, 0, 9, 1, 6, 't', 'e', 's', 't'}
	vsa := ParseVSA(data)
	if vsa == nil {
		t.Fatal("expected non-nil VSA")
	}
	if vsa.VendorID != VendorCisco {
		t.Errorf("vendorID = %d, want %d", vsa.VendorID, VendorCisco)
	}
	if vsa.Type != 1 {
		t.Errorf("type = %d, want 1", vsa.Type)
	}
	if string(vsa.Value) != "test" {
		t.Errorf("value = %q, want %q", string(vsa.Value), "test")
	}

	// Too short
	if ParseVSA([]byte{0, 0}) != nil {
		t.Error("expected nil for short data")
	}
}

func TestAttrName(t *testing.T) {
	if name := AttrName(AttrUserName); name != "User-Name" {
		t.Errorf("got %q, want User-Name", name)
	}
	if name := AttrName(AttrEAPMessage); name != "EAP-Message" {
		t.Errorf("got %q, want EAP-Message", name)
	}
	if name := AttrName(255); name != "Unknown" {
		t.Errorf("got %q, want Unknown", name)
	}
}

func TestEAPTypeName(t *testing.T) {
	if name := EAPTypeName(EAPTypeTLS); name != "EAP-TLS" {
		t.Errorf("got %q, want EAP-TLS", name)
	}
	if name := EAPTypeName(EAPTypePEAP); name != "PEAP" {
		t.Errorf("got %q, want PEAP", name)
	}
	if name := EAPTypeName(200); name != "Unknown" {
		t.Errorf("got %q, want Unknown", name)
	}
}

func TestParsePacket(t *testing.T) {
	// Build a minimal Access-Request packet
	pkt := make([]byte, 20)
	pkt[0] = CodeAccessRequest
	pkt[1] = 42 // identifier
	pkt[2] = 0
	pkt[3] = 20 // length = 20 (header only)
	// authenticator: 16 zero bytes

	parsed, err := ParsePacket(pkt)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if parsed.Code != CodeAccessRequest {
		t.Errorf("code = %d, want %d", parsed.Code, CodeAccessRequest)
	}
	if parsed.Identifier != 42 {
		t.Errorf("identifier = %d, want 42", parsed.Identifier)
	}
	if len(parsed.Attributes) != 0 {
		t.Errorf("expected 0 attributes, got %d", len(parsed.Attributes))
	}
}

func TestPacketEncodeRoundtrip(t *testing.T) {
	original := &Packet{
		Code:       CodeAccessAccept,
		Identifier: 7,
		Secret:     "testing123",
		Attributes: []Attribute{
			{Type: AttrReplyMessage, Value: []byte("Welcome")},
			{Type: AttrSessionTimeout, Value: []byte{0, 0, 0x0E, 0x10}}, // 3600
		},
	}

	encoded := original.Encode()
	decoded, err := ParsePacket(encoded)
	if err != nil {
		t.Fatalf("parse error: %v", err)
	}
	if decoded.Code != original.Code {
		t.Errorf("code mismatch: %d != %d", decoded.Code, original.Code)
	}
	if decoded.Identifier != original.Identifier {
		t.Errorf("identifier mismatch: %d != %d", decoded.Identifier, original.Identifier)
	}
	if len(decoded.Attributes) != 2 {
		t.Errorf("expected 2 attributes, got %d", len(decoded.Attributes))
	}
	msg := decoded.GetString(AttrReplyMessage)
	if msg != "Welcome" {
		t.Errorf("reply message = %q, want %q", msg, "Welcome")
	}
}
