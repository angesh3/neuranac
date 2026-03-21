#!/usr/bin/env bash
# Proto stub generation for NeuraNAC services.
#
# Prerequisites:
#   go install google.golang.org/protobuf/cmd/protoc-gen-go@latest
#   go install google.golang.org/grpc/cmd/protoc-gen-go-grpc@latest
#   pip install grpcio-tools
#
# Usage:  ./proto/generate.sh

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== NeuraNAC Proto Stub Generator ==="

# Output directories
GO_SYNC_OUT="$ROOT_DIR/services/sync-engine/internal/pb"
GO_RADIUS_OUT="$ROOT_DIR/services/radius-server/internal/pb"
PY_OUT="$ROOT_DIR/services/api-gateway/app/pb"

mkdir -p "$GO_SYNC_OUT" "$GO_RADIUS_OUT" "$PY_OUT"

# Check protoc
if ! command -v protoc &>/dev/null; then
  echo "ERROR: protoc not found. Install Protocol Buffers compiler."
  echo "  brew install protobuf   # macOS"
  echo "  apt install -y protobuf-compiler  # Debian/Ubuntu"
  exit 1
fi

echo "protoc version: $(protoc --version)"

# ── Go stubs ─────────────────────────────────────────────────────────────────
echo ""
echo "--- Generating Go stubs ---"

# sync.proto → sync-engine
echo "  sync.proto → $GO_SYNC_OUT"
protoc \
  --proto_path="$SCRIPT_DIR" \
  --go_out="$GO_SYNC_OUT" --go_opt=paths=source_relative \
  --go-grpc_out="$GO_SYNC_OUT" --go-grpc_opt=paths=source_relative \
  "$SCRIPT_DIR/sync.proto"

# policy.proto + ai.proto → radius-server
for proto in policy.proto ai.proto; do
  echo "  $proto → $GO_RADIUS_OUT"
  protoc \
    --proto_path="$SCRIPT_DIR" \
    --go_out="$GO_RADIUS_OUT" --go_opt=paths=source_relative \
    --go-grpc_out="$GO_RADIUS_OUT" --go-grpc_opt=paths=source_relative \
    "$SCRIPT_DIR/$proto"
done

# ── Python stubs ─────────────────────────────────────────────────────────────
echo ""
echo "--- Generating Python stubs ---"

python3 -m grpc_tools.protoc \
  --proto_path="$SCRIPT_DIR" \
  --python_out="$PY_OUT" \
  --grpc_python_out="$PY_OUT" \
  --pyi_out="$PY_OUT" \
  "$SCRIPT_DIR/sync.proto" \
  "$SCRIPT_DIR/policy.proto" \
  "$SCRIPT_DIR/ai.proto"

# Create __init__.py for the Python package
touch "$PY_OUT/__init__.py"

echo ""
echo "=== Done ==="
echo "  Go (sync-engine):   $GO_SYNC_OUT"
echo "  Go (radius-server): $GO_RADIUS_OUT"
echo "  Python:             $PY_OUT"
