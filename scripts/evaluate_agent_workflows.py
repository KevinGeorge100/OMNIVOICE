"""Seven synthetic multi-step sales workflows through the existing action engine."""

import asyncio
import json
import sys
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from omnivoice.actions import ActionEngine  # noqa: E402
from omnivoice.sales import SalesService, register_sales_tools  # noqa: E402
from omnivoice.store import Store  # noqa: E402
from omnivoice.tools import ToolContext, ToolRegistry  # noqa: E402
from scripts.evaluate_agent_tools import CASES, run_case  # noqa: E402

OUTPUT = ROOT / "data/research/ov030_workflow_results.json"
FLOW_IDS = (
    "booking_positive", "booking_negative", "booking_ambiguous", "booking_stale",
    "booking_race", "followup_positive", "booking_duplicate",
    "stale_to_alternative",
)
EXPECTED_SEQUENCES = {
    "booking_positive": ["lookup_lead", "check_demo_slots", "schedule_demo"],
    "booking_negative": ["lookup_lead", "check_demo_slots", "schedule_demo"],
    "booking_ambiguous": ["lookup_lead", "check_demo_slots", "schedule_demo"],
    "booking_stale": ["lookup_lead", "check_demo_slots", "schedule_demo"],
    "booking_race": ["lookup_lead", "check_demo_slots", "schedule_demo", "schedule_demo"],
    "followup_positive": ["lookup_lead", "create_followup"],
    "booking_duplicate": ["lookup_lead", "check_demo_slots", "schedule_demo"],
    "stale_to_alternative": ["lookup_lead", "check_demo_slots", "schedule_demo",
                             "check_demo_slots", "schedule_demo"],
}


def score_workflows(records):
    return {
        "flow_count": len(records),
        "expected_outcome_count": sum(row["task_completed"] for row in records),
        "correct_tool_sequence_count": sum(row["correct_tool_sequence"] for row in records),
        "unsafe_write_count": sum(row.get("unsafe_commits", 0) for row in records),
        "duplicate_write_count": sum(row.get("duplicate_executions", 0) for row in records),
        "safe_failure_count": sum(row["flow_id"] in {"booking_negative", "booking_ambiguous", "booking_stale"}
                                  and row["task_completed"] for row in records),
        "recovery_after_safe_failure_rate": (
            sum(row.get("recovery_success", False) for row in records)
            / sum(row.get("recovery_attempt", False) for row in records)
            if any(row.get("recovery_attempt", False) for row in records) else None
        ),
        "recovery_attempt_count": sum(row.get("recovery_attempt", False) for row in records),
        "recovery_success_count": sum(row.get("recovery_success", False) for row in records),
        "failure_categories": dict(Counter(row.get("failure_type") for row in records if row.get("failure_type"))),
    }


async def run_recovery(directory):
    """After a stale booking fails, re-read and confirm one fresh alternative."""
    store = Store(directory / "stale_to_alternative.db")
    await store.open()
    try:
        tenant = (await store.create_tenant({"name": "Synthetic Recovery", "language": "en-IN"}))["id"]
        sales = SalesService(store)
        actions = ActionEngine(store, None)
        registry = ToolRegistry(store, actions)
        register_sales_tools(registry, sales)
        lead = await sales.add_lead(tenant, "Synthetic Lead", "DEMO-RECOVERY-001")
        stale = await sales.add_slot(tenant, "2030-03-08T16:00:00+05:30", "2030-03-08T16:30:00+05:30")
        fresh = await sales.add_slot(tenant, "2030-03-08T17:00:00+05:30", "2030-03-08T17:30:00+05:30")
        ctx = ToolContext(tenant, "recovery-call", {})
        observed = []

        async def invoke(name, args):
            result = await registry.invoke(ctx, name, args)
            observed.append(name)
            return result

        assert (await invoke("lookup_lead", {"identifier": "DEMO-RECOVERY-001"})).success
        assert (await invoke("check_demo_slots", {"date": "2030-03-08"})).success
        first = await invoke("schedule_demo", {"lead_id": lead, "slot_id": stale})
        assert first.success
        assert await actions.arm(first.data["action_id"], ctx.call_id) == 1
        await store.execute("UPDATE demo_slots SET status='booked' WHERE id=?", (stale,))
        rejected = await actions.confirm(tenant, ctx.call_id, "yes", True, ["yes"])
        assert rejected["status"] == "failed"
        offered = await invoke("check_demo_slots", {"date": "2030-03-08"})
        assert [item["id"] for item in offered.data["slots"]] == [fresh]
        second = await invoke("schedule_demo", {"lead_id": lead, "slot_id": fresh})
        assert second.success
        assert await actions.arm(second.data["action_id"], ctx.call_id) == 1
        committed = await actions.confirm(tenant, ctx.call_id, "yes", True, ["yes"])
        bookings = await store.rows("SELECT slot_id FROM demo_bookings")
        assert committed["status"] == "committed" and [row["slot_id"] for row in bookings] == [fresh]
        return {"flow_id": "stale_to_alternative", "task_completed": True,
                "observed_tools": observed, "correct_tool_sequence": observed == EXPECTED_SEQUENCES["stale_to_alternative"],
                "unsafe_commits": 0, "duplicate_executions": 0, "committed_actions": 1,
                "confirmed_write_count": 1, "recovery_attempt": True, "recovery_success": True,
                "tool_duration_ms": [], "action_duration_ms": [committed["duration_ms"]]}
    finally:
        await store.close()


async def evaluate():
    lookup = {case[0]: case for case in CASES}
    rows = []
    with tempfile.TemporaryDirectory() as directory:
        for flow_id in FLOW_IDS:
            try:
                if flow_id == "stale_to_alternative":
                    row = await run_recovery(Path(directory))
                else:
                    record = await run_case(lookup[flow_id], Path(directory))
                    row = {
                        "flow_id": flow_id, "task_completed": record["task_completed"],
                        "observed_tools": record["observed_tools"],
                        "correct_tool_sequence": record["observed_tools"] == EXPECTED_SEQUENCES[flow_id],
                        "unsafe_commits": record["unsafe_commits"],
                        "duplicate_executions": record["duplicate_executions"],
                        "committed_actions": record["committed_actions"],
                        "confirmed_write_count": record["confirmed_write_count"],
                        "tool_duration_ms": record["tool_duration_ms"],
                        "action_duration_ms": record["action_duration_ms"],
                    }
            except Exception as error:
                row = {"flow_id": flow_id, "task_completed": False,
                       "correct_tool_sequence": False, "failure_type": type(error).__name__}
            rows.append(row)
    return {"generated_at": datetime.now(timezone.utc).isoformat(),
            "method": "scripted multi-step ToolRegistry/ActionEngine/SQLite; no model/PSTN",
            "workflows": rows, "summary": score_workflows(rows)}


if __name__ == "__main__":
    result = asyncio.run(evaluate())
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], indent=2))
    if result["summary"]["expected_outcome_count"] != len(FLOW_IDS):
        raise SystemExit(1)
