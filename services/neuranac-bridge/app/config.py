"""NeuraNAC Bridge configuration — loaded from environment variables.

The Bridge is a generic connection manager that runs on EVERY site (on-prem
and cloud). It replaces the old NeuraNAC-only connector with a pluggable adapter
architecture.

Env prefix: NEURANAC_BRIDGE_
"""
import os
from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings


class BridgeSettings(BaseSettings):
    # ── Identity ─────────────────────────────────────────────────────────────
    bridge_name: str = "neuranac-bridge-01"
    bridge_version: str = "1.0.0"
    site_id: str = "00000000-0000-0000-0000-000000000001"
    tenant_id: str = "00000000-0000-0000-0000-000000000000"
    node_type: str = "bridge"

    # ── Cloud NeuraNAC (where this bridge registers and tunnels to) ───────────────
    cloud_neuranac_api_url: str = "http://localhost:8080"
    cloud_neuranac_ws_url: str = "ws://localhost:8080/api/v1/ws/bridge"

    # ── Peer NeuraNAC (for NeuraNAC-to-NeuraNAC adapter in hybrid mode) ────────────────────
    peer_api_url: str = ""
    peer_grpc_address: str = ""

    # ── NeuraNAC adapter settings (optional, only if NeuraNAC exists on-prem) ─────────
    legacy_nac_enabled: bool = False
    legacy_nac_hostname: str = "legacy-nac.local"
    legacy_nac_ers_port: int = 9060
    legacy_nac_ers_username: str = "admin"
    legacy_nac_ers_password: str = ""
    legacy_nac_event_port: int = 8910
    legacy_nac_node_name: str = "neuranac-bridge"
    legacy_nac_cert_path: str = ""
    legacy_nac_key_path: str = ""
    legacy_nac_ca_path: str = ""
    legacy_nac_verify_ssl: bool = False

    # ── Tunnel settings ──────────────────────────────────────────────────────
    tunnel_reconnect_base_delay: float = 5.0
    tunnel_reconnect_max_delay: float = 120.0
    tunnel_heartbeat_interval: int = 30

    # ── Registration ─────────────────────────────────────────────────────────
    registration_retry_interval: int = 10
    heartbeat_interval: int = 30

    # ── Zero-trust activation ────────────────────────────────────────────────
    activation_code: str = ""

    # ── mTLS (per-tenant certs issued during activation) ─────────────────────
    bridge_trust_enforce: bool = False  # When True, require valid mTLS certs for all connections
    client_cert_path: str = ""
    client_key_path: str = ""
    ca_cert_path: str = ""

    # ── Deployment mode ──────────────────────────────────────────────────────
    deployment_mode: str = "standalone"  # standalone | hybrid
    site_type: str = "onprem"            # onprem | cloud

    # ── Adapter auto-discovery ───────────────────────────────────────────────
    adapters_enabled: str = ""  # comma-separated: "legacy_nac,neuranac_to_neuranac,generic_rest"

    # ── Simulated mode (for dev/demo without real NeuraNAC or peer) ───────────────
    simulated: bool = True

    # ── Service ──────────────────────────────────────────────────────────────
    host: str = "0.0.0.0"
    port: int = 8090
    log_level: str = "info"

    # ── NATS (for cross-site event bridging) ─────────────────────────────────
    nats_url: str = "nats://localhost:4222"

    class Config:
        env_prefix = "NEURANAC_BRIDGE_"
        env_file = ".env"
        case_sensitive = False

    @property
    def enabled_adapters(self) -> list[str]:
        """Return list of adapter types to auto-start."""
        if self.adapters_enabled:
            return [a.strip() for a in self.adapters_enabled.split(",") if a.strip()]
        # Auto-detect from config
        adapters = []
        if self.legacy_nac_enabled and self.legacy_nac_hostname:
            adapters.append("legacy_nac")
        if self.deployment_mode == "hybrid" and (self.peer_api_url or self.peer_grpc_address):
            adapters.append("neuranac_to_neuranac")
        return adapters


@lru_cache
def get_bridge_settings() -> BridgeSettings:
    return BridgeSettings()
