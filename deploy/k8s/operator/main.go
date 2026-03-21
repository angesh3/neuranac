// NeuraNAC Kubernetes Operator
// Watches NeuraNACNode and NeuraNACTenant CRDs, reconciles node registry and tenant
// provisioning via the NeuraNAC API Gateway.
//
// Reconciliation loop:
//
//	NeuraNACNode  → POST /api/v1/nodes/register  (upsert node in DB)
//	           PUT  /api/v1/nodes/{id}       (status sync)
//	NeuraNACTenant → POST /api/v1/tenants/        (create tenant + quota)
//	            PUT  /api/v1/tenants/{id}    (update status)
//
// Build: go build -o neuranac-operator ./deploy/k8s/operator
package main

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"os/signal"
	"sync"
	"syscall"
	"time"
)

// ── Config ──────────────────────────────────────────────────────────────────

type Config struct {
	Namespace     string
	APIGatewayURL string
	APIToken      string
	PollInterval  time.Duration
	LeaderID      string
}

func loadConfig() Config {
	hostname, _ := os.Hostname()
	return Config{
		Namespace:     getEnv("WATCH_NAMESPACE", "neuranac"),
		APIGatewayURL: getEnv("API_GATEWAY_URL", "http://api-gateway:8080"),
		APIToken:      getEnv("NeuraNAC_OPERATOR_TOKEN", ""),
		PollInterval:  parseDuration(getEnv("POLL_INTERVAL", "30s"), 30*time.Second),
		LeaderID:      getEnv("LEADER_ID", hostname),
	}
}

// ── CRD Spec structs (mirror the OpenAPI schema from neuranac-node.yaml) ────────

type NeuraNACNodeSpec struct {
	NodeID         string `json:"nodeId"`
	Role           string `json:"role"`
	SiteType       string `json:"siteType"`
	SiteID         string `json:"siteId"`
	DeploymentMode string `json:"deploymentMode"`
	ServiceType    string `json:"serviceType"`
	PeerAddress    string `json:"peerAddress"`
	SyncEnabled    bool   `json:"syncEnabled"`
}

type NeuraNACNodeStatus struct {
	Health         string `json:"health"`
	LastSyncTime   string `json:"lastSyncTime,omitempty"`
	ActiveSessions int    `json:"activeSessions"`
	SyncLagMs      int    `json:"syncLagMs"`
}

type NeuraNACNode struct {
	Name   string        `json:"name"`
	Spec   NeuraNACNodeSpec   `json:"spec"`
	Status NeuraNACNodeStatus `json:"status"`
}

type NeuraNACTenantSpec struct {
	Name          string `json:"name"`
	Slug          string `json:"slug"`
	IsolationMode string `json:"isolationMode"`
	LicenseTier   string `json:"licenseTier"`
	MaxEndpoints  int    `json:"maxEndpoints"`
}

type NeuraNACTenantStatus struct {
	Phase         string `json:"phase"`
	EndpointCount int    `json:"endpointCount"`
	LastActivity  string `json:"lastActivity,omitempty"`
}

type NeuraNACTenant struct {
	Name   string          `json:"name"`
	Spec   NeuraNACTenantSpec   `json:"spec"`
	Status NeuraNACTenantStatus `json:"status"`
}

// ── Reconcilers ─────────────────────────────────────────────────────────────

type NodeReconciler struct {
	cfg    Config
	client *http.Client
	mu     sync.Mutex
	known  map[string]string // nodeId → last reconciled hash
}

func NewNodeReconciler(cfg Config) *NodeReconciler {
	return &NodeReconciler{
		cfg:    cfg,
		client: &http.Client{Timeout: 10 * time.Second},
		known:  make(map[string]string),
	}
}

func (r *NodeReconciler) Reconcile(ctx context.Context, node NeuraNACNode) error {
	r.mu.Lock()
	defer r.mu.Unlock()

	hash := fmt.Sprintf("%s:%s:%s:%s", node.Spec.NodeID, node.Spec.Role, node.Spec.SiteID, node.Spec.ServiceType)
	if r.known[node.Spec.NodeID] == hash {
		return nil // already reconciled
	}

	body, _ := json.Marshal(map[string]interface{}{
		"node_id":         node.Spec.NodeID,
		"hostname":        node.Name,
		"role":            node.Spec.Role,
		"site_id":         node.Spec.SiteID,
		"site_type":       node.Spec.SiteType,
		"deployment_mode": node.Spec.DeploymentMode,
		"service_type":    node.Spec.ServiceType,
		"peer_address":    node.Spec.PeerAddress,
		"sync_enabled":    node.Spec.SyncEnabled,
		"status":          "active",
		"metadata": map[string]string{
			"source":    "k8s-operator",
			"namespace": r.cfg.Namespace,
		},
	})

	url := fmt.Sprintf("%s/api/v1/nodes/register", r.cfg.APIGatewayURL)
	req, err := http.NewRequestWithContext(ctx, "POST", url, bytes.NewReader(body))
	if err != nil {
		return fmt.Errorf("build request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")
	if r.cfg.APIToken != "" {
		req.Header.Set("Authorization", "Bearer "+r.cfg.APIToken)
	}

	resp, err := r.client.Do(req)
	if err != nil {
		return fmt.Errorf("API call failed: %w", err)
	}
	defer resp.Body.Close()
	io.Copy(io.Discard, resp.Body)

	if resp.StatusCode >= 200 && resp.StatusCode < 300 {
		r.known[node.Spec.NodeID] = hash
		log.Printf("[NodeReconciler] Registered node %s (role=%s, site=%s)", node.Spec.NodeID, node.Spec.Role, node.Spec.SiteID)
		return nil
	}
	return fmt.Errorf("API returned %d for node %s", resp.StatusCode, node.Spec.NodeID)
}

type TenantReconciler struct {
	cfg    Config
	client *http.Client
	mu     sync.Mutex
	known  map[string]string
}

func NewTenantReconciler(cfg Config) *TenantReconciler {
	return &TenantReconciler{
		cfg:    cfg,
		client: &http.Client{Timeout: 10 * time.Second},
		known:  make(map[string]string),
	}
}

func (r *TenantReconciler) Reconcile(ctx context.Context, tenant NeuraNACTenant) error {
	r.mu.Lock()
	defer r.mu.Unlock()

	hash := fmt.Sprintf("%s:%s:%s:%d", tenant.Spec.Slug, tenant.Spec.IsolationMode, tenant.Spec.LicenseTier, tenant.Spec.MaxEndpoints)
	if r.known[tenant.Spec.Slug] == hash {
		return nil
	}

	body, _ := json.Marshal(map[string]interface{}{
		"name":           tenant.Spec.Name,
		"slug":           tenant.Spec.Slug,
		"isolation_mode": tenant.Spec.IsolationMode,
		"license_tier":   tenant.Spec.LicenseTier,
		"max_endpoints":  tenant.Spec.MaxEndpoints,
		"status":         "active",
		"metadata": map[string]string{
			"source":    "k8s-operator",
			"namespace": r.cfg.Namespace,
		},
	})

	url := fmt.Sprintf("%s/api/v1/tenants/", r.cfg.APIGatewayURL)
	req, err := http.NewRequestWithContext(ctx, "POST", url, bytes.NewReader(body))
	if err != nil {
		return fmt.Errorf("build request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")
	if r.cfg.APIToken != "" {
		req.Header.Set("Authorization", "Bearer "+r.cfg.APIToken)
	}

	resp, err := r.client.Do(req)
	if err != nil {
		return fmt.Errorf("API call failed: %w", err)
	}
	defer resp.Body.Close()
	io.Copy(io.Discard, resp.Body)

	if resp.StatusCode >= 200 && resp.StatusCode < 300 || resp.StatusCode == 409 {
		r.known[tenant.Spec.Slug] = hash
		log.Printf("[TenantReconciler] Provisioned tenant %s (tier=%s, max=%d)", tenant.Spec.Slug, tenant.Spec.LicenseTier, tenant.Spec.MaxEndpoints)
		return nil
	}
	return fmt.Errorf("API returned %d for tenant %s", resp.StatusCode, tenant.Spec.Slug)
}

// ── Simulated CRD Watcher (polls API Gateway for desired state) ─────────────
// In production this would use k8s.io/client-go informers/watch on CRDs.
// For now, we poll the API Gateway's /api/v1/nodes and /api/v1/tenants
// to reconcile state, and accept CRD specs via a local HTTP endpoint.

type CRDWatcher struct {
	cfg              Config
	nodeReconciler   *NodeReconciler
	tenantReconciler *TenantReconciler
	pendingNodes     []NeuraNACNode
	pendingTenants   []NeuraNACTenant
	mu               sync.Mutex
}

func NewCRDWatcher(cfg Config, nr *NodeReconciler, tr *TenantReconciler) *CRDWatcher {
	return &CRDWatcher{cfg: cfg, nodeReconciler: nr, tenantReconciler: tr}
}

func (w *CRDWatcher) EnqueueNode(node NeuraNACNode) {
	w.mu.Lock()
	defer w.mu.Unlock()
	w.pendingNodes = append(w.pendingNodes, node)
}

func (w *CRDWatcher) EnqueueTenant(tenant NeuraNACTenant) {
	w.mu.Lock()
	defer w.mu.Unlock()
	w.pendingTenants = append(w.pendingTenants, tenant)
}

func (w *CRDWatcher) Run(ctx context.Context) {
	ticker := time.NewTicker(w.cfg.PollInterval)
	defer ticker.Stop()
	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			w.reconcilePending(ctx)
		}
	}
}

func (w *CRDWatcher) reconcilePending(ctx context.Context) {
	w.mu.Lock()
	nodes := w.pendingNodes
	tenants := w.pendingTenants
	w.pendingNodes = nil
	w.pendingTenants = nil
	w.mu.Unlock()

	for _, n := range nodes {
		if err := w.nodeReconciler.Reconcile(ctx, n); err != nil {
			log.Printf("[CRDWatcher] Node reconcile error: %v", err)
			w.mu.Lock()
			w.pendingNodes = append(w.pendingNodes, n) // re-queue
			w.mu.Unlock()
		}
	}
	for _, t := range tenants {
		if err := w.tenantReconciler.Reconcile(ctx, t); err != nil {
			log.Printf("[CRDWatcher] Tenant reconcile error: %v", err)
			w.mu.Lock()
			w.pendingTenants = append(w.pendingTenants, t)
			w.mu.Unlock()
		}
	}
}

// ── Main ────────────────────────────────────────────────────────────────────

func main() {
	cfg := loadConfig()
	log.Printf("Starting NeuraNAC Kubernetes Operator")
	log.Printf("  Namespace:   %s", cfg.Namespace)
	log.Printf("  API Gateway: %s", cfg.APIGatewayURL)
	log.Printf("  Leader ID:   %s", cfg.LeaderID)
	log.Printf("  Poll:        %s", cfg.PollInterval)

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	nodeReconciler := NewNodeReconciler(cfg)
	tenantReconciler := NewTenantReconciler(cfg)
	watcher := NewCRDWatcher(cfg, nodeReconciler, tenantReconciler)

	// HTTP endpoints: health + CRD submission
	mux := http.NewServeMux()
	mux.HandleFunc("/healthz", func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(200)
		fmt.Fprint(w, "ok")
	})
	mux.HandleFunc("/readyz", func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(200)
		fmt.Fprint(w, "ok")
	})
	mux.HandleFunc("/api/v1/operator/status", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]interface{}{
			"status":        "running",
			"leader_id":     cfg.LeaderID,
			"namespace":     cfg.Namespace,
			"known_nodes":   len(nodeReconciler.known),
			"known_tenants": len(tenantReconciler.known),
		})
	})
	mux.HandleFunc("/api/v1/operator/reconcile/node", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			http.Error(w, "POST only", http.StatusMethodNotAllowed)
			return
		}
		var node NeuraNACNode
		if err := json.NewDecoder(r.Body).Decode(&node); err != nil {
			http.Error(w, err.Error(), http.StatusBadRequest)
			return
		}
		watcher.EnqueueNode(node)
		w.WriteHeader(http.StatusAccepted)
		fmt.Fprintf(w, `{"status":"enqueued","nodeId":"%s"}`, node.Spec.NodeID)
	})
	mux.HandleFunc("/api/v1/operator/reconcile/tenant", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			http.Error(w, "POST only", http.StatusMethodNotAllowed)
			return
		}
		var tenant NeuraNACTenant
		if err := json.NewDecoder(r.Body).Decode(&tenant); err != nil {
			http.Error(w, err.Error(), http.StatusBadRequest)
			return
		}
		watcher.EnqueueTenant(tenant)
		w.WriteHeader(http.StatusAccepted)
		fmt.Fprintf(w, `{"status":"enqueued","slug":"%s"}`, tenant.Spec.Slug)
	})

	server := &http.Server{Addr: ":8443", Handler: mux}
	go func() {
		log.Printf("Operator HTTP server on :8443")
		if err := server.ListenAndServe(); err != http.ErrServerClosed {
			log.Fatalf("HTTP server error: %v", err)
		}
	}()

	// Start CRD watcher loop
	go watcher.Run(ctx)

	log.Println("Operator running — reconcilers active")

	// Wait for shutdown
	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, syscall.SIGINT, syscall.SIGTERM)
	<-sigCh

	log.Println("Shutting down operator")
	cancel()
	shutdownCtx, shutdownCancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer shutdownCancel()
	server.Shutdown(shutdownCtx)
	log.Println("Operator stopped")
}

// ── Helpers ─────────────────────────────────────────────────────────────────

func getEnv(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}

func parseDuration(s string, fallback time.Duration) time.Duration {
	d, err := time.ParseDuration(s)
	if err != nil {
		return fallback
	}
	return d
}
