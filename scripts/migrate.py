#!/usr/bin/env python3
"""NeuraNAC Database Migration Runner — tracks applied migrations, supports upgrade and rollback.

Usage:
    python scripts/migrate.py upgrade              # Apply all pending migrations
    python scripts/migrate.py upgrade V005         # Apply up to V005
    python scripts/migrate.py rollback             # Rollback last applied migration
    python scripts/migrate.py rollback V003        # Rollback down to (but not including) V003
    python scripts/migrate.py status               # Show applied/pending migrations
    python scripts/migrate.py validate             # Verify checksums of applied migrations

The runner uses the neuranac_schema_versions table to track which migrations have been
applied, their checksums, and timestamps. Each migration file can optionally have
a companion *_rollback.sql file for down-migration support.

Migration files must be in database/migrations/ and follow the naming convention:
    V001_description.sql          (up migration)
    V001_description_rollback.sql (optional down migration)
"""
import hashlib
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# Allow running from project root or scripts dir
PROJECT_ROOT = Path(__file__).resolve().parent.parent
MIGRATIONS_DIR = PROJECT_ROOT / "database" / "migrations"

# Database connection from environment
DB_HOST = os.getenv("POSTGRES_HOST", "localhost")
DB_PORT = os.getenv("POSTGRES_PORT", "5432")
DB_NAME = os.getenv("POSTGRES_DB", "neuranac")
DB_USER = os.getenv("POSTGRES_USER", "neuranac")
DB_PASS = os.getenv("POSTGRES_PASSWORD", "neuranac_dev_password")

VERSION_PATTERN = re.compile(r"^(V\d{3})_(.+)\.sql$")
ROLLBACK_PATTERN = re.compile(r"^(V\d{3})_(.+)_rollback\.sql$")


def get_connection():
    """Get a psycopg2 connection (sync, for the migration script)."""
    try:
        import psycopg2
    except ImportError:
        print("ERROR: psycopg2 is required. Install with: pip install psycopg2-binary")
        sys.exit(1)
    return psycopg2.connect(
        host=DB_HOST, port=DB_PORT, dbname=DB_NAME,
        user=DB_USER, password=DB_PASS,
    )


def ensure_schema_versions_table(conn):
    """Create the tracking table if it doesn't exist."""
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS neuranac_schema_versions (
                version VARCHAR(20) PRIMARY KEY,
                description TEXT,
                applied_at TIMESTAMPTZ DEFAULT NOW(),
                applied_by VARCHAR(255) DEFAULT CURRENT_USER,
                checksum VARCHAR(64)
            )
        """)
    conn.commit()


def get_applied_versions(conn) -> dict:
    """Return {version: {description, applied_at, checksum}} for all applied migrations."""
    with conn.cursor() as cur:
        cur.execute("SELECT version, description, applied_at, checksum FROM neuranac_schema_versions ORDER BY version")
        rows = cur.fetchall()
    return {
        row[0]: {"description": row[1], "applied_at": row[2], "checksum": row[3]}
        for row in rows
    }


def discover_migrations() -> list:
    """Discover migration files and return sorted list of (version, description, path)."""
    migrations = []
    if not MIGRATIONS_DIR.exists():
        print(f"ERROR: Migrations directory not found: {MIGRATIONS_DIR}")
        sys.exit(1)

    for f in sorted(MIGRATIONS_DIR.iterdir()):
        m = VERSION_PATTERN.match(f.name)
        if m and not ROLLBACK_PATTERN.match(f.name):
            version = m.group(1)
            description = m.group(2).replace("_", " ")
            migrations.append((version, description, f))
    return migrations


def file_checksum(path: Path) -> str:
    """SHA-256 checksum of a migration file."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def find_rollback_file(migration_path: Path) -> Path | None:
    """Find the companion rollback file for a migration."""
    stem = migration_path.stem  # e.g. V001_initial_schema
    rollback = migration_path.parent / f"{stem}_rollback.sql"
    return rollback if rollback.exists() else None


def cmd_status(conn):
    """Show migration status."""
    applied = get_applied_versions(conn)
    migrations = discover_migrations()

    print(f"\n{'Version':<10} {'Description':<40} {'Status':<12} {'Applied At'}")
    print("-" * 90)
    for version, desc, path in migrations:
        if version in applied:
            info = applied[version]
            ts = info["applied_at"].strftime("%Y-%m-%d %H:%M:%S") if info["applied_at"] else "?"
            checksum_ok = info["checksum"] == file_checksum(path)
            status = "applied" if checksum_ok else "MODIFIED!"
            print(f"{version:<10} {desc:<40} {status:<12} {ts}")
        else:
            print(f"{version:<10} {desc:<40} {'pending':<12} -")

    pending = [v for v, _, _ in migrations if v not in applied]
    print(f"\nTotal: {len(migrations)} migrations, {len(applied)} applied, {len(pending)} pending")


def cmd_upgrade(conn, target_version=None):
    """Apply pending migrations up to target_version (or all if None)."""
    applied = get_applied_versions(conn)
    migrations = discover_migrations()

    pending = [(v, d, p) for v, d, p in migrations if v not in applied]
    if target_version:
        pending = [(v, d, p) for v, d, p in pending if v <= target_version]

    if not pending:
        print("No pending migrations to apply.")
        return

    print(f"Applying {len(pending)} migration(s)...\n")
    for version, desc, path in pending:
        sql = path.read_text()
        checksum = file_checksum(path)
        print(f"  Applying {version}: {desc}...", end=" ", flush=True)
        try:
            with conn.cursor() as cur:
                cur.execute(sql)
                cur.execute(
                    """INSERT INTO neuranac_schema_versions (version, description, checksum)
                       VALUES (%s, %s, %s)
                       ON CONFLICT (version) DO UPDATE SET
                           checksum = EXCLUDED.checksum,
                           applied_at = NOW()""",
                    (version, desc, checksum),
                )
            conn.commit()
            print("OK")
        except Exception as e:
            conn.rollback()
            print(f"FAILED\n  Error: {e}")
            sys.exit(1)

    print(f"\nDone. {len(pending)} migration(s) applied successfully.")


def cmd_rollback(conn, target_version=None):
    """Rollback the last applied migration, or down to target_version."""
    applied = get_applied_versions(conn)
    migrations = discover_migrations()

    # Build list of applied migrations in reverse order
    applied_migrations = [
        (v, d, p) for v, d, p in migrations if v in applied
    ]
    applied_migrations.reverse()

    if not applied_migrations:
        print("No migrations to rollback.")
        return

    to_rollback = []
    for v, d, p in applied_migrations:
        if target_version and v <= target_version:
            break
        to_rollback.append((v, d, p))

    if not to_rollback and not target_version:
        to_rollback = [applied_migrations[0]]

    if not to_rollback:
        print(f"Nothing to rollback (already at or below {target_version}).")
        return

    print(f"Rolling back {len(to_rollback)} migration(s)...\n")
    for version, desc, path in to_rollback:
        rollback_file = find_rollback_file(path)
        if not rollback_file:
            print(f"  WARNING: No rollback file for {version} ({path.stem}_rollback.sql)")
            print(f"  Removing version tracking entry only (schema changes NOT reverted).")
            with conn.cursor() as cur:
                cur.execute("DELETE FROM neuranac_schema_versions WHERE version = %s", (version,))
            conn.commit()
            continue

        sql = rollback_file.read_text()
        print(f"  Rolling back {version}: {desc}...", end=" ", flush=True)
        try:
            with conn.cursor() as cur:
                cur.execute(sql)
                cur.execute("DELETE FROM neuranac_schema_versions WHERE version = %s", (version,))
            conn.commit()
            print("OK")
        except Exception as e:
            conn.rollback()
            print(f"FAILED\n  Error: {e}")
            sys.exit(1)

    print(f"\nDone. {len(to_rollback)} migration(s) rolled back.")


def cmd_validate(conn):
    """Validate checksums of applied migrations against current files."""
    applied = get_applied_versions(conn)
    migrations = discover_migrations()
    errors = 0

    print(f"\nValidating {len(applied)} applied migration(s)...\n")
    for version, desc, path in migrations:
        if version not in applied:
            continue
        stored_checksum = applied[version]["checksum"]
        current_checksum = file_checksum(path)
        if stored_checksum != current_checksum:
            print(f"  MISMATCH {version}: file has been modified since it was applied!")
            print(f"    Stored:  {stored_checksum}")
            print(f"    Current: {current_checksum}")
            errors += 1
        else:
            print(f"  OK {version}")

    if errors:
        print(f"\n{errors} checksum mismatch(es) found! Migration files may have been modified.")
        sys.exit(1)
    else:
        print("\nAll checksums valid.")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)

    command = sys.argv[1]
    target = sys.argv[2] if len(sys.argv) > 2 else None

    conn = get_connection()
    ensure_schema_versions_table(conn)

    try:
        if command == "status":
            cmd_status(conn)
        elif command == "upgrade":
            cmd_upgrade(conn, target)
        elif command == "rollback":
            cmd_rollback(conn, target)
        elif command == "validate":
            cmd_validate(conn)
        else:
            print(f"Unknown command: {command}")
            print("Commands: upgrade, rollback, status, validate")
            sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
