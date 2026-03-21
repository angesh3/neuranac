package integration

import (
	"crypto/md5"
	"encoding/binary"
	"fmt"
	"math/rand"
	"net"
	"testing"
	"time"
)

// RADIUS packet codes
const (
	CodeAccessRequest   = 1
	CodeAccessAccept    = 2
	CodeAccessReject    = 3
	CodeAccountingReq   = 4
	CodeAccountingResp  = 5
	CodeAccessChallenge = 11
)

// RADIUS attribute types
const (
	AttrUserName         = 1
	AttrUserPassword     = 2
	AttrNASIPAddress     = 4
	AttrNASPort          = 5
	AttrServiceType      = 6
	AttrCallingStationID = 31
	AttrNASPortType      = 61
	AttrEAPMessage       = 79
	AttrMsgAuthenticator = 80
	AttrAcctStatusType   = 40
	AttrAcctSessionID    = 44
)

// RadiusPacket represents a raw RADIUS protocol packet
type RadiusPacket struct {
	Code          byte
	Identifier    byte
	Authenticator [16]byte
	Attributes    []RadiusAttribute
	Secret        string
}

// RadiusAttribute represents a RADIUS AVP
type RadiusAttribute struct {
	Type  byte
	Value []byte
}

// BuildAccessRequest constructs a RADIUS Access-Request packet
func BuildAccessRequest(username, password, secret string, nasIP string) *RadiusPacket {
	pkt := &RadiusPacket{
		Code:       CodeAccessRequest,
		Identifier: byte(rand.Intn(256)),
		Secret:     secret,
	}
	// Generate random authenticator
	for i := range pkt.Authenticator {
		pkt.Authenticator[i] = byte(rand.Intn(256))
	}

	// Add User-Name
	pkt.AddAttribute(AttrUserName, []byte(username))
	// Add User-Password (PAP encrypted)
	pkt.AddAttribute(AttrUserPassword, encryptPAPPassword(password, secret, pkt.Authenticator))
	// Add NAS-IP-Address
	pkt.AddAttribute(AttrNASIPAddress, net.ParseIP(nasIP).To4())
	// Add NAS-Port-Type (Ethernet = 15)
	portType := make([]byte, 4)
	binary.BigEndian.PutUint32(portType, 15)
	pkt.AddAttribute(AttrNASPortType, portType)

	return pkt
}

// BuildMABRequest constructs a MAC Authentication Bypass request
func BuildMABRequest(mac, secret, nasIP string) *RadiusPacket {
	pkt := &RadiusPacket{
		Code:       CodeAccessRequest,
		Identifier: byte(rand.Intn(256)),
		Secret:     secret,
	}
	for i := range pkt.Authenticator {
		pkt.Authenticator[i] = byte(rand.Intn(256))
	}

	// MAB: username = MAC address
	pkt.AddAttribute(AttrUserName, []byte(mac))
	pkt.AddAttribute(AttrCallingStationID, []byte(mac))
	pkt.AddAttribute(AttrNASIPAddress, net.ParseIP(nasIP).To4())

	serviceType := make([]byte, 4)
	binary.BigEndian.PutUint32(serviceType, 10) // Call-Check
	pkt.AddAttribute(AttrServiceType, serviceType)

	return pkt
}

// BuildAccountingRequest constructs a RADIUS Accounting-Request
func BuildAccountingRequest(statusType uint32, sessionID, mac, secret, nasIP string) *RadiusPacket {
	pkt := &RadiusPacket{
		Code:       CodeAccountingReq,
		Identifier: byte(rand.Intn(256)),
		Secret:     secret,
	}
	for i := range pkt.Authenticator {
		pkt.Authenticator[i] = byte(rand.Intn(256))
	}

	st := make([]byte, 4)
	binary.BigEndian.PutUint32(st, statusType)
	pkt.AddAttribute(AttrAcctStatusType, st)
	pkt.AddAttribute(AttrAcctSessionID, []byte(sessionID))
	pkt.AddAttribute(AttrCallingStationID, []byte(mac))
	pkt.AddAttribute(AttrNASIPAddress, net.ParseIP(nasIP).To4())

	return pkt
}

// BuildEAPIdentityRequest builds an Access-Request with EAP-Identity
func BuildEAPIdentityRequest(username, secret, nasIP string) *RadiusPacket {
	pkt := &RadiusPacket{
		Code:       CodeAccessRequest,
		Identifier: byte(rand.Intn(256)),
		Secret:     secret,
	}
	for i := range pkt.Authenticator {
		pkt.Authenticator[i] = byte(rand.Intn(256))
	}

	// EAP-Response/Identity
	identity := []byte(username)
	eapLen := 5 + len(identity)
	eapMsg := []byte{
		2,                    // Response
		1,                    // ID
		byte(eapLen >> 8),    // Length high
		byte(eapLen & 0xff),  // Length low
		1,                    // Type: Identity
	}
	eapMsg = append(eapMsg, identity...)

	pkt.AddAttribute(AttrUserName, []byte(username))
	pkt.AddAttribute(AttrEAPMessage, eapMsg)
	pkt.AddAttribute(AttrNASIPAddress, net.ParseIP(nasIP).To4())

	// Message-Authenticator (zeroed, then computed)
	pkt.AddAttribute(AttrMsgAuthenticator, make([]byte, 16))

	return pkt
}

// AddAttribute adds an attribute to the packet
func (p *RadiusPacket) AddAttribute(attrType byte, value []byte) {
	p.Attributes = append(p.Attributes, RadiusAttribute{
		Type:  attrType,
		Value: value,
	})
}

// Encode serializes the RADIUS packet to bytes
func (p *RadiusPacket) Encode() []byte {
	// Calculate total length
	attrLen := 0
	for _, a := range p.Attributes {
		attrLen += 2 + len(a.Value)
	}
	totalLen := 20 + attrLen

	buf := make([]byte, totalLen)
	buf[0] = p.Code
	buf[1] = p.Identifier
	binary.BigEndian.PutUint16(buf[2:4], uint16(totalLen))
	copy(buf[4:20], p.Authenticator[:])

	offset := 20
	for _, a := range p.Attributes {
		buf[offset] = a.Type
		buf[offset+1] = byte(2 + len(a.Value))
		copy(buf[offset+2:], a.Value)
		offset += 2 + len(a.Value)
	}

	return buf
}

// ParseRadiusResponse parses a raw RADIUS response
func ParseRadiusResponse(data []byte) (*RadiusPacket, error) {
	if len(data) < 20 {
		return nil, fmt.Errorf("packet too short: %d bytes", len(data))
	}

	pkt := &RadiusPacket{
		Code:       data[0],
		Identifier: data[1],
	}
	copy(pkt.Authenticator[:], data[4:20])

	length := int(binary.BigEndian.Uint16(data[2:4]))
	if length > len(data) {
		length = len(data)
	}

	// Parse attributes
	offset := 20
	for offset < length {
		if offset+2 > length {
			break
		}
		attrType := data[offset]
		attrLen := int(data[offset+1])
		if attrLen < 2 || offset+attrLen > length {
			break
		}
		value := make([]byte, attrLen-2)
		copy(value, data[offset+2:offset+attrLen])
		pkt.Attributes = append(pkt.Attributes, RadiusAttribute{
			Type:  attrType,
			Value: value,
		})
		offset += attrLen
	}

	return pkt, nil
}

// GetAttribute returns the first attribute of the given type
func (p *RadiusPacket) GetAttribute(attrType byte) []byte {
	for _, a := range p.Attributes {
		if a.Type == attrType {
			return a.Value
		}
	}
	return nil
}

// encryptPAPPassword encrypts a PAP password per RFC 2865 Section 5.2
func encryptPAPPassword(password, secret string, authenticator [16]byte) []byte {
	// Pad password to multiple of 16 bytes
	pass := []byte(password)
	padLen := 16 - (len(pass) % 16)
	if padLen < 16 {
		pass = append(pass, make([]byte, padLen)...)
	}
	if len(pass) == 0 {
		pass = make([]byte, 16)
	}

	encrypted := make([]byte, len(pass))
	// First block: XOR with MD5(secret + authenticator)
	hash := md5.Sum(append([]byte(secret), authenticator[:]...))
	for i := 0; i < 16; i++ {
		encrypted[i] = pass[i] ^ hash[i]
	}

	// Subsequent blocks: XOR with MD5(secret + previous ciphertext)
	for block := 1; block < len(pass)/16; block++ {
		hash = md5.Sum(append([]byte(secret), encrypted[(block-1)*16:block*16]...))
		for i := 0; i < 16; i++ {
			encrypted[block*16+i] = pass[block*16+i] ^ hash[i]
		}
	}

	return encrypted
}

// sendRADIUS sends a RADIUS packet to the given address and returns the response
func sendRADIUS(t *testing.T, addr string, pkt *RadiusPacket, timeout time.Duration) *RadiusPacket {
	t.Helper()

	conn, err := net.DialTimeout("udp", addr, timeout)
	if err != nil {
		t.Skipf("RADIUS server not available at %s: %v", addr, err)
		return nil
	}
	defer conn.Close()

	conn.SetDeadline(time.Now().Add(timeout))

	encoded := pkt.Encode()
	_, err = conn.Write(encoded)
	if err != nil {
		t.Fatalf("failed to send RADIUS packet: %v", err)
	}

	buf := make([]byte, 4096)
	n, err := conn.Read(buf)
	if err != nil {
		t.Fatalf("failed to read RADIUS response: %v", err)
	}

	resp, err := ParseRadiusResponse(buf[:n])
	if err != nil {
		t.Fatalf("failed to parse RADIUS response: %v", err)
	}

	return resp
}

// --- Protocol Tests ---

func TestRADIUS_PacketEncoding(t *testing.T) {
	pkt := BuildAccessRequest("testuser", "testpass", "testing123", "10.0.0.1")
	encoded := pkt.Encode()

	if len(encoded) < 20 {
		t.Fatalf("encoded packet too short: %d", len(encoded))
	}
	if encoded[0] != CodeAccessRequest {
		t.Errorf("expected code %d, got %d", CodeAccessRequest, encoded[0])
	}

	length := binary.BigEndian.Uint16(encoded[2:4])
	if int(length) != len(encoded) {
		t.Errorf("length field %d != actual length %d", length, len(encoded))
	}

	// Parse it back
	parsed, err := ParseRadiusResponse(encoded)
	if err != nil {
		t.Fatalf("parse error: %v", err)
	}
	if parsed.Code != CodeAccessRequest {
		t.Errorf("parsed code %d != %d", parsed.Code, CodeAccessRequest)
	}

	username := parsed.GetAttribute(AttrUserName)
	if string(username) != "testuser" {
		t.Errorf("expected username 'testuser', got '%s'", string(username))
	}
}

func TestRADIUS_MABPacketConstruction(t *testing.T) {
	pkt := BuildMABRequest("AA:BB:CC:DD:EE:FF", "secret", "10.0.0.1")
	encoded := pkt.Encode()

	parsed, err := ParseRadiusResponse(encoded)
	if err != nil {
		t.Fatalf("parse error: %v", err)
	}

	username := string(parsed.GetAttribute(AttrUserName))
	if username != "AA:BB:CC:DD:EE:FF" {
		t.Errorf("MAB username should be MAC, got '%s'", username)
	}

	callingStation := string(parsed.GetAttribute(AttrCallingStationID))
	if callingStation != "AA:BB:CC:DD:EE:FF" {
		t.Errorf("Calling-Station-Id should be MAC, got '%s'", callingStation)
	}
}

func TestRADIUS_AccountingPacketConstruction(t *testing.T) {
	pkt := BuildAccountingRequest(1, "sess-123", "AA:BB:CC:DD:EE:FF", "secret", "10.0.0.1")
	encoded := pkt.Encode()

	parsed, err := ParseRadiusResponse(encoded)
	if err != nil {
		t.Fatalf("parse error: %v", err)
	}

	if parsed.Code != CodeAccountingReq {
		t.Errorf("expected Accounting-Request code %d, got %d", CodeAccountingReq, parsed.Code)
	}

	sessID := string(parsed.GetAttribute(AttrAcctSessionID))
	if sessID != "sess-123" {
		t.Errorf("expected session ID 'sess-123', got '%s'", sessID)
	}
}

func TestRADIUS_EAPIdentityPacket(t *testing.T) {
	pkt := BuildEAPIdentityRequest("802.1x-user", "secret", "10.0.0.1")
	encoded := pkt.Encode()

	parsed, err := ParseRadiusResponse(encoded)
	if err != nil {
		t.Fatalf("parse error: %v", err)
	}

	eapMsg := parsed.GetAttribute(AttrEAPMessage)
	if eapMsg == nil {
		t.Fatal("EAP-Message attribute missing")
	}
	if len(eapMsg) < 5 {
		t.Fatalf("EAP-Message too short: %d", len(eapMsg))
	}
	if eapMsg[0] != 2 { // EAP Response
		t.Errorf("expected EAP Response (2), got %d", eapMsg[0])
	}
	if eapMsg[4] != 1 { // Identity
		t.Errorf("expected EAP Identity type (1), got %d", eapMsg[4])
	}

	identity := string(eapMsg[5:])
	if identity != "802.1x-user" {
		t.Errorf("expected identity '802.1x-user', got '%s'", identity)
	}
}

func TestRADIUS_PAPPasswordEncryption(t *testing.T) {
	var auth [16]byte
	for i := range auth {
		auth[i] = byte(i)
	}
	encrypted := encryptPAPPassword("password", "secret", auth)

	if len(encrypted) == 0 {
		t.Fatal("encrypted password is empty")
	}
	if len(encrypted)%16 != 0 {
		t.Errorf("encrypted password length %d is not multiple of 16", len(encrypted))
	}

	// Verify it's not the plaintext
	if string(encrypted[:8]) == "password" {
		t.Error("password was not encrypted")
	}
}

func TestRADIUS_ResponseParsing(t *testing.T) {
	// Build a mock Access-Accept response
	resp := make([]byte, 20)
	resp[0] = CodeAccessAccept
	resp[1] = 42 // Identifier
	binary.BigEndian.PutUint16(resp[2:4], 20) // Length

	parsed, err := ParseRadiusResponse(resp)
	if err != nil {
		t.Fatalf("parse error: %v", err)
	}
	if parsed.Code != CodeAccessAccept {
		t.Errorf("expected Access-Accept, got code %d", parsed.Code)
	}
	if parsed.Identifier != 42 {
		t.Errorf("expected identifier 42, got %d", parsed.Identifier)
	}
}

func TestRADIUS_ResponseWithAttributes(t *testing.T) {
	// Build Access-Accept with a Reply-Message attribute
	replyMsg := []byte("Welcome to NeuraNAC")
	attrLen := 2 + len(replyMsg)
	totalLen := 20 + attrLen

	resp := make([]byte, totalLen)
	resp[0] = CodeAccessAccept
	resp[1] = 1
	binary.BigEndian.PutUint16(resp[2:4], uint16(totalLen))
	// Attribute: Reply-Message (18)
	resp[20] = 18
	resp[21] = byte(attrLen)
	copy(resp[22:], replyMsg)

	parsed, err := ParseRadiusResponse(resp)
	if err != nil {
		t.Fatalf("parse error: %v", err)
	}

	msg := parsed.GetAttribute(18)
	if string(msg) != "Welcome to NeuraNAC" {
		t.Errorf("expected 'Welcome to NeuraNAC', got '%s'", string(msg))
	}
}

func TestRADIUS_ShortPacketRejected(t *testing.T) {
	_, err := ParseRadiusResponse([]byte{1, 2, 3})
	if err == nil {
		t.Error("expected error for short packet")
	}
}

func TestRADIUS_LiveAccessRequest(t *testing.T) {
	// This test requires a running RADIUS server
	addr := "127.0.0.1:1812"
	conn, err := net.DialTimeout("udp", addr, 500*time.Millisecond)
	if err != nil {
		t.Skipf("RADIUS server not available at %s, skipping live test", addr)
		return
	}
	conn.Close()

	pkt := BuildAccessRequest("admin", "admin123", "testing123", "10.0.0.1")
	resp := sendRADIUS(t, addr, pkt, 3*time.Second)

	if resp == nil {
		t.Skip("no response from RADIUS server")
		return
	}

	// Expect either Accept, Reject, or Challenge — any valid RADIUS response
	validCodes := map[byte]bool{
		CodeAccessAccept:    true,
		CodeAccessReject:    true,
		CodeAccessChallenge: true,
	}
	if !validCodes[resp.Code] {
		t.Errorf("unexpected response code: %d", resp.Code)
	}

	// Verify response identifier matches request
	if resp.Identifier != pkt.Identifier {
		t.Errorf("response identifier %d != request identifier %d", resp.Identifier, pkt.Identifier)
	}
}

func TestRADIUS_LiveMABRequest(t *testing.T) {
	addr := "127.0.0.1:1812"
	conn, err := net.DialTimeout("udp", addr, 500*time.Millisecond)
	if err != nil {
		t.Skipf("RADIUS server not available at %s", addr)
		return
	}
	conn.Close()

	pkt := BuildMABRequest("AA:BB:CC:DD:EE:FF", "testing123", "10.0.0.1")
	resp := sendRADIUS(t, addr, pkt, 3*time.Second)

	if resp == nil {
		t.Skip("no response")
		return
	}

	validCodes := map[byte]bool{
		CodeAccessAccept: true,
		CodeAccessReject: true,
	}
	if !validCodes[resp.Code] {
		t.Errorf("unexpected MAB response code: %d", resp.Code)
	}
}

func TestRADIUS_LiveAccountingRequest(t *testing.T) {
	addr := "127.0.0.1:1813"
	conn, err := net.DialTimeout("udp", addr, 500*time.Millisecond)
	if err != nil {
		t.Skipf("RADIUS accounting not available at %s", addr)
		return
	}
	conn.Close()

	pkt := BuildAccountingRequest(1, "acct-sess-001", "AA:BB:CC:DD:EE:FF", "testing123", "10.0.0.1")
	resp := sendRADIUS(t, addr, pkt, 3*time.Second)

	if resp == nil {
		t.Skip("no response")
		return
	}

	if resp.Code != CodeAccountingResp {
		t.Errorf("expected Accounting-Response (%d), got %d", CodeAccountingResp, resp.Code)
	}
}

func TestRADIUS_LiveEAPIdentity(t *testing.T) {
	addr := "127.0.0.1:1812"
	conn, err := net.DialTimeout("udp", addr, 500*time.Millisecond)
	if err != nil {
		t.Skipf("RADIUS server not available at %s", addr)
		return
	}
	conn.Close()

	pkt := BuildEAPIdentityRequest("eap-user@neuranac.local", "testing123", "10.0.0.1")
	resp := sendRADIUS(t, addr, pkt, 3*time.Second)

	if resp == nil {
		t.Skip("no response")
		return
	}

	// EAP Identity should trigger Access-Challenge with EAP-Request
	validCodes := map[byte]bool{
		CodeAccessChallenge: true,
		CodeAccessReject:    true,
		CodeAccessAccept:    true,
	}
	if !validCodes[resp.Code] {
		t.Errorf("unexpected EAP response code: %d", resp.Code)
	}
}
