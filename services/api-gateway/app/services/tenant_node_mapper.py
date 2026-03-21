"""Tenant-to-Node Mapping Service — allocation, capacity, and reassignment.

Core invariant: one tenant → many nodes, one node → exactly one tenant.

Provides:
  - Automatic node allocation based on capacity (least-loaded)
  - Quota enforcement before allocation
  - Graceful node release with session drain
  - Capacity overview for the control plane
  - Rebalancing suggestion (which nodes to move)
"""
from typing import Optional, List, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import structlog

logger = structlog.get_logger()


class TenantNodeMapper:
    """Stateless service — all state lives in PostgreSQL."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_allocation_summary(self, tenant_id: str) -> Dict:
        """Return allocation summary for a tenant: allocated nodes, quota, capacity."""
        result = await self.db.execute(text(
            "SELECT q.max_nodes, "
            "(SELECT count(*) FROM neuranac_tenant_node_map WHERE tenant_id = :tid AND status = 'active') as allocated, "
            "(SELECT COALESCE(sum(n.active_sessions), 0) FROM neuranac_node_registry n "
            "  JOIN neuranac_tenant_node_map m ON m.node_id = n.id "
            "  WHERE m.tenant_id = :tid AND m.status = 'active') as total_sessions, "
            "(SELECT COALESCE(avg(n.cpu_pct), 0) FROM neuranac_node_registry n "
            "  JOIN neuranac_tenant_node_map m ON m.node_id = n.id "
            "  WHERE m.tenant_id = :tid AND m.status = 'active') as avg_cpu "
            "FROM neuranac_tenant_quotas q WHERE q.tenant_id = :tid"
        ), {"tid": tenant_id})
        row = result.fetchone()
        if not row:
            return {"max_nodes": 0, "allocated": 0, "total_sessions": 0, "avg_cpu": 0.0}
        return {
            "max_nodes": row[0],
            "allocated": row[1],
            "total_sessions": row[2],
            "avg_cpu": round(float(row[3]), 2),
            "remaining_quota": row[0] - row[1],
        }

    async def find_available_nodes(self, site_id: Optional[str] = None,
                                   limit: int = 10) -> List[Dict]:
        """Find unallocated nodes, optionally filtered by site, ordered by least load."""
        query = (
            "SELECT n.id, n.node_name, n.site_id, n.role, n.k8s_pod_name, "
            "n.k8s_namespace, n.cpu_pct, n.mem_pct, n.active_sessions, n.status "
            "FROM neuranac_node_registry n "
            "WHERE n.status = 'active' "
            "AND n.id NOT IN (SELECT node_id FROM neuranac_tenant_node_map WHERE status = 'active') "
        )
        params = {}
        if site_id:
            query += "AND n.site_id = :sid "
            params["sid"] = site_id
        query += "ORDER BY n.cpu_pct ASC, n.active_sessions ASC LIMIT :lim"
        params["lim"] = limit

        result = await self.db.execute(text(query), params)
        rows = result.fetchall()
        return [
            {
                "node_id": str(r[0]), "node_name": r[1], "site_id": str(r[2]),
                "role": r[3], "k8s_pod_name": r[4], "k8s_namespace": r[5],
                "cpu_pct": r[6], "mem_pct": r[7], "active_sessions": r[8],
                "status": r[9],
            }
            for r in rows
        ]

    async def auto_allocate(self, tenant_id: str, count: int = 1,
                            site_id: Optional[str] = None) -> List[str]:
        """Automatically allocate `count` least-loaded available nodes to the tenant.

        Returns list of allocated node IDs. Raises ValueError if quota exceeded
        or not enough available nodes.
        """
        summary = await self.get_allocation_summary(tenant_id)
        remaining = summary.get("remaining_quota", 0)
        if count > remaining:
            raise ValueError(
                f"Cannot allocate {count} nodes: only {remaining} quota remaining "
                f"(max={summary['max_nodes']}, allocated={summary['allocated']})"
            )

        available = await self.find_available_nodes(site_id=site_id, limit=count)
        if len(available) < count:
            raise ValueError(
                f"Only {len(available)} nodes available, need {count}"
            )

        allocated_ids = []
        for node in available[:count]:
            nid = node["node_id"]
            await self.db.execute(text(
                "INSERT INTO neuranac_tenant_node_map (tenant_id, node_id) VALUES (:tid, :nid)"
            ), {"tid": tenant_id, "nid": nid})
            await self.db.execute(text(
                "UPDATE neuranac_node_registry SET tenant_id = :tid WHERE id = :nid"
            ), {"tid": tenant_id, "nid": nid})
            allocated_ids.append(nid)
            logger.info("Auto-allocated node to tenant",
                        node_id=nid, tenant_id=tenant_id)

        await self.db.commit()
        return allocated_ids

    async def release_all(self, tenant_id: str) -> int:
        """Release all nodes from a tenant. Returns count of released nodes."""
        result = await self.db.execute(text(
            "UPDATE neuranac_tenant_node_map SET status = 'released', released_at = now() "
            "WHERE tenant_id = :tid AND status = 'active' RETURNING node_id"
        ), {"tid": tenant_id})
        rows = result.fetchall()
        for r in rows:
            await self.db.execute(text(
                "UPDATE neuranac_node_registry SET tenant_id = NULL WHERE id = :nid"
            ), {"nid": str(r[0])})
        await self.db.commit()
        logger.info("Released all nodes from tenant",
                    tenant_id=tenant_id, count=len(rows))
        return len(rows)

    async def get_rebalance_suggestions(self) -> List[Dict]:
        """Suggest node rebalancing across tenants based on load imbalance.

        Returns a list of suggestions: which tenant is overloaded, which has spare capacity.
        """
        result = await self.db.execute(text(
            "SELECT t.id, t.name, t.slug, "
            "  count(m.id) as node_count, "
            "  COALESCE(avg(n.cpu_pct), 0) as avg_cpu, "
            "  COALESCE(sum(n.active_sessions), 0) as total_sessions, "
            "  q.max_nodes "
            "FROM tenants t "
            "LEFT JOIN neuranac_tenant_node_map m ON m.tenant_id = t.id AND m.status = 'active' "
            "LEFT JOIN neuranac_node_registry n ON m.node_id = n.id "
            "LEFT JOIN neuranac_tenant_quotas q ON q.tenant_id = t.id "
            "GROUP BY t.id, t.name, t.slug, q.max_nodes "
            "HAVING count(m.id) > 0 "
            "ORDER BY avg(n.cpu_pct) DESC"
        ))
        rows = result.fetchall()
        suggestions = []
        for r in rows:
            avg_cpu = float(r[4])
            if avg_cpu > 80:
                suggestions.append({
                    "tenant_id": str(r[0]), "tenant_name": r[1], "slug": r[2],
                    "node_count": r[3], "avg_cpu": round(avg_cpu, 2),
                    "total_sessions": r[5], "max_nodes": r[6],
                    "suggestion": "scale_up" if r[3] < (r[6] or 999) else "optimize",
                    "reason": f"High CPU ({avg_cpu:.0f}%) across {r[3]} nodes",
                })
            elif avg_cpu < 20 and r[3] > 1:
                suggestions.append({
                    "tenant_id": str(r[0]), "tenant_name": r[1], "slug": r[2],
                    "node_count": r[3], "avg_cpu": round(avg_cpu, 2),
                    "total_sessions": r[5], "max_nodes": r[6],
                    "suggestion": "scale_down",
                    "reason": f"Low utilization ({avg_cpu:.0f}%) with {r[3]} nodes",
                })
        return suggestions
