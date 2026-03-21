package config

import (
	"fmt"
	"os"
	"strconv"
)

type Config struct {
	Env                string
	NodeID             string
	SiteID             string // UUID of this site in neuranac_sites
	SiteType           string // "onprem" or "cloud"
	DeploymentMode     string // "standalone" or "hybrid"
	RadiusAuthPort     int
	RadiusAcctPort     int
	RadSecPort         int
	CoAPort            int
	TacacsPort         int
	PostgresHost       string
	PostgresPort       int
	PostgresDB         string
	PostgresUser       string
	PostgresPass       string
	PostgresSSL        string
	RedisHost          string
	RedisPort          int
	RedisPass          string
	NatsURL            string
	PolicyEngineGRPC   string
	AIEngineGRPC       string
	TLSCertPath        string
	TLSAutoGenerate    bool
	GRPCClientCert     string
	GRPCClientKey      string
	GRPCCACert         string
	RadSecSecret       string
	CacheEncryptionKey string
	AllowedNASCIDRs    string // comma-separated CIDRs, empty = allow all
	RadiusRateLimit    int    // max requests per second per source IP, 0 = unlimited
	LogLevel           string
}

func Load() (*Config, error) {
	cfg := &Config{
		Env:                getEnv("NeuraNAC_ENV", "development"),
		NodeID:             getEnv("NEURANAC_NODE_ID", "twin-a"),
		SiteID:             getEnv("NEURANAC_SITE_ID", "00000000-0000-0000-0000-000000000001"),
		SiteType:           getEnv("NEURANAC_SITE_TYPE", "onprem"),
		DeploymentMode:     getEnv("DEPLOYMENT_MODE", "standalone"),
		RadiusAuthPort:     getEnvInt("RADIUS_AUTH_PORT", 1812),
		RadiusAcctPort:     getEnvInt("RADIUS_ACCT_PORT", 1813),
		RadSecPort:         getEnvInt("RADIUS_RADSEC_PORT", 2083),
		CoAPort:            getEnvInt("RADIUS_COA_PORT", 3799),
		TacacsPort:         getEnvInt("TACACS_PORT", 49),
		PostgresHost:       getEnv("POSTGRES_HOST", "localhost"),
		PostgresPort:       getEnvInt("POSTGRES_PORT", 5432),
		PostgresDB:         getEnv("POSTGRES_DB", "neuranac"),
		PostgresUser:       getEnv("POSTGRES_USER", "neuranac"),
		PostgresPass:       getEnv("POSTGRES_PASSWORD", ""),
		PostgresSSL:        getEnv("POSTGRES_SSL_MODE", "disable"),
		RedisHost:          getEnv("REDIS_HOST", "localhost"),
		RedisPort:          getEnvInt("REDIS_PORT", 6379),
		RedisPass:          getEnv("REDIS_PASSWORD", ""),
		NatsURL:            getEnv("NATS_URL", "nats://localhost:4222"),
		PolicyEngineGRPC:   getEnv("POLICY_ENGINE_GRPC", "localhost:9091"),
		AIEngineGRPC:       getEnv("AI_ENGINE_GRPC", "localhost:9092"),
		TLSCertPath:        getEnv("TLS_CERT_PATH", "/etc/neuranac/certs"),
		TLSAutoGenerate:    getEnv("TLS_AUTO_GENERATE", "true") == "true",
		GRPCClientCert:     getEnv("GRPC_CLIENT_CERT", ""),
		GRPCClientKey:      getEnv("GRPC_CLIENT_KEY", ""),
		GRPCCACert:         getEnv("GRPC_CA_CERT", ""),
		RadSecSecret:       getEnv("RADSEC_SECRET", "radsec"),
		CacheEncryptionKey: getEnv("CACHE_ENCRYPTION_KEY", ""),
		AllowedNASCIDRs:    getEnv("RADIUS_ALLOWED_CIDRS", ""),
		RadiusRateLimit:    getEnvInt("RADIUS_RATE_LIMIT", 0),
		LogLevel:           getEnv("LOG_LEVEL", "info"),
	}

	if cfg.PostgresPass == "" && cfg.Env == "production" {
		return nil, fmt.Errorf("POSTGRES_PASSWORD is required in production")
	}

	return cfg, nil
}

func (c *Config) PostgresDSN() string {
	return fmt.Sprintf("postgres://%s:%s@%s:%d/%s?sslmode=%s",
		c.PostgresUser, c.PostgresPass, c.PostgresHost, c.PostgresPort, c.PostgresDB, c.PostgresSSL)
}

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
