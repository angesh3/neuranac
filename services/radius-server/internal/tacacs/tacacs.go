package tacacs

import (
	"context"
	"crypto/md5"
	"encoding/binary"
	"fmt"
	"io"
	"net"
	"time"

	"github.com/neuranac/services/radius-server/internal/config"
	"github.com/neuranac/services/radius-server/internal/handler"
	"go.uber.org/zap"
	"golang.org/x/crypto/bcrypt"
)

// TACACS+ Header constants
const (
	TACACSMajorVersion = 0xC0
	TACACSMinorVersion = 0x01

	TypeAuthentication = 0x01
	TypeAuthorization  = 0x02
	TypeAccounting     = 0x03

	FlagSingleConnect = 0x04
	FlagUnencrypted   = 0x01
)

// Header represents a TACACS+ packet header (12 bytes)
type Header struct {
	Version   byte
	Type      byte
	SeqNo     byte
	Flags     byte
	SessionID uint32
	Length    uint32
}

// ListenAndServe starts the TACACS+ TCP listener
func ListenAndServe(ctx context.Context, addr string, cfg *config.Config, h *handler.Handler, logger *zap.Logger) error {
	listener, err := net.Listen("tcp", addr)
	if err != nil {
		return fmt.Errorf("listen tcp: %w", err)
	}
	defer listener.Close()

	logger.Info("TACACS+ listener started", zap.String("addr", addr))

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
				logger.Error("TACACS+ accept error", zap.Error(err))
				continue
			}
		}

		go handleConnection(ctx, conn, cfg, h, logger)
	}
}

func handleConnection(ctx context.Context, conn net.Conn, cfg *config.Config, h *handler.Handler, logger *zap.Logger) {
	defer conn.Close()
	remoteAddr := conn.RemoteAddr().String()
	logger.Info("TACACS+ connection", zap.String("remote", remoteAddr))

	for {
		select {
		case <-ctx.Done():
			return
		default:
			conn.SetReadDeadline(time.Now().Add(300 * time.Second))

			// Read 12-byte header
			headerBuf := make([]byte, 12)
			_, err := io.ReadFull(conn, headerBuf)
			if err != nil {
				if err != io.EOF {
					logger.Debug("TACACS+ read header error", zap.Error(err))
				}
				return
			}

			hdr := parseHeader(headerBuf)
			if hdr.Length > 65535 {
				logger.Warn("TACACS+ invalid body length", zap.Uint32("length", hdr.Length))
				return
			}

			// Read body
			body := make([]byte, hdr.Length)
			if hdr.Length > 0 {
				_, err = io.ReadFull(conn, body)
				if err != nil {
					logger.Error("TACACS+ read body error", zap.Error(err))
					return
				}
			}

			// Decrypt body if encrypted
			if hdr.Flags&FlagUnencrypted == 0 {
				// Look up shared secret for this NAS IP
				nasIP := conn.RemoteAddr().(*net.TCPAddr).IP.String()
				nad, err := h.GetNADByIP(ctx, nasIP)
				if err != nil {
					logger.Warn("TACACS+ unknown NAS", zap.String("nas_ip", nasIP))
					return
				}
				body = decryptBody(hdr, body, nad.SharedSecret)
			}

			// Handle by type
			var resp []byte
			switch hdr.Type {
			case TypeAuthentication:
				resp = handleAuthentication(ctx, hdr, body, h, logger)
			case TypeAuthorization:
				resp = handleAuthorization(ctx, hdr, body, h, logger)
			case TypeAccounting:
				resp = handleAccounting(ctx, hdr, body, h, logger)
			default:
				logger.Warn("TACACS+ unknown type", zap.Int("type", int(hdr.Type)))
				return
			}

			if resp != nil {
				conn.Write(resp)
			}
		}
	}
}

func parseHeader(data []byte) *Header {
	return &Header{
		Version:   data[0],
		Type:      data[1],
		SeqNo:     data[2],
		Flags:     data[3],
		SessionID: binary.BigEndian.Uint32(data[4:8]),
		Length:    binary.BigEndian.Uint32(data[8:12]),
	}
}

func decryptBody(hdr *Header, body []byte, secret string) []byte {
	// TACACS+ encryption: XOR body with pseudo-pad generated from
	// MD5(session_id + secret + version + seq_no + previous_hash)
	decrypted := make([]byte, len(body))
	copy(decrypted, body)

	sessionBytes := make([]byte, 4)
	binary.BigEndian.PutUint32(sessionBytes, hdr.SessionID)

	padInput := append(sessionBytes, []byte(secret)...)
	padInput = append(padInput, hdr.Version, hdr.SeqNo)

	pad := md5.Sum(padInput)
	padSlice := pad[:]

	for i := 0; i < len(decrypted); i++ {
		if i > 0 && i%16 == 0 {
			// Generate next block of pad
			h := md5.New()
			h.Write(sessionBytes)
			h.Write([]byte(secret))
			h.Write([]byte{hdr.Version, hdr.SeqNo})
			h.Write(padSlice[len(padSlice)-16:])
			newPad := h.Sum(nil)
			padSlice = append(padSlice, newPad...)
		}
		decrypted[i] ^= padSlice[i]
	}

	return decrypted
}

// TACACS+ Reply status codes
const (
	AuthenStatusPass    = 0x01
	AuthenStatusFail    = 0x02
	AuthenStatusGetUser = 0x03
	AuthenStatusGetPass = 0x04
	AuthenStatusGetData = 0x05
	AuthenStatusError   = 0x07
	AuthenStatusRestart = 0x08

	AuthorStatusPassAdd  = 0x01
	AuthorStatusPassRepl = 0x02
	AuthorStatusFail     = 0x10
	AuthorStatusError    = 0x11

	AcctStatusSuccess = 0x01
	AcctStatusError   = 0x02
)

func handleAuthentication(ctx context.Context, hdr *Header, body []byte, h *handler.Handler, logger *zap.Logger) []byte {
	logger.Info("TACACS+ authentication request", zap.Uint32("session", hdr.SessionID))

	// Parse authentication START body
	// Byte layout: action(1) + priv_lvl(1) + authen_type(1) + service(1) +
	//              user_len(1) + port_len(1) + rem_addr_len(1) + data_len(1) +
	//              user + port + rem_addr + data
	if len(body) < 8 {
		return buildAuthenReply(hdr, AuthenStatusError, "Malformed packet")
	}

	userLen := int(body[4])
	portLen := int(body[5])
	remLen := int(body[6])
	dataLen := int(body[7])

	offset := 8
	username := ""
	if userLen > 0 && offset+userLen <= len(body) {
		username = string(body[offset : offset+userLen])
		offset += userLen
	}

	port := ""
	if portLen > 0 && offset+portLen <= len(body) {
		port = string(body[offset : offset+portLen])
		offset += portLen
	}

	_ = remLen // skip remote addr
	offset += remLen

	password := ""
	if dataLen > 0 && offset+dataLen <= len(body) {
		password = string(body[offset : offset+dataLen])
	}

	logger.Info("TACACS+ authen",
		zap.String("user", username),
		zap.String("port", port),
	)

	// If no username provided, request it
	if username == "" {
		return buildAuthenReply(hdr, AuthenStatusGetUser, "Username: ")
	}

	// If no password provided, request it
	if password == "" {
		return buildAuthenReply(hdr, AuthenStatusGetPass, "Password: ")
	}

	// Look up user and verify credentials
	user, err := h.GetUserByUsername(ctx, "", username)
	if err != nil {
		logger.Warn("TACACS+ user not found", zap.String("user", username))
		return buildAuthenReply(hdr, AuthenStatusFail, "Authentication failed")
	}

	// Verify password using bcrypt
	if err := bcrypt.CompareHashAndPassword([]byte(user.PasswordHash), []byte(password)); err != nil {
		logger.Warn("TACACS+ password mismatch", zap.String("user", username))
		return buildAuthenReply(hdr, AuthenStatusFail, "Authentication failed")
	}

	logger.Info("TACACS+ authentication successful", zap.String("user", username))
	return buildAuthenReply(hdr, AuthenStatusPass, "")
}

func handleAuthorization(ctx context.Context, hdr *Header, body []byte, h *handler.Handler, logger *zap.Logger) []byte {
	logger.Info("TACACS+ authorization request", zap.Uint32("session", hdr.SessionID))

	// Parse AUTHOR REQUEST body
	// authen_method(1) + priv_lvl(1) + authen_type(1) + authen_service(1) +
	// user_len(1) + port_len(1) + rem_addr_len(1) + arg_cnt(1) +
	// arg_len[arg_cnt] + user + port + rem_addr + args...
	if len(body) < 8 {
		return buildAuthorReply(hdr, AuthorStatusError, nil, "Malformed packet")
	}

	privLvl := int(body[1])
	userLen := int(body[4])
	argCnt := int(body[7])

	offset := 8

	// Read arg lengths
	argLens := make([]int, argCnt)
	for i := 0; i < argCnt && offset < len(body); i++ {
		argLens[i] = int(body[offset])
		offset++
	}

	// Read user
	username := ""
	if userLen > 0 && offset+userLen <= len(body) {
		username = string(body[offset : offset+userLen])
	}

	logger.Info("TACACS+ authorization",
		zap.String("user", username),
		zap.Int("priv_lvl", privLvl),
		zap.Int("args", argCnt),
	)

	// Evaluate authorization policy via the policy engine (gRPC with circuit breaker)
	// Falls back to default permit if policy engine is unavailable
	result := h.EvaluateTACACSPolicy(ctx, "", username, privLvl)
	if !result.Permitted {
		logger.Warn("TACACS+ authorization denied by policy",
			zap.String("user", username),
			zap.Int("priv_lvl", privLvl),
		)
		return buildAuthorReply(hdr, AuthorStatusFail, nil, "Authorization denied by policy")
	}

	return buildAuthorReply(hdr, AuthorStatusPassAdd, result.Args, "")
}

func handleAccounting(ctx context.Context, hdr *Header, body []byte, h *handler.Handler, logger *zap.Logger) []byte {
	logger.Info("TACACS+ accounting request", zap.Uint32("session", hdr.SessionID))

	// Parse ACCT REQUEST body
	// flags(1) + authen_method(1) + priv_lvl(1) + authen_type(1) +
	// authen_service(1) + user_len(1) + port_len(1) + rem_addr_len(1) +
	// arg_cnt(1) + arg_len[arg_cnt] + user + port + rem_addr + args
	if len(body) < 9 {
		return buildAcctReply(hdr, AcctStatusError, "Malformed packet")
	}

	flags := body[0]
	userLen := int(body[5])
	offset := 9 + int(body[8]) // skip arg_cnt arg_lens

	username := ""
	if userLen > 0 && offset+userLen <= len(body) {
		username = string(body[offset : offset+userLen])
	}

	flagStr := "unknown"
	switch {
	case flags&0x02 != 0:
		flagStr = "start"
	case flags&0x04 != 0:
		flagStr = "stop"
	case flags&0x08 != 0:
		flagStr = "watchdog"
	}

	logger.Info("TACACS+ accounting",
		zap.String("user", username),
		zap.String("flag", flagStr),
	)

	return buildAcctReply(hdr, AcctStatusSuccess, "")
}

func buildAuthenReply(hdr *Header, status byte, serverMsg string) []byte {
	// REPLY: status(1) + flags(1) + server_msg_len(2) + data_len(2) + server_msg + data
	msgBytes := []byte(serverMsg)
	bodyLen := 6 + len(msgBytes)
	replyBody := make([]byte, bodyLen)
	replyBody[0] = status
	replyBody[1] = 0 // flags
	binary.BigEndian.PutUint16(replyBody[2:4], uint16(len(msgBytes)))
	binary.BigEndian.PutUint16(replyBody[4:6], 0) // data_len
	copy(replyBody[6:], msgBytes)

	return buildTACACSPacket(hdr, replyBody)
}

func buildAuthorReply(hdr *Header, status byte, args []string, serverMsg string) []byte {
	msgBytes := []byte(serverMsg)
	argCnt := len(args)

	// Calculate total arg bytes
	totalArgBytes := 0
	for _, a := range args {
		totalArgBytes += len(a)
	}

	// REPLY: status(1) + arg_cnt(1) + server_msg_len(2) + data_len(2) + arg_len[n] + server_msg + data + args
	bodyLen := 6 + argCnt + len(msgBytes) + totalArgBytes
	replyBody := make([]byte, bodyLen)
	replyBody[0] = status
	replyBody[1] = byte(argCnt)
	binary.BigEndian.PutUint16(replyBody[2:4], uint16(len(msgBytes)))
	binary.BigEndian.PutUint16(replyBody[4:6], 0)

	offset := 6
	for _, a := range args {
		replyBody[offset] = byte(len(a))
		offset++
	}
	copy(replyBody[offset:], msgBytes)
	offset += len(msgBytes)
	for _, a := range args {
		copy(replyBody[offset:], []byte(a))
		offset += len(a)
	}

	return buildTACACSPacket(hdr, replyBody)
}

func buildAcctReply(hdr *Header, status byte, serverMsg string) []byte {
	msgBytes := []byte(serverMsg)
	// REPLY: server_msg_len(2) + data_len(2) + status(1) + server_msg + data
	bodyLen := 5 + len(msgBytes)
	replyBody := make([]byte, bodyLen)
	binary.BigEndian.PutUint16(replyBody[0:2], uint16(len(msgBytes)))
	binary.BigEndian.PutUint16(replyBody[2:4], 0)
	replyBody[4] = status
	copy(replyBody[5:], msgBytes)

	return buildTACACSPacket(hdr, replyBody)
}

func buildTACACSPacket(reqHdr *Header, body []byte) []byte {
	// Build 12-byte header + body
	pkt := make([]byte, 12+len(body))
	pkt[0] = reqHdr.Version
	pkt[1] = reqHdr.Type
	pkt[2] = reqHdr.SeqNo + 1 // Response seq = request seq + 1
	pkt[3] = reqHdr.Flags
	binary.BigEndian.PutUint32(pkt[4:8], reqHdr.SessionID)
	binary.BigEndian.PutUint32(pkt[8:12], uint32(len(body)))
	copy(pkt[12:], body)
	return pkt
}
