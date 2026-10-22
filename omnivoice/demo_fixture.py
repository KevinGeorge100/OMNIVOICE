"""Isolated, repeatable synthetic sales fixture for local demonstrations.

This module never opens the production Store: Store.open() intentionally reconciles
in-flight calls on startup, which would be unsafe for a data-only reset command.
"""

import json
import secrets
import sqlite3
import time
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .models import TenantInput
from .store import SCHEMA, token_hash

MARKER = "omnivoice-final-demo-v1"
LEAD_REFERENCE = "DEMO-ALPHA-001"
DEFAULT_DATABASE = Path("data/demo/omnivoice-demo.db")
try:
    ZONE = ZoneInfo("Asia/Kolkata")
except ZoneInfoNotFoundError:
    ZONE = timezone(timedelta(hours=5, minutes=30))

FAQS = (
    ("What is OmniVoice?", "OmniVoice is an enterprise voice AI platform for live telephone conversations."),
    ("How does OmniVoice work?", "A carrier streams call audio to the voice engine. It detects speech, uses approved knowledge and tools, then speaks a response. Writes require explicit caller confirmation."),
    ("Which languages are available?", "This demo is configured for English (India). Other supported configurations require separate provider and call validation."),
    ("What does OmniVoice cost?", "No public price is set in this demo. A team member can discuss a tailored proposal."),
    ("Which systems can OmniVoice connect to?", "The current project integrates telephony, speech providers and Groq. The demo booking tools use local tenant-scoped data; external CRM and calendar integrations are not configured."),
    ("How do I book a demo?", "Ask for available demo times, choose one, and explicitly confirm the proposed booking before it is saved."),
)


def _fixture_tenants(db: sqlite3.Connection) -> list[str]:
    rows = db.execute("SELECT id, config FROM tenants").fetchall()
    result = []
    for tenant_id, raw in rows:
        try:
            if json.loads(raw).get("demo_fixture") == MARKER:
                result.append(tenant_id)
        except (TypeError, ValueError):
            continue
    return result


def _slot_times(now: datetime) -> list[tuple[str, str]]:
    friday = now.date() + timedelta(days=(4 - now.weekday()) % 7 or 7)
    return [
        (
            datetime.combine(friday + timedelta(days=days), datetime.min.time(), ZONE)
            .replace(hour=hour).isoformat(),
            datetime.combine(friday + timedelta(days=days), datetime.min.time(), ZONE)
            .replace(hour=hour, minute=30).isoformat(),
        )
        for days, hour in ((0, 16), (3, 11), (5, 15))
    ]


def prepare_demo(database: Path, *, reset: bool = False, dry_run: bool = False) -> dict:
    """Seed or reset only the uniquely marked fixture; never touch other tenants."""
    database = Path(database)
    if not database.exists() and reset:
        raise ValueError("Demo database does not exist; run seed first")
    if not database.exists() and dry_run:
        return {"operation": "create", "dry_run": True, "tenant_id": None}
    if not dry_run:
        database.parent.mkdir(parents=True, exist_ok=True)
    uri = f"file:{database.resolve().as_posix()}?mode={'ro' if dry_run else 'rwc'}"
    with closing(sqlite3.connect(uri, uri=True, timeout=5)) as db:
        db.execute("PRAGMA foreign_keys=ON")
        if not dry_run:
            db.executescript(SCHEMA)
        elif not db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='tenants'"
        ).fetchone():
            return {"operation": "create", "dry_run": True, "tenant_id": None}
        matches = _fixture_tenants(db)
        if len(matches) > 1:
            raise ValueError("Multiple marked demo tenants found; manual review required")
        tenant_id = matches[0] if matches else None
        if reset and not tenant_id:
            raise ValueError("No marked synthetic demo tenant; refusing to reset")
        if tenant_id:
            if db.execute("SELECT 1 FROM lines WHERE tenant_id=? LIMIT 1", (tenant_id,)).fetchone():
                raise ValueError("Demo tenant has a carrier line; refusing to reset")
            if db.execute(
                "SELECT 1 FROM calls WHERE tenant_id=? AND (status='active' OR ended IS NULL) LIMIT 1",
                (tenant_id,),
            ).fetchone():
                raise ValueError("Demo tenant has an active call; refusing to reset")
        operation = "reset" if reset else "exists" if tenant_id else "create"
        if dry_run or operation == "exists":
            return {"operation": operation, "dry_run": dry_run, "tenant_id": tenant_id}

        now = time.time()
        db.execute("BEGIN IMMEDIATE")
        try:
            if tenant_id:
                for table in (
                    "demo_bookings", "followups", "demo_slots", "leads", "actions", "calls", "knowledge"
                ):
                    db.execute(f"DELETE FROM {table} WHERE tenant_id=?", (tenant_id,))
                db.execute("UPDATE tenants SET revision=revision+1 WHERE id=?", (tenant_id,))
            else:
                tenant_id = uuid4().hex
                config = TenantInput(
                    name="OmniVoice Synthetic Demo",
                    language="en-IN",
                    timezone="Asia/Kolkata",
                    greeting="Hello, this is the OmniVoice demo assistant. How can I help you?",
                    instructions="Use approved knowledge and tenant-scoped tools. Never claim a booking until it commits.",
                    confirmation_phrases=["yes", "yes confirm"],
                ).model_dump()
                config["demo_fixture"] = MARKER
                db.execute(
                    "INSERT INTO tenants VALUES (?,?,?,?,0,?)",
                    (tenant_id, config["name"], token_hash(secrets.token_urlsafe(32)),
                     json.dumps(config), now),
                )
            for question, answer in FAQS:
                db.execute(
                    "INSERT INTO knowledge VALUES (?,?,?,?,?,?,?)",
                    (uuid4().hex, tenant_id, "faq", question, answer, 1, now),
                )
            db.execute(
                "INSERT INTO leads VALUES (?,?,?,?,?,?,?,?,?,?)",
                (uuid4().hex, tenant_id, "Demo Visitor", LEAD_REFERENCE, None,
                 "new", "synthetic_demo", "", now, now),
            )
            for start, end in _slot_times(datetime.now(ZONE)):
                db.execute(
                    "INSERT INTO demo_slots VALUES (?,?,?,?,?,?)",
                    (uuid4().hex, tenant_id, start, end, "available", now),
                )
            db.commit()
        except Exception:
            db.rollback()
            raise
        return {"operation": operation, "dry_run": False, "tenant_id": tenant_id,
                "knowledge": len(FAQS), "leads": 1, "slots": 3}
