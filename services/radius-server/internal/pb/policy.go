package pb

// PolicyRequest is a lightweight Go struct mirroring the protobuf PolicyRequest.
// This avoids requiring full protobuf code generation while still supporting
// gRPC communication with the policy engine.
type PolicyRequest struct {
	TenantID  string       `protobuf:"bytes,1,opt,name=tenant_id,json=tenantId,proto3" json:"tenant_id,omitempty"`
	SessionID string       `protobuf:"bytes,2,opt,name=session_id,json=sessionId,proto3" json:"session_id,omitempty"`
	Auth      *AuthContext `protobuf:"bytes,3,opt,name=auth_context,json=authContext,proto3" json:"auth_context,omitempty"`
}

func (m *PolicyRequest) Reset()         {}
func (m *PolicyRequest) String() string { return "" }
func (m *PolicyRequest) ProtoMessage()  {}

// AuthContext holds authentication context for policy evaluation.
type AuthContext struct {
	AuthType         string `protobuf:"bytes,1,opt,name=auth_type,json=authType,proto3" json:"auth_type,omitempty"`
	EapType          string `protobuf:"bytes,2,opt,name=eap_type,json=eapType,proto3" json:"eap_type,omitempty"`
	Username         string `protobuf:"bytes,3,opt,name=username,proto3" json:"username,omitempty"`
	CallingStationID string `protobuf:"bytes,4,opt,name=calling_station_id,json=callingStationId,proto3" json:"calling_station_id,omitempty"`
}

func (m *AuthContext) Reset()         {}
func (m *AuthContext) String() string { return "" }
func (m *AuthContext) ProtoMessage()  {}

// PolicyResponse is a lightweight Go struct mirroring the protobuf PolicyResponse.
type PolicyResponse struct {
	Decision      *PolicyDecision      `protobuf:"bytes,1,opt,name=decision,proto3" json:"decision,omitempty"`
	MatchedRuleID string               `protobuf:"bytes,2,opt,name=matched_rule_id,json=matchedRuleId,proto3" json:"matched_rule_id,omitempty"`
	Authorization *AuthorizationResult `protobuf:"bytes,5,opt,name=authorization,proto3" json:"authorization,omitempty"`
	Reason        string               `protobuf:"bytes,6,opt,name=reason,proto3" json:"reason,omitempty"`
}

func (m *PolicyResponse) Reset()         {}
func (m *PolicyResponse) String() string { return "" }
func (m *PolicyResponse) ProtoMessage()  {}

// PolicyDecision holds the permit/deny/quarantine decision.
type PolicyDecision struct {
	Type        int32  `protobuf:"varint,1,opt,name=type,proto3" json:"type,omitempty"`
	Description string `protobuf:"bytes,2,opt,name=description,proto3" json:"description,omitempty"`
}

func (m *PolicyDecision) Reset()         {}
func (m *PolicyDecision) String() string { return "" }
func (m *PolicyDecision) ProtoMessage()  {}

// Decision type constants matching the proto enum.
const (
	DecisionUnspecified int32 = 0
	DecisionPermit      int32 = 1
	DecisionDeny        int32 = 2
	DecisionQuarantine  int32 = 3
	DecisionRedirect    int32 = 4
	DecisionContinue    int32 = 5
)

// AuthorizationResult holds VLAN, SGT, DACL and other authorization attributes.
type AuthorizationResult struct {
	VlanID         string `protobuf:"bytes,1,opt,name=vlan_id,json=vlanId,proto3" json:"vlan_id,omitempty"`
	SgtValue       int32  `protobuf:"varint,4,opt,name=sgt_value,json=sgtValue,proto3" json:"sgt_value,omitempty"`
	DaclName       string `protobuf:"bytes,5,opt,name=dacl_name,json=daclName,proto3" json:"dacl_name,omitempty"`
	CoaAction      string `protobuf:"bytes,8,opt,name=coa_action,json=coaAction,proto3" json:"coa_action,omitempty"`
	SessionTimeout int32  `protobuf:"varint,12,opt,name=session_timeout,json=sessionTimeout,proto3" json:"session_timeout,omitempty"`
}

func (m *AuthorizationResult) Reset()         {}
func (m *AuthorizationResult) String() string { return "" }
func (m *AuthorizationResult) ProtoMessage()  {}
