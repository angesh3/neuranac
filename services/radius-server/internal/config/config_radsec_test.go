package config

import (
	"os"
	"testing"
)

func TestRadSecSecretDefault(t *testing.T) {
	// Clear env to test default
	os.Unsetenv("RADSEC_SECRET")
	cfg, err := Load()
	if err != nil {
		t.Fatalf("Load error: %v", err)
	}
	if cfg.RadSecSecret != "radsec" {
		t.Errorf("RadSecSecret = %q, want %q", cfg.RadSecSecret, "radsec")
	}
}

func TestRadSecSecretFromEnv(t *testing.T) {
	os.Setenv("RADSEC_SECRET", "my-custom-radsec-secret")
	defer os.Unsetenv("RADSEC_SECRET")

	cfg, err := Load()
	if err != nil {
		t.Fatalf("Load error: %v", err)
	}
	if cfg.RadSecSecret != "my-custom-radsec-secret" {
		t.Errorf("RadSecSecret = %q, want %q", cfg.RadSecSecret, "my-custom-radsec-secret")
	}
}
