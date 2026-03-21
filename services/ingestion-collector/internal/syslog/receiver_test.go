package syslog

import (
	"testing"
)

func TestParsePRI(t *testing.T) {
	tests := []struct {
		pri      string
		facility string
		severity string
	}{
		{"134", "local0", "informational"}, // 16*8 + 6
		{"0", "kern", "emergency"},
		{"11", "user", "critical"},         // 1*8 + 3
		{"38", "auth", "informational"},    // 4*8 + 6
		{"191", "local7", "debug"},         // 23*8 + 7
	}

	for _, tt := range tests {
		t.Run(tt.pri, func(t *testing.T) {
			result := parsePRI(tt.pri)
			if result["facility"] != tt.facility {
				t.Errorf("parsePRI(%s) facility = %q, want %q", tt.pri, result["facility"], tt.facility)
			}
			if result["severity"] != tt.severity {
				t.Errorf("parsePRI(%s) severity = %q, want %q", tt.pri, result["severity"], tt.severity)
			}
		})
	}
}

func TestParseSyslog_RFC5424(t *testing.T) {
	r := &Receiver{}
	msg := `<134>1 2026-03-04T12:00:00Z switch1 sshd 12345 - User logged in`
	result := r.parseSyslog(msg)
	if result == nil {
		t.Fatal("parseSyslog returned nil for RFC 5424 message")
	}
	if result["format"] != "rfc5424" {
		t.Errorf("format = %q, want rfc5424", result["format"])
	}
	if result["hostname"] != "switch1" {
		t.Errorf("hostname = %q, want switch1", result["hostname"])
	}
	if result["app_name"] != "sshd" {
		t.Errorf("app_name = %q, want sshd", result["app_name"])
	}
	if result["severity"] != "informational" {
		t.Errorf("severity = %q, want informational", result["severity"])
	}
	if result["facility"] != "local0" {
		t.Errorf("facility = %q, want local0", result["facility"])
	}
}

func TestParseSyslog_RFC3164(t *testing.T) {
	r := &Receiver{}
	msg := `<38>Mar  4 12:00:00 switch1 %LINK-3-UPDOWN: Interface GigabitEthernet0/1, changed state to up`
	result := r.parseSyslog(msg)
	if result == nil {
		t.Fatal("parseSyslog returned nil for RFC 3164 message")
	}
	if result["format"] != "rfc3164" {
		t.Errorf("format = %q, want rfc3164", result["format"])
	}
	if result["hostname"] != "switch1" {
		t.Errorf("hostname = %q, want switch1", result["hostname"])
	}
	if result["severity"] != "informational" {
		t.Errorf("severity = %q, want informational", result["severity"])
	}
}

func TestParseSyslog_Unparseable(t *testing.T) {
	r := &Receiver{}
	msg := `This is not a valid syslog message`
	result := r.parseSyslog(msg)
	if result != nil {
		t.Errorf("parseSyslog should return nil for unparseable message, got %v", result)
	}
}

func TestSeverityNames(t *testing.T) {
	expected := []string{
		"emergency", "alert", "critical", "error",
		"warning", "notice", "informational", "debug",
	}
	if len(severityNames) != 8 {
		t.Fatalf("severityNames has %d entries, want 8", len(severityNames))
	}
	for i, name := range expected {
		if severityNames[i] != name {
			t.Errorf("severityNames[%d] = %q, want %q", i, severityNames[i], name)
		}
	}
}

func TestFacilityNames(t *testing.T) {
	if len(facilityNames) != 24 {
		t.Fatalf("facilityNames has %d entries, want 24", len(facilityNames))
	}
	// Spot check
	if facilityNames[0] != "kern" {
		t.Errorf("facilityNames[0] = %q, want kern", facilityNames[0])
	}
	if facilityNames[4] != "auth" {
		t.Errorf("facilityNames[4] = %q, want auth", facilityNames[4])
	}
	if facilityNames[16] != "local0" {
		t.Errorf("facilityNames[16] = %q, want local0", facilityNames[16])
	}
}

func TestReceiverStats(t *testing.T) {
	r := &Receiver{}
	stats := r.Stats()
	if stats["received"] != 0 || stats["parsed"] != 0 {
		t.Errorf("initial stats should be zero, got %v", stats)
	}
	r.received.Add(10)
	r.parsed.Add(8)
	stats = r.Stats()
	if stats["received"] != 10 {
		t.Errorf("received = %d, want 10", stats["received"])
	}
	if stats["parsed"] != 8 {
		t.Errorf("parsed = %d, want 8", stats["parsed"])
	}
}
