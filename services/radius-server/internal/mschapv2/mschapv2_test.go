package mschapv2

import (
	"encoding/hex"
	"testing"
)

func TestNTPasswordHash(t *testing.T) {
	// Known test vector: password "Password" should produce a known NT hash
	hash, err := NTPasswordHash("Password")
	if err != nil {
		t.Fatalf("NTPasswordHash error: %v", err)
	}
	if len(hash) != 16 {
		t.Fatalf("expected 16 bytes, got %d", len(hash))
	}
	// The NT hash of "Password" is well-known: a4f49c406510bdcab6824ee7c30fd852
	expected := "a4f49c406510bdcab6824ee7c30fd852"
	got := hex.EncodeToString(hash[:])
	if got != expected {
		t.Errorf("NTPasswordHash(\"Password\") = %s, want %s", got, expected)
	}
}

func TestHashNTPasswordHash(t *testing.T) {
	ntHash, _ := NTPasswordHash("Password")
	hashHash := HashNTPasswordHash(ntHash)
	if len(hashHash) != 16 {
		t.Fatalf("expected 16 bytes, got %d", len(hashHash))
	}
	// Should not be all zeros
	allZero := true
	for _, b := range hashHash {
		if b != 0 {
			allZero = false
			break
		}
	}
	if allZero {
		t.Error("HashNTPasswordHash returned all zeros")
	}
}

func TestChallengeHash(t *testing.T) {
	var peer, auth [16]byte
	for i := range peer {
		peer[i] = byte(i)
		auth[i] = byte(i + 16)
	}
	result := ChallengeHash(peer, auth, "testuser")
	if len(result) != 8 {
		t.Fatalf("expected 8 bytes, got %d", len(result))
	}
}

func TestChallengeResponse(t *testing.T) {
	var challenge [8]byte
	for i := range challenge {
		challenge[i] = byte(i)
	}
	ntHash, _ := NTPasswordHash("testpassword")
	result := ChallengeResponse(challenge, ntHash)
	if len(result) != 24 {
		t.Fatalf("expected 24 bytes, got %d", len(result))
	}
}

func TestGenerateNTResponse(t *testing.T) {
	var auth, peer [16]byte
	for i := range auth {
		auth[i] = byte(i)
		peer[i] = byte(i + 100)
	}
	ntHash, _ := NTPasswordHash("MyPassword")
	result := GenerateNTResponse(auth, peer, "User", ntHash)
	if len(result) != 24 {
		t.Fatalf("expected 24 bytes, got %d", len(result))
	}
}

func TestVerifyRoundTrip(t *testing.T) {
	password := "SecurePass123"
	username := "testuser"

	// Generate authenticator challenge
	authChallenge, err := GenerateAuthChallenge()
	if err != nil {
		t.Fatalf("GenerateAuthChallenge error: %v", err)
	}

	// Simulate peer generating their response
	var peerChallenge [16]byte
	for i := range peerChallenge {
		peerChallenge[i] = byte(i * 3)
	}

	ntHash, err := NTPasswordHash(password)
	if err != nil {
		t.Fatalf("NTPasswordHash error: %v", err)
	}

	ntResponse := GenerateNTResponse(authChallenge, peerChallenge, username, ntHash)

	// Build a response struct as if from the peer
	resp := &Response{
		PeerChallenge: peerChallenge,
		NTResponse:    ntResponse,
		Username:      username,
	}

	// Verify should succeed with correct password
	authResp, err := Verify(authChallenge, resp, password)
	if err != nil {
		t.Fatalf("Verify failed: %v", err)
	}
	if authResp == "" {
		t.Fatal("expected non-empty auth response")
	}
	if authResp[:2] != "S=" {
		t.Errorf("auth response should start with S=, got %s", authResp[:2])
	}

	// Verify should fail with wrong password
	_, err = Verify(authChallenge, resp, "WrongPassword")
	if err == nil {
		t.Error("Verify should fail with wrong password")
	}
}

func TestBuildChallengePacket(t *testing.T) {
	var auth [16]byte
	for i := range auth {
		auth[i] = byte(i)
	}
	pkt := BuildChallengePacket(1, auth, "NeuraNAC-RADIUS")
	if len(pkt) < 21 {
		t.Fatalf("challenge packet too short: %d bytes", len(pkt))
	}
	if pkt[0] != 1 { // OpCode Challenge
		t.Errorf("expected OpCode 1, got %d", pkt[0])
	}
	if pkt[1] != 1 { // CHAP ID
		t.Errorf("expected CHAP ID 1, got %d", pkt[1])
	}
	if pkt[4] != 16 { // Value-Size
		t.Errorf("expected Value-Size 16, got %d", pkt[4])
	}
}

func TestBuildSuccessPacket(t *testing.T) {
	pkt := BuildSuccessPacket(1, "S=ABCDEF1234567890")
	if pkt[0] != 3 { // OpCode Success
		t.Errorf("expected OpCode 3, got %d", pkt[0])
	}
}

func TestBuildFailurePacket(t *testing.T) {
	pkt := BuildFailurePacket(1, "E=691 R=0 V=3 M=Authentication failed")
	if pkt[0] != 4 { // OpCode Failure
		t.Errorf("expected OpCode 4, got %d", pkt[0])
	}
}

func TestMD4KnownVector(t *testing.T) {
	// RFC 1320 test vectors
	h := newMD4()
	h.Write([]byte(""))
	got := hex.EncodeToString(h.Sum(nil))
	expected := "31d6cfe0d16ae931b73c59d7e0c089c0"
	if got != expected {
		t.Errorf("MD4(\"\") = %s, want %s", got, expected)
	}

	h2 := newMD4()
	h2.Write([]byte("a"))
	got2 := hex.EncodeToString(h2.Sum(nil))
	expected2 := "bde52cb31de33e46245e05fbdbd6fb24"
	if got2 != expected2 {
		t.Errorf("MD4(\"a\") = %s, want %s", got2, expected2)
	}

	h3 := newMD4()
	h3.Write([]byte("abc"))
	got3 := hex.EncodeToString(h3.Sum(nil))
	expected3 := "a448017aaf21d8525fc10ae87aa6729d"
	if got3 != expected3 {
		t.Errorf("MD4(\"abc\") = %s, want %s", got3, expected3)
	}
}

func TestDesKeyFromHash(t *testing.T) {
	input := []byte{0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07}
	key := desKeyFromHash(input)
	if len(key) != 8 {
		t.Fatalf("expected 8-byte DES key, got %d", len(key))
	}
}

func TestCompareBytes(t *testing.T) {
	a := []byte{1, 2, 3}
	b := []byte{1, 2, 3}
	c := []byte{1, 2, 4}

	if !compareBytes(a, b) {
		t.Error("identical slices should compare equal")
	}
	if compareBytes(a, c) {
		t.Error("different slices should not compare equal")
	}
	if compareBytes(a, []byte{1, 2}) {
		t.Error("different length slices should not compare equal")
	}
}
