#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# NeuraNAC Sales Demo — Full Build Pipeline
#
# 1. Record video (Playwright)
# 2. Generate narration audio (macOS say or Piper)
# 3. Mux video + audio → final MP4
#
# Prerequisites:
#   - Docker stack running (make run + demo-tools)
#   - Node.js, Playwright (npx playwright install chromium)
#   - ffmpeg (brew install ffmpeg)
#   - macOS: say (built-in) | Linux: Piper TTS optional
#
# Usage:
#   ./scripts/build-sales-demo.sh              # Full build
#   ./scripts/build-sales-demo.sh --record     # Record only
#   ./scripts/build-sales-demo.sh --audio      # Generate audio only
#   ./scripts/build-sales-demo.sh --mux        # Mux only (needs existing video + audio)
#   ./scripts/build-sales-demo.sh --voice Samantha --rate 125
#
# Output: artifacts/sales-demo/neuranac-sales-demo-with-audio.mp4
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
OUT_DIR="$PROJECT_ROOT/artifacts/sales-demo"
FINAL_MP4="$OUT_DIR/neuranac-sales-demo-with-audio.mp4"

# Options
DO_RECORD=true
DO_AUDIO=true
DO_MUX=true
VOICE="${VOICE:-Samantha}"
RATE="${RATE:-130}"
USE_PIPER="${USE_PIPER:-}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --record) DO_RECORD=true; DO_AUDIO=false; DO_MUX=false; shift ;;
    --audio)  DO_RECORD=false; DO_AUDIO=true; DO_MUX=false; shift ;;
    --mux)    DO_RECORD=false; DO_AUDIO=false; DO_MUX=true; shift ;;
    --voice)  VOICE="$2"; shift 2 ;;
    --rate)   RATE="$2"; shift 2 ;;
    --piper)  USE_PIPER=true; shift ;;
    -h|--help)
      head -35 "$0" | tail -30
      exit 0
      ;;
    *) echo "Unknown: $1"; exit 1 ;;
  esac
done

mkdir -p "$OUT_DIR"
cd "$PROJECT_ROOT"

# ── Step 1: Record video ─────────────────────────────────────────────────────
record_video() {
  echo ""
  echo "═══ Step 1: Recording video ═══"
  if [[ -z "${DEMO_PASSWORD:-}" ]]; then
    DEMO_PASSWORD=$(docker compose -f deploy/docker-compose.yml exec -T api-gateway python -c "
from pathlib import Path
p = Path('/tmp/neuranac-initial-password')
if p.exists():
    for line in p.read_text().strip().splitlines():
        if line.startswith('password='):
            print(line.split('=', 1)[1])
            break
else:
    print('admin')
" 2>/dev/null || echo "admin")
    export DEMO_PASSWORD
  fi
  export DEMO_USERNAME="${DEMO_USERNAME:-admin}"
  export DEMO_BASE_URL="${DEMO_BASE_URL:-http://localhost:3001}"
  node tests/e2e/sales-demo-recording.mjs
  # Playwright saves to artifacts/sales-demo/*.webm
  VIDEO_FILE=$(ls -t "$OUT_DIR"/*.webm 2>/dev/null | head -1)
  if [[ -z "$VIDEO_FILE" ]]; then
    echo "No video file found. Ensure recording completed."
    exit 1
  fi
  echo "  → $VIDEO_FILE"
}

# ── Step 2: Generate audio ────────────────────────────────────────────────────
generate_audio() {
  echo ""
  echo "═══ Step 2: Generating narration audio ═══"
  VOICE="$VOICE" RATE="$RATE" "$SCRIPT_DIR/generate-demo-audio.sh" ${USE_PIPER:+--piper}
}

# ── Step 3: Mux video + audio ───────────────────────────────────────────────
mux_video_audio() {
  echo ""
  echo "═══ Step 3: Muxing video + audio ═══"
  VIDEO_FILE=$(ls -t "$OUT_DIR"/*.webm 2>/dev/null | head -1)
  AUDIO_FILE="$OUT_DIR/neuranac-demo-narration.m4a"
  if [[ -z "$VIDEO_FILE" || ! -f "$VIDEO_FILE" ]]; then
    echo "No video file. Run with --record first."
    exit 1
  fi
  if [[ ! -f "$AUDIO_FILE" ]]; then
    echo "No audio file. Run with --audio first."
    exit 1
  fi
  # Re-encode VP8→H.264 (MP4 doesn't support VP8 from WebM)
  ffmpeg -y -i "$VIDEO_FILE" -i "$AUDIO_FILE" -c:v libx264 -preset fast -crf 23 -c:a aac -b:a 128k -shortest "$FINAL_MP4" 2>/dev/null
  echo "  → $FINAL_MP4"
}

# ── Main ─────────────────────────────────────────────────────────────────────
main() {
  echo "NeuraNAC Sales Demo Build"
  echo "  Output: $FINAL_MP4"
  [[ "$DO_RECORD" == true ]] && record_video
  [[ "$DO_AUDIO" == true ]]  && generate_audio
  [[ "$DO_MUX" == true ]]   && mux_video_audio
  echo ""
  echo "Done. Open: $FINAL_MP4"
}

main "$@"
