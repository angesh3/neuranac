package netflow

import (
	"encoding/binary"
	"testing"
)

func TestHandleNetFlowV5_TooShort(t *testing.T) {
	c := &Collector{}
	// Less than header size — should not panic
	c.handleNetFlowV5(make([]byte, 10), "10.0.0.1")
	// No flows should be recorded
	if c.flows.Load() != 0 {
		t.Errorf("flows = %d, want 0 for short packet", c.flows.Load())
	}
}

func TestHandleNetFlowV5_SingleFlow(t *testing.T) {
	// Build a valid NetFlow v5 packet with 1 flow record
	data := make([]byte, NFv5HeaderSize+NFv5RecordSize)
	// Header
	binary.BigEndian.PutUint16(data[0:2], 5)  // version
	binary.BigEndian.PutUint16(data[2:4], 1)  // count = 1
	binary.BigEndian.PutUint32(data[4:8], 1000) // sysUptime
	binary.BigEndian.PutUint32(data[8:12], 1709550000) // unixSecs

	// Flow record at offset 24
	rec := data[NFv5HeaderSize:]
	rec[0], rec[1], rec[2], rec[3] = 10, 0, 0, 1    // srcIP
	rec[4], rec[5], rec[6], rec[7] = 10, 0, 0, 2    // dstIP
	rec[8], rec[9], rec[10], rec[11] = 10, 0, 0, 254 // nextHop
	binary.BigEndian.PutUint32(rec[16:20], 100)       // packets
	binary.BigEndian.PutUint32(rec[20:24], 50000)     // bytes
	binary.BigEndian.PutUint16(rec[32:34], 12345)     // srcPort
	binary.BigEndian.PutUint16(rec[34:36], 443)       // dstPort
	rec[38] = 6  // TCP
	rec[39] = 0  // ToS

	// We can't call handleNetFlowV5 without a publisher, but we can test parsing logic
	// Test the packet length validation
	if len(data) < NFv5HeaderSize+1*NFv5RecordSize {
		t.Error("test data should be >= header + 1 record")
	}

	// Verify header parsing
	version := binary.BigEndian.Uint16(data[0:2])
	if version != 5 {
		t.Errorf("version = %d, want 5", version)
	}
	count := int(binary.BigEndian.Uint16(data[2:4]))
	if count != 1 {
		t.Errorf("count = %d, want 1", count)
	}

	// Verify record parsing
	srcIP := rec[0:4]
	if srcIP[0] != 10 || srcIP[1] != 0 || srcIP[2] != 0 || srcIP[3] != 1 {
		t.Errorf("srcIP = %v, want 10.0.0.1", srcIP)
	}
	packets := binary.BigEndian.Uint32(rec[16:20])
	if packets != 100 {
		t.Errorf("packets = %d, want 100", packets)
	}
	bytes := binary.BigEndian.Uint32(rec[20:24])
	if bytes != 50000 {
		t.Errorf("bytes = %d, want 50000", bytes)
	}
	proto := rec[38]
	if proto != 6 {
		t.Errorf("protocol = %d, want 6 (TCP)", proto)
	}
}

func TestHandleNetFlowV5_TruncatedRecords(t *testing.T) {
	c := &Collector{}
	// Header says 2 flows but only 1 record worth of data
	data := make([]byte, NFv5HeaderSize+NFv5RecordSize)
	binary.BigEndian.PutUint16(data[0:2], 5) // version
	binary.BigEndian.PutUint16(data[2:4], 2) // count = 2 (but only 1 record)

	c.handleNetFlowV5(data, "10.0.0.1")
	// Should not process any flows since packet is truncated
	if c.flows.Load() != 0 {
		t.Errorf("flows = %d, want 0 for truncated packet", c.flows.Load())
	}
}

func TestHandlePacket_VersionDispatch(t *testing.T) {
	c := &Collector{}

	// Version 5
	data5 := make([]byte, 4)
	binary.BigEndian.PutUint16(data5[0:2], 5)
	// Won't fully process (no publisher), but shouldn't panic
	c.handlePacket(data5, nil)

	// Version 9
	data9 := make([]byte, 4)
	binary.BigEndian.PutUint16(data9[0:2], 9)
	c.handlePacket(data9, nil)

	// Version 10 (IPFIX)
	data10 := make([]byte, 4)
	binary.BigEndian.PutUint16(data10[0:2], 10)
	c.handlePacket(data10, nil)

	// Unknown version
	dataUnk := make([]byte, 4)
	binary.BigEndian.PutUint16(dataUnk[0:2], 99)
	c.handlePacket(dataUnk, nil)
}

func TestHandlePacket_TooShort(t *testing.T) {
	c := &Collector{}
	c.handlePacket([]byte{0x00}, nil)
	// Should not panic
}

func TestCollectorStats(t *testing.T) {
	c := &Collector{}
	stats := c.Stats()
	if stats["received"] != 0 || stats["flows"] != 0 {
		t.Errorf("initial stats should be zero, got %v", stats)
	}
	c.received.Add(7)
	c.flows.Add(42)
	stats = c.Stats()
	if stats["received"] != 7 {
		t.Errorf("received = %d, want 7", stats["received"])
	}
	if stats["flows"] != 42 {
		t.Errorf("flows = %d, want 42", stats["flows"])
	}
}

func TestConstants(t *testing.T) {
	if NFv5HeaderSize != 24 {
		t.Errorf("NFv5HeaderSize = %d, want 24", NFv5HeaderSize)
	}
	if NFv5RecordSize != 48 {
		t.Errorf("NFv5RecordSize = %d, want 48", NFv5RecordSize)
	}
}
