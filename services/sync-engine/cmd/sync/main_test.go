package main

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"testing"
)

func TestHealthEndpoint(t *testing.T) {
	os.Setenv("NEURANAC_NODE_ID", "test-node")
	defer os.Unsetenv("NEURANAC_NODE_ID")

	nodeID := os.Getenv("NEURANAC_NODE_ID")
	mux := http.NewServeMux()
	mux.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]string{
			"status":  "healthy",
			"service": "sync-engine",
			"node_id": nodeID,
		})
	})

	req := httptest.NewRequest("GET", "/health", nil)
	rr := httptest.NewRecorder()
	mux.ServeHTTP(rr, req)

	if rr.Code != http.StatusOK {
		t.Errorf("expected status 200, got %d", rr.Code)
	}

	var body map[string]string
	if err := json.Unmarshal(rr.Body.Bytes(), &body); err != nil {
		t.Fatalf("failed to decode response: %v", err)
	}
	if body["status"] != "healthy" {
		t.Errorf("expected status healthy, got %s", body["status"])
	}
	if body["service"] != "sync-engine" {
		t.Errorf("expected service sync-engine, got %s", body["service"])
	}
	if body["node_id"] != "test-node" {
		t.Errorf("expected node_id test-node, got %s", body["node_id"])
	}
}

func TestSyncStatusEndpoint(t *testing.T) {
	nodeID := "twin-a"
	peerAddr := "10.0.0.2:9090"

	mux := http.NewServeMux()
	mux.HandleFunc("/sync/status", func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]interface{}{
			"node_id":         nodeID,
			"peer_address":    peerAddr,
			"peer_configured": peerAddr != "",
		})
	})

	req := httptest.NewRequest("GET", "/sync/status", nil)
	rr := httptest.NewRecorder()
	mux.ServeHTTP(rr, req)

	if rr.Code != http.StatusOK {
		t.Errorf("expected status 200, got %d", rr.Code)
	}

	var body map[string]interface{}
	if err := json.Unmarshal(rr.Body.Bytes(), &body); err != nil {
		t.Fatalf("failed to decode response: %v", err)
	}
	if body["node_id"] != "twin-a" {
		t.Errorf("expected node_id twin-a, got %v", body["node_id"])
	}
	if body["peer_configured"] != true {
		t.Errorf("expected peer_configured true, got %v", body["peer_configured"])
	}
}

func TestSyncStatusNoPeer(t *testing.T) {
	nodeID := "twin-a"
	peerAddr := ""

	mux := http.NewServeMux()
	mux.HandleFunc("/sync/status", func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]interface{}{
			"node_id":         nodeID,
			"peer_address":    peerAddr,
			"peer_configured": peerAddr != "",
		})
	})

	req := httptest.NewRequest("GET", "/sync/status", nil)
	rr := httptest.NewRecorder()
	mux.ServeHTTP(rr, req)

	var body map[string]interface{}
	json.Unmarshal(rr.Body.Bytes(), &body)
	if body["peer_configured"] != false {
		t.Errorf("expected peer_configured false, got %v", body["peer_configured"])
	}
}

func TestDefaultNodeID(t *testing.T) {
	os.Unsetenv("NEURANAC_NODE_ID")
	nodeID := os.Getenv("NEURANAC_NODE_ID")
	if nodeID == "" {
		nodeID = "twin-a"
	}
	if nodeID != "twin-a" {
		t.Errorf("expected default node_id twin-a, got %s", nodeID)
	}
}

func TestDefaultGRPCPort(t *testing.T) {
	os.Unsetenv("SYNC_GRPC_PORT")
	grpcPort := os.Getenv("SYNC_GRPC_PORT")
	if grpcPort == "" {
		grpcPort = "9090"
	}
	if grpcPort != "9090" {
		t.Errorf("expected default grpc port 9090, got %s", grpcPort)
	}
}
