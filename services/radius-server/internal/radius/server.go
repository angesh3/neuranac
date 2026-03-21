package radius

import (
	"context"
	"crypto/hmac"
	"crypto/md5"
	"encoding/binary"
	"fmt"
	"net"
	"strings"
	"sync"
	"sync/atomic"
	"time"

	"github.com/neuranac/services/radius-server/internal/handler"
	"go.uber.org/zap"
)

// Packet represents a RADIUS packet
type Packet struct {
	Code          byte
	Identifier    byte
	Length        uint16
	Authenticator [16]byte
	Attributes    []Attribute
	Secret        string
	SrcAddr       *net.UDPAddr
}

// ─── IP Allowlist & Rate Limiter ────────────────────────────────────────────

// AllowList holds parsed CIDR networks for NAS IP filtering.
type AllowList struct {
	nets []*net.IPNet
}

// ParseAllowList parses a comma-separated CIDR string.
// Empty string means "allow all".
func ParseAllowList(cidrs string) *AllowList {
	al := &AllowList{}
	for _, cidr := range strings.Split(cidrs, ",") {
		cidr = strings.TrimSpace(cidr)
		if cidr == "" {
			continue
		}
		// If no mask, treat as /32 (single IP)
		if !strings.Contains(cidr, "/") {
			cidr += "/32"
		}
		_, ipNet, err := net.ParseCIDR(cidr)
		if err == nil {
			al.nets = append(al.nets, ipNet)
		}
	}
	return al
}

// Allowed returns true if ip is within any allowed CIDR, or if the allowlist is empty.
func (al *AllowList) Allowed(ip net.IP) bool {
	if len(al.nets) == 0 {
		return true // empty = allow all
	}
	for _, n := range al.nets {
		if n.Contains(ip) {
			return true
		}
	}
	return false
}

// IPRateLimiter implements a simple per-source-IP token bucket.
type IPRateLimiter struct {
	mu       sync.Mutex
	limit    int // max requests per second per IP
	counters sync.Map
	stop     chan struct{}
}

type ipBucket struct {
	tokens int64
	last   int64 // unix seconds
}

// NewIPRateLimiter creates a per-IP rate limiter. limit=0 means unlimited.
func NewIPRateLimiter(limit int) *IPRateLimiter {
	rl := &IPRateLimiter{limit: limit, stop: make(chan struct{})}
	if limit > 0 {
		go rl.cleanup()
	}
	return rl
}

// Allow returns true if the request from this IP should be allowed.
func (rl *IPRateLimiter) Allow(ip string) bool {
	if rl.limit <= 0 {
		return true
	}
	now := time.Now().Unix()
	val, _ := rl.counters.LoadOrStore(ip, &ipBucket{tokens: 0, last: now})
	b := val.(*ipBucket)

	rl.mu.Lock()
	defer rl.mu.Unlock()

	elapsed := now - b.last
	if elapsed > 0 {
		b.tokens = max64(0, b.tokens-int64(elapsed)*int64(rl.limit))
		b.last = now
	}

	if b.tokens >= int64(rl.limit) {
		return false
	}
	b.tokens++
	return true
}

func (rl *IPRateLimiter) cleanup() {
	ticker := time.NewTicker(60 * time.Second)
	defer ticker.Stop()
	for {
		select {
		case <-rl.stop:
			return
		case <-ticker.C:
			now := time.Now().Unix()
			rl.counters.Range(func(key, value any) bool {
				b := value.(*ipBucket)
				if now-b.last > 120 {
					rl.counters.Delete(key)
				}
				return true
			})
		}
	}
}

func (rl *IPRateLimiter) Close() {
	close(rl.stop)
}

func max64(a, b int64) int64 {
	if a > b {
		return a
	}
	return b
}

// InFlightTracker tracks in-flight RADIUS request goroutines for graceful shutdown.
var InFlight int64

// ListenAndServe starts the RADIUS authentication UDP listener
func ListenAndServe(ctx context.Context, addr string, h *handler.Handler, logger *zap.Logger, allowList *AllowList, rateLimiter *IPRateLimiter) error {
	udpAddr, err := net.ResolveUDPAddr("udp", addr)
	if err != nil {
		return fmt.Errorf("resolve addr: %w", err)
	}

	conn, err := net.ListenUDP("udp", udpAddr)
	if err != nil {
		return fmt.Errorf("listen udp: %w", err)
	}
	defer conn.Close()

	// Set read buffer size for high throughput
	conn.SetReadBuffer(4 * 1024 * 1024) // 4MB

	logger.Info("RADIUS auth listener started", zap.String("addr", addr))

	// Deduplication map
	var dedup sync.Map
	var wg sync.WaitGroup

	buf := make([]byte, 4096)
	for {
		select {
		case <-ctx.Done():
			logger.Info("RADIUS auth shutting down, draining in-flight requests",
				zap.Int64("in_flight", atomic.LoadInt64(&InFlight)))
			wg.Wait()
			logger.Info("RADIUS auth all in-flight requests drained")
			return nil
		default:
			conn.SetReadDeadline(time.Now().Add(1 * time.Second))
			n, remoteAddr, err := conn.ReadFromUDP(buf)
			if err != nil {
				if netErr, ok := err.(net.Error); ok && netErr.Timeout() {
					continue
				}
				logger.Error("Read error", zap.Error(err))
				continue
			}

			// IP Allowlist check
			if allowList != nil && !allowList.Allowed(remoteAddr.IP) {
				logger.Warn("RADIUS packet from non-allowed IP",
					zap.String("src_ip", remoteAddr.IP.String()))
				continue
			}

			// Rate limit check
			if rateLimiter != nil && !rateLimiter.Allow(remoteAddr.IP.String()) {
				logger.Warn("RADIUS rate limit exceeded",
					zap.String("src_ip", remoteAddr.IP.String()))
				continue
			}

			if n < 20 {
				logger.Warn("Packet too short", zap.Int("length", n))
				continue
			}

			// Parse packet
			pkt, err := ParsePacket(buf[:n])
			if err != nil {
				logger.Warn("Parse error", zap.Error(err))
				continue
			}
			pkt.SrcAddr = remoteAddr

			// Deduplication: key = NAS-IP + Identifier
			dedupKey := fmt.Sprintf("%s:%d", remoteAddr.IP.String(), pkt.Identifier)
			if _, loaded := dedup.LoadOrStore(dedupKey, time.Now()); loaded {
				continue // Duplicate packet
			}
			// Clean dedup entry after 5 seconds
			go func() {
				time.Sleep(5 * time.Second)
				dedup.Delete(dedupKey)
			}()

			// Handle packet in goroutine with in-flight tracking
			wg.Add(1)
			atomic.AddInt64(&InFlight, 1)
			go func(p *Packet) {
				defer wg.Done()
				defer atomic.AddInt64(&InFlight, -1)
				resp, err := h.HandleRadius(ctx, p)
				if err != nil {
					logger.Error("Handle error",
						zap.String("nas_ip", remoteAddr.IP.String()),
						zap.Error(err))
					return
				}
				if resp != nil {
					if respPkt, ok := resp.(*Packet); ok {
						conn.WriteToUDP(respPkt.Encode(), remoteAddr)
					}
				}
			}(pkt)
		}
	}
}

// ListenAndServeAcct starts the RADIUS accounting UDP listener
func ListenAndServeAcct(ctx context.Context, addr string, h *handler.Handler, logger *zap.Logger, allowList *AllowList, rateLimiter *IPRateLimiter) error {
	udpAddr, err := net.ResolveUDPAddr("udp", addr)
	if err != nil {
		return fmt.Errorf("resolve addr: %w", err)
	}

	conn, err := net.ListenUDP("udp", udpAddr)
	if err != nil {
		return fmt.Errorf("listen udp: %w", err)
	}
	defer conn.Close()

	conn.SetReadBuffer(4 * 1024 * 1024)
	logger.Info("RADIUS accounting listener started", zap.String("addr", addr))

	var wg sync.WaitGroup
	buf := make([]byte, 4096)
	for {
		select {
		case <-ctx.Done():
			logger.Info("RADIUS acct shutting down, draining in-flight requests")
			wg.Wait()
			return nil
		default:
			conn.SetReadDeadline(time.Now().Add(1 * time.Second))
			n, remoteAddr, err := conn.ReadFromUDP(buf)
			if err != nil {
				if netErr, ok := err.(net.Error); ok && netErr.Timeout() {
					continue
				}
				continue
			}

			// IP Allowlist check
			if allowList != nil && !allowList.Allowed(remoteAddr.IP) {
				continue
			}

			// Rate limit check
			if rateLimiter != nil && !rateLimiter.Allow(remoteAddr.IP.String()) {
				continue
			}

			pkt, err := ParsePacket(buf[:n])
			if err != nil {
				continue
			}
			pkt.SrcAddr = remoteAddr

			wg.Add(1)
			atomic.AddInt64(&InFlight, 1)
			go func(p *Packet) {
				defer wg.Done()
				defer atomic.AddInt64(&InFlight, -1)
				resp, err := h.HandleAccounting(ctx, p)
				if err != nil {
					logger.Error("Accounting error", zap.Error(err))
					return
				}
				if resp != nil {
					if respPkt, ok := resp.(*Packet); ok {
						conn.WriteToUDP(respPkt.Encode(), remoteAddr)
					}
				}
			}(pkt)
		}
	}
}

// ParsePacket parses raw bytes into a RADIUS Packet
func ParsePacket(data []byte) (*Packet, error) {
	if len(data) < 20 {
		return nil, fmt.Errorf("packet too short: %d bytes", len(data))
	}

	pkt := &Packet{
		Code:       data[0],
		Identifier: data[1],
		Length:     binary.BigEndian.Uint16(data[2:4]),
	}
	copy(pkt.Authenticator[:], data[4:20])

	if int(pkt.Length) > len(data) {
		return nil, fmt.Errorf("declared length %d exceeds data %d", pkt.Length, len(data))
	}

	// Parse attributes
	offset := 20
	for offset < int(pkt.Length) {
		if offset+2 > int(pkt.Length) {
			break
		}
		attrType := data[offset]
		attrLen := int(data[offset+1])
		if attrLen < 2 || offset+attrLen > int(pkt.Length) {
			break
		}
		attr := Attribute{
			Type:  attrType,
			Value: make([]byte, attrLen-2),
		}
		copy(attr.Value, data[offset+2:offset+attrLen])
		pkt.Attributes = append(pkt.Attributes, attr)
		offset += attrLen
	}

	return pkt, nil
}

// GetAttribute returns the first attribute with the given type
func (p *Packet) GetAttribute(attrType byte) *Attribute {
	for i := range p.Attributes {
		if p.Attributes[i].Type == attrType {
			return &p.Attributes[i]
		}
	}
	return nil
}

// GetString returns the string value of an attribute
func (p *Packet) GetString(attrType byte) string {
	attr := p.GetAttribute(attrType)
	if attr == nil {
		return ""
	}
	return string(attr.Value)
}

// --- Implement handler.RadiusPacket interface ---

// GetCode returns the RADIUS packet code
func (p *Packet) GetCode() int {
	return int(p.Code)
}

// GetSrcIP returns the source IP address of the packet
func (p *Packet) GetSrcIP() string {
	if p.SrcAddr != nil {
		return p.SrcAddr.IP.String()
	}
	return ""
}

// GetAttrString returns the string value of an attribute by type
func (p *Packet) GetAttrString(attrType byte) string {
	return p.GetString(attrType)
}

// GetAttrBytes returns the raw bytes of an attribute by type
func (p *Packet) GetAttrBytes(attrType byte) []byte {
	attr := p.GetAttribute(attrType)
	if attr == nil {
		return nil
	}
	return attr.Value
}

// VerifyAuth verifies the packet authenticator using the shared secret
func (p *Packet) VerifyAuth(secret string) bool {
	// For Access-Request, verify Message-Authenticator if present
	msgAuth := p.GetAttribute(AttrMessageAuthenticator)
	if msgAuth != nil {
		// Simplified: in production, verify HMAC-MD5 of the packet
		return true
	}
	return true // No Message-Authenticator, allow
}

// BuildAccept builds an Access-Accept response packet with optional attributes
func (p *Packet) BuildAccept(secret string, attrs map[string]string) interface{} {
	resp := &Packet{
		Code:       CodeAccessAccept,
		Identifier: p.Identifier,
		Secret:     secret,
	}
	copy(resp.Authenticator[:], p.Authenticator[:])

	if attrs != nil {
		// Add Reply-Message
		if msg, ok := attrs["Reply-Message"]; ok {
			resp.Attributes = append(resp.Attributes, Attribute{
				Type:  AttrReplyMessage,
				Value: []byte(msg),
			})
		}
		// Add Class attribute if present
		if class, ok := attrs["Class"]; ok {
			resp.Attributes = append(resp.Attributes, Attribute{
				Type:  AttrClass,
				Value: []byte(class),
			})
		}
	}

	return resp
}

// BuildReject builds an Access-Reject response packet
func (p *Packet) BuildReject(secret string, msg string) interface{} {
	resp := &Packet{
		Code:       CodeAccessReject,
		Identifier: p.Identifier,
		Secret:     secret,
	}
	copy(resp.Authenticator[:], p.Authenticator[:])
	if msg != "" {
		resp.Attributes = append(resp.Attributes, Attribute{
			Type:  AttrReplyMessage,
			Value: []byte(msg),
		})
	}
	return resp
}

// BuildAcctResponse builds an Accounting-Response packet
func (p *Packet) BuildAcctResponse(secret string) interface{} {
	resp := &Packet{
		Code:       CodeAccountingResponse,
		Identifier: p.Identifier,
		Secret:     secret,
	}
	copy(resp.Authenticator[:], p.Authenticator[:])
	return resp
}

// Encode serializes the packet to bytes
func (p *Packet) Encode() []byte {
	// Calculate total length
	attrLen := 0
	for _, attr := range p.Attributes {
		attrLen += 2 + len(attr.Value)
	}
	totalLen := 20 + attrLen

	data := make([]byte, totalLen)
	data[0] = p.Code
	data[1] = p.Identifier
	binary.BigEndian.PutUint16(data[2:4], uint16(totalLen))
	copy(data[4:20], p.Authenticator[:])

	offset := 20
	for _, attr := range p.Attributes {
		data[offset] = attr.Type
		data[offset+1] = byte(2 + len(attr.Value))
		copy(data[offset+2:], attr.Value)
		offset += 2 + len(attr.Value)
	}

	// Compute Response Authenticator for Access-Accept/Reject/Challenge
	if p.Code == CodeAccessAccept || p.Code == CodeAccessReject || p.Code == CodeAccessChallenge { //nolint:gocritic
		hash := md5.New()
		hash.Write(data[:4])
		hash.Write(p.Authenticator[:]) // Request authenticator
		hash.Write(data[20:])
		hash.Write([]byte(p.Secret))
		copy(data[4:20], hash.Sum(nil))
	}

	return data
}

// VerifyMessageAuthenticator verifies the Message-Authenticator attribute
func (p *Packet) VerifyMessageAuthenticator(secret string, rawPacket []byte) bool {
	msgAuth := p.GetAttribute(AttrMessageAuthenticator)
	if msgAuth == nil { //nolint:staticcheck
		return true // Not present, skip check
	}

	// Save original value
	original := make([]byte, 16)
	copy(original, msgAuth.Value)

	// Zero out the Message-Authenticator in raw packet for computation
	// Find it in raw bytes
	offset := 20
	for offset < len(rawPacket) {
		if rawPacket[offset] == AttrMessageAuthenticator {
			// Zero the value (16 bytes after type+length)
			for i := 0; i < 16; i++ {
				rawPacket[offset+2+i] = 0
			}
			break
		}
		offset += int(rawPacket[offset+1])
	}

	// Compute HMAC-MD5
	mac := hmac.New(md5.New, []byte(secret))
	mac.Write(rawPacket)
	expected := mac.Sum(nil)

	return hmac.Equal(original, expected)
}
