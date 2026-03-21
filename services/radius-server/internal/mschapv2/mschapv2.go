package mschapv2

import (
	"crypto/des"
	"crypto/rand"
	"crypto/sha1"
	"encoding/binary"
	"fmt"
	"hash"
	"math/bits"

	"golang.org/x/text/encoding/unicode"
)

// Challenge represents an MSCHAPv2 challenge
type Challenge struct {
	AuthChallenge [16]byte
	PeerChallenge [16]byte
	Username      string
}

// Response represents an MSCHAPv2 response from the peer
type Response struct {
	PeerChallenge [16]byte
	Reserved      [8]byte
	NTResponse    [24]byte
	Flags         byte
	Username      string
}

// SuccessResponse represents the authenticator's success response
type SuccessResponse struct {
	AuthResponse string // "S=<hex>" string
}

// GenerateAuthChallenge creates a random 16-byte authenticator challenge
func GenerateAuthChallenge() ([16]byte, error) {
	var challenge [16]byte
	_, err := rand.Read(challenge[:])
	return challenge, err
}

// ParseResponse parses an MSCHAPv2 response packet (49 bytes + username)
// Format: ident(1) + flags(1) + peer_challenge(16) + reserved(8) + nt_response(24) + flags(1)
func ParseResponse(data []byte) (*Response, error) {
	if len(data) < 50 {
		return nil, fmt.Errorf("MSCHAPv2 response too short: %d bytes", len(data))
	}

	resp := &Response{}
	// Skip ident byte (data[0]) and flags byte (data[1])
	copy(resp.PeerChallenge[:], data[2:18])
	copy(resp.Reserved[:], data[18:26])
	copy(resp.NTResponse[:], data[26:50])
	if len(data) > 50 {
		resp.Flags = data[50]
	}

	return resp, nil
}

// Verify checks the MSCHAPv2 NT-Response against the user's password.
// Returns the authenticator response string ("S=<hex>") on success.
func Verify(authChallenge [16]byte, resp *Response, password string) (string, error) {
	// Step 1: Convert password to UTF-16LE (NT Hash input)
	ntHash, err := NTPasswordHash(password)
	if err != nil {
		return "", fmt.Errorf("NT hash: %w", err)
	}

	// Step 2: Generate expected NT-Response
	expectedNTResponse := GenerateNTResponse(authChallenge, resp.PeerChallenge, resp.Username, ntHash)

	// Step 3: Compare
	if !compareBytes(expectedNTResponse[:], resp.NTResponse[:]) {
		return "", fmt.Errorf("NT-Response mismatch")
	}

	// Step 4: Generate authenticator response for success message
	authResp := GenerateAuthenticatorResponse(password, resp.NTResponse, resp.PeerChallenge, authChallenge, resp.Username)

	return authResp, nil
}

// NTPasswordHash computes the MD4 hash of the UTF-16LE encoded password (NT Hash)
func NTPasswordHash(password string) ([16]byte, error) {
	var result [16]byte

	// Encode password as UTF-16LE
	encoder := unicode.UTF16(unicode.LittleEndian, unicode.IgnoreBOM).NewEncoder()
	utf16Pass, err := encoder.Bytes([]byte(password))
	if err != nil {
		return result, fmt.Errorf("UTF-16LE encode: %w", err)
	}

	// MD4 hash (inline implementation — golang.org/x/crypto/md4 is deprecated)
	h := newMD4()
	h.Write(utf16Pass)
	copy(result[:], h.Sum(nil))
	return result, nil
}

// HashNTPasswordHash computes MD4(NTPasswordHash) — the "hash of hash"
func HashNTPasswordHash(ntHash [16]byte) [16]byte {
	var result [16]byte
	h := newMD4()
	h.Write(ntHash[:])
	copy(result[:], h.Sum(nil))
	return result
}

// ChallengeHash computes SHA1(PeerChallenge + AuthChallenge + Username)[0:8]
func ChallengeHash(peerChallenge, authChallenge [16]byte, username string) [8]byte {
	var result [8]byte
	h := sha1.New()
	h.Write(peerChallenge[:])
	h.Write(authChallenge[:])
	h.Write([]byte(username))
	digest := h.Sum(nil)
	copy(result[:], digest[:8])
	return result
}

// GenerateNTResponse computes the 24-byte NT-Response per RFC 2759
func GenerateNTResponse(authChallenge, peerChallenge [16]byte, username string, ntHash [16]byte) [24]byte {
	challengeHash := ChallengeHash(peerChallenge, authChallenge, username)
	return ChallengeResponse(challengeHash, ntHash)
}

// ChallengeResponse computes DES encryption of the challenge using NT hash as key material
func ChallengeResponse(challenge [8]byte, ntHash [16]byte) [24]byte {
	var result [24]byte

	// Split 16-byte hash into three 7-byte DES keys (with zero padding)
	key1 := desKeyFromHash(ntHash[0:7])
	key2 := desKeyFromHash(ntHash[7:14])

	// Third key: last 2 bytes of hash + 5 zero bytes
	thirdPart := make([]byte, 7)
	copy(thirdPart, ntHash[14:16])
	key3 := desKeyFromHash(thirdPart)

	// DES-ECB encrypt the challenge with each key
	copy(result[0:8], desEncrypt(key1, challenge[:]))
	copy(result[8:16], desEncrypt(key2, challenge[:]))
	copy(result[16:24], desEncrypt(key3, challenge[:]))

	return result
}

// GenerateAuthenticatorResponse creates the "S=<hex>" success string per RFC 2759
func GenerateAuthenticatorResponse(password string, ntResponse [24]byte, peerChallenge, authChallenge [16]byte, username string) string {
	ntHash, _ := NTPasswordHash(password)
	ntHashHash := HashNTPasswordHash(ntHash)

	// Magic constants from RFC 2759
	magic1 := []byte{
		0x4D, 0x61, 0x67, 0x69, 0x63, 0x20, 0x73, 0x65, 0x72, 0x76,
		0x65, 0x72, 0x20, 0x74, 0x6F, 0x20, 0x63, 0x6C, 0x69, 0x65,
		0x6E, 0x74, 0x20, 0x73, 0x69, 0x67, 0x6E, 0x69, 0x6E, 0x67,
		0x20, 0x63, 0x6F, 0x6E, 0x73, 0x74, 0x61, 0x6E, 0x74,
	}
	magic2 := []byte{
		0x50, 0x61, 0x64, 0x20, 0x74, 0x6F, 0x20, 0x6D, 0x61, 0x6B,
		0x65, 0x20, 0x69, 0x74, 0x20, 0x64, 0x6F, 0x20, 0x6D, 0x6F,
		0x72, 0x65, 0x20, 0x74, 0x68, 0x61, 0x6E, 0x20, 0x6F, 0x6E,
		0x65, 0x20, 0x69, 0x74, 0x65, 0x72, 0x61, 0x74, 0x69, 0x6F,
		0x6E,
	}

	h := sha1.New()
	h.Write(ntHashHash[:])
	h.Write(ntResponse[:])
	h.Write(magic1)
	digest := h.Sum(nil)

	challengeHash := ChallengeHash(peerChallenge, authChallenge, username)

	h2 := sha1.New()
	h2.Write(digest)
	h2.Write(challengeHash[:])
	h2.Write(magic2)
	authResp := h2.Sum(nil)

	return fmt.Sprintf("S=%X", authResp)
}

// BuildChallengePacket builds an MSCHAPv2 Challenge EAP packet
// OpCode=1 (Challenge), MS-CHAPv2-ID, MS-Length, Value-Size=16, Challenge(16), Name
func BuildChallengePacket(chapID byte, authChallenge [16]byte, serverName string) []byte {
	nameBytes := []byte(serverName)
	valueSize := byte(16)
	msLength := uint16(5 + int(valueSize) + len(nameBytes)) // opcode(1)+id(1)+ms-length(2)+value-size(1)+challenge(16)+name

	pkt := make([]byte, msLength)
	pkt[0] = 1 // OpCode: Challenge
	pkt[1] = chapID
	binary.BigEndian.PutUint16(pkt[2:4], msLength)
	pkt[4] = valueSize
	copy(pkt[5:21], authChallenge[:])
	copy(pkt[21:], nameBytes)

	return pkt
}

// BuildSuccessPacket builds an MSCHAPv2 Success EAP packet
// OpCode=3 (Success), MS-CHAPv2-ID, MS-Length, Message("S=<hex>")
func BuildSuccessPacket(chapID byte, authResponse string) []byte {
	msgBytes := []byte(authResponse)
	msLength := uint16(4 + len(msgBytes))

	pkt := make([]byte, msLength)
	pkt[0] = 3 // OpCode: Success
	pkt[1] = chapID
	binary.BigEndian.PutUint16(pkt[2:4], msLength)
	copy(pkt[4:], msgBytes)

	return pkt
}

// BuildFailurePacket builds an MSCHAPv2 Failure EAP packet
func BuildFailurePacket(chapID byte, message string) []byte {
	msgBytes := []byte(message)
	msLength := uint16(4 + len(msgBytes))

	pkt := make([]byte, msLength)
	pkt[0] = 4 // OpCode: Failure
	pkt[1] = chapID
	binary.BigEndian.PutUint16(pkt[2:4], msLength)
	copy(pkt[4:], msgBytes)

	return pkt
}

// desKeyFromHash converts 7 bytes to an 8-byte DES key with parity bits
func desKeyFromHash(hash []byte) []byte {
	if len(hash) < 7 {
		padded := make([]byte, 7)
		copy(padded, hash)
		hash = padded
	}
	key := make([]byte, 8)
	key[0] = hash[0] >> 1
	key[1] = ((hash[0] & 0x01) << 6) | (hash[1] >> 2)
	key[2] = ((hash[1] & 0x03) << 5) | (hash[2] >> 3)
	key[3] = ((hash[2] & 0x07) << 4) | (hash[3] >> 4)
	key[4] = ((hash[3] & 0x0F) << 3) | (hash[4] >> 5)
	key[5] = ((hash[4] & 0x1F) << 2) | (hash[5] >> 6)
	key[6] = ((hash[5] & 0x3F) << 1) | (hash[6] >> 7)
	key[7] = hash[6] & 0x7F

	// Set odd parity
	for i := range key {
		key[i] = (key[i] << 1) | parityBit(key[i])
	}
	return key
}

func parityBit(b byte) byte {
	// Count number of 1-bits; if even, parity bit = 1 (odd parity)
	count := 0
	for i := 0; i < 7; i++ {
		if b&(1<<uint(i)) != 0 {
			count++
		}
	}
	if count%2 == 0 {
		return 1
	}
	return 0
}

func desEncrypt(key, data []byte) []byte {
	block, err := des.NewCipher(key)
	if err != nil {
		return make([]byte, 8)
	}
	result := make([]byte, 8)
	block.Encrypt(result, data)
	return result
}

func compareBytes(a, b []byte) bool {
	if len(a) != len(b) {
		return false
	}
	var diff byte
	for i := range a {
		diff |= a[i] ^ b[i]
	}
	return diff == 0
}

// ============================================================================
// Inline MD4 implementation (RFC 1320)
// golang.org/x/crypto/md4 is deprecated, so we include a minimal MD4 here.
// MD4 is only used for NTLM/MSCHAPv2 compatibility — NOT for security.
// ============================================================================

const md4BlockSize = 64
const md4Size = 16

type md4digest struct {
	s   [4]uint32
	x   [md4BlockSize]byte
	nx  int
	len uint64
}

func newMD4() hash.Hash {
	d := new(md4digest)
	d.Reset()
	return d
}

func (d *md4digest) Reset() {
	d.s[0] = 0x67452301
	d.s[1] = 0xEFCDAB89
	d.s[2] = 0x98BADCFE
	d.s[3] = 0x10325476
	d.nx = 0
	d.len = 0
}

func (d *md4digest) Size() int      { return md4Size }
func (d *md4digest) BlockSize() int { return md4BlockSize }

func (d *md4digest) Write(p []byte) (nn int, err error) {
	nn = len(p)
	d.len += uint64(nn)
	if d.nx > 0 {
		n := copy(d.x[d.nx:], p)
		d.nx += n
		if d.nx == md4BlockSize {
			md4Block(d, d.x[:])
			d.nx = 0
		}
		p = p[n:]
	}
	for len(p) >= md4BlockSize {
		md4Block(d, p[:md4BlockSize])
		p = p[md4BlockSize:]
	}
	if len(p) > 0 {
		d.nx = copy(d.x[:], p)
	}
	return
}

func (d *md4digest) Sum(in []byte) []byte {
	d0 := *d
	hash := d0.checkSum()
	return append(in, hash[:]...)
}

func (d *md4digest) checkSum() [md4Size]byte {
	length := d.len
	var tmp [md4BlockSize]byte
	tmp[0] = 0x80
	if length%md4BlockSize < 56 {
		d.Write(tmp[0 : 56-length%md4BlockSize])
	} else {
		d.Write(tmp[0 : md4BlockSize+56-length%md4BlockSize])
	}
	length <<= 3
	binary.LittleEndian.PutUint64(tmp[:8], length)
	d.Write(tmp[:8])

	var digest [md4Size]byte
	binary.LittleEndian.PutUint32(digest[0:], d.s[0])
	binary.LittleEndian.PutUint32(digest[4:], d.s[1])
	binary.LittleEndian.PutUint32(digest[8:], d.s[2])
	binary.LittleEndian.PutUint32(digest[12:], d.s[3])
	return digest
}

func md4Block(d *md4digest, p []byte) {
	var X [16]uint32
	for i := 0; i < 16; i++ {
		X[i] = binary.LittleEndian.Uint32(p[i*4:])
	}

	a, b, c, d0 := d.s[0], d.s[1], d.s[2], d.s[3]

	// Round 1
	for i, k := range [16]int{0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15} {
		shifts := [4]uint{3, 7, 11, 19}
		f := (b & c) | (^b & d0)
		sum := a + f + X[k]
		a, b, c, d0 = d0, bits.RotateLeft32(sum, int(shifts[i%4])), b, c
	}

	// Round 2
	for i, k := range [16]int{0, 4, 8, 12, 1, 5, 9, 13, 2, 6, 10, 14, 3, 7, 11, 15} {
		shifts := [4]uint{3, 5, 9, 13}
		f := (b & c) | (b & d0) | (c & d0)
		sum := a + f + X[k] + 0x5A827999
		a, b, c, d0 = d0, bits.RotateLeft32(sum, int(shifts[i%4])), b, c
	}

	// Round 3
	for i, k := range [16]int{0, 8, 4, 12, 2, 10, 6, 14, 1, 9, 5, 13, 3, 11, 7, 15} {
		shifts := [4]uint{3, 9, 11, 15}
		f := b ^ c ^ d0
		sum := a + f + X[k] + 0x6ED9EBA1
		a, b, c, d0 = d0, bits.RotateLeft32(sum, int(shifts[i%4])), b, c
	}

	d.s[0] += a
	d.s[1] += b
	d.s[2] += c
	d.s[3] += d0
}
