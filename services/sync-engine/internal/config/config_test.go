package config

import (
	"os"
	"testing"
	"time"
)

func TestLoadDefaults(t *testing.T) {
	// Clear env vars that might affect defaults
	for _, k := range []string{"NEURANAC_NODE_ID", "NeuraNAC_ENV", "NEURANAC_SITE_TYPE", "SYNC_GRPC_PORT",
		"SYNC_PEER_ADDRESS", "DATABASE_URL", "SYNC_TLS_ENABLED", "SYNC_HUB_REPLICATOR_ENABLED"} {
		os.Unsetenv(k)
	}

	cfg := Load()

	if cfg.NodeID != "twin-a" {
		t.Errorf("NodeID = %q, want %q", cfg.NodeID, "twin-a")
	}
	if cfg.Env != "development" {
		t.Errorf("Env = %q, want %q", cfg.Env, "development")
	}
	if cfg.SiteType != "onprem" {
		t.Errorf("SiteType = %q, want %q", cfg.SiteType, "onprem")
	}
	if cfg.GRPCPort != "9090" {
		t.Errorf("GRPCPort = %q, want %q", cfg.GRPCPort, "9090")
	}
	if cfg.HealthPort != "9100" {
		t.Errorf("HealthPort = %q, want %q", cfg.HealthPort, "9100")
	}
	if cfg.MaxRecvMsgSize != 10*1024*1024 {
		t.Errorf("MaxRecvMsgSize = %d, want %d", cfg.MaxRecvMsgSize, 10*1024*1024)
	}
	if cfg.JournalBatchSize != 100 {
		t.Errorf("JournalBatchSize = %d, want 100", cfg.JournalBatchSize)
	}
	if cfg.JournalPollInterval != 2*time.Second {
		t.Errorf("JournalPollInterval = %v, want 2s", cfg.JournalPollInterval)
	}
	if cfg.TLSEnabled {
		t.Error("TLSEnabled should be false by default")
	}
	if cfg.HubReplicatorEnabled {
		t.Error("HubReplicatorEnabled should be false by default")
	}
}

func TestLoadFromEnv(t *testing.T) {
	os.Setenv("NEURANAC_NODE_ID", "node-x")
	os.Setenv("NeuraNAC_ENV", "production")
	os.Setenv("NEURANAC_SITE_TYPE", "cloud")
	os.Setenv("SYNC_GRPC_PORT", "9999")
	os.Setenv("SYNC_PEER_ADDRESS", "peer:9090")
	os.Setenv("SYNC_TLS_ENABLED", "true")
	os.Setenv("SYNC_HUB_REPLICATOR_ENABLED", "true")
	os.Setenv("SYNC_JOURNAL_BATCH_SIZE", "500")
	os.Setenv("SYNC_JOURNAL_POLL_INTERVAL", "5s")
	defer func() {
		for _, k := range []string{"NEURANAC_NODE_ID", "NeuraNAC_ENV", "NEURANAC_SITE_TYPE", "SYNC_GRPC_PORT",
			"SYNC_PEER_ADDRESS", "SYNC_TLS_ENABLED", "SYNC_HUB_REPLICATOR_ENABLED",
			"SYNC_JOURNAL_BATCH_SIZE", "SYNC_JOURNAL_POLL_INTERVAL"} {
			os.Unsetenv(k)
		}
	}()

	cfg := Load()

	if cfg.NodeID != "node-x" {
		t.Errorf("NodeID = %q, want %q", cfg.NodeID, "node-x")
	}
	if cfg.Env != "production" {
		t.Errorf("Env = %q, want %q", cfg.Env, "production")
	}
	if cfg.SiteType != "cloud" {
		t.Errorf("SiteType = %q, want %q", cfg.SiteType, "cloud")
	}
	if cfg.GRPCPort != "9999" {
		t.Errorf("GRPCPort = %q, want %q", cfg.GRPCPort, "9999")
	}
	if cfg.PeerAddress != "peer:9090" {
		t.Errorf("PeerAddress = %q, want %q", cfg.PeerAddress, "peer:9090")
	}
	if !cfg.TLSEnabled {
		t.Error("TLSEnabled should be true")
	}
	if !cfg.HubReplicatorEnabled {
		t.Error("HubReplicatorEnabled should be true")
	}
	if cfg.JournalBatchSize != 500 {
		t.Errorf("JournalBatchSize = %d, want 500", cfg.JournalBatchSize)
	}
	if cfg.JournalPollInterval != 5*time.Second {
		t.Errorf("JournalPollInterval = %v, want 5s", cfg.JournalPollInterval)
	}
}

func TestIsDevelopment(t *testing.T) {
	cfg := &Config{Env: "development"}
	if !cfg.IsDevelopment() {
		t.Error("IsDevelopment() should be true for development")
	}

	cfg.Env = "production"
	if cfg.IsDevelopment() {
		t.Error("IsDevelopment() should be false for production")
	}
}

func TestHasPeer(t *testing.T) {
	cfg := &Config{PeerAddress: ""}
	if cfg.HasPeer() {
		t.Error("HasPeer() should be false when empty")
	}

	cfg.PeerAddress = "peer:9090"
	if !cfg.HasPeer() {
		t.Error("HasPeer() should be true when set")
	}
}

func TestBuildDatabaseURL(t *testing.T) {
	// With DATABASE_URL env var
	os.Setenv("DATABASE_URL", "postgres://custom:pass@host:5432/mydb")
	defer os.Unsetenv("DATABASE_URL")

	cfg := &Config{}
	url := cfg.buildDatabaseURL()
	if url != "postgres://custom:pass@host:5432/mydb" {
		t.Errorf("buildDatabaseURL() = %q, want custom URL", url)
	}

	// Without DATABASE_URL
	os.Unsetenv("DATABASE_URL")
	url = cfg.buildDatabaseURL()
	if url == "" {
		t.Error("buildDatabaseURL() should return a non-empty URL")
	}
}

func TestGetEnvHelpers(t *testing.T) {
	os.Setenv("TEST_SYNC_STR", "hello")
	os.Setenv("TEST_SYNC_INT", "42")
	os.Setenv("TEST_SYNC_BOOL", "true")
	os.Setenv("TEST_SYNC_DUR", "10s")
	defer func() {
		os.Unsetenv("TEST_SYNC_STR")
		os.Unsetenv("TEST_SYNC_INT")
		os.Unsetenv("TEST_SYNC_BOOL")
		os.Unsetenv("TEST_SYNC_DUR")
	}()

	if v := getEnv("TEST_SYNC_STR", "x"); v != "hello" {
		t.Errorf("getEnv = %q, want %q", v, "hello")
	}
	if v := getEnv("MISSING", "fallback"); v != "fallback" {
		t.Errorf("getEnv = %q, want %q", v, "fallback")
	}
	if v := getEnvInt("TEST_SYNC_INT", 0); v != 42 {
		t.Errorf("getEnvInt = %d, want 42", v)
	}
	if v := getEnvInt("MISSING", 99); v != 99 {
		t.Errorf("getEnvInt = %d, want 99", v)
	}
	if v := getEnvBool("TEST_SYNC_BOOL", false); !v {
		t.Error("getEnvBool should be true")
	}
	if v := getEnvBool("MISSING", false); v {
		t.Error("getEnvBool should be false for missing key")
	}
	if v := getEnvDuration("TEST_SYNC_DUR", time.Second); v != 10*time.Second {
		t.Errorf("getEnvDuration = %v, want 10s", v)
	}
	if v := getEnvDuration("MISSING", 3*time.Second); v != 3*time.Second {
		t.Errorf("getEnvDuration = %v, want 3s", v)
	}
}
