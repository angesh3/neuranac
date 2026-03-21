package service

import (
	"context"
	"sync/atomic"
	"testing"
	"time"

	"go.uber.org/zap"
)

func newTestSyncService(t *testing.T) *SyncServiceImpl {
	t.Helper()
	logger, _ := zap.NewDevelopment()
	peerConnected := false
	peerNodeID := "twin-b"
	var pendingOut, pendingIn, bytesSynced, conflicts int64
	lastSync := time.Now().Add(-5 * time.Second)

	return &SyncServiceImpl{
		DB:              nil, // no real DB in unit tests
		NodeID:          "twin-a",
		PeerConnected:   &peerConnected,
		PeerNodeID:      &peerNodeID,
		PendingOutbound: &pendingOut,
		PendingInbound:  &pendingIn,
		BytesSynced:     &bytesSynced,
		Conflicts:       &conflicts,
		LastSyncAt:      &lastSync,
		StartedAt:       time.Now().Add(-10 * time.Minute),
		Logger:          logger,
	}
}

func TestHealthCheck_NilDB_Degraded(t *testing.T) {
	svc := newTestSyncService(t)
	ctx := context.Background()

	resp, err := svc.HealthCheck(ctx, nil)
	if err != nil {
		t.Fatalf("HealthCheck error: %v", err)
	}
	if resp.NodeId != "twin-a" {
		t.Errorf("NodeId = %q, want %q", resp.NodeId, "twin-a")
	}
	// nil DB should report degraded
	if resp.Status != 2 { // NODE_STATUS_DEGRADED = 2
		t.Errorf("Status = %d, want 2 (degraded)", resp.Status)
	}
	if resp.UptimeSeconds < 1 {
		t.Error("UptimeSeconds should be > 0")
	}
	if resp.Role != "twin" {
		t.Errorf("Role = %q, want %q", resp.Role, "twin")
	}
}

func TestGetSyncStatus_WithPeer(t *testing.T) {
	svc := newTestSyncService(t)
	ctx := context.Background()

	// Set some pending changes
	atomic.StoreInt64(svc.PendingOutbound, 42)
	atomic.StoreInt64(svc.BytesSynced, 1024*1024)
	*svc.PeerConnected = true

	resp, err := svc.GetSyncStatus(ctx, nil)
	if err != nil {
		t.Fatalf("GetSyncStatus error: %v", err)
	}
	if resp.NodeId != "twin-a" {
		t.Errorf("NodeId = %q, want %q", resp.NodeId, "twin-a")
	}
	if resp.PeerNodeId != "twin-b" {
		t.Errorf("PeerNodeId = %q, want %q", resp.PeerNodeId, "twin-b")
	}
	if !resp.PeerConnected {
		t.Error("PeerConnected should be true")
	}
	if resp.PendingOutbound != 42 {
		t.Errorf("PendingOutbound = %d, want 42", resp.PendingOutbound)
	}
	if resp.BytesSyncedLast24H != 1024*1024 {
		t.Errorf("BytesSyncedLast24H = %d, want %d", resp.BytesSyncedLast24H, 1024*1024)
	}
	if resp.ReplicationLagMs <= 0 {
		t.Error("ReplicationLagMs should be > 0 when LastSyncAt is in the past")
	}
}

func TestGetSyncStatus_NoPeer(t *testing.T) {
	svc := newTestSyncService(t)
	svc.PeerNodeID = nil
	svc.PeerConnected = nil
	ctx := context.Background()

	resp, err := svc.GetSyncStatus(ctx, nil)
	if err != nil {
		t.Fatalf("GetSyncStatus error: %v", err)
	}
	if resp.PeerNodeId != "" {
		t.Errorf("PeerNodeId = %q, want empty", resp.PeerNodeId)
	}
	if resp.PeerConnected {
		t.Error("PeerConnected should be false when nil")
	}
}

func TestGetSyncStatus_NoLastSync(t *testing.T) {
	svc := newTestSyncService(t)
	zeroTime := time.Time{}
	svc.LastSyncAt = &zeroTime
	ctx := context.Background()

	resp, err := svc.GetSyncStatus(ctx, nil)
	if err != nil {
		t.Fatalf("GetSyncStatus error: %v", err)
	}
	if resp.LastSyncAt != nil {
		t.Error("LastSyncAt should be nil when zero time")
	}
}

func TestGetSyncStatus_ConflictCounter(t *testing.T) {
	svc := newTestSyncService(t)
	atomic.StoreInt64(svc.Conflicts, 7)
	ctx := context.Background()

	resp, err := svc.GetSyncStatus(ctx, nil)
	if err != nil {
		t.Fatalf("GetSyncStatus error: %v", err)
	}
	if resp.ConflictsLast24H != 7 {
		t.Errorf("ConflictsLast24H = %d, want 7", resp.ConflictsLast24H)
	}
}

func TestHealthCheck_ActiveSessions_NilDB(t *testing.T) {
	svc := newTestSyncService(t)
	ctx := context.Background()

	resp, err := svc.HealthCheck(ctx, nil)
	if err != nil {
		t.Fatalf("HealthCheck error: %v", err)
	}
	// With nil DB, active sessions should be 0 (no panic)
	if resp.ActiveSessions != 0 {
		t.Errorf("ActiveSessions = %d, want 0 with nil DB", resp.ActiveSessions)
	}
}

func TestSyncServiceImpl_PendingChangesAtomic(t *testing.T) {
	svc := newTestSyncService(t)

	// Simulate concurrent updates
	done := make(chan struct{})
	go func() {
		for i := 0; i < 1000; i++ {
			atomic.AddInt64(svc.PendingOutbound, 1)
		}
		close(done)
	}()

	<-done

	val := atomic.LoadInt64(svc.PendingOutbound)
	if val != 1000 {
		t.Errorf("PendingOutbound = %d, want 1000", val)
	}
}
