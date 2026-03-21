package config

import (
	"os"
	"testing"
)

func TestLoadDefaults(t *testing.T) {
	// Clear production-required vars
	os.Unsetenv("NeuraNAC_ENV")
	os.Unsetenv("POSTGRES_PASSWORD")

	cfg, err := Load()
	if err != nil {
		t.Fatalf("Load() error: %v", err)
	}

	if cfg.Env != "development" {
		t.Errorf("Env = %q, want %q", cfg.Env, "development")
	}
	if cfg.NodeID != "twin-a" {
		t.Errorf("NodeID = %q, want %q", cfg.NodeID, "twin-a")
	}
	if cfg.RadiusAuthPort != 1812 {
		t.Errorf("RadiusAuthPort = %d, want 1812", cfg.RadiusAuthPort)
	}
	if cfg.RadiusAcctPort != 1813 {
		t.Errorf("RadiusAcctPort = %d, want 1813", cfg.RadiusAcctPort)
	}
	if cfg.RadSecPort != 2083 {
		t.Errorf("RadSecPort = %d, want 2083", cfg.RadSecPort)
	}
	if cfg.CoAPort != 3799 {
		t.Errorf("CoAPort = %d, want 3799", cfg.CoAPort)
	}
	if cfg.TacacsPort != 49 {
		t.Errorf("TacacsPort = %d, want 49", cfg.TacacsPort)
	}
	if cfg.PostgresHost != "localhost" {
		t.Errorf("PostgresHost = %q, want %q", cfg.PostgresHost, "localhost")
	}
	if cfg.PostgresPort != 5432 {
		t.Errorf("PostgresPort = %d, want 5432", cfg.PostgresPort)
	}
	if cfg.RedisHost != "localhost" {
		t.Errorf("RedisHost = %q, want %q", cfg.RedisHost, "localhost")
	}
	if cfg.RedisPort != 6379 {
		t.Errorf("RedisPort = %d, want 6379", cfg.RedisPort)
	}
	if cfg.NatsURL != "nats://localhost:4222" {
		t.Errorf("NatsURL = %q, want %q", cfg.NatsURL, "nats://localhost:4222")
	}
	if cfg.TLSAutoGenerate != true {
		t.Error("TLSAutoGenerate should be true by default")
	}
}

func TestLoadFromEnv(t *testing.T) {
	os.Setenv("NeuraNAC_ENV", "staging")
	os.Setenv("NEURANAC_NODE_ID", "node-b")
	os.Setenv("RADIUS_AUTH_PORT", "11812")
	os.Setenv("POSTGRES_HOST", "db.example.com")
	os.Setenv("POSTGRES_PORT", "15432")
	os.Setenv("POSTGRES_PASSWORD", "secret123")
	os.Setenv("REDIS_HOST", "redis.example.com")
	os.Setenv("REDIS_PORT", "16379")
	defer func() {
		os.Unsetenv("NeuraNAC_ENV")
		os.Unsetenv("NEURANAC_NODE_ID")
		os.Unsetenv("RADIUS_AUTH_PORT")
		os.Unsetenv("POSTGRES_HOST")
		os.Unsetenv("POSTGRES_PORT")
		os.Unsetenv("POSTGRES_PASSWORD")
		os.Unsetenv("REDIS_HOST")
		os.Unsetenv("REDIS_PORT")
	}()

	cfg, err := Load()
	if err != nil {
		t.Fatalf("Load() error: %v", err)
	}

	if cfg.Env != "staging" {
		t.Errorf("Env = %q, want %q", cfg.Env, "staging")
	}
	if cfg.NodeID != "node-b" {
		t.Errorf("NodeID = %q, want %q", cfg.NodeID, "node-b")
	}
	if cfg.RadiusAuthPort != 11812 {
		t.Errorf("RadiusAuthPort = %d, want 11812", cfg.RadiusAuthPort)
	}
	if cfg.PostgresHost != "db.example.com" {
		t.Errorf("PostgresHost = %q, want %q", cfg.PostgresHost, "db.example.com")
	}
	if cfg.PostgresPort != 15432 {
		t.Errorf("PostgresPort = %d, want 15432", cfg.PostgresPort)
	}
	if cfg.RedisHost != "redis.example.com" {
		t.Errorf("RedisHost = %q, want %q", cfg.RedisHost, "redis.example.com")
	}
	if cfg.RedisPort != 16379 {
		t.Errorf("RedisPort = %d, want 16379", cfg.RedisPort)
	}
}

func TestLoadProductionRequiresPassword(t *testing.T) {
	os.Setenv("NeuraNAC_ENV", "production")
	os.Unsetenv("POSTGRES_PASSWORD")
	defer os.Unsetenv("NeuraNAC_ENV")

	_, err := Load()
	if err == nil {
		t.Error("Load() should fail in production without POSTGRES_PASSWORD")
	}
}

func TestLoadProductionWithPassword(t *testing.T) {
	os.Setenv("NeuraNAC_ENV", "production")
	os.Setenv("POSTGRES_PASSWORD", "prod-secret")
	defer func() {
		os.Unsetenv("NeuraNAC_ENV")
		os.Unsetenv("POSTGRES_PASSWORD")
	}()

	cfg, err := Load()
	if err != nil {
		t.Fatalf("Load() error: %v", err)
	}
	if cfg.PostgresPass != "prod-secret" {
		t.Errorf("PostgresPass = %q, want %q", cfg.PostgresPass, "prod-secret")
	}
}

func TestPostgresDSN(t *testing.T) {
	cfg := &Config{
		PostgresUser: "neuranac",
		PostgresPass: "pass",
		PostgresHost: "db",
		PostgresPort: 5432,
		PostgresDB:   "neuranac",
		PostgresSSL:  "disable",
	}
	dsn := cfg.PostgresDSN()
	expected := "postgres://neuranac:pass@db:5432/neuranac?sslmode=disable"
	if dsn != expected {
		t.Errorf("PostgresDSN() = %q, want %q", dsn, expected)
	}
}

func TestRedisAddr(t *testing.T) {
	cfg := &Config{RedisHost: "redis", RedisPort: 6379}
	addr := cfg.RedisAddr()
	if addr != "redis:6379" {
		t.Errorf("RedisAddr() = %q, want %q", addr, "redis:6379")
	}
}

func TestSiteDeploymentDefaults(t *testing.T) {
	os.Unsetenv("NEURANAC_SITE_ID")
	os.Unsetenv("NEURANAC_SITE_TYPE")
	os.Unsetenv("DEPLOYMENT_MODE")

	cfg, err := Load()
	if err != nil {
		t.Fatalf("Load() error: %v", err)
	}

	if cfg.SiteID != "00000000-0000-0000-0000-000000000001" {
		t.Errorf("SiteID = %q, want default UUID", cfg.SiteID)
	}
	if cfg.SiteType != "onprem" {
		t.Errorf("SiteType = %q, want %q", cfg.SiteType, "onprem")
	}
	if cfg.DeploymentMode != "standalone" {
		t.Errorf("DeploymentMode = %q, want %q", cfg.DeploymentMode, "standalone")
	}
}

func TestSiteDeploymentFromEnv(t *testing.T) {
	os.Setenv("NEURANAC_SITE_ID", "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
	os.Setenv("NEURANAC_SITE_TYPE", "cloud")
	os.Setenv("DEPLOYMENT_MODE", "hybrid")
	defer func() {
		os.Unsetenv("NEURANAC_SITE_ID")
		os.Unsetenv("NEURANAC_SITE_TYPE")
		os.Unsetenv("DEPLOYMENT_MODE")
	}()

	cfg, err := Load()
	if err != nil {
		t.Fatalf("Load() error: %v", err)
	}

	if cfg.SiteID != "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee" {
		t.Errorf("SiteID = %q, want custom UUID", cfg.SiteID)
	}
	if cfg.SiteType != "cloud" {
		t.Errorf("SiteType = %q, want %q", cfg.SiteType, "cloud")
	}
	if cfg.DeploymentMode != "hybrid" {
		t.Errorf("DeploymentMode = %q, want %q", cfg.DeploymentMode, "hybrid")
	}
}

func TestGetEnv(t *testing.T) {
	os.Setenv("TEST_KEY_123", "hello")
	defer os.Unsetenv("TEST_KEY_123")

	if v := getEnv("TEST_KEY_123", "default"); v != "hello" {
		t.Errorf("getEnv = %q, want %q", v, "hello")
	}
	if v := getEnv("NONEXISTENT_KEY_XYZ", "default"); v != "default" {
		t.Errorf("getEnv = %q, want %q", v, "default")
	}
}

func TestGetEnvInt(t *testing.T) {
	os.Setenv("TEST_INT_123", "42")
	defer os.Unsetenv("TEST_INT_123")

	if v := getEnvInt("TEST_INT_123", 0); v != 42 {
		t.Errorf("getEnvInt = %d, want 42", v)
	}
	if v := getEnvInt("NONEXISTENT_INT_XYZ", 99); v != 99 {
		t.Errorf("getEnvInt = %d, want 99", v)
	}

	os.Setenv("TEST_INT_BAD", "notanumber")
	defer os.Unsetenv("TEST_INT_BAD")
	if v := getEnvInt("TEST_INT_BAD", 7); v != 7 {
		t.Errorf("getEnvInt with bad value = %d, want 7", v)
	}
}
