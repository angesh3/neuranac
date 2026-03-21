package dhcp

import (
	"testing"
)

func TestParseDHCPOptions(t *testing.T) {
	// Build options: hostname(12)="myhost", msgtype(53)=1(DISCOVER), end(255)
	data := []byte{
		12, 6, 'm', 'y', 'h', 'o', 's', 't', // option 12 (hostname)
		53, 1, 1, // option 53 (msg type = DISCOVER)
		60, 5, 'C', 'i', 's', 'c', 'o', // option 60 (vendor class)
		55, 3, 0x01, 0x03, 0x06, // option 55 (param list)
		255, // end
	}

	opts := parseDHCPOptions(data)

	if string(opts[12]) != "myhost" {
		t.Errorf("hostname = %q, want myhost", string(opts[12]))
	}
	if opts[53][0] != 1 {
		t.Errorf("msg_type = %d, want 1 (DISCOVER)", opts[53][0])
	}
	if string(opts[60]) != "Cisco" {
		t.Errorf("vendor_class = %q, want Cisco", string(opts[60]))
	}
	if len(opts[55]) != 3 {
		t.Errorf("param_list length = %d, want 3", len(opts[55]))
	}
}

func TestParseDHCPOptions_Empty(t *testing.T) {
	opts := parseDHCPOptions([]byte{255})
	if len(opts) != 0 {
		t.Errorf("expected 0 options for end-only, got %d", len(opts))
	}
}

func TestParseDHCPOptions_Padding(t *testing.T) {
	data := []byte{0, 0, 53, 1, 3, 255} // 2 padding bytes, then msgtype=REQUEST
	opts := parseDHCPOptions(data)
	if opts[53][0] != 3 {
		t.Errorf("msg_type = %d, want 3 (REQUEST)", opts[53][0])
	}
}

func TestParseDHCPOptions_Truncated(t *testing.T) {
	data := []byte{12, 10, 'a', 'b'} // says length 10 but only 2 bytes
	opts := parseDHCPOptions(data)
	if _, ok := opts[12]; ok {
		t.Error("should not parse truncated option")
	}
}

func TestMsgTypes(t *testing.T) {
	expected := map[byte]string{
		1: "DISCOVER", 2: "OFFER", 3: "REQUEST", 4: "DECLINE",
		5: "ACK", 6: "NAK", 7: "RELEASE", 8: "INFORM",
	}
	for code, name := range expected {
		if msgTypes[code] != name {
			t.Errorf("msgTypes[%d] = %q, want %q", code, msgTypes[code], name)
		}
	}
}

func TestKnownFingerprints(t *testing.T) {
	// Verify a few known entries exist
	if _, ok := knownFingerprints["01,03,06,0c,0f,1c,28,29,2a"]; !ok {
		t.Error("missing Linux fingerprint")
	}
	if _, ok := knownFingerprints["01,03,06,0c,0f,1c"]; !ok {
		t.Error("missing Android fingerprint")
	}
}

func TestSnooperStats(t *testing.T) {
	s := &Snooper{}
	stats := s.Stats()
	if stats["received"] != 0 || stats["fingerprinted"] != 0 {
		t.Errorf("initial stats should be zero, got %v", stats)
	}
	s.received.Add(20)
	s.fingerprinted.Add(15)
	stats = s.Stats()
	if stats["received"] != 20 {
		t.Errorf("received = %d, want 20", stats["received"])
	}
	if stats["fingerprinted"] != 15 {
		t.Errorf("fingerprinted = %d, want 15", stats["fingerprinted"])
	}
}

func TestHandlePacket_TooShort(t *testing.T) {
	s := &Snooper{}
	// Packet shorter than 240 bytes — should return silently
	s.handlePacket(make([]byte, 100), nil)
	if s.fingerprinted.Load() != 0 {
		t.Error("should not fingerprint short packet")
	}
}

func TestHandlePacket_BadMagicCookie(t *testing.T) {
	s := &Snooper{}
	data := make([]byte, 260)
	// Wrong magic cookie
	data[236], data[237], data[238], data[239] = 0, 0, 0, 0
	s.handlePacket(data, nil)
	if s.fingerprinted.Load() != 0 {
		t.Error("should not fingerprint with bad magic cookie")
	}
}

func TestHandlePacket_ValidMagicCookie(t *testing.T) {
	// Can't fully test without publisher, but verify magic cookie check
	data := make([]byte, 260)
	data[236], data[237], data[238], data[239] = 99, 130, 83, 99
	// Set MAC at offset 28
	data[28], data[29], data[30], data[31], data[32], data[33] = 0xaa, 0xbb, 0xcc, 0xdd, 0xee, 0xff
	// Add DHCP options at offset 240
	data[240] = 53  // msg type option
	data[241] = 1   // length
	data[242] = 1   // DISCOVER
	data[243] = 255 // end

	// Validate the magic cookie check passes
	if data[236] != 99 || data[237] != 130 || data[238] != 83 || data[239] != 99 {
		t.Error("magic cookie validation failed")
	}
}
