#!/usr/bin/env python3
"""Generate Python and Go gRPC stubs from proto definitions.
Usage: python scripts/generate_proto.py
"""
import os
import sys
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROTO_DIR = os.path.join(ROOT, "proto")

PY_TARGETS = [
    os.path.join(ROOT, "services", "policy-engine", "app", "generated"),
    os.path.join(ROOT, "services", "api-gateway", "app", "generated"),
]

PROTO_FILES = ["policy.proto", "sync.proto", "ai.proto"]


def generate_python():
    """Generate Python protobuf + gRPC stubs using grpc_tools."""
    from grpc_tools import protoc

    for out_dir in PY_TARGETS:
        os.makedirs(out_dir, exist_ok=True)
        init_file = os.path.join(out_dir, "__init__.py")
        if not os.path.exists(init_file):
            open(init_file, "w").close()

        for proto_file in PROTO_FILES:
            proto_path = os.path.join(PROTO_DIR, proto_file)
            if not os.path.exists(proto_path):
                print(f"  SKIP {proto_file} (not found)")
                continue
            result = protoc.main([
                "grpc_tools.protoc",
                f"-I{PROTO_DIR}",
                f"--python_out={out_dir}",
                f"--grpc_python_out={out_dir}",
                proto_path,
            ])
            status = "OK" if result == 0 else f"FAIL({result})"
            print(f"  {proto_file} -> {out_dir} [{status}]")


def generate_go():
    """Generate Go protobuf + gRPC stubs (requires protoc + protoc-gen-go)."""
    go_targets = {
        "policy.proto": os.path.join(ROOT, "services", "radius-server", "internal", "pb"),
        "sync.proto": os.path.join(ROOT, "services", "sync-engine", "internal", "pb"),
        "ai.proto": os.path.join(ROOT, "services", "radius-server", "internal", "pb"),
    }
    for proto_file, out_dir in go_targets.items():
        os.makedirs(out_dir, exist_ok=True)
        proto_path = os.path.join(PROTO_DIR, proto_file)
        if not os.path.exists(proto_path):
            continue
        try:
            subprocess.run([
                "protoc",
                f"-I{PROTO_DIR}",
                f"--go_out={out_dir}", f"--go_opt=paths=source_relative",
                f"--go-grpc_out={out_dir}", f"--go-grpc_opt=paths=source_relative",
                proto_path,
            ], check=True)
            print(f"  {proto_file} -> {out_dir} [OK]")
        except FileNotFoundError:
            print(f"  {proto_file} -> SKIP (protoc not found, use Docker build)")
        except subprocess.CalledProcessError as e:
            print(f"  {proto_file} -> FAIL: {e}")


if __name__ == "__main__":
    print("=== Generating Python stubs ===")
    try:
        generate_python()
    except ImportError:
        print("  grpc_tools not installed. Run: pip install grpcio-tools")

    print("\n=== Generating Go stubs ===")
    generate_go()

    print("\nDone.")
