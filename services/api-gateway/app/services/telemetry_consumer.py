"""NATS → DB Telemetry Consumer — subscribes to telemetry subjects published by
the ingestion-collector and persists events into neuranac_telemetry_events.

Subjects consumed:
  neuranac.telemetry.snmp   — SNMP trap events
  neuranac.telemetry.syslog — Syslog messages
  neuranac.telemetry.netflow — NetFlow/IPFIX records
  neuranac.telemetry.dhcp   — DHCP snooped events
  neuranac.telemetry.neighbor — CDP/LLDP neighbor discoveries

The consumer runs as an asyncio background task started during API Gateway
lifespan and batches INSERTs for throughput.
"""
import asyncio
import json
import os
from datetime import datetime, timezone
from typing import List, Optional

import structlog

logger = structlog.get_logger()

TELEMETRY_SUBJECTS = [
    "neuranac.telemetry.snmp",
    "neuranac.telemetry.syslog",
    "neuranac.telemetry.netflow",
    "neuranac.telemetry.dhcp",
    "neuranac.telemetry.neighbor",
]

BATCH_SIZE = int(os.getenv("TELEMETRY_CONSUMER_BATCH_SIZE", "50"))
FLUSH_INTERVAL_SECONDS = float(os.getenv("TELEMETRY_CONSUMER_FLUSH_INTERVAL", "2.0"))

_consumer_task: Optional[asyncio.Task] = None
_running = False


async def start_telemetry_consumer():
    """Start the background NATS → DB consumer. Safe to call even if NATS is unavailable."""
    global _consumer_task, _running
    _running = True
    _consumer_task = asyncio.create_task(_run_consumer())
    logger.info("Telemetry consumer started")


async def stop_telemetry_consumer():
    """Gracefully stop the consumer task."""
    global _running, _consumer_task
    _running = False
    if _consumer_task and not _consumer_task.done():
        _consumer_task.cancel()
        try:
            await _consumer_task
        except asyncio.CancelledError:
            pass
    _consumer_task = None
    logger.info("Telemetry consumer stopped")


async def _run_consumer():
    """Main consumer loop: subscribe to NATS subjects and batch-flush to DB."""
    from app.services.nats_client import get_nats_js

    js = get_nats_js()
    if js is None:
        logger.warning("Telemetry consumer: NATS unavailable — will retry in 10s")
        while _running:
            await asyncio.sleep(10)
            from app.services.nats_client import get_nats_js
            js = get_nats_js()
            if js is not None:
                break
        if not _running:
            return

    # Ensure stream exists (idempotent)
    try:
        await js.add_stream(
            name="TELEMETRY",
            subjects=TELEMETRY_SUBJECTS,
            max_age=86400_000_000_000,  # 24h retention in nanoseconds
        )
    except Exception as exc:
        logger.debug("Telemetry stream may already exist", error=str(exc))

    # Subscribe with durable pull consumer for reliable delivery
    subscriptions = []
    for subject in TELEMETRY_SUBJECTS:
        try:
            sub = await js.subscribe(subject, durable=f"api-gw-{subject.split('.')[-1]}")
            subscriptions.append(sub)
            logger.info("Subscribed to telemetry subject", subject=subject)
        except Exception as exc:
            logger.warning("Failed to subscribe to telemetry subject",
                           subject=subject, error=str(exc))

    if not subscriptions:
        logger.error("Telemetry consumer: no subscriptions created — exiting")
        return

    buffer: List[dict] = []

    async def _flush_buffer():
        nonlocal buffer
        if not buffer:
            return
        batch = buffer[:BATCH_SIZE]
        buffer = buffer[BATCH_SIZE:]
        try:
            await _insert_batch(batch)
        except Exception as exc:
            logger.error("Telemetry consumer: DB insert failed",
                         error=str(exc), batch_size=len(batch))

    while _running:
        try:
            for sub in subscriptions:
                try:
                    msgs = await sub.fetch(batch=BATCH_SIZE, timeout=0.5)
                    for msg in msgs:
                        try:
                            data = json.loads(msg.data.decode())
                            data["_subject"] = msg.subject
                            buffer.append(data)
                            await msg.ack()
                        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                            logger.debug("Telemetry consumer: bad message", error=str(exc))
                            await msg.ack()  # ack to avoid redelivery of corrupt msgs
                except Exception:
                    pass  # timeout or temporary error, keep going

            if len(buffer) >= BATCH_SIZE:
                await _flush_buffer()
            else:
                await asyncio.sleep(FLUSH_INTERVAL_SECONDS)
                await _flush_buffer()

        except asyncio.CancelledError:
            # Final flush before exit
            await _flush_buffer()
            raise
        except Exception as exc:
            logger.error("Telemetry consumer loop error", error=str(exc))
            await asyncio.sleep(2)


async def _insert_batch(events: List[dict]):
    """Batch-insert telemetry events into neuranac_telemetry_events."""
    from app.database.session import get_async_engine
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.orm import sessionmaker

    engine = get_async_engine()
    if engine is None:
        logger.warning("Telemetry consumer: DB engine not available, dropping batch",
                       batch_size=len(events))
        return

    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        for event in events:
            subject = event.pop("_subject", "")
            event_type = subject.split(".")[-1] if subject else "unknown"
            try:
                await session.execute(text("""
                    INSERT INTO neuranac_telemetry_events
                        (event_type, source_ip, site_id, node_id, severity,
                         facility, trap_oid, message, raw_data)
                    VALUES
                        (:event_type, CAST(:source_ip AS inet), CAST(:site_id AS uuid), :node_id,
                         :severity, :facility, :trap_oid, :message, CAST(:raw_data AS jsonb))
                """), {
                    "event_type": event_type,
                    "source_ip": event.get("source_ip", "0.0.0.0"),
                    "site_id": event.get("site_id"),
                    "node_id": event.get("node_id"),
                    "severity": event.get("severity", "info"),
                    "facility": event.get("facility"),
                    "trap_oid": event.get("trap_oid") or event.get("oid"),
                    "message": event.get("message", ""),
                    "raw_data": json.dumps(event),
                })
            except Exception as exc:
                logger.debug("Telemetry insert failed for single event",
                             error=str(exc), event_type=event_type)
        await session.commit()
        logger.debug("Telemetry batch inserted", count=len(events))
