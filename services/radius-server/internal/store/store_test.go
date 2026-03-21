package store

import (
	"testing"
)

func TestNADInfoStruct(t *testing.T) {
	nad := NADInfo{
		TenantID:      "t1",
		DeviceID:      "d1",
		SharedSecret:  "secret",
		Vendor:        "cisco",
		Model:         "C9300",
		CoAPort:       3799,
		RadSecEnabled: true,
	}

	if nad.TenantID != "t1" {
		t.Errorf("TenantID = %q, want %q", nad.TenantID, "t1")
	}
	if nad.SharedSecret != "secret" {
		t.Errorf("SharedSecret = %q, want %q", nad.SharedSecret, "secret")
	}
	if nad.CoAPort != 3799 {
		t.Errorf("CoAPort = %d, want 3799", nad.CoAPort)
	}
	if !nad.RadSecEnabled {
		t.Error("RadSecEnabled should be true")
	}
}

func TestEndpointInfoStruct(t *testing.T) {
	ep := EndpointInfo{
		ID:         "ep-1",
		MAC:        "AA:BB:CC:DD:EE:FF",
		DeviceType: "windows-pc",
		Vendor:     "Dell",
		OS:         "Windows 11",
		Status:     "active",
		GroupID:    "grp-1",
	}

	if ep.MAC != "AA:BB:CC:DD:EE:FF" {
		t.Errorf("MAC = %q, want %q", ep.MAC, "AA:BB:CC:DD:EE:FF")
	}
	if ep.DeviceType != "windows-pc" {
		t.Errorf("DeviceType = %q, want %q", ep.DeviceType, "windows-pc")
	}
	if ep.Status != "active" {
		t.Errorf("Status = %q, want %q", ep.Status, "active")
	}
}

func TestInternalUserStruct(t *testing.T) {
	user := InternalUser{
		ID:           "u1",
		TenantID:     "t1",
		Username:     "admin",
		PasswordHash: "$2a$10$xxx",
		Email:        "admin@neuranac.local",
		Groups:       []string{"admins", "operators"},
		Status:       "active",
	}

	if user.Username != "admin" {
		t.Errorf("Username = %q, want %q", user.Username, "admin")
	}
	if len(user.Groups) != 2 {
		t.Errorf("Groups count = %d, want 2", len(user.Groups))
	}
	if user.Groups[0] != "admins" {
		t.Errorf("Groups[0] = %q, want %q", user.Groups[0], "admins")
	}
}

func TestAIAgentInfoStruct(t *testing.T) {
	agent := AIAgentInfo{
		ID:         "a1",
		TenantID:   "t1",
		AgentName:  "copilot-1",
		AgentType:  "code-assistant",
		Status:     "active",
		AuthMethod: "certificate",
		Runtime:    "python3.12",
	}

	if agent.AgentName != "copilot-1" {
		t.Errorf("AgentName = %q, want %q", agent.AgentName, "copilot-1")
	}
	if agent.AuthMethod != "certificate" {
		t.Errorf("AuthMethod = %q, want %q", agent.AuthMethod, "certificate")
	}
}

func TestPolicyResultStruct(t *testing.T) {
	pr := PolicyResult{
		Decision:  "permit",
		VLAN:      "100",
		SGT:       15,
		RiskScore: 42,
	}

	if pr.Decision != "permit" {
		t.Errorf("Decision = %q, want %q", pr.Decision, "permit")
	}
	if pr.VLAN != "100" {
		t.Errorf("VLAN = %q, want %q", pr.VLAN, "100")
	}
	if pr.SGT != 15 {
		t.Errorf("SGT = %d, want 15", pr.SGT)
	}
	if pr.RiskScore != 42 {
		t.Errorf("RiskScore = %d, want 42", pr.RiskScore)
	}
}

func TestDataStoreStruct(t *testing.T) {
	// Verify struct can be created with nil fields (for unit testing scenarios)
	ds := &DataStore{}
	if ds.DB != nil {
		t.Error("DB should be nil")
	}
	if ds.Redis != nil {
		t.Error("Redis should be nil")
	}
	if ds.NATS != nil {
		t.Error("NATS should be nil")
	}
	if ds.Logger != nil {
		t.Error("Logger should be nil")
	}
}
