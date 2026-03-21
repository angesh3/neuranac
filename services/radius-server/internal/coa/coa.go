package coa

import (
	"context"
	"fmt"
	"net"
	"sync"
	"time"

	"github.com/neuranac/services/radius-server/internal/radius"
	"go.uber.org/zap"
)

// CoASender sends Change of Authorization requests to NADs
type CoASender struct {
	logger  *zap.Logger
	pending sync.Map // map[string]chan *radius.Packet for tracking responses
}

// NewSender creates a new CoA sender
func NewSender(logger *zap.Logger) *CoASender {
	return &CoASender{logger: logger}
}

// SendDisconnect sends a Disconnect-Request to a NAD
func (s *CoASender) SendDisconnect(ctx context.Context, nadIP string, nadPort int, secret string, sessionID string, mac string) error {
	pkt := &radius.Packet{
		Code:       radius.CodeDisconnectRequest,
		Identifier: generateID(),
	}

	// Add Acct-Session-Id
	if sessionID != "" {
		pkt.Attributes = append(pkt.Attributes, radius.Attribute{
			Type:  radius.AttrAcctSessionID,
			Value: []byte(sessionID),
		})
	}

	// Add Calling-Station-Id (MAC)
	if mac != "" {
		pkt.Attributes = append(pkt.Attributes, radius.Attribute{
			Type:  radius.AttrCallingStationID,
			Value: []byte(mac),
		})
	}

	pkt.Secret = secret
	return s.send(ctx, nadIP, nadPort, pkt)
}

// SendCoA sends a CoA-Request to change session attributes (VLAN, SGT, etc.)
func (s *CoASender) SendCoA(ctx context.Context, nadIP string, nadPort int, secret string, sessionID string, attrs map[string]string) error {
	pkt := &radius.Packet{
		Code:       radius.CodeCoARequest,
		Identifier: generateID(),
	}

	if sessionID != "" {
		pkt.Attributes = append(pkt.Attributes, radius.Attribute{
			Type:  radius.AttrAcctSessionID,
			Value: []byte(sessionID),
		})
	}

	// Add vendor-specific attributes for VLAN/SGT changes
	for key, value := range attrs {
		switch key {
		case "filter-id":
			pkt.Attributes = append(pkt.Attributes, radius.Attribute{
				Type: radius.AttrFilterID, Value: []byte(value),
			})
		case "session-timeout":
			// encode as 4-byte integer
		}
	}

	pkt.Secret = secret
	return s.send(ctx, nadIP, nadPort, pkt)
}

// SendReauthenticate sends a CoA to trigger reauthentication
func (s *CoASender) SendReauthenticate(ctx context.Context, nadIP string, nadPort int, secret string, sessionID string) error {
	pkt := &radius.Packet{
		Code:       radius.CodeCoARequest,
		Identifier: generateID(),
	}

	if sessionID != "" {
		pkt.Attributes = append(pkt.Attributes, radius.Attribute{
			Type:  radius.AttrAcctSessionID,
			Value: []byte(sessionID),
		})
	}

	// Cisco VSA for reauthenticate
	// Vendor-Id: 9 (Cisco), Attribute: subscriber:command=reauthenticate
	ciscoReauth := buildCiscoVSA("subscriber:command=reauthenticate")
	pkt.Attributes = append(pkt.Attributes, radius.Attribute{
		Type:  radius.AttrVendorSpecific,
		Value: ciscoReauth,
	})

	pkt.Secret = secret
	return s.send(ctx, nadIP, nadPort, pkt)
}

func (s *CoASender) send(ctx context.Context, nadIP string, nadPort int, pkt *radius.Packet) error {
	addr := fmt.Sprintf("%s:%d", nadIP, nadPort)

	conn, err := net.DialTimeout("udp", addr, 5*time.Second)
	if err != nil {
		return fmt.Errorf("dial NAD %s: %w", addr, err)
	}
	defer conn.Close()

	// Encode and send
	data := pkt.Encode()
	conn.SetWriteDeadline(time.Now().Add(5 * time.Second))
	if _, err := conn.Write(data); err != nil {
		return fmt.Errorf("send to NAD %s: %w", addr, err)
	}

	// Wait for response
	conn.SetReadDeadline(time.Now().Add(5 * time.Second))
	respBuf := make([]byte, 4096)
	n, err := conn.Read(respBuf)
	if err != nil {
		return fmt.Errorf("read response from NAD %s: %w", addr, err)
	}

	resp, err := radius.ParsePacket(respBuf[:n])
	if err != nil {
		return fmt.Errorf("parse response: %w", err)
	}

	switch resp.Code {
	case radius.CodeDisconnectACK, radius.CodeCoAACK:
		s.logger.Info("CoA acknowledged", zap.String("nad", addr), zap.Int("code", int(resp.Code)))
		return nil
	case radius.CodeDisconnectNAK, radius.CodeCoANAK:
		s.logger.Warn("CoA rejected", zap.String("nad", addr))
		return fmt.Errorf("CoA rejected by NAD %s", addr)
	default:
		return fmt.Errorf("unexpected response code %d from NAD %s", resp.Code, addr)
	}
}

// ListenForResponses listens for unsolicited CoA responses
func ListenForResponses(ctx context.Context, addr string, logger *zap.Logger) error {
	udpAddr, err := net.ResolveUDPAddr("udp", addr)
	if err != nil {
		return err
	}
	conn, err := net.ListenUDP("udp", udpAddr)
	if err != nil {
		return err
	}
	defer conn.Close()

	logger.Info("CoA response listener started", zap.String("addr", addr))
	buf := make([]byte, 4096)
	for {
		select {
		case <-ctx.Done():
			return nil
		default:
			conn.SetReadDeadline(time.Now().Add(1 * time.Second))
			n, _, err := conn.ReadFromUDP(buf)
			if err != nil {
				if netErr, ok := err.(net.Error); ok && netErr.Timeout() {
					continue
				}
				continue
			}
			if n > 0 {
				logger.Debug("CoA response received", zap.Int("bytes", n))
			}
		}
	}
}

func buildCiscoVSA(avPair string) []byte {
	// Vendor-Id: 9 (Cisco), Type: 1 (Cisco-AV-Pair)
	vendorID := []byte{0, 0, 0, 9}
	avData := []byte(avPair)
	vsaLen := byte(2 + len(avData))
	result := append(vendorID, 1, vsaLen)
	result = append(result, avData...)
	return result
}

var idCounter byte = 0
var idMu sync.Mutex

func generateID() byte {
	idMu.Lock()
	defer idMu.Unlock()
	idCounter++
	return idCounter
}
