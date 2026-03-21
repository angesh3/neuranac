package config

import (
	"fmt"
	"os"
	"strconv"
)

// Config holds all configuration for the ingestion collector service.
type Config struct {
	Env            string
	NodeID         string
	SiteID         string
	SiteType       string
	DeploymentMode string

	// Listener ports
	SNMPTrapPort int
	SyslogPort   int
	NetFlowPort  int
	DHCPPort     int
	HealthPort   int

	// SNMP polling
	SNMPPollInterval int // seconds between SNMP polls
	SNMPCommunity    string
	SNMPVersion      string // "2c" or "3"
	SNMPv3User       string
	SNMPv3AuthPass   string
	SNMPv3PrivPass   string

	// PostgreSQL
	PostgresHost string
	PostgresPort int
	PostgresDB   string
	PostgresUser string
	PostgresPass string
	PostgresSSL  string

	// NATS
	NatsURL string

	// Redis (for dedup + rate tracking)
	RedisHost string
	RedisPort int
	RedisPass string

	// Batch settings
	BatchSize     int
	FlushInterval int // milliseconds

	LogLevel string
}

// Load reads configuration from environment variables with defaults.
func Load() (*Config, error) {
	cfg := &Config{
		Env:            getEnv("NeuraNAC_ENV", "development"),
		NodeID:         getEnv("NEURANAC_NODE_ID", "twin-a"),
		SiteID:         getEnv("NEURANAC_SITE_ID", "00000000-0000-0000-0000-000000000001"),
		SiteType:       getEnv("NEURANAC_SITE_TYPE", "onprem"),
		DeploymentMode: getEnv("DEPLOYMENT_MODE", "standalone"),

		SNMPTrapPort: getEnvInt("SNMP_TRAP_PORT", 1162),
		SyslogPort:   getEnvInt("SYSLOG_PORT", 1514),
		NetFlowPort:  getEnvInt("NETFLOW_PORT", 2055),
		DHCPPort:     getEnvInt("DHCP_SNOOP_PORT", 6767),
		HealthPort:   getEnvInt("HEALTH_PORT", 9102),

		SNMPPollInterval: getEnvInt("SNMP_POLL_INTERVAL", 300),
		SNMPCommunity:    getEnv("SNMP_COMMUNITY", "public"),
		SNMPVersion:      getEnv("SNMP_VERSION", "2c"),
		SNMPv3User:       getEnv("SNMPV3_USER", ""),
		SNMPv3AuthPass:   getEnv("SNMPV3_AUTH_PASS", ""),
		SNMPv3PrivPass:   getEnv("SNMPV3_PRIV_PASS", ""),

		PostgresHost: getEnv("POSTGRES_HOST", "localhost"),
		PostgresPort: getEnvInt("POSTGRES_PORT", 5432),
		PostgresDB:   getEnv("POSTGRES_DB", "neuranac"),
		PostgresUser: getEnv("POSTGRES_USER", "neuranac"),
		PostgresPass: getEnv("POSTGRES_PASSWORD", ""),
		PostgresSSL:  getEnv("POSTGRES_SSL_MODE", "disable"),

		NatsURL: getEnv("NATS_URL", "nats://localhost:4222"),

		RedisHost: getEnv("REDIS_HOST", "localhost"),
		RedisPort: getEnvInt("REDIS_PORT", 6379),
		RedisPass: getEnv("REDIS_PASSWORD", ""),

		BatchSize:     getEnvInt("BATCH_SIZE", 100),
		FlushInterval: getEnvInt("FLUSH_INTERVAL_MS", 1000),

		LogLevel: getEnv("LOG_LEVEL", "info"),
	}

	if cfg.PostgresPass == "" && cfg.Env == "production" {
		return nil, fmt.Errorf("POSTGRES_PASSWORD is required in production")
	}

	return cfg, nil
}

// PostgresDSN returns the PostgreSQL connection string.
func (c *Config) PostgresDSN() string {
	return fmt.Sprintf("postgres://%s:%s@%s:%d/%s?sslmode=%s",
		c.PostgresUser, c.PostgresPass, c.PostgresHost, c.PostgresPort, c.PostgresDB, c.PostgresSSL)
}

// RedisAddr returns the Redis address.
func (c *Config) RedisAddr() string {
	return fmt.Sprintf("%s:%d", c.RedisHost, c.RedisPort)
}

func getEnv(key, defaultVal string) string {
	if val := os.Getenv(key); val != "" {
		return val
	}
	return defaultVal
}

func getEnvInt(key string, defaultVal int) int {
	if val := os.Getenv(key); val != "" {
		if intVal, err := strconv.Atoi(val); err == nil {
			return intVal
		}
	}
	return defaultVal
}
