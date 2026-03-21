#!/usr/bin/env python3
"""
Collect training data from NeuraNAC operational logs for LLM fine-tuning.

Sources:
  1. Positive chat feedback   — queries that users found helpful
  2. Accepted policy translations — NL → policy JSON pairs
  3. Resolved troubleshooting sessions — symptoms → root cause + fix
  4. NAC knowledge base articles — built-in domain knowledge
  5. Endpoint profiling corrections — operator-corrected device labels

Output: JSONL file at /data/training/finetune_pairs.jsonl
        Each line: {"instruction": "...", "output": "...", "source": "..."}

Usage:
  python3 scripts/collect_training_data.py [--db-url postgresql://neuranac:neuranac@localhost:5432/neuranac] [--output /data/training/finetune_pairs.jsonl]
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def get_db_connection(db_url: str):
    """Get a psycopg2 connection (sync driver for scripts)."""
    try:
        import psycopg2
        import psycopg2.extras
        conn = psycopg2.connect(db_url)
        conn.autocommit = True
        return conn
    except ImportError:
        print("ERROR: psycopg2 not installed. Install with: pip install psycopg2-binary")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: Cannot connect to database: {e}")
        return None


def safe_query(conn, sql: str, params=None):
    """Execute a query and return rows, or empty list on error."""
    if conn is None:
        return []
    try:
        import psycopg2.extras
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params or ())
            return cur.fetchall()
    except Exception as e:
        print(f"  WARNING: Query failed ({e}), skipping this source")
        return []


# ---------------------------------------------------------------------------
# Collectors — each returns a list of {"instruction", "output", "source"}
# ---------------------------------------------------------------------------

def collect_chat_feedback(conn, days: int = 30) -> list:
    """Collect chat interactions where the user gave positive feedback."""
    pairs = []
    rows = safe_query(conn, """
        SELECT query, response, intent
        FROM ai_chat_log
        WHERE feedback = 'positive'
          AND created_at > NOW() - INTERVAL '%s days'
        ORDER BY created_at DESC
        LIMIT 500
    """, (days,))
    for r in rows:
        pairs.append({
            "instruction": r["query"],
            "output": r["response"],
            "source": "chat_positive_feedback",
        })
    return pairs


def collect_policy_translations(conn, days: int = 30) -> list:
    """Collect NL → policy rule translations that operators accepted."""
    pairs = []
    rows = safe_query(conn, """
        SELECT natural_language, translated_rules
        FROM policy_translations
        WHERE status = 'accepted'
          AND created_at > NOW() - INTERVAL '%s days'
        ORDER BY created_at DESC
        LIMIT 200
    """, (days,))
    for r in rows:
        pairs.append({
            "instruction": f"Translate this policy: {r['natural_language']}",
            "output": r["translated_rules"],
            "source": "policy_accepted",
        })
    return pairs


def collect_troubleshooting_resolutions(conn, days: int = 30) -> list:
    """Collect troubleshooting sessions that were resolved."""
    pairs = []
    rows = safe_query(conn, """
        SELECT symptoms, root_cause, resolution
        FROM troubleshooting_sessions
        WHERE resolved = true
          AND created_at > NOW() - INTERVAL '%s days'
        ORDER BY created_at DESC
        LIMIT 200
    """, (days,))
    for r in rows:
        pairs.append({
            "instruction": f"Troubleshoot: {r['symptoms']}",
            "output": f"Root cause: {r['root_cause']}\nResolution: {r['resolution']}",
            "source": "troubleshoot_resolved",
        })
    return pairs


def collect_profiling_corrections(conn, days: int = 30) -> list:
    """Collect operator corrections to endpoint profiling results."""
    pairs = []
    rows = safe_query(conn, """
        SELECT mac_address, original_type, corrected_type, vendor, hostname
        FROM endpoint_profile_corrections
        WHERE created_at > NOW() - INTERVAL '%s days'
        ORDER BY created_at DESC
        LIMIT 300
    """, (days,))
    for r in rows:
        attrs = f"MAC: {r['mac_address']}, Vendor: {r.get('vendor', 'unknown')}, Hostname: {r.get('hostname', 'unknown')}"
        pairs.append({
            "instruction": f"What device type is this endpoint? {attrs}",
            "output": f"This endpoint is a {r['corrected_type']}.",
            "source": "profiling_correction",
        })
    return pairs


def collect_nac_knowledge_base() -> list:
    """Generate training pairs from the built-in NAC knowledge base articles."""
    pairs = []
    try:
        # Import from the AI engine's knowledge base
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services", "ai-engine"))
        from app.intents.nac_knowledge import NAC_KNOWLEDGE_ARTICLES
        from app.intents.product_knowledge import PRODUCT_KNOWLEDGE_INTENTS

        for article in NAC_KNOWLEDGE_ARTICLES:
            # Use the title as the question
            pairs.append({
                "instruction": f"Explain: {article['title']}",
                "output": article["content"],
                "source": "nac_knowledge_base",
            })
            # Also generate a question from keywords
            keywords = article.get("keywords", [])
            if keywords:
                kw_question = f"What do you know about {', '.join(keywords[:3])}?"
                pairs.append({
                    "instruction": kw_question,
                    "output": article["content"],
                    "source": "nac_knowledge_base",
                })

        for intent in PRODUCT_KNOWLEDGE_INTENTS:
            if intent.get("response"):
                pairs.append({
                    "instruction": f"Tell me about NeuraNAC {intent['intent'].replace('_', ' ')}",
                    "output": intent["response"],
                    "source": "product_knowledge_base",
                })
    except ImportError as e:
        print(f"  WARNING: Could not import knowledge base ({e}), skipping")
    return pairs


def collect_seed_training_data() -> list:
    """Generate seed training pairs for bootstrapping a fine-tune when no operational
    data is available yet. These are manually curated NAC domain Q&A pairs."""
    return [
        {
            "instruction": "What RADIUS attribute assigns a VLAN?",
            "output": "Tunnel-Private-Group-ID (RADIUS attribute 81) is used to assign a VLAN to an authenticated endpoint. The RADIUS server includes this attribute in the Access-Accept packet. The switch reads it and places the port in the specified VLAN.",
            "source": "seed",
        },
        {
            "instruction": "What is the difference between MAB and 802.1X?",
            "output": "802.1X uses an EAP supplicant on the endpoint for cryptographic authentication (certificates or credentials). MAB (MAC Authentication Bypass) uses the endpoint's MAC address as the identity when no 802.1X supplicant is available. 802.1X is more secure; MAB is used for devices that cannot run a supplicant (printers, IP phones, IoT sensors).",
            "source": "seed",
        },
        {
            "instruction": "How does Change of Authorization (CoA) work?",
            "output": "CoA (RFC 5176) allows a RADIUS server to push authorization changes to a Network Access Device (NAD) mid-session. The server sends a CoA-Request to port 3799 on the NAD, which can trigger reauthentication, VLAN change, ACL update, or session disconnect. The NAD responds with CoA-ACK or CoA-NAK.",
            "source": "seed",
        },
        {
            "instruction": "SQL: How many endpoints authenticated in the last 24 hours?",
            "output": "SELECT COUNT(DISTINCT endpoint_mac) as unique_endpoints FROM auth_sessions WHERE started_at >= NOW() - INTERVAL '24 hours'",
            "source": "seed",
        },
        {
            "instruction": "SQL: Show top 10 network devices by session count",
            "output": "SELECT nas_ip, COUNT(*) as session_count FROM auth_sessions WHERE started_at >= NOW() - INTERVAL '7 days' GROUP BY nas_ip ORDER BY session_count DESC LIMIT 10",
            "source": "seed",
        },
        {
            "instruction": "Translate this policy: Block all BYOD devices after 6pm",
            "output": "{\"rules\": [{\"name\": \"block-byod-after-hours\", \"conditions\": [{\"attribute\": \"endpoint.ownership\", \"operator\": \"equals\", \"value\": \"BYOD\"}, {\"attribute\": \"time.hour\", \"operator\": \"greater_than\", \"value\": \"18\"}], \"action\": \"deny\"}], \"explanation\": \"Denies network access to BYOD (Bring Your Own Device) endpoints after 6:00 PM.\"}",
            "source": "seed",
        },
        {
            "instruction": "Translate this policy: Allow all corporate laptops on VLAN 100",
            "output": "{\"rules\": [{\"name\": \"corporate-laptops-vlan100\", \"conditions\": [{\"attribute\": \"endpoint.ownership\", \"operator\": \"equals\", \"value\": \"corporate\"}, {\"attribute\": \"endpoint.device_type\", \"operator\": \"in\", \"value\": [\"windows-pc\", \"macos\", \"linux-workstation\"]}], \"action\": \"permit\", \"authorization\": {\"vlan\": 100}}], \"explanation\": \"Permits corporate-owned laptops and assigns them to VLAN 100.\"}",
            "source": "seed",
        },
        {
            "instruction": "What is posture assessment in NAC?",
            "output": "Posture assessment checks an endpoint's security compliance before granting full network access. It evaluates: antivirus status and definitions, OS patch level, disk encryption, firewall status, and prohibited software. Endpoints that fail posture can be quarantined or given limited access until remediated.",
            "source": "seed",
        },
        {
            "instruction": "Troubleshoot: EAP-TLS authentication is failing with 'certificate unknown' error",
            "output": "Root cause: The endpoint's client certificate is not signed by a CA trusted by the RADIUS server.\nResolution: 1) Verify the endpoint certificate chain — ensure the issuing CA is in NeuraNAC's trusted certificate store. 2) Check certificate validity dates. 3) Verify the certificate has not been revoked (check CRL/OCSP). 4) Ensure the EAP-TLS authentication policy references the correct certificate profile.",
            "source": "seed",
        },
        {
            "instruction": "What is a Security Group Tag (SGT)?",
            "output": "A Security Group Tag (SGT) is a 16-bit identifier assigned to endpoints or users that enables software-defined segmentation (TrustSec/CTS). Instead of using IP-based ACLs, SGTs classify traffic by identity. SGT-based policies (SGACL) are enforced at switches and firewalls. Example: employees get SGT 10, contractors get SGT 20, and an SGACL blocks SGT 20 from reaching finance servers.",
            "source": "seed",
        },
        {
            "instruction": "What are the common EAP types used in 802.1X?",
            "output": "Common EAP types: 1) EAP-TLS — certificate-based, most secure, requires client cert. 2) PEAP (MSCHAPv2) — password-based, encrypted tunnel, most common for Windows. 3) EAP-FAST — Cisco proprietary, PAC-based, fast reauthentication. 4) EAP-TTLS — similar to PEAP but more flexible inner methods. 5) EAP-MD5 — legacy, no mutual authentication, not recommended.",
            "source": "seed",
        },
        {
            "instruction": "How does NeuraNAC detect Shadow AI usage on the network?",
            "output": "NeuraNAC's Shadow AI Detector monitors DNS queries and network flows against 14 built-in AI service signatures (OpenAI, Anthropic, Google Gemini, GitHub Copilot, Hugging Face, etc.). When an endpoint resolves api.openai.com or similar domains, NeuraNAC flags it with the service name, risk level, and whether it is on the approved list. Admins can add custom signatures and set auto-quarantine policies for unauthorized AI usage.",
            "source": "seed",
        },
    ]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Collect LLM fine-tuning data from NeuraNAC")
    parser.add_argument("--db-url", default=os.getenv("AI_PG_DSN", "postgresql://neuranac:neuranac@localhost:5432/neuranac"),
                        help="PostgreSQL connection URL")
    parser.add_argument("--output", default=os.getenv("AI_TRAINING_OUTPUT", "/data/training/finetune_pairs.jsonl"),
                        help="Output JSONL file path")
    parser.add_argument("--days", type=int, default=30, help="How many days of history to collect")
    parser.add_argument("--include-seed", action="store_true", default=True,
                        help="Include seed training data for bootstrapping")
    parser.add_argument("--include-knowledge-base", action="store_true", default=True,
                        help="Include built-in NAC knowledge base articles")
    args = parser.parse_args()

    print(f"NeuraNAC Training Data Collector")
    print(f"  Database:  {args.db_url.split('@')[-1] if '@' in args.db_url else args.db_url}")
    print(f"  Output:    {args.output}")
    print(f"  Days:      {args.days}")
    print()

    all_pairs = []

    # 1. Database-sourced training pairs
    print("Connecting to database...")
    conn = get_db_connection(args.db_url)

    collectors = [
        ("Chat feedback", collect_chat_feedback),
        ("Policy translations", collect_policy_translations),
        ("Troubleshooting resolutions", collect_troubleshooting_resolutions),
        ("Profiling corrections", collect_profiling_corrections),
    ]

    for name, collector_fn in collectors:
        print(f"  Collecting {name}...")
        pairs = collector_fn(conn, args.days)
        print(f"    → {len(pairs)} pairs")
        all_pairs.extend(pairs)

    if conn:
        conn.close()

    # 2. Built-in knowledge base
    if args.include_knowledge_base:
        print("  Collecting NAC knowledge base...")
        kb_pairs = collect_nac_knowledge_base()
        print(f"    → {len(kb_pairs)} pairs")
        all_pairs.extend(kb_pairs)

    # 3. Seed training data
    if args.include_seed:
        print("  Adding seed training data...")
        seed_pairs = collect_seed_training_data()
        print(f"    → {len(seed_pairs)} pairs")
        all_pairs.extend(seed_pairs)

    # Deduplicate by instruction
    seen = set()
    unique_pairs = []
    for p in all_pairs:
        key = p["instruction"].strip().lower()
        if key not in seen:
            seen.add(key)
            unique_pairs.append(p)

    # Write output
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w") as f:
        for pair in unique_pairs:
            f.write(json.dumps(pair, ensure_ascii=False) + "\n")

    # Summary
    by_source = {}
    for p in unique_pairs:
        by_source[p["source"]] = by_source.get(p["source"], 0) + 1

    print()
    print(f"Training data collected: {len(unique_pairs)} unique pairs")
    for source, count in sorted(by_source.items()):
        print(f"  {source}: {count}")
    print(f"\nWritten to: {output_path}")
    print(f"File size:  {output_path.stat().st_size / 1024:.1f} KB")


if __name__ == "__main__":
    main()
