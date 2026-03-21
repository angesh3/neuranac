package pb

import (
	"context"

	"google.golang.org/grpc"
)

// PolicyServiceClient is the client API for PolicyService.
type PolicyServiceClient interface {
	Evaluate(ctx context.Context, in *PolicyRequest, opts ...grpc.CallOption) (*PolicyResponse, error)
}

type policyServiceClient struct {
	cc grpc.ClientConnInterface
}

// NewPolicyServiceClient returns a new PolicyServiceClient.
func NewPolicyServiceClient(cc grpc.ClientConnInterface) PolicyServiceClient {
	return &policyServiceClient{cc}
}

func (c *policyServiceClient) Evaluate(ctx context.Context, in *PolicyRequest, opts ...grpc.CallOption) (*PolicyResponse, error) {
	out := new(PolicyResponse)
	err := c.cc.Invoke(ctx, "/neuranac.policy.v1.PolicyService/Evaluate", in, out, opts...)
	if err != nil {
		return nil, err
	}
	return out, nil
}
