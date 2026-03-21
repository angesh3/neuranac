package service

import (
	"context"
	"database/sql"
	"sync/atomic"
	"time"

	"github.com/neuranac/services/sync-engine/internal/pb"
	"go.uber.org/zap"
	"google.golang.org/protobuf/types/known/timestamppb"
)

// SyncServiceImpl implements pb.SyncServiceServer backed by PostgreSQL.
type SyncServiceImpl struct {
	pb.UnimplementedSyncServiceServer
	DB              *sql.DB
	NodeID          string
	PeerConnected   *bool
	PeerNodeID      *string
	PendingOutbound *int64
	PendingInbound  *int64
	BytesSynced     *int64
	Conflicts       *int64
	LastSyncAt      *time.Time
	StartedAt       time.Time
	Logger          *zap.Logger
}

func (s *SyncServiceImpl) HealthCheck(ctx context.Context, req *pb.HealthRequest) (*pb.HealthResponse, error) {
	status := pb.NodeStatus_NODE_STATUS_HEALTHY
	if s.DB == nil {
		status = pb.NodeStatus_NODE_STATUS_DEGRADED
	}

	var activeSessions int64
	if s.DB != nil {
		row := s.DB.QueryRowContext(ctx, `SELECT COUNT(*) FROM sessions WHERE is_active = true`)
		_ = row.Scan(&activeSessions)
	}

	return &pb.HealthResponse{
		NodeId:         s.NodeID,
		Status:         status,
		Role:           "twin",
		UptimeSeconds:  int64(time.Since(s.StartedAt).Seconds()),
		ActiveSessions: activeSessions,
		SyncLagMs:      0,
		PendingChanges: atomic.LoadInt64(s.PendingOutbound),
		RespondedAt:    timestamppb.Now(),
	}, nil
}

func (s *SyncServiceImpl) GetSyncStatus(ctx context.Context, req *pb.SyncStatusRequest) (*pb.SyncStatusResponse, error) {
	peerID := ""
	if s.PeerNodeID != nil {
		peerID = *s.PeerNodeID
	}
	connected := false
	if s.PeerConnected != nil {
		connected = *s.PeerConnected
	}

	resp := &pb.SyncStatusResponse{
		NodeId:             s.NodeID,
		PeerNodeId:         peerID,
		PeerConnected:      connected,
		PendingOutbound:    atomic.LoadInt64(s.PendingOutbound),
		PendingInbound:     atomic.LoadInt64(s.PendingInbound),
		BytesSyncedLast24H: atomic.LoadInt64(s.BytesSynced),
		ConflictsLast24H:   atomic.LoadInt64(s.Conflicts),
	}

	if s.LastSyncAt != nil && !s.LastSyncAt.IsZero() {
		resp.LastSyncAt = timestamppb.New(*s.LastSyncAt)
		resp.ReplicationLagMs = time.Since(*s.LastSyncAt).Milliseconds()
	}

	return resp, nil
}
