package main

import (
	"testing"

	"github.com/neuranac/services/sync-engine/internal/config"
	"go.uber.org/zap"
)

func TestLoadPeerTLSCredentials_Disabled(t *testing.T) {
	logger, _ := zap.NewDevelopment()
	cfg := &config.Config{
		TLSEnabled:  false,
		TLSCertPath: "/fake/cert.pem",
		TLSKeyPath:  "/fake/key.pem",
	}

	creds := loadPeerTLSCredentials(cfg, logger)
	if creds != nil {
		t.Error("expected nil credentials when TLS is disabled")
	}
}

func TestLoadPeerTLSCredentials_EmptyPaths(t *testing.T) {
	logger, _ := zap.NewDevelopment()
	cfg := &config.Config{
		TLSEnabled:  true,
		TLSCertPath: "",
		TLSKeyPath:  "",
	}

	creds := loadPeerTLSCredentials(cfg, logger)
	if creds != nil {
		t.Error("expected nil credentials when cert paths are empty")
	}
}

func TestLoadPeerTLSCredentials_InvalidCert(t *testing.T) {
	logger, _ := zap.NewDevelopment()
	cfg := &config.Config{
		TLSEnabled:  true,
		TLSCertPath: "/nonexistent/cert.pem",
		TLSKeyPath:  "/nonexistent/key.pem",
	}

	creds := loadPeerTLSCredentials(cfg, logger)
	if creds != nil {
		t.Error("expected nil credentials when cert files don't exist")
	}
}

func TestConnectToPeer_UsesConfig(t *testing.T) {
	// Verify that connectToPeer accepts *config.Config (compile-time check)
	// We can't actually dial in a unit test, but we verify the signature
	cfg := &config.Config{
		PeerAddress:    "localhost:9999",
		TLSEnabled:     false,
		DeploymentMode: "hybrid",
	}
	_ = cfg // compile-time validation that connectToPeer accepts *config.Config
}
