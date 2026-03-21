#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# NeuraNAC Sales Demo — Audio Generation
#
# Generates narration audio from sales-demo-narration.txt using TTS.
# Supports: macOS say (default), Piper TTS (if installed), or custom WAV input.
#
# Usage:
#   ./scripts/generate-demo-audio.sh                    # Use macOS say (default)
#   ./scripts/generate-demo-audio.sh --voice Samantha   # Specify voice
#   ./scripts/generate-demo-audio.sh --piper            # Use Piper if available
#   ./scripts/generate-demo-audio.sh --rate 125         # Slower speech
#
# Output: artifacts/sales-demo/neuranac-demo-narration.m4a
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
NARRATION_FILE="$PROJECT_ROOT/tests/e2e/sales-demo-narration.txt"
OUT_DIR="$PROJECT_ROOT/artifacts/sales-demo"
OUT_M4A="$OUT_DIR/neuranac-demo-narration.m4a"
OUT_WAV="$OUT_DIR/neuranac-demo-narration.wav"

# Defaults
VOICE="${VOICE:-Samantha}"
RATE="${RATE:-130}"
USE_PIPER=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --voice) VOICE="$2"; shift 2 ;;
    --rate)  RATE="$2";  shift 2 ;;
    --piper) USE_PIPER=true; shift ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

mkdir -p "$OUT_DIR"

# Extract narration text (strip # comments, join lines, preserve [[slnc N]] tags)
extract_text() {
  grep -v '^#' "$NARRATION_FILE" | grep -v '^[[:space:]]*$' | tr '\n' ' ' | sed 's/  */ /g'
}

# ── macOS say ────────────────────────────────────────────────────────────────
gen_say() {
  local text
  text=$(extract_text)
  echo "Generating audio with macOS say (voice=$VOICE, rate=$RATE)..."
  say -v "$VOICE" -r "$RATE" -o "$OUT_DIR/temp.aiff" "$text"
  # Convert AIFF to M4A (AAC)
  ffmpeg -y -i "$OUT_DIR/temp.aiff" -c:a aac -b:a 128k -ar 44100 "$OUT_M4A" 2>/dev/null
  rm -f "$OUT_DIR/temp.aiff"
  echo "  → $OUT_M4A"
}

# ── Piper TTS ─────────────────────────────────────────────────────────────────
gen_piper() {
  if ! python3 -c "import piper" 2>/dev/null; then
    echo "Piper not installed. Fallback to macOS say."
    gen_say
    return
  fi
  local model_dir model
  model_dir="${PIPER_MODEL_DIR:-$HOME/.local/share/piper}"
  model=$(find "$model_dir" -name "*.onnx" 2>/dev/null | head -1)
  if [[ -z "$model" ]]; then
    echo "No Piper model found. Run: python3 -m piper.download_voices en_US-lessac-medium"
    echo "Fallback to macOS say."
    gen_say
    return
  fi
  echo "Generating audio with Piper..."
  local text
  text=$(extract_text | sed 's/\[\[slnc [0-9]*\]\]//g')  # Piper doesn't support slnc
  echo "$text" | python3 -m piper -m "$model" -f "$OUT_WAV" --sentence-silence 0.5 2>/dev/null
  ffmpeg -y -i "$OUT_WAV" -c:a aac -b:a 128k -ar 44100 "$OUT_M4A" 2>/dev/null
  echo "  → $OUT_M4A"
}

# ── Main ─────────────────────────────────────────────────────────────────────
main() {
  if [[ ! -f "$NARRATION_FILE" ]]; then
    echo "Narration file not found: $NARRATION_FILE"
    exit 1
  fi

  if ! command -v ffmpeg &>/dev/null; then
    echo "ffmpeg is required. Install with: brew install ffmpeg"
    exit 1
  fi

  if [[ "$USE_PIPER" == true ]]; then
    gen_piper
  else
    case "$(uname -s)" in
      Darwin) gen_say ;;
      *)      gen_piper ;;
    esac
  fi
}

main "$@"
