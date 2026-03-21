# NeuraNAC AI Features — Complete Technical Guide

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Three AI Touchpoints](#three-ai-touchpoints)
4. [16 AI Modules](#16-ai-modules)
5. [LLM Configuration](#llm-configuration)
6. [Inline AI in RADIUS](#inline-ai-in-radius)
7. [AI Chat Interface](#ai-chat-interface)
8. [Background & On-Demand AI](#background--on-demand-ai)
9. [Data Flow](#data-flow)
10. [Design Principles](#design-principles)
11. [Environment Variables](#environment-variables)
12. [API Endpoints](#api-endpoints)
13. [File Inventory](#file-inventory)

---

## Overview

NeuraNAC embeds **16 AI modules** across its stack, providing real-time security intelligence during RADIUS authentication, a natural language chat interface for operators, and background analytics for capacity planning, threat detection, and automated incident response.

**Key facts:**
- **16 AI modules** loaded at startup as a singleton `AIContainer`
- **66 action/knowledge intents** for the chat interface
- **37 knowledge articles** (22 NAC + 15 product)
- **LLM is optional** — all core features work without it
- **4 inline AI calls** per RADIUS authentication (profile, risk, anomaly, drift)
- **Circuit breaker** ensures AI never blocks RADIUS authentication

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        FRONTEND (React)                             │
│  ┌──────────────┐  ┌──────────────────┐  ┌───────────────────────┐ │
│  │AIModeToggle  │  │ AIChatLayout     │  │ AIResponseCard        │ │
│  │(Agent/Dash)  │  │ (ChatGPT-like UI)│  │ (table/nav/text/error)│ │
│  └──────┬───────┘  └────────┬─────────┘  └───────────────────────┘ │
│         │                   │  POST /api/v1/ai/chat                │
└─────────┼───────────────────┼──────────────────────────────────────┘
          │                   ▼
┌─────────┼───────────────────────────────────────────────────────────┐
│         │         API GATEWAY (FastAPI, port 8080)                  │
│         │  ┌──────────────────────────────────┐                    │
│         │  │ ai_chat.py — proxy to AI Engine  │                    │
│         │  │ Passes user's JWT token through  │                    │
│         │  └──────────────┬───────────────────┘                    │
└─────────┼─────────────────┼────────────────────────────────────────┘
          │                 ▼
┌─────────┼───────────────────────────────────────────────────────────┐
│         │         AI ENGINE (FastAPI, port 8081)                    │
│         │  ┌──────────────────────────────────────────────────────┐ │
│         │  │              16 AI Modules                           │ │
│         │  │  ActionRouter, EndpointProfiler, RiskScorer,        │ │
│         │  │  ShadowAIDetector, NLPolicyAssistant, Troubleshooter│ │
│         │  │  AnomalyDetector, DriftDetector, RAGTroubleshooter, │ │
│         │  │  TrainingPipeline, NLToSQL, AdaptiveRisk,           │ │
│         │  │  TLSFingerprinter, CapacityPlanner, PlaybookEngine, │ │
│         │  │  ModelRegistry                                      │ │
│         │  └──────────────────────────────────────────────────────┘ │
└─────────┼──────────────────────────────────────────────────────────┘
          │                 ▲
          │                 │  Inline AI calls (3s timeout)
          │                 │
┌─────────┼─────────────────┼────────────────────────────────────────┐
│         │    RADIUS SERVER (Go, port 1812/1813)                    │
│         │  ┌──────────────┴───────────────────┐                    │
│         │  │ ai_client.go — circuit breaker    │                   │
│         │  │ Profile → Risk → Anomaly → Drift  │                   │
│         │  └──────────────────────────────────┘                    │
└─────────┼──────────────────────────────────────────────────────────┘
```

---

## Three AI Touchpoints

NeuraNAC's AI features are accessed through three distinct integration points:

### 1. User-Facing AI Chat

Operators interact with a full-screen ChatGPT-like interface. Messages are routed through the API Gateway to the AI Engine's ActionRouter, which classifies the intent and returns structured responses.

**Flow:**
```
User types message → AIChatLayout.tsx
  → POST /api/v1/ai/chat (API Gateway, ai_chat.py)
    → Proxied to AI Engine with user's JWT token
      → ActionRouter.route() classifies the message
        → Tier 1: Pattern match (66 regex intents)
        → Tier 1: NAC KB scoring (22 articles, keyword engine)
        → Tier 2: Ollama LLM fallback (optional)
        → Tier 3: Fuzzy keyword match → fallback help
      → Returns structured response
    → Rendered by AIResponseCard.tsx
```

**Response types rendered by the frontend:**

| Type | Example Query | Rendering |
|------|---------------|-----------|
| `text` | "What is 802.1X?" | Markdown knowledge card |
| `api_result` | "Show all endpoints" | Data table with results |
| `navigation` | "Go to policies" | Auto-navigates the UI |
| `policy_translation` | "Allow engineers on VLAN 100" | Policy rules JSON card |
| `error` | API/AI failure | Error message card |

### 2. Inline AI in RADIUS Authentication

Four AI calls execute automatically during every RADIUS authentication. The Go-based RADIUS server calls the AI Engine via HTTP with a 3-second timeout and circuit breaker. AI results enrich the auth decision but never block it.

**Flow per RADIUS auth:**
```
Access-Request arrives → handler.go
  → Policy evaluation (gRPC to policy-engine)
  → AI Step 1: ProfileEndpoint(mac)     — async goroutine, non-blocking
  → AI Step 2: ComputeRisk(session)     — inline, 3s timeout
  → AI Step 3: RecordDrift(outcome)     — fire-and-forget goroutine
  → AI Step 4: AnalyzeAnomaly(session)  — inline, 3s timeout
  → Access-Accept/Reject sent to switch
```

### 3. Background & On-Demand AI

Modules that run on schedule, on security events, or when explicitly triggered by operators via API calls or the chat interface.

---

## 16 AI Modules

### Group 1: Real-Time Security (inline during every RADIUS auth)

| # | Module | File | What It Does |
|---|--------|------|--------------|
| 1 | **EndpointProfiler** | `profiler.py` | Classifies devices using OUI database (~500 vendors) + rule-based heuristics. Supports ONNX model if trained. Outputs: device_type (18 categories including `ai-agent`, `ai-gpu-node`), vendor, OS, confidence score |
| 2 | **RiskScorer** | `risk.py` | Computes a 0–100 composite risk score from 4 dimensions: behavioral (failed auths, unusual time), identity (stale credentials, group changes), endpoint (posture failures, unknown device), AI activity (unauthorized AI usage). Classifies into: low (<30), medium (30–59), high (60–79), critical (80+) |
| 3 | **AnomalyDetector** | `anomaly.py` | Builds per-entity statistical baselines using a sliding window (1000 observations). Uses z-score deviation to flag anomalies. Baselines persisted in Redis (`AI_REDIS_URL`), falls back to in-memory. Example: user normally authenticates at 9am from building A but just authenticated at 3am from building C |
| 4 | **PolicyDriftDetector** | `anomaly.py` | Records expected vs actual auth decisions over time. Analyzes divergence patterns — e.g., if a "permit" policy starts seeing 20% denials, drift is detected. Also tracks policy evaluation timing |

### Group 2: Security Intelligence (on-demand)

| # | Module | File | What It Does |
|---|--------|------|--------------|
| 5 | **ShadowAIDetector** | `shadow.py` | Detects unauthorized AI service usage by matching DNS queries and network flows against 14 built-in signatures: OpenAI, Anthropic, Google Gemini, GitHub Copilot, Hugging Face, Replicate, Midjourney, DALL-E, Stability AI, Cohere, AWS Bedrock, Azure OpenAI, Ollama, vLLM. Loads custom signatures from PostgreSQL. Classifies by risk: high (LLMs), medium (coding/image AI), low (enterprise cloud AI) |
| 6 | **TLSFingerprinter** | `tls_fingerprint.py` | Analyzes TLS Client Hello to generate JA3/JA4 hashes. Matches against 16 JA3 + 3 JA4 known signatures (Chrome, Firefox, curl, Python, malware, C2 frameworks). Detects TLS version downgrade, unusual cipher suites, known-bad fingerprints. Custom signatures can be added via API |
| 7 | **AdaptiveRiskEngine** | `adaptive_risk.py` | Learns optimal risk thresholds from operator feedback. When an operator marks a decision as correct/incorrect, the system records it. After every 10 feedback entries (minimum 20), recalibrates quarantine/monitor/allow boundaries per tenant. Default thresholds: quarantine ≥70, monitor ≥40, allow <40 |

### Group 3: Natural Language Interface (user-facing)

| # | Module | File | What It Does |
|---|--------|------|--------------|
| 8 | **ActionRouter** | `action_router.py` | The central brain of the AI chat. Routes natural language to 66 intents across 3 tiers: (1) regex pattern matching + 37 knowledge articles with keyword scoring, (2) optional Ollama LLM fallback, (3) fuzzy keyword match + help message. Distinguishes informational queries from action requests. Executes API calls using the user's JWT token |
| 9 | **NLPolicyAssistant** | `nlp_policy.py` | Translates natural language to structured policy rules. Sends a prompt to the LLM with NeuraNAC's full policy schema (attributes, operators, actions). Returns JSON with rules + explanation. Example: "Block all BYOD devices after 6pm" → policy rules JSON |
| 10 | **RAGTroubleshooter** | `rag_troubleshooter.py` | Retrieval-Augmented Generation for root-cause analysis. Searches 12 built-in KB articles (EAP-TLS failures, PEAP issues, MAB problems, VLAN assignment, CoA failures, Shadow AI, risk scores, policy drift, migration, etc.). Feeds relevant articles as context to LLM. Can use pgvector embeddings if available |
| 11 | **NLToSQL** | `nl_to_sql.py` | Converts natural language questions to safe, read-only SQL. 18 pre-built query templates for common questions (endpoint counts, session stats, policy summaries). Falls back to LLM with schema context for complex questions. Safety regex blocks any non-SELECT queries to prevent data modification |

### Group 4: Operations & ML Ops

| # | Module | File | What It Does |
|---|--------|------|--------------|
| 12 | **AITroubleshooter** | `troubleshooter.py` | Rule-based diagnostics for common network issues. Pattern-matches query keywords to known issue categories (auth failures, VLAN assignment, CoA, posture). Returns root cause, issue list, recommended fixes, and evidence |
| 13 | **TrainingPipeline** | `training_pipeline.py` | Collects labeled training samples (MAC attributes → device_type). Trains sklearn classifiers. Exports to ONNX format that EndpointProfiler can load at runtime. Tracks training stats and sample counts |
| 14 | **CapacityPlanner** | `capacity_planner.py` | Records time-series infrastructure metrics (RADIUS TPS, endpoint count, session count). Uses linear regression + exponential smoothing to forecast when capacity limits will be hit. Returns forecasts per metric with horizon |
| 15 | **PlaybookEngine** | `playbooks.py` | 6 built-in automated incident response playbooks: `quarantine_endpoint`, `investigate_shadow_ai`, `respond_to_anomaly`, `remediate_drift`, `escalate_critical`, `certificate_expiry`. Supports custom playbooks via API. Executes multi-step workflows with context variables |
| 16 | **ModelRegistry** | `model_registry.py` | Manages ML model versions with A/B testing. Registers models with name, version, type, endpoint, weight. Creates experiments with traffic splits between model versions. Tracks which model is serving which percentage of requests |

---

## LLM Configuration

### Current Status: No LLM Running

> **Important:** The NeuraNAC AI Agent currently runs **entirely without an LLM**. No Ollama, no
> OpenAI, no cloud LLM — nothing. All intelligence comes from built-in pattern matching,
> keyword scoring, and rule-based logic. The code is **pre-wired** to use an LLM as an
> optional enhancement, but no LLM is deployed or required.

**What's in the code vs what's running:**

| Layer | LLM Status | Details |
|-------|------------|---------|
| **Source code** | Pre-wired | 4 modules contain `httpx.post(LLM_API_URL, ...)` calls |
| **Docker Compose** | Not included | No Ollama or LLM service in `docker-compose.yml` |
| **Runtime** | Not running | At startup, `check_llm()` pings Ollama, gets connection refused, sets `_llm_available = False` |
| **User queries** | Answered without LLM | All 37 knowledge articles + 66 intents work via pattern matching and keyword scoring |

### Pre-Wired LLM Settings (Not Active)

| Setting | Default Value | Env Var |
|---------|---------------|---------|
| **LLM Model** | `llama3` (Meta Llama 3) | `AI_LLM_MODEL` |
| **LLM API URL** | `http://localhost:11434/api/generate` | `AI_LLM_API_URL` |
| **LLM Required?** | **No** — optional fallback only | — |
| **Temperature** | `0.1` (low, deterministic) | Hardcoded |
| **Timeout** | 30s for LLM calls | Hardcoded |

### LLM Usage by Module

Only **4 of 16 modules** can optionally use an LLM. The other 12 are fully self-contained
and never call any LLM:

| Module | What LLM Would Do (if enabled) | Works Without LLM? |
|--------|--------------------------------|---------------------|
| **ActionRouter** | Intent classification when patterns miss | Yes — uses pattern matching + NAC KB scoring |
| **RAGTroubleshooter** | Root-cause analysis with KB context | Yes — returns KB articles directly |
| **NLToSQL** | Generate SQL when templates miss | Yes — uses 18 pre-built query templates |
| **NLPolicyAssistant** | Translate complex NL to policy rules | Partially — needs LLM for complex translations |

### Three-Tier Intelligence

```
Tier 1: Pattern Matching + Knowledge Base     ← ACTIVE TODAY (handles everything)
  ├── 66 regex-matched intents (product KB + action intents)
  ├── 22 NAC knowledge articles (keyword-scoring engine)
  └── 50+ fuzzy keyword fallback mappings

Tier 2: LLM Fallback                          ← NOT ACTIVE (no LLM deployed)
  └── Would send intent list + user query to LLM
  └── Would parse JSON response → route to matching intent

Tier 3: Fallback Help Message                 ← ACTIVE (last resort)
```

At startup, the AI Engine calls `ActionRouter.check_llm()` which pings `GET /api/tags`
on the Ollama URL. If Ollama is not reachable, `_llm_available` is set to `False` and
Tier 2 is silently skipped for the lifetime of the process.

### Enabling a Local LLM (Optional)

See **[docs/LOCAL_LLM_GUIDE.md](LOCAL_LLM_GUIDE.md)** for a comprehensive guide on
deploying a private, containerized LLM with self-learning capabilities.

Quick start:
```bash
# Add Ollama to your stack
docker compose -f deploy/docker-compose.yml --profile llm up -d

# Or standalone
ollama serve &
ollama pull llama3
```

Set `AI_LLM_API_URL=http://ollama:11434/api/generate` in the AI Engine environment.

---

## Inline AI in RADIUS

### How It Works

The Go RADIUS server (`services/radius-server/internal/handler/`) makes inline HTTP calls to the Python AI Engine during every RADIUS authentication.

```
Access-Request
  │
  ├─→ Policy evaluation (gRPC to policy-engine)
  │
  ├─→ AI Step 1: Profile endpoint
  │   POST /api/v1/profile { mac_address: "AA:BB:CC:DD:EE:FF" }
  │   Response: { device_type: "iphone", vendor: "Apple", confidence: 0.92 }
  │   (Runs in async goroutine — non-blocking)
  │
  ├─→ AI Step 2: Compute risk score
  │   POST /api/v1/risk-score { session_id, username, endpoint_mac, ... }
  │   Response: { total_score: 45, risk_level: "medium", factors: [...] }
  │
  ├─→ AI Step 3: Record policy drift
  │   POST /api/v1/drift/record { policy_id, expected: "permit", actual: "deny" }
  │   (Fire-and-forget goroutine — never blocks)
  │
  └─→ AI Step 4: Analyze anomaly
      POST /api/v1/anomaly/analyze { endpoint_mac, auth_time_hour, day_of_week }
      Response: { is_anomalous: true, anomaly_score: 78, recommendation: "..." }
```

### Circuit Breaker

The `AIClient` in `ai_client.go` has a built-in circuit breaker to protect RADIUS from AI Engine failures:

| Parameter | Value |
|-----------|-------|
| HTTP timeout | 3 seconds |
| Circuit opens after | 3 consecutive failures |
| Circuit recovery | Auto half-open after 30 seconds |
| 4xx errors | Do not count toward circuit breaker |
| 5xx errors | Count as failures |
| Drift recording | Fire-and-forget (never blocks) |
| Profiling | Async goroutine (never blocks) |

When the circuit is open, all AI calls are skipped and RADIUS continues operating normally without AI enrichment.

### Device Type Classification

The EndpointProfiler classifies devices into 18 categories:

```
windows-pc, macos, linux-workstation, iphone, android,
ipad, printer, ip-phone, camera, iot-sensor,
smart-tv, gaming-console, server, switch, access-point,
ai-agent, ai-gpu-node, unknown
```

---

## AI Chat Interface

### Frontend Components

| Component | File | Purpose |
|-----------|------|---------|
| **AIModeToggle** | `web/src/components/AIModeToggle.tsx` | Animated pill toggle between "Agent" (AI chat) and "Dash" (classic dashboard). Violet gradient for AI mode |
| **AIChatLayout** | `web/src/components/AIChatLayout.tsx` | Full-screen ChatGPT-like layout with message history, auto-scroll, textarea input, suggestion chips |
| **AIResponseCard** | `web/src/components/AIResponseCard.tsx` | Polymorphic response cards: renders markdown, data tables, navigation actions, policy rules, or errors based on response type |
| **ai-store** | `web/src/lib/ai-store.ts` | Zustand store with localStorage persistence. Manages: aiMode toggle, messages (last 200), loading state, context-aware suggestions, current route |

### Context-Aware Suggestions

The AI chat provides different suggestion chips based on the current page:

| Current Route | Suggestions |
|---------------|-------------|
| `/` (Dashboard) | System status, Active sessions, Audit log, Shadow AI |
| `/policies` | List policies, Create policy, Translate policy, Check drift |
| `/network-devices` | List devices, Add switch, Discover devices |
| `/endpoints` | List endpoints, Profile device, Shadow AI report |
| `/legacy-nac` | legacy sync status, Start migration, Compare policies |

### ActionRouter Routing Priority

1. **Navigation intents** — "Go to policies" → navigates UI
2. **Pattern-matched knowledge** — "What is NeuraNAC?" → product knowledge
3. **NAC KB scoring** (informational queries) — "How does MAB work?" → NAC article
4. **Action intents** — "Show endpoints" → API call with user's JWT
5. **NLP policy passthrough** — "Create a rule to block BYOD" → NLPolicyAssistant
6. **LLM fallback** (if Ollama available)
7. **NAC KB scoring** (non-informational) — catches remaining
8. **Fuzzy keyword match** — last resort
9. **Fallback help message**

### NAC Knowledge Scoring Engine

The NAC knowledge base (`nac_knowledge.py`) uses a keyword scoring engine instead of rigid regex:

**Scoring formula:**
- Exact keyword phrase match: **+3.0** (+ bonus for phrase length)
- Word-level overlap: **+1.5** per matching word
- Title words in query: **+2.0** per word
- Minimum threshold: **3.0** required to return an article

**22 NAC Knowledge Articles:**

| Article ID | Topic |
|------------|-------|
| `nac_overview` | What is NAC, 802.1X framework |
| `radius_protocol` | RADIUS protocol deep dive |
| `dot1x` | 802.1X authentication flow |
| `mab` | MAC Authentication Bypass |
| `tacacs` | TACACS+ protocol |
| `posture` | Endpoint posture assessment |
| `profiling` | Device profiling techniques |
| `segmentation` | SGT / TrustSec segmentation |
| `guest_byod` | Guest access and BYOD onboarding |
| `certificates` | PKI, certificates, EAP-TLS |
| `identity_sources` | LDAP, AD, SAML, SCIM |
| `shadow_ai` | Shadow AI detection in NAC |
| `risk_scoring` | AI-driven risk scoring |
| `tls_fingerprint` | JA3/JA4 TLS fingerprinting |
| `coa` | Change of Authorization (RFC 5176) |
| `playbooks` | Automated incident response |
| `deployment_modes` | Standalone, hybrid, multi-site |
| `competitors_overview` | NeuraNAC vs 6 competitors (NeuraNAC, Aruba, Forescout, Portnox, Fortinet, Juniper) |
| `auth_failures` | Troubleshooting authentication failures |
| `capacity_planning` | Infrastructure capacity planning |
| `api_integration` | REST API and integrations |
| `compliance_audit` | GDPR, HIPAA, PCI-DSS, SOX, NIST, ISO 27001 |

---

## Background & On-Demand AI

### Shadow AI Detection

Detects unauthorized AI service usage on the network using 14 built-in signatures:

| Service | Category | Risk Level |
|---------|----------|------------|
| OpenAI ChatGPT | LLM | High |
| Anthropic Claude | LLM | High |
| Google Gemini | LLM | High |
| GitHub Copilot | Coding | Medium |
| Hugging Face | ML Platform | Medium |
| Replicate | ML Platform | Medium |
| Midjourney | Image Gen | Medium |
| DALL-E | Image Gen | Medium |
| Stability AI | Image Gen | Medium |
| Cohere | LLM | Medium |
| AWS Bedrock | Cloud AI | Low |
| Azure OpenAI | Cloud AI | Low |
| Ollama (local) | Local LLM | Medium |
| vLLM (local) | Local LLM | Medium |

Custom signatures can be added via the PostgreSQL `ai_services` table.

### Automated Playbooks

6 built-in incident response playbooks:

| Playbook | Trigger | Steps |
|----------|---------|-------|
| `quarantine_endpoint` | High-risk device detected | Isolate → notify → investigate → remediate |
| `investigate_shadow_ai` | Unauthorized AI usage | Capture flow → identify user → check policy → alert |
| `respond_to_anomaly` | Behavioral anomaly flagged | Verify → correlate → escalate if confirmed |
| `remediate_drift` | Policy drift detected | Analyze delta → rollback or update → verify |
| `escalate_critical` | Critical risk score (≥80) | Page on-call → gather evidence → incident ticket |
| `certificate_expiry` | Cert near expiration | Alert → auto-renew if possible → notify admin |

---

## Data Flow

```
                    ┌─────────────┐
                    │   Browser   │
                    │   (React)   │
                    └──────┬──────┘
                           │ AI Chat / Dashboard
                           ▼
                    ┌──────────────┐
                    │ API Gateway  │◄── JWT Auth + AI permission check
                    │  (port 8080) │
                    └──┬───────┬───┘
                       │       │
            ┌──────────┘       └──────────┐
            ▼                             ▼
    ┌───────────────┐            ┌────────────────┐
    │  AI Engine    │            │ Policy Engine  │
    │  (port 8081)  │            │ (gRPC :50051)  │
    │               │            └───────┬────────┘
    │ 16 modules    │                    │
    │               │◄───────────────────┤
    │               │  Inline AI calls   │
    │               │  (3s timeout +     │
    │               │   circuit breaker) │
    │               │                    │
    │               │            ┌───────┴────────┐
    │               │            │ RADIUS Server  │
    │               │            │  (Go, :1812)   │
    │               │            │  ai_client.go  │
    └───────┬───────┘            └────────────────┘
            │
     ┌──────┼──────┐
     ▼      ▼      ▼
┌────────┐ ┌────────┐ ┌──────────────┐
│ Redis  │ │Postgres│ │ Ollama (opt) │
│        │ │        │ │ llama3       │
│Anomaly │ │Sessions│ │ LLM fallback │
│baseline│ │AI sigs │ │              │
│Risk thr│ │Audit   │ │              │
└────────┘ └────────┘ └──────────────┘
```

---

## Design Principles

1. **AI never blocks RADIUS** — 3-second timeout + circuit breaker ensures authentication always completes even if AI Engine is down. Profiling is async, drift recording is fire-and-forget.

2. **LLM is optional** — All core features work without Ollama or any external LLM. Pattern matching, keyword scoring, sklearn ML, and rule-based logic handle everything. LLM enhances 4 modules when available.

3. **Graceful degradation** — If Redis is down, anomaly baselines fall back to in-memory. If pgvector is unavailable, RAG uses built-in KB. If LLM is unavailable, NLP falls back to templates. If AI Engine is down, RADIUS operates without AI enrichment.

4. **Per-tenant learning** — Adaptive risk thresholds and policy drift are tracked per tenant. Feedback loops allow each tenant's AI to calibrate independently.

5. **Operator feedback loop** — Risk decisions can be corrected by operators via `/api/v1/risk/feedback`. The system learns from that feedback and auto-adjusts thresholds.

6. **Security by design** — NL-to-SQL blocks non-SELECT queries. API calls use the operator's JWT token (not a service account). Shadow AI detection runs with built-in signatures (no external dependency).

7. **Knowledge is code** — All knowledge articles are Python source code, not external files or databases. They deploy automatically with every Docker build and are version-controlled in git.

---

## Environment Variables

| Variable | Default | Used By | Description |
|----------|---------|---------|-------------|
| `AI_LLM_API_URL` | `http://localhost:11434/api/generate` | ActionRouter, NLPolicy, RAG, NLToSQL | Ollama LLM API endpoint |
| `AI_LLM_MODEL` | `llama3` | ActionRouter, NLPolicy, RAG, NLToSQL | LLM model name |
| `AI_ENGINE_URL` | `http://localhost:8081` | RADIUS ai_client, API Gateway | AI Engine base URL |
| `AI_ENGINE_API_KEY` | `neuranac_ai_dev_key_change_in_production` | AI Engine, API Gateway | API key for AI Engine auth |
| `AI_INLINE_ENABLED` | `true` (not "false") | RADIUS ai_client | Enable/disable inline AI in RADIUS |
| `AI_REDIS_URL` | `redis://localhost:6379/1` | AnomalyDetector, AdaptiveRisk | Redis for baselines and thresholds |
| `AI_BASELINE_TTL` | `604800` (7 days) | AnomalyDetector | Baseline TTL in Redis (seconds) |
| `AI_MODEL_PATH` | `/data/models` | EndpointProfiler | Path to ONNX models |
| `AI_PG_DSN` | `postgresql://neuranac:neuranac@localhost:5432/neuranac` | RAG, NLToSQL | PostgreSQL connection for pgvector/queries |
| `API_GATEWAY_URL` | `http://localhost:8080` | ActionRouter | API Gateway URL for executing actions |

---

## API Endpoints

### AI Engine (port 8081)

| Method | Path | Module | Auth |
|--------|------|--------|------|
| `GET` | `/health` | — | Public |
| `GET` | `/knowledge-status` | — | Public |
| `POST` | `/api/v1/profile` | EndpointProfiler | API Key |
| `POST` | `/api/v1/risk-score` | RiskScorer | API Key |
| `POST` | `/api/v1/shadow-ai/detect` | ShadowAIDetector | API Key |
| `POST` | `/api/v1/nlp/translate` | NLPolicyAssistant | API Key |
| `POST` | `/api/v1/troubleshoot` | AITroubleshooter | API Key |
| `POST` | `/api/v1/anomaly/analyze` | AnomalyDetector | API Key |
| `POST` | `/api/v1/drift/record` | PolicyDriftDetector | API Key |
| `GET` | `/api/v1/drift/analyze` | PolicyDriftDetector | API Key |
| `POST` | `/api/v1/ai/chat` | ActionRouter | API Key |
| `GET` | `/api/v1/ai/capabilities` | — | API Key |
| `POST` | `/api/v1/rag/troubleshoot` | RAGTroubleshooter | API Key |
| `POST` | `/api/v1/training/sample` | TrainingPipeline | API Key |
| `GET` | `/api/v1/training/stats` | TrainingPipeline | API Key |
| `POST` | `/api/v1/training/train` | TrainingPipeline | API Key |
| `POST` | `/api/v1/nl-sql/query` | NLToSQL | API Key |
| `POST` | `/api/v1/risk/feedback` | AdaptiveRiskEngine | API Key |
| `GET` | `/api/v1/risk/thresholds` | AdaptiveRiskEngine | API Key |
| `GET` | `/api/v1/risk/adaptive-stats` | AdaptiveRiskEngine | API Key |
| `POST` | `/api/v1/tls/analyze-ja3` | TLSFingerprinter | API Key |
| `POST` | `/api/v1/tls/analyze-ja4` | TLSFingerprinter | API Key |
| `POST` | `/api/v1/tls/compute-ja3` | TLSFingerprinter | API Key |
| `POST` | `/api/v1/tls/custom-signature` | TLSFingerprinter | API Key |
| `GET` | `/api/v1/tls/detections` | TLSFingerprinter | API Key |
| `GET` | `/api/v1/tls/stats` | TLSFingerprinter | API Key |
| `POST` | `/api/v1/capacity/record` | CapacityPlanner | API Key |
| `GET` | `/api/v1/capacity/forecast` | CapacityPlanner | API Key |
| `GET` | `/api/v1/capacity/metrics` | CapacityPlanner | API Key |
| `GET` | `/api/v1/playbooks` | PlaybookEngine | API Key |
| `GET` | `/api/v1/playbooks/{id}` | PlaybookEngine | API Key |
| `POST` | `/api/v1/playbooks` | PlaybookEngine | API Key |
| `POST` | `/api/v1/playbooks/{id}/execute` | PlaybookEngine | API Key |
| `GET` | `/api/v1/playbooks/executions/list` | PlaybookEngine | API Key |
| `GET` | `/api/v1/playbooks/stats/summary` | PlaybookEngine | API Key |
| `POST` | `/api/v1/models/register` | ModelRegistry | API Key |
| `GET` | `/api/v1/models` | ModelRegistry | API Key |
| `POST` | `/api/v1/models/experiments` | ModelRegistry | API Key |
| `GET` | `/api/v1/models/experiments` | ModelRegistry | API Key |
| `POST` | `/api/v1/models/experiments/{id}/stop` | ModelRegistry | API Key |
| `GET` | `/api/v1/models/stats` | ModelRegistry | API Key |

### API Gateway AI Proxy (port 8080)

| Method | Path | Permission | Description |
|--------|------|------------|-------------|
| `POST` | `/api/v1/ai/chat` | `ai:read` | Natural language chat |
| `GET` | `/api/v1/ai/capabilities` | — | List AI modules and intents |
| `GET` | `/api/v1/ai/suggestions` | — | Context-aware suggestion chips |

---

## File Inventory

### AI Engine — Core (`services/ai-engine/app/`)

| File | Lines | Description |
|------|-------|-------------|
| `main.py` | 410 | FastAPI app, all AI endpoints, health + knowledge-status |
| `dependencies.py` | 182 | Singleton AIContainer, DI helpers, 16 module lifecycle |
| `action_router.py` | 377 | Central router: pattern match + NAC KB + LLM + fallback |
| `profiler.py` | 157 | Endpoint device classification (OUI + ONNX) |
| `risk.py` | 86 | Multi-dimensional risk scoring |
| `shadow.py` | 103 | Shadow AI detection (14 signatures) |
| `nlp_policy.py` | 119 | NL → policy rules translation |
| `troubleshooter.py` | 86 | Rule-based auth issue diagnostics |
| `anomaly.py` | 266 | Anomaly detection + policy drift (Redis baselines) |
| `rag_troubleshooter.py` | 206 | RAG: KB retrieval + LLM root-cause analysis |
| `training_pipeline.py` | ~200 | sklearn → ONNX training export |
| `nl_to_sql.py` | 249 | NL → safe SQL (18 templates + LLM) |
| `adaptive_risk.py` | 129 | Learns risk thresholds from feedback |
| `tls_fingerprint.py` | ~200 | JA3/JA4 fingerprinting (16+3 signatures) |
| `capacity_planner.py` | ~150 | Linear regression + exponential smoothing forecasts |
| `playbooks.py` | ~200 | 6 built-in playbooks + custom |
| `model_registry.py` | ~200 | A/B testing + model version management |
| `oui_database.py` | ~500 entries | MAC vendor OUI lookup |
| `schemas.py` | ~150 | Pydantic request/response models |

### AI Engine — Knowledge (`services/ai-engine/app/intents/`)

| File | Description |
|------|-------------|
| `__init__.py` | Aggregates ALL_INTENTS + NAVIGATION_INTENTS |
| `product_knowledge.py` | 15 product knowledge intents (regex patterns) |
| `nac_knowledge.py` | 22 NAC articles + keyword scoring engine |
| `dashboard.py` | Dashboard action intents |
| `policies.py` | Policy CRUD intents |
| `field_extractor.py` | NLP field extraction from messages |

### RADIUS Server — AI Client (`services/radius-server/internal/handler/`)

| File | Description |
|------|-------------|
| `ai_client.go` | HTTP client with circuit breaker for AI Engine calls |
| `handler.go` | RADIUS handler — calls aiClient inline during auth |

### Frontend — AI UI (`web/src/`)

| File | Description |
|------|-------------|
| `lib/ai-store.ts` | Zustand state store (aiMode, messages, suggestions) |
| `components/AIModeToggle.tsx` | Agent/Dashboard toggle pill |
| `components/AIChatLayout.tsx` | Full-screen chat layout |
| `components/AIResponseCard.tsx` | Polymorphic response renderer |

### API Gateway — AI Proxy (`services/api-gateway/app/routers/`)

| File | Description |
|------|-------------|
| `ai_chat.py` | Proxies /ai/chat, /ai/capabilities, /ai/suggestions |
