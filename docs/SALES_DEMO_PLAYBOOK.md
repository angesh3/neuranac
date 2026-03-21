# NeuraNAC Sales Demo Playbook

## Demo Objective
Deliver a clear enterprise story with three flagship use cases and an end-to-end walkthrough that positions NeuraNAC as a category-leading NAC platform.

## Top 3 Use Cases

1. **AI-Aware NAC Governance**
   - Authenticate and govern AI agents as first-class network identities.
   - Detect shadow AI traffic and map AI data flow risks.
   - Enforce policy actions in the same control plane.

2. **Hybrid Multi-Site NAC Operations**
   - Run standalone or hybrid with shared policy intent across sites.
   - Monitor site and node health from one UI.
   - Support modernization from legacy NAC environments without tool sprawl.

3. **Real-Time Access Visibility and Response**
   - Correlate active sessions, endpoint context, posture state, and diagnostics.
   - Move from detection to policy response quickly.
   - Reduce mean-time-to-investigate and improve operator consistency.

## Positioning Statements

- NeuraNAC combines **AI governance + NAC policy enforcement + hybrid federation** in one platform experience.
- The value is not just individual features, but the integrated workflow from identity to enforcement to operations.
- For sales framing: emphasize this combined capability as a practical differentiator that is difficult to replicate with fragmented legacy stacks.

## Recorded Demo Artifacts

- Raw video: `artifacts/sales-demo/*.webm`
- Narration text: `tests/e2e/sales-demo-narration.txt`
- Final narrated demo: `artifacts/sales-demo/neuranac-sales-demo-with-audio.mp4`

## Recording the Demo

### Full build (video + audio + mux → MP4)

```bash
# 1. Start stack and demo-tools
docker compose -f deploy/docker-compose.yml up -d
docker compose -f deploy/docker-compose.yml --profile demo up -d demo-tools

# 2. Build complete demo (record → generate audio → mux)
./scripts/build-sales-demo.sh
# Output: artifacts/sales-demo/neuranac-sales-demo-with-audio.mp4
```

Or via Make: `make demo-build`

### Step-by-step

| Step | Command | Output |
|------|---------|--------|
| Record video | `make demo-record` or `node tests/e2e/sales-demo-recording.mjs` | `artifacts/sales-demo/*.webm` |
| Generate audio | `make demo-audio` or `./scripts/generate-demo-audio.sh` | `artifacts/sales-demo/neuranac-demo-narration.m4a` |
| Full build | `./scripts/build-sales-demo.sh` | `neuranac-sales-demo-with-audio.mp4` |

### Audio options (better quality)

```bash
# Slower, clearer speech (default: Samantha @ 130 wpm)
./scripts/generate-demo-audio.sh --voice Samantha --rate 125

# Alternative voices (macOS): Daniel, Karen, Alex
./scripts/generate-demo-audio.sh --voice Daniel

# Use Piper TTS if installed (pip install piper-tts)
./scripts/generate-demo-audio.sh --piper
```

### Demo flow

Login → AI mode → **visible toggle click** to Dashboard → use cases 1–3 → RADIUS simulator traffic → sessions/endpoints. Pacing and gaps are configurable in `tests/e2e/sales-demo-recording.mjs` (PACING object).

