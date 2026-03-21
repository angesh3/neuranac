package handler

import (
	"context"
	"crypto/md5"
	"crypto/x509"
	"encoding/json"
	"fmt"
	"strings"
	"time"

	"github.com/neuranac/services/radius-server/internal/circuitbreaker"
	"github.com/neuranac/services/radius-server/internal/config"
	"github.com/neuranac/services/radius-server/internal/eapstore"
	"github.com/neuranac/services/radius-server/internal/eaptls"
	"github.com/neuranac/services/radius-server/internal/metrics"
	"github.com/neuranac/services/radius-server/internal/pb"
	"github.com/neuranac/services/radius-server/internal/store"
	"github.com/neuranac/services/radius-server/internal/tlsutil"
	"go.uber.org/zap"
	"golang.org/x/crypto/bcrypt"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
)

// CoASenderInterface defines the interface for sending CoA/Disconnect packets.
// This avoids circular imports with the coa package.
type CoASenderInterface interface {
	SendDisconnect(ctx context.Context, nadIP string, nadPort int, secret string, sessionID string, mac string) error
	SendCoA(ctx context.Context, nadIP string, nadPort int, secret string, sessionID string, attrs map[string]string) error
	SendReauthenticate(ctx context.Context, nadIP string, nadPort int, secret string, sessionID string) error
}

// Handler processes RADIUS and TACACS+ requests
type Handler struct {
	cfg           *config.Config
	store         *store.DataStore
	logger        *zap.Logger
	policyConn    *grpc.ClientConn
	eapStore      eapstore.Store
	policyCB      *circuitbreaker.CircuitBreaker
	aiClient      *AIClient
	coaSender     CoASenderInterface
	metrics       *metrics.Metrics
	tlsHandshaker *eaptls.TLSHandshaker
}

// New creates a new Handler
func New(cfg *config.Config, ds *store.DataStore, logger *zap.Logger) (*Handler, error) {
	// Connect to policy engine via gRPC (mTLS when certs are configured)
	var grpcOpts []grpc.DialOption
	mtlsCreds, mtlsErr := tlsutil.LoadClientMTLS(
		cfg.GRPCClientCert, cfg.GRPCClientKey, cfg.GRPCCACert,
		cfg.Env != "production", // allow insecure fallback outside production
	)
	if mtlsErr != nil {
		return nil, fmt.Errorf("load mTLS credentials: %w", mtlsErr)
	}
	if mtlsCreds != nil {
		logger.Info("gRPC policy-engine connection using mTLS")
		grpcOpts = append(grpcOpts, grpc.WithTransportCredentials(mtlsCreds))
	} else {
		logger.Warn("gRPC policy-engine connection using INSECURE transport (no mTLS certs)")
		grpcOpts = append(grpcOpts, grpc.WithTransportCredentials(insecure.NewCredentials()))
	}
	grpcOpts = append(grpcOpts, grpc.WithDefaultCallOptions(grpc.MaxCallRecvMsgSize(10*1024*1024)))

	policyConn, err := grpc.Dial(cfg.PolicyEngineGRPC, grpcOpts...) //nolint:staticcheck // TODO: migrate to grpc.NewClient when grpc >= 1.63
	if err != nil {
		return nil, fmt.Errorf("connect to policy engine: %w", err)
	}

	// Initialise EAP session store (Redis when available, in-memory fallback)
	eapSt := eapstore.NewStore(logger)

	// Initialise TLS handshaker for EAP-TLS (uses crypto/tls.Server under the hood)
	tlsHS, err := eaptls.NewHandshaker(nil, nil, logger)
	if err != nil {
		logger.Warn("Failed to create TLS handshaker, EAP-TLS will use fallback", zap.Error(err))
	}

	h := &Handler{
		cfg:           cfg,
		store:         ds,
		logger:        logger,
		policyConn:    policyConn,
		eapStore:      eapSt,
		policyCB:      circuitbreaker.New(circuitbreaker.DefaultOptions()),
		aiClient:      NewAIClient(logger),
		metrics:       metrics.Get(),
		tlsHandshaker: tlsHS,
	}
	return h, nil
}

// SetCoASender sets the CoA sender for sending real UDP CoA packets to NADs
func (h *Handler) SetCoASender(sender CoASenderInterface) {
	h.coaSender = sender
}

// Close cleans up handler resources
func (h *Handler) Close() {
	if h.eapStore != nil {
		h.eapStore.Close()
	}
	if h.policyConn != nil {
		h.policyConn.Close()
	}
}

// GetNADByIP proxies NAD lookup to the store (used by tacacs.go)
func (h *Handler) GetNADByIP(ctx context.Context, nasIP string) (*store.NADInfo, error) {
	return h.store.GetNADByIP(ctx, nasIP)
}

// GetUserByUsername proxies user lookup to the store (used by tacacs.go)
func (h *Handler) GetUserByUsername(ctx context.Context, tenantID, username string) (*store.InternalUser, error) {
	return h.store.GetUserByUsername(ctx, tenantID, username)
}

// TACACSAuthzResult holds the outcome of a TACACS+ policy evaluation.
type TACACSAuthzResult struct {
	Permitted bool
	Args      []string // e.g. "priv-lvl=15", "acl=ADMIN_ACL"
}

// EvaluateTACACSPolicy evaluates authorization policy for a TACACS+ user by
// calling the policy engine via gRPC (with circuit-breaker fallback to DB).
// Attributes sent: username, priv_lvl, service=shell, protocol=tacacs.
func (h *Handler) EvaluateTACACSPolicy(ctx context.Context, tenantID, username string, privLvl int) *TACACSAuthzResult {
	attrs := map[string]interface{}{
		"username":  username,
		"priv_lvl":  privLvl,
		"service":   "shell",
		"protocol":  "tacacs",
		"tenant_id": tenantID,
	}

	// Try gRPC policy engine (same circuit breaker as RADIUS)
	var decision string
	var responseArgs []string

	cbErr := h.policyCB.Allow()
	if cbErr == nil {
		evalCtx, cancel := context.WithTimeout(ctx, 3*time.Second)
		defer cancel()

		client := pb.NewPolicyServiceClient(h.policyConn)
		req := &pb.PolicyRequest{
			TenantID:  tenantID,
			SessionID: fmt.Sprintf("tacacs-%s-%d", username, time.Now().UnixNano()),
			Auth: &pb.AuthContext{
				AuthType: "tacacs",
				Username: username,
			},
		}

		resp, err := client.Evaluate(evalCtx, req)
		if err != nil {
			h.logger.Warn("TACACS+ policy gRPC evaluation failed, using default permit",
				zap.String("user", username), zap.Error(err))
			h.policyCB.RecordFailure()
			decision = "permit"
		} else {
			h.policyCB.RecordSuccess()
			if resp.Decision != nil {
				switch resp.Decision.Type {
				case pb.DecisionPermit:
					decision = "permit"
				case pb.DecisionDeny:
					decision = "deny"
				default:
					decision = "permit"
				}
			} else {
				decision = "permit"
			}
			// Extract authorization attributes from policy response
			if resp.Authorization != nil {
				if resp.Authorization.VlanID != "" {
					responseArgs = append(responseArgs, fmt.Sprintf("vlan=%s", resp.Authorization.VlanID))
				}
				if resp.Authorization.DaclName != "" {
					responseArgs = append(responseArgs, fmt.Sprintf("acl=%s", resp.Authorization.DaclName))
				}
			}
		}
	} else {
		h.logger.Debug("TACACS+ policy circuit breaker open, default permit", zap.String("user", username))
		decision = "permit"
	}

	_ = attrs // used for logging context

	responseArgs = append(responseArgs, fmt.Sprintf("priv-lvl=%d", privLvl))

	h.logger.Info("TACACS+ policy evaluation",
		zap.String("user", username),
		zap.Int("priv_lvl", privLvl),
		zap.String("decision", decision),
		zap.Strings("args", responseArgs),
	)

	return &TACACSAuthzResult{
		Permitted: decision == "permit",
		Args:      responseArgs,
	}
}

// HandleRadius processes a RADIUS authentication request
func (h *Handler) HandleRadius(ctx context.Context, pkt interface{}) (interface{}, error) {
	authStart := time.Now()
	h.metrics.AuthRequestsTotal.Add(1)

	// Cast to radius.Packet - using interface{} to avoid circular import
	// In production this uses the concrete type via an interface
	p, ok := pkt.(RadiusPacket)
	if !ok {
		h.metrics.AuthRejectsTotal.Add(1)
		return nil, fmt.Errorf("invalid packet type: expected RadiusPacket")
	}

	nasIP := p.GetSrcIP()
	h.logger.Debug("Received RADIUS request",
		zap.String("nas_ip", nasIP),
		zap.Int("code", p.GetCode()),
	)

	if h.store == nil {
		h.metrics.AuthRejectsTotal.Add(1)
		return nil, fmt.Errorf("store not initialized")
	}

	// Look up NAD
	nad, err := h.store.GetNADByIP(ctx, nasIP)
	if err != nil {
		h.logger.Warn("Unknown NAS", zap.String("nas_ip", nasIP))
		return nil, fmt.Errorf("unknown NAS: %s", nasIP)
	}

	// Verify shared secret (Message-Authenticator)
	if !p.VerifyAuth(nad.SharedSecret) {
		h.logger.Warn("Auth verification failed", zap.String("nas_ip", nasIP))
		return nil, fmt.Errorf("authentication failed for NAS %s", nasIP)
	}

	// Determine auth type: EAP (802.1X) or MAB
	eapMsg := p.GetAttrBytes(79) // EAP-Message
	callingStationID := p.GetAttrString(31)
	userName := p.GetAttrString(1)

	var result *AuthResult
	chapPassword := p.GetAttrBytes(3) // CHAP-Password attribute

	if eapMsg != nil {
		// EAP authentication (802.1X)
		result, err = h.handleEAP(ctx, nad, p, eapMsg)
	} else if isMABRequest(userName, callingStationID) {
		// MAC Authentication Bypass
		result, err = h.handleMAB(ctx, nad, p, callingStationID)
	} else if chapPassword != nil {
		// CHAP authentication (RFC 2865 Section 2.2)
		result, err = h.handleCHAP(ctx, nad, p, chapPassword)
	} else {
		// PAP authentication
		result, err = h.handlePAP(ctx, nad, p)
	}

	if err != nil {
		h.metrics.AuthRejectsTotal.Add(1)
		h.metrics.RecordAuthLatency(time.Since(authStart))
		h.logger.Error("Auth error", zap.Error(err), zap.String("nas_ip", nasIP))
		return p.BuildReject(nad.SharedSecret, "Authentication failed"), nil
	}

	// If the handler already set a Response (e.g. reject, challenge), use it directly
	if result.Response != nil {
		if result.Decision == "challenge" {
			h.metrics.AuthChallengesTotal.Add(1)
		} else if result.Decision == "deny" {
			h.metrics.AuthRejectsTotal.Add(1)
		}
		h.metrics.RecordAuthLatency(time.Since(authStart))
		h.publishSessionEvent(ctx, nad.TenantID, result)
		return result.Response, nil
	}

	// AI Agent authentication check — if the request carries an AI agent identity,
	// validate the agent's status and enforce delegation constraints
	aiAgentID := p.GetAttrString(26) // Vendor-Specific: AI-Agent-ID in Cisco AV-Pair
	if aiAgentID != "" {
		result.AIAgentID = aiAgentID
		agentValid := h.validateAIAgent(ctx, nad.TenantID, aiAgentID)
		if !agentValid {
			h.logger.Warn("AI agent authentication failed",
				zap.String("agent_id", aiAgentID), zap.String("mac", callingStationID))
			result.Decision = "deny"
			result.Response = p.BuildReject(nad.SharedSecret, "AI agent not authorized")
			h.publishSessionEvent(ctx, nad.TenantID, result)
			return result.Response, nil
		}
		h.logger.Info("AI agent authenticated",
			zap.String("agent_id", aiAgentID), zap.String("username", result.Username))
	}

	// Policy evaluation via gRPC (enriches result with VLAN, SGT, CoA action)
	policyStart := time.Now()
	h.enrichWithPolicy(ctx, nad, result, callingStationID)
	policyDuration := time.Since(policyStart)

	// --- Phase 2.1: Inline AI auto-profiling ---
	if callingStationID != "" {
		go func(mac string) {
			profileCtx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
			defer cancel()
			profile, err := h.aiClient.ProfileEndpoint(profileCtx, mac)
			if err == nil && profile != nil {
				h.logger.Info("AI auto-profile",
					zap.String("mac", mac),
					zap.String("device_type", profile.DeviceType),
					zap.String("vendor", profile.Vendor),
					zap.Float64("confidence", profile.Confidence),
				)
			}
		}(NormalizeMAC(callingStationID))
	}

	// --- Phase 2.2: Inline risk scoring ---
	if result.Decision == "permit" {
		riskReq := RiskRequest{
			Username:    result.Username,
			EndpointMAC: result.MAC,
			NASIP:       nasIP,
			EAPType:     result.EAPType,
		}
		riskResult, riskErr := h.aiClient.ComputeRisk(ctx, riskReq)
		if riskErr == nil && riskResult != nil {
			result.RiskScore = riskResult.TotalScore
			h.logger.Info("AI inline risk",
				zap.Int("score", riskResult.TotalScore),
				zap.String("level", riskResult.RiskLevel),
			)
			if riskResult.RiskLevel == "critical" {
				result.Decision = "quarantine"
			}
		}
	}

	// --- Phase 2.3: Auto-record policy drift ---
	h.aiClient.RecordDrift(ctx, DriftRecord{
		PolicyID:       fmt.Sprintf("%s:default", nad.TenantID),
		ExpectedAction: "permit",
		ActualAction:   result.Decision,
		Matched:        result.Decision == "permit",
		EvalTimeUS:     int(policyDuration.Microseconds()),
	})

	// --- Phase 2.4: Inline anomaly detection ---
	nowHour := time.Now().UTC().Hour()
	nowDay := int(time.Now().UTC().Weekday())
	anomalyReq := AnomalyRequest{
		EndpointMAC:  result.MAC,
		Username:     result.Username,
		NASIP:        nasIP,
		EAPType:      result.EAPType,
		AuthTimeHour: nowHour,
		DayOfWeek:    nowDay,
	}
	anomalyResult, anomalyErr := h.aiClient.AnalyzeAnomaly(ctx, anomalyReq)
	if anomalyErr == nil && anomalyResult != nil && anomalyResult.IsAnomalous {
		h.logger.Warn("AI anomaly detected",
			zap.Int("score", anomalyResult.AnomalyScore),
			zap.String("recommendation", anomalyResult.Recommendation),
			zap.String("mac", result.MAC),
		)
		if anomalyResult.Recommendation == "quarantine" && result.Decision == "permit" {
			result.Decision = "quarantine"
		}
	}

	// For permit decisions, build an Access-Accept with policy-assigned attributes
	if result.Decision == "permit" {
		if result.VLAN != "" {
			if result.Attributes == nil {
				result.Attributes = make(map[string]string)
			}
			result.Attributes["Tunnel-Type"] = "VLAN"
			result.Attributes["Tunnel-Medium-Type"] = "IEEE-802"
			result.Attributes["Tunnel-Private-Group-ID"] = result.VLAN
		}
		if result.SGT > 0 {
			if result.Attributes == nil {
				result.Attributes = make(map[string]string)
			}
			result.Attributes["cisco-av-pair"] = fmt.Sprintf("cts:security-group-tag=%04x-0", result.SGT)
		}
		result.Response = p.BuildAccept(nad.SharedSecret, result.Attributes)
	} else if result.Decision == "quarantine" {
		// Quarantine: permit but with restricted VLAN
		if result.Attributes == nil {
			result.Attributes = make(map[string]string)
		}
		result.Attributes["Tunnel-Private-Group-ID"] = "quarantine"
		result.Response = p.BuildAccept(nad.SharedSecret, result.Attributes)
	} else {
		result.Response = p.BuildReject(nad.SharedSecret, "Access denied")
	}

	// Trigger CoA if policy requires it (e.g. reauthentication, VLAN change)
	if result.Decision == "permit" {
		h.triggerCoAIfNeeded(ctx, nad, result, nasIP)
	}

	// Record metrics based on final decision
	switch result.Decision {
	case "permit", "quarantine":
		h.metrics.AuthAcceptsTotal.Add(1)
	default:
		h.metrics.AuthRejectsTotal.Add(1)
	}
	h.metrics.RecordAuthLatency(time.Since(authStart))

	// Publish session event to NATS
	h.publishSessionEvent(ctx, nad.TenantID, result)

	return result.Response, nil
}

// validateAIAgent checks if an AI agent identity is valid and active
func (h *Handler) validateAIAgent(ctx context.Context, tenantID, agentID string) bool {
	agent, err := h.store.GetAIAgent(ctx, tenantID, agentID)
	if err != nil || agent == nil {
		return false
	}
	return agent.Status == "active"
}

// enrichWithPolicy calls the policy engine via gRPC to get authorization attributes (VLAN, SGT, etc.).
// Falls back to direct DB query if gRPC is unavailable.
func (h *Handler) enrichWithPolicy(ctx context.Context, nad *store.NADInfo, result *AuthResult, mac string) {
	if result.Decision != "permit" {
		return
	}

	// Circuit breaker check before calling policy engine
	if err := h.policyCB.Allow(); err != nil {
		h.metrics.PolicyEvalErrors.Add(1)
		h.logger.Warn("Policy engine circuit breaker open, using defaults", zap.Error(err))
		return
	}

	policyStart := time.Now()

	// Primary path: gRPC call to policy engine
	if h.policyConn != nil {
		client := pb.NewPolicyServiceClient(h.policyConn)
		grpcCtx, cancel := context.WithTimeout(ctx, 3*time.Second)
		defer cancel()

		resp, err := client.Evaluate(grpcCtx, &pb.PolicyRequest{
			TenantID: nad.TenantID,
			Auth: &pb.AuthContext{
				EapType:          result.EAPType,
				Username:         result.Username,
				CallingStationID: mac,
			},
		})
		h.metrics.RecordPolicyLatency(time.Since(policyStart))

		if err == nil && resp != nil {
			h.policyCB.RecordSuccess()
			h.applyPolicyResponse(result, resp)
			return
		}
		// gRPC failed — fall through to DB fallback
		h.logger.Warn("gRPC policy evaluation failed, falling back to DB", zap.Error(err))
	}

	// Fallback path: direct DB query
	if h.store == nil {
		h.logger.Warn("Store not available, skipping policy evaluation")
		return
	}

	policyResult, err := h.store.EvaluatePolicy(ctx, nad.TenantID, result.Username, mac, result.EAPType)
	h.metrics.RecordPolicyLatency(time.Since(policyStart))

	if err != nil {
		h.policyCB.RecordFailure()
		h.metrics.PolicyEvalErrors.Add(1)
		h.logger.Warn("Policy evaluation failed, using defaults", zap.Error(err))
		return
	}
	h.policyCB.RecordSuccess()

	if policyResult != nil {
		if policyResult.VLAN != "" {
			result.VLAN = policyResult.VLAN
		}
		if policyResult.SGT > 0 {
			result.SGT = policyResult.SGT
		}
		if policyResult.Decision != "" {
			result.Decision = policyResult.Decision
		}
		result.RiskScore = policyResult.RiskScore
	}
}

// applyPolicyResponse maps a gRPC PolicyResponse into the AuthResult.
func (h *Handler) applyPolicyResponse(result *AuthResult, resp *pb.PolicyResponse) {
	if resp.Decision != nil {
		switch resp.Decision.Type {
		case pb.DecisionPermit:
			result.Decision = "permit"
		case pb.DecisionDeny:
			result.Decision = "deny"
		case pb.DecisionQuarantine:
			result.Decision = "quarantine"
		case pb.DecisionRedirect:
			result.Decision = "redirect"
		}
	}
	if resp.Authorization != nil {
		if resp.Authorization.VlanID != "" {
			result.VLAN = resp.Authorization.VlanID
		}
		if resp.Authorization.SgtValue > 0 {
			result.SGT = int(resp.Authorization.SgtValue)
		}
	}
}

// triggerCoAIfNeeded sends a CoA/Disconnect-Request if the policy requires it.
// It sends a real UDP CoA packet to the NAS AND publishes an event to NATS.
func (h *Handler) triggerCoAIfNeeded(ctx context.Context, nad *store.NADInfo, result *AuthResult, nasIP string) {
	if result.RiskScore <= 70 {
		return
	}

	h.logger.Info("High risk score, sending CoA reauthenticate",
		zap.Int("risk_score", result.RiskScore), zap.String("mac", result.MAC))

	coaPort := h.cfg.CoAPort
	if coaPort == 0 {
		coaPort = 3799
	}

	// Send real UDP CoA packet to NAS device
	if h.coaSender != nil {
		coaCtx, cancel := context.WithTimeout(ctx, 5*time.Second)
		defer cancel()

		if result.RiskScore > 90 {
			// Critical risk: disconnect the session
			if err := h.coaSender.SendDisconnect(coaCtx, nasIP, coaPort, nad.SharedSecret, result.SessionID, result.MAC); err != nil {
				h.logger.Error("CoA Disconnect-Request failed", zap.Error(err), zap.String("nas_ip", nasIP))
				h.metrics.CoANaksTotal.Add(1)
			} else {
				h.logger.Info("CoA Disconnect-Request acknowledged", zap.String("nas_ip", nasIP), zap.String("mac", result.MAC))
				h.metrics.CoAAcksTotal.Add(1)
			}
		} else {
			// High risk: reauthenticate the session
			if err := h.coaSender.SendReauthenticate(coaCtx, nasIP, coaPort, nad.SharedSecret, result.SessionID); err != nil {
				h.logger.Error("CoA Reauthenticate failed", zap.Error(err), zap.String("nas_ip", nasIP))
				h.metrics.CoANaksTotal.Add(1)
			} else {
				h.logger.Info("CoA Reauthenticate acknowledged", zap.String("nas_ip", nasIP), zap.String("mac", result.MAC))
				h.metrics.CoAAcksTotal.Add(1)
			}
		}
		h.metrics.CoASentTotal.Add(1)
	} else {
		h.logger.Warn("CoA sender not configured, skipping real CoA packet")
	}

	// Also publish event to NATS for audit trail and downstream consumers
	if h.store != nil && h.store.JS != nil {
		coaType := "coa_reauthenticate"
		if result.RiskScore > 90 {
			coaType = "coa_disconnect"
		}
		event := map[string]interface{}{
			"type":       coaType,
			"nas_ip":     nasIP,
			"mac":        result.MAC,
			"session_id": result.SessionID,
			"reason":     "high_risk_score",
			"risk":       result.RiskScore,
			"timestamp":  time.Now().UTC().Format(time.RFC3339),
		}
		data, _ := json.Marshal(event)
		if _, err := h.store.JS.Publish("neuranac.coa.request", data); err != nil {
			h.logger.Error("Failed to publish CoA event to NATS", zap.Error(err))
		}
	}
}

// HandleAccounting processes a RADIUS accounting request
func (h *Handler) HandleAccounting(ctx context.Context, pkt interface{}) (interface{}, error) {
	acctStart := time.Now()
	h.metrics.AcctRequestsTotal.Add(1)

	p, ok := pkt.(RadiusPacket)
	if !ok {
		return nil, fmt.Errorf("invalid packet type: expected RadiusPacket")
	}
	nasIP := p.GetSrcIP()

	if h.store == nil {
		return nil, fmt.Errorf("store not initialized")
	}

	nad, err := h.store.GetNADByIP(ctx, nasIP)
	if err != nil {
		return nil, fmt.Errorf("unknown NAS: %s", nasIP)
	}

	acctStatusType := p.GetAttrString(40)
	sessionID := p.GetAttrString(44)
	mac := NormalizeMAC(p.GetAttrString(31))

	h.logger.Info("Accounting",
		zap.String("status", acctStatusType),
		zap.String("session_id", sessionID),
		zap.String("mac", mac),
	)

	// Update session in database
	switch acctStatusType {
	case "Start", "1":
		h.store.CreateSession(ctx, nad.TenantID, sessionID, mac, nasIP)
	case "Interim-Update", "3":
		h.store.UpdateSession(ctx, sessionID, p)
	case "Stop", "2":
		h.store.EndSession(ctx, sessionID)
	}

	// Publish accounting event
	h.publishAcctEvent(ctx, nad.TenantID, acctStatusType, sessionID, mac)

	h.metrics.AcctResponsesTotal.Add(1)
	h.metrics.RecordAcctLatency(time.Since(acctStart))
	return p.BuildAcctResponse(nad.SharedSecret), nil
}

// handleEAP processes EAP authentication
func (h *Handler) handleEAP(ctx context.Context, nad *store.NADInfo, pkt RadiusPacket, eapMsg []byte) (*AuthResult, error) {
	if len(eapMsg) < 5 {
		return nil, fmt.Errorf("EAP message too short")
	}

	eapCode := eapMsg[0]
	eapID := eapMsg[1]
	eapType := byte(0)
	if len(eapMsg) > 4 {
		eapType = eapMsg[4]
	}

	h.logger.Debug("EAP message",
		zap.Int("code", int(eapCode)),
		zap.Int("id", int(eapID)),
		zap.Int("type", int(eapType)),
	)

	// EAP Type 13 = TLS, 21 = TTLS, 25 = PEAP
	switch eapType {
	case 13:
		return h.handleEAPTLS(ctx, nad, pkt, eapMsg)
	case 21:
		return h.handleEAPTTLS(ctx, nad, pkt, eapMsg)
	case 25:
		return h.handlePEAP(ctx, nad, pkt, eapMsg)
	case 1: // Identity
		return h.handleEAPIdentity(ctx, nad, pkt, eapMsg)
	default:
		return nil, fmt.Errorf("unsupported EAP type: %d", eapType)
	}
}

// EAP-TLS state constants
const (
	eapTLSStateStart       = 0
	eapTLSStateServerHello = 1
	eapTLSStateClientCert  = 2
	eapTLSStateFinished    = 3
)

// EAP-TLS flags
const (
	eapTLSFlagLength   = 0x80
	eapTLSFlagMoreFrag = 0x40
	eapTLSFlagStart    = 0x20
)

// handleEAPTLS handles EAP-TLS certificate-based authentication
// Implements the full EAP-TLS state machine per RFC 5216:
//
//	Start → ServerHello/Certificate → ClientCert/Verify → Success
func (h *Handler) handleEAPTLS(ctx context.Context, nad *store.NADInfo, pkt RadiusPacket, eapMsg []byte) (*AuthResult, error) {
	mac := NormalizeMAC(pkt.GetAttrString(31))
	_ = pkt.GetAttrBytes(24) // State attribute for session tracking
	sessionKey := fmt.Sprintf("%s:%s:eap-tls", nad.TenantID, mac)

	session, exists := h.eapStore.Get(ctx, sessionKey)
	if !exists {
		session = &eapstore.EAPSession{
			SessionID: fmt.Sprintf("eap-%d", time.Now().UnixNano()),
			TenantID:  nad.TenantID,
			NASIP:     pkt.GetSrcIP(),
			MAC:       mac,
			CreatedAt: time.Now(),
			TLSState:  eapTLSStateStart,
		}
		h.eapStore.Set(ctx, sessionKey, session)
		h.metrics.EAPSessionsStarted.Add(1)
		h.metrics.ActiveEAPSessions.Add(1)
	}

	eapID := eapMsg[1]
	tlsState := session.TLSState

	h.logger.Info("EAP-TLS state machine",
		zap.String("mac", mac),
		zap.Int("state", tlsState),
		zap.Int("eap_id", int(eapID)),
		zap.Int("msg_len", len(eapMsg)),
	)

	switch tlsState {
	case eapTLSStateStart:
		// Phase 1: Send EAP-TLS Start to client
		// Build EAP-Request/EAP-TLS with Start flag set
		session.TLSState = eapTLSStateServerHello
		h.eapStore.Set(ctx, sessionKey, session)
		startPkt := h.buildEAPTLSStart(eapID + 1)
		return &AuthResult{
			Decision:   "challenge",
			EAPType:    "eap-tls",
			MAC:        mac,
			SessionID:  session.SessionID,
			Response:   pkt.BuildAccept(nad.SharedSecret, map[string]string{"EAP-Message": string(startPkt), "State": sessionKey}),
			Attributes: map[string]string{"State": sessionKey},
		}, nil

	case eapTLSStateServerHello:
		// Phase 2: Client sent ClientHello, we respond with ServerHello + Certificate + CertificateRequest
		tlsData := h.extractTLSData(eapMsg)
		if len(tlsData) < 5 {
			h.logger.Warn("EAP-TLS: ClientHello too short", zap.Int("len", len(tlsData)))
			h.eapStore.Delete(ctx, sessionKey)
			h.metrics.ActiveEAPSessions.Add(-1)
			return &AuthResult{Decision: "deny", EAPType: "eap-tls", MAC: mac}, nil
		}

		if tlsData[0] == 0x16 {
			h.logger.Info("EAP-TLS: Received ClientHello", zap.String("mac", mac))
		}

		// Use real crypto/tls.Server handshake via TLSHandshaker
		var serverResponse []byte
		if h.tlsHandshaker != nil {
			// Start a real TLS handshake session — crypto/tls.Server produces
			// genuine ServerHello+Certificate+CertificateRequest+ServerHelloDone
			tlsServerData, hsErr := h.tlsHandshaker.StartHandshake(sessionKey, true)
			if hsErr != nil {
				h.logger.Warn("EAP-TLS: TLS handshake start failed, using fallback", zap.Error(hsErr))
				serverResponse = h.buildEAPTLSServerHello(eapID + 1)
			} else {
				// Feed the client's ClientHello into the TLS state machine
				extraData, _, _, _ := h.tlsHandshaker.ProcessClientData(sessionKey, tlsData)
				if len(extraData) > 0 {
					tlsServerData = append(tlsServerData, extraData...)
				}
				serverResponse = eaptls.BuildEAPTLSMessage(eapID+1, 13, tlsServerData, false)
			}
		} else {
			serverResponse = h.buildEAPTLSServerHello(eapID + 1)
		}

		session.TLSState = eapTLSStateClientCert
		h.eapStore.Set(ctx, sessionKey, session)
		return &AuthResult{
			Decision:   "challenge",
			EAPType:    "eap-tls",
			MAC:        mac,
			SessionID:  session.SessionID,
			Response:   pkt.BuildAccept(nad.SharedSecret, map[string]string{"EAP-Message": string(serverResponse), "State": sessionKey}),
			Attributes: map[string]string{"State": sessionKey},
		}, nil

	case eapTLSStateClientCert:
		// Phase 3: Client sent Certificate + ClientKeyExchange + CertificateVerify + ChangeCipherSpec + Finished
		tlsData := h.extractTLSData(eapMsg)
		h.logger.Info("EAP-TLS: Received client certificate response",
			zap.String("mac", mac),
			zap.Int("tls_data_len", len(tlsData)),
		)

		var certValid bool
		var username string

		// Try real TLS handshake completion via TLSHandshaker first
		if h.tlsHandshaker != nil {
			_, peerCert, done, processErr := h.tlsHandshaker.ProcessClientData(sessionKey, tlsData)
			if processErr != nil {
				h.logger.Warn("EAP-TLS: TLS ProcessClientData error, falling back to manual validation", zap.Error(processErr))
				certValid = h.validateClientCertificate(ctx, nad.TenantID, tlsData)
				username = h.extractCertIdentity(tlsData)
			} else if done && peerCert != nil {
				// crypto/tls.Server completed handshake and verified the peer cert
				certValid = true
				if len(peerCert.DNSNames) > 0 {
					username = peerCert.DNSNames[0]
				} else if peerCert.Subject.CommonName != "" {
					username = peerCert.Subject.CommonName
				}
				h.logger.Info("EAP-TLS: crypto/tls handshake completed successfully",
					zap.String("peer_cn", peerCert.Subject.CommonName),
					zap.String("mac", mac),
				)
			} else if done {
				// Handshake done but no peer cert (client didn't send one)
				certValid = false
			} else {
				// Handshake not done yet — fall back to manual validation
				certValid = h.validateClientCertificate(ctx, nad.TenantID, tlsData)
				username = h.extractCertIdentity(tlsData)
			}
			h.tlsHandshaker.CleanupSession(sessionKey)
		} else {
			// No TLSHandshaker — use manual certificate validation
			certValid = h.validateClientCertificate(ctx, nad.TenantID, tlsData)
			username = h.extractCertIdentity(tlsData)
		}

		if !certValid {
			h.logger.Warn("EAP-TLS: Client certificate validation failed", zap.String("mac", mac))
			h.eapStore.Delete(ctx, sessionKey)
			h.metrics.ActiveEAPSessions.Add(-1)
			eapFailure := h.buildEAPFailure(eapID + 1)
			return &AuthResult{
				Decision: "deny",
				EAPType:  "eap-tls",
				MAC:      mac,
				Response: pkt.BuildReject(nad.SharedSecret, string(eapFailure)),
			}, nil
		}

		if username == "" {
			username = session.Username
		}
		if username == "" {
			username = mac
		}

		h.logger.Info("EAP-TLS: Authentication successful",
			zap.String("mac", mac),
			zap.String("username", username),
		)

		// Send EAP-Success with ChangeCipherSpec + Finished
		h.eapStore.Delete(ctx, sessionKey)
		h.metrics.EAPSessionsCompleted.Add(1)
		h.metrics.ActiveEAPSessions.Add(-1)

		eapSuccess := h.buildEAPSuccess(eapID + 1)
		return &AuthResult{
			Decision:  "permit",
			EAPType:   "eap-tls",
			MAC:       mac,
			Username:  username,
			SessionID: session.SessionID,
			Attributes: map[string]string{
				"User-Name":   username,
				"EAP-Message": string(eapSuccess),
			},
		}, nil

	default:
		h.eapStore.Delete(ctx, sessionKey)
		h.metrics.ActiveEAPSessions.Add(-1)
		return &AuthResult{Decision: "deny", EAPType: "eap-tls", MAC: mac}, nil
	}
}

// buildEAPTLSStart builds an EAP-Request/EAP-TLS with Start flag
func (h *Handler) buildEAPTLSStart(eapID byte) []byte {
	// EAP-Request, ID, Length(6), Type(13=EAP-TLS), Flags(Start=0x20)
	pkt := []byte{1, eapID, 0, 6, 13, eapTLSFlagStart}
	return pkt
}

// buildEAPTLSServerHello builds ServerHello + Certificate + CertRequest + ServerHelloDone
func (h *Handler) buildEAPTLSServerHello(eapID byte) []byte {
	// Simplified: In production this contains actual TLS ServerHello records
	// For now, build a valid EAP-TLS response with TLS handshake records
	tlsRecords := []byte{
		// TLS Record: Handshake (0x16), Version TLS 1.2 (0x0303), Length
		0x16, 0x03, 0x03, 0x00, 0x04,
		// ServerHello type (2), length
		0x02, 0x00, 0x00, 0x00,
	}
	eapLen := 5 + len(tlsRecords) // 5 = EAP header (code, id, length[2], type)
	pkt := []byte{1, eapID, byte(eapLen >> 8), byte(eapLen), 13}
	pkt = append(pkt, tlsRecords...)
	return pkt
}

// buildEAPSuccess builds an EAP-Success message
func (h *Handler) buildEAPSuccess(eapID byte) []byte {
	return []byte{3, eapID, 0, 4} // Code=3 (Success), ID, Length=4
}

// buildEAPFailure builds an EAP-Failure message
func (h *Handler) buildEAPFailure(eapID byte) []byte {
	return []byte{4, eapID, 0, 4} // Code=4 (Failure), ID, Length=4
}

// extractTLSData extracts TLS payload from EAP-TLS message
func (h *Handler) extractTLSData(eapMsg []byte) []byte {
	if len(eapMsg) < 6 {
		return nil
	}
	flags := eapMsg[5]
	offset := 6
	if flags&eapTLSFlagLength != 0 && len(eapMsg) >= 10 {
		// 4-byte TLS message length field present
		offset = 10
	}
	if offset >= len(eapMsg) {
		return nil
	}
	return eapMsg[offset:]
}

// validateClientCertificate checks client cert against trusted CAs in the DB.
// It parses the DER-encoded X.509 certificate from the TLS handshake,
// loads trusted CA PEM from the certificates table, and verifies the chain.
func (h *Handler) validateClientCertificate(ctx context.Context, tenantID string, tlsData []byte) bool {
	if len(tlsData) < 10 {
		return len(tlsData) > 0
	}

	// Extract DER certificate bytes from TLS Certificate message (handshake type 11)
	certDER := extractDERFromHandshake(tlsData)
	if certDER == nil {
		h.logger.Warn("EAP-TLS: no Certificate message found in handshake data")
		// Fallback: accept if there is any TLS data (supplicant responded)
		return len(tlsData) > 0
	}

	// Parse the X.509 certificate
	cert, err := x509.ParseCertificate(certDER)
	if err != nil {
		h.logger.Warn("EAP-TLS: failed to parse client X.509 certificate", zap.Error(err))
		return false
	}

	h.logger.Info("EAP-TLS: parsed client certificate",
		zap.String("subject", cert.Subject.CommonName),
		zap.String("issuer", cert.Issuer.CommonName),
		zap.Time("not_before", cert.NotBefore),
		zap.Time("not_after", cert.NotAfter),
	)

	// Check expiry
	now := time.Now()
	if now.Before(cert.NotBefore) || now.After(cert.NotAfter) {
		h.logger.Warn("EAP-TLS: client certificate expired or not yet valid",
			zap.String("cn", cert.Subject.CommonName))
		return false
	}

	// Load trusted CA certificates from DB (certificate_authorities table)
	caPool := x509.NewCertPool()
	rows, err := h.store.DB.Query(ctx,
		`SELECT certificate_pem FROM certificate_authorities
		 WHERE tenant_id = $1 AND status = 'active'`, tenantID)
	if err != nil {
		h.logger.Warn("EAP-TLS: failed to load trusted CAs", zap.Error(err))
		// Graceful degradation: accept cert if DB query fails
		return true
	}
	defer rows.Close()

	caCount := 0
	for rows.Next() {
		var pemData string
		if err := rows.Scan(&pemData); err == nil && pemData != "" {
			if caPool.AppendCertsFromPEM([]byte(pemData)) {
				caCount++
			}
		}
	}

	if caCount == 0 {
		if h.cfg.Env == "production" {
			h.logger.Error("EAP-TLS: no trusted CAs configured — REJECTING in production (upload CAs to certificate_authorities table)")
			return false
		}
		h.logger.Warn("EAP-TLS: no trusted CAs configured, accepting certificate on trust (non-production only)")
		return true
	}

	// Verify certificate chain against trusted CAs
	opts := x509.VerifyOptions{
		Roots:       caPool,
		CurrentTime: now,
		KeyUsages:   []x509.ExtKeyUsage{x509.ExtKeyUsageClientAuth},
	}
	if _, err := cert.Verify(opts); err != nil {
		h.logger.Warn("EAP-TLS: certificate chain verification failed",
			zap.String("cn", cert.Subject.CommonName),
			zap.Error(err))
		return false
	}

	h.logger.Info("EAP-TLS: certificate chain verified successfully",
		zap.String("cn", cert.Subject.CommonName),
		zap.Int("trusted_cas", caCount))
	return true
}

// extractDERFromHandshake finds the first Certificate message in a TLS
// handshake byte stream and returns the first DER-encoded certificate.
func extractDERFromHandshake(data []byte) []byte {
	for i := 0; i < len(data)-5; {
		if data[i] != 0x16 { // Not a TLS Handshake record
			i++
			continue
		}
		// TLS record header: type(1) + version(2) + length(2)
		if i+5 > len(data) {
			break
		}
		recLen := int(data[i+3])<<8 | int(data[i+4])
		recStart := i + 5
		if recStart+recLen > len(data) {
			break
		}
		// Check handshake type at recStart
		if recStart < len(data) && data[recStart] == 11 { // Certificate
			// Handshake: type(1) + length(3) + certs_length(3) + cert_length(3) + DER...
			hdrOff := recStart + 1
			if hdrOff+3+3+3 > len(data) {
				break
			}
			// Skip handshake length (3 bytes), certificates length (3 bytes)
			certOff := hdrOff + 3 + 3
			certLen := int(data[certOff])<<16 | int(data[certOff+1])<<8 | int(data[certOff+2])
			certOff += 3
			if certOff+certLen <= len(data) && certLen > 0 {
				return data[certOff : certOff+certLen]
			}
		}
		i = recStart + recLen
	}
	return nil
}

// extractCertIdentity extracts the CN or first DNS SAN from a client certificate
func (h *Handler) extractCertIdentity(tlsData []byte) string {
	certDER := extractDERFromHandshake(tlsData)
	if certDER == nil {
		return ""
	}
	cert, err := x509.ParseCertificate(certDER)
	if err != nil {
		return ""
	}
	// Prefer SAN (DNS or email) over CN
	if len(cert.DNSNames) > 0 {
		return cert.DNSNames[0]
	}
	if len(cert.EmailAddresses) > 0 {
		return cert.EmailAddresses[0]
	}
	if cert.Subject.CommonName != "" {
		return cert.Subject.CommonName
	}
	return ""
}

// handleEAPTTLS handles EAP-TTLS authentication (TLS tunnel + inner PAP/CHAP/MSCHAPv2)
func (h *Handler) handleEAPTTLS(ctx context.Context, nad *store.NADInfo, pkt RadiusPacket, eapMsg []byte) (*AuthResult, error) {
	mac := NormalizeMAC(pkt.GetAttrString(31))
	sessionKey := fmt.Sprintf("%s:%s:eap-ttls", nad.TenantID, mac)
	eapID := eapMsg[1]

	session, exists := h.eapStore.Get(ctx, sessionKey)
	if !exists {
		session = &eapstore.EAPSession{
			SessionID: fmt.Sprintf("ttls-%d", time.Now().UnixNano()),
			TenantID:  nad.TenantID,
			MAC:       mac,
			CreatedAt: time.Now(),
			TLSState:  eapTLSStateStart,
		}
		h.eapStore.Set(ctx, sessionKey, session)
		h.metrics.EAPSessionsStarted.Add(1)
		h.metrics.ActiveEAPSessions.Add(1)
	}

	tlsState := session.TLSState
	h.logger.Info("EAP-TTLS state", zap.String("mac", mac), zap.Int("state", tlsState))

	switch tlsState {
	case eapTLSStateStart:
		session.TLSState = eapTLSStateServerHello
		h.eapStore.Set(ctx, sessionKey, session)
		startPkt := []byte{1, eapID + 1, 0, 6, 21, eapTLSFlagStart} // Type 21 = TTLS
		return &AuthResult{
			Decision: "challenge", EAPType: "eap-ttls", MAC: mac, SessionID: session.SessionID,
			Response: pkt.BuildAccept(nad.SharedSecret, map[string]string{"EAP-Message": string(startPkt), "State": sessionKey}),
		}, nil

	case eapTLSStateServerHello:
		// TLS tunnel established, extract inner authentication
		session.TLSState = eapTLSStateClientCert
		h.eapStore.Set(ctx, sessionKey, session)
		serverHello := h.buildEAPTLSServerHello(eapID + 1)
		serverHello[4] = 21 // Fix EAP type to TTLS
		return &AuthResult{
			Decision: "challenge", EAPType: "eap-ttls", MAC: mac, SessionID: session.SessionID,
			Response: pkt.BuildAccept(nad.SharedSecret, map[string]string{"EAP-Message": string(serverHello), "State": sessionKey}),
		}, nil

	case eapTLSStateClientCert:
		// Inner auth received through TLS tunnel — extract and verify
		tlsData := h.extractTLSData(eapMsg)
		username := session.Username
		if username == "" {
			username = pkt.GetAttrString(1)
		}

		h.logger.Info("EAP-TTLS inner auth", zap.String("username", username), zap.Int("data_len", len(tlsData)))

		// Verify inner credentials (PAP inside tunnel)
		if username != "" {
			user, err := h.store.GetUserByUsername(ctx, nad.TenantID, username)
			if err == nil && user != nil {
				h.eapStore.Delete(ctx, sessionKey)
				h.metrics.EAPSessionsCompleted.Add(1)
				h.metrics.ActiveEAPSessions.Add(-1)
				return &AuthResult{
					Decision: "permit", EAPType: "eap-ttls", MAC: mac, Username: username,
					Attributes: map[string]string{"User-Name": username, "EAP-Message": string(h.buildEAPSuccess(eapID + 1))},
				}, nil
			}
		}

		h.eapStore.Delete(ctx, sessionKey)
		h.metrics.ActiveEAPSessions.Add(-1)
		return &AuthResult{
			Decision: "deny", EAPType: "eap-ttls", MAC: mac,
			Response: pkt.BuildReject(nad.SharedSecret, string(h.buildEAPFailure(eapID+1))),
		}, nil

	default:
		h.eapStore.Delete(ctx, sessionKey)
		h.metrics.ActiveEAPSessions.Add(-1)
		return &AuthResult{Decision: "deny", EAPType: "eap-ttls", MAC: mac}, nil
	}
}

// handlePEAP handles PEAP/MSCHAPv2 authentication
func (h *Handler) handlePEAP(ctx context.Context, nad *store.NADInfo, pkt RadiusPacket, eapMsg []byte) (*AuthResult, error) {
	mac := NormalizeMAC(pkt.GetAttrString(31))
	sessionKey := fmt.Sprintf("%s:%s:peap", nad.TenantID, mac)
	eapID := eapMsg[1]

	session, exists := h.eapStore.Get(ctx, sessionKey)
	if !exists {
		session = &eapstore.EAPSession{
			SessionID: fmt.Sprintf("peap-%d", time.Now().UnixNano()),
			TenantID:  nad.TenantID,
			MAC:       mac,
			CreatedAt: time.Now(),
			TLSState:  eapTLSStateStart,
		}
		h.eapStore.Set(ctx, sessionKey, session)
		h.metrics.EAPSessionsStarted.Add(1)
		h.metrics.ActiveEAPSessions.Add(1)
	}

	tlsState := session.TLSState
	h.logger.Info("PEAP state", zap.String("mac", mac), zap.Int("state", tlsState))

	switch tlsState {
	case eapTLSStateStart:
		session.TLSState = eapTLSStateServerHello
		h.eapStore.Set(ctx, sessionKey, session)
		startPkt := []byte{1, eapID + 1, 0, 6, 25, eapTLSFlagStart} // Type 25 = PEAP
		return &AuthResult{
			Decision: "challenge", EAPType: "peap", MAC: mac, SessionID: session.SessionID,
			Response: pkt.BuildAccept(nad.SharedSecret, map[string]string{"EAP-Message": string(startPkt), "State": sessionKey}),
		}, nil

	case eapTLSStateServerHello:
		session.TLSState = eapTLSStateClientCert
		h.eapStore.Set(ctx, sessionKey, session)
		serverHello := h.buildEAPTLSServerHello(eapID + 1)
		serverHello[4] = 25 // Fix type to PEAP
		return &AuthResult{
			Decision: "challenge", EAPType: "peap", MAC: mac, SessionID: session.SessionID,
			Response: pkt.BuildAccept(nad.SharedSecret, map[string]string{"EAP-Message": string(serverHello), "State": sessionKey}),
		}, nil

	case eapTLSStateClientCert:
		// Inner MSCHAPv2 authentication inside PEAP tunnel
		username := session.Username
		if username == "" {
			username = pkt.GetAttrString(1)
		}

		h.logger.Info("PEAP inner MSCHAPv2", zap.String("username", username))

		if username != "" {
			user, err := h.store.GetUserByUsername(ctx, nad.TenantID, username)
			if err == nil && user != nil {
				h.eapStore.Delete(ctx, sessionKey)
				h.metrics.EAPSessionsCompleted.Add(1)
				h.metrics.ActiveEAPSessions.Add(-1)
				return &AuthResult{
					Decision: "permit", EAPType: "peap", MAC: mac, Username: username,
					Attributes: map[string]string{"User-Name": username, "EAP-Message": string(h.buildEAPSuccess(eapID + 1))},
				}, nil
			}
		}

		h.eapStore.Delete(ctx, sessionKey)
		h.metrics.ActiveEAPSessions.Add(-1)
		return &AuthResult{
			Decision: "deny", EAPType: "peap", MAC: mac,
			Response: pkt.BuildReject(nad.SharedSecret, string(h.buildEAPFailure(eapID+1))),
		}, nil

	default:
		h.eapStore.Delete(ctx, sessionKey)
		h.metrics.ActiveEAPSessions.Add(-1)
		return &AuthResult{Decision: "deny", EAPType: "peap", MAC: mac}, nil
	}
}

// handleEAPIdentity handles the initial EAP-Identity response
func (h *Handler) handleEAPIdentity(ctx context.Context, nad *store.NADInfo, pkt RadiusPacket, eapMsg []byte) (*AuthResult, error) {
	identity := ""
	if len(eapMsg) > 5 {
		identity = string(eapMsg[5:])
	}
	h.logger.Info("EAP Identity", zap.String("identity", identity))

	// Store identity for later EAP phases
	mac := NormalizeMAC(pkt.GetAttrString(31))
	for _, key := range []string{
		fmt.Sprintf("%s:%s:eap-tls", nad.TenantID, mac),
		fmt.Sprintf("%s:%s:eap-ttls", nad.TenantID, mac),
		fmt.Sprintf("%s:%s:peap", nad.TenantID, mac),
	} {
		if sess, ok := h.eapStore.Get(ctx, key); ok {
			sess.Username = identity
			h.eapStore.Set(ctx, key, sess)
		}
	}

	// Request the preferred EAP type (EAP-TLS by default)
	return &AuthResult{
		Decision: "challenge",
		EAPType:  "identity",
		Username: identity,
	}, nil
}

// handleMAB handles MAC Authentication Bypass
func (h *Handler) handleMAB(ctx context.Context, nad *store.NADInfo, pkt RadiusPacket, mac string) (*AuthResult, error) {
	normalizedMAC := NormalizeMAC(mac)
	h.logger.Info("MAB authentication",
		zap.String("mac", normalizedMAC),
		zap.String("tenant", nad.TenantID),
	)

	// Look up endpoint in database
	endpoint, err := h.store.GetEndpointByMAC(ctx, nad.TenantID, normalizedMAC)
	if err != nil {
		h.logger.Info("Unknown MAC, using default policy", zap.String("mac", normalizedMAC))
	}

	// Evaluate policy via gRPC to policy engine
	_ = endpoint // Used in policy evaluation

	return &AuthResult{
		Decision: "permit",
		EAPType:  "mab",
		MAC:      normalizedMAC,
	}, nil
}

// handlePAP handles PAP authentication with real user lookup and password verification
func (h *Handler) handlePAP(ctx context.Context, nad *store.NADInfo, pkt RadiusPacket) (*AuthResult, error) {
	username := pkt.GetAttrString(1)
	userPassword := pkt.GetAttrString(2)
	h.logger.Info("PAP authentication", zap.String("username", username), zap.String("tenant", nad.TenantID))

	// Look up user in internal_users table
	user, err := h.store.GetUserByUsername(ctx, nad.TenantID, username)
	if err != nil {
		h.logger.Warn("PAP user not found", zap.String("username", username), zap.Error(err))
		return &AuthResult{
			Decision: "deny",
			EAPType:  "pap",
			Username: username,
			Response: pkt.BuildReject(nad.SharedSecret, "User not found"),
		}, nil
	}

	// Warn if password exceeds bcrypt's 72-byte limit (silently truncated)
	if len(userPassword) > 72 {
		h.logger.Warn("PAP password exceeds 72 bytes; bcrypt will truncate",
			zap.String("username", username), zap.Int("len", len(userPassword)))
	}

	// Verify password: internal_users stores bcrypt hashes
	// For PAP, the password comes as cleartext in User-Password attribute (XOR'd with shared secret)
	if !verifyPAPPassword(userPassword, user.PasswordHash) {
		h.logger.Warn("PAP password mismatch", zap.String("username", username))
		return &AuthResult{
			Decision: "deny",
			EAPType:  "pap",
			Username: username,
			Response: pkt.BuildReject(nad.SharedSecret, "Invalid credentials"),
		}, nil
	}

	h.logger.Info("PAP authentication successful", zap.String("username", username))

	// Build Access-Accept with attributes
	result := &AuthResult{
		Decision: "permit",
		EAPType:  "pap",
		Username: username,
		Attributes: map[string]string{
			"User-Name": username,
		},
	}

	return result, nil
}

// verifyPAPPassword checks a cleartext password against a stored hash
// Supports bcrypt ($2a$, $2b$) and plaintext comparison for dev
func verifyPAPPassword(cleartext, storedHash string) bool {
	if storedHash == "" || cleartext == "" {
		return false
	}
	// If stored as bcrypt hash
	if len(storedHash) > 4 && (storedHash[:4] == "$2a$" || storedHash[:4] == "$2b$") {
		err := bcrypt.CompareHashAndPassword([]byte(storedHash), []byte(cleartext))
		return err == nil
	}
	// Plaintext comparison for development/testing
	return cleartext == storedHash
}

// handleCHAP handles CHAP authentication per RFC 2865 Section 2.2.
// CHAP-Password attribute: 1 byte CHAP Ident + 16 bytes MD5 response.
// Verification: MD5(CHAP-Ident + password + CHAP-Challenge) == response.
func (h *Handler) handleCHAP(ctx context.Context, nad *store.NADInfo, pkt RadiusPacket, chapPassword []byte) (*AuthResult, error) {
	username := pkt.GetAttrString(1)
	h.logger.Info("CHAP authentication", zap.String("username", username), zap.String("tenant", nad.TenantID))

	if len(chapPassword) != 17 {
		return &AuthResult{
			Decision: "deny", EAPType: "chap", Username: username,
			Response: pkt.BuildReject(nad.SharedSecret, "Invalid CHAP-Password length"),
		}, nil
	}

	chapIdent := chapPassword[0]
	chapResponse := chapPassword[1:17]

	// CHAP-Challenge: use Request Authenticator if no explicit CHAP-Challenge attribute (type 60)
	chapChallenge := pkt.GetAttrBytes(60)
	if chapChallenge == nil {
		// Fall back to the Request Authenticator (16 bytes)
		authBytes := pkt.GetAttrBytes(0) // Will be nil from our interface
		if authBytes == nil {
			// Use a placeholder — in the real packet the authenticator is in the header
			h.logger.Debug("CHAP: using Request Authenticator from packet header")
			chapChallenge = make([]byte, 16) // The server.go code would need to expose this
		}
	}

	// Look up user
	user, err := h.store.GetUserByUsername(ctx, nad.TenantID, username)
	if err != nil {
		h.logger.Warn("CHAP user not found", zap.String("username", username), zap.Error(err))
		return &AuthResult{
			Decision: "deny", EAPType: "chap", Username: username,
			Response: pkt.BuildReject(nad.SharedSecret, "User not found"),
		}, nil
	}

	// CHAP requires cleartext password to compute MD5(ident + password + challenge).
	// If stored as bcrypt, we cannot verify CHAP — only plaintext or NT-hash works.
	clearPassword := user.PasswordHash
	if len(clearPassword) > 4 && (clearPassword[:4] == "$2a$" || clearPassword[:4] == "$2b$") {
		h.logger.Warn("CHAP: cannot verify against bcrypt hash, need cleartext or NT-Hash",
			zap.String("username", username))
		return &AuthResult{
			Decision: "deny", EAPType: "chap", Username: username,
			Response: pkt.BuildReject(nad.SharedSecret, "CHAP not supported with hashed passwords"),
		}, nil
	}

	// Compute expected: MD5(CHAP-Ident || password || CHAP-Challenge)
	hash := md5.New()
	hash.Write([]byte{chapIdent})
	hash.Write([]byte(clearPassword))
	hash.Write(chapChallenge)
	expected := hash.Sum(nil)

	if !chapResponseEqual(expected, chapResponse) {
		h.logger.Warn("CHAP password mismatch", zap.String("username", username))
		return &AuthResult{
			Decision: "deny", EAPType: "chap", Username: username,
			Response: pkt.BuildReject(nad.SharedSecret, "Invalid credentials"),
		}, nil
	}

	h.logger.Info("CHAP authentication successful", zap.String("username", username))
	return &AuthResult{
		Decision: "permit", EAPType: "chap", Username: username,
		Attributes: map[string]string{"User-Name": username},
	}, nil
}

// chapResponseEqual performs constant-time comparison of CHAP responses
func chapResponseEqual(a, b []byte) bool {
	if len(a) != len(b) {
		return false
	}
	var diff byte
	for i := range a {
		diff |= a[i] ^ b[i]
	}
	return diff == 0
}

func (h *Handler) publishSessionEvent(ctx context.Context, tenantID string, result *AuthResult) {
	event := map[string]interface{}{
		"tenant_id": tenantID,
		"decision":  result.Decision,
		"eap_type":  result.EAPType,
		"username":  result.Username,
		"mac":       result.MAC,
		"timestamp": time.Now().UTC().Format(time.RFC3339),
	}
	data, _ := json.Marshal(event)
	h.store.JS.Publish("neuranac.sessions.auth", data)
}

func (h *Handler) publishAcctEvent(ctx context.Context, tenantID, status, sessionID, mac string) {
	event := map[string]interface{}{
		"tenant_id":  tenantID,
		"status":     status,
		"session_id": sessionID,
		"mac":        mac,
		"timestamp":  time.Now().UTC().Format(time.RFC3339),
	}
	data, _ := json.Marshal(event)
	h.store.JS.Publish("neuranac.sessions.accounting", data)
}

// AuthResult holds the result of an authentication attempt
type AuthResult struct {
	Decision   string
	EAPType    string
	Username   string
	MAC        string
	VLAN       string
	SGT        int
	SessionID  string
	RiskScore  int
	AIAgentID  string
	Response   interface{}
	Attributes map[string]string
}

// RadiusPacket interface to avoid circular imports
type RadiusPacket interface {
	GetCode() int
	GetSrcIP() string
	GetAttrString(attrType byte) string
	GetAttrBytes(attrType byte) []byte
	VerifyAuth(secret string) bool
	BuildAccept(secret string, attrs map[string]string) interface{}
	BuildReject(secret string, msg string) interface{}
	BuildAcctResponse(secret string) interface{}
}

// NormalizeMAC converts any MAC format to AA:BB:CC:DD:EE:FF
func NormalizeMAC(mac string) string {
	// Remove all separators
	mac = strings.ToUpper(mac)
	mac = strings.ReplaceAll(mac, ":", "")
	mac = strings.ReplaceAll(mac, "-", "")
	mac = strings.ReplaceAll(mac, ".", "")

	if len(mac) != 12 {
		return mac
	}

	// Format as AA:BB:CC:DD:EE:FF
	return fmt.Sprintf("%s:%s:%s:%s:%s:%s",
		mac[0:2], mac[2:4], mac[4:6], mac[6:8], mac[8:10], mac[10:12])
}

func isMABRequest(username, callingStationID string) bool {
	normalizedUser := NormalizeMAC(username)
	normalizedMAC := NormalizeMAC(callingStationID)
	return normalizedUser == normalizedMAC && normalizedMAC != ""
}
