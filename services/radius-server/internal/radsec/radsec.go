package radsec

import (
	"context"
	"crypto/tls"
	"crypto/x509"
	"fmt"
	"io"
	"net"
	"os"
	"time"

	"github.com/neuranac/services/radius-server/internal/config"
	"github.com/neuranac/services/radius-server/internal/handler"
	"github.com/neuranac/services/radius-server/internal/radius"
	"go.uber.org/zap"
)

// ListenAndServe starts the RadSec (RADIUS over TLS) listener on TCP
func ListenAndServe(ctx context.Context, addr string, cfg *config.Config, h *handler.Handler, logger *zap.Logger) error {
	tlsCfg, err := buildTLSConfig(cfg)
	if err != nil {
		return fmt.Errorf("build TLS config: %w", err)
	}

	listener, err := tls.Listen("tcp", addr, tlsCfg)
	if err != nil {
		return fmt.Errorf("listen TLS: %w", err)
	}
	defer listener.Close()

	logger.Info("RadSec listener started", zap.String("addr", addr))

	go func() {
		<-ctx.Done()
		listener.Close()
	}()

	for {
		conn, err := listener.Accept()
		if err != nil {
			select {
			case <-ctx.Done():
				return nil
			default:
				logger.Error("Accept error", zap.Error(err))
				continue
			}
		}

		go handleRadSecConn(ctx, conn, cfg, h, logger)
	}
}

func handleRadSecConn(ctx context.Context, conn net.Conn, cfg *config.Config, h *handler.Handler, logger *zap.Logger) {
	defer conn.Close()

	tlsConn, ok := conn.(*tls.Conn)
	if !ok {
		logger.Error("Not a TLS connection")
		return
	}

	// Complete TLS handshake
	if err := tlsConn.Handshake(); err != nil {
		logger.Error("TLS handshake failed", zap.Error(err))
		return
	}

	state := tlsConn.ConnectionState()
	logger.Info("RadSec connection established",
		zap.String("remote", conn.RemoteAddr().String()),
		zap.String("tls_version", fmt.Sprintf("0x%04x", state.Version)),
		zap.Int("peer_certs", len(state.PeerCertificates)),
	)

	// Read RADIUS packets from TLS stream
	// RadSec: RADIUS packets are sent over TLS TCP stream
	// Each packet starts with Code(1) + ID(1) + Length(2) header
	buf := make([]byte, 4096)
	for {
		select {
		case <-ctx.Done():
			return
		default:
			conn.SetReadDeadline(time.Now().Add(300 * time.Second))

			// Read RADIUS header (4 bytes: code, id, length)
			_, err := io.ReadFull(conn, buf[:4])
			if err != nil {
				if err != io.EOF {
					logger.Error("RadSec read error", zap.Error(err))
				}
				return
			}

			// Get packet length
			pktLen := int(buf[2])<<8 | int(buf[3])
			if pktLen < 20 || pktLen > 4096 {
				logger.Warn("Invalid RadSec packet length", zap.Int("length", pktLen))
				return
			}

			// Read rest of packet
			_, err = io.ReadFull(conn, buf[4:pktLen])
			if err != nil {
				logger.Error("RadSec read body error", zap.Error(err))
				return
			}

			// Parse RADIUS packet
			pkt, err := radius.ParsePacket(buf[:pktLen])
			if err != nil {
				logger.Error("RadSec parse error", zap.Error(err))
				continue
			}

			// RadSec uses TLS for security; shared secret is configurable
			// via RADSEC_SECRET env var (default "radsec" per RFC 6614)
			pkt.Secret = cfg.RadSecSecret

			// Handle the packet
			resp, err := h.HandleRadius(ctx, pkt)
			if err != nil {
				logger.Error("RadSec handle error", zap.Error(err))
				continue
			}

			// Send response back over TLS
			if resp != nil {
				// Encode response and write to TLS connection
				// resp is a radius.Packet
				if respPkt, ok := resp.(*radius.Packet); ok {
					respBytes := respPkt.Encode()
					conn.Write(respBytes)
				}
			}
		}
	}
}

func buildTLSConfig(cfg *config.Config) (*tls.Config, error) {
	certFile := cfg.TLSCertPath + "/radsec.crt"
	keyFile := cfg.TLSCertPath + "/radsec.key"
	caFile := cfg.TLSCertPath + "/ca.crt"

	cert, err := tls.LoadX509KeyPair(certFile, keyFile)
	if err != nil {
		return nil, fmt.Errorf("load cert: %w", err)
	}

	caCert, err := os.ReadFile(caFile)
	if err != nil {
		return nil, fmt.Errorf("read CA cert: %w", err)
	}
	caPool := x509.NewCertPool()
	caPool.AppendCertsFromPEM(caCert)

	return &tls.Config{
		Certificates: []tls.Certificate{cert},
		ClientAuth:   tls.RequireAndVerifyClientCert,
		ClientCAs:    caPool,
		MinVersion:   tls.VersionTLS13,
	}, nil
}
