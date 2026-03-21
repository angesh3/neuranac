"""Namespace Isolation Helper — per-tenant Kubernetes namespace conventions.

Provides utilities for:
  - Generating tenant-specific K8s namespace names
  - Validating namespace ownership
  - Generating resource labels for tenant isolation
  - RBAC policy templates for namespace-level isolation

Naming convention:
  neuranac-{tenant_slug}           — primary namespace
  neuranac-{tenant_slug}-data      — data plane (RADIUS, TACACS+)
  neuranac-{tenant_slug}-bridge    — bridge adapters

Labels:
  neuranac.cisco.com/tenant-id: <uuid>
  neuranac.cisco.com/tenant-slug: <slug>
  neuranac.cisco.com/isolation-mode: row|schema|namespace
"""
import re
from typing import Optional


# K8s namespace max length = 63, prefix "neuranac-" = 4, suffix max "-bridge" = 7 → slug max 52
MAX_SLUG_LEN = 52
NS_PREFIX = "neuranac"
LABEL_PREFIX = "neuranac.cisco.com"


def tenant_namespace(slug: str, suffix: Optional[str] = None) -> str:
    """Generate the primary namespace name for a tenant.

    Args:
        slug: Tenant slug (lowercase alphanumeric + hyphens)
        suffix: Optional suffix like 'data', 'bridge'

    Returns:
        K8s-valid namespace string, e.g. 'neuranac-acme-corp' or 'neuranac-acme-corp-bridge'
    """
    clean = _sanitize_slug(slug)
    ns = f"{NS_PREFIX}-{clean}"
    if suffix:
        ns = f"{ns}-{suffix}"
    return ns[:63]


def tenant_labels(tenant_id: str, slug: str, isolation_mode: str = "row") -> dict:
    """Generate standard K8s labels for tenant-owned resources.

    These labels are applied to all K8s resources (Pods, Services, ConfigMaps)
    belonging to a tenant for filtering, RBAC, and NetworkPolicy selection.
    """
    return {
        f"{LABEL_PREFIX}/tenant-id": tenant_id,
        f"{LABEL_PREFIX}/tenant-slug": _sanitize_slug(slug),
        f"{LABEL_PREFIX}/isolation-mode": isolation_mode,
        f"{LABEL_PREFIX}/managed-by": "neuranac-control-plane",
    }


def tenant_network_policy(tenant_id: str, slug: str) -> dict:
    """Generate a NetworkPolicy spec that isolates a tenant's namespace.

    Only allows:
      - Ingress from pods with the same tenant-id label
      - Ingress from the neuranac-system namespace (control plane)
      - Egress to the same tenant namespace + DNS + NATS
    """
    ns = tenant_namespace(slug)
    labels = tenant_labels(tenant_id, slug)

    return {
        "apiVersion": "networking.k8s.io/v1",
        "kind": "NetworkPolicy",
        "metadata": {
            "name": f"tenant-isolation-{_sanitize_slug(slug)}",
            "namespace": ns,
            "labels": labels,
        },
        "spec": {
            "podSelector": {
                "matchLabels": {
                    f"{LABEL_PREFIX}/tenant-id": tenant_id,
                }
            },
            "policyTypes": ["Ingress", "Egress"],
            "ingress": [
                {
                    "from": [
                        {
                            "podSelector": {
                                "matchLabels": {
                                    f"{LABEL_PREFIX}/tenant-id": tenant_id,
                                }
                            }
                        },
                        {
                            "namespaceSelector": {
                                "matchLabels": {
                                    "kubernetes.io/metadata.name": "neuranac-system",
                                }
                            }
                        },
                    ]
                }
            ],
            "egress": [
                {
                    "to": [
                        {
                            "podSelector": {
                                "matchLabels": {
                                    f"{LABEL_PREFIX}/tenant-id": tenant_id,
                                }
                            }
                        }
                    ]
                },
                {
                    "to": [{"namespaceSelector": {}}],
                    "ports": [
                        {"port": 53, "protocol": "UDP"},
                        {"port": 53, "protocol": "TCP"},
                        {"port": 4222, "protocol": "TCP"},
                    ],
                },
            ],
        },
    }


def tenant_resource_quota(slug: str, tier: str = "standard") -> dict:
    """Generate a K8s ResourceQuota for a tenant namespace."""
    ns = tenant_namespace(slug)
    tier_limits = {
        "free":       {"cpu": "2",  "memory": "4Gi",  "pods": "10"},
        "standard":   {"cpu": "8",  "memory": "16Gi", "pods": "50"},
        "enterprise": {"cpu": "32", "memory": "64Gi", "pods": "200"},
        "unlimited":  {"cpu": "128", "memory": "256Gi", "pods": "1000"},
    }
    limits = tier_limits.get(tier, tier_limits["standard"])

    return {
        "apiVersion": "v1",
        "kind": "ResourceQuota",
        "metadata": {
            "name": f"tenant-quota-{_sanitize_slug(slug)}",
            "namespace": ns,
        },
        "spec": {
            "hard": {
                "requests.cpu": limits["cpu"],
                "requests.memory": limits["memory"],
                "pods": limits["pods"],
            }
        },
    }


def validate_namespace_ownership(namespace: str, tenant_slug: str) -> bool:
    """Check if a namespace belongs to the given tenant."""
    expected = tenant_namespace(tenant_slug)
    return (
        namespace == expected
        or namespace.startswith(f"{expected}-")
    )


def _sanitize_slug(slug: str) -> str:
    """Sanitize a tenant slug for use in K8s resource names."""
    clean = re.sub(r"[^a-z0-9-]", "-", slug.lower())
    clean = re.sub(r"-+", "-", clean).strip("-")
    return clean[:MAX_SLUG_LEN]
