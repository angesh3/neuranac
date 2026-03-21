// RADIUS Protocol Load Test
//
// Sends concurrent RADIUS Access-Request packets (PAP + MAB) to the NeuraNAC
// RADIUS server over UDP and measures latency, throughput, and error rate.
//
// Usage:
//   go run tests/load/radius_load_test.go \
//     -addr 127.0.0.1:1812 -secret testing123 \
//     -users 50 -duration 60s -rps 200
//
// Environment:
//   RADIUS_ADDR      (default 127.0.0.1:1812)
//   RADIUS_SECRET    (default testing123)
//   LOAD_USERS       (default 50)
//   LOAD_DURATION    (default 60s)
//   LOAD_RPS         (default 200)
package main

import (
	"crypto/md5"
	"encoding/binary"
	"flag"
	"fmt"
	"math"
	"math/rand"
	"net"
	"os"
	"sort"
	"strconv"
	"sync"
	"sync/atomic"
	"time"
)

// RADIUS packet codes
const (
	CodeAccessRequest  = 1
	CodeAccessAccept   = 2
	CodeAccessReject   = 3
	CodeAccessChallenge = 11
)

// RADIUS attribute types
const (
	AttrUserName     = 1
	AttrUserPassword = 2
	AttrNASIPAddress = 4
	AttrNASPort      = 5
	AttrServiceType  = 6
	AttrCallingStationID = 31
	AttrNASPortType  = 61
)

type Config struct {
	Addr     string
	Secret   string
	Users    int
	Duration time.Duration
	RPS      int
}

type Stats struct {
	Sent      int64
	Received  int64
	Accepts   int64
	Rejects   int64
	Challenges int64
	Timeouts  int64
	Errors    int64
	Latencies []float64
	mu        sync.Mutex
}

func (s *Stats) RecordLatency(ms float64) {
	s.mu.Lock()
	s.Latencies = append(s.Latencies, ms)
	s.mu.Unlock()
}

func (s *Stats) Report() {
	sort.Float64s(s.Latencies)
	n := len(s.Latencies)

	fmt.Println("\n══════════════════════════════════════════════════")
	fmt.Println("  NeuraNAC RADIUS Load Test Results")
	fmt.Println("══════════════════════════════════════════════════")
	fmt.Printf("  Packets sent:       %d\n", atomic.LoadInt64(&s.Sent))
	fmt.Printf("  Responses received: %d\n", atomic.LoadInt64(&s.Received))
	fmt.Printf("  Access-Accept:      %d\n", atomic.LoadInt64(&s.Accepts))
	fmt.Printf("  Access-Reject:      %d\n", atomic.LoadInt64(&s.Rejects))
	fmt.Printf("  Access-Challenge:   %d\n", atomic.LoadInt64(&s.Challenges))
	fmt.Printf("  Timeouts:           %d\n", atomic.LoadInt64(&s.Timeouts))
	fmt.Printf("  Errors:             %d\n", atomic.LoadInt64(&s.Errors))

	if n > 0 {
		sum := 0.0
		for _, v := range s.Latencies {
			sum += v
		}
		avg := sum / float64(n)
		p50 := s.Latencies[n*50/100]
		p95 := s.Latencies[n*95/100]
		p99 := s.Latencies[int(math.Min(float64(n*99/100), float64(n-1)))]
		fmt.Println("──────────────────────────────────────────────────")
		fmt.Printf("  Avg latency:  %.2f ms\n", avg)
		fmt.Printf("  p50 latency:  %.2f ms\n", p50)
		fmt.Printf("  p95 latency:  %.2f ms\n", p95)
		fmt.Printf("  p99 latency:  %.2f ms\n", p99)
		fmt.Printf("  Min latency:  %.2f ms\n", s.Latencies[0])
		fmt.Printf("  Max latency:  %.2f ms\n", s.Latencies[n-1])
	}

	total := atomic.LoadInt64(&s.Sent)
	errRate := float64(atomic.LoadInt64(&s.Timeouts)+atomic.LoadInt64(&s.Errors)) / math.Max(float64(total), 1) * 100
	fmt.Println("──────────────────────────────────────────────────")
	fmt.Printf("  Error rate:   %.2f%%\n", errRate)

	// Pass/fail thresholds
	pass := true
	if n > 0 {
		p95 := s.Latencies[n*95/100]
		if p95 > 1000 {
			fmt.Println("  ✗ FAIL: p95 latency > 1000ms")
			pass = false
		}
	}
	if errRate > 5 {
		fmt.Println("  ✗ FAIL: error rate > 5%")
		pass = false
	}
	if pass {
		fmt.Println("  ✓ PASS: All thresholds met")
	}
	fmt.Println("══════════════════════════════════════════════════")
}

// buildPAPRequest builds a RADIUS Access-Request with PAP authentication.
func buildPAPRequest(id byte, username, password, secret string, authenticator [16]byte) []byte {
	// Encode password per RFC 2865 §5.2
	encPass := papEncrypt([]byte(password), []byte(secret), authenticator[:])

	attrs := []byte{}
	attrs = appendAttr(attrs, AttrUserName, []byte(username))
	attrs = appendAttr(attrs, AttrUserPassword, encPass)
	attrs = appendAttr(attrs, AttrNASIPAddress, net.ParseIP("10.0.0.1").To4())
	attrs = appendAttr(attrs, AttrNASPort, uint32ToBytes(1))
	attrs = appendAttr(attrs, AttrServiceType, uint32ToBytes(2)) // Framed
	attrs = appendAttr(attrs, AttrNASPortType, uint32ToBytes(15)) // Ethernet

	pkt := make([]byte, 20+len(attrs))
	pkt[0] = CodeAccessRequest
	pkt[1] = id
	binary.BigEndian.PutUint16(pkt[2:4], uint16(len(pkt)))
	copy(pkt[4:20], authenticator[:])
	copy(pkt[20:], attrs)
	return pkt
}

// buildMABRequest builds a RADIUS Access-Request for MAC Authentication Bypass.
func buildMABRequest(id byte, mac, secret string, authenticator [16]byte) []byte {
	attrs := []byte{}
	attrs = appendAttr(attrs, AttrUserName, []byte(mac))
	attrs = appendAttr(attrs, AttrCallingStationID, []byte(mac))
	attrs = appendAttr(attrs, AttrNASIPAddress, net.ParseIP("10.0.0.1").To4())
	attrs = appendAttr(attrs, AttrNASPort, uint32ToBytes(1))
	attrs = appendAttr(attrs, AttrServiceType, uint32ToBytes(10)) // Call-Check
	attrs = appendAttr(attrs, AttrNASPortType, uint32ToBytes(15))

	pkt := make([]byte, 20+len(attrs))
	pkt[0] = CodeAccessRequest
	pkt[1] = id
	binary.BigEndian.PutUint16(pkt[2:4], uint16(len(pkt)))
	copy(pkt[4:20], authenticator[:])
	copy(pkt[20:], attrs)
	return pkt
}

func appendAttr(buf []byte, attrType byte, value []byte) []byte {
	buf = append(buf, attrType, byte(2+len(value)))
	buf = append(buf, value...)
	return buf
}

func uint32ToBytes(v uint32) []byte {
	b := make([]byte, 4)
	binary.BigEndian.PutUint32(b, v)
	return b
}

func papEncrypt(password, secret, authenticator []byte) []byte {
	// Pad password to multiple of 16
	padded := make([]byte, ((len(password)/16)+1)*16)
	copy(padded, password)

	result := make([]byte, len(padded))
	prev := authenticator
	for i := 0; i < len(padded); i += 16 {
		h := md5.New()
		h.Write(secret)
		h.Write(prev)
		hash := h.Sum(nil)
		for j := 0; j < 16; j++ {
			result[i+j] = padded[i+j] ^ hash[j]
		}
		prev = result[i : i+16]
	}
	return result
}

func randomMAC() string {
	return fmt.Sprintf("AA:BB:CC:%02X:%02X:%02X", rand.Intn(256), rand.Intn(256), rand.Intn(256))
}

func worker(cfg Config, stats *Stats, wg *sync.WaitGroup, stop <-chan struct{}, rateLimit <-chan time.Time) {
	defer wg.Done()

	conn, err := net.Dial("udp", cfg.Addr)
	if err != nil {
		fmt.Fprintf(os.Stderr, "dial error: %v\n", err)
		atomic.AddInt64(&stats.Errors, 1)
		return
	}
	defer conn.Close()

	buf := make([]byte, 4096)
	var id byte

	for {
		select {
		case <-stop:
			return
		case <-rateLimit:
		}

		id++
		var authenticator [16]byte
		rand.Read(authenticator[:])

		var pkt []byte
		if rand.Float32() < 0.7 {
			// 70% PAP auth
			user := fmt.Sprintf("loadtest_user_%d", rand.Intn(cfg.Users))
			pkt = buildPAPRequest(id, user, "LoadTestPass123!", cfg.Secret, authenticator)
		} else {
			// 30% MAB
			mac := randomMAC()
			pkt = buildMABRequest(id, mac, cfg.Secret, authenticator)
		}

		start := time.Now()
		atomic.AddInt64(&stats.Sent, 1)

		conn.SetWriteDeadline(time.Now().Add(2 * time.Second))
		_, err := conn.Write(pkt)
		if err != nil {
			atomic.AddInt64(&stats.Errors, 1)
			continue
		}

		conn.SetReadDeadline(time.Now().Add(3 * time.Second))
		n, err := conn.Read(buf)
		elapsed := time.Since(start).Seconds() * 1000

		if err != nil {
			if netErr, ok := err.(net.Error); ok && netErr.Timeout() {
				atomic.AddInt64(&stats.Timeouts, 1)
			} else {
				atomic.AddInt64(&stats.Errors, 1)
			}
			continue
		}

		if n < 20 {
			atomic.AddInt64(&stats.Errors, 1)
			continue
		}

		atomic.AddInt64(&stats.Received, 1)
		stats.RecordLatency(elapsed)

		code := buf[0]
		switch code {
		case CodeAccessAccept:
			atomic.AddInt64(&stats.Accepts, 1)
		case CodeAccessReject:
			atomic.AddInt64(&stats.Rejects, 1)
		case CodeAccessChallenge:
			atomic.AddInt64(&stats.Challenges, 1)
		}
	}
}

func main() {
	addr := flag.String("addr", envOrDefault("RADIUS_ADDR", "127.0.0.1:1812"), "RADIUS server address")
	secret := flag.String("secret", envOrDefault("RADIUS_SECRET", "testing123"), "RADIUS shared secret")
	users := flag.Int("users", envOrDefaultInt("LOAD_USERS", 50), "Number of concurrent users")
	duration := flag.Duration("duration", envOrDefaultDuration("LOAD_DURATION", 60*time.Second), "Test duration")
	rps := flag.Int("rps", envOrDefaultInt("LOAD_RPS", 200), "Target requests per second")
	flag.Parse()

	cfg := Config{
		Addr:     *addr,
		Secret:   *secret,
		Users:    *users,
		Duration: *duration,
		RPS:      *rps,
	}

	fmt.Println("══════════════════════════════════════════════════")
	fmt.Println("  NeuraNAC RADIUS Protocol Load Test")
	fmt.Println("══════════════════════════════════════════════════")
	fmt.Printf("  Target:     %s\n", cfg.Addr)
	fmt.Printf("  Users:      %d\n", cfg.Users)
	fmt.Printf("  Duration:   %s\n", cfg.Duration)
	fmt.Printf("  Target RPS: %d\n", cfg.RPS)
	fmt.Println("──────────────────────────────────────────────────")

	stats := &Stats{}
	stop := make(chan struct{})
	var wg sync.WaitGroup

	// Rate limiter: emit tokens at target RPS
	interval := time.Second / time.Duration(cfg.RPS)
	rateCh := make(chan time.Time, cfg.RPS)
	go func() {
		ticker := time.NewTicker(interval)
		defer ticker.Stop()
		for {
			select {
			case <-stop:
				return
			case t := <-ticker.C:
				select {
				case rateCh <- t:
				default: // drop if workers can't keep up
				}
			}
		}
	}()

	// Start workers
	for i := 0; i < cfg.Users; i++ {
		wg.Add(1)
		go worker(cfg, stats, &wg, stop, rateCh)
	}

	// Progress reporter
	go func() {
		ticker := time.NewTicker(5 * time.Second)
		defer ticker.Stop()
		for {
			select {
			case <-stop:
				return
			case <-ticker.C:
				sent := atomic.LoadInt64(&stats.Sent)
				recv := atomic.LoadInt64(&stats.Received)
				to := atomic.LoadInt64(&stats.Timeouts)
				fmt.Printf("  [progress] sent=%d recv=%d timeouts=%d\n", sent, recv, to)
			}
		}
	}()

	// Run for duration
	time.Sleep(cfg.Duration)
	close(stop)
	wg.Wait()

	stats.Report()
}

func envOrDefault(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}

func envOrDefaultInt(key string, fallback int) int {
	if v := os.Getenv(key); v != "" {
		if i, err := strconv.Atoi(v); err == nil {
			return i
		}
	}
	return fallback
}

func envOrDefaultDuration(key string, fallback time.Duration) time.Duration {
	if v := os.Getenv(key); v != "" {
		if d, err := time.ParseDuration(v); err == nil {
			return d
		}
	}
	return fallback
}
