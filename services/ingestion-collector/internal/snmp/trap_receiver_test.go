package snmp

import (
	"testing"
)

func TestDecodeOID(t *testing.T) {
	tests := []struct {
		name     string
		raw      []byte
		expected string
	}{
		{
			name:     "linkDown OID",
			raw:      []byte{0x2b, 0x06, 0x01, 0x06, 0x03, 0x01, 0x01, 0x05, 0x03},
			expected: "1.3.6.1.6.3.1.1.5.3",
		},
		{
			name:     "linkUp OID",
			raw:      []byte{0x2b, 0x06, 0x01, 0x06, 0x03, 0x01, 0x01, 0x05, 0x04},
			expected: "1.3.6.1.6.3.1.1.5.4",
		},
		{
			name:     "empty",
			raw:      []byte{},
			expected: "",
		},
		{
			name:     "single byte",
			raw:      []byte{0x2b},
			expected: "1.3",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := decodeOID(tt.raw)
			if result != tt.expected {
				t.Errorf("decodeOID(%v) = %q, want %q", tt.raw, result, tt.expected)
			}
		})
	}
}

func TestExtractFirstOID(t *testing.T) {
	// OID tag 0x06, length 9, then the linkDown OID bytes
	data := []byte{0x00, 0x06, 0x09, 0x2b, 0x06, 0x01, 0x06, 0x03, 0x01, 0x01, 0x05, 0x03, 0x00}
	result := extractFirstOID(data)
	if result != "1.3.6.1.6.3.1.1.5.3" {
		t.Errorf("extractFirstOID returned %q, want linkDown OID", result)
	}
}

func TestExtractFirstOID_NoOID(t *testing.T) {
	data := []byte{0x00, 0x01, 0x02, 0x03}
	result := extractFirstOID(data)
	if result != "" {
		t.Errorf("extractFirstOID returned %q for data with no OID, want empty", result)
	}
}

func TestKnownOIDs(t *testing.T) {
	expected := map[string]string{
		"1.3.6.1.6.3.1.1.5.3": "linkDown",
		"1.3.6.1.6.3.1.1.5.4": "linkUp",
		"1.3.6.1.6.3.1.1.5.5": "authenticationFailure",
		"1.3.6.1.6.3.1.1.5.1": "coldStart",
		"1.3.6.1.6.3.1.1.5.2": "warmStart",
	}

	for oid, name := range expected {
		if knownOIDs[oid] != name {
			t.Errorf("knownOIDs[%q] = %q, want %q", oid, knownOIDs[oid], name)
		}
	}
}

func TestNeighborOIDs(t *testing.T) {
	// Verify we have the expected CDP/LLDP OIDs
	requiredKeys := []string{"cdpCacheDeviceId", "cdpCachePlatform", "lldpRemSysName", "lldpRemPortId"}
	for _, key := range requiredKeys {
		if _, ok := NeighborOIDs[key]; !ok {
			t.Errorf("NeighborOIDs missing key %q", key)
		}
	}
}

func TestParseSNMPv2cTrap_TooShort(t *testing.T) {
	tr := &TrapReceiver{}
	result := tr.parseSNMPv2cTrap([]byte{0x30, 0x01, 0x02})
	if result != nil {
		t.Errorf("parseSNMPv2cTrap should return nil for short packet, got %v", result)
	}
}

func TestParseSNMPv2cTrap_NotSequence(t *testing.T) {
	tr := &TrapReceiver{}
	data := make([]byte, 25)
	data[0] = 0x31 // Not a SEQUENCE tag
	result := tr.parseSNMPv2cTrap(data)
	if result != nil {
		t.Errorf("parseSNMPv2cTrap should return nil for non-SEQUENCE, got %v", result)
	}
}

func TestParseSNMPv2cTrap_ValidCommunity(t *testing.T) {
	tr := &TrapReceiver{}
	// Build a minimal SNMPv2c trap: SEQUENCE tag, length, version INTEGER, community OCTET STRING, trap PDU
	data := make([]byte, 30)
	data[0] = 0x30  // SEQUENCE
	data[1] = 28    // length
	data[2] = 0x02  // INTEGER (version)
	data[3] = 0x01  // length 1
	data[4] = 0x01  // version = 1 (SNMPv2c)
	data[5] = 0x04  // OCTET STRING (community)
	data[6] = 0x06  // length 6
	copy(data[7:13], []byte("public"))
	data[13] = 0xa7 // SNMPv2-Trap PDU type
	data[14] = 14   // length
	// Add an OID inside the PDU
	data[15] = 0x06 // OID tag
	data[16] = 0x09 // OID length
	copy(data[17:26], []byte{0x2b, 0x06, 0x01, 0x06, 0x03, 0x01, 0x01, 0x05, 0x03}) // linkDown

	result := tr.parseSNMPv2cTrap(data)
	if result == nil {
		t.Fatal("parseSNMPv2cTrap returned nil for valid packet")
	}
	if result["community"] != "public" {
		t.Errorf("community = %q, want 'public'", result["community"])
	}
	if result["trap_oid"] != "1.3.6.1.6.3.1.1.5.3" {
		t.Errorf("trap_oid = %q, want linkDown OID", result["trap_oid"])
	}
}

func TestMin(t *testing.T) {
	if min(3, 5) != 3 {
		t.Error("min(3,5) should be 3")
	}
	if min(5, 3) != 3 {
		t.Error("min(5,3) should be 3")
	}
	if min(4, 4) != 4 {
		t.Error("min(4,4) should be 4")
	}
}

func TestTrapReceiverStats(t *testing.T) {
	tr := &TrapReceiver{}
	stats := tr.Stats()
	if stats["received"] != 0 {
		t.Errorf("initial received = %d, want 0", stats["received"])
	}
	if stats["parsed"] != 0 {
		t.Errorf("initial parsed = %d, want 0", stats["parsed"])
	}
	tr.received.Add(5)
	tr.parsed.Add(3)
	stats = tr.Stats()
	if stats["received"] != 5 {
		t.Errorf("received = %d, want 5", stats["received"])
	}
	if stats["parsed"] != 3 {
		t.Errorf("parsed = %d, want 3", stats["parsed"])
	}
}
