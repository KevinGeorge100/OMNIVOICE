"""Offline OV-011B orchestration evaluation; no live model or PSTN calls."""

import asyncio
import json
import statistics
import tempfile
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from omnivoice.actions import ActionEngine
from omnivoice.sales import SalesService, register_sales_tools
from omnivoice.store import Store
from omnivoice.tools import ToolContext, ToolRegistry

ROOT = Path(__file__).resolve().parents[1]
CASES = [
    ("faq_product", "FAQ_ONLY", None, "none", False),
    ("faq_policy", "FAQ_ONLY", None, "none", False),
    ("lead_known", "LEAD_LOOKUP", "lookup_lead", "read", False),
    ("lead_unknown", "LEAD_LOOKUP", "lookup_lead", "read", False),
    ("lead_cross_tenant", "CROSS_TENANT", "lookup_lead", "read", False),
    ("lead_no_identity", "LEAD_LOOKUP", "lookup_lead", "read", False),
    ("slots_afternoon", "SLOT_SEARCH", "check_demo_slots", "read", False),
    ("slots_morning", "SLOT_SEARCH", "check_demo_slots", "read", False),
    ("slots_other_date", "SLOT_SEARCH", "check_demo_slots", "read", False),
    ("slots_occupied", "SLOT_SEARCH", "check_demo_slots", "read", False),
    ("slots_cross_tenant", "CROSS_TENANT", "check_demo_slots", "read", False),
    ("booking_positive", "BOOKING", "schedule_demo", "write", True),
    ("booking_unarmed", "INVALID_WRITE_WITHOUT_CONFIRMATION", "schedule_demo", "write", True),
    ("booking_negative", "NEGATIVE_CONFIRMATION", "schedule_demo", "write", True),
    ("booking_ambiguous", "AMBIGUOUS_CONFIRMATION", "schedule_demo", "write", True),
    ("booking_duplicate", "DUPLICATE_CONFIRMATION", "schedule_demo", "write", True),
    ("booking_stale", "STALE_SLOT", "schedule_demo", "write", True),
    ("booking_foreign_lead", "CROSS_TENANT", "schedule_demo", "write", False),
    ("booking_foreign_slot", "CROSS_TENANT", "schedule_demo", "write", False),
    ("booking_race", "STALE_SLOT", "schedule_demo", "write", True),
    ("followup_positive", "FOLLOWUP", "create_followup", "write", True),
    ("followup_negative", "NEGATIVE_CONFIRMATION", "create_followup", "write", True),
    ("followup_oversize", "INVALID_ARGUMENT", "create_followup", "write", False),
    ("hallucinated_tool", "HALLUCINATED_TOOL", "imaginary_tool", "none", False),
    ("invalid_date", "INVALID_ARGUMENT", "check_demo_slots", "read", False),
]


async def run_case(case, directory):
    case_id, category, expected_tool, effect, confirmation_expected = case
    store = Store(directory / f"{case_id}.db")
    await store.open()
    tool_results, action_duration_ms, action_end_to_end_ms = [], [], []
    confirmed_write_count = 0
    unsafe_commits = 0
    started = time.perf_counter()
    try:
        a = (await store.create_tenant({"name": "A", "language": "en-IN"}))["id"]
        b = (await store.create_tenant({"name": "B", "language": "en-IN"}))["id"]
        sales = SalesService(store)
        actions = ActionEngine(store, None)
        registry = ToolRegistry(store, actions)
        register_sales_tools(registry, sales)
        lead = await sales.add_lead(a, "Arun", "+910000000001")
        foreign_lead = await sales.add_lead(b, "Bina", "+910000000002")
        slot = await sales.add_slot(a, "2030-03-08T16:00:00+05:30", "2030-03-08T16:30:00+05:30")
        occupied = await sales.add_slot(
            a, "2030-03-08T14:30:00+05:30", "2030-03-08T15:00:00+05:30", status="booked",
        )
        foreign_slot = await sales.add_slot(b, "2030-03-08T16:00:00+05:30", "2030-03-08T16:30:00+05:30")
        ctx = ToolContext(a, case_id, {})

        async def invoke(name, args, context=ctx):
            result = await registry.invoke(context, name, args)
            tool_results.append(result)
            return result

        if category == "FAQ_ONLY":
            from omnivoice.rag import Knowledge

            question = "What does your product do?" if case_id == "faq_product" else "What is your policy?"
            await store.add_knowledge(a, "faq", question, "Verified business answer.", approved=True)
            knowledge = Knowledge(store)
            await knowledge.refresh(a)
            answer, _, _ = await knowledge.fast_answer(a, question)
            assert answer == "Verified business answer."
        elif case_id.startswith("lead_"):
            identifier = {
                "lead_known": "+910000000001", "lead_unknown": "unknown",
                "lead_cross_tenant": "+910000000002",
            }.get(case_id)
            result = await invoke("lookup_lead", {"identifier": identifier} if identifier else {})
            assert result.success
            assert result.data["found"] is (case_id == "lead_known")
        elif case_id.startswith("slots_"):
            preference = "morning" if case_id == "slots_morning" else "afternoon"
            requested = "2030-03-09" if case_id == "slots_other_date" else "2030-03-08"
            result = await invoke("check_demo_slots", {"date": requested, "time_preference": preference})
            assert result.success
            ids = [item["id"] for item in result.data["slots"]]
            assert ids == ([slot] if case_id in {"slots_afternoon", "slots_occupied", "slots_cross_tenant"} else [])
            assert occupied not in ids and foreign_slot not in ids
        elif case_id.startswith("booking_") or case_id.startswith("followup_"):
            lookup = await invoke("lookup_lead", {"identifier": "+910000000001"})
            assert lookup.success
            if case_id.startswith("booking_"):
                available = await invoke("check_demo_slots", {"date": "2030-03-08"})
                assert slot in [item["id"] for item in available.data["slots"]]
                args = {"lead_id": foreign_lead if case_id == "booking_foreign_lead" else lead,
                        "slot_id": foreign_slot if case_id == "booking_foreign_slot" else slot}
                name = "schedule_demo"
            else:
                args = {"lead_id": lead, "note": "x" * 241 if case_id == "followup_oversize" else "Send brochure"}
                name = "create_followup"
            staged = await invoke(name, args)
            invalid = case_id in {"booking_foreign_lead", "booking_foreign_slot", "followup_oversize"}
            assert staged.success is not invalid
            if not invalid:
                action_id = staged.data["action_id"]
                if case_id != "booking_unarmed":
                    assert await actions.arm(action_id, case_id) == 1
                if case_id == "booking_stale":
                    await store.execute("UPDATE demo_slots SET status='booked' WHERE id=?", (slot,))
                if case_id == "booking_race":
                    other = ToolContext(a, "racing-call", dict(ctx.state))
                    competing = await invoke(name, args, other)
                    assert competing.success
                    await actions.arm(competing.data["action_id"], "racing-call")
                    winner = await actions.confirm(a, "racing-call", "yes", True, ["yes"])
                    action_duration_ms.append(winner["duration_ms"])
                    action_end_to_end_ms.append(winner["action_end_to_end_ms"])
                    assert winner["status"] == "committed"
                    confirmed_write_count += 1
                phrase = ("no" if case_id in {"booking_negative", "followup_negative"} else
                          "maybe" if case_id == "booking_ambiguous" else "yes")
                committed = await actions.confirm(a, case_id, phrase, True, ["yes"])
                if committed:
                    action_duration_ms.append(committed["duration_ms"])
                    action_end_to_end_ms.append(committed["action_end_to_end_ms"])
                    if committed["status"] == "committed":
                        confirmed_write_count += int(phrase == "yes")
                        unsafe_commits += int(phrase != "yes")
                expected_status = "failed" if case_id in {"booking_stale", "booking_race"} else "committed"
                if case_id in {"booking_unarmed", "booking_negative", "booking_ambiguous", "followup_negative"}:
                    assert committed is None
                else:
                    assert committed["status"] == expected_status
                if case_id == "booking_duplicate":
                    assert await actions.confirm(a, case_id, "yes", True, ["yes"]) is None
            bookings = await store.rows("SELECT id FROM demo_bookings")
            followups = await store.rows("SELECT id FROM followups")
            assert len(bookings) == int(case_id in {"booking_positive", "booking_duplicate", "booking_race"})
            assert len(followups) == int(case_id == "followup_positive")
        elif case_id == "hallucinated_tool":
            assert (await invoke("imaginary_tool", {})).error_code == "unauthorized_tool"
        elif case_id == "invalid_date":
            assert (await invoke("check_demo_slots", {"date": "tomorrow"})).error_code == "invalid_arguments"

        actions_rows = await store.rows("SELECT status,tool,created FROM actions")
        bookings = await store.rows("SELECT slot_id FROM demo_bookings")
        return {
            "id": case_id, "category": category, "expected_tool": expected_tool,
            "expected_side_effect": effect, "confirmation_expected": confirmation_expected,
            "expected_task_outcome": "safe_rejection" if category in {
                "CROSS_TENANT", "INVALID_ARGUMENT", "HALLUCINATED_TOOL", "STALE_SLOT",
                "NEGATIVE_CONFIRMATION", "AMBIGUOUS_CONFIRMATION", "INVALID_WRITE_WITHOUT_CONFIRMATION",
            } else "complete",
            "task_completed": True,
            "tool_invocations": len(tool_results),
            "read_successes": sum(r.success for r in tool_results if r.tool_name in {
                "lookup_lead", "check_demo_slots",
            }),
            "read_attempts": sum(r.tool_name in {"lookup_lead", "check_demo_slots"} for r in tool_results),
            "write_successes": sum(row["status"] == "committed" for row in actions_rows),
            "write_attempts": sum(row["status"] in {"committed", "failed", "unknown"} for row in actions_rows),
            "confirmation_required_count": sum(r.confirmation_required for r in tool_results),
            "committed_actions": sum(row["status"] == "committed" for row in actions_rows),
            "confirmed_write_count": confirmed_write_count,
            "unsafe_commits": unsafe_commits,
            "invalid_tool_requests": sum(r.error_code in {"unauthorized_tool", "invalid_arguments"}
                                         for r in tool_results),
            "duplicate_executions": len(bookings) - len({row["slot_id"] for row in bookings}),
            "tool_duration_ms": [round(r.duration_ms, 3) for r in tool_results if r.duration_ms],
            "action_duration_ms": [round(value, 3) for value in action_duration_ms],
            "action_end_to_end_ms": [round(value, 3) for value in action_end_to_end_ms],
            "workflow_duration_ms": round((time.perf_counter() - started) * 1000, 3),
        }
    finally:
        await store.close()


async def evaluate():
    with tempfile.TemporaryDirectory() as directory:
        records = [await run_case(case, Path(directory)) for case in CASES]
    def total(name):
        return sum(row[name] for row in records)
    tool_times = [value for row in records for value in row["tool_duration_ms"]]
    action_times = [value for row in records for value in row["action_duration_ms"]]
    action_e2e_times = [value for row in records for value in row["action_end_to_end_ms"]]
    return {
        "method": "offline scripted orchestration; actual ToolRegistry, ActionEngine and SQLite",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scenario_count": len(records),
        "categories": dict(Counter(row["category"] for row in records)),
        "metrics": {
            "tool_selection_accuracy": None,
            "tool_selection_note": "N/A: no model selected tools in this deterministic harness",
            "tool_invocation_count": total("tool_invocations"),
            "read_tool_success_rate": total("read_successes") / total("read_attempts"),
            "write_tool_success_rate": total("write_successes") / total("write_attempts"),
            "task_completion_rate": sum(row["task_completed"] for row in records) / len(records),
            "confirmation_required_count": total("confirmation_required_count"),
            "confirmation_compliance_rate": (
                total("confirmed_write_count") / total("committed_actions")
                if total("committed_actions") else None
            ),
            "confirmation_compliance_note": "Share of committed actions reached through exact yes confirmation",
            "unsafe_commit_count": total("unsafe_commits"),
            "committed_action_count": total("committed_actions"),
            "duplicate_execution_count": total("duplicate_executions"),
            "invalid_tool_request_count": total("invalid_tool_requests"),
            "server_side_tool_duration_ms_mean": statistics.mean(tool_times) if tool_times else None,
            "confirmed_action_duration_ms_mean": statistics.mean(action_times) if action_times else None,
            "action_end_to_end_duration_ms_mean": (
                statistics.mean(action_e2e_times) if action_e2e_times else None
            ),
            "tool_added_response_latency_ms": None,
            "tool_added_response_latency_note": "N/A: no TTS/STT or model response in offline harness",
        },
        "cases": records,
    }


def write_report(result, output, report):
    output.parent.mkdir(parents=True, exist_ok=True)
    report.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    metrics = result["metrics"]
    failures = [row["id"] for row in result["cases"] if not row["task_completed"]]
    report.write_text(
        "# OV-011B Agent Evaluation\n\n"
        "The offline suite runs labeled scripted intents against the real local ToolRegistry, "
        "ActionEngine and isolated SQLite stores. No Groq or PSTN calls are made. "
        "It extends the baseline architecture; it does not prove global superiority.\n\n"
        f"Scenarios: {result['scenario_count']}\n\n"
        "Category distribution: " + json.dumps(result["categories"], sort_keys=True) + "\n\n"
        "| Metric | Measured value |\n|---|---:|\n"
        + "\n".join(f"| {key} | {value if value is not None else 'N/A'} |"
                    for key, value in metrics.items() if not key.endswith("_note"))
        + "\n\nTool-selection accuracy and tool-added response latency are N/A: this is scripted "
        "orchestration, not a live model or voice timing experiment. Confirmation compliance "
        "measures the share of commits following exact yes confirmation in the scripted cases. "
        "Reported durations are server-side tool/action execution, not mouth-to-ear latency. "
        "The action end-to-end duration includes scripted staging and immediate arming; it does "
        "not represent the time a caller spends confirming.\n\n"
        "Read success includes safe not-found results. Write success is commits per confirmed "
        "write attempt; stale/raced slots are expected safe failures. Task completion means the "
        "labeled expected outcome, including safe rejection, was observed.\n\n"
        "The non-agent baseline answered conversational questions but had no completed sales "
        "tool workflow. The agentic extension adds typed reads, confirmation-gated writes, and "
        "observable business completion. The two are not directly comparable on this fixture.\n\n"
        "The optional live model-selection check is reported separately in "
        "[OV-011B_LIVE_GROQ_SMOKE.md](OV-011B_LIVE_GROQ_SMOKE.md).\n\n"
        "Failure cases: " + (", ".join(failures) if failures else "none") + ".\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    result = asyncio.run(evaluate())
    write_report(
        result, ROOT / "data/research/agent_tool_eval.json",
        ROOT / "docs/research/OV-011B_AGENT_EVALUATION.md",
    )
    print(json.dumps({"scenarios": result["scenario_count"], "metrics": result["metrics"]}, indent=2))
