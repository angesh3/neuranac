package tacacs

import (
	"encoding/binary"
	"testing"
)

func TestParseHeader(t *testing.T) {
	data := make([]byte, 12)
	data[0] = TACACSMajorVersion | TACACSMinorVersion // version
	data[1] = TypeAuthentication                       // type
	data[2] = 1                                        // seq_no
	data[3] = FlagSingleConnect                        // flags
	binary.BigEndian.PutUint32(data[4:8], 0x12345678)  // session_id
	binary.BigEndian.PutUint32(data[8:12], 100)        // length

	hdr := parseHeader(data)

	if hdr.Version != TACACSMajorVersion|TACACSMinorVersion {
		t.Errorf("Version = 0x%02x, want 0x%02x", hdr.Version, TACACSMajorVersion|TACACSMinorVersion)
	}
	if hdr.Type != TypeAuthentication {
		t.Errorf("Type = %d, want %d", hdr.Type, TypeAuthentication)
	}
	if hdr.SeqNo != 1 {
		t.Errorf("SeqNo = %d, want 1", hdr.SeqNo)
	}
	if hdr.Flags != FlagSingleConnect {
		t.Errorf("Flags = %d, want %d", hdr.Flags, FlagSingleConnect)
	}
	if hdr.SessionID != 0x12345678 {
		t.Errorf("SessionID = 0x%08x, want 0x12345678", hdr.SessionID)
	}
	if hdr.Length != 100 {
		t.Errorf("Length = %d, want 100", hdr.Length)
	}
}

func TestDecryptBodyIdentity(t *testing.T) {
	// With FlagUnencrypted, body should not be decrypted, but decryptBody
	// always XORs. We test that encrypt + decrypt = identity.
	hdr := &Header{
		Version:   TACACSMajorVersion | TACACSMinorVersion,
		SeqNo:     1,
		SessionID: 42,
	}
	original := []byte("hello world test data for tacacs")

	encrypted := decryptBody(hdr, original, "secretkey")
	// Decrypt again with same params should recover original
	decrypted := decryptBody(hdr, encrypted, "secretkey")

	if string(decrypted) != string(original) {
		t.Errorf("decrypt(encrypt(data)) != data: got %q, want %q", decrypted, original)
	}
}

func TestDecryptBodyEmpty(t *testing.T) {
	hdr := &Header{Version: 0xC1, SeqNo: 1, SessionID: 1}
	result := decryptBody(hdr, []byte{}, "secret")
	if len(result) != 0 {
		t.Errorf("expected empty result, got %d bytes", len(result))
	}
}

func TestDecryptBodyLong(t *testing.T) {
	// Test with body longer than 16 bytes to exercise multi-block pad
	hdr := &Header{Version: 0xC1, SeqNo: 1, SessionID: 99}
	original := make([]byte, 48) // 3 blocks of 16
	for i := range original {
		original[i] = byte(i)
	}

	encrypted := decryptBody(hdr, original, "longsecretkey123")
	decrypted := decryptBody(hdr, encrypted, "longsecretkey123")

	for i := range original {
		if decrypted[i] != original[i] {
			t.Fatalf("mismatch at byte %d: got 0x%02x, want 0x%02x", i, decrypted[i], original[i])
		}
	}
}

func TestBuildAuthenReply(t *testing.T) {
	hdr := &Header{
		Version:   0xC1,
		Type:      TypeAuthentication,
		SeqNo:     1,
		Flags:     0,
		SessionID: 100,
	}

	reply := buildAuthenReply(hdr, AuthenStatusPass, "")
	if len(reply) < 12 {
		t.Fatalf("reply too short: %d bytes", len(reply))
	}

	// Check header
	if reply[0] != hdr.Version {
		t.Errorf("version = 0x%02x, want 0x%02x", reply[0], hdr.Version)
	}
	if reply[1] != TypeAuthentication {
		t.Errorf("type = %d, want %d", reply[1], TypeAuthentication)
	}
	if reply[2] != hdr.SeqNo+1 {
		t.Errorf("seq_no = %d, want %d", reply[2], hdr.SeqNo+1)
	}
	sessID := binary.BigEndian.Uint32(reply[4:8])
	if sessID != 100 {
		t.Errorf("session_id = %d, want 100", sessID)
	}

	// Check body starts at offset 12
	bodyLen := binary.BigEndian.Uint32(reply[8:12])
	if bodyLen != uint32(len(reply)-12) {
		t.Errorf("body length header = %d, actual body = %d", bodyLen, len(reply)-12)
	}

	// Status byte is first byte of body
	if reply[12] != AuthenStatusPass {
		t.Errorf("status = %d, want %d", reply[12], AuthenStatusPass)
	}
}

func TestBuildAuthenReplyWithMessage(t *testing.T) {
	hdr := &Header{Version: 0xC1, Type: TypeAuthentication, SeqNo: 1, SessionID: 1}
	reply := buildAuthenReply(hdr, AuthenStatusFail, "Authentication failed")

	// Body: status(1) + flags(1) + server_msg_len(2) + data_len(2) + msg
	body := reply[12:]
	if body[0] != AuthenStatusFail {
		t.Errorf("status = %d, want %d", body[0], AuthenStatusFail)
	}
	msgLen := binary.BigEndian.Uint16(body[2:4])
	if msgLen != 21 { // "Authentication failed" = 21 bytes
		t.Errorf("msg_len = %d, want 21", msgLen)
	}
	msg := string(body[6 : 6+msgLen])
	if msg != "Authentication failed" {
		t.Errorf("msg = %q, want %q", msg, "Authentication failed")
	}
}

func TestBuildAuthorReply(t *testing.T) {
	hdr := &Header{Version: 0xC1, Type: TypeAuthorization, SeqNo: 1, SessionID: 200}
	args := []string{"priv-lvl=15"}
	reply := buildAuthorReply(hdr, AuthorStatusPassAdd, args, "")

	if len(reply) < 12 {
		t.Fatalf("reply too short: %d bytes", len(reply))
	}

	body := reply[12:]
	if body[0] != AuthorStatusPassAdd {
		t.Errorf("status = %d, want %d", body[0], AuthorStatusPassAdd)
	}
	if body[1] != 1 { // arg_cnt
		t.Errorf("arg_cnt = %d, want 1", body[1])
	}
}

func TestBuildAcctReply(t *testing.T) {
	hdr := &Header{Version: 0xC1, Type: TypeAccounting, SeqNo: 1, SessionID: 300}
	reply := buildAcctReply(hdr, AcctStatusSuccess, "")

	if len(reply) < 12 {
		t.Fatalf("reply too short: %d bytes", len(reply))
	}

	body := reply[12:]
	// ACCT REPLY: server_msg_len(2) + data_len(2) + status(1) + server_msg + data
	if body[4] != AcctStatusSuccess {
		t.Errorf("status = %d, want %d", body[4], AcctStatusSuccess)
	}
}

func TestBuildTACACSPacket(t *testing.T) {
	hdr := &Header{
		Version:   0xC1,
		Type:      TypeAuthentication,
		SeqNo:     3,
		Flags:     FlagUnencrypted,
		SessionID: 12345,
	}
	body := []byte{0x01, 0x02, 0x03}
	pkt := buildTACACSPacket(hdr, body)

	if len(pkt) != 12+3 {
		t.Fatalf("packet length = %d, want %d", len(pkt), 15)
	}
	if pkt[0] != 0xC1 {
		t.Errorf("version = 0x%02x, want 0xC1", pkt[0])
	}
	if pkt[2] != 4 { // SeqNo + 1
		t.Errorf("seq_no = %d, want 4", pkt[2])
	}
	if pkt[3] != FlagUnencrypted {
		t.Errorf("flags = %d, want %d", pkt[3], FlagUnencrypted)
	}
	bodyLen := binary.BigEndian.Uint32(pkt[8:12])
	if bodyLen != 3 {
		t.Errorf("body length = %d, want 3", bodyLen)
	}
}

func TestConstants(t *testing.T) {
	if TACACSMajorVersion != 0xC0 {
		t.Errorf("TACACSMajorVersion = 0x%02x, want 0xC0", TACACSMajorVersion)
	}
	if TypeAuthentication != 0x01 {
		t.Errorf("TypeAuthentication = %d, want 1", TypeAuthentication)
	}
	if TypeAuthorization != 0x02 {
		t.Errorf("TypeAuthorization = %d, want 2", TypeAuthorization)
	}
	if TypeAccounting != 0x03 {
		t.Errorf("TypeAccounting = %d, want 3", TypeAccounting)
	}
	if AuthenStatusPass != 0x01 {
		t.Errorf("AuthenStatusPass = %d, want 1", AuthenStatusPass)
	}
	if AuthenStatusFail != 0x02 {
		t.Errorf("AuthenStatusFail = %d, want 2", AuthenStatusFail)
	}
}
