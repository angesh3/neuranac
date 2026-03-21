package tlsutil

import (
	"crypto/tls"
	"crypto/x509"
	"fmt"
	"os"

	"google.golang.org/grpc/credentials"
)

// LoadClientMTLS builds gRPC TransportCredentials for mTLS client connections.
// Falls back to insecure if cert files are missing and allowInsecure is true.
//
// Env vars / paths:
//
//	certFile  – client certificate (PEM)
//	keyFile   – client private key (PEM)
//	caFile    – CA certificate used to verify the server (PEM)
func LoadClientMTLS(certFile, keyFile, caFile string, allowInsecure bool) (credentials.TransportCredentials, error) {
	// If any path is empty, fall back
	if certFile == "" || keyFile == "" || caFile == "" {
		if allowInsecure {
			return nil, nil // caller should use insecure.NewCredentials()
		}
		return nil, fmt.Errorf("mTLS cert paths not configured and insecure fallback disallowed")
	}

	// Check files exist before loading
	for _, f := range []string{certFile, keyFile, caFile} {
		if _, err := os.Stat(f); os.IsNotExist(err) {
			if allowInsecure {
				return nil, nil
			}
			return nil, fmt.Errorf("mTLS file not found: %s", f)
		}
	}

	cert, err := tls.LoadX509KeyPair(certFile, keyFile)
	if err != nil {
		return nil, fmt.Errorf("load client key-pair: %w", err)
	}

	caPEM, err := os.ReadFile(caFile)
	if err != nil {
		return nil, fmt.Errorf("read CA cert: %w", err)
	}
	caPool := x509.NewCertPool()
	if !caPool.AppendCertsFromPEM(caPEM) {
		return nil, fmt.Errorf("failed to parse CA certificate")
	}

	tlsCfg := &tls.Config{
		Certificates: []tls.Certificate{cert},
		RootCAs:      caPool,
		MinVersion:   tls.VersionTLS13,
	}

	return credentials.NewTLS(tlsCfg), nil
}

// LoadServerMTLS builds gRPC TransportCredentials for mTLS server listeners.
func LoadServerMTLS(certFile, keyFile, caFile string) (credentials.TransportCredentials, error) {
	cert, err := tls.LoadX509KeyPair(certFile, keyFile)
	if err != nil {
		return nil, fmt.Errorf("load server key-pair: %w", err)
	}

	caPEM, err := os.ReadFile(caFile)
	if err != nil {
		return nil, fmt.Errorf("read CA cert: %w", err)
	}
	caPool := x509.NewCertPool()
	if !caPool.AppendCertsFromPEM(caPEM) {
		return nil, fmt.Errorf("failed to parse CA certificate")
	}

	tlsCfg := &tls.Config{
		Certificates: []tls.Certificate{cert},
		ClientCAs:    caPool,
		ClientAuth:   tls.RequireAndVerifyClientCert,
		MinVersion:   tls.VersionTLS13,
	}

	return credentials.NewTLS(tlsCfg), nil
}
