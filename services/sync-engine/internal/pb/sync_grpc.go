// Package pb provides hand-written Go types matching proto/sync.proto.
// Replace with protoc-generated code when the build pipeline runs:
//
//	protoc --go_out=. --go-grpc_out=. proto/sync.proto
package pb

import (
	"context"

	"google.golang.org/grpc"
	"google.golang.org/protobuf/types/known/structpb"
	"google.golang.org/protobuf/types/known/timestamppb"
)

// ---------- enums ----------

type Operation int32

const (
	Operation_OPERATION_UNSPECIFIED Operation = 0
	Operation_OPERATION_CREATE     Operation = 1
	Operation_OPERATION_UPDATE     Operation = 2
	Operation_OPERATION_DELETE     Operation = 3
)

type AckStatus int32

const (
	AckStatus_ACK_STATUS_UNSPECIFIED       AckStatus = 0
	AckStatus_ACK_STATUS_OK                AckStatus = 1
	AckStatus_ACK_STATUS_CONFLICT_RESOLVED AckStatus = 2
	AckStatus_ACK_STATUS_REJECTED          AckStatus = 3
)

type NodeStatus int32

const (
	NodeStatus_NODE_STATUS_UNSPECIFIED  NodeStatus = 0
	NodeStatus_NODE_STATUS_HEALTHY      NodeStatus = 1
	NodeStatus_NODE_STATUS_DEGRADED     NodeStatus = 2
	NodeStatus_NODE_STATUS_UNREACHABLE  NodeStatus = 3
	NodeStatus_NODE_STATUS_SYNCING      NodeStatus = 4
)

// ---------- messages ----------

type VectorClock struct {
	Clocks map[string]int64
}

type ConfigChange struct {
	Id          string
	EntityType  string
	EntityId    string
	Operation   Operation
	Data        *structpb.Struct
	TenantId    string
	SourceNode  string
	VectorClock *VectorClock
	Timestamp   *timestamppb.Timestamp
	Scope       string
}

type ConfigAck struct {
	ChangeId           string
	Status             AckStatus
	ConflictResolution string
	MergedClock        *VectorClock
}

type PushAck struct {
	ReceivedCount  int64
	ProcessedCount int64
	FailedIds      []string
}

type HealthRequest struct {
	NodeId string
	SentAt *timestamppb.Timestamp
}

type HealthResponse struct {
	NodeId         string
	Status         NodeStatus
	Role           string
	UptimeSeconds  int64
	ActiveSessions int64
	SyncLagMs      int64
	PendingChanges int64
	RespondedAt    *timestamppb.Timestamp
}

type ResyncRequest struct {
	RequestingNode string
	EntityTypes    []string
	TenantId       string
}

type SyncStatusRequest struct {
	NodeId string
}

type SyncStatusResponse struct {
	NodeId            string
	PeerNodeId        string
	PeerConnected     bool
	ReplicationLagMs  int64
	PendingOutbound   int64
	PendingInbound    int64
	ConflictsLast24H  int64
	BytesSyncedLast24H int64
	LastSyncAt        *timestamppb.Timestamp
}

// ---------- service interface ----------

// SyncServiceServer is the server API for SyncService.
type SyncServiceServer interface {
	SyncConfig(SyncService_SyncConfigServer) error
	PushSessions(SyncService_PushSessionsServer) error
	PushAuditLogs(SyncService_PushAuditLogsServer) error
	HealthCheck(context.Context, *HealthRequest) (*HealthResponse, error)
	FullResync(*ResyncRequest, SyncService_FullResyncServer) error
	GetSyncStatus(context.Context, *SyncStatusRequest) (*SyncStatusResponse, error)
}

// Stream interfaces (simplified — real protoc output has full grpc.ServerStream wrappers)
type SyncService_SyncConfigServer interface {
	Send(*ConfigAck) error
	Recv() (*ConfigChange, error)
	grpc.ServerStream
}

type SyncService_PushSessionsServer interface {
	SendAndClose(*PushAck) error
	Recv() (*ConfigChange, error)
	grpc.ServerStream
}

type SyncService_PushAuditLogsServer interface {
	SendAndClose(*PushAck) error
	Recv() (*ConfigChange, error)
	grpc.ServerStream
}

type SyncService_FullResyncServer interface {
	Send(*ConfigChange) error
	grpc.ServerStream
}

// UnimplementedSyncServiceServer provides default no-op implementations.
type UnimplementedSyncServiceServer struct{}

func (UnimplementedSyncServiceServer) SyncConfig(SyncService_SyncConfigServer) error {
	return nil
}
func (UnimplementedSyncServiceServer) PushSessions(SyncService_PushSessionsServer) error {
	return nil
}
func (UnimplementedSyncServiceServer) PushAuditLogs(SyncService_PushAuditLogsServer) error {
	return nil
}
func (UnimplementedSyncServiceServer) HealthCheck(context.Context, *HealthRequest) (*HealthResponse, error) {
	return &HealthResponse{}, nil
}
func (UnimplementedSyncServiceServer) FullResync(*ResyncRequest, SyncService_FullResyncServer) error {
	return nil
}
func (UnimplementedSyncServiceServer) GetSyncStatus(context.Context, *SyncStatusRequest) (*SyncStatusResponse, error) {
	return &SyncStatusResponse{}, nil
}

// RegisterSyncServiceServer registers the service with the gRPC server.
// NOTE: This uses grpc.ServiceDesc; when replacing with protoc output, swap to generated code.
func RegisterSyncServiceServer(s *grpc.Server, srv SyncServiceServer) {
	s.RegisterService(&_SyncService_serviceDesc, srv)
}

var _SyncService_serviceDesc = grpc.ServiceDesc{
	ServiceName: "neuranac.sync.v1.SyncService",
	HandlerType: (*SyncServiceServer)(nil),
	Methods: []grpc.MethodDesc{
		{
			MethodName: "HealthCheck",
			Handler:    _SyncService_HealthCheck_Handler,
		},
		{
			MethodName: "GetSyncStatus",
			Handler:    _SyncService_GetSyncStatus_Handler,
		},
	},
	Streams:  []grpc.StreamDesc{},
	Metadata: "proto/sync.proto",
}

func _SyncService_HealthCheck_Handler(srv interface{}, ctx context.Context, dec func(interface{}) error, interceptor grpc.UnaryServerInterceptor) (interface{}, error) {
	in := new(HealthRequest)
	if err := dec(in); err != nil {
		return nil, err
	}
	if interceptor == nil {
		return srv.(SyncServiceServer).HealthCheck(ctx, in)
	}
	info := &grpc.UnaryServerInfo{Server: srv, FullMethod: "/neuranac.sync.v1.SyncService/HealthCheck"}
	return interceptor(ctx, in, info, func(ctx context.Context, req interface{}) (interface{}, error) {
		return srv.(SyncServiceServer).HealthCheck(ctx, req.(*HealthRequest))
	})
}

func _SyncService_GetSyncStatus_Handler(srv interface{}, ctx context.Context, dec func(interface{}) error, interceptor grpc.UnaryServerInterceptor) (interface{}, error) {
	in := new(SyncStatusRequest)
	if err := dec(in); err != nil {
		return nil, err
	}
	if interceptor == nil {
		return srv.(SyncServiceServer).GetSyncStatus(ctx, in)
	}
	info := &grpc.UnaryServerInfo{Server: srv, FullMethod: "/neuranac.sync.v1.SyncService/GetSyncStatus"}
	return interceptor(ctx, in, info, func(ctx context.Context, req interface{}) (interface{}, error) {
		return srv.(SyncServiceServer).GetSyncStatus(ctx, req.(*SyncStatusRequest))
	})
}
