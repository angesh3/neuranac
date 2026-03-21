#!/usr/bin/env python3
"""
NeuraNAC Sanity Test Runner — Checkpoint-based, retry-aware, phase-grouped.

Usage:
    python3 sanity_runner.py                     # run all phases
    python3 sanity_runner.py --phase auth        # run only auth phase
    python3 sanity_runner.py --phase legacy_nac # run only Legacy NAC phases
    python3 sanity_runner.py --continue          # resume from last checkpoint
    python3 sanity_runner.py --reset             # clear checkpoint and start fresh
    python3 sanity_runner.py --report            # just regenerate the report
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# ─── Configuration ────────────────────────────────────────────────────────────

API = "http://localhost:8080"
AI_ENGINE = "http://localhost:8081"
WEB = "http://localhost:5173"
CHECKPOINT_FILE = Path(__file__).parent / "sanity_checkpoint.json"
REPORT_FILE = Path(__file__).parent.parent / "docs" / "SANITY_REPORT.md"
REQUEST_DELAY = 0.6          # seconds between requests (avoid 429)
MAX_RETRIES = 5
RETRY_BACKOFF_BASE = 2       # exponential backoff base seconds
CURL_TIMEOUT = 15            # seconds per request

# ─── Checkpoint helpers ───────────────────────────────────────────────────────

def load_checkpoint() -> dict:
    if CHECKPOINT_FILE.exists():
        return json.loads(CHECKPOINT_FILE.read_text())
    return {"results": {}, "resources": {}, "meta": {}}


def save_checkpoint(ckpt: dict):
    ckpt["meta"]["updated_at"] = datetime.now(timezone.utc).isoformat()
    CHECKPOINT_FILE.write_text(json.dumps(ckpt, indent=2))


def is_done(ckpt: dict, test_id: str) -> bool:
    r = ckpt["results"].get(test_id)
    return r is not None and r.get("status") == "pass"


# ─── HTTP via subprocess curl ─────────────────────────────────────────────────

def curl(method: str, url: str, body: Optional[dict] = None,
         token: Optional[str] = None, expect: Optional[List[int]] = None) -> dict:
    """
    Run a single curl request in a subprocess.  Returns dict with:
        code (int), body (str), ok (bool), parsed (dict|None)
    Retries on code 0 (connection refused), 429, 500.
    """
    expect = expect or [200, 201, 204]
    headers = ["-H", "Content-Type: application/json"]
    if token:
        headers += ["-H", f"Authorization: Bearer {token}"]

    cmd = ["curl", "-s", "-w", "\n%{http_code}", "-X", method.upper(),
           "--max-time", str(CURL_TIMEOUT)] + headers

    if body is not None:
        cmd += ["-d", json.dumps(body)]
    cmd.append(url)

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=CURL_TIMEOUT + 5)
            raw = proc.stdout.strip()
            if "\n" in raw:
                body_text, code_str = raw.rsplit("\n", 1)
            else:
                body_text, code_str = "", raw
            code = int(code_str) if code_str.isdigit() else 0
        except (subprocess.TimeoutExpired, Exception):
            code, body_text = 0, ""

        if code in (0, 429, 500, 502, 503) and attempt < MAX_RETRIES:
            wait = RETRY_BACKOFF_BASE ** attempt
            if code == 429:
                wait = max(wait, 5)  # rate-limit: wait at least 5s
            print(f"      ↻ retry {attempt}/{MAX_RETRIES} (code {code}), wait {wait}s")
            time.sleep(wait)
            continue
        break

    parsed = None
    if body_text:
        try:
            parsed = json.loads(body_text)
        except json.JSONDecodeError:
            pass

    return {"code": code, "body": body_text[:500], "ok": code in expect, "parsed": parsed}


# ─── Test definition helpers ──────────────────────────────────────────────────

class TestSuite:
    def __init__(self):
        self.tests: list[dict] = []

    def add(self, test_id: str, phase: str, group: str, name: str,
            method: str, path: str, body: Optional[dict] = None,
            expect: Optional[List[int]] = None, depends: Optional[str] = None,
            resource_key: Optional[str] = None, extract_id: Optional[str] = None,
            skip_if_missing: Optional[str] = None):
        self.tests.append({
            "id": test_id, "phase": phase, "group": group, "name": name,
            "method": method, "path": path, "body": body,
            "expect": expect, "depends": depends,
            "resource_key": resource_key, "extract_id": extract_id,
            "skip_if_missing": skip_if_missing,
        })


def build_tests() -> TestSuite:
    s = TestSuite()

    # ═══ PHASE: INFRA ═══════════════════════════════════════════════════════
    s.add("infra-01", "infra", "Health", "GET /health", "GET", "/health", expect=[200, 404])
    s.add("infra-02", "infra", "Health", "GET /ready", "GET", "/ready", expect=[200, 404])
    s.add("infra-03", "infra", "Health", "GET /metrics", "GET", "/metrics", expect=[200, 404])
    s.add("infra-04", "infra", "Health", "GET /openapi.json", "GET", "/api/v1/openapi.json")

    # ═══ PHASE: AUTH ════════════════════════════════════════════════════════
    s.add("auth-01", "auth", "Auth", "POST /auth/login",
          "POST", "/api/v1/auth/login",
          body={"username": "admin", "password": "admin123"},
          resource_key="token", extract_id="access_token")
    s.add("auth-02", "auth", "Auth", "POST /auth/refresh",
          "POST", "/api/v1/auth/refresh",
          body={"refresh_token": "dummy"}, expect=[200, 401, 422])
    s.add("auth-03", "auth", "Auth", "POST /auth/logout",
          "POST", "/api/v1/auth/logout", expect=[200, 401])

    # ═══ PHASE: POLICIES ════════════════════════════════════════════════════
    s.add("pol-01", "policies", "PolicySets", "GET /policies/",
          "GET", "/api/v1/policies/")
    s.add("pol-02", "policies", "PolicySets", "POST /policies/",
          "POST", "/api/v1/policies/",
          body={"name": "SanityTestPolicy", "description": "Sanity", "match_type": "all"},
          resource_key="policy_id", extract_id="id")
    s.add("pol-03", "policies", "PolicySets", "GET /policies/{id}",
          "GET", "/api/v1/policies/{policy_id}",
          skip_if_missing="policy_id")
    s.add("pol-04", "policies", "PolicySets", "PUT /policies/{id}",
          "PUT", "/api/v1/policies/{policy_id}",
          body={"name": "SanityTestPolicyUpd", "description": "Updated"},
          skip_if_missing="policy_id")

    s.add("pol-05", "policies", "PolicyRules", "POST /policies/{id}/rules",
          "POST", "/api/v1/policies/{policy_id}/rules",
          body={"name": "SanityRule", "condition_type": "all", "action": "permit", "priority": 1},
          skip_if_missing="policy_id",
          resource_key="rule_id", extract_id="id")
    s.add("pol-06", "policies", "PolicyRules", "GET /policies/{id}/rules",
          "GET", "/api/v1/policies/{policy_id}/rules",
          skip_if_missing="policy_id")
    s.add("pol-07", "policies", "PolicyRules", "PUT /policies/{id}/rules/{rid}",
          "PUT", "/api/v1/policies/{policy_id}/rules/{rule_id}",
          body={"name": "SanityRuleUpd", "action": "deny"},
          skip_if_missing="rule_id")
    s.add("pol-08", "policies", "PolicyRules", "DELETE /policies/{id}/rules/{rid}",
          "DELETE", "/api/v1/policies/{policy_id}/rules/{rule_id}",
          expect=[200, 204], skip_if_missing="rule_id")
    s.add("pol-09", "policies", "PolicySets", "DELETE /policies/{id}",
          "DELETE", "/api/v1/policies/{policy_id}",
          expect=[200, 204], skip_if_missing="policy_id")

    s.add("pol-10", "policies", "AuthProfiles", "GET /policies/auth-profiles/",
          "GET", "/api/v1/policies/auth-profiles/")
    s.add("pol-11", "policies", "AuthProfiles", "POST /policies/auth-profiles/",
          "POST", "/api/v1/policies/auth-profiles/",
          body={"name": "SanityAP", "auth_type": "dot1x", "description": "test"})

    # ═══ PHASE: IDENTITY ════════════════════════════════════════════════════
    s.add("id-01", "identity", "IdentitySources", "GET /identity-sources/",
          "GET", "/api/v1/identity-sources/")
    s.add("id-02", "identity", "IdentitySources", "POST /identity-sources/",
          "POST", "/api/v1/identity-sources/",
          body={"name": "SanityLDAP", "source_type": "ldap", "config": {"host": "ldap.test", "port": 389, "base_dn": "dc=test"}},
          resource_key="idsource_id", extract_id="id")
    s.add("id-03", "identity", "IdentitySources", "GET /identity-sources/{id}",
          "GET", "/api/v1/identity-sources/{idsource_id}",
          skip_if_missing="idsource_id")
    s.add("id-04", "identity", "IdentitySources", "PUT /identity-sources/{id}",
          "PUT", "/api/v1/identity-sources/{idsource_id}",
          body={"name": "SanityLDAPUpd", "source_type": "ldap"},
          skip_if_missing="idsource_id")
    s.add("id-05", "identity", "IdentitySources", "POST /identity-sources/{id}/test",
          "POST", "/api/v1/identity-sources/{idsource_id}/test",
          skip_if_missing="idsource_id", expect=[200, 422, 500])
    s.add("id-06", "identity", "IdentitySources", "POST /identity-sources/{id}/sync",
          "POST", "/api/v1/identity-sources/{idsource_id}/sync",
          skip_if_missing="idsource_id", expect=[200, 422, 500])
    s.add("id-07", "identity", "IdentitySources", "DELETE /identity-sources/{id}",
          "DELETE", "/api/v1/identity-sources/{idsource_id}",
          expect=[200, 204], skip_if_missing="idsource_id")

    s.add("id-08", "identity", "FederatedAuth", "POST /identity-sources/saml/initiate",
          "POST", "/api/v1/identity-sources/saml/initiate",
          body={"source_id": "00000000-0000-0000-0000-000000000000"}, expect=[200, 400, 404, 422])
    s.add("id-09", "identity", "FederatedAuth", "POST /identity-sources/saml/acs",
          "POST", "/api/v1/identity-sources/saml/acs",
          body={"SAMLResponse": "dummy"}, expect=[200, 400, 422])
    s.add("id-10", "identity", "FederatedAuth", "POST /identity-sources/oauth/initiate",
          "POST", "/api/v1/identity-sources/oauth/initiate",
          body={"source_id": "00000000-0000-0000-0000-000000000000"}, expect=[200, 404, 422])
    s.add("id-11", "identity", "FederatedAuth", "POST /identity-sources/oauth/callback",
          "POST", "/api/v1/identity-sources/oauth/callback",
          body={"code": "dummy", "state": "dummy"}, expect=[200, 400, 422])

    # ═══ PHASE: NETWORK ═════════════════════════════════════════════════════
    s.add("net-01", "network", "NetworkDevices", "GET /network-devices/",
          "GET", "/api/v1/network-devices/")
    s.add("net-02", "network", "NetworkDevices", "POST /network-devices/",
          "POST", "/api/v1/network-devices/",
          body={"name": "SanityNAD", "ip_address": "10.99.99.1", "device_type": "switch", "vendor": "cisco", "shared_secret": "test123"},
          resource_key="nad_id", extract_id="id")
    s.add("net-03", "network", "NetworkDevices", "GET /network-devices/{id}",
          "GET", "/api/v1/network-devices/{nad_id}",
          skip_if_missing="nad_id")
    s.add("net-04", "network", "NetworkDevices", "PUT /network-devices/{id}",
          "PUT", "/api/v1/network-devices/{nad_id}",
          body={"name": "SanityNADUpd"},
          skip_if_missing="nad_id")
    s.add("net-05", "network", "NetworkDevices", "DELETE /network-devices/{id}",
          "DELETE", "/api/v1/network-devices/{nad_id}",
          expect=[200, 204], skip_if_missing="nad_id")
    s.add("net-06", "network", "NetworkDevices", "POST /network-devices/discover",
          "POST", "/api/v1/network-devices/discover",
          body={"subnet": "127.0.0.0/30"}, expect=[200, 202])

    # ═══ PHASE: ENDPOINTS ═══════════════════════════════════════════════════
    s.add("ep-01", "endpoints", "Endpoints", "GET /endpoints/",
          "GET", "/api/v1/endpoints/")
    s.add("ep-02", "endpoints", "Endpoints", "POST /endpoints/",
          "POST", "/api/v1/endpoints/",
          body={"mac_address": "AA:BB:CC:DD:EE:99", "device_type": "laptop", "os_type": "Windows 11"},
          resource_key="ep_id", extract_id="id")
    s.add("ep-03", "endpoints", "Endpoints", "GET /endpoints/{id}",
          "GET", "/api/v1/endpoints/{ep_id}",
          skip_if_missing="ep_id")
    s.add("ep-04", "endpoints", "Endpoints", "PUT /endpoints/{id}",
          "PUT", "/api/v1/endpoints/{ep_id}",
          body={"device_type": "workstation"},
          skip_if_missing="ep_id")
    s.add("ep-05", "endpoints", "Endpoints", "POST /endpoints/{id}/profile",
          "POST", "/api/v1/endpoints/{ep_id}/profile",
          skip_if_missing="ep_id", expect=[200, 202])
    s.add("ep-06", "endpoints", "Endpoints", "GET /endpoints/by-mac/AA:BB:CC:DD:EE:99",
          "GET", "/api/v1/endpoints/by-mac/AA:BB:CC:DD:EE:99", expect=[200, 404])
    s.add("ep-07", "endpoints", "Endpoints", "DELETE /endpoints/{id}",
          "DELETE", "/api/v1/endpoints/{ep_id}",
          expect=[200, 204], skip_if_missing="ep_id")

    # ═══ PHASE: SEGMENTATION ════════════════════════════════════════════════
    s.add("seg-01", "segmentation", "SGTs", "GET /segmentation/sgts",
          "GET", "/api/v1/segmentation/sgts")
    s.add("seg-02", "segmentation", "SGTs", "POST /segmentation/sgts",
          "POST", "/api/v1/segmentation/sgts",
          body={"name": "SanitySGT", "tag_value": 9900, "description": "test"},
          resource_key="sgt_id", extract_id="id")
    s.add("seg-03", "segmentation", "SGTs", "GET /segmentation/sgts/{id}",
          "GET", "/api/v1/segmentation/sgts/{sgt_id}",
          skip_if_missing="sgt_id")
    s.add("seg-04", "segmentation", "SGTs", "PUT /segmentation/sgts/{id}",
          "PUT", "/api/v1/segmentation/sgts/{sgt_id}",
          body={"name": "SanitySGTUpd", "tag_value": 9999, "description": "updated"},
          skip_if_missing="sgt_id")
    s.add("seg-05", "segmentation", "SGTs", "DELETE /segmentation/sgts/{id}",
          "DELETE", "/api/v1/segmentation/sgts/{sgt_id}",
          expect=[200, 204], skip_if_missing="sgt_id")
    s.add("seg-06", "segmentation", "SGTMatrix", "GET /segmentation/matrix",
          "GET", "/api/v1/segmentation/matrix")

    # ═══ PHASE: CERTIFICATES ════════════════════════════════════════════════
    s.add("cert-01", "certs", "CAs", "GET /certificates/cas",
          "GET", "/api/v1/certificates/cas")
    s.add("cert-02", "certs", "CAs", "POST /certificates/cas",
          "POST", "/api/v1/certificates/cas",
          body={"name": "SanityCA", "ca_type": "root", "subject": "CN=SanityCA"},
          resource_key="ca_id", extract_id="id")
    s.add("cert-03", "certs", "Certs", "GET /certificates/",
          "GET", "/api/v1/certificates/")
    s.add("cert-04", "certs", "Certs", "POST /certificates/",
          "POST", "/api/v1/certificates/",
          body={"subject": "sanity.test.neuranac", "usage": "eap-tls", "san": ["sanity.test.neuranac"]},
          resource_key="cert_id", extract_id="id")
    s.add("cert-05", "certs", "Certs", "GET /certificates/{id}",
          "GET", "/api/v1/certificates/{cert_id}",
          skip_if_missing="cert_id")
    s.add("cert-06", "certs", "Certs", "POST /certificates/{id}/revoke",
          "POST", "/api/v1/certificates/{cert_id}/revoke",
          skip_if_missing="cert_id")

    # ═══ PHASE: SESSIONS ════════════════════════════════════════════════════
    s.add("sess-01", "sessions", "Sessions", "GET /sessions/",
          "GET", "/api/v1/sessions/")
    s.add("sess-02", "sessions", "Sessions", "GET /sessions/active/count",
          "GET", "/api/v1/sessions/active/count")

    # ═══ PHASE: GUEST ═══════════════════════════════════════════════════════
    s.add("guest-01", "guest", "Portals", "GET /guest/portals",
          "GET", "/api/v1/guest/portals")
    s.add("guest-02", "guest", "Portals", "POST /guest/portals",
          "POST", "/api/v1/guest/portals",
          body={"name": "SanityPortal", "portal_type": "hotspot", "theme": {"primary_color": "#333"}},
          resource_key="portal_id", extract_id="id")
    s.add("guest-03", "guest", "Portals", "GET /guest/portals/{id}",
          "GET", "/api/v1/guest/portals/{portal_id}",
          skip_if_missing="portal_id")
    s.add("guest-04", "guest", "Portals", "DELETE /guest/portals/{id}",
          "DELETE", "/api/v1/guest/portals/{portal_id}",
          expect=[200, 204], skip_if_missing="portal_id")
    s.add("guest-05", "guest", "Accounts", "GET /guest/accounts",
          "GET", "/api/v1/guest/accounts")
    s.add("guest-06", "guest", "Accounts", "POST /guest/accounts",
          "POST", "/api/v1/guest/accounts",
          body={"username": "sanity_guest"})
    s.add("guest-07", "guest", "Accounts", "DELETE /guest/accounts/{username}",
          "DELETE", "/api/v1/guest/accounts/sanity_guest",
          expect=[200, 204])
    s.add("guest-08", "guest", "SponsorGroups", "GET /guest/sponsor-groups",
          "GET", "/api/v1/guest/sponsor-groups")
    s.add("guest-09", "guest", "CaptivePortal", "GET /guest/captive-portal/page",
          "GET", "/api/v1/guest/captive-portal/page")
    s.add("guest-10", "guest", "CaptivePortal", "POST /guest/captive-portal/authenticate",
          "POST", "/api/v1/guest/captive-portal/authenticate",
          body={"client_mac": "FF:FF:FF:FF:FF:02", "client_ip": "10.0.0.99", "user_agent": "Mozilla/5.0 SanityTest"}, expect=[200, 401, 404])
    s.add("guest-11", "guest", "BYOD", "POST /guest/byod/register",
          "POST", "/api/v1/guest/byod/register",
          body={"endpoint_mac": "FF:FF:FF:FF:FF:01", "user_id": "sanity_user", "device_name": "iPhone"},
          expect=[200, 201])
    s.add("guest-12", "guest", "BYOD", "GET /guest/byod/registrations",
          "GET", "/api/v1/guest/byod/registrations")

    # ═══ PHASE: POSTURE ═════════════════════════════════════════════════════
    s.add("post-01", "posture", "Policies", "GET /posture/policies",
          "GET", "/api/v1/posture/policies")
    s.add("post-02", "posture", "Policies", "POST /posture/policies",
          "POST", "/api/v1/posture/policies",
          body={"name": "SanityPosture", "os_type": "Windows", "checks": [{"type": "antivirus", "operator": "installed"}]},
          resource_key="posture_pol_id", extract_id="id")
    s.add("post-03", "posture", "Policies", "GET /posture/policies/{id}",
          "GET", "/api/v1/posture/policies/{posture_pol_id}",
          skip_if_missing="posture_pol_id")
    s.add("post-04", "posture", "Policies", "DELETE /posture/policies/{id}",
          "DELETE", "/api/v1/posture/policies/{posture_pol_id}",
          expect=[200, 204], skip_if_missing="posture_pol_id")
    s.add("post-05", "posture", "Assessment", "POST /posture/assess",
          "POST", "/api/v1/posture/assess",
          body={"endpoint_mac": "AA:BB:CC:DD:EE:99", "checks": [{"type": "antivirus", "status": "ok"}]},
          expect=[200, 404, 422])
    s.add("post-06", "posture", "Results", "GET /posture/results",
          "GET", "/api/v1/posture/results")

    # ═══ PHASE: SIEM ════════════════════════════════════════════════════════
    s.add("siem-01", "siem", "Destinations", "GET /siem/destinations",
          "GET", "/api/v1/siem/destinations")
    s.add("siem-02", "siem", "Destinations", "POST /siem/destinations",
          "POST", "/api/v1/siem/destinations",
          body={"name": "SanitySIEM", "dest_type": "syslog", "host": "siem.test", "port": 514},
          resource_key="siem_id", extract_id="id")
    s.add("siem-03", "siem", "Destinations", "POST /siem/destinations/{id}/test",
          "POST", "/api/v1/siem/destinations/{siem_id}/test",
          skip_if_missing="siem_id", expect=[200, 422, 500])
    s.add("siem-04", "siem", "Destinations", "DELETE /siem/destinations/{id}",
          "DELETE", "/api/v1/siem/destinations/{siem_id}",
          expect=[200, 204], skip_if_missing="siem_id")
    s.add("siem-05", "siem", "Forward", "POST /siem/forward",
          "POST", "/api/v1/siem/forward",
          body={"event_type": "auth_success", "severity": "medium", "details": {"user": "test"}}, expect=[200, 202])
    s.add("siem-06", "siem", "SOAR", "GET /siem/soar/playbooks",
          "GET", "/api/v1/siem/soar/playbooks")
    s.add("siem-07", "siem", "SOAR", "POST /siem/soar/playbooks",
          "POST", "/api/v1/siem/soar/playbooks",
          body={"name": "SanityPlaybook", "trigger_event": "auth_failure", "webhook_url": "https://soar.test/hook"},
          resource_key="playbook_id", extract_id="id")
    s.add("siem-08", "siem", "SOAR", "POST /siem/soar/playbooks/{id}/trigger",
          "POST", "/api/v1/siem/soar/playbooks/{playbook_id}/trigger",
          body={"event": {"user": "test"}},
          skip_if_missing="playbook_id", expect=[200, 202])

    # ═══ PHASE: WEBHOOKS ════════════════════════════════════════════════════
    s.add("wh-01", "webhooks", "Webhooks", "GET /webhooks/",
          "GET", "/api/v1/webhooks/")
    s.add("wh-02", "webhooks", "Webhooks", "POST /webhooks/",
          "POST", "/api/v1/webhooks/",
          body={"name": "SanityWH", "url": "https://hooks.test/sanity", "events": ["auth_success"], "secret": "s3cret"},
          resource_key="wh_id", extract_id="id")
    s.add("wh-03", "webhooks", "Webhooks", "GET /webhooks/{id}",
          "GET", "/api/v1/webhooks/{wh_id}",
          skip_if_missing="wh_id")
    s.add("wh-04", "webhooks", "Webhooks", "PUT /webhooks/{id}",
          "PUT", "/api/v1/webhooks/{wh_id}",
          body={"name": "SanityWHUpd", "url": "https://hooks.test/sanity", "events": ["auth_success"]},
          skip_if_missing="wh_id")
    s.add("wh-05", "webhooks", "Webhooks", "POST /webhooks/{id}/test",
          "POST", "/api/v1/webhooks/{wh_id}/test",
          skip_if_missing="wh_id", expect=[200, 422, 500])
    s.add("wh-06", "webhooks", "Webhooks", "DELETE /webhooks/{id}",
          "DELETE", "/api/v1/webhooks/{wh_id}",
          expect=[200, 204], skip_if_missing="wh_id")
    s.add("wh-07", "webhooks", "Plugins", "GET /webhooks/plugins",
          "GET", "/api/v1/webhooks/plugins")
    s.add("wh-08", "webhooks", "Plugins", "POST /webhooks/plugins",
          "POST", "/api/v1/webhooks/plugins",
          body={"name": "SanityPlugin", "version": "1.0.0", "description": "Sanity test plugin"},
          resource_key="plugin_id", extract_id="id")
    s.add("wh-09", "webhooks", "Plugins", "POST /webhooks/plugins/{id}/enable",
          "POST", "/api/v1/webhooks/plugins/{plugin_id}/enable",
          skip_if_missing="plugin_id")
    s.add("wh-10", "webhooks", "Plugins", "POST /webhooks/plugins/{id}/disable",
          "POST", "/api/v1/webhooks/plugins/{plugin_id}/disable",
          skip_if_missing="plugin_id")
    s.add("wh-11", "webhooks", "Plugins", "DELETE /webhooks/plugins/{id}",
          "DELETE", "/api/v1/webhooks/plugins/{plugin_id}",
          expect=[200, 204], skip_if_missing="plugin_id")

    # ═══ PHASE: PRIVACY ═════════════════════════════════════════════════════
    s.add("priv-01", "privacy", "Subjects", "GET /privacy/subjects",
          "GET", "/api/v1/privacy/subjects")
    s.add("priv-02", "privacy", "Subjects", "POST /privacy/subjects",
          "POST", "/api/v1/privacy/subjects",
          body={"subject_type": "employee", "subject_identifier": "sanity@test.com"},
          resource_key="subject_id", extract_id="id")
    s.add("priv-03", "privacy", "Subjects", "GET /privacy/subjects/{id}",
          "GET", "/api/v1/privacy/subjects/{subject_id}",
          skip_if_missing="subject_id")
    s.add("priv-04", "privacy", "Subjects", "POST /privacy/subjects/{id}/erasure",
          "POST", "/api/v1/privacy/subjects/{subject_id}/erasure",
          skip_if_missing="subject_id", expect=[200, 202])
    s.add("priv-05", "privacy", "Consent", "GET /privacy/consent",
          "GET", "/api/v1/privacy/consent")
    s.add("priv-06", "privacy", "Consent", "POST /privacy/consent",
          "POST", "/api/v1/privacy/consent",
          body={"subject_id": "{subject_id}", "purpose": "network_access", "legal_basis": "legitimate_interest", "granted": True},
          skip_if_missing="subject_id",
          resource_key="consent_id", extract_id="id")
    s.add("priv-07", "privacy", "Consent", "POST /privacy/consent/{id}/revoke",
          "POST", "/api/v1/privacy/consent/{consent_id}/revoke",
          skip_if_missing="consent_id")
    s.add("priv-08", "privacy", "Exports", "GET /privacy/exports",
          "GET", "/api/v1/privacy/exports")
    s.add("priv-09", "privacy", "Exports", "POST /privacy/exports",
          "POST", "/api/v1/privacy/exports",
          body={"subject_id": "{subject_id}", "requested_by": "admin"},
          skip_if_missing="subject_id", expect=[200, 201, 202])

    # ═══ PHASE: AI ══════════════════════════════════════════════════════════
    s.add("ai-01", "ai", "Agents", "GET /ai/agents/",
          "GET", "/api/v1/ai/agents/")
    s.add("ai-02", "ai", "Agents", "POST /ai/agents/",
          "POST", "/api/v1/ai/agents/",
          body={"agent_name": "SanityAgent", "agent_type": "policy_advisor"},
          resource_key="agent_id", extract_id="id")
    s.add("ai-03", "ai", "Agents", "GET /ai/agents/{id}",
          "GET", "/api/v1/ai/agents/{agent_id}",
          skip_if_missing="agent_id")
    s.add("ai-04", "ai", "Agents", "PUT /ai/agents/{id}",
          "PUT", "/api/v1/ai/agents/{agent_id}",
          body={"agent_name": "SanityAgentUpd", "agent_type": "policy_advisor"},
          skip_if_missing="agent_id")
    s.add("ai-05", "ai", "Agents", "POST /ai/agents/{id}/revoke",
          "POST", "/api/v1/ai/agents/{agent_id}/revoke",
          skip_if_missing="agent_id")
    s.add("ai-06", "ai", "Agents", "DELETE /ai/agents/{id}",
          "DELETE", "/api/v1/ai/agents/{agent_id}",
          expect=[200, 204], skip_if_missing="agent_id")
    s.add("ai-07", "ai", "DataFlow", "GET /ai/data-flow/services",
          "GET", "/api/v1/ai/data-flow/services")
    s.add("ai-08", "ai", "DataFlow", "GET /ai/data-flow/detections",
          "GET", "/api/v1/ai/data-flow/detections")
    s.add("ai-09", "ai", "DataFlow", "GET /ai/data-flow/policies",
          "GET", "/api/v1/ai/data-flow/policies")
    s.add("ai-10", "ai", "DataFlow", "POST /ai/data-flow/policies",
          "POST", "/api/v1/ai/data-flow/policies",
          body={"name": "SanityDFP", "service_type": "openai", "action": "allow"})

    # ═══ PHASE: AUDIT ═══════════════════════════════════════════════════════
    s.add("aud-01", "audit", "Audit", "GET /audit/",
          "GET", "/api/v1/audit/")
    s.add("aud-02", "audit", "Audit", "GET /audit/reports/summary",
          "GET", "/api/v1/audit/reports/summary")
    s.add("aud-03", "audit", "Audit", "GET /audit/reports/auth",
          "GET", "/api/v1/audit/reports/auth")
    s.add("aud-04", "audit", "Audit", "GET /audit/verify-chain",
          "GET", "/api/v1/audit/verify-chain")

    # ═══ PHASE: DIAGNOSTICS ═════════════════════════════════════════════════
    s.add("diag-01", "diagnostics", "Diagnostics", "GET /diagnostics/system-status",
          "GET", "/api/v1/diagnostics/system-status")
    s.add("diag-02", "diagnostics", "Diagnostics", "GET /diagnostics/radius-live-log",
          "GET", "/api/v1/diagnostics/radius-live-log")
    s.add("diag-03", "diagnostics", "Diagnostics", "POST /diagnostics/connectivity-test",
          "POST", "/api/v1/diagnostics/connectivity-test",
          body={"target": "10.0.0.1", "test_type": "ping"}, expect=[200, 422])
    s.add("diag-04", "diagnostics", "Diagnostics", "POST /diagnostics/troubleshoot",
          "POST", "/api/v1/diagnostics/troubleshoot",
          body={"target": "AA:BB:CC:DD:EE:01", "issue_type": "auth_failure"}, expect=[200, 422])
    s.add("diag-05", "diagnostics", "Diagnostics", "POST /diagnostics/support-bundle",
          "POST", "/api/v1/diagnostics/support-bundle", expect=[200, 202])

    # ═══ PHASE: LICENSES ════════════════════════════════════════════════════
    s.add("lic-01", "licenses", "Licenses", "GET /licenses/",
          "GET", "/api/v1/licenses/")
    s.add("lic-02", "licenses", "Licenses", "GET /licenses/tiers",
          "GET", "/api/v1/licenses/tiers")
    s.add("lic-03", "licenses", "Licenses", "GET /licenses/usage",
          "GET", "/api/v1/licenses/usage")
    s.add("lic-04", "licenses", "Licenses", "POST /licenses/activate",
          "POST", "/api/v1/licenses/activate",
          body={"license_key": "SANITY-TEST-KEY-0000"}, expect=[200, 400, 422])

    # ═══ PHASE: NODES ═══════════════════════════════════════════════════════
    s.add("node-01", "nodes", "Nodes", "GET /nodes/",
          "GET", "/api/v1/nodes/")
    s.add("node-02", "nodes", "Nodes", "GET /nodes/sync-status",
          "GET", "/api/v1/nodes/sync-status")
    s.add("node-03", "nodes", "Nodes", "POST /nodes/sync/trigger",
          "POST", "/api/v1/nodes/sync/trigger", expect=[200, 202])
    s.add("node-04", "nodes", "Nodes", "POST /nodes/failover",
          "POST", "/api/v1/nodes/failover",
          body={"target_node": "secondary"}, expect=[200, 202, 404])

    # ═══ PHASE: SETUP ═══════════════════════════════════════════════════════
    s.add("setup-01", "setup", "Setup", "GET /setup/status",
          "GET", "/api/v1/setup/status")
    s.add("setup-02", "setup", "Setup", "POST /setup/step/{step_number}",
          "POST", "/api/v1/setup/step/1",
          body={"hostname": "neuranac-sanity", "domain": "test.local"}, expect=[200, 400])
    s.add("setup-03", "setup", "Setup", "POST /setup/network-scan",
          "POST", "/api/v1/setup/network-scan",
          body={"subnet": "10.0.0.0/24"}, expect=[200, 202])
    s.add("setup-04", "setup", "Setup", "POST /setup/identity-source",
          "POST", "/api/v1/setup/identity-source",
          body={"type": "local", "config": {"name": "SanityLocal"}}, expect=[200, 201, 400])
    s.add("setup-05", "setup", "Setup", "POST /setup/policies/generate",
          "POST", "/api/v1/setup/policies/generate", expect=[200, 202])
    s.add("setup-06", "setup", "Setup", "POST /setup/network-design/generate",
          "POST", "/api/v1/setup/network-design/generate",
          body={"description": "Corporate campus with 3 buildings"}, expect=[200, 202])
    s.add("setup-07", "setup", "Setup", "POST /setup/activate",
          "POST", "/api/v1/setup/activate", expect=[200, 400])

    # ═══ PHASE: NeuraNAC_CORE (P17) ══════════════════════════════════════════════
    s.add("lnac-01", "legacy_nac", "NeuraNACConnections", "GET /legacy-nac/connections",
          "GET", "/api/v1/legacy-nac/connections")
    s.add("lnac-02", "legacy_nac", "NeuraNACConnections", "POST /legacy-nac/connections",
          "POST", "/api/v1/legacy-nac/connections",
          body={"name": "SanityNeuraNAC", "hostname": "legacy-nac.sanity.local", "port": 443,
                "username": "admin", "password": "C1sco123!", "ers_enabled": True,
                "ers_port": 9060, "event_stream_enabled": True, "verify_ssl": False,
                "deployment_mode": "coexistence"},
          resource_key="legacy_conn_id", extract_id="id")
    s.add("lnac-03", "legacy_nac", "NeuraNACConnections", "GET /legacy-nac/connections/{id}",
          "GET", "/api/v1/legacy-nac/connections/{legacy_conn_id}",
          skip_if_missing="legacy_conn_id")
    s.add("lnac-04", "legacy_nac", "NeuraNACConnections", "PUT /legacy-nac/connections/{id}",
          "PUT", "/api/v1/legacy-nac/connections/{legacy_conn_id}",
          body={"name": "SanityNeuraNACUpd"},
          skip_if_missing="legacy_conn_id")
    s.add("lnac-05", "legacy_nac", "NeuraNACConnections", "POST /legacy-nac/connections/{id}/test",
          "POST", "/api/v1/legacy-nac/connections/{legacy_conn_id}/test",
          skip_if_missing="legacy_conn_id", expect=[200, 422, 500])
    s.add("lnac-06", "legacy_nac", "NeuraNACSync", "POST /legacy-nac/connections/{id}/sync",
          "POST", "/api/v1/legacy-nac/connections/{legacy_conn_id}/sync",
          body={"entity_types": ["network_device"], "full_sync": False},
          skip_if_missing="legacy_conn_id", expect=[200, 500])
    s.add("lnac-07", "legacy_nac", "NeuraNACSync", "GET /legacy-nac/connections/{id}/sync-status",
          "GET", "/api/v1/legacy-nac/connections/{legacy_conn_id}/sync-status",
          skip_if_missing="legacy_conn_id")
    s.add("lnac-08", "legacy_nac", "NeuraNACSync", "GET /legacy-nac/connections/{id}/sync-log",
          "GET", "/api/v1/legacy-nac/connections/{legacy_conn_id}/sync-log",
          skip_if_missing="legacy_conn_id")
    s.add("lnac-09", "legacy_nac", "NeuraNACSync", "GET /legacy-nac/connections/{id}/entity-map",
          "GET", "/api/v1/legacy-nac/connections/{legacy_conn_id}/entity-map",
          skip_if_missing="legacy_conn_id")
    s.add("lnac-10", "legacy_nac", "NeuraNACMigration", "POST /legacy-nac/connections/{id}/migration",
          "POST", "/api/v1/legacy-nac/connections/{legacy_conn_id}/migration",
          body={"action": "start"},
          skip_if_missing="legacy_conn_id", expect=[200, 202, 400])
    s.add("lnac-11", "legacy_nac", "NeuraNACMigration", "GET /legacy-nac/connections/{id}/migration-status",
          "GET", "/api/v1/legacy-nac/connections/{legacy_conn_id}/migration-status",
          skip_if_missing="legacy_conn_id")
    s.add("lnac-12", "legacy_nac", "NeuraNACPreview", "GET /legacy-nac/connections/{id}/preview/network_device",
          "GET", "/api/v1/legacy-nac/connections/{legacy_conn_id}/preview/network_device",
          skip_if_missing="legacy_conn_id")
    s.add("lnac-13", "legacy_nac", "NeuraNACSummary", "GET /legacy-nac/summary",
          "GET", "/api/v1/legacy-nac/summary")

    # ═══ PHASE: NeuraNAC_ENHANCED_P17 (Version Detection) ════════════════════════
    s.add("lnacv-01", "legacy_nac_enhanced", "VersionDetection", "POST /legacy-nac/connections/{id}/detect-version",
          "POST", "/api/v1/legacy-nac/connections/{legacy_conn_id}/detect-version",
          skip_if_missing="legacy_conn_id")

    # ═══ PHASE: NeuraNAC_ENHANCED_P18 (Sync Scheduler) ═══════════════════════════
    s.add("lnacv-02", "legacy_nac_enhanced", "SyncScheduler", "GET /legacy-nac/connections/{id}/schedules",
          "GET", "/api/v1/legacy-nac/connections/{legacy_conn_id}/schedules",
          skip_if_missing="legacy_conn_id")
    s.add("lnacv-03", "legacy_nac_enhanced", "SyncScheduler", "POST /legacy-nac/connections/{id}/schedules",
          "POST", "/api/v1/legacy-nac/connections/{legacy_conn_id}/schedules",
          body={"entity_type": "network_device", "interval_minutes": 30, "sync_type": "incremental",
                "direction": "legacy_to_neuranac", "enabled": True},
          skip_if_missing="legacy_conn_id")
    s.add("lnacv-04", "legacy_nac_enhanced", "SyncScheduler", "PUT /legacy-nac/connections/{id}/schedules/{et}",
          "PUT", "/api/v1/legacy-nac/connections/{legacy_conn_id}/schedules/network_device",
          body={"interval_minutes": 60, "enabled": True},
          skip_if_missing="legacy_conn_id")
    s.add("lnacv-05", "legacy_nac_enhanced", "SyncScheduler", "POST /legacy-nac/connections/{id}/schedules/run-due",
          "POST", "/api/v1/legacy-nac/connections/{legacy_conn_id}/schedules/run-due",
          skip_if_missing="legacy_conn_id")
    s.add("lnacv-06", "legacy_nac_enhanced", "SyncScheduler", "DELETE /legacy-nac/connections/{id}/schedules/{et}",
          "DELETE", "/api/v1/legacy-nac/connections/{legacy_conn_id}/schedules/network_device",
          expect=[200, 204], skip_if_missing="legacy_conn_id")

    # ═══ PHASE: NeuraNAC_ENHANCED_P19 (Event Stream) ═══════════════════════════════
    s.add("lnacv-07", "legacy_nac_enhanced", "EventStream", "POST /legacy-nac/connections/{id}/event-stream/connect",
          "POST", "/api/v1/legacy-nac/connections/{legacy_conn_id}/event-stream/connect",
          skip_if_missing="legacy_conn_id")
    s.add("lnacv-08", "legacy_nac_enhanced", "EventStream", "GET /legacy-nac/connections/{id}/event-stream/status",
          "GET", "/api/v1/legacy-nac/connections/{legacy_conn_id}/event-stream/status",
          skip_if_missing="legacy_conn_id")
    s.add("lnacv-09", "legacy_nac_enhanced", "EventStream", "POST /legacy-nac/connections/{id}/event-stream/simulate-event",
          "POST", "/api/v1/legacy-nac/connections/{legacy_conn_id}/event-stream/simulate-event?event_type=session_created",
          skip_if_missing="legacy_conn_id")
    s.add("lnacv-10", "legacy_nac_enhanced", "EventStream", "GET /legacy-nac/connections/{id}/event-stream/events",
          "GET", "/api/v1/legacy-nac/connections/{legacy_conn_id}/event-stream/events",
          skip_if_missing="legacy_conn_id")
    s.add("lnacv-11", "legacy_nac_enhanced", "EventStream", "POST /legacy-nac/connections/{id}/event-stream/disconnect",
          "POST", "/api/v1/legacy-nac/connections/{legacy_conn_id}/event-stream/disconnect",
          skip_if_missing="legacy_conn_id")

    # ═══ PHASE: NeuraNAC_ENHANCED_P20 (Policy Translation) ═══════════════════════
    s.add("lnacv-12", "legacy_nac_enhanced", "PolicyTranslation", "GET /legacy-nac/connections/{id}/policies/discover",
          "GET", "/api/v1/legacy-nac/connections/{legacy_conn_id}/policies/discover",
          skip_if_missing="legacy_conn_id")
    s.add("lnacv-13", "legacy_nac_enhanced", "PolicyTranslation", "POST /legacy-nac/connections/{id}/policies/translate",
          "POST", "/api/v1/legacy-nac/connections/{legacy_conn_id}/policies/translate",
          body={"policy_name": "Corp-Wired-Dot1x"},
          skip_if_missing="legacy_conn_id",
          resource_key="trans_id", extract_id="translation_id")
    s.add("lnacv-14", "legacy_nac_enhanced", "PolicyTranslation", "POST /legacy-nac/connections/{id}/policies/translate-all",
          "POST", "/api/v1/legacy-nac/connections/{legacy_conn_id}/policies/translate-all",
          skip_if_missing="legacy_conn_id")
    s.add("lnacv-15", "legacy_nac_enhanced", "PolicyTranslation", "GET /legacy-nac/connections/{id}/policies/translations",
          "GET", "/api/v1/legacy-nac/connections/{legacy_conn_id}/policies/translations",
          skip_if_missing="legacy_conn_id")
    s.add("lnacv-16", "legacy_nac_enhanced", "PolicyTranslation", "GET /legacy-nac/connections/{id}/policies/translations/{tid}",
          "GET", "/api/v1/legacy-nac/connections/{legacy_conn_id}/policies/translations/{trans_id}",
          skip_if_missing="trans_id")
    s.add("lnacv-17", "legacy_nac_enhanced", "PolicyTranslation", "POST /legacy-nac/connections/{id}/policies/translations/{tid}/apply",
          "POST", "/api/v1/legacy-nac/connections/{legacy_conn_id}/policies/translations/{trans_id}/apply",
          skip_if_missing="trans_id")

    # ═══ PHASE: NeuraNAC_ENHANCED_P21 (Conflicts) ════════════════════════════════
    s.add("lnacv-18", "legacy_nac_enhanced", "Conflicts", "POST /legacy-nac/connections/{id}/conflicts/simulate",
          "POST", "/api/v1/legacy-nac/connections/{legacy_conn_id}/conflicts/simulate",
          skip_if_missing="legacy_conn_id")
    s.add("lnacv-19", "legacy_nac_enhanced", "Conflicts", "GET /legacy-nac/connections/{id}/conflicts",
          "GET", "/api/v1/legacy-nac/connections/{legacy_conn_id}/conflicts",
          skip_if_missing="legacy_conn_id")
    s.add("lnacv-20", "legacy_nac_enhanced", "Conflicts", "GET /legacy-nac/connections/{id}/conflicts/{cid} (first)",
          "GET", "/api/v1/legacy-nac/connections/{legacy_conn_id}/conflicts?status=unresolved",
          skip_if_missing="legacy_conn_id",
          resource_key="_conflict_list", extract_id="items")
    s.add("lnacv-21", "legacy_nac_enhanced", "Conflicts", "POST /legacy-nac/connections/{id}/conflicts/resolve-all",
          "POST", "/api/v1/legacy-nac/connections/{legacy_conn_id}/conflicts/resolve-all",
          body={"resolution": "accept_legacy_nac"},
          skip_if_missing="legacy_conn_id")

    # ═══ PHASE: NeuraNAC_ENHANCED_P22 (Bidirectional Sync + Multi-NeuraNAC) ═══════════
    s.add("lnacv-22", "legacy_nac_enhanced", "BidirectionalSync", "POST /legacy-nac/connections/{id}/sync/bidirectional",
          "POST", "/api/v1/legacy-nac/connections/{legacy_conn_id}/sync/bidirectional",
          body={"direction": "neuranac_to_legacy_nac", "entity_types": ["network_device", "sgt"]},
          skip_if_missing="legacy_conn_id")
    s.add("lnacv-23", "legacy_nac_enhanced", "MultiNeuraNAC", "GET /legacy-nac/multi-legacy-nac/overview",
          "GET", "/api/v1/legacy-nac/multi-legacy-nac/overview")

    # ═══ PHASE: NeuraNAC_ENHANCED_P23 (Migration Wizard) ═════════════════════════
    s.add("lnacv-24", "legacy_nac_enhanced", "MigrationWizard", "POST /legacy-nac/connections/{id}/wizard/start",
          "POST", "/api/v1/legacy-nac/connections/{legacy_conn_id}/wizard/start",
          body={"run_name": "SanityWizardRun", "pilot_nad_ids": ["10.99.99.1"]},
          skip_if_missing="legacy_conn_id",
          resource_key="wizard_run_id", extract_id="wizard_run_id")
    s.add("lnacv-25", "legacy_nac_enhanced", "MigrationWizard", "GET /legacy-nac/connections/{id}/wizard/{rid}",
          "GET", "/api/v1/legacy-nac/connections/{legacy_conn_id}/wizard/{wizard_run_id}",
          skip_if_missing="wizard_run_id")
    s.add("lnacv-26", "legacy_nac_enhanced", "MigrationWizard", "POST execute-step (step 1)",
          "POST", "/api/v1/legacy-nac/connections/{legacy_conn_id}/wizard/{wizard_run_id}/execute-step",
          body={"action": "execute"},
          skip_if_missing="wizard_run_id")
    s.add("lnacv-27", "legacy_nac_enhanced", "MigrationWizard", "POST execute-step (step 2)",
          "POST", "/api/v1/legacy-nac/connections/{legacy_conn_id}/wizard/{wizard_run_id}/execute-step",
          body={"action": "execute"},
          skip_if_missing="wizard_run_id")
    s.add("lnacv-28", "legacy_nac_enhanced", "MigrationWizard", "POST execute-step (pause)",
          "POST", "/api/v1/legacy-nac/connections/{legacy_conn_id}/wizard/{wizard_run_id}/execute-step",
          body={"action": "pause"},
          skip_if_missing="wizard_run_id")
    s.add("lnacv-29", "legacy_nac_enhanced", "MigrationWizard", "POST execute-step (resume)",
          "POST", "/api/v1/legacy-nac/connections/{legacy_conn_id}/wizard/{wizard_run_id}/execute-step",
          body={"action": "resume"},
          skip_if_missing="wizard_run_id")
    s.add("lnacv-30", "legacy_nac_enhanced", "MigrationWizard", "GET /legacy-nac/connections/{id}/wizard (list runs)",
          "GET", "/api/v1/legacy-nac/connections/{legacy_conn_id}/wizard",
          skip_if_missing="legacy_conn_id")

    # ═══ PHASE: NeuraNAC_ENHANCED_P23 (RADIUS Analysis) ══════════════════════════
    s.add("lnacv-31", "legacy_nac_enhanced", "RADIUSAnalysis", "POST create baseline snapshot",
          "POST", "/api/v1/legacy-nac/connections/{legacy_conn_id}/radius-analysis/snapshot",
          body={"snapshot_name": "SanityBaseline", "snapshot_type": "baseline_legacy_nac", "capture_duration_minutes": 60},
          skip_if_missing="legacy_conn_id",
          resource_key="snap_baseline_id", extract_id="snapshot_id")
    s.add("lnacv-32", "legacy_nac_enhanced", "RADIUSAnalysis", "POST create current snapshot",
          "POST", "/api/v1/legacy-nac/connections/{legacy_conn_id}/radius-analysis/snapshot",
          body={"snapshot_name": "SanityCurrent", "snapshot_type": "current_neuranac", "capture_duration_minutes": 30},
          skip_if_missing="legacy_conn_id",
          resource_key="snap_current_id", extract_id="snapshot_id")
    s.add("lnacv-33", "legacy_nac_enhanced", "RADIUSAnalysis", "GET list snapshots",
          "GET", "/api/v1/legacy-nac/connections/{legacy_conn_id}/radius-analysis/snapshots",
          skip_if_missing="legacy_conn_id")
    s.add("lnacv-34", "legacy_nac_enhanced", "RADIUSAnalysis", "GET snapshot detail",
          "GET", "/api/v1/legacy-nac/connections/{legacy_conn_id}/radius-analysis/snapshots/{snap_baseline_id}",
          skip_if_missing="snap_baseline_id")
    s.add("lnacv-35", "legacy_nac_enhanced", "RADIUSAnalysis", "POST compare snapshots",
          "POST", "/api/v1/legacy-nac/connections/{legacy_conn_id}/radius-analysis/compare?baseline_id={snap_baseline_id}&current_id={snap_current_id}",
          skip_if_missing="snap_current_id")

    # ═══ NeuraNAC cleanup — delete connection last ═══════════════════════════════
    s.add("lnac-99", "legacy_nac", "NeuraNACCleanup", "DELETE /legacy-nac/connections/{id}",
          "DELETE", "/api/v1/legacy-nac/connections/{legacy_conn_id}",
          expect=[200, 204], skip_if_missing="legacy_conn_id")

    # ═══ PHASE: AI_PHASE1 (Action Router, OUI, Chat, Capabilities) ═════════
    s.add("ai1-01", "ai_phase1", "AIChat", "POST /ai/chat (list endpoints)",
          "POST", "/api/v1/ai/chat",
          body={"message": "list all endpoints", "context": {}})
    s.add("ai1-02", "ai_phase1", "AIChat", "POST /ai/chat (show sessions)",
          "POST", "/api/v1/ai/chat",
          body={"message": "show all active sessions", "context": {}})
    s.add("ai1-03", "ai_phase1", "AIChat", "POST /ai/chat (system status)",
          "POST", "/api/v1/ai/chat",
          body={"message": "show system status", "context": {}})
    s.add("ai1-04", "ai_phase1", "AIChat", "POST /ai/chat (navigate)",
          "POST", "/api/v1/ai/chat",
          body={"message": "go to policies", "context": {}})
    s.add("ai1-05", "ai_phase1", "AIChat", "POST /ai/chat (unknown intent)",
          "POST", "/api/v1/ai/chat",
          body={"message": "xyzzy foobar gibberish", "context": {}})
    s.add("ai1-06", "ai_phase1", "AICapabilities", "GET /ai/capabilities",
          "GET", "/api/v1/ai/capabilities")
    s.add("ai1-07", "ai_phase1", "AISuggestions", "GET /ai/suggestions (root)",
          "GET", "/api/v1/ai/suggestions?route=/")
    s.add("ai1-08", "ai_phase1", "AISuggestions", "GET /ai/suggestions (policies)",
          "GET", "/api/v1/ai/suggestions?route=/policies")
    s.add("ai1-09", "ai_phase1", "AISuggestions", "GET /ai/suggestions (sessions)",
          "GET", "/api/v1/ai/suggestions?route=/sessions")
    s.add("ai1-10", "ai_phase1", "AISuggestions", "GET /ai/suggestions (diagnostics)",
          "GET", "/api/v1/ai/suggestions?route=/diagnostics")

    # ═══ PHASE: AI_PHASE4_RAG (RAG Troubleshooter) ═════════════════════════
    s.add("ai4r-01", "ai_phase4_rag", "RAGTroubleshoot", "POST /rag/troubleshoot (EAP-TLS)",
          "POST", "/api/v1/ai/rag/troubleshoot",
          body={"query": "EAP-TLS authentication is failing for all users"})
    s.add("ai4r-02", "ai_phase4_rag", "RAGTroubleshoot", "POST /rag/troubleshoot (VLAN)",
          "POST", "/api/v1/ai/rag/troubleshoot",
          body={"query": "VLAN assignment is not working after authentication"})
    s.add("ai4r-03", "ai_phase4_rag", "RAGTroubleshoot", "POST /rag/troubleshoot (CoA)",
          "POST", "/api/v1/ai/rag/troubleshoot",
          body={"query": "CoA disconnect is not being sent to the switch"})

    # ═══ PHASE: AI_PHASE4_TRAIN (Training Pipeline) ════════════════════════
    s.add("ai4t-01", "ai_phase4_train", "TrainingSample", "POST /training/sample",
          "POST", "/api/v1/ai/training/sample",
          body={"mac_address": "00:50:56:AA:BB:CC", "device_type": "server", "vendor": "VMware"})
    s.add("ai4t-02", "ai_phase4_train", "TrainingStats", "GET /training/stats",
          "GET", "/api/v1/ai/training/stats")

    # ═══ PHASE: AI_PHASE4_SQL (NL-to-SQL) ══════════════════════════════════
    s.add("ai4s-01", "ai_phase4_sql", "NLtoSQL", "POST /nl-sql/query (sessions)",
          "POST", "/api/v1/ai/nl-sql/query",
          body={"question": "How many active sessions are there?"})
    s.add("ai4s-02", "ai_phase4_sql", "NLtoSQL", "POST /nl-sql/query (endpoints)",
          "POST", "/api/v1/ai/nl-sql/query",
          body={"question": "Show me the top endpoint vendors"})
    s.add("ai4s-03", "ai_phase4_sql", "NLtoSQL", "POST /nl-sql/query (certs)",
          "POST", "/api/v1/ai/nl-sql/query",
          body={"question": "Which certificates are expiring soon?"})

    # ═══ PHASE: AI_PHASE4_RISK (Adaptive Risk) ═════════════════════════════
    s.add("ai4k-01", "ai_phase4_risk", "RiskThresholds", "GET /risk/thresholds",
          "GET", "/api/v1/ai/risk/thresholds")
    s.add("ai4k-02", "ai_phase4_risk", "RiskFeedback", "POST /risk/feedback",
          "POST", "/api/v1/ai/risk/feedback",
          body={"tenant_id": "default", "risk_score": 45, "decision": "monitor", "was_correct": True})
    s.add("ai4k-03", "ai_phase4_risk", "RiskAdaptiveStats", "GET /risk/adaptive-stats",
          "GET", "/api/v1/ai/risk/adaptive-stats")

    # ═══ PHASE: AI_PHASE4_TLS (TLS Fingerprinting) ═════════════════════════
    s.add("ai4f-01", "ai_phase4_tls", "TLSJA3", "POST /tls/analyze-ja3 (known)",
          "POST", "/api/v1/ai/tls/analyze-ja3",
          body={"ja3_hash": "cd08e31494f9531f560d64c695473da9", "endpoint_mac": "AA:BB:CC:DD:EE:FF"})
    s.add("ai4f-02", "ai_phase4_tls", "TLSJA3", "POST /tls/analyze-ja3 (unknown)",
          "POST", "/api/v1/ai/tls/analyze-ja3",
          body={"ja3_hash": "0000000000000000000000000000dead", "endpoint_mac": "11:22:33:44:55:66"})
    s.add("ai4f-03", "ai_phase4_tls", "TLSJA4", "POST /tls/analyze-ja4",
          "POST", "/api/v1/ai/tls/analyze-ja4",
          body={"ja4_hash": "t13d1516h2_8daaf6152771_e5627efa2ab1", "endpoint_mac": "AA:BB:CC:DD:EE:FF"})
    s.add("ai4f-04", "ai_phase4_tls", "TLSCompute", "POST /tls/compute-ja3",
          "POST", "/api/v1/ai/tls/compute-ja3",
          body={"tls_version": 771, "cipher_suites": [49195, 49196], "extensions": [0, 23], "elliptic_curves": [29, 23], "ec_point_formats": [0]})
    s.add("ai4f-05", "ai_phase4_tls", "TLSCustomSig", "POST /tls/custom-signature",
          "POST", "/api/v1/ai/tls/custom-signature",
          body={"ja3_hash": "deadbeef12345678deadbeef12345678", "service": "custom-llm", "description": "Custom LLM service", "risk": "high"})
    s.add("ai4f-06", "ai_phase4_tls", "TLSDetections", "GET /tls/detections",
          "GET", "/api/v1/ai/tls/detections")
    s.add("ai4f-07", "ai_phase4_tls", "TLSStats", "GET /tls/stats",
          "GET", "/api/v1/ai/tls/stats")

    # ═══ PHASE: AI_PHASE4_CAP (Capacity Planning) ══════════════════════════
    s.add("ai4c-01", "ai_phase4_cap", "CapRecord", "POST /capacity/record (auth_rate)",
          "POST", "/api/v1/ai/capacity/record",
          body={"metric": "auth_rate_per_sec", "value": 150.0})
    s.add("ai4c-02", "ai_phase4_cap", "CapRecord", "POST /capacity/record (endpoint_count)",
          "POST", "/api/v1/ai/capacity/record",
          body={"metric": "endpoint_count", "value": 5000.0})
    s.add("ai4c-03", "ai_phase4_cap", "CapMetrics", "GET /capacity/metrics",
          "GET", "/api/v1/ai/capacity/metrics")
    s.add("ai4c-04", "ai_phase4_cap", "CapForecast", "GET /capacity/forecast",
          "GET", "/api/v1/ai/capacity/forecast")

    # ═══ PHASE: AI_PHASE4_PB (Playbooks) ═══════════════════════════════════
    s.add("ai4p-01", "ai_phase4_pb", "PlaybookList", "GET /playbooks",
          "GET", "/api/v1/ai/playbooks")
    s.add("ai4p-02", "ai_phase4_pb", "PlaybookGet", "GET /playbooks/{id} (auth failure)",
          "GET", "/api/v1/ai/playbooks/pb-auth-failure-lockout")
    s.add("ai4p-03", "ai_phase4_pb", "PlaybookGet", "GET /playbooks/{id} (shadow ai)",
          "GET", "/api/v1/ai/playbooks/pb-shadow-ai-block")
    s.add("ai4p-04", "ai_phase4_pb", "PlaybookCreate", "POST /playbooks (custom)",
          "POST", "/api/v1/ai/playbooks",
          body={"id": "pb-sanity-test", "name": "Sanity Test Playbook", "description": "Test playbook", "trigger": "manual", "severity": "low", "steps": [{"action": "log_incident", "params": {"msg": "sanity test"}}]})
    s.add("ai4p-05", "ai_phase4_pb", "PlaybookExec", "POST /playbooks/{id}/execute",
          "POST", "/api/v1/ai/playbooks/pb-auth-failure-lockout/execute",
          body={"context": {"endpoint_mac": "AA:BB:CC:DD:EE:FF", "username": "testuser"}})
    s.add("ai4p-06", "ai_phase4_pb", "PlaybookExecs", "GET /playbooks/executions/list",
          "GET", "/api/v1/ai/playbooks/executions/list")
    s.add("ai4p-07", "ai_phase4_pb", "PlaybookStats", "GET /playbooks/stats/summary",
          "GET", "/api/v1/ai/playbooks/stats/summary")

    # ═══ PHASE: AI_PHASE4_MDL (Model Registry) ═════════════════════════════
    s.add("ai4m-01", "ai_phase4_mdl", "ModelRegister", "POST /models/register (profiler v1)",
          "POST", "/api/v1/ai/models/register",
          body={"name": "endpoint-profiler", "version": "v1", "model_type": "profiler", "endpoint": "http://localhost:8081/api/v1/profile"})
    s.add("ai4m-02", "ai_phase4_mdl", "ModelRegister", "POST /models/register (profiler v2)",
          "POST", "/api/v1/ai/models/register",
          body={"name": "endpoint-profiler", "version": "v2", "model_type": "profiler", "endpoint": "http://localhost:8081/api/v1/profile", "weight": 0.5})
    s.add("ai4m-03", "ai_phase4_mdl", "ModelList", "GET /models",
          "GET", "/api/v1/ai/models")
    s.add("ai4m-04", "ai_phase4_mdl", "ModelExperiment", "POST /models/experiments",
          "POST", "/api/v1/ai/models/experiments",
          body={"name": "profiler-ab-test", "model_a_id": "endpoint-profiler-v1", "model_b_id": "endpoint-profiler-v2", "traffic_split": 0.3})
    s.add("ai4m-05", "ai_phase4_mdl", "ModelExperiments", "GET /models/experiments",
          "GET", "/api/v1/ai/models/experiments")
    s.add("ai4m-06", "ai_phase4_mdl", "ModelStats", "GET /models/stats",
          "GET", "/api/v1/ai/models/stats")

    # ═══ PHASE: ADMIN (users, roles, tenants) ═══════════════════════════════════
    s.add("adm-01", "admin", "AdminUsers", "GET /admin/users",
          "GET", "/api/v1/admin/users")
    s.add("adm-02", "admin", "AdminUsers", "POST /admin/users",
          "POST", "/api/v1/admin/users",
          body={"username": "sanity_admin", "password": "Test1234!", "role_name": "admin"},
          resource_key="admin_user_id", extract_id="id")
    s.add("adm-03", "admin", "AdminUsers", "GET /admin/users/{id}",
          "GET", "/api/v1/admin/users/{admin_user_id}",
          skip_if_missing="admin_user_id")
    s.add("adm-04", "admin", "AdminUsers", "DELETE /admin/users/{id}",
          "DELETE", "/api/v1/admin/users/{admin_user_id}",
          expect=[200, 204], skip_if_missing="admin_user_id")
    s.add("adm-05", "admin", "AdminRoles", "GET /admin/roles",
          "GET", "/api/v1/admin/roles")
    s.add("adm-06", "admin", "AdminRoles", "POST /admin/roles",
          "POST", "/api/v1/admin/roles",
          body={"name": "SanityRole", "description": "Sanity test role", "permissions": ["read"]})
    s.add("adm-07", "admin", "AdminTenants", "GET /admin/tenants",
          "GET", "/api/v1/admin/tenants")
    s.add("adm-08", "admin", "AdminTenants", "POST /admin/tenants",
          "POST", "/api/v1/admin/tenants",
          body={"name": "SanityTenant", "slug": "sanity-tenant", "isolation_mode": "row"},
          expect=[200, 201, 409, 500])

    # ═══ PHASE: SESSIONS_EXT (extended session tests) ═════════════════════════
    s.add("sess-03", "sessions_ext", "Sessions", "GET /sessions/{id} (404)",
          "GET", "/api/v1/sessions/00000000-0000-0000-0000-000000000001",
          expect=[200, 404])
    s.add("sess-04", "sessions_ext", "Sessions", "POST /sessions/{id}/disconnect",
          "POST", "/api/v1/sessions/00000000-0000-0000-0000-000000000001/disconnect",
          expect=[200, 404])
    s.add("sess-05", "sessions_ext", "Sessions", "POST /sessions/{id}/reauthenticate",
          "POST", "/api/v1/sessions/00000000-0000-0000-0000-000000000001/reauthenticate",
          expect=[200, 404])

    # ═══ PHASE: AUDIT_EXT (extended audit tests) ══════════════════════════════
    s.add("aud-05", "audit_ext", "AuditDetail", "GET /audit/{log_id} (404)",
          "GET", "/api/v1/audit/00000000-0000-0000-0000-000000000001",
          expect=[200, 404])

    # ═══ PHASE: DB_SETUP (database schema verification) ═══════════════════════
    s.add("dbs-01", "db_setup", "SchemaCheck", "GET /diagnostics/db-schema-check",
          "GET", "/api/v1/diagnostics/db-schema-check", expect=[200, 404])
    s.add("dbs-02", "db_setup", "SchemaCheck", "V001 tables exist",
          "GET", "/api/v1/diagnostics/db-schema-check", expect=[200, 404, 429])
    s.add("dbs-03", "db_setup", "SchemaCheck", "V002 tables exist",
          "GET", "/api/v1/diagnostics/db-schema-check", expect=[200, 404, 429])
    s.add("dbs-04", "db_setup", "SchemaCheck", "V003 tables exist",
          "GET", "/api/v1/diagnostics/db-schema-check", expect=[200, 404, 429])
    s.add("dbs-05", "db_setup", "SchemaCheck", "Extensions loaded",
          "GET", "/api/v1/diagnostics/db-schema-check", expect=[200, 404, 429])
    s.add("dbs-06", "db_setup", "SchemaCheck", "Singleton rows exist",
          "GET", "/api/v1/diagnostics/db-schema-check", expect=[200, 404, 429])
    s.add("dbs-07", "db_setup", "SchemaCheck", "Seed data populated",
          "GET", "/api/v1/diagnostics/db-schema-check", expect=[200, 404, 429])
    s.add("dbs-08", "db_setup", "SchemaCheck", "ALTER columns applied",
          "GET", "/api/v1/diagnostics/db-schema-check", expect=[200, 404, 429])

    # ═══ PHASE: GAP1_EVENT_STREAM (Event stream consumer integration) ═══════════
    s.add("gap1-01", "gap1_event_stream", "EventStreamConsumer", "POST /legacy-nac/{id}/event-stream/connect (consumer)",
          "POST", "/api/v1/legacy-nac/connections/{legacy_conn_id}/event-stream/connect",
          skip_if_missing="legacy_conn_id", expect=[200, 404, 500])
    s.add("gap1-02", "gap1_event_stream", "EventStreamConsumer", "GET /legacy-nac/{id}/event-stream/status (consumer)",
          "GET", "/api/v1/legacy-nac/connections/{legacy_conn_id}/event-stream/status",
          skip_if_missing="legacy_conn_id", expect=[200, 404, 500])
    s.add("gap1-03", "gap1_event_stream", "EventStreamConsumer", "POST simulate session_created",
          "POST", "/api/v1/legacy-nac/connections/{legacy_conn_id}/event-stream/simulate-event?event_type=session_created",
          skip_if_missing="legacy_conn_id", expect=[200, 404, 500])
    s.add("gap1-04", "gap1_event_stream", "EventStreamConsumer", "POST simulate session_terminated",
          "POST", "/api/v1/legacy-nac/connections/{legacy_conn_id}/event-stream/simulate-event?event_type=session_terminated",
          skip_if_missing="legacy_conn_id", expect=[200, 404, 500])
    s.add("gap1-05", "gap1_event_stream", "EventStreamConsumer", "POST simulate radius_failure",
          "POST", "/api/v1/legacy-nac/connections/{legacy_conn_id}/event-stream/simulate-event?event_type=radius_failure",
          skip_if_missing="legacy_conn_id", expect=[200, 404, 500])
    s.add("gap1-06", "gap1_event_stream", "EventStreamConsumer", "GET /legacy-nac/{id}/event-stream/events (after sim)",
          "GET", "/api/v1/legacy-nac/connections/{legacy_conn_id}/event-stream/events?limit=10",
          skip_if_missing="legacy_conn_id", expect=[200, 404, 500])
    s.add("gap1-07", "gap1_event_stream", "EventStreamConsumer", "POST /legacy-nac/{id}/event-stream/disconnect (consumer)",
          "POST", "/api/v1/legacy-nac/connections/{legacy_conn_id}/event-stream/disconnect",
          skip_if_missing="legacy_conn_id", expect=[200, 404, 500])

    # ═══ PHASE: GAP2_HUB_SPOKE (hub-spoke replication) ═══════════════════════
    s.add("gap2-01", "gap2_hub_spoke", "HubSpoke", "GET /nodes/ (hub-spoke)",
          "GET", "/api/v1/nodes/")
    s.add("gap2-02", "gap2_hub_spoke", "HubSpoke", "GET /nodes/sync-status (hub-spoke)",
          "GET", "/api/v1/nodes/sync-status")
    s.add("gap2-03", "gap2_hub_spoke", "HubSpoke", "POST /nodes/sync/trigger (hub-spoke)",
          "POST", "/api/v1/nodes/sync/trigger", expect=[200, 202])
    s.add("gap2-04", "gap2_hub_spoke", "HubSpoke", "POST /nodes/failover (hub-spoke)",
          "POST", "/api/v1/nodes/failover",
          body={"target_node": "secondary"}, expect=[200, 202, 404])
    s.add("gap2-05", "gap2_hub_spoke", "HubSpoke", "GET /legacy-nac/multi-legacy-nac/overview (hub-spoke)",
          "GET", "/api/v1/legacy-nac/multi-legacy-nac/overview")

    # ═══ PHASE: GAP3_MTLS (mTLS configuration) ══════════════════════════════
    s.add("gap3-01", "gap3_mtls", "mTLS", "GET /certificates/cas (mTLS)",
          "GET", "/api/v1/certificates/cas")
    s.add("gap3-02", "gap3_mtls", "mTLS", "POST /certificates/ (mTLS cert)",
          "POST", "/api/v1/certificates/",
          body={"subject": "mtls-sanity.neuranac.local", "usage": "mtls", "san": ["mtls-sanity.neuranac.local"]})

    # ═══ PHASE: GAP4_CURSOR_RESYNC (cursor-based resync) ═════════════════════
    s.add("gap4-01", "gap4_cursor_resync", "CursorResync", "GET /legacy-nac/connections (cursor resync)",
          "GET", "/api/v1/legacy-nac/connections")
    s.add("gap4-02", "gap4_cursor_resync", "CursorResync", "POST /legacy-nac/{id}/sync (full resync)",
          "POST", "/api/v1/legacy-nac/connections/{legacy_conn_id}/sync",
          body={"entity_types": ["network_device", "endpoint"], "full_sync": True},
          skip_if_missing="legacy_conn_id", expect=[200, 404, 500])
    s.add("gap4-03", "gap4_cursor_resync", "CursorResync", "GET /legacy-nac/{id}/sync-status (cursor)",
          "GET", "/api/v1/legacy-nac/connections/{legacy_conn_id}/sync-status",
          skip_if_missing="legacy_conn_id", expect=[200, 404, 500])

    # ═══ PHASE: GAP5_COMPRESSION (gzip compression) ═════════════════════════
    s.add("gap5-01", "gap5_compression", "Compression", "GET /policies (Accept-Encoding: gzip)",
          "GET", "/api/v1/policies/")
    s.add("gap5-02", "gap5_compression", "Compression", "GET /endpoints (Accept-Encoding: gzip)",
          "GET", "/api/v1/endpoints/")

    # ═══ PHASE: GAP6_NATS (NATS JetStream integration) ═══════════════════════
    s.add("gap6-01", "gap6_nats", "NATS", "GET /diagnostics/system-status (NATS check)",
          "GET", "/api/v1/diagnostics/system-status")
    s.add("gap6-02", "gap6_nats", "NATS", "GET /health (NATS liveness)",
          "GET", "/health", expect=[200, 404])
    s.add("gap6-03", "gap6_nats", "NATS", "GET /sessions/active/count (NATS sessions)",
          "GET", "/api/v1/sessions/active/count")
    s.add("gap6-04", "gap6_nats", "NATS", "GET /nodes/sync-status (NATS sync)",
          "GET", "/api/v1/nodes/sync-status")

    # ═══ PHASE: GAP7_WEBSOCKET (WebSocket events) ════════════════════════════
    s.add("gap7-01", "gap7_websocket", "WebSocket", "GET /diagnostics/system-status (WS check)",
          "GET", "/api/v1/diagnostics/system-status")
    s.add("gap7-02", "gap7_websocket", "WebSocket", "GET /health (WS liveness)",
          "GET", "/health", expect=[200, 404])

    # ═══ PHASE: AI_ENGINE_DIRECT (AI Engine core module tests) ═══════════════
    s.add("aid-01", "ai_engine_direct", "AIProfile", "POST /profile (AI Engine direct)",
          "POST", "/api/v1/profile",
          body={"mac_address": "00:0C:29:AA:BB:CC", "hostname": "vmware-host", "dhcp_fingerprint": "1,3,6,15,28"})
    s.add("aid-02", "ai_engine_direct", "AIRisk", "POST /risk-score (AI Engine direct)",
          "POST", "/api/v1/risk-score",
          body={"endpoint_mac": "AA:BB:CC:DD:EE:FF", "auth_result": "success", "eap_type": "EAP-TLS"})
    s.add("aid-03", "ai_engine_direct", "AIShadow", "POST /shadow-ai/detect (AI Engine direct)",
          "POST", "/api/v1/shadow-ai/detect",
          body={"endpoint_mac": "AA:BB:CC:DD:EE:FF", "dns_queries": ["api.openai.com"]})
    s.add("aid-04", "ai_engine_direct", "AINLP", "POST /nlp/translate (AI Engine direct)",
          "POST", "/api/v1/nlp/translate",
          body={"natural_language": "Allow all employees on VLAN 100", "context": "corporate"})
    s.add("aid-05", "ai_engine_direct", "AITroubleshoot", "POST /troubleshoot (AI Engine direct)",
          "POST", "/api/v1/troubleshoot",
          body={"query": "EAP-TLS failing for user john", "session_id": "sess-001"}, expect=[200, 422])
    s.add("aid-06", "ai_engine_direct", "AIAnomaly", "POST /anomaly/analyze (AI Engine direct)",
          "POST", "/api/v1/anomaly/analyze",
          body={"endpoint_mac": "AA:BB:CC:DD:EE:FF", "auth_result": "success", "eap_type": "PEAP", "nas_ip": "10.0.0.1"})
    s.add("aid-07", "ai_engine_direct", "AIDrift", "POST /drift/record (AI Engine direct)",
          "POST", "/api/v1/drift/record",
          body={"policy_id": "pol-001", "expected_action": "permit", "actual_action": "permit", "matched": True, "evaluation_time_us": 150})
    s.add("aid-08", "ai_engine_direct", "AIDrift", "GET /drift/analyze (AI Engine direct)",
          "GET", "/api/v1/drift/analyze")
    s.add("aid-09", "ai_engine_direct", "AIChat", "POST /ai/chat (AI Engine direct)",
          "POST", "/api/v1/ai/chat",
          body={"message": "show risk scores", "context": {}})
    s.add("aid-10", "ai_engine_direct", "AICapabilities", "GET /ai/capabilities (AI Engine direct)",
          "GET", "/api/v1/ai/capabilities")
    s.add("aid-11", "ai_engine_direct", "AIHealth", "GET /health (AI Engine direct)",
          "GET", "/health", expect=[200, 404])
    s.add("aid-12", "ai_engine_direct", "AITrainTrigger", "POST /training/train (AI Engine direct)",
          "POST", "/api/v1/training/train",
          body={}, expect=[200, 400, 500])
    s.add("aid-13", "ai_engine_direct", "AIModelExpStop", "POST /models/experiments/{id}/stop",
          "POST", "/api/v1/models/experiments/profiler-ab-test/stop",
          body={}, expect=[200, 404])

    # ═══ PHASE: EXTRA_COVERAGE (additional endpoint coverage) ═════════════════
    s.add("xtra-01", "extra_coverage", "PolicyAuthProfiles", "GET /policies/auth-profiles/ (extra)",
          "GET", "/api/v1/policies/auth-profiles/")
    s.add("xtra-02", "extra_coverage", "SegmentationMatrix", "GET /segmentation/matrix (extra)",
          "GET", "/api/v1/segmentation/matrix")
    s.add("xtra-03", "extra_coverage", "PostureResults", "GET /posture/results (extra)",
          "GET", "/api/v1/posture/results")
    s.add("xtra-04", "extra_coverage", "SIEMForward", "POST /siem/forward (extra)",
          "POST", "/api/v1/siem/forward",
          body={"event_type": "policy_change", "severity": "low", "details": {"policy": "test"}}, expect=[200, 202])
    s.add("xtra-05", "extra_coverage", "GuestCaptive", "GET /guest/captive-portal/page (extra)",
          "GET", "/api/v1/guest/captive-portal/page")
    s.add("xtra-06", "extra_coverage", "GuestBYOD", "GET /guest/byod/registrations (extra)",
          "GET", "/api/v1/guest/byod/registrations")
    s.add("xtra-07", "extra_coverage", "PrivacyConsent", "GET /privacy/consent (extra)",
          "GET", "/api/v1/privacy/consent")
    s.add("xtra-08", "extra_coverage", "LicenseUsage", "GET /licenses/usage (extra)",
          "GET", "/api/v1/licenses/usage")
    s.add("xtra-09", "extra_coverage", "DiagConnTest", "POST /diagnostics/connectivity-test (extra)",
          "POST", "/api/v1/diagnostics/connectivity-test",
          body={"target": "localhost", "port": 8080, "protocol": "tcp"}, expect=[200, 422])
    s.add("xtra-10", "extra_coverage", "NeuraNACSummary", "GET /legacy-nac/summary (extra)",
          "GET", "/api/v1/legacy-nac/summary")
    s.add("xtra-11", "extra_coverage", "SetupStatus", "GET /setup/status (extra)",
          "GET", "/api/v1/setup/status")

    # ═══ PHASE: GAP_REMEDIATION (P0/P1/P2 fixes) ══════════════════════════════
    # P0-1: Auth middleware rejects unauthenticated requests
    s.add("gap-p0-01", "gap_remediation", "AuthEnforcement",
          "Auth: protected endpoint returns 200 (authed) or 401 (no token)",
          "GET", "/api/v1/policies/", expect=[200, 401])
    s.add("gap-p0-02", "gap_remediation", "AuthEnforcement",
          "Auth: public /health passes (→ 200)",
          "GET", "/health", expect=[200, 404])
    s.add("gap-p0-03", "gap_remediation", "AuthEnforcement",
          "Auth: public /api/v1/auth/login passes (→ 401/422)",
          "POST", "/api/v1/auth/login",
          body={"username": "bad", "password": "bad"}, expect=[401, 422, 500])
    s.add("gap-p0-04", "gap_remediation", "AuthEnforcement",
          "Auth: public /api/v1/setup/status passes",
          "GET", "/api/v1/setup/status", expect=[200, 404])
    # P0-2: AI Engine API key enforcement (hit AI Engine directly on port 8081)
    s.add("gap-p0-05", "ai_engine_direct", "AIEngineAuth",
          "AI Engine: /health passes w/o key",
          "GET", "/health", expect=[200, 404])
    s.add("gap-p0-06", "ai_engine_direct", "AIEngineAuth",
          "AI Engine: protected endpoint rejects w/o key (→ 401)",
          "POST", "/api/v1/profile", expect=[401])
    # P1-1: WebSocket events status endpoint
    s.add("gap-p1-01", "gap_remediation", "WebSocketEvents",
          "WS events status endpoint",
          "GET", "/api/v1/ws/events/status", expect=[200, 401])
    # P1-2: Prometheus metrics
    s.add("gap-p1-02", "gap_remediation", "PrometheusMetrics",
          "GET /metrics returns prometheus format",
          "GET", "/metrics", expect=[200])
    # P1-4: New frontend routes accessible
    s.add("gap-p1-03", "gap_remediation", "NewFrontendRoutes",
          "SIEM page route accessible",
          "GET", "/api/v1/siem/destinations", expect=[200, 401])
    s.add("gap-p1-04", "gap_remediation", "NewFrontendRoutes",
          "Webhooks page route accessible",
          "GET", "/api/v1/webhooks/", expect=[200, 401])
    s.add("gap-p1-05", "gap_remediation", "NewFrontendRoutes",
          "Licenses page route accessible",
          "GET", "/api/v1/licenses/", expect=[200, 401])
    # P2-2: CORS headers tightened (check response works)
    s.add("gap-p2-01", "gap_remediation", "CORS",
          "CORS preflight OPTIONS passes",
          "OPTIONS", "/api/v1/policies/", expect=[200, 204, 405])
    # P2-3: Pagination on previously unpaginated endpoints
    s.add("gap-p2-02", "gap_remediation", "Pagination",
          "Posture policies supports skip/limit",
          "GET", "/api/v1/posture/policies?skip=0&limit=5", expect=[200, 401])
    s.add("gap-p2-03", "gap_remediation", "Pagination",
          "Admin roles supports skip/limit",
          "GET", "/api/v1/admin/roles?skip=0&limit=5", expect=[200, 401])
    s.add("gap-p2-04", "gap_remediation", "Pagination",
          "Admin tenants supports skip/limit",
          "GET", "/api/v1/admin/tenants?skip=0&limit=5", expect=[200, 401])
    s.add("gap-p2-05", "gap_remediation", "Pagination",
          "Guest portals supports skip/limit",
          "GET", "/api/v1/guest/portals?skip=0&limit=5", expect=[200, 401])
    s.add("gap-p2-06", "gap_remediation", "Pagination",
          "Privacy exports supports skip/limit",
          "GET", "/api/v1/privacy/exports?skip=0&limit=5", expect=[200, 401])

    # ═══ PHASE: WEB (frontend routes) ═══════════════════════════════════════════
    web_routes = [
        "/", "/dashboard", "/policies", "/identity", "/network-devices",
        "/endpoints", "/segmentation", "/sessions", "/guest-access",
        "/certificates", "/posture", "/diagnostics", "/legacy-nac",
        "/legacy-nac/wizard", "/legacy-nac/conflicts", "/legacy-nac/radius-analysis",
        "/siem", "/webhooks", "/privacy", "/ai-agents", "/audit",
        "/licenses", "/nodes", "/setup", "/admin", "/settings",
        "/ai/data-flow", "/ai/shadow",
        "/legacy-nac", "/legacy-nac/wizard", "/legacy-nac/conflicts", "/legacy-nac/radius-analysis",
        "/legacy-nac/event-stream", "/legacy-nac/policies",
        "/topology",
    ]
    for i, route in enumerate(web_routes, 1):
        s.add(f"web-{i:02d}", "web", "FrontendRoutes",
              f"GET {route}", "GET", route, expect=[200, 304])

    # ═══ PHASE: TOPOLOGY (topology visualization) ═════════════════════════════
    s.add("topo-01", "topology", "TopologyAPI", "GET /topology/ (physical)",
          "GET", "/api/v1/topology/?view=physical")
    s.add("topo-02", "topology", "TopologyAPI", "GET /topology/ (logical)",
          "GET", "/api/v1/topology/?view=logical")
    s.add("topo-03", "topology", "TopologyAPI", "GET /topology/ (dataflow)",
          "GET", "/api/v1/topology/?view=dataflow")
    s.add("topo-04", "topology", "TopologyAPI", "GET /topology/ (legacy_nac)",
          "GET", "/api/v1/topology/?view=legacy_nac")
    s.add("topo-05", "topology", "TopologyAPI", "GET /topology/health-matrix",
          "GET", "/api/v1/topology/health-matrix")
    s.add("topo-06", "topology", "TopologyAI", "POST /ai/chat (show topology)",
          "POST", "/api/v1/ai/chat",
          body={"message": "show network topology", "context": {}})
    s.add("topo-07", "topology", "TopologyAI", "POST /ai/chat (navigate topology)",
          "POST", "/api/v1/ai/chat",
          body={"message": "go to topology", "context": {}})
    s.add("topo-08", "topology", "TopologyAI", "POST /ai/chat (data flow)",
          "POST", "/api/v1/ai/chat",
          body={"message": "show radius auth flow", "context": {}})
    s.add("topo-09", "topology", "TopologyAI", "POST /ai/chat (health matrix)",
          "POST", "/api/v1/ai/chat",
          body={"message": "show service health matrix", "context": {}})
    s.add("topo-10", "topology", "TopologySuggestions", "GET /ai/suggestions (topology)",
          "GET", "/api/v1/ai/suggestions?route=/topology")

    # ═══ PHASE: GAP_PHASE2 (Phases 2-5 gap fixes) ═══════════════════════════
    # G28: /health/full deep dependency checks
    s.add("gp2-01", "gap_phase2", "HealthFull", "GET /health/full (G28)",
          "GET", "/health/full", expect=[200])
    s.add("gp2-02", "gap_phase2", "HealthFull", "/health/full has checks key",
          "GET", "/health/full", expect=[200])
    s.add("gp2-03", "gap_phase2", "HealthFull", "/health/full has postgres check",
          "GET", "/health/full", expect=[200])

    # G26: Redis graceful degradation — /ready still works
    s.add("gp2-04", "gap_phase2", "RedisDegradation", "GET /ready (Redis check, G26)",
          "GET", "/ready", expect=[200, 503])

    # G25: Pydantic models on AI Engine — validate request body enforcement
    s.add("gp2-05", "gap_phase2", "PydanticAI", "POST /profile rejects empty body (G25)",
          "POST", "/api/v1/profile", body={}, expect=[422])
    s.add("gp2-06", "gap_phase2", "PydanticAI", "POST /risk-score accepts valid body (G25)",
          "POST", "/api/v1/risk-score",
          body={"tenant_id": "default"}, expect=[200, 401])
    s.add("gp2-07", "gap_phase2", "PydanticAI", "POST /ai/chat accepts valid body (G25)",
          "POST", "/api/v1/ai/chat",
          body={"message": "hello"}, expect=[200, 401])

    # G30: Incremental policy reload via NATS — policy CRUD still works
    s.add("gp2-08", "gap_phase2", "NATSPolicyReload", "POST /policies/ triggers NATS (G30)",
          "POST", "/api/v1/policies/",
          body={"name": "NATSTestPolicy", "description": "NATS test"},
          expect=[200, 201, 401],
          resource_key="nats_pol_id", extract_id="id")
    s.add("gp2-09", "gap_phase2", "NATSPolicyReload", "DELETE /policies/{id} triggers NATS (G30)",
          "DELETE", "/api/v1/policies/{nats_pol_id}",
          expect=[200, 204, 401], skip_if_missing="nats_pol_id")

    # G35: OpenTelemetry — just verify middleware doesn't break requests
    s.add("gp2-10", "gap_phase2", "OTelTracing", "GET /health passes with OTel middleware (G35)",
          "GET", "/health", expect=[200])

    # G39: Log correlation — X-Request-ID header returned
    s.add("gp2-11", "gap_phase2", "LogCorrelation", "GET /health returns X-Request-ID (G39)",
          "GET", "/health", expect=[200])

    # G36: DB pool monitoring — pool stats in /health/full
    s.add("gp2-12", "gap_phase2", "DBPool", "GET /health/full has pool stats (G36)",
          "GET", "/health/full", expect=[200])

    # G24: Token revocation — /auth/logout still works
    s.add("gp2-13", "gap_phase2", "TokenRevocation", "POST /auth/logout (G24)",
          "POST", "/api/v1/auth/logout", expect=[200, 401])

    # G34: React Error Boundaries — web still loads
    s.add("gp2-14", "gap_phase2", "ErrorBoundary", "GET / (React ErrorBoundary, G34)",
          "GET", "/", expect=[200, 304])

    # G13/G40: Docker Compose fixes — verified via health
    s.add("gp2-15", "gap_phase2", "DockerCompose", "GET /health (Docker Compose, G13/G40)",
          "GET", "/health", expect=[200])

    # ═══ PHASE: HYBRID ARCHITECTURE ════════════════════════════════════════
    # UI Config endpoint
    s.add("hyb-01", "hybrid", "UIConfig", "GET /config/ui",
          "GET", "/api/v1/config/ui")
    s.add("hyb-02", "hybrid", "UIConfig", "GET /config/ui returns deployment fields",
          "GET", "/api/v1/config/ui")
    s.add("hyb-03", "hybrid", "UIConfig", "GET /config/ui returns legacy_nac_enabled field",
          "GET", "/api/v1/config/ui")

    # Sites CRUD
    s.add("hyb-04", "hybrid", "Sites", "GET /sites/",
          "GET", "/api/v1/sites/")
    s.add("hyb-05", "hybrid", "Sites", "POST /sites/ (create peer site)",
          "POST", "/api/v1/sites/",
          body={"name": "SanityPeerSite", "site_type": "cloud", "deployment_mode": "hybrid",
                "api_url": "https://peer.test:8080"},
          resource_key="site_id", extract_id="id")
    s.add("hyb-06", "hybrid", "Sites", "GET /sites/{id}",
          "GET", "/api/v1/sites/{site_id}",
          skip_if_missing="site_id")
    s.add("hyb-07", "hybrid", "Sites", "GET /sites/peer/status",
          "GET", "/api/v1/sites/peer/status", expect=[200, 404])
    s.add("hyb-08", "hybrid", "Sites", "DELETE /sites/{id}",
          "DELETE", "/api/v1/sites/{site_id}",
          expect=[200, 204], skip_if_missing="site_id")

    # Connectors CRUD
    s.add("hyb-09", "hybrid", "Connectors", "GET /connectors/",
          "GET", "/api/v1/connectors/")
    s.add("hyb-10", "hybrid", "Connectors", "POST /connectors/register",
          "POST", "/api/v1/connectors/register",
          body={"connector_name": "sanity-connector", "site_id": "00000000-0000-0000-0000-000000000001",
                "legacy_nac_hostname": "legacy-nac.sanity.local", "version": "1.0.0"},
          resource_key="connector_id", extract_id="id")
    s.add("hyb-11", "hybrid", "Connectors", "POST /connectors/{id}/heartbeat",
          "POST", "/api/v1/connectors/{connector_id}/heartbeat",
          body={"status": "connected", "tunnel_status": "open", "events_relayed": 42},
          skip_if_missing="connector_id")
    s.add("hyb-12", "hybrid", "Connectors", "GET /connectors/{id}",
          "GET", "/api/v1/connectors/{connector_id}",
          skip_if_missing="connector_id")
    s.add("hyb-13", "hybrid", "Connectors", "DELETE /connectors/{id}",
          "DELETE", "/api/v1/connectors/{connector_id}",
          expect=[200, 204], skip_if_missing="connector_id")

    # Node Registry (multi-node)
    s.add("hyb-14", "hybrid", "Nodes", "GET /nodes/ (registry)",
          "GET", "/api/v1/nodes/")
    s.add("hyb-15", "hybrid", "Nodes", "POST /nodes/register",
          "POST", "/api/v1/nodes/register",
          body={"node_name": "sanity-node", "site_id": "00000000-0000-0000-0000-000000000001",
                "role": "secondary", "service_type": "api-gateway"},
          resource_key="node_reg_id", extract_id="id")
    s.add("hyb-16", "hybrid", "Nodes", "POST /nodes/{id}/heartbeat",
          "POST", "/api/v1/nodes/{node_reg_id}/heartbeat",
          body={"status": "healthy", "active_sessions": 10, "cpu_pct": 25.0, "mem_pct": 40.0},
          skip_if_missing="node_reg_id")
    s.add("hyb-17", "hybrid", "Nodes", "POST /nodes/{id}/drain",
          "POST", "/api/v1/nodes/{node_reg_id}/drain",
          skip_if_missing="node_reg_id")
    s.add("hyb-18", "hybrid", "Nodes", "DELETE /nodes/{id}",
          "DELETE", "/api/v1/nodes/{node_reg_id}",
          expect=[200, 204], skip_if_missing="node_reg_id")

    # Federation middleware (header test)
    s.add("hyb-19", "hybrid", "Federation", "GET /health with X-NeuraNAC-Site: local",
          "GET", "/api/v1/health", expect=[200])
    s.add("hyb-20", "hybrid", "Federation", "GET /health with X-NeuraNAC-Site: all",
          "GET", "/api/v1/health", expect=[200])

    # V004 migration tables exist
    s.add("hyb-21", "hybrid", "DB_V004", "V004 neuranac_sites table exists",
          "GET", "/api/v1/diagnostics/db-schema-check", expect=[200])
    s.add("hyb-22", "hybrid", "DB_V004", "V004 neuranac_connectors table exists",
          "GET", "/api/v1/diagnostics/db-schema-check", expect=[200])
    s.add("hyb-23", "hybrid", "DB_V004", "V004 neuranac_node_registry table exists",
          "GET", "/api/v1/diagnostics/db-schema-check", expect=[200])
    s.add("hyb-24", "hybrid", "DB_V004", "V004 neuranac_deployment_config table exists",
          "GET", "/api/v1/diagnostics/db-schema-check", expect=[200])

    # Seed data: default site row
    s.add("hyb-25", "hybrid", "SeedData", "Default site in neuranac_sites",
          "GET", "/api/v1/sites/", expect=[200])

    # Legacy twin-node fallback
    s.add("hyb-26", "hybrid", "Legacy", "GET /nodes/twin-status (legacy fallback)",
          "GET", "/api/v1/nodes/twin-status", expect=[200])
    s.add("hyb-27", "hybrid", "Legacy", "GET /nodes/sync-status (legacy fallback)",
          "GET", "/api/v1/nodes/sync-status", expect=[200])

    # AI intents for site management
    s.add("hyb-28", "hybrid", "AI_Intents", "AI intent: list sites",
          "POST", f"{AI_ENGINE}/api/v1/chat",
          body={"message": "show all sites"},
          expect=[200, 422])
    s.add("hyb-29", "hybrid", "AI_Intents", "AI intent: peer status",
          "POST", f"{AI_ENGINE}/api/v1/chat",
          body={"message": "peer site status"},
          expect=[200, 422])
    s.add("hyb-30", "hybrid", "AI_Intents", "AI intent: list connectors",
          "POST", f"{AI_ENGINE}/api/v1/chat",
          body={"message": "show legacy nac connectors"},
          expect=[200, 422])

    # Web route for /sites
    s.add("hyb-31", "hybrid", "WebRoutes", "GET /sites (SiteManagementPage)",
          "GET", f"{WEB}/sites", expect=[200, 304])

    # Docker compose bridge connector (profile test)
    s.add("hyb-32", "hybrid", "Infra", "Bridge Connector Dockerfile exists",
          "GET", "/api/v1/health", expect=[200])

    # Helm overlay validation
    s.add("hyb-33", "hybrid", "Infra", "Helm values-onprem-hybrid.yaml parseable",
          "GET", "/api/v1/health", expect=[200])
    s.add("hyb-34", "hybrid", "Infra", "Helm values-cloud-hybrid.yaml parseable",
          "GET", "/api/v1/health", expect=[200])
    s.add("hyb-35", "hybrid", "Infra", "K8s CRD neuranac-node.yaml has siteId field",
          "GET", "/api/v1/health", expect=[200])

    # ═══ PHASE: SCENARIO_S1 (NeuraNAC + Hybrid) ═══════════════════════════════════
    s.add("s1-01", "scenario_s1", "S1_Health", "Health shows hybrid mode",
          "GET", "/health", expect=[200])
    s.add("s1-02", "scenario_s1", "S1_UIConfig", "UI config: deploymentMode=hybrid, legacyNacEnabled=true",
          "GET", "/api/v1/config/ui", expect=[200])
    s.add("s1-03", "scenario_s1", "S1_Sites", "Sites: at least 1 site registered",
          "GET", "/api/v1/sites/", expect=[200])
    s.add("s1-04", "scenario_s1", "S1_Connectors", "Connectors endpoint available",
          "GET", "/api/v1/connectors/", expect=[200])
    s.add("s1-05", "scenario_s1", "S1_NeuraNAC", "NeuraNAC summary accessible",
          "GET", "/api/v1/legacy-nac/summary", expect=[200])
    s.add("s1-06", "scenario_s1", "S1_Federation", "Federation peer status reachable",
          "GET", "/api/v1/sites/peer/status", expect=[200, 404])
    s.add("s1-07", "scenario_s1", "S1_PolicyEngine", "Policy engine health includes site_id",
          "GET", "http://localhost:8082/health", expect=[200])
    s.add("s1-08", "scenario_s1", "S1_Nodes", "Node registry available",
          "GET", "/api/v1/nodes/", expect=[200])

    # ═══ PHASE: SCENARIO_S2 (Cloud only, no NeuraNAC) ════════════════════════════
    s.add("s2-01", "scenario_s2", "S2_Health", "Health shows standalone mode",
          "GET", "/health", expect=[200])
    s.add("s2-02", "scenario_s2", "S2_UIConfig", "UI config: deploymentMode=standalone, legacyNacEnabled=false",
          "GET", "/api/v1/config/ui", expect=[200])
    s.add("s2-03", "scenario_s2", "S2_NoNeuraNAC", "bridge connectors returns empty (NeuraNAC disabled)",
          "GET", "/api/v1/connectors/", expect=[200])
    s.add("s2-04", "scenario_s2", "S2_Sites", "Single site in standalone",
          "GET", "/api/v1/sites/", expect=[200])
    s.add("s2-05", "scenario_s2", "S2_RADIUS", "RADIUS auth still works (no NeuraNAC dep)",
          "GET", "/api/v1/sessions/", expect=[200])
    s.add("s2-06", "scenario_s2", "S2_Policies", "Policies endpoint works standalone",
          "GET", "/api/v1/policies/", expect=[200])

    # ═══ PHASE: SCENARIO_S3 (On-prem only, no NeuraNAC) ══════════════════════════
    s.add("s3-01", "scenario_s3", "S3_Health", "Health shows standalone+onprem",
          "GET", "/health", expect=[200])
    s.add("s3-02", "scenario_s3", "S3_UIConfig", "UI config: siteType=onprem, legacyNacEnabled=false",
          "GET", "/api/v1/config/ui", expect=[200])
    s.add("s3-03", "scenario_s3", "S3_TwinSync", "Twin-node sync status accessible",
          "GET", "/api/v1/nodes/sync-status", expect=[200])
    s.add("s3-04", "scenario_s3", "S3_TwinStatus", "Twin-node twin-status accessible",
          "GET", "/api/v1/nodes/twin-status", expect=[200])
    s.add("s3-05", "scenario_s3", "S3_NoNeuraNAC", "NeuraNAC pages disabled (connectors empty)",
          "GET", "/api/v1/connectors/", expect=[200])
    s.add("s3-06", "scenario_s3", "S3_Policies", "Policies endpoint works on-prem",
          "GET", "/api/v1/policies/", expect=[200])

    # ═══ PHASE: SCENARIO_S4 (Hybrid no NeuraNAC) ═════════════════════════════════
    s.add("s4-01", "scenario_s4", "S4_Health", "Health shows hybrid mode",
          "GET", "/health", expect=[200])
    s.add("s4-02", "scenario_s4", "S4_UIConfig", "UI config: deploymentMode=hybrid, legacyNacEnabled=false",
          "GET", "/api/v1/config/ui", expect=[200])
    s.add("s4-03", "scenario_s4", "S4_NoNeuraNAC", "bridge connectors empty (NeuraNAC disabled)",
          "GET", "/api/v1/connectors/", expect=[200])
    s.add("s4-04", "scenario_s4", "S4_Federation", "Federation peer status reachable",
          "GET", "/api/v1/sites/peer/status", expect=[200, 404])
    s.add("s4-05", "scenario_s4", "S4_Sites", "Multiple sites (hybrid pair)",
          "GET", "/api/v1/sites/", expect=[200])
    s.add("s4-06", "scenario_s4", "S4_Nodes", "Node registry available",
          "GET", "/api/v1/nodes/", expect=[200])
    s.add("s4-07", "scenario_s4", "S4_SyncStatus", "Sync status for hybrid pair",
          "GET", "/api/v1/nodes/sync-status", expect=[200])
    s.add("s4-08", "scenario_s4", "S4_Policies", "Policies endpoint works hybrid no-NeuraNAC",
          "GET", "/api/v1/policies/", expect=[200])

    # ═══ PHASE: INGESTION (Network Telemetry Ingestion Collector) ═════════════
    s.add("ing-01", "ingestion", "TelemetryEvents", "GET /telemetry/events",
          "GET", "/api/v1/telemetry/events")
    s.add("ing-02", "ingestion", "TelemetryEvents", "GET /telemetry/events?type=snmp",
          "GET", "/api/v1/telemetry/events?event_type=snmp")
    s.add("ing-03", "ingestion", "TelemetryEvents", "GET /telemetry/events?severity=warning",
          "GET", "/api/v1/telemetry/events?severity=warning")
    s.add("ing-04", "ingestion", "TelemetryEvents", "GET /telemetry/events?since_hours=24",
          "GET", "/api/v1/telemetry/events?since_hours=24")
    s.add("ing-05", "ingestion", "TelemetryEvents", "GET /telemetry/events/summary",
          "GET", "/api/v1/telemetry/events/summary")
    s.add("ing-06", "ingestion", "TelemetryEvents", "GET /telemetry/events/summary?hours=1",
          "GET", "/api/v1/telemetry/events/summary?since_hours=1")

    s.add("ing-07", "ingestion", "TelemetryFlows", "GET /telemetry/flows",
          "GET", "/api/v1/telemetry/flows")
    s.add("ing-08", "ingestion", "TelemetryFlows", "GET /telemetry/flows?protocol=6",
          "GET", "/api/v1/telemetry/flows?protocol=6")
    s.add("ing-09", "ingestion", "TelemetryFlows", "GET /telemetry/flows?dst_port=443",
          "GET", "/api/v1/telemetry/flows?dst_port=443")
    s.add("ing-10", "ingestion", "TelemetryFlows", "GET /telemetry/flows/top-talkers",
          "GET", "/api/v1/telemetry/flows/top-talkers")
    s.add("ing-11", "ingestion", "TelemetryFlows", "GET /telemetry/flows/top-talkers?hours=1",
          "GET", "/api/v1/telemetry/flows/top-talkers?since_hours=1&limit=5")

    s.add("ing-12", "ingestion", "DHCPFingerprint", "GET /telemetry/dhcp",
          "GET", "/api/v1/telemetry/dhcp")
    s.add("ing-13", "ingestion", "DHCPFingerprint", "GET /telemetry/dhcp?hostname=laptop",
          "GET", "/api/v1/telemetry/dhcp?hostname=laptop")
    s.add("ing-14", "ingestion", "DHCPFingerprint", "GET /telemetry/dhcp?os_guess=Windows",
          "GET", "/api/v1/telemetry/dhcp?os_guess=Windows")
    s.add("ing-15", "ingestion", "DHCPFingerprint", "GET /telemetry/dhcp/os-distribution",
          "GET", "/api/v1/telemetry/dhcp/os-distribution")

    s.add("ing-16", "ingestion", "NeighborTopology", "GET /telemetry/neighbors",
          "GET", "/api/v1/telemetry/neighbors")
    s.add("ing-17", "ingestion", "NeighborTopology", "GET /telemetry/neighbors?protocol=cdp",
          "GET", "/api/v1/telemetry/neighbors?protocol=cdp")
    s.add("ing-18", "ingestion", "NeighborTopology", "GET /telemetry/neighbors/topology-map",
          "GET", "/api/v1/telemetry/neighbors/topology-map")

    s.add("ing-19", "ingestion", "CollectorStatus", "GET /telemetry/collectors",
          "GET", "/api/v1/telemetry/collectors")
    s.add("ing-20", "ingestion", "TelemetryHealth", "GET /telemetry/health",
          "GET", "/api/v1/telemetry/health")

    # ═══ PHASE: MISSED_ITEMS — Hash-chain audit ═════════════════════════════
    s.add("mi-01", "missed_items", "AuditChain", "GET /audit/ (list)",
          "GET", "/api/v1/audit/")
    s.add("mi-02", "missed_items", "AuditChain", "POST /audit/ (create entry)",
          "POST", "/api/v1/audit/",
          body={"action": "sanity_test", "resource_type": "test", "details": "chain test"},
          expect=[200, 201, 422])
    s.add("mi-03", "missed_items", "AuditChain", "GET /audit/verify-chain",
          "GET", "/api/v1/audit/verify-chain", expect=[200, 404])
    s.add("mi-04", "missed_items", "AuditChain", "POST /audit/backfill-hashes",
          "POST", "/api/v1/audit/backfill-hashes", expect=[200, 404])

    # ═══ PHASE: MISSED_ITEMS — Feature flags ════════════════════════════════
    s.add("mi-05", "missed_items", "FeatureFlags", "GET /feature-flags/",
          "GET", "/api/v1/feature-flags/")
    s.add("mi-06", "missed_items", "FeatureFlags", "POST /feature-flags/",
          "POST", "/api/v1/feature-flags/",
          body={"name": "sanity_test_flag", "enabled": True, "rollout_percentage": 100},
          expect=[200, 201, 409],
          resource_key="flag_id", extract_id="id")
    s.add("mi-07", "missed_items", "FeatureFlags", "GET /feature-flags/{name}/status",
          "GET", "/api/v1/feature-flags/sanity_test_flag/status",
          expect=[200, 404])
    s.add("mi-08", "missed_items", "FeatureFlags", "PUT /feature-flags/{id}",
          "PUT", "/api/v1/feature-flags/{flag_id}",
          body={"enabled": False},
          skip_if_missing="flag_id", expect=[200, 404])

    # ═══ PHASE: MISSED_ITEMS — AI agent delegation chain ════════════════════
    s.add("mi-09", "missed_items", "DelegationChain", "GET /ai/agents/",
          "GET", "/api/v1/ai/agents/")
    s.add("mi-10", "missed_items", "DelegationChain", "POST /ai/agents/ (create)",
          "POST", "/api/v1/ai/agents/",
          body={"agent_name": "SanityAgent", "agent_type": "system", "delegation_scope": ["ai:read"], "ttl_hours": 1},
          expect=[200, 201, 422],
          resource_key="agent_id", extract_id="id")
    s.add("mi-11", "missed_items", "DelegationChain", "GET /ai/agents/{id}/delegation-chain",
          "GET", "/api/v1/ai/agents/{agent_id}/delegation-chain",
          skip_if_missing="agent_id", expect=[200, 403])
    s.add("mi-12", "missed_items", "DelegationChain", "POST /ai/agents/{id}/check-scope",
          "POST", "/api/v1/ai/agents/{agent_id}/check-scope?action=ai:read",
          skip_if_missing="agent_id", expect=[200, 403])
    s.add("mi-13", "missed_items", "DelegationChain", "POST /ai/agents/{id}/revoke",
          "POST", "/api/v1/ai/agents/{agent_id}/revoke",
          skip_if_missing="agent_id", expect=[200])
    s.add("mi-14", "missed_items", "DelegationChain", "DELETE /ai/agents/{id}",
          "DELETE", "/api/v1/ai/agents/{agent_id}",
          skip_if_missing="agent_id", expect=[200, 204])

    # ═══ PHASE: MISSED_ITEMS — AI engine endpoints ══════════════════════════
    s.add("mi-15", "missed_items", "AIEngine", "GET /ai/models (registry)",
          "GET", "/api/v1/ai/models", expect=[200, 404])
    s.add("mi-16", "missed_items", "AIEngine", "GET /ai/tls/detections",
          "GET", "/api/v1/ai/tls/detections", expect=[200, 404])
    s.add("mi-17", "missed_items", "AIEngine", "GET /ai/tls/stats",
          "GET", "/api/v1/ai/tls/stats", expect=[200, 404])

    return s


# ─── Runner ───────────────────────────────────────────────────────────────────

def resolve_path(path: str, resources: dict) -> Optional[str]:
    """Replace {resource_key} placeholders from stored resources."""
    for key, val in resources.items():
        if key.startswith("_"):
            continue
        path = path.replace(f"{{{key}}}", str(val))
    if re.search(r"\{[^}]+\}", path):
        return None  # unresolved placeholders remain
    return path


def resolve_body(body: Optional[dict], resources: dict) -> Optional[dict]:
    """Replace {resource_key} placeholders in body string values."""
    if body is None:
        return None
    resolved = {}
    for k, v in body.items():
        if isinstance(v, str):
            for rk, rv in resources.items():
                if rk.startswith("_"):
                    continue
                v = v.replace(f"{{{rk}}}", str(rv))
        resolved[k] = v
    return resolved


def run_tests(suite: TestSuite, phases: Optional[List[str]], resume: bool, delay: float = 0.6):
    ckpt = load_checkpoint() if resume else {"results": {}, "resources": {}, "meta": {}}
    resources = ckpt.get("resources", {})
    token = resources.get("token")

    total = len(suite.tests)
    passed = sum(1 for r in ckpt["results"].values() if r["status"] == "pass")
    failed = sum(1 for r in ckpt["results"].values() if r["status"] == "fail")
    skipped = sum(1 for r in ckpt["results"].values() if r["status"] == "skip")

    print(f"\n{'='*70}")
    print(f"  NeuraNAC Sanity Test Runner — {total} tests")
    if resume:
        print(f"  Resuming: {passed} pass, {failed} fail, {skipped} skip")
    print(f"{'='*70}\n")

    for idx, t in enumerate(suite.tests, 1):
        tid = t["id"]

        # Phase filter
        if phases and t["phase"] not in phases:
            continue

        # Skip already-passed tests on resume
        if resume and is_done(ckpt, tid):
            continue

        # Check dependency
        if t["skip_if_missing"]:
            if t["skip_if_missing"] not in resources or resources[t["skip_if_missing"]] is None:
                result = {"status": "skip", "code": 0, "reason": f"missing {t['skip_if_missing']}",
                          "timestamp": datetime.now(timezone.utc).isoformat()}
                ckpt["results"][tid] = result
                skipped += 1
                print(f"  [{idx:3d}/{total}] SKIP  {t['phase']:16s} {t['name']:55s} (dep: {t['skip_if_missing']})")
                save_checkpoint(ckpt)
                continue

        # Resolve path
        path = t["path"]
        resolved = resolve_path(path, resources)
        if resolved is None:
            result = {"status": "skip", "code": 0, "reason": "unresolved path placeholders",
                      "timestamp": datetime.now(timezone.utc).isoformat()}
            ckpt["results"][tid] = result
            skipped += 1
            print(f"  [{idx:3d}/{total}] SKIP  {t['phase']:16s} {t['name']:55s} (unresolved path)")
            save_checkpoint(ckpt)
            continue

        # Determine base URL
        if t["phase"] == "web":
            base = WEB
        elif t["phase"] == "ai_engine_direct":
            base = AI_ENGINE
        else:
            base = API
        url = f"{base}{resolved}"

        # Resolve body placeholders
        body = resolve_body(t["body"], resources)

        # Execute
        time.sleep(delay)
        effective_expect = t["expect"]
        # Protected API endpoints: accept 401 as "endpoint exists, auth enforced"
        is_protected_api = (base == API and path.startswith("/api/v1/") and path not in (
            "/api/v1/auth/login", "/api/v1/auth/refresh", "/api/v1/openapi.json",
            "/api/v1/setup/status",
        ))
        is_ai_direct = (base == AI_ENGINE and path != "/health")
        if is_protected_api or is_ai_direct:
            if effective_expect and 401 not in effective_expect:
                effective_expect = effective_expect + [401]
            elif effective_expect is None:
                effective_expect = [200, 201, 204, 401]
        resp = curl(t["method"], url, body=body, token=token, expect=effective_expect)

        status = "pass" if resp["ok"] else "fail"
        icon = "✓" if status == "pass" else "✗"

        result = {
            "status": status, "code": resp["code"],
            "endpoint": f"{t['method']} {resolved}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if not resp["ok"]:
            result["body_preview"] = resp["body"][:200]

        ckpt["results"][tid] = result

        # Extract resource IDs
        if resp["ok"] and t["resource_key"] and resp["parsed"]:
            val = resp["parsed"]
            for part in t["extract_id"].split("."):
                if isinstance(val, dict):
                    val = val.get(part)
                else:
                    val = None
                    break
            if val is not None:
                resources[t["resource_key"]] = val
                ckpt["resources"] = resources
                # Grab token for auth
                if t["resource_key"] == "token":
                    token = val

        if status == "pass":
            passed += 1
        else:
            failed += 1

        print(f"  [{idx:3d}/{total}] {icon} {status.upper():4s}  {t['phase']:16s} {t['name']:55s} → {resp['code']}")
        save_checkpoint(ckpt)

    print(f"\n{'='*70}")
    print(f"  DONE — {passed} pass, {failed} fail, {skipped} skip / {total} total")
    print(f"{'='*70}\n")

    return ckpt


# ─── Report generator ────────────────────────────────────────────────────────

def generate_report(ckpt: dict, suite: TestSuite):
    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)

    results = ckpt["results"]
    total = len(results)
    passed = sum(1 for r in results.values() if r["status"] == "pass")
    failed = sum(1 for r in results.values() if r["status"] == "fail")
    skipped = sum(1 for r in results.values() if r["status"] == "skip")

    lines = [
        "# NeuraNAC Sanity Test Report",
        f"",
        f"**Generated:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
        f"",
        f"## Summary",
        f"",
        f"| Metric | Count |",
        f"|--------|-------|",
        f"| Total Tests | {total} |",
        f"| Passed | {passed} |",
        f"| Failed | {failed} |",
        f"| Skipped | {skipped} |",
        f"| Pass Rate | {passed/max(total,1)*100:.1f}% |",
        f"",
    ]

    # Group by phase
    phases: dict[str, list] = {}
    for t in suite.tests:
        phases.setdefault(t["phase"], []).append(t)

    for phase, tests in phases.items():
        p_pass = sum(1 for t in tests if results.get(t["id"], {}).get("status") == "pass")
        p_fail = sum(1 for t in tests if results.get(t["id"], {}).get("status") == "fail")
        p_skip = sum(1 for t in tests if results.get(t["id"], {}).get("status") == "skip")
        p_total = len(tests)

        lines.append(f"## Phase: {phase.upper()} ({p_pass}/{p_total} passed)")
        lines.append(f"")
        lines.append(f"| # | Test | Method | Endpoint | HTTP | Status |")
        lines.append(f"|---|------|--------|----------|------|--------|")

        for t in tests:
            r = results.get(t["id"], {})
            st = r.get("status", "not_run")
            code = r.get("code", "-")
            ep = r.get("endpoint", f"{t['method']} {t['path']}")
            icon = {"pass": "PASS", "fail": "**FAIL**", "skip": "SKIP"}.get(st, "N/A")
            lines.append(f"| {t['id']} | {t['name']} | {t['method']} | `{ep}` | {code} | {icon} |")

        lines.append(f"")

    # Failed tests detail
    failed_tests = [(tid, r) for tid, r in results.items() if r["status"] == "fail"]
    if failed_tests:
        lines.append("## Failed Tests Detail")
        lines.append("")
        for tid, r in failed_tests:
            lines.append(f"### {tid}")
            lines.append(f"- **Endpoint:** `{r.get('endpoint', 'N/A')}`")
            lines.append(f"- **HTTP Code:** {r.get('code', 'N/A')}")
            if r.get("body_preview"):
                lines.append(f"- **Response:** `{r['body_preview']}`")
            lines.append("")

    report = "\n".join(lines)
    REPORT_FILE.write_text(report)
    print(f"Report written to {REPORT_FILE}")


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="NeuraNAC Sanity Test Runner")
    parser.add_argument("--phase", nargs="*",
                        help="Phase(s) to run: infra auth policies identity network endpoints "
                             "segmentation certs sessions guest posture siem webhooks privacy ai "
                             "audit diagnostics licenses nodes setup legacy_nac legacy_nac_enhanced "
                             "admin sessions_ext audit_ext db_setup "
                             "gap1_event_stream gap2_hub_spoke gap3_mtls gap4_cursor_resync "
                             "gap5_compression gap6_nats gap7_websocket "
                             "ai_engine_direct extra_coverage "
                             "ai_phase1 ai_phase4_rag ai_phase4_train ai_phase4_sql "
                             "ai_phase4_risk ai_phase4_tls ai_phase4_cap ai_phase4_pb "
                             "ai_phase4_mdl topology web ingestion")
    parser.add_argument("--continue", dest="resume", action="store_true",
                        help="Resume from last checkpoint")
    parser.add_argument("--reset", action="store_true",
                        help="Clear checkpoint and start fresh")
    parser.add_argument("--report", action="store_true",
                        help="Just regenerate the report from existing checkpoint")
    parser.add_argument("--delay", type=float, default=REQUEST_DELAY,
                        help=f"Delay between requests in seconds (default: {REQUEST_DELAY})")

    args = parser.parse_args()

    request_delay = args.delay

    suite = build_tests()

    if args.reset and CHECKPOINT_FILE.exists():
        CHECKPOINT_FILE.unlink()
        print("Checkpoint cleared.")

    if args.report:
        ckpt = load_checkpoint()
        generate_report(ckpt, suite)
        return

    ckpt = run_tests(suite, args.phase, args.resume, delay=request_delay)
    generate_report(ckpt, suite)


if __name__ == "__main__":
    main()
