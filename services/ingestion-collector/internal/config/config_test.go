package config

import (
	"os"
	"testing"
)

func TestLoadDefaults(t *testing.T) {
	// Clear relevant env vars to test defaults
	envVars := []string{
		"NeuraNAC_ENV", "NEURANAC_NODE_ID", "NEURANAC_SITE_ID", "NEURANAC_SITE_TYPE",
		"DEPLOYMENT_MODE", "SNMP_TRAP_PORT", "SYSLOG_PORT", "NETFLOW_PORT",
		"DHCP_SNOOP_PORT", "HEALTH_PORT", "SNMP_COMMUNITY", "SNMP_POLL_INTERVAL",
		"POSTGRES_HOST", "POSTGRES_PORT", "POSTGRES_DB", "POSTGRES_USER",
		"POSTGRES_PASSWORD", "NATS_URL", "REDIS_HOST", "REDIS_PORT",
		"REDIS_PASSWORD", "BATCH_SIZE", "FLUSH_INTERVAL_MS", "LOG_LEVEL",
	}
	saved := make(map[string]string)
	for _, v := range envVars {
		saved[v] = os.Getenv(v)
		os.Unsetenv(v)
	}
	defer func() {
		for k, v := range saved {
			if v != "" {
				os.Setenv(k, v)
			}
		}
	}()

	cfg, err := Load()
	if err != nil {
		t.Fatalf("Load() error: %v", err)
	}

	if cfg.Env != "development" {
		t.Errorf("Env = %q, want development", cfg.Env)
	}
	if cfg.NodeID != "twin-a" {
		t.Errorf("NodeID = %q, want twin-a", cfg.NodeID)
	}
	if cfg.SNMPTrapPort != 1162 {
		t.Errorf("SNMPTrapPort = %d, want 1162", cfg.SNMPTrapPort)
	}
	if cfg.SyslogPort != 1514 {
		t.Errorf("SyslogPort = %d, want 1514", cfg.SyslogPort)
	}
	if cfg.NetFlowPort != 2055 {
		t.Errorf("NetFlowPort = %d, want 2055", cfg.NetFlowPort)
	}
	if cfg.DHCPPort != 6767 {
		t.Errorf("DHCPPort = %d, want 6767", cfg.DHCPPort)
	}
	if cfg.HealthPort != 9102 {
		t.Errorf("HealthPort = %d, want 9102", cfg.HealthPort)
	}
	if cfg.SNMPCommunity != "public" {
		t.Errorf("SNMPCommunity = %q, want public", cfg.SNMPCommunity)
	}
	if cfg.SNMPPollInterval != 300 {
		t.Errorf("SNMPPollInterval = %d, want 300", cfg.SNMPPollInterval)
	}
	if cfg.BatchSize != 100 {
		t.Errorf("BatchSize = %d, want 100", cfg.BatchSize)
	}
	if cfg.FlushInterval != 1000 {
		t.Errorf("FlushInterval = %d, want 1000", cfg.FlushInterval)
	}
	if cfg.NatsURL != "nats://localhost:4222" {
		t.Errorf("NatsURL = %q, want nats://localhost:4222", cfg.NatsURL)
	}
}

func TestLoadEnvOverrides(t *testing.T) {
	os.Setenv("SNMP_TRAP_PORT", "2162")
	os.Setenv("SYSLOG_PORT", "2514")
	os.Setenv("NETFLOW_PORT", "3055")
	os.Setenv("SNMP_COMMUNITY", "private")
	os.Setenv("BATCH_SIZE", "500")
	defer func() {
		os.Unsetenv("SNMP_TRAP_PORT")
		os.Unsetenv("SYSLOG_PORT")
		os.Unsetenv("NETFLOW_PORT")
		os.Unsetenv("SNMP_COMMUNITY")
		os.Unsetenv("BATCH_SIZE")
	}()

	cfg, err := Load()
	if err != nil {
		t.Fatalf("Load() error: %v", err)
	}

	if cfg.SNMPTrapPort != 2162 {
		t.Errorf("SNMPTrapPort = %d, want 2162", cfg.SNMPTrapPort)
	}
	if cfg.SyslogPort != 2514 {
		t.Errorf("SyslogPort = %d, want 2514", cfg.SyslogPort)
	}
	if cfg.NetFlowPort != 3055 {
		t.Errorf("NetFlowPort = %d, want 3055", cfg.NetFlowPort)
	}
	if cfg.SNMPCommunity != "private" {
		t.Errorf("SNMPCommunity = %q, want private", cfg.SNMPCommunity)
	}
	if cfg.BatchSize != 500 {
		t.Errorf("BatchSize = %d, want 500", cfg.BatchSize)
	}
}

func TestLoadProductionRequiresPassword(t *testing.T) {
	os.Setenv("NeuraNAC_ENV", "production")
	os.Setenv("POSTGRES_PASSWORD", "")
	defer func() {
		os.Unsetenv("NeuraNAC_ENV")
		os.Unsetenv("POSTGRES_PASSWORD")
	}()

	_, err := Load()
	if err == nil {
		t.Error("Load() should fail in production without POSTGRES_PASSWORD")
	}
}

func TestPostgresDSN(t *testing.T) {
	cfg := &Config{
		PostgresUser: "neuranac",
		PostgresPass: "secret",
		PostgresHost: "db.local",
		PostgresPort: 5432,
		PostgresDB:   "neuranac",
		PostgresSSL:  "require",
	}
	expected := "postgres://neuranac:secret@db.local:5432/neuranac?sslmode=require"
	if cfg.PostgresDSN() != expected {
		t.Errorf("PostgresDSN() = %q, want %q", cfg.PostgresDSN(), expected)
	}
}

func TestRedisAddr(t *testing.T) {
	cfg := &Config{RedisHost: "redis.local", RedisPort: 6380}
	if cfg.RedisAddr() != "redis.local:6380" {
		t.Errorf("RedisAddr() = %q, want redis.local:6380", cfg.RedisAddr())
	}
}

func TestGetEnv(t *testing.T) {
	os.Setenv("TEST_NeuraNAC_VAR", "hello")
	defer os.Unsetenv("TEST_NeuraNAC_VAR")

	if getEnv("TEST_NeuraNAC_VAR", "default") != "hello" {
		t.Error("getEnv should return env value")
	}
	if getEnv("TEST_NeuraNAC_MISSING", "default") != "default" {
		t.Error("getEnv should return default for missing var")
	}
}

func TestGetEnvInt(t *testing.T) {
	os.Setenv("TEST_NeuraNAC_INT", "42")
	defer os.Unsetenv("TEST_NeuraNAC_INT")

	if getEnvInt("TEST_NeuraNAC_INT", 0) != 42 {
		t.Error("getEnvInt should parse int from env")
	}
	if getEnvInt("TEST_NeuraNAC_MISSING_INT", 99) != 99 {
		t.Error("getEnvInt should return default for missing var")
	}

	os.Setenv("TEST_NeuraNAC_BAD_INT", "notanumber")
	defer os.Unsetenv("TEST_NeuraNAC_BAD_INT")
	if getEnvInt("TEST_NeuraNAC_BAD_INT", 77) != 77 {
		t.Error("getEnvInt should return default for non-integer")
	}
}
