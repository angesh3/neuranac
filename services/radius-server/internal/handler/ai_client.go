package handler

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"sync/atomic"
	"time"

	"go.uber.org/zap"
)

// AIClient communicates with the AI Engine for inline profiling, risk scoring,
// anomaly detection, and policy drift recording during RADIUS authentication.
type AIClient struct {
	baseURL    string
	httpClient *http.Client
	logger     *zap.Logger
	enabled    bool

	// Circuit breaker state for graceful degradation
	consecFails  atomic.Int64 // consecutive failures
	circuitOpen  atomic.Bool  // true = skip AI calls
	lastOpenTime atomic.Int64 // unix timestamp when circuit opened
}

// NewAIClient creates a new AI Engine HTTP client.
func NewAIClient(logger *zap.Logger) *AIClient {
	baseURL := os.Getenv("AI_ENGINE_URL")
	if baseURL == "" {
		baseURL = "http://localhost:8081"
	}
	enabled := os.Getenv("AI_INLINE_ENABLED") != "false"

	return &AIClient{
		baseURL: baseURL,
		httpClient: &http.Client{
			Timeout: 3 * time.Second, // Tight timeout to avoid blocking RADIUS
		},
		logger:  logger,
		enabled: enabled,
	}
}

// ProfileRequest is sent to POST /api/v1/profile
type ProfileRequest struct {
	MACAddress  string            `json:"mac_address"`
	RadiusAttrs map[string]string `json:"radius_attributes,omitempty"`
	DHCPAttrs   map[string]string `json:"dhcp_attributes,omitempty"`
	DNSQueries  []string          `json:"dns_queries,omitempty"`
	PortsUsed   []int             `json:"ports_used,omitempty"`
}

// ProfileResult from AI engine
type ProfileResult struct {
	DeviceType   string  `json:"device_type"`
	Vendor       string  `json:"vendor"`
	OS           string  `json:"os"`
	Confidence   float64 `json:"confidence"`
	ModelVersion string  `json:"model_version"`
}

// RiskRequest is sent to POST /api/v1/risk-score
type RiskRequest struct {
	SessionID       string `json:"session_id"`
	Username        string `json:"username"`
	EndpointMAC     string `json:"endpoint_mac"`
	NASIP           string `json:"nas_ip"`
	EAPType         string `json:"eap_type"`
	FailedAttempts  int    `json:"failed_attempts"`
	IsNewEndpoint   bool   `json:"is_new_endpoint"`
	AIAgentDetected bool   `json:"ai_agent_detected"`
}

// RiskResult from AI engine
type RiskResult struct {
	TotalScore int    `json:"total_score"`
	RiskLevel  string `json:"risk_level"`
}

// AnomalyRequest is sent to POST /api/v1/anomaly/analyze
type AnomalyRequest struct {
	EndpointMAC  string `json:"endpoint_mac"`
	Username     string `json:"username"`
	NASIP        string `json:"nas_ip"`
	EAPType      string `json:"eap_type"`
	AuthTimeHour int    `json:"auth_time_hour"`
	DayOfWeek    int    `json:"day_of_week"`
}

// AnomalyResult from AI engine
type AnomalyResult struct {
	IsAnomalous    bool   `json:"is_anomalous"`
	AnomalyScore   int    `json:"anomaly_score"`
	Recommendation string `json:"recommendation"`
}

// DriftRecord is sent to POST /api/v1/drift/record
type DriftRecord struct {
	PolicyID       string `json:"policy_id"`
	ExpectedAction string `json:"expected_action"`
	ActualAction   string `json:"actual_action"`
	Matched        bool   `json:"matched"`
	EvalTimeUS     int    `json:"evaluation_time_us"`
}

// ProfileEndpoint calls the AI Engine to profile a MAC address inline.
func (c *AIClient) ProfileEndpoint(ctx context.Context, mac string) (*ProfileResult, error) {
	if !c.enabled {
		return nil, nil
	}
	req := ProfileRequest{MACAddress: mac}
	var result ProfileResult
	if err := c.post(ctx, "/api/v1/profile", req, &result); err != nil {
		c.logger.Debug("AI profile failed (non-blocking)", zap.Error(err), zap.String("mac", mac))
		return nil, err
	}
	return &result, nil
}

// ComputeRisk calls the AI Engine to compute a risk score for a session.
func (c *AIClient) ComputeRisk(ctx context.Context, req RiskRequest) (*RiskResult, error) {
	if !c.enabled {
		return nil, nil
	}
	var result RiskResult
	if err := c.post(ctx, "/api/v1/risk-score", req, &result); err != nil {
		c.logger.Debug("AI risk score failed (non-blocking)", zap.Error(err))
		return nil, err
	}
	return &result, nil
}

// AnalyzeAnomaly calls the AI Engine to check for behavioral anomalies.
func (c *AIClient) AnalyzeAnomaly(ctx context.Context, req AnomalyRequest) (*AnomalyResult, error) {
	if !c.enabled {
		return nil, nil
	}
	var result AnomalyResult
	if err := c.post(ctx, "/api/v1/anomaly/analyze", req, &result); err != nil {
		c.logger.Debug("AI anomaly check failed (non-blocking)", zap.Error(err))
		return nil, err
	}
	return &result, nil
}

// RecordDrift sends a policy evaluation outcome to the drift detector.
func (c *AIClient) RecordDrift(ctx context.Context, rec DriftRecord) {
	if !c.enabled {
		return
	}
	// Fire-and-forget — don't block RADIUS on drift recording
	go func() {
		bgCtx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
		defer cancel()
		var ignored map[string]interface{}
		_ = c.post(bgCtx, "/api/v1/drift/record", rec, &ignored)
	}()
}

// isCircuitOpen checks if the AI circuit breaker is open.
// Auto-recovers (half-open) after 30 seconds.
func (c *AIClient) isCircuitOpen() bool {
	if !c.circuitOpen.Load() {
		return false
	}
	// Check if enough time has passed to try again (half-open)
	openedAt := c.lastOpenTime.Load()
	if time.Now().Unix()-openedAt > 30 {
		c.circuitOpen.Store(false)
		c.consecFails.Store(0)
		c.logger.Info("AI circuit breaker half-open, retrying")
		return false
	}
	return true
}

// recordSuccess resets the consecutive failure counter.
func (c *AIClient) recordSuccess() {
	c.consecFails.Store(0)
}

// recordFailure increments failures and opens circuit after 3 consecutive.
func (c *AIClient) recordFailure() {
	fails := c.consecFails.Add(1)
	if fails >= 3 && !c.circuitOpen.Load() {
		c.circuitOpen.Store(true)
		c.lastOpenTime.Store(time.Now().Unix())
		c.logger.Warn("AI circuit breaker OPEN after 3 consecutive failures — AI calls disabled for 30s")
	}
}

// post is a helper that POSTs JSON and decodes the response.
func (c *AIClient) post(ctx context.Context, path string, body interface{}, result interface{}) error {
	// Circuit breaker check
	if c.isCircuitOpen() {
		return fmt.Errorf("ai circuit breaker open")
	}
	data, err := json.Marshal(body)
	if err != nil {
		return fmt.Errorf("marshal: %w", err)
	}

	req, err := http.NewRequestWithContext(ctx, "POST", c.baseURL+path, bytes.NewReader(data))
	if err != nil {
		return fmt.Errorf("new request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := c.httpClient.Do(req)
	if err != nil {
		c.recordFailure()
		return fmt.Errorf("http do: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode >= 500 {
		c.recordFailure()
		return fmt.Errorf("ai engine returned %d", resp.StatusCode)
	}

	if resp.StatusCode >= 400 {
		// 4xx errors are client-side — don't count toward circuit breaker
		return fmt.Errorf("ai engine returned %d", resp.StatusCode)
	}

	c.recordSuccess()
	if result != nil {
		if err := json.NewDecoder(resp.Body).Decode(result); err != nil {
			return fmt.Errorf("decode: %w", err)
		}
	}
	return nil
}
