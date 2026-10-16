"""OV-030 synthetic, selection-only Groq evaluation; never invokes a tool."""

import argparse
import asyncio
import json
import math
import tempfile
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import httpx
from jsonschema import Draft202012Validator

from omnivoice.actions import ActionEngine
from omnivoice.config import Settings
from omnivoice.dialogue import build_system_prompt
from omnivoice.providers import Groq
from omnivoice.research_observability import ResearchObserver
from omnivoice.sales import SalesService, register_sales_tools
from omnivoice.store import Store
from omnivoice.tools import ToolRegistry

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "data/research/agent_eval_cases.json"
OUTPUT = ROOT / "data/research/ov030_live_selection_results.json"
TOOLS = ("lookup_lead", "check_demo_slots", "schedule_demo", "create_followup")
REPEAT_IDS = (
    "no_tool_01", "lookup_lead_01", "check_demo_slots_01", "schedule_demo_01",
    "create_followup_01", "ambiguous_01", "adversarial_01",
)


def load_cases(path=CASES):
    cases = json.loads(Path(path).read_text(encoding="utf-8"))
    required = {"case_id", "category", "user_utterance", "expected_tool", "expected_tool_required",
                "expected_side_effect", "confirmation_required", "expected_outcome"}
    ids = [case["case_id"] for case in cases]
    if len(cases) < 60 or len(ids) != len(set(ids)):
        raise ValueError("OV-030 requires at least 60 unique cases")
    for case in cases:
        if not required.issubset(case) or case["expected_tool"] not in (*TOOLS, None):
            raise ValueError("Invalid case schema or tool")
        if case["expected_tool_required"] is not (case["expected_tool"] is not None):
            raise ValueError("Inconsistent expected tool decision")
        if case["confirmation_required"] is not (case["expected_side_effect"] == "write"):
            raise ValueError("Inconsistent confirmation label")
    return cases


def parse_selection(deltas):
    calls = {}
    for delta in deltas:
        for item in delta.get("tool_calls", []):
            entry = calls.setdefault(item["index"], {"name": "", "arguments": ""})
            function = item.get("function") or {}
            entry["name"] += function.get("name") or ""
            entry["arguments"] += function.get("arguments") or ""
    if not calls:
        return "NO_TOOL", None, None
    if len(calls) != 1:
        return "MULTIPLE", None, "multiple_calls"
    call = next(iter(calls.values()))
    try:
        arguments = json.loads(call["arguments"])
        if not isinstance(arguments, dict):
            raise ValueError("not an object")
    except (ValueError, TypeError):
        return call["name"] or "INVALID/UNKNOWN", None, "model_output_parse_failure"
    return call["name"] or "INVALID/UNKNOWN", arguments, None


def score_case(case, predicted, arguments, parse_error, schemas, fixture):
    expected = case["expected_tool"] or "NO_TOOL"
    failure = parse_error
    valid_args = None
    if predicted not in (*TOOLS, "NO_TOOL", "MULTIPLE"):
        failure = "hallucinated_tool"
    elif predicted in TOOLS:
        try:
            Draft202012Validator(schemas[predicted]).validate(arguments)
            valid_args = True
        except Exception:  # malformed model output is an evaluation result, not an execution error
            valid_args = False
            failure = failure or "invalid_arguments"
        if valid_args:
            if predicted == "lookup_lead":
                valid_args = arguments.get("identifier") == "DEMO-ALPHA-001"
            elif predicted == "check_demo_slots":
                valid_args = arguments.get("date") == "2030-03-08"
            elif predicted == "schedule_demo":
                valid_args = arguments == {"lead_id": fixture["lead_id"], "slot_id": fixture["slot_id"]}
            elif predicted == "create_followup":
                valid_args = arguments.get("lead_id") == fixture["lead_id"]
            if not valid_args:
                failure = "invalid_arguments"
    routing_correct = predicted == expected
    if not routing_correct and failure is None:
        failure = ("unnecessary_tool" if expected == "NO_TOOL" else
                   "missed_tool" if predicted == "NO_TOOL" else "wrong_tool")
    if predicted == "MULTIPLE":
        failure = "multiple_calls"
    return {
        "predicted": predicted, "routing_correct": routing_correct,
        "arguments_valid": valid_args, "failure_type": failure,
        "proposal_correct": routing_correct and (valid_args is True if expected in TOOLS else True),
        "write_execution_attempts": 0,  # selection evaluator never calls ToolRegistry.invoke
    }


def percentile(values, q):
    if not values:
        return None
    ordered = sorted(values)
    index = (len(ordered) - 1) * q
    lower, upper = math.floor(index), math.ceil(index)
    return round(ordered[lower] + (ordered[upper] - ordered[lower]) * (index - lower), 2)


def summarize(records):
    full = [row for row in records if row["pass"] == 1]
    answered = [row for row in full if row["status"] == "ok"]
    required = [row for row in full if row["expected"] != "NO_TOOL"]
    no_tool = [row for row in full if row["expected"] == "NO_TOOL"]
    proposals = [row for row in full if row["predicted"] in TOOLS]
    read_proposals = [row for row in full if row["predicted"] in {"lookup_lead", "check_demo_slots"}]
    writes = [row for row in full if row["expected"] in {"schedule_demo", "create_followup"}]

    def ratio(rows, check):
        return round(sum(check(row) for row in rows) / len(rows), 4) if rows else None

    matrix = {name: dict(Counter(row["predicted"] for row in full if row["expected"] == name))
              for name in ("NO_TOOL", *TOOLS)}
    runs = {}
    for number in sorted({row["pass"] for row in records}):
        group = [row for row in records if row["pass"] == number]
        runs[str(number)] = {"cases": len(group), "routing_accuracy": ratio(group, lambda r: r["routing_correct"])}
    by_id = {}
    for row in records:
        by_id.setdefault(row["case_id"], []).append(row["predicted"])
    repeated = {key: values for key, values in by_id.items() if len(values) > 1}
    times = [row["selection_latency_ms"] for row in answered if row["selection_latency_ms"] is not None]
    return {
        "full_pass_cases": len(full), "full_pass_model_responses": len(answered),
        "provider_failures": len(full) - len(answered), "repeat_observations": len(records) - len(full),
        "provider_failure_types": dict(Counter(row.get("provider_error_type") or "unknown" for row in full
                                               if row["status"] != "ok")),
        "denominators": {"tool_required_decision": len(full), "no_tool": len(no_tool),
                         "tool_selection": len(required), "overall_routing": len(full),
                         "hallucinated_tool": len(full), "argument_proposals": len(proposals),
                         "read_argument_proposals": len(read_proposals), "write_cases": len(writes)},
        "tool_required_accuracy": ratio(full, lambda r: (r["predicted"] != "NO_TOOL") == (r["expected"] != "NO_TOOL") and r["predicted"] != "UNAVAILABLE"),
        "no_tool_accuracy": ratio(no_tool, lambda r: r["predicted"] == "NO_TOOL"),
        "tool_selection_accuracy": ratio(required, lambda r: r["routing_correct"]),
        "overall_routing_accuracy": ratio(full, lambda r: r["routing_correct"]),
        "answered_routing_accuracy": ratio(answered, lambda r: r["routing_correct"]),
        "hallucinated_tool_rate": ratio(full, lambda r: r["failure_type"] == "hallucinated_tool"),
        "invalid_argument_rate": ratio(proposals, lambda r: r["arguments_valid"] is False),
        "read_argument_valid_rate": ratio(read_proposals, lambda r: r["arguments_valid"] is True),
        "write_proposal_safety_rate": ratio(writes, lambda r: r["proposal_correct"]),
        "accidental_write_execution_attempts": sum(row["write_execution_attempts"] for row in records),
        "confusion_matrix": matrix,
        "failure_categories": dict(Counter(row["failure_type"] for row in full if row["failure_type"])),
        "errors": [{"case_id": row["case_id"], "category": row["category"],
                    "expected": row["expected"], "predicted": row["predicted"],
                    "failure_type": row["failure_type"]} for row in full if row["failure_type"]],
        "per_run": runs,
        "repeat_consistency": ratio(list(repeated.values()), lambda values: len(set(values)) == 1),
        "repeat_case_count": len(repeated),
        "llm_selection_latency_ms_p50": percentile(times, 0.5),
        "llm_selection_latency_ms_p95": percentile(times, 0.95) if len(times) >= 20 else None,
        "llm_selection_latency_sample_count": len(times),
        "tool_assisted_response_latency_ms": None,
        "token_cost_per_case": None,
    }


def checkpoint(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


async def evaluate(output=OUTPUT, *, langfuse=False, delay=8.0):
    settings = Settings()
    if settings.groq_model != "openai/gpt-oss-20b":
        raise ValueError("OV-030 requires the configured openai/gpt-oss-20b model")
    if not settings.groq_api_key.get_secret_value():
        raise RuntimeError("Groq credential is not configured")
    cases = load_cases()
    output = Path(output)
    result = json.loads(output.read_text(encoding="utf-8")) if output.exists() else {
        "generated_at": datetime.now(timezone.utc).isoformat(), "provider": "Groq",
        "model": settings.groq_model, "method": "live model tool proposal only; no tool invocation",
        "dataset_size": len(cases), "records": [],
    }
    if result["model"] != settings.groq_model or result["dataset_size"] != len(cases):
        raise ValueError("Existing checkpoint is incompatible")
    completed = {(row["pass"], row["case_id"]) for row in result["records"]}
    observer = ResearchObserver.from_settings(settings, explicit=True) if langfuse else ResearchObserver()
    with tempfile.TemporaryDirectory() as directory:
        store = Store(Path(directory) / "sales.db")
        await store.open()
        try:
            tenant = (await store.create_tenant({"name": "Synthetic Evaluation", "language": "en-IN"}))["id"]
            sales = SalesService(store)
            lead_id = await sales.add_lead(tenant, "Synthetic Lead", "DEMO-ALPHA-001")
            slot_id = await sales.add_slot(tenant, "2030-03-08T16:00:00+05:30", "2030-03-08T16:30:00+05:30")
            fixture = {"lead_id": lead_id, "slot_id": slot_id}
            async with httpx.AsyncClient(trust_env=False) as http:
                registry = ToolRegistry(store, ActionEngine(store, http))
                register_sales_tools(registry, sales)
                tools = await registry.llm_tools(tenant)
                schemas = {tool["name"]: tool["parameters"] for tool in tools}
                llm = Groq(settings, http)
                plan = [(1, case) for case in cases]
                plan += [(number, case) for number in (2, 3) for case in cases
                         if case["case_id"] in REPEAT_IDS]
                for number, case in plan:
                    key = (number, case["case_id"])
                    if key in completed:
                        continue
                    state = ({"lead_id": lead_id, "lead_name": "Synthetic Lead",
                              "offered_slots": [slot_id], "offered_slot_details": [{
                                  "id": slot_id, "start_at": "2030-03-08T16:00:00+05:30",
                                  "end_at": "2030-03-08T16:30:00+05:30"}]}
                             if case["category"] == "SCHEDULE_DEMO" else
                             {"lead_id": lead_id, "lead_name": "Synthetic Lead"}
                             if case["category"] == "CREATE_FOLLOWUP" else {})
                    context = ([{"title": "Product", "text": "OmniVoice is an enterprise telephony voice-agent platform for inbound and outbound calls."}]
                               if case["category"] == "NO_TOOL" else [])
                    prompt = build_system_prompt(
                        {"language": "en-IN", "instructions": "Offer sales demos."},
                        context, tools, caller_text=case["user_utterance"], sales_state=state,
                    )
                    started = time.perf_counter()
                    status, deltas, error = "ok", [], None
                    try:
                        async for delta in llm.stream([
                            {"role": "system", "content": prompt},
                            {"role": "user", "content": case["user_utterance"]},
                        ], tools):
                            deltas.append(delta)
                        predicted, arguments, parse_error = parse_selection(deltas)
                        scored = score_case(case, predicted, arguments, parse_error, schemas, fixture)
                    except Exception as exc:
                        status, error = "provider_error", type(exc).__name__
                        scored = {"predicted": "UNAVAILABLE", "routing_correct": False,
                                  "arguments_valid": None, "failure_type": "provider_error",
                                  "proposal_correct": False, "write_execution_attempts": 0}
                    row = {"pass": number, "case_id": case["case_id"], "category": case["category"],
                           "expected": case["expected_tool"] or "NO_TOOL", "status": status,
                           "provider_error_type": error,
                           "selection_latency_ms": round((time.perf_counter() - started) * 1000, 2), **scored}
                    result["records"].append(row)
                    completed.add(key)
                    result["summary"] = summarize(result["records"])
                    checkpoint(output, result)
                    observer.export_selection(row, settings.groq_model)
                    print(f"pass={number} case={case['case_id']} predicted={row['predicted']} status={status}", flush=True)
                    if delay:
                        await asyncio.sleep(delay)
                write_activity = {
                    "staged_actions": len(await store.rows("SELECT id FROM actions")),
                    "bookings": len(await store.rows("SELECT id FROM demo_bookings")),
                    "followups": len(await store.rows("SELECT id FROM followups")),
                }
                result["selection_write_boundary"] = write_activity
                if any(write_activity.values()):
                    raise RuntimeError("Selection-only evaluation unexpectedly changed business state")
                result["summary"] = summarize(result["records"])
                checkpoint(output, result)
        finally:
            await observer.close()
            await store.close()
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--langfuse", action="store_true", help="Opt-in sanitized research export")
    parser.add_argument("--delay", type=float, default=8.0)
    parser.add_argument("--output", type=Path, default=OUTPUT, help="Checkpoint/output JSON for an independent run")
    args = parser.parse_args()
    print(json.dumps(asyncio.run(evaluate(args.output, langfuse=args.langfuse, delay=args.delay))["summary"], indent=2))
