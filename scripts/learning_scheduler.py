#!/usr/bin/env python3
"""
NeuraNAC Self-Learning Scheduler — Orchestrates the continuous learning pipeline.

This script manages the weekly (or custom interval) learning cycle:
  1. Collect training data from operational logs
  2. Validate data quality and quantity
  3. Trigger LoRA fine-tuning (if GPU host available)
  4. Deploy the new adapter to Ollama
  5. Run A/B test via ModelRegistry
  6. Monitor and promote or rollback

Can run as:
  - A cron job:    0 2 * * 0  python3 scripts/learning_scheduler.py --phase collect
  - A one-shot:    python3 scripts/learning_scheduler.py --phase all
  - Manual steps:  python3 scripts/learning_scheduler.py --phase deploy

Phases:
  collect   — Gather training data from DB + knowledge base
  validate  — Check data quality thresholds
  finetune  — Run LoRA fine-tuning (requires GPU)
  deploy    — Create Ollama model from adapter
  abtest    — Register new model for A/B testing
  promote   — Promote winning model to 100% traffic
  rollback  — Rollback to base model
  status    — Show current learning pipeline status
  all       — Run collect → validate → finetune → deploy → abtest

Usage:
  python3 scripts/learning_scheduler.py --phase status
  python3 scripts/learning_scheduler.py --phase collect --days 30
  python3 scripts/learning_scheduler.py --phase all --ollama-url http://localhost:11434
"""
import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

TRAINING_DATA_DIR = os.getenv("AI_TRAINING_DATA", "/data/training")
MODELS_DIR = os.getenv("AI_MODEL_PATH", "/data/models")
OLLAMA_URL = os.getenv("AI_OLLAMA_URL", "http://localhost:11434")
AI_ENGINE_URL = os.getenv("AI_ENGINE_URL", "http://localhost:8081")
AI_ENGINE_API_KEY = os.getenv("AI_ENGINE_API_KEY", "neuranac_ai_dev_key_change_in_production")
DB_URL = os.getenv("AI_PG_DSN", "postgresql://neuranac:neuranac@localhost:5432/neuranac")
LLM_MODEL = os.getenv("AI_LLM_MODEL", "llama3.1:8b")

TRAINING_OUTPUT = os.path.join(TRAINING_DATA_DIR, "finetune_pairs.jsonl")
LORA_OUTPUT = os.path.join(MODELS_DIR, "neuranac-nac-lora")
STATE_FILE = os.path.join(TRAINING_DATA_DIR, "learning_state.json")

MIN_TRAINING_PAIRS = 20  # Minimum pairs to trigger fine-tuning
MIN_NEW_PAIRS = 5        # Minimum new pairs since last fine-tune to justify retraining


def log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}")


def load_state() -> dict:
    """Load the learning pipeline state from disk."""
    if Path(STATE_FILE).exists():
        with open(STATE_FILE) as f:
            return json.load(f)
    return {
        "last_collect": None,
        "last_finetune": None,
        "last_deploy": None,
        "last_abtest": None,
        "total_pairs_last_finetune": 0,
        "current_model": LLM_MODEL,
        "adapter_version": 0,
        "abtest_active": False,
        "abtest_experiment_id": None,
    }


def save_state(state: dict):
    """Persist learning pipeline state."""
    Path(STATE_FILE).parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


# ---------------------------------------------------------------------------
# Phase implementations
# ---------------------------------------------------------------------------

def phase_collect(args) -> bool:
    """Phase 1: Collect training data."""
    log("PHASE: COLLECT — Gathering training data from NeuraNAC operational logs")

    script = Path(__file__).parent / "collect_training_data.py"
    if not script.exists():
        log(f"  ERROR: {script} not found")
        return False

    cmd = [
        sys.executable, str(script),
        "--db-url", args.db_url,
        "--output", TRAINING_OUTPUT,
        "--days", str(args.days),
    ]
    result = subprocess.run(cmd, capture_output=False)
    if result.returncode != 0:
        log("  ERROR: Data collection failed")
        return False

    state = load_state()
    state["last_collect"] = datetime.now().isoformat()
    save_state(state)

    log("  COLLECT complete")
    return True


def phase_validate(args) -> bool:
    """Phase 2: Validate training data quality."""
    log("PHASE: VALIDATE — Checking training data quality")

    if not Path(TRAINING_OUTPUT).exists():
        log(f"  ERROR: Training data not found at {TRAINING_OUTPUT}")
        log("  Run --phase collect first")
        return False

    # Count pairs
    with open(TRAINING_OUTPUT) as f:
        pairs = [json.loads(line) for line in f if line.strip()]

    total = len(pairs)
    log(f"  Total training pairs: {total}")

    if total < MIN_TRAINING_PAIRS:
        log(f"  ERROR: Need at least {MIN_TRAINING_PAIRS} pairs, got {total}")
        return False

    # Check for new data since last fine-tune
    state = load_state()
    new_pairs = total - state.get("total_pairs_last_finetune", 0)
    log(f"  New pairs since last fine-tune: {new_pairs}")

    if new_pairs < MIN_NEW_PAIRS and not args.force:
        log(f"  SKIP: Only {new_pairs} new pairs (minimum {MIN_NEW_PAIRS}). Use --force to override.")
        return False

    # Check data distribution
    by_source = {}
    for p in pairs:
        s = p.get("source", "unknown")
        by_source[s] = by_source.get(s, 0) + 1

    log("  Data distribution:")
    for source, count in sorted(by_source.items()):
        log(f"    {source}: {count}")

    # Check for empty outputs
    empty = sum(1 for p in pairs if not p.get("output", "").strip())
    if empty > 0:
        log(f"  WARNING: {empty} pairs have empty outputs")

    # Check avg length
    avg_len = sum(len(p.get("output", "")) for p in pairs) / max(1, total)
    log(f"  Average output length: {avg_len:.0f} chars")

    log("  VALIDATE passed")
    return True


def phase_finetune(args) -> bool:
    """Phase 3: Run LoRA fine-tuning."""
    log("PHASE: FINETUNE — Running LoRA fine-tuning")

    script = Path(__file__).parent / "finetune_llm.py"
    if not script.exists():
        log(f"  ERROR: {script} not found")
        return False

    if not Path(TRAINING_OUTPUT).exists():
        log(f"  ERROR: Training data not found. Run --phase collect first.")
        return False

    cmd = [
        sys.executable, str(script),
        "--input", TRAINING_OUTPUT,
        "--output", LORA_OUTPUT,
        "--epochs", str(args.epochs),
        "--base-model", args.base_model,
    ]

    log(f"  Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=False)

    if result.returncode != 0:
        log("  ERROR: Fine-tuning failed")
        return False

    # Update state
    state = load_state()
    state["last_finetune"] = datetime.now().isoformat()
    state["adapter_version"] = state.get("adapter_version", 0) + 1
    with open(TRAINING_OUTPUT) as f:
        state["total_pairs_last_finetune"] = sum(1 for line in f if line.strip())
    save_state(state)

    log(f"  FINETUNE complete — adapter v{state['adapter_version']}")
    return True


def phase_deploy(args) -> bool:
    """Phase 4: Deploy LoRA adapter to Ollama."""
    log("PHASE: DEPLOY — Creating Ollama model from LoRA adapter")

    try:
        import httpx
    except ImportError:
        log("  ERROR: httpx not installed. pip install httpx")
        return False

    # Check Ollama is reachable
    ollama_url = args.ollama_url
    try:
        resp = httpx.get(f"{ollama_url}/api/tags", timeout=5)
        if resp.status_code != 200:
            log(f"  ERROR: Ollama not healthy at {ollama_url}")
            return False
    except Exception as e:
        log(f"  ERROR: Cannot reach Ollama at {ollama_url}: {e}")
        return False

    # Check adapter exists
    adapter_path = Path(LORA_OUTPUT)
    if not adapter_path.exists():
        log(f"  ERROR: LoRA adapter not found at {adapter_path}")
        log("  Run --phase finetune first")
        return False

    state = load_state()
    version = state.get("adapter_version", 1)
    model_name = f"neuranac-nac-v{version}"

    # Create model via Ollama API
    modelfile_content = (
        f"FROM {LLM_MODEL}\n"
        f"ADAPTER {LORA_OUTPUT}\n"
        f"PARAMETER temperature 0.1\n"
        f"PARAMETER top_p 0.9\n"
        f"PARAMETER num_ctx 4096\n"
        f'SYSTEM """You are the NeuraNAC AI Assistant, an expert in Network Access Control (NAC), '
        f"RADIUS, TACACS+, 802.1X, and enterprise network security. "
        f"Always respond with accurate, structured information. "
        f'When generating SQL, ONLY produce SELECT queries."""\n'
    )

    log(f"  Creating Ollama model: {model_name}")
    try:
        resp = httpx.post(
            f"{ollama_url}/api/create",
            json={"name": model_name, "modelfile": modelfile_content},
            timeout=300,
        )
        if resp.status_code != 200:
            log(f"  ERROR: Ollama create failed: {resp.text}")
            return False
    except Exception as e:
        log(f"  ERROR: Ollama create failed: {e}")
        return False

    state["last_deploy"] = datetime.now().isoformat()
    state["deployed_model"] = model_name
    save_state(state)

    log(f"  DEPLOY complete — model '{model_name}' available in Ollama")
    return True


def phase_abtest(args) -> bool:
    """Phase 5: Register A/B test via AI Engine ModelRegistry."""
    log("PHASE: ABTEST — Setting up A/B test for new model")

    try:
        import httpx
    except ImportError:
        log("  ERROR: httpx not installed. pip install httpx")
        return False

    state = load_state()
    new_model = state.get("deployed_model")
    if not new_model:
        log("  ERROR: No deployed model found. Run --phase deploy first.")
        return False

    headers = {"X-API-Key": AI_ENGINE_API_KEY, "Content-Type": "application/json"}

    try:
        # Register base model
        log(f"  Registering base model: {LLM_MODEL}")
        httpx.post(
            f"{AI_ENGINE_URL}/api/v1/models/register",
            json={"name": LLM_MODEL, "version": "base", "model_type": "llm",
                  "endpoint": OLLAMA_URL, "weight": 80},
            headers=headers, timeout=10,
        )

        # Register fine-tuned model
        log(f"  Registering fine-tuned model: {new_model}")
        httpx.post(
            f"{AI_ENGINE_URL}/api/v1/models/register",
            json={"name": new_model, "version": str(state.get("adapter_version", 1)),
                  "model_type": "llm", "endpoint": OLLAMA_URL, "weight": 20},
            headers=headers, timeout=10,
        )

        # Create experiment
        log("  Creating A/B experiment (80% base / 20% fine-tuned)")
        resp = httpx.post(
            f"{AI_ENGINE_URL}/api/v1/models/experiments",
            json={"name": f"nac-finetune-v{state.get('adapter_version', 1)}",
                  "model_a_id": LLM_MODEL, "model_b_id": new_model,
                  "traffic_split": 0.2},
            headers=headers, timeout=10,
        )

        if resp.status_code == 200:
            exp_data = resp.json()
            state["abtest_active"] = True
            state["abtest_experiment_id"] = exp_data.get("experiment_id")
            state["last_abtest"] = datetime.now().isoformat()
            save_state(state)
            log(f"  ABTEST active — experiment ID: {state['abtest_experiment_id']}")
            return True
        else:
            log(f"  WARNING: Experiment creation returned {resp.status_code}: {resp.text}")
            return False
    except Exception as e:
        log(f"  ERROR: A/B test setup failed: {e}")
        return False


def phase_promote(args) -> bool:
    """Phase 6: Promote fine-tuned model to 100% traffic."""
    state = load_state()
    new_model = state.get("deployed_model")
    if not new_model:
        log("ERROR: No deployed model to promote")
        return False

    log(f"PHASE: PROMOTE — Setting {new_model} as primary model")
    state["current_model"] = new_model
    state["abtest_active"] = False
    save_state(state)

    log(f"  Model promoted. Update AI_LLM_MODEL={new_model} in your environment.")
    log(f"  Then restart AI Engine: docker compose restart ai-engine")
    return True


def phase_rollback(args) -> bool:
    """Phase 7: Rollback to base model."""
    log(f"PHASE: ROLLBACK — Reverting to base model: {LLM_MODEL}")
    state = load_state()
    state["current_model"] = LLM_MODEL
    state["abtest_active"] = False
    save_state(state)

    log(f"  Rolled back to {LLM_MODEL}")
    log(f"  Restart AI Engine: docker compose restart ai-engine")
    return True


def phase_status(args) -> bool:
    """Show current learning pipeline status."""
    state = load_state()

    print(f"\n{'='*60}")
    print(f"NeuraNAC Self-Learning Pipeline Status")
    print(f"{'='*60}")
    print(f"  Current model:      {state.get('current_model', 'not set')}")
    print(f"  Adapter version:    v{state.get('adapter_version', 0)}")
    print(f"  A/B test active:    {state.get('abtest_active', False)}")
    print(f"  Experiment ID:      {state.get('abtest_experiment_id', 'none')}")
    print()
    print(f"  Last collect:       {state.get('last_collect', 'never')}")
    print(f"  Last fine-tune:     {state.get('last_finetune', 'never')}")
    print(f"  Last deploy:        {state.get('last_deploy', 'never')}")
    print(f"  Last A/B test:      {state.get('last_abtest', 'never')}")
    print(f"  Training pairs:     {state.get('total_pairs_last_finetune', 0)}")
    print()

    # Check training data
    if Path(TRAINING_OUTPUT).exists():
        with open(TRAINING_OUTPUT) as f:
            current_pairs = sum(1 for line in f if line.strip())
        new_pairs = current_pairs - state.get("total_pairs_last_finetune", 0)
        print(f"  Current data pairs: {current_pairs}")
        print(f"  New since last:     {new_pairs}")
        print(f"  Ready to retrain:   {'yes' if new_pairs >= MIN_NEW_PAIRS else 'no'}")
    else:
        print(f"  Training data:      not collected yet")

    # Check Ollama
    try:
        import httpx
        resp = httpx.get(f"{OLLAMA_URL}/api/tags", timeout=3)
        models = [m["name"] for m in resp.json().get("models", [])]
        print(f"\n  Ollama status:      running")
        print(f"  Available models:   {', '.join(models) if models else 'none'}")
    except Exception:
        print(f"\n  Ollama status:      not reachable at {OLLAMA_URL}")

    print()
    return True


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

PHASES = {
    "collect": phase_collect,
    "validate": phase_validate,
    "finetune": phase_finetune,
    "deploy": phase_deploy,
    "abtest": phase_abtest,
    "promote": phase_promote,
    "rollback": phase_rollback,
    "status": phase_status,
}


def main():
    parser = argparse.ArgumentParser(
        description="NeuraNAC Self-Learning Scheduler",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Phases:
  collect    Gather training data from DB + knowledge base
  validate   Check data quality and quantity thresholds
  finetune   Run LoRA fine-tuning (requires GPU host)
  deploy     Create Ollama model from LoRA adapter
  abtest     Register A/B test via ModelRegistry
  promote    Set fine-tuned model as primary (100% traffic)
  rollback   Revert to base model
  status     Show current pipeline status
  all        Run collect → validate → finetune → deploy → abtest
""",
    )
    parser.add_argument("--phase", required=True, choices=list(PHASES.keys()) + ["all"],
                        help="Pipeline phase to run")
    parser.add_argument("--db-url", default=DB_URL, help="PostgreSQL connection URL")
    parser.add_argument("--ollama-url", default=OLLAMA_URL, help="Ollama API URL")
    parser.add_argument("--days", type=int, default=30, help="Days of history to collect")
    parser.add_argument("--epochs", type=int, default=3, help="Fine-tuning epochs")
    parser.add_argument("--base-model", default="unsloth/Meta-Llama-3.1-8B-Instruct-bnb-4bit",
                        help="Base model for fine-tuning")
    parser.add_argument("--force", action="store_true", help="Force retraining even with few new pairs")

    args = parser.parse_args()

    if args.phase == "all":
        phases_to_run = ["collect", "validate", "finetune", "deploy", "abtest"]
        log("Running full pipeline: collect → validate → finetune → deploy → abtest")
        for phase_name in phases_to_run:
            success = PHASES[phase_name](args)
            if not success:
                log(f"Pipeline stopped at phase: {phase_name}")
                sys.exit(1)
        log("Full pipeline complete!")
    else:
        success = PHASES[args.phase](args)
        if not success:
            sys.exit(1)


if __name__ == "__main__":
    main()
