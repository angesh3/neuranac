"""gRPC server for Policy Engine - called by RADIUS server"""
import json
import grpc
from concurrent import futures
import structlog

logger = structlog.get_logger()

# Try importing generated stubs; fall back to generic handler
_pb2 = None
_pb2_grpc = None
try:
    from app.generated import policy_pb2 as _pb2
    from app.generated import policy_pb2_grpc as _pb2_grpc
    logger.info("Using generated protobuf stubs")
except ImportError:
    logger.info("Generated stubs not found, using generic gRPC handler")


class PolicyServicer:
    """Implements the PolicyService gRPC interface.
    Works both with generated pb2 stubs (production) and without (dev/fallback).
    """

    def __init__(self, evaluator):
        self.evaluator = evaluator

    async def Evaluate(self, request, context):
        """Evaluate a single policy request"""
        # When using generated stubs, request is a protobuf message.
        # When using generic handler, request is already a dict (deserialized JSON).
        if isinstance(request, dict):
            req_dict = request
        else:
            req_dict = self._proto_to_dict(request)

        result = await self.evaluator.evaluate(req_dict)

        # If using generated stubs, convert result to protobuf response
        if _pb2 is not None:
            return self._dict_to_proto_response(result)
        return result

    async def BatchEvaluate(self, request, context):
        """Evaluate multiple policy requests"""
        if isinstance(request, dict):
            requests = request.get("requests", [])
        else:
            requests = list(request.requests) if hasattr(request, 'requests') else []
        responses = []
        for req in requests:
            resp = await self.Evaluate(req, context)
            responses.append(resp)
        if _pb2 is not None:
            batch_resp = _pb2.BatchPolicyResponse()
            batch_resp.responses.extend(responses)
            return batch_resp
        return {"responses": responses}

    def _proto_to_dict(self, request):
        """Convert a protobuf PolicyRequest to evaluation dict"""
        auth_ctx = getattr(request, 'auth_context', None)
        net_ctx = getattr(request, 'network_context', None)
        id_ctx = getattr(request, 'identity_context', None)
        ep_ctx = getattr(request, 'endpoint_context', None)
        ai_ctx = getattr(request, 'ai_context', None)
        return {
            "tenant_id": getattr(request, 'tenant_id', ''),
            "session_id": getattr(request, 'session_id', ''),
            "auth_context": {
                "auth_type": getattr(auth_ctx, 'auth_type', '') if auth_ctx else '',
                "eap_type": getattr(auth_ctx, 'eap_type', '') if auth_ctx else '',
                "username": getattr(auth_ctx, 'username', '') if auth_ctx else '',
                "calling_station_id": getattr(auth_ctx, 'calling_station_id', '') if auth_ctx else '',
            },
            "network_context": {
                "nas_ip": getattr(net_ctx, 'nas_ip', '') if net_ctx else '',
                "nas_port": getattr(net_ctx, 'nas_port', '') if net_ctx else '',
                "device_vendor": getattr(net_ctx, 'device_vendor', '') if net_ctx else '',
            },
            "identity_context": {
                "username": getattr(id_ctx, 'username', '') if id_ctx else '',
                "groups": list(getattr(id_ctx, 'groups', [])) if id_ctx else [],
            },
            "endpoint_context": {
                "mac_address": getattr(ep_ctx, 'mac_address', '') if ep_ctx else '',
                "device_type": getattr(ep_ctx, 'device_type', '') if ep_ctx else '',
                "posture_status": getattr(ep_ctx, 'posture_status', '') if ep_ctx else '',
            },
            "ai_context": {
                "agent_id": getattr(ai_ctx, 'agent_id', '') if ai_ctx else '',
                "agent_type": getattr(ai_ctx, 'agent_type', '') if ai_ctx else '',
                "risk_score": getattr(ai_ctx, 'risk_score', 0) if ai_ctx else 0,
                "shadow_ai_detected": getattr(ai_ctx, 'shadow_ai_detected', False) if ai_ctx else False,
            },
        }

    def _dict_to_proto_response(self, result):
        """Convert evaluation result dict to protobuf PolicyResponse"""
        resp = _pb2.PolicyResponse()
        decision = result.get("decision", {})
        resp.decision.type = self._decision_enum(decision.get("type", "deny"))
        resp.decision.description = decision.get("description", "")
        resp.matched_rule_id = result.get("matched_rule_id") or ""
        resp.matched_rule_name = result.get("matched_rule_name") or ""
        resp.evaluation_time_us = result.get("evaluation_time_us", 0)
        auth = result.get("authorization", {})
        if auth:
            resp.authorization.vlan_id = auth.get("vlan_id") or ""
            resp.authorization.vlan_name = auth.get("vlan_name") or ""
            resp.authorization.sgt_value = auth.get("sgt_value") or 0
            resp.authorization.coa_action = auth.get("coa_action") or ""
            resp.authorization.redirect_url = auth.get("redirect_url") or ""
            resp.authorization.session_timeout = auth.get("session_timeout") or 0
        return resp

    @staticmethod
    def _decision_enum(dtype):
        mapping = {"permit": 1, "deny": 2, "quarantine": 3, "redirect": 4, "continue": 5}
        return mapping.get(dtype, 0)

    @classmethod
    def register(cls, server, evaluator):
        """Register the servicer with a gRPC server"""
        servicer = cls(evaluator)
        if _pb2_grpc is not None:
            _pb2_grpc.add_PolicyServiceServicer_to_server(servicer, server)
            logger.info("PolicyServicer registered with generated stubs")
        else:
            # Register using GenericRpcHandler (fallback when proto stubs are not generated)
            class _PolicyGenericHandler(grpc.GenericRpcHandler):
                def __init__(self, svc):
                    self._svc = svc
                    self._methods = {
                        "/neuranac.policy.v1.PolicyService/Evaluate": grpc.unary_unary_rpc_method_handler(
                            svc.Evaluate,
                        ),
                        "/neuranac.policy.v1.PolicyService/BatchEvaluate": grpc.unary_unary_rpc_method_handler(
                            svc.BatchEvaluate,
                        ),
                    }

                def service(self, handler_call_details):
                    return self._methods.get(handler_call_details.method)

            server.add_generic_rpc_handlers([_PolicyGenericHandler(servicer)])
            logger.info("PolicyServicer registered with generic gRPC handler")
