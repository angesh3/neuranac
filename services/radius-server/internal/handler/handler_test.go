package handler

import (
	"testing"
)

func TestVerifyPAPPassword_Plaintext(t *testing.T) {
	tests := []struct {
		name      string
		cleartext string
		stored    string
		want      bool
	}{
		{"match", "testing123", "testing123", true},
		{"mismatch", "wrong", "testing123", false},
		{"empty_cleartext", "", "testing123", false},
		{"empty_stored", "testing123", "", false},
		{"both_empty", "", "", false},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := verifyPAPPassword(tt.cleartext, tt.stored)
			if got != tt.want {
				t.Errorf("verifyPAPPassword(%q, %q) = %v, want %v", tt.cleartext, tt.stored, got, tt.want)
			}
		})
	}
}

func TestVerifyPAPPassword_BcryptPrefix(t *testing.T) {
	// Bcrypt hashes start with $2a$ or $2b$ - should use bcrypt.CompareHashAndPassword
	// With a fake hash that won't match, this should return false
	got := verifyPAPPassword("test", "$2a$10$fakeHashThatWontMatchAnything")
	if got != false {
		t.Errorf("verifyPAPPassword with invalid bcrypt hash should return false")
	}
}

func TestNormalizeMAC(t *testing.T) {
	tests := []struct {
		input string
		want  string
	}{
		{"aa:bb:cc:dd:ee:ff", "AA:BB:CC:DD:EE:FF"},
		{"AA-BB-CC-DD-EE-FF", "AA:BB:CC:DD:EE:FF"},
		{"aabb.ccdd.eeff", "AA:BB:CC:DD:EE:FF"},
		{"aabbccddeeff", "AA:BB:CC:DD:EE:FF"},
		{"short", "SHORT"},  // too short, returned as-is (uppercased)
		{"", ""},
	}
	for _, tt := range tests {
		t.Run(tt.input, func(t *testing.T) {
			got := NormalizeMAC(tt.input)
			if got != tt.want {
				t.Errorf("NormalizeMAC(%q) = %q, want %q", tt.input, got, tt.want)
			}
		})
	}
}

func TestIsMABRequest(t *testing.T) {
	tests := []struct {
		username         string
		callingStationID string
		want             bool
	}{
		{"AA:BB:CC:DD:EE:FF", "AA:BB:CC:DD:EE:FF", true},
		{"aabbccddeeff", "AA:BB:CC:DD:EE:FF", true},
		{"alice", "AA:BB:CC:DD:EE:FF", false},
		{"", "", false},
	}
	for _, tt := range tests {
		t.Run(tt.username+"_"+tt.callingStationID, func(t *testing.T) {
			got := isMABRequest(tt.username, tt.callingStationID)
			if got != tt.want {
				t.Errorf("isMABRequest(%q, %q) = %v, want %v", tt.username, tt.callingStationID, got, tt.want)
			}
		})
	}
}
