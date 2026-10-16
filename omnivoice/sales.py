"""Tenant-scoped local sales capabilities and atomic booking."""

from __future__ import annotations

import time
from datetime import date, datetime, timezone
from uuid import uuid4

from .tools import ToolDefinition


class SalesError(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


class SalesService:
    def __init__(self, store):
        self.store = store

    async def add_lead(self, tenant_id, name, identifier, *, email=None, status="new", source="demo", notes=""):
        if (not 1 <= len(name.strip()) <= 100 or not 1 <= len(identifier.strip()) <= 80
                or len(notes) > 240 or len(status) > 40 or len(source) > 40):
            raise ValueError("Invalid lead fields")
        lead_id, now = uuid4().hex, time.time()
        await self.store.execute(
            "INSERT INTO leads VALUES (?,?,?,?,?,?,?,?,?,?)",
            (lead_id, tenant_id, name, identifier, email, status, source, notes, now, now),
        )
        return lead_id

    async def add_slot(self, tenant_id, start_at, end_at, *, status="available"):
        start, end = datetime.fromisoformat(start_at), datetime.fromisoformat(end_at)
        if start.tzinfo is None or end.tzinfo is None or end <= start or status not in {
            "available", "booked",
        }:
            raise ValueError("Slots require ordered timezone-aware datetimes")
        slot_id = uuid4().hex
        await self.store.execute(
            "INSERT INTO demo_slots VALUES (?,?,?,?,?,?)",
            (slot_id, tenant_id, start.isoformat(), end.isoformat(), status, time.time()),
        )
        return slot_id

    async def lookup_lead(self, ctx, args):
        identifier = args.get("identifier") or (ctx.state or {}).get("caller_identifier")
        if not identifier:
            return {"found": False, "reason": "identity_required"}
        lead = await self.store.one(
            "SELECT id,name,status,source FROM leads WHERE tenant_id=? AND identifier=?",
            (ctx.tenant_id, identifier),
        )
        if not lead:
            return {"found": False, "reason": "not_found"}
        if ctx.state is not None:
            ctx.state["lead_id"] = lead["id"]
            ctx.state["lead_name"] = lead["name"]
        return {"found": True, "lead": lead}

    async def check_demo_slots(self, ctx, args):
        requested = date.fromisoformat(args["date"])
        preference = args.get("time_preference", "any")
        hours = {
            "morning": " AND CAST(substr(start_at,12,2) AS INTEGER)<12",
            "afternoon": " AND CAST(substr(start_at,12,2) AS INTEGER) BETWEEN 12 AND 16",
            "evening": " AND CAST(substr(start_at,12,2) AS INTEGER)>=17",
        }
        rows = await self.store.rows(
            "SELECT id,start_at,end_at FROM demo_slots "
            "WHERE tenant_id=? AND status='available' AND substr(start_at,1,10)=? "
            + hours.get(preference, "") + " ORDER BY start_at LIMIT 100",
            (ctx.tenant_id, requested.isoformat()),
        )
        def matching(row):
            start = datetime.fromisoformat(row["start_at"])
            return start.astimezone(timezone.utc) > datetime.now(timezone.utc)

        slots = [row for row in rows if matching(row)][:8]
        if ctx.state is not None:
            ctx.state["offered_slots"] = [row["id"] for row in slots]
            ctx.state["offered_slot_details"] = slots
        return {"slots": slots}

    async def validate_schedule(self, ctx, args):
        state = ctx.state or {}
        if args["lead_id"] != state.get("lead_id") or args["slot_id"] not in state.get("offered_slots", []):
            raise SalesError("selection_required")
        lead = await self.store.one(
            "SELECT name FROM leads WHERE tenant_id=? AND id=?", (ctx.tenant_id, args["lead_id"]),
        )
        slot = await self.store.one(
            "SELECT start_at FROM demo_slots WHERE tenant_id=? AND id=? AND status='available'",
            (ctx.tenant_id, args["slot_id"]),
        )
        if not lead or not slot or datetime.fromisoformat(slot["start_at"]) <= datetime.now(timezone.utc):
            raise SalesError("slot_unavailable")
        start = datetime.fromisoformat(slot["start_at"])
        clock = f"{start.hour % 12 or 12}:{start.minute:02} {'AM' if start.hour < 12 else 'PM'}"
        return f"Should I book the demo for {lead['name']} on {start:%A, %d %B %Y} at {clock}?"

    async def validate_followup(self, ctx, args):
        if args["lead_id"] != (ctx.state or {}).get("lead_id"):
            raise SalesError("selection_required")
        if not await self.store.one(
            "SELECT id FROM leads WHERE tenant_id=? AND id=?", (ctx.tenant_id, args["lead_id"]),
        ):
            raise SalesError("lead_not_found")
        return f"Should I save this follow-up for the lead: {args['note']}?"

    async def schedule_demo(self, tenant_id, call_id, args, action_id):
        booking_id, now = uuid4().hex, time.time()
        async with self.store.lock:
            try:
                await self.store.db.execute("BEGIN IMMEDIATE")
                lead = await self.store.db.execute(
                    "SELECT id FROM leads WHERE tenant_id=? AND id=?", (tenant_id, args["lead_id"]),
                )
                if not await lead.fetchone():
                    await self.store.db.rollback()
                    return {"ok": False, "error_code": "lead_not_found"}
                slot_time = await self.store.db.execute(
                    "SELECT start_at FROM demo_slots WHERE tenant_id=? AND id=?",
                    (tenant_id, args["slot_id"]),
                )
                slot_row = await slot_time.fetchone()
                if not slot_row or datetime.fromisoformat(slot_row["start_at"]) <= datetime.now(timezone.utc):
                    await self.store.db.rollback()
                    return {"ok": False, "error_code": "slot_unavailable"}
                cursor = await self.store.db.execute(
                    "UPDATE demo_slots SET status='booked' "
                    "WHERE id=? AND tenant_id=? AND status='available'",
                    (args["slot_id"], tenant_id),
                )
                if cursor.rowcount != 1:
                    await self.store.db.rollback()
                    return {"ok": False, "error_code": "slot_unavailable"}
                await self.store.db.execute(
                    "INSERT INTO demo_bookings VALUES (?,?,?,?,?,?,?)",
                    (booking_id, tenant_id, args["lead_id"], args["slot_id"], call_id, "booked", now),
                )
                await self.store.db.commit()
            except Exception:
                await self.store.db.rollback()
                raise
        return {"ok": True, "booking_id": booking_id, "status": "booked"}

    async def create_followup(self, tenant_id, call_id, args, action_id):
        followup_id = uuid4().hex
        async with self.store.lock:
            try:
                await self.store.db.execute("BEGIN IMMEDIATE")
                lead = await self.store.db.execute(
                    "SELECT id FROM leads WHERE tenant_id=? AND id=?", (tenant_id, args["lead_id"]),
                )
                if not await lead.fetchone():
                    await self.store.db.rollback()
                    return {"ok": False, "error_code": "lead_not_found"}
                cursor = await self.store.db.execute(
                    "INSERT INTO followups VALUES (?,?,?,?,?,?,?)",
                    (followup_id, tenant_id, args["lead_id"], call_id, args["note"], "open", time.time()),
                )
                if cursor.rowcount != 1:
                    raise SalesError("lead_not_found")
                await self.store.db.commit()
            except Exception:
                await self.store.db.rollback()
                raise
        return {"ok": True, "followup_id": followup_id, "status": "open"}


def register_sales_tools(registry, sales):
    identifier = {"type": "string", "minLength": 1, "maxLength": 80}
    uid = {"type": "string", "pattern": "^[0-9a-f]{32}$"}
    registry.register(ToolDefinition(
        "lookup_lead", "Find an existing lead for this tenant by exact caller identifier. Ask for it if unknown.",
        {"type": "object", "properties": {"identifier": identifier}, "additionalProperties": False},
        "read", "local", registry.timeout_ms, handler=sales.lookup_lead,
    ))
    registry.register(ToolDefinition(
        "check_demo_slots", "Return available demo slots on a specified ISO date for this tenant.",
        {"type": "object", "properties": {
            "date": {"type": "string", "format": "date", "pattern": "^\\d{4}-\\d{2}-\\d{2}$"},
            "time_preference": {"enum": ["any", "morning", "afternoon", "evening"]},
        }, "required": ["date"], "additionalProperties": False},
        "read", "local", registry.timeout_ms, handler=sales.check_demo_slots,
    ))
    registry.register(ToolDefinition(
        "schedule_demo", "Book a previously offered slot for a resolved lead. Requires explicit confirmation.",
        {"type": "object", "properties": {"lead_id": uid, "slot_id": uid},
         "required": ["lead_id", "slot_id"], "additionalProperties": False},
        "write", "local", registry.timeout_ms, confirmation_required=True,
        stage_validator=sales.validate_schedule,
    ))
    registry.register(ToolDefinition(
        "create_followup", "Save a bounded follow-up note for a resolved lead. Requires explicit confirmation.",
        {"type": "object", "properties": {"lead_id": uid,
         "note": {"type": "string", "minLength": 1, "maxLength": 240}},
         "required": ["lead_id", "note"], "additionalProperties": False},
        "write", "local", registry.timeout_ms, confirmation_required=True,
        stage_validator=sales.validate_followup,
    ))
    registry.actions.register_local_write("schedule_demo", sales.schedule_demo)
    registry.actions.register_local_write("create_followup", sales.create_followup)
