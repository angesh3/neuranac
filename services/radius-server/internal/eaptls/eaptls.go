package eaptls

import (
	"crypto/ecdsa"
	"crypto/elliptic"
	"crypto/rand"
	"crypto/tls"
	"crypto/x509"
	"crypto/x509/pkix"
	"encoding/binary"
	"fmt"
	"math/big"
	"net"
	"sync"
	"time"

	"go.uber.org/zap"
)

// TLSHandshaker manages real TLS handshakes for EAP-TLS/TTLS/PEAP.
// It uses Go's crypto/tls package to perform proper TLS 1.2/1.3 negotiation
// with real cipher suite selection, certificate exchange, and key derivation.
type TLSHandshaker struct {
	serverCert tls.Certificate
	caPool     *x509.CertPool
	logger     *zap.Logger
	sessions   sync.Map // sessionKey -> *TLSSession
}

// TLSSession tracks an in-progress TLS handshake using an in-memory pipe
type TLSSession struct {
	Conn       *tls.Conn
	serverPipe net.Conn // server-side of the pipe
	clientPipe net.Conn // "client-side" we feed EAP data into
	Done       bool
	PeerCert   *x509.Certificate
	mu         sync.Mutex
}

// NewHandshaker creates a TLS handshaker with server certificate and trusted CAs.
// If serverCert is nil, an ephemeral self-signed cert is generated for dev/testing.
func NewHandshaker(serverCert *tls.Certificate, caPool *x509.CertPool, logger *zap.Logger) (*TLSHandshaker, error) {
	h := &TLSHandshaker{
		caPool: caPool,
		logger: logger,
	}

	if serverCert != nil {
		h.serverCert = *serverCert
	} else {
		cert, err := generateEphemeralCert()
		if err != nil {
			return nil, fmt.Errorf("generate ephemeral cert: %w", err)
		}
		h.serverCert = cert
		logger.Warn("EAP-TLS: using ephemeral self-signed server certificate (dev mode)")
	}

	return h, nil
}

// StartHandshake begins a new TLS handshake session.
// Returns the initial ServerHello+Certificate+CertificateRequest+ServerHelloDone as TLS records.
func (h *TLSHandshaker) StartHandshake(sessionKey string, requireClientCert bool) ([]byte, error) {
	// Create an in-memory pipe to simulate the network connection
	clientConn, serverConn := net.Pipe()

	clientAuth := tls.NoClientCert
	if requireClientCert {
		clientAuth = tls.RequireAnyClientCert
		if h.caPool != nil {
			clientAuth = tls.RequireAndVerifyClientCert
		}
	}

	tlsCfg := &tls.Config{
		Certificates: []tls.Certificate{h.serverCert},
		ClientAuth:   clientAuth,
		ClientCAs:    h.caPool,
		MinVersion:   tls.VersionTLS12,
		MaxVersion:   tls.VersionTLS12, // EAP-TLS typically uses TLS 1.2
		CipherSuites: []uint16{
			tls.TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256,
			tls.TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384,
			tls.TLS_ECDHE_ECDSA_WITH_AES_128_GCM_SHA256,
			tls.TLS_ECDHE_ECDSA_WITH_AES_256_GCM_SHA384,
			tls.TLS_RSA_WITH_AES_128_GCM_SHA256,
			tls.TLS_RSA_WITH_AES_256_GCM_SHA384,
		},
	}

	tlsConn := tls.Server(serverConn, tlsCfg)

	session := &TLSSession{
		Conn:       tlsConn,
		serverPipe: serverConn,
		clientPipe: clientConn,
	}
	h.sessions.Store(sessionKey, session)

	// Start TLS handshake in background — it will block waiting for client data
	go func() {
		err := tlsConn.Handshake()
		session.mu.Lock()
		defer session.mu.Unlock()
		if err != nil {
			h.logger.Debug("TLS handshake completed with error", zap.Error(err))
		} else {
			session.Done = true
			state := tlsConn.ConnectionState()
			if len(state.PeerCertificates) > 0 {
				session.PeerCert = state.PeerCertificates[0]
			}
		}
	}()

	// The TLS server will write ServerHello+Certificate+etc to the pipe.
	// We need to give it a moment to produce its first flight of messages.
	// Read the server's initial TLS records from the client side of the pipe.
	time.Sleep(10 * time.Millisecond)
	return h.readFromPipe(clientConn, 100*time.Millisecond)
}

// ProcessClientData feeds client TLS data into the handshake and returns
// any server response records. Returns the peer certificate if handshake completes.
func (h *TLSHandshaker) ProcessClientData(sessionKey string, clientData []byte) (serverResponse []byte, peerCert *x509.Certificate, handshakeDone bool, err error) {
	val, ok := h.sessions.Load(sessionKey)
	if !ok {
		return nil, nil, false, fmt.Errorf("session not found: %s", sessionKey)
	}
	session := val.(*TLSSession)

	// Write client TLS records into the pipe (simulating network delivery)
	session.clientPipe.SetWriteDeadline(time.Now().Add(1 * time.Second))
	_, err = session.clientPipe.Write(clientData)
	if err != nil {
		return nil, nil, false, fmt.Errorf("write client data: %w", err)
	}

	// Wait a moment for the TLS state machine to process and produce response
	time.Sleep(10 * time.Millisecond)

	// Read any server response
	serverResponse, _ = h.readFromPipe(session.clientPipe, 100*time.Millisecond)

	// Check if handshake completed
	session.mu.Lock()
	done := session.Done
	cert := session.PeerCert
	session.mu.Unlock()

	if done {
		return serverResponse, cert, true, nil
	}

	return serverResponse, nil, false, nil
}

// CleanupSession removes a handshake session and closes pipes
func (h *TLSHandshaker) CleanupSession(sessionKey string) {
	val, ok := h.sessions.LoadAndDelete(sessionKey)
	if !ok {
		return
	}
	session := val.(*TLSSession)
	session.clientPipe.Close()
	session.serverPipe.Close()
}

// readFromPipe reads available data from the pipe with a timeout
func (h *TLSHandshaker) readFromPipe(conn net.Conn, timeout time.Duration) ([]byte, error) {
	buf := make([]byte, 16384) // TLS records can be up to 16KB
	conn.SetReadDeadline(time.Now().Add(timeout))
	var result []byte
	for {
		n, err := conn.Read(buf)
		if n > 0 {
			result = append(result, buf[:n]...)
		}
		if err != nil {
			break
		}
	}
	return result, nil
}

// BuildEAPTLSMessage wraps TLS records in an EAP-TLS message with proper framing.
// eapType: 13=EAP-TLS, 21=EAP-TTLS, 25=PEAP
func BuildEAPTLSMessage(eapID byte, eapType byte, tlsData []byte, isStart bool) []byte {
	flags := byte(0)
	if isStart {
		flags |= 0x20 // Start flag
	}

	hasLength := len(tlsData) > 0 && isStart
	if hasLength {
		flags |= 0x80 // Length included flag
	}

	// EAP header: Code(1) + ID(1) + Length(2) + Type(1) + Flags(1) [+ TLSLength(4)] + Data
	headerLen := 6
	if hasLength {
		headerLen = 10
	}
	totalLen := headerLen + len(tlsData)

	pkt := make([]byte, totalLen)
	pkt[0] = 1 // EAP-Request
	pkt[1] = eapID
	binary.BigEndian.PutUint16(pkt[2:4], uint16(totalLen))
	pkt[4] = eapType
	pkt[5] = flags

	offset := 6
	if hasLength {
		binary.BigEndian.PutUint32(pkt[6:10], uint32(len(tlsData)))
		offset = 10
	}

	copy(pkt[offset:], tlsData)
	return pkt
}

// ExtractTLSPayload extracts the TLS record data from an EAP-TLS message
func ExtractTLSPayload(eapMsg []byte) []byte {
	if len(eapMsg) < 6 {
		return nil
	}
	flags := eapMsg[5]
	offset := 6
	if flags&0x80 != 0 && len(eapMsg) >= 10 {
		// 4-byte TLS message length field present
		offset = 10
	}
	if offset >= len(eapMsg) {
		return nil
	}
	return eapMsg[offset:]
}

// generateEphemeralCert creates a self-signed ECDSA certificate for dev/testing
func generateEphemeralCert() (tls.Certificate, error) {
	key, err := ecdsa.GenerateKey(elliptic.P256(), rand.Reader)
	if err != nil {
		return tls.Certificate{}, err
	}

	template := &x509.Certificate{
		SerialNumber: big.NewInt(1),
		Subject: pkix.Name{
			Organization: []string{"NeuraNAC RADIUS Server"},
			CommonName:   "neuranac-radius-eaptls",
		},
		NotBefore:             time.Now().Add(-1 * time.Hour),
		NotAfter:              time.Now().Add(365 * 24 * time.Hour),
		KeyUsage:              x509.KeyUsageDigitalSignature | x509.KeyUsageKeyEncipherment,
		ExtKeyUsage:           []x509.ExtKeyUsage{x509.ExtKeyUsageServerAuth},
		BasicConstraintsValid: true,
	}

	certDER, err := x509.CreateCertificate(rand.Reader, template, template, &key.PublicKey, key)
	if err != nil {
		return tls.Certificate{}, err
	}

	return tls.Certificate{
		Certificate: [][]byte{certDER},
		PrivateKey:  key,
	}, nil
}
