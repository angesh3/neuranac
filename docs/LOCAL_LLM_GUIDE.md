# Local LLM Deployment Guide for NeuraNAC

## Why a Local LLM?

Running a private, containerized LLM ensures:

- **Data privacy** — No authentication logs, policy data, or network topology leaves your infrastructure
- **Regulatory compliance** — Meets GDPR, HIPAA, PCI-DSS data residency requirements
- **Air-gapped support** — Works in classified or isolated networks with no internet
- **Low latency** — No round-trip to cloud APIs; sub-second responses on local hardware
- **No per-token costs** — Unlimited queries after initial hardware investment
- **Self-learning** — The model can be fine-tuned on your own NAC data over time

---

## Table of Contents

1. [LLM Comparison for NAC](#llm-comparison-for-nac)
2. [Recommended Model](#recommended-model)
3. [Deployment Options](#deployment-options)
4. [Docker Compose Integration](#docker-compose-integration)
5. [Kubernetes / Helm Deployment](#kubernetes--helm-deployment)
6. [Self-Learning Pipeline](#self-learning-pipeline)
7. [Fine-Tuning with NAC Data](#fine-tuning-with-nac-data)
8. [Hardware Requirements](#hardware-requirements)
9. [Security Considerations](#security-considerations)
10. [Monitoring & Maintenance](#monitoring--maintenance)

---

## LLM Comparison for NAC

### Evaluation Criteria for a NAC Product

A NAC product LLM needs to:
1. **Understand structured data** — JSON policies, RADIUS attributes, network configs
2. **Generate safe SQL** — read-only queries against the NeuraNAC schema
3. **Reason about security** — risk scores, anomalies, compliance frameworks
4. **Run on modest hardware** — not every deployment site has GPU servers
5. **Support fine-tuning** — learn from local NAC data over time
6. **Be commercially licensable** — deployable in enterprise/government environments

### Model Comparison

| Model | Parameters | RAM (Quantized) | License | JSON Output | Reasoning | Fine-Tunable | NAC Fit |
|-------|-----------|-----------------|---------|-------------|-----------|-------------|---------|
| **Llama 3.1 8B** | 8B | ~5 GB (Q4) | Meta Community | Good | Good | Yes (LoRA) | **Best overall** |
| **Llama 3.1 70B** | 70B | ~40 GB (Q4) | Meta Community | Excellent | Excellent | Yes (QLoRA) | Best quality, needs GPU |
| **Mistral 7B v0.3** | 7B | ~4.5 GB (Q4) | Apache 2.0 | Good | Good | Yes (LoRA) | Great, very permissive license |
| **Mixtral 8x7B** | 47B (MoE) | ~26 GB (Q4) | Apache 2.0 | Very Good | Very Good | Limited | Good if RAM available |
| **Phi-3 Mini 3.8B** | 3.8B | ~2.5 GB (Q4) | MIT | Decent | Decent | Yes | Best for constrained hardware |
| **Phi-3 Medium 14B** | 14B | ~8 GB (Q4) | MIT | Good | Good | Yes | Good balance |
| **Qwen2.5 7B** | 7B | ~4.5 GB (Q4) | Apache 2.0 | Very Good | Very Good | Yes | Strong JSON, good coding |
| **CodeLlama 7B** | 7B | ~4.5 GB (Q4) | Meta Community | Good | Medium | Yes | Good for SQL generation |
| **Gemma 2 9B** | 9B | ~6 GB (Q4) | Google Permissive | Good | Good | Yes | Good general purpose |
| **DeepSeek-R1 7B** | 7B | ~4.5 GB (Q4) | MIT | Good | Excellent | Yes | Strong reasoning |

### Container Runtime Comparison

| Runtime | API Compatibility | GPU Support | Docker Image | Multi-Model | Fine-Tune Support |
|---------|-------------------|-------------|--------------|-------------|-------------------|
| **Ollama** | Ollama API + OpenAI-compat | CUDA, Metal, ROCm | `ollama/ollama` | Yes | No (inference only) |
| **vLLM** | OpenAI-compatible | CUDA required | `vllm/vllm-openai` | Yes | No |
| **llama.cpp server** | OpenAI-compatible | CUDA, Metal, Vulkan | `ghcr.io/ggerganov/llama.cpp:server` | No | No |
| **LocalAI** | OpenAI-compatible | CUDA, Metal | `localai/localai` | Yes | Yes (LoRA) |
| **text-generation-inference** | OpenAI-compatible | CUDA | `ghcr.io/huggingface/text-generation-inference` | No | No |
| **Unsloth** | Training only | CUDA | `unsloth/unsloth` | — | Yes (LoRA/QLoRA) |

---

## Recommended Model

### Primary Recommendation: Llama 3.1 8B via Ollama

**Why this is the best fit for NeuraNAC:**

1. **Right size for NAC** — 8B parameters is enough to understand RADIUS attributes, policy
   JSON, SQL schemas, and security concepts. Larger models add diminishing returns for
   structured NAC data.

2. **Runs on CPU** — Works on any server with 8GB+ RAM. No GPU required (though GPU
   accelerates 10x). This matters because NAC appliances and on-prem servers rarely have GPUs.

3. **Excellent JSON output** — Llama 3.1 was specifically trained to produce structured JSON,
   which is exactly what ActionRouter, NLToSQL, and NLPolicyAssistant need.

4. **Meta Community License** — Free for commercial use under 700M monthly active users.
   Covers all enterprise deployments.

5. **Ollama makes it trivial** — Single Docker image, single command to pull models, REST API
   that NeuraNAC already speaks (the code is pre-wired for Ollama's API).

6. **Fine-tunable** — Can be fine-tuned with LoRA on NAC-specific data to create a
   domain-specialized model.

### Alternative Recommendations

| Scenario | Recommended Model | Why |
|----------|-------------------|-----|
| **Constrained hardware** (4GB RAM) | Phi-3 Mini 3.8B | Smallest model that still produces usable JSON |
| **Maximum quality** (GPU server) | Llama 3.1 70B (Q4) | Best reasoning and accuracy, needs ~40GB VRAM |
| **Apache 2.0 license required** | Mistral 7B v0.3 or Qwen2.5 7B | Most permissive licenses, no usage restrictions |
| **SQL generation focus** | CodeLlama 7B | Optimized for code/SQL but weaker on general reasoning |
| **Best reasoning** | DeepSeek-R1 7B | Chain-of-thought reasoning, MIT license |
| **Air-gapped / government** | Llama 3.1 8B (pre-downloaded) | Well-audited, US-origin, widely deployed in gov |

---

## Deployment Options

### Option 1: Ollama in Docker (Recommended)

Simplest path. NeuraNAC's code is already pre-wired for Ollama's API.

```bash
# Pull and run
docker run -d --name neuranac-ollama \
  -p 11434:11434 \
  -v ollama-data:/root/.ollama \
  ollama/ollama

# Download the model (one-time, ~4.7GB)
docker exec neuranac-ollama ollama pull llama3.1:8b

# Verify
curl http://localhost:11434/api/tags
```

### Option 2: Ollama with GPU (NVIDIA)

```bash
docker run -d --name neuranac-ollama \
  --gpus all \
  -p 11434:11434 \
  -v ollama-data:/root/.ollama \
  ollama/ollama

docker exec neuranac-ollama ollama pull llama3.1:8b
```

### Option 3: vLLM (High-throughput, GPU required)

Best for production with multiple concurrent users. OpenAI-compatible API.

```bash
docker run -d --name neuranac-vllm \
  --gpus all \
  -p 8000:8000 \
  -v vllm-models:/root/.cache/huggingface \
  vllm/vllm-openai \
  --model meta-llama/Meta-Llama-3.1-8B-Instruct \
  --max-model-len 4096 \
  --dtype half
```

For vLLM, set: `AI_LLM_API_URL=http://neuranac-vllm:8000/v1/completions`

### Option 4: LocalAI (Fine-tuning support)

Supports loading LoRA adapters at runtime — useful for the self-learning pipeline.

```bash
docker run -d --name neuranac-localai \
  -p 8080:8080 \
  -v localai-models:/models \
  localai/localai
```

### Option 5: Air-Gapped / Offline

For networks with no internet access:

```bash
# On a machine WITH internet:
docker pull ollama/ollama
docker save ollama/ollama > ollama-image.tar
ollama pull llama3.1:8b
# Copy the model files from ~/.ollama/models/

# On the air-gapped machine:
docker load < ollama-image.tar
docker run -d -p 11434:11434 -v /path/to/models:/root/.ollama ollama/ollama
```

---

## Docker Compose Integration

Add this to `deploy/docker-compose.yml` to include the LLM in the NeuraNAC stack:

```yaml
  # ── Local LLM (Ollama) ──────────────────────────────────────────────
  ollama:
    image: ollama/ollama:latest
    profiles: ["llm"]                    # Only starts with: --profile llm
    container_name: neuranac-ollama
    ports:
      - "11434:11434"
    volumes:
      - ollama-data:/root/.ollama
    deploy:
      resources:
        limits:
          memory: 8G                     # Llama 3.1 8B Q4 needs ~5GB
        reservations:
          memory: 6G
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:11434/api/tags"]
      interval: 30s
      timeout: 10s
      retries: 3
    restart: unless-stopped

  # One-time model pull (init container pattern)
  ollama-init:
    image: ollama/ollama:latest
    profiles: ["llm"]
    depends_on:
      ollama:
        condition: service_healthy
    entrypoint: ["ollama", "pull", "llama3.1:8b"]
    environment:
      - OLLAMA_HOST=http://ollama:11434
    restart: "no"
```

Add the volume:
```yaml
volumes:
  ollama-data:
```

Update the `ai-engine` service environment:
```yaml
  ai-engine:
    environment:
      - AI_LLM_API_URL=http://ollama:11434/api/generate
      - AI_LLM_MODEL=llama3.1:8b
```

**Usage:**
```bash
# Without LLM (default — current behavior)
docker compose -f deploy/docker-compose.yml up -d

# With LLM
docker compose -f deploy/docker-compose.yml --profile llm up -d
```

---

## Kubernetes / Helm Deployment

### Helm Values (`deploy/helm/neuranac/values.yaml`)

```yaml
ollama:
  enabled: false                        # Set to true to deploy LLM
  image:
    repository: ollama/ollama
    tag: latest
  model: "llama3.1:8b"
  resources:
    requests:
      memory: "6Gi"
      cpu: "2"
    limits:
      memory: "8Gi"
      cpu: "4"
      # nvidia.com/gpu: "1"            # Uncomment for GPU
  persistence:
    enabled: true
    size: 20Gi
    storageClass: ""                    # Use default storage class
```

### Kubernetes Deployment Template

```yaml
# deploy/helm/neuranac/templates/ollama.yaml
{{- if .Values.ollama.enabled }}
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ include "neuranac.fullname" . }}-ollama
spec:
  replicas: 1
  selector:
    matchLabels:
      app: ollama
  template:
    metadata:
      labels:
        app: ollama
    spec:
      containers:
        - name: ollama
          image: "{{ .Values.ollama.image.repository }}:{{ .Values.ollama.image.tag }}"
          ports:
            - containerPort: 11434
          resources: {{ toYaml .Values.ollama.resources | nindent 12 }}
          volumeMounts:
            - name: ollama-data
              mountPath: /root/.ollama
          livenessProbe:
            httpGet:
              path: /api/tags
              port: 11434
            initialDelaySeconds: 30
            periodSeconds: 30
          readinessProbe:
            httpGet:
              path: /api/tags
              port: 11434
            initialDelaySeconds: 10
            periodSeconds: 10
      volumes:
        - name: ollama-data
          persistentVolumeClaim:
            claimName: {{ include "neuranac.fullname" . }}-ollama-data
---
apiVersion: v1
kind: Service
metadata:
  name: {{ include "neuranac.fullname" . }}-ollama
spec:
  selector:
    app: ollama
  ports:
    - port: 11434
      targetPort: 11434
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: {{ include "neuranac.fullname" . }}-ollama-data
spec:
  accessModes: ["ReadWriteOnce"]
  resources:
    requests:
      storage: {{ .Values.ollama.persistence.size }}
  {{- if .Values.ollama.persistence.storageClass }}
  storageClassName: {{ .Values.ollama.persistence.storageClass }}
  {{- end }}
---
# Init Job: pull the model after deployment
apiVersion: batch/v1
kind: Job
metadata:
  name: {{ include "neuranac.fullname" . }}-ollama-init
  annotations:
    "helm.sh/hook": post-install,post-upgrade
    "helm.sh/hook-weight": "5"
spec:
  template:
    spec:
      restartPolicy: OnFailure
      containers:
        - name: pull-model
          image: curlimages/curl:latest
          command: ["sh", "-c"]
          args:
            - |
              echo "Waiting for Ollama..."
              until curl -sf http://{{ include "neuranac.fullname" . }}-ollama:11434/api/tags; do sleep 5; done
              echo "Pulling model {{ .Values.ollama.model }}..."
              curl -X POST http://{{ include "neuranac.fullname" . }}-ollama:11434/api/pull \
                -d '{"name": "{{ .Values.ollama.model }}"}'
              echo "Model ready."
{{- end }}
```

---

## Self-Learning Pipeline

NeuraNAC already has the building blocks for a self-learning system. Here's how they connect
to create a continuous improvement loop:

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    SELF-LEARNING LOOP                            │
│                                                                 │
│  ┌──────────────┐    ┌──────────────┐    ┌────────────────┐    │
│  │ 1. COLLECT   │ →  │ 2. STORE     │ →  │ 3. FINE-TUNE   │   │
│  │              │    │              │    │                │    │
│  │ RADIUS auths │    │ PostgreSQL   │    │ LoRA adapter   │    │
│  │ Chat queries │    │ training     │    │ on Llama 3.1   │    │
│  │ Operator     │    │ samples      │    │                │    │
│  │ feedback     │    │              │    │ OR sklearn →   │    │
│  │ Policy drift │    │ Redis        │    │ ONNX retrain   │    │
│  └──────────────┘    │ baselines    │    └───────┬────────┘    │
│                      └──────────────┘            │             │
│                                                  ▼             │
│  ┌──────────────┐    ┌──────────────┐    ┌────────────────┐    │
│  │ 6. MONITOR   │ ←  │ 5. A/B TEST  │ ←  │ 4. DEPLOY      │   │
│  │              │    │              │    │                │    │
│  │ Track        │    │ ModelRegistry│    │ Hot-reload     │    │
│  │ accuracy,    │    │ splits       │    │ LoRA adapter   │    │
│  │ latency,     │    │ traffic      │    │ or ONNX model  │    │
│  │ drift        │    │ 80/20        │    │                │    │
│  └──────────────┘    └──────────────┘    └────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

### Existing NeuraNAC Components That Feed the Loop

| Component | What It Collects | How It Learns |
|-----------|-----------------|---------------|
| **TrainingPipeline** | Labeled endpoint samples (MAC → device_type) | Trains sklearn RandomForest → ONNX export |
| **AdaptiveRiskEngine** | Operator feedback (risk decision correct/incorrect) | Recalibrates quarantine/monitor/allow thresholds |
| **AnomalyDetector** | Auth patterns per entity (time, location, frequency) | Builds statistical baselines, adapts z-score thresholds |
| **PolicyDriftDetector** | Expected vs actual auth outcomes | Detects divergence patterns over time |
| **ModelRegistry** | Model version performance metrics | A/B tests new models against current |
| **ActionRouter** | Chat queries + matched intents | Logs which queries miss (potential training data) |

### Two Learning Tracks

**Track A: Traditional ML (Already Built)**
```
Endpoint data → TrainingPipeline → sklearn → ONNX → EndpointProfiler
                                                    ↓
                                              ModelRegistry (A/B test)
```
This is already implemented. You can add samples via `POST /api/v1/training/sample`
and retrain via `POST /api/v1/training/train`.

**Track B: LLM Fine-Tuning (New — Requires Local LLM)**
```
Chat logs + feedback → Curate training pairs → LoRA fine-tune → Deploy adapter
                                                                ↓
                                                          ModelRegistry (A/B test)
```
This track requires a local LLM and a fine-tuning pipeline. See the next section.

---

## Fine-Tuning with NAC Data

### What Is Fine-Tuning?

Fine-tuning creates a **LoRA adapter** — a small (~50–200MB) file that modifies the base
model's behavior for your specific domain. The base model stays unchanged. You can:

- Swap adapters without re-downloading the base model
- A/B test different adapters (e.g., v1 vs v2 of your NAC fine-tune)
- Roll back instantly by removing the adapter

### Step 1: Collect Training Data

Create training pairs from NeuraNAC's operational data:

```jsonl
{"instruction": "What RADIUS attribute assigns a VLAN?", "output": "Tunnel-Private-Group-ID (RADIUS attribute 81) is used to assign a VLAN to an authenticated endpoint. The RADIUS server includes this attribute in the Access-Accept packet. The switch reads it and places the port in the specified VLAN."}
{"instruction": "Translate this policy: Block all printers after 8pm", "output": "{\"rules\": [{\"name\": \"block-printers-after-hours\", \"conditions\": [{\"attribute\": \"endpoint.device_type\", \"operator\": \"equals\", \"value\": \"printer\"}, {\"attribute\": \"time.hour\", \"operator\": \"greater_than\", \"value\": \"20\"}], \"action\": \"deny\"}], \"explanation\": \"Denies network access to endpoints profiled as printers after 8:00 PM.\"}"}
{"instruction": "SQL: How many failed authentications in the last hour?", "output": "SELECT COUNT(*) as failed_auths FROM auth_sessions WHERE auth_result = 'reject' AND started_at >= NOW() - INTERVAL '1 hour'"}
{"instruction": "Why is endpoint AA:BB:CC:DD:EE:FF failing 802.1X?", "output": "Common causes for 802.1X failure on a specific endpoint: 1) Client certificate expired or not installed, 2) Supplicant misconfigured (wrong EAP type), 3) MAC address not in endpoint database for MAB fallback, 4) RADIUS shared secret mismatch between switch and NeuraNAC. Check the RADIUS live log filtered by MAC address for the specific EAP failure code."}
```

**Automated data collection script** (add to `scripts/`):

```python
#!/usr/bin/env python3
"""Collect training data from NeuraNAC operational logs for LLM fine-tuning."""
import json
import asyncpg
import asyncio

async def collect_training_data():
    conn = await asyncpg.connect("postgresql://neuranac:neuranac@localhost:5432/neuranac")

    pairs = []

    # 1. Successful chat interactions (query → response that was helpful)
    rows = await conn.fetch("""
        SELECT query, response, intent FROM ai_chat_log
        WHERE feedback = 'positive' AND created_at > NOW() - INTERVAL '30 days'
    """)
    for r in rows:
        pairs.append({
            "instruction": r["query"],
            "output": r["response"],
            "source": "chat_positive_feedback"
        })

    # 2. Policy translations that were accepted
    rows = await conn.fetch("""
        SELECT natural_language, translated_rules FROM policy_translations
        WHERE status = 'accepted' AND created_at > NOW() - INTERVAL '30 days'
    """)
    for r in rows:
        pairs.append({
            "instruction": f"Translate this policy: {r['natural_language']}",
            "output": r["translated_rules"],
            "source": "policy_accepted"
        })

    # 3. Troubleshooting sessions with resolution
    rows = await conn.fetch("""
        SELECT symptoms, root_cause, resolution FROM troubleshooting_sessions
        WHERE resolved = true AND created_at > NOW() - INTERVAL '30 days'
    """)
    for r in rows:
        pairs.append({
            "instruction": f"Troubleshoot: {r['symptoms']}",
            "output": f"Root cause: {r['root_cause']}\nResolution: {r['resolution']}",
            "source": "troubleshoot_resolved"
        })

    with open("/data/training/finetune_pairs.jsonl", "w") as f:
        for p in pairs:
            f.write(json.dumps(p) + "\n")

    print(f"Collected {len(pairs)} training pairs")
    await conn.close()

asyncio.run(collect_training_data())
```

### Step 2: Fine-Tune with LoRA

Using **Unsloth** (fastest, most memory-efficient LoRA fine-tuning):

```bash
# Run the fine-tuning container
docker run --gpus all -it \
  -v /data/training:/data \
  -v /data/models:/output \
  unsloth/unsloth:latest \
  python3 -c "
from unsloth import FastLanguageModel
import json

# Load base model
model, tokenizer = FastLanguageModel.from_pretrained(
    'unsloth/Meta-Llama-3.1-8B-Instruct-bnb-4bit',
    max_seq_length=4096,
    load_in_4bit=True,
)

# Add LoRA adapter
model = FastLanguageModel.get_peft_model(
    model,
    r=16,
    target_modules=['q_proj','k_proj','v_proj','o_proj',
                    'gate_proj','up_proj','down_proj'],
    lora_alpha=16,
    lora_dropout=0,
    use_gradient_checkpointing='unsloth',
)

# Load training data
from datasets import Dataset
with open('/data/finetune_pairs.jsonl') as f:
    data = [json.loads(l) for l in f]

dataset = Dataset.from_list(data)

# Format as Llama 3.1 chat template
def format_row(row):
    return {'text': f'<|begin_of_text|><|start_header_id|>user<|end_header_id|>\n\n{row[\"instruction\"]}<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n\n{row[\"output\"]}<|eot_id|>'}

dataset = dataset.map(format_row)

from trl import SFTTrainer
from transformers import TrainingArguments

trainer = SFTTrainer(
    model=model,
    train_dataset=dataset,
    dataset_text_field='text',
    max_seq_length=4096,
    args=TrainingArguments(
        output_dir='/output/neuranac-nac-lora',
        per_device_train_batch_size=2,
        gradient_accumulation_steps=4,
        warmup_steps=10,
        num_train_epochs=3,
        learning_rate=2e-4,
        fp16=True,
        logging_steps=10,
        save_strategy='epoch',
    ),
)

trainer.train()
model.save_pretrained('/output/neuranac-nac-lora')
print('Fine-tuning complete. LoRA adapter saved to /output/neuranac-nac-lora')
"
```

### Step 3: Deploy the Fine-Tuned Model

**With Ollama (create a Modelfile):**

```dockerfile
# /data/models/Modelfile.neuranac-nac
FROM llama3.1:8b
ADAPTER /data/models/neuranac-nac-lora

PARAMETER temperature 0.1
PARAMETER num_ctx 4096

SYSTEM """You are the NeuraNAC AI Assistant, an expert in Network Access Control (NAC).
You help network administrators configure policies, troubleshoot authentication issues,
understand RADIUS/TACACS+ protocols, and manage endpoint security.
Always respond with accurate, structured information. When generating policy rules,
output valid JSON. When generating SQL, only produce SELECT queries."""
```

```bash
# Create the custom model
docker exec neuranac-ollama ollama create neuranac-nac -f /data/models/Modelfile.neuranac-nac

# Update AI Engine env
AI_LLM_MODEL=neuranac-nac
```

### Step 4: A/B Test via ModelRegistry

Use NeuraNAC's built-in ModelRegistry to A/B test the fine-tuned model against the base:

```bash
# Register base model
curl -X POST http://localhost:8081/api/v1/models/register \
  -H "X-API-Key: $AI_KEY" \
  -d '{"name": "llama3.1-base", "version": "1.0", "model_type": "llm",
       "endpoint": "http://ollama:11434", "weight": 80}'

# Register fine-tuned model
curl -X POST http://localhost:8081/api/v1/models/register \
  -H "X-API-Key: $AI_KEY" \
  -d '{"name": "neuranac-nac-v1", "version": "1.0", "model_type": "llm",
       "endpoint": "http://ollama:11434", "weight": 20}'

# Create experiment: 80% base / 20% fine-tuned
curl -X POST http://localhost:8081/api/v1/models/experiments \
  -H "X-API-Key: $AI_KEY" \
  -d '{"name": "nac-finetune-v1-test", "model_a_id": "llama3.1-base",
       "model_b_id": "neuranac-nac-v1", "traffic_split": 0.2}'
```

### Continuous Learning Schedule

```
Weekly:
  1. Collect training pairs from positive chat feedback + accepted policies
  2. Append to training dataset
  3. Re-run LoRA fine-tune (incremental, ~30 min on GPU)
  4. Deploy new adapter version
  5. A/B test 80/20 for one week
  6. If metrics improve, promote to 100%
  7. If metrics degrade, rollback to previous adapter
```

---

## Hardware Requirements

### CPU-Only Deployment (No GPU)

| Model | RAM | CPU Cores | Tokens/sec | Latency (avg) |
|-------|-----|-----------|------------|----------------|
| Phi-3 Mini 3.8B (Q4) | 4 GB | 4 | ~8 tok/s | ~3s |
| Llama 3.1 8B (Q4) | 8 GB | 4 | ~5 tok/s | ~5s |
| Mistral 7B (Q4) | 8 GB | 4 | ~5 tok/s | ~5s |
| Llama 3.1 8B (Q4) | 8 GB | 8 | ~10 tok/s | ~2.5s |

### GPU Deployment

| Model | VRAM | GPU | Tokens/sec | Latency (avg) |
|-------|------|-----|------------|----------------|
| Llama 3.1 8B (Q4) | 6 GB | RTX 3060 | ~40 tok/s | ~0.5s |
| Llama 3.1 8B (FP16) | 16 GB | RTX 4090 | ~80 tok/s | ~0.3s |
| Llama 3.1 70B (Q4) | 40 GB | A100 80GB | ~30 tok/s | ~1s |
| Mixtral 8x7B (Q4) | 26 GB | A100 40GB | ~25 tok/s | ~1.2s |

### Recommendations by Deployment

| Deployment | Model | Hardware | Cost Estimate |
|------------|-------|----------|---------------|
| **Dev laptop** | Phi-3 Mini 3.8B | MacBook 16GB | Already owned |
| **Small office** (< 500 endpoints) | Llama 3.1 8B Q4 CPU | Any server, 16GB RAM | ~$500 |
| **Medium site** (500-5000) | Llama 3.1 8B Q4 GPU | Server + RTX 3060 | ~$1,500 |
| **Large campus** (5000+) | Llama 3.1 70B Q4 | Server + A100 | ~$15,000 |
| **Enterprise multi-site** | vLLM + Llama 3.1 8B | 2x GPU server (HA) | ~$5,000 |

---

## Security Considerations

### Network Isolation

```
┌─────────────────────────────────────────────┐
│            NeuraNAC Internal Network              │
│                                             │
│  ┌───────────┐        ┌──────────────────┐  │
│  │ AI Engine │──HTTP──│ Ollama (LLM)     │  │
│  │ :8081     │        │ :11434           │  │
│  └───────────┘        │ NO external      │  │
│                       │ network access   │  │
│                       └──────────────────┘  │
└─────────────────────────────────────────────┘
         ✗ No internet access for LLM
         ✗ No data exfiltration possible
         ✓ Ollama only listens on internal Docker network
```

### Key Security Practices

1. **No internet access for LLM container** — Use Docker network policies or Kubernetes
   NetworkPolicy to prevent the LLM container from reaching the internet

2. **No sensitive data in prompts** — NeuraNAC's ActionRouter sends intent descriptions and user
   queries, not raw authentication logs or passwords

3. **Model provenance** — Download models from official sources (ollama.com, huggingface.co)
   and verify checksums before deploying to air-gapped environments

4. **Prompt injection protection** — NeuraNAC's NLToSQL already blocks non-SELECT queries. The
   ActionRouter validates LLM JSON responses against known intent names

5. **Resource limits** — Always set memory limits on the LLM container to prevent it from
   starving other NeuraNAC services

### Kubernetes NetworkPolicy for LLM

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: ollama-isolation
spec:
  podSelector:
    matchLabels:
      app: ollama
  policyTypes:
    - Ingress
    - Egress
  ingress:
    - from:
        - podSelector:
            matchLabels:
              app: ai-engine         # Only AI Engine can talk to LLM
      ports:
        - port: 11434
  egress: []                          # No outbound access at all
```

---

## Monitoring & Maintenance

### Health Checks

```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# Check if AI Engine sees the LLM
curl http://localhost:8081/knowledge-status

# Check LLM availability via capabilities
curl -H "X-API-Key: $AI_KEY" http://localhost:8081/api/v1/ai/capabilities \
  | jq '.modules[] | select(.name == "ActionRouter") | .llm_available'
```

### Model Update Procedure

```bash
# 1. Pull new model version
docker exec neuranac-ollama ollama pull llama3.1:8b

# 2. Restart AI Engine to re-check LLM availability
docker compose -f deploy/docker-compose.yml restart ai-engine

# 3. Verify
curl http://localhost:8081/api/v1/ai/capabilities | jq '.modules[7]'
```

### Storage Management

```bash
# Check model storage usage
docker exec neuranac-ollama du -sh /root/.ollama/models/

# Remove unused models
docker exec neuranac-ollama ollama rm <model-name>

# List all models
docker exec neuranac-ollama ollama list
```

### Monitoring Metrics

| Metric | Source | What to Watch |
|--------|--------|---------------|
| LLM response time | AI Engine logs | Should be < 5s for CPU, < 1s for GPU |
| LLM success rate | AI Engine logs | Should be > 95% |
| Circuit breaker state | RADIUS ai_client | Should remain closed |
| Memory usage | Docker stats | Should stay below container limit |
| Tokens/second | Ollama metrics | Indicates if hardware is sufficient |
| Training data size | TrainingPipeline API | Growing = healthy feedback loop |
| A/B test winner | ModelRegistry API | Fine-tuned model should improve over time |

---

## Implementation Reference

### Files Created / Modified

| File | Type | Description |
|------|------|-------------|
| `deploy/docker-compose.yml` | Modified | Added `ollama` + `ollama-init` services (profile: `llm`), LLM env vars to `ai-engine`, training/model volumes |
| `deploy/ollama/Modelfile.neuranac-nac` | New | Ollama Modelfile with NeuraNAC NAC system prompt for creating the custom `neuranac-nac` model |
| `deploy/helm/neuranac/templates/ollama.yaml` | New | K8s Deployment, Service, PVC, model-pull Job, NetworkPolicy for Ollama |
| `deploy/helm/neuranac/values.yaml` | Modified | Added `ollama` section (enabled, image, model, resources, persistence) and `aiEngine.llm` config |
| `services/ai-engine/app/main.py` | Modified | Added `/llm-status` public endpoint for LLM health monitoring |
| `services/ai-engine/app/action_router.py` | Modified | Default model updated to `llama3.1:8b` |
| `services/ai-engine/app/rag_troubleshooter.py` | Modified | Default model updated to `llama3.1:8b` |
| `services/ai-engine/app/nl_to_sql.py` | Modified | Default model updated to `llama3.1:8b` |
| `services/ai-engine/app/nlp_policy.py` | Modified | Default model updated to `llama3.1:8b` |
| `scripts/collect_training_data.py` | New | Collects training pairs from DB logs, knowledge base, and seed data |
| `scripts/finetune_llm.py` | New | LoRA fine-tuning script using Unsloth + Llama 3.1 8B |
| `scripts/learning_scheduler.py` | New | Orchestrates the full self-learning pipeline (collect → validate → finetune → deploy → A/B test) |

### Quick Start

```bash
# 1. Start NeuraNAC with local LLM
docker compose -f deploy/docker-compose.yml --profile llm up -d

# 2. Wait for model pull (~5 min on first run, downloads ~4.7 GB)
docker logs -f neuranac-ollama-init

# 3. Verify LLM is running
curl http://localhost:8081/llm-status | jq .

# 4. Restart AI Engine to detect the LLM
docker compose -f deploy/docker-compose.yml restart ai-engine

# 5. Verify LLM is active in router
curl http://localhost:8081/llm-status | jq '.llm_active_in_router'
# Should return: true
```

### Self-Learning Quick Start

```bash
# Collect training data from operational logs + built-in knowledge
python3 scripts/collect_training_data.py \
  --db-url postgresql://neuranac:neuranac@localhost:5432/neuranac \
  --output /data/training/finetune_pairs.jsonl

# Check pipeline status
python3 scripts/learning_scheduler.py --phase status

# Run full pipeline (requires GPU host for fine-tuning)
python3 scripts/learning_scheduler.py --phase all \
  --ollama-url http://localhost:11434

# Or run individual phases
python3 scripts/learning_scheduler.py --phase collect --days 30
python3 scripts/learning_scheduler.py --phase validate
python3 scripts/learning_scheduler.py --phase finetune --epochs 3
python3 scripts/learning_scheduler.py --phase deploy
python3 scripts/learning_scheduler.py --phase abtest
```

### Cron Schedule (Recommended)

```cron
# Weekly: Collect training data (Sunday 1am)
0 1 * * 0  cd /opt/neuranac && python3 scripts/learning_scheduler.py --phase collect --days 7

# Weekly: Validate + fine-tune + deploy (Sunday 2am, after collect)
0 2 * * 0  cd /opt/neuranac && python3 scripts/learning_scheduler.py --phase all

# Monthly: Check pipeline status and log (1st of month)
0 6 1 * *  cd /opt/neuranac && python3 scripts/learning_scheduler.py --phase status >> /var/log/neuranac-learning.log
```

### API Endpoints

| Endpoint | Auth | Description |
|----------|------|-------------|
| `GET /llm-status` | Public | Shows LLM config, Ollama reachability, model availability, router status |
| `GET /knowledge-status` | Public | Shows loaded knowledge base (intents, articles) |
| `GET /api/v1/ai/capabilities` | API Key | Full AI capabilities including LLM status |
| `POST /api/v1/models/register` | API Key | Register a model version for A/B testing |
| `POST /api/v1/models/experiments` | API Key | Create A/B experiment between models |
| `GET /api/v1/training/stats` | API Key | Training pipeline sample counts |
