"""
RAG-powered Troubleshooter — retrieves relevant knowledge base documents
using pgvector embeddings and feeds them as context to the LLM for
root-cause analysis and recommended fixes.
"""
import os
import json
import hashlib
import structlog
import httpx
from typing import List, Dict, Any, Optional

logger = structlog.get_logger()

LLM_API_URL = os.getenv("AI_LLM_API_URL", "http://localhost:11434/api/generate")
LLM_MODEL = os.getenv("AI_LLM_MODEL", "llama3.1:8b")
PG_DSN = os.getenv("AI_PG_DSN", "postgresql://neuranac:neuranac@localhost:5432/neuranac")

# ─── Built-in knowledge base (used when pgvector is not available) ────────────

KNOWLEDGE_BASE: List[Dict[str, str]] = [
    {"id": "kb-001", "title": "EAP-TLS Authentication Failure",
     "content": "EAP-TLS failures commonly occur due to: 1) Expired client certificate, 2) Untrusted CA in the RADIUS server trust store, 3) Clock skew between client and server, 4) CRL/OCSP check failure. Fix: Verify cert dates, add CA to trust store, sync NTP, check CRL distribution point reachability."},
    {"id": "kb-002", "title": "PEAP/MSCHAPv2 Authentication Failure",
     "content": "PEAP failures often result from: 1) Incorrect password, 2) Account lockout in AD/LDAP, 3) Server certificate not trusted by supplicant, 4) TLS version mismatch. Fix: Reset password, check AD lockout policy, install server cert on client, enable TLS 1.2."},
    {"id": "kb-003", "title": "MAB Authentication Failure",
     "content": "MAB (MAC Authentication Bypass) failures occur when: 1) MAC address not registered in endpoint database, 2) Wrong MAC format (should be AA:BB:CC:DD:EE:FF), 3) MAB not enabled on switch port, 4) RADIUS shared secret mismatch. Fix: Register MAC, normalize format, enable MAB on port, verify shared secret."},
    {"id": "kb-004", "title": "VLAN Assignment Issues",
     "content": "VLAN assignment problems: 1) Policy rule not matching — check condition attributes, 2) VLAN not configured on switch trunk, 3) Tunnel-Private-Group-ID attribute not returned in Access-Accept, 4) Switch ignoring RADIUS VLAN attributes. Fix: Check policy conditions, verify switch VLAN config, check RADIUS attribute in live log."},
    {"id": "kb-005", "title": "CoA (Change of Authorization) Failure",
     "content": "CoA failures: 1) RADIUS CoA port (3799) blocked by firewall, 2) Wrong CoA shared secret, 3) Session-ID mismatch between CoA request and NAS, 4) NAS does not support RFC 5176. Fix: Open port 3799, verify CoA secret matches NAS config, check session ID, verify NAS CoA support."},
    {"id": "kb-006", "title": "Shadow AI Detection — Unauthorized AI Usage",
     "content": "Shadow AI alerts trigger when endpoints access AI services (OpenAI, Anthropic, etc.) without approval. Common scenarios: 1) Developer using ChatGPT API, 2) Copilot extension in IDE, 3) AI-powered SaaS tools. Fix: Create AI data flow policy to allow/block/monitor specific services, educate users, implement DLP."},
    {"id": "kb-007", "title": "High Risk Score Investigation",
     "content": "High risk scores (>70) indicate: 1) Behavioral anomaly — unusual auth time or location, 2) Endpoint posture failure — missing antivirus or OS patches, 3) Identity risk — compromised credentials or excessive failed attempts, 4) AI agent without proper delegation. Fix: Check anomaly details, run posture assessment, review auth logs, validate AI agent registration."},
    {"id": "kb-008", "title": "Policy Drift Detection",
     "content": "Policy drift occurs when actual auth outcomes diverge from intended policy. Causes: 1) Policy rule order changed, 2) New endpoints not matching expected conditions, 3) Identity source sync issues, 4) Time-based conditions expired. Fix: Review policy rule ordering, check condition attributes, force identity sync, update time-based rules."},
    {"id": "kb-009", "title": "NeuraNAC to NeuraNAC Migration Issues",
     "content": "Common migration issues: 1) Policy translation confidence too low — review AI-translated rules manually, 2) SGT values conflict between NeuraNAC and NeuraNAC, 3) Network device shared secrets differ, 4) Event Stream connection fails after migration. Fix: Review translated policies, reconcile SGT numbering, sync shared secrets, reconnect Event Stream."},
    {"id": "kb-010", "title": "RADIUS Live Log Shows No Events",
     "content": "Empty RADIUS live log: 1) RADIUS server not running or not reachable, 2) Network device not configured to send RADIUS to NeuraNAC, 3) Firewall blocking UDP 1812/1813, 4) Shared secret mismatch causing silent drops. Fix: Check RADIUS server health, verify NAS RADIUS config points to NeuraNAC, open firewall ports, test shared secret."},
    {"id": "kb-011", "title": "Certificate Expiry and Renewal",
     "content": "Certificate issues: 1) EAP server certificate expired — clients reject TLS handshake, 2) CA certificate not in client trust store, 3) OCSP responder unreachable, 4) CRL expired. Fix: Renew server cert, distribute CA cert via GPO/MDM, check OCSP URL accessibility, update CRL."},
    {"id": "kb-012", "title": "Guest Portal Not Loading",
     "content": "Guest portal issues: 1) Captive portal redirect not configured on switch, 2) DNS resolution failing in guest VLAN, 3) Certificate warning blocking portal, 4) ACL too restrictive. Fix: Configure switch redirect ACL, allow DNS in guest ACL, use trusted cert for portal, verify pre-auth ACL."},
]


class RAGTroubleshooter:
    """RAG-enhanced troubleshooter with pgvector support and fallback to keyword matching."""

    def __init__(self):
        self._pg_pool = None
        self._pgvector_available = False
        self._llm_available = False

    async def initialize(self):
        """Try to connect to PostgreSQL with pgvector extension."""
        try:
            import asyncpg
            self._pg_pool = await asyncpg.create_pool(PG_DSN, min_size=1, max_size=3)
            row = await self._pg_pool.fetchval("SELECT COUNT(*) FROM pg_extension WHERE extname='vector'")
            self._pgvector_available = row > 0
            if self._pgvector_available:
                await self._ensure_kb_table()
                logger.info("RAG troubleshooter: pgvector available")
            else:
                logger.info("RAG troubleshooter: pgvector not installed, using keyword matching")
        except Exception as e:
            logger.warning("RAG troubleshooter: DB unavailable, using built-in KB", error=str(e))
            self._pgvector_available = False

        # Check LLM
        try:
            async with httpx.AsyncClient(timeout=3) as client:
                resp = await client.get(LLM_API_URL.replace("/api/generate", "/api/tags"))
                self._llm_available = resp.status_code == 200
        except Exception:
            self._llm_available = False
        logger.info("RAG troubleshooter initialized", pgvector=self._pgvector_available, llm=self._llm_available)

    async def _ensure_kb_table(self):
        """Create the knowledge base table with vector column if it doesn't exist."""
        if not self._pg_pool:
            return
        await self._pg_pool.execute("""
            CREATE TABLE IF NOT EXISTS ai_knowledge_base (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                embedding vector(384),
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        # Seed built-in KB if empty
        count = await self._pg_pool.fetchval("SELECT COUNT(*) FROM ai_knowledge_base")
        if count == 0:
            for doc in KNOWLEDGE_BASE:
                await self._pg_pool.execute(
                    "INSERT INTO ai_knowledge_base (id, title, content) VALUES ($1, $2, $3) ON CONFLICT DO NOTHING",
                    doc["id"], doc["title"], doc["content"],
                )
            logger.info("Seeded knowledge base", count=len(KNOWLEDGE_BASE))

    async def troubleshoot(self, query: str, context: Optional[Dict] = None) -> Dict[str, Any]:
        """Analyze an issue using RAG: retrieve relevant KB docs, then generate analysis."""
        # Step 1: Retrieve relevant documents
        docs = await self._retrieve(query)

        # Step 2: Generate analysis with LLM (or rule-based fallback)
        if self._llm_available:
            return await self._llm_analyze(query, docs, context)
        else:
            return self._keyword_analyze(query, docs, context)

    async def _retrieve(self, query: str, top_k: int = 3) -> List[Dict[str, str]]:
        """Retrieve most relevant KB documents for the query."""
        # TODO: When embeddings are available, use pgvector cosine similarity
        # For now, use keyword matching
        query_lower = query.lower()
        scored = []
        for doc in KNOWLEDGE_BASE:
            score = 0
            title_lower = doc["title"].lower()
            content_lower = doc["content"].lower()
            for word in query_lower.split():
                if len(word) > 3:
                    if word in title_lower:
                        score += 3
                    if word in content_lower:
                        score += 1
            if score > 0:
                scored.append((score, doc))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [doc for _, doc in scored[:top_k]]

    async def _llm_analyze(self, query: str, docs: List[Dict], context: Optional[Dict]) -> Dict[str, Any]:
        """Use LLM with retrieved context to generate troubleshooting analysis."""
        kb_context = "\n\n".join(f"[{d['title']}]\n{d['content']}" for d in docs)
        prompt = f"""You are NeuraNAC AI Troubleshooter. Analyze the network issue using the knowledge base context provided.

Knowledge Base Context:
{kb_context}

User Issue: {query}

Provide a structured response with:
1. Root Cause (most likely reason)
2. Recommended Fixes (numbered steps)
3. Evidence (what to check)

Respond in JSON format: {{"root_cause": "...", "recommended_fixes": ["fix1", "fix2"], "evidence": ["evidence1"], "confidence": 0.0-1.0, "kb_articles_used": ["id1"]}}"""

        try:
            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(LLM_API_URL, json={
                    "model": LLM_MODEL, "prompt": prompt, "stream": False, "temperature": 0.2,
                })
                text = resp.json().get("response", "")
                import re
                m = re.search(r'\{[^}]+\}', text, re.DOTALL)
                if m:
                    parsed = json.loads(m.group())
                    parsed["source"] = "rag_llm"
                    parsed["kb_docs_retrieved"] = len(docs)
                    return parsed
                return {"root_cause": text, "recommended_fixes": [], "evidence": [],
                        "confidence": 0.5, "source": "rag_llm_raw", "kb_docs_retrieved": len(docs)}
        except Exception as e:
            logger.error("LLM analysis failed", error=str(e))
            return self._keyword_analyze(query, docs, context)

    def _keyword_analyze(self, query: str, docs: List[Dict], context: Optional[Dict]) -> Dict[str, Any]:
        """Fallback keyword-based analysis using retrieved KB documents."""
        if not docs:
            return {
                "root_cause": "Unable to determine root cause from available information.",
                "recommended_fixes": [
                    "Check RADIUS live log for detailed error messages",
                    "Verify network device shared secret configuration",
                    "Run a connectivity test to the authentication server",
                ],
                "evidence": [],
                "confidence": 0.2,
                "source": "keyword_fallback",
                "kb_docs_retrieved": 0,
            }

        best_doc = docs[0]
        # Extract fixes from content (lines starting with numbers or after "Fix:")
        content = best_doc["content"]
        fixes = []
        if "Fix:" in content:
            fix_text = content.split("Fix:")[-1].strip()
            fixes = [f.strip() for f in fix_text.split(",") if f.strip()]

        return {
            "root_cause": best_doc["title"],
            "recommended_fixes": fixes or ["Review the knowledge base article for detailed steps"],
            "evidence": [f"Matched KB article: {best_doc['title']}"],
            "confidence": 0.6,
            "source": "keyword_match",
            "kb_docs_retrieved": len(docs),
            "kb_article": best_doc["id"],
        }
