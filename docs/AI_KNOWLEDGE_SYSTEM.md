# NeuraNAC AI Knowledge System

## Overview

The NeuraNAC AI Agent has a built-in knowledge base that enables it to answer any question about Network Access Control (NAC), NeuraNAC product features, competitor comparisons, and operational how-tos — **without requiring an external LLM**.

The knowledge is **embedded in the AI Engine source code** and deployed automatically with every build.

---

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│                    AI Action Router                       │
│  ┌──────────┐  ┌──────────────┐  ┌────────────────────┐ │
│  │Navigation│  │  Pattern      │  │  NAC Knowledge     │ │
│  │ Intents  │→ │  Matching     │→ │  Scoring Engine    │ │
│  └──────────┘  │  (regex)      │  │  (keyword scoring) │ │
│                └──────────────┘  └────────────────────┘ │
│                       ↓                    ↓             │
│              ┌──────────────┐    ┌────────────────────┐ │
│              │ Product KB   │    │ NAC KB             │ │
│              │ (15 intents) │    │ (22 articles)      │ │
│              └──────────────┘    └────────────────────┘ │
└──────────────────────────────────────────────────────────┘
```

### Routing Priority (action_router.py)

1. **Navigation intents** — "Go to policies" → navigates UI
2. **Pattern-matched knowledge intents** — "What is NeuraNAC?" → product knowledge
3. **NAC KB scoring** (for informational queries) — "How does MAB work?" → NAC article
4. **Action intents** — "Show endpoints" → API call
5. **LLM fallback** (if configured)
6. **NAC KB scoring** (for non-informational) — catches remaining
7. **Fuzzy keyword match** — last resort keyword matching
8. **Fallback help message**

---

## Knowledge Files

| File | Location | Content |
|------|----------|---------|
| `product_knowledge.py` | `services/ai-engine/app/intents/` | 15 intents: product overview, features, architecture, getting started, AI capabilities, migration, security, twin-nodes, competitor comparison, greeting, thanks, policy how-to, device how-to, endpoint how-to, troubleshooting |
| `nac_knowledge.py` | `services/ai-engine/app/intents/` | 22 articles: NAC overview, RADIUS, 802.1X, MAB, TACACS+, posture, profiling, segmentation/SGT, guest/BYOD, certificates/PKI, identity sources, shadow AI, risk scoring, TLS fingerprinting, CoA, playbooks, deployment modes, competitors (6 vendors), auth failures, capacity planning, API/integrations, compliance/audit |
| `__init__.py` | `services/ai-engine/app/intents/` | Aggregates all intents into `ALL_INTENTS` |
| `action_router.py` | `services/ai-engine/app/` | Routing logic, informational query detection, NAC KB scoring integration |

---

## How It Deploys Automatically

### 1. Source Code (Git)
All knowledge files are Python source code tracked in git:
```
services/ai-engine/app/intents/
├── __init__.py              # aggregates ALL_INTENTS
├── product_knowledge.py     # 15 product knowledge intents
├── nac_knowledge.py         # 22 NAC domain articles + scoring engine
├── dashboard.py             # dashboard action intents
├── policies.py              # policy action intents
├── ...                      # other domain intents
```

**Any `git clone` or `git pull` gets the latest knowledge.**

### 2. Docker Build
The Dockerfile copies ALL source files into the container:
```dockerfile
# services/ai-engine/Dockerfile
COPY . .   # ← copies all intents/ files into the image
```

**Any `docker compose build ai-engine` bakes knowledge into the image.**

### 3. Docker Compose (Local Dev)
```yaml
# deploy/docker-compose.yml
ai-engine:
  build:
    context: ../services/ai-engine   # ← builds from source
    dockerfile: Dockerfile
```

**`docker compose up` always builds with latest knowledge.**

### 4. Kubernetes / Helm (Production)
```yaml
# deploy/helm/neuranac/templates/ai-engine.yaml
image: "{{ .Values.aiEngine.image.repository }}:{{ .Values.aiEngine.image.tag }}"
```

**CI/CD builds the image → pushes to registry → Helm deploys it.**

### 5. Health Verification
After any deployment, verify knowledge is loaded:
```bash
curl http://<AI_ENGINE_HOST>:8081/knowledge-status
```

Expected response:
```json
{
  "status": "loaded",
  "total_intents": 66,
  "knowledge_intents": 15,
  "nac_knowledge_articles": 22,
  "nac_article_ids": ["nac_overview", "radius_protocol", "dot1x", ...],
  "product_knowledge_intents": 15,
  "product_intent_ids": ["product_overview", "product_features", ...]
}
```

**This endpoint requires no API key** — it's in the public paths list.

---

## How to Add New Knowledge

### Adding a NAC Knowledge Article

Edit `services/ai-engine/app/intents/nac_knowledge.py`:

```python
# Add to NAC_KNOWLEDGE_ARTICLES list:
{
    "id": "your_topic_id",
    "title": "Your Topic Title",
    "keywords": [
        "keyword1", "keyword2", "phrase match",
        # Add stems and variations for better matching
    ],
    "content": (
        "### Your Topic Title\n\n"
        "Detailed markdown content here...\n\n"
        "**Key Points:**\n"
        "- Point 1\n"
        "- Point 2\n"
    ),
},
```

The keyword scoring engine will automatically match queries to your article — **no regex patterns needed**.

### Adding a Product Knowledge Intent

Edit `services/ai-engine/app/intents/product_knowledge.py`:

```python
# Add to PRODUCT_KNOWLEDGE_INTENTS list:
{
    "intent": "your_intent_id",
    "patterns": [
        r"regex pattern 1",
        r"regex pattern 2",
    ],
    "knowledge": "Your markdown response text",
    "description": "Short description",
},
```

Product knowledge intents use **regex pattern matching** for precise control.

### After Adding Knowledge

1. **Rebuild**: `docker compose -f deploy/docker-compose.yml build ai-engine`
2. **Restart**: `docker compose -f deploy/docker-compose.yml up -d ai-engine`
3. **Verify**: `curl http://localhost:8081/knowledge-status`

---

## Keyword Scoring Engine

The NAC knowledge base uses a scoring engine (`nac_knowledge.py:find_best_article()`) instead of rigid regex patterns. This enables it to answer **any** NAC question, even with unusual phrasing.

**Scoring formula:**
- Exact keyword phrase in query: **+3.0** (+ bonus for length)
- Word-level overlap with keywords: **+1.5** per word
- Title words in query: **+2.0** per word
- Minimum threshold to return: **3.0**

**Example:** Query "How does TACACS+ differ from RADIUS?"
- "tacacs" keyword → +3.6 (exact match)
- "radius" keyword → +3.6 (exact match)
- "differ" in title words → no match (but keywords catch it)
- Total: ~7.2 → returns the TACACS+ article

---

## Environment Portability Checklist

| Scenario | Knowledge Available? | How? |
|---|---|---|
| New laptop, clone repo | ✅ | Git clone includes all `.py` files |
| `docker compose up` | ✅ | Dockerfile `COPY . .` bakes files into image |
| CI/CD pipeline builds | ✅ | Same Dockerfile → image includes knowledge |
| Helm deploy to K8s | ✅ | Container image includes knowledge |
| New developer joins | ✅ | `git clone` + `docker compose up` → done |
| Staging/prod environment | ✅ | Same image used across environments |

**No external databases, no file mounts, no environment variables needed for knowledge.** It's pure Python source code baked into the container image.

---

## Monitoring

- **Health**: `GET /health` — overall AI engine health
- **Knowledge**: `GET /knowledge-status` — knowledge base inventory
- **Docker healthcheck**: Runs every 10s, checks `/health`
- **K8s probes**: liveness + readiness + startup probes on `/health`
