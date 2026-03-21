package radius

// RADIUS attribute types per RFC 2865/2866
const (
	AttrUserName          = 1
	AttrUserPassword      = 2
	AttrCHAPPassword      = 3
	AttrNASIPAddress      = 4
	AttrNASPort           = 5
	AttrServiceType       = 6
	AttrFramedProtocol    = 7
	AttrFramedIPAddress   = 8
	AttrFramedIPNetmask   = 9
	AttrFramedRouting     = 10
	AttrFilterID          = 11
	AttrFramedMTU         = 12
	AttrFramedCompression = 13
	AttrLoginIPHost       = 14
	AttrLoginService      = 15
	AttrLoginTCPPort      = 16
	AttrReplyMessage      = 18
	AttrCallbackNumber    = 19
	AttrCallbackID        = 20
	AttrState             = 24
	AttrClass             = 25
	AttrVendorSpecific    = 26
	AttrSessionTimeout    = 27
	AttrIdleTimeout       = 28
	AttrTerminationAction = 29
	AttrCalledStationID   = 30
	AttrCallingStationID  = 31
	AttrNASIdentifier     = 32
	AttrAcctStatusType    = 40
	AttrAcctDelayTime     = 41
	AttrAcctInputOctets   = 42
	AttrAcctOutputOctets  = 43
	AttrAcctSessionID     = 44
	AttrAcctAuthentic     = 45
	AttrAcctSessionTime   = 46
	AttrAcctInputPackets  = 47
	AttrAcctOutputPackets = 48
	AttrAcctTerminateCause = 49
	AttrNASPortType       = 61
	AttrTunnelType        = 64
	AttrTunnelMediumType  = 65
	AttrTunnelPrivateGroupID = 81
	AttrEAPMessage        = 79
	AttrMessageAuthenticator = 80
)

// RADIUS packet codes
const (
	CodeAccessRequest      = 1
	CodeAccessAccept       = 2
	CodeAccessReject       = 3
	CodeAccountingRequest  = 4
	CodeAccountingResponse = 5
	CodeAccessChallenge    = 11
	CodeDisconnectRequest  = 40
	CodeDisconnectACK      = 41
	CodeDisconnectNAK      = 42
	CodeCoARequest         = 43
	CodeCoAACK             = 44
	CodeCoANAK             = 45
)

// EAP types
const (
	EAPTypeIdentity     = 1
	EAPTypeNotification = 2
	EAPTypeNak          = 3
	EAPTypeMD5Challenge = 4
	EAPTypeOTP          = 5
	EAPTypeGTC          = 6
	EAPTypeTLS          = 13
	EAPTypeLEAP         = 17
	EAPTypeSIM          = 18
	EAPTypeTTLS         = 21
	EAPTypePEAP         = 25
	EAPTypeMSCHAPv2     = 26
	EAPTypeFAST         = 43
	EAPTypeMACSec       = 0xFE
)

// EAP codes
const (
	EAPCodeRequest  = 1
	EAPCodeResponse = 2
	EAPCodeSuccess  = 3
	EAPCodeFailure  = 4
)

// Accounting status types
const (
	AcctStatusStart         = 1
	AcctStatusStop          = 2
	AcctStatusInterimUpdate = 3
	AcctStatusAccountingOn  = 7
	AcctStatusAccountingOff = 8
)

// Vendor IDs
const (
	VendorCisco    = 9
	VendorMicrosoft = 311
	VendorJuniper  = 2636
	VendorAruba    = 14823
	VendorMeraki   = 29671
)

// Cisco AV-Pair sub-attributes
const (
	CiscoAVPair      = 1
	CiscoAuditSessionID = 253
	CiscoSGT         = 254
)

// Attribute represents a RADIUS attribute with type and value
type Attribute struct {
	Type   byte
	Length byte
	Value  []byte
}

// VendorAttribute represents a vendor-specific attribute (VSA)
type VendorAttribute struct {
	VendorID  uint32
	Type      byte
	Length    byte
	Value     []byte
}

// EAPPacket represents an EAP packet extracted from RADIUS EAP-Message attributes
type EAPPacket struct {
	Code       byte
	Identifier byte
	Length     uint16
	Type       byte // only for Request/Response
	Data       []byte
}

// ParseEAPPacket parses raw EAP data from concatenated EAP-Message attributes
func ParseEAPPacket(data []byte) *EAPPacket {
	if len(data) < 4 {
		return nil
	}
	pkt := &EAPPacket{
		Code:       data[0],
		Identifier: data[1],
		Length:     uint16(data[2])<<8 | uint16(data[3]),
	}
	if pkt.Code == EAPCodeRequest || pkt.Code == EAPCodeResponse {
		if len(data) >= 5 {
			pkt.Type = data[4]
			if len(data) > 5 {
				pkt.Data = data[5:]
			}
		}
	} else if len(data) > 4 {
		pkt.Data = data[4:]
	}
	return pkt
}

// ParseVSA parses a vendor-specific attribute from raw RADIUS attribute value
func ParseVSA(data []byte) *VendorAttribute {
	if len(data) < 6 {
		return nil
	}
	vsa := &VendorAttribute{
		VendorID: uint32(data[0])<<24 | uint32(data[1])<<16 | uint32(data[2])<<8 | uint32(data[3]),
		Type:     data[4],
		Length:   data[5],
	}
	if len(data) > 6 {
		vsa.Value = data[6:]
	}
	return vsa
}

// AttrName returns a human-readable name for a RADIUS attribute type
func AttrName(attrType byte) string {
	names := map[byte]string{
		AttrUserName:          "User-Name",
		AttrUserPassword:      "User-Password",
		AttrNASIPAddress:      "NAS-IP-Address",
		AttrNASPort:           "NAS-Port",
		AttrServiceType:       "Service-Type",
		AttrFilterID:          "Filter-Id",
		AttrReplyMessage:      "Reply-Message",
		AttrState:             "State",
		AttrClass:             "Class",
		AttrVendorSpecific:    "Vendor-Specific",
		AttrSessionTimeout:    "Session-Timeout",
		AttrIdleTimeout:       "Idle-Timeout",
		AttrCalledStationID:   "Called-Station-Id",
		AttrCallingStationID:  "Calling-Station-Id",
		AttrNASIdentifier:     "NAS-Identifier",
		AttrAcctStatusType:    "Acct-Status-Type",
		AttrAcctSessionID:     "Acct-Session-Id",
		AttrNASPortType:       "NAS-Port-Type",
		AttrTunnelType:        "Tunnel-Type",
		AttrTunnelMediumType:  "Tunnel-Medium-Type",
		AttrTunnelPrivateGroupID: "Tunnel-Private-Group-Id",
		AttrEAPMessage:        "EAP-Message",
		AttrMessageAuthenticator: "Message-Authenticator",
	}
	if name, ok := names[attrType]; ok {
		return name
	}
	return "Unknown"
}

// EAPTypeName returns a human-readable name for an EAP type
func EAPTypeName(eapType byte) string {
	names := map[byte]string{
		EAPTypeIdentity:     "Identity",
		EAPTypeNotification: "Notification",
		EAPTypeNak:          "Nak",
		EAPTypeMD5Challenge: "MD5-Challenge",
		EAPTypeTLS:          "EAP-TLS",
		EAPTypeTTLS:         "EAP-TTLS",
		EAPTypePEAP:         "PEAP",
		EAPTypeMSCHAPv2:     "EAP-MSCHAPv2",
		EAPTypeFAST:         "EAP-FAST",
	}
	if name, ok := names[eapType]; ok {
		return name
	}
	return "Unknown"
}
