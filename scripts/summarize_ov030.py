"""Recompute OV-030 figures from retained synthetic case records."""

import argparse
import asyncio
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.evaluate_agent_tools import evaluate as evaluate_ov011b
from scripts.evaluate_agent_workflows import OUTPUT as WORKFLOW_OUTPUT
from scripts.evaluate_live_agent_selection import OUTPUT as LIVE_OUTPUT
from scripts.evaluate_live_agent_selection import ROOT, percentile, summarize

OUTPUT = ROOT / "data/research/ov030_summary.json"


async def build_summary(live_path=LIVE_OUTPUT):
    live = json.loads(Path(live_path).read_text(encoding="utf-8"))
    workflows = json.loads(WORKFLOW_OUTPUT.read_text(encoding="utf-8"))
    prior = await evaluate_ov011b()
    metrics = prior["metrics"]
    if not (prior["scenario_count"] == 25 and metrics["task_completion_rate"] == 1
            and metrics["committed_action_count"] == 4
            and metrics["confirmation_compliance_rate"] == 1
            and metrics["unsafe_commit_count"] == 0
            and metrics["duplicate_execution_count"] == 0):
        raise RuntimeError("OV-011B safety invariant regression")
    tool_times = [value for case in prior["cases"] for value in case["tool_duration_ms"]]
    action_times = [value for case in prior["cases"] for value in case["action_duration_ms"]]
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dataset_size": live["dataset_size"],
        "dataset_categories": dict(Counter(row["category"] for row in live["records"] if row["pass"] == 1)),
        "model": live["model"], "provider": live["provider"],
        "live_model": summarize(live["records"]),
        "deterministic_orchestration": {
            "scenario_count": prior["scenario_count"],
            "deterministic_task_outcome_rate": metrics["task_completion_rate"],
            "confirmation_compliance_rate": metrics["confirmation_compliance_rate"],
            "unsafe_commit_count": metrics["unsafe_commit_count"],
            "duplicate_booking_count": metrics["duplicate_execution_count"],
            "read_tool_success_rate": metrics["read_tool_success_rate"],
            "confirmed_write_success_rate": metrics["write_tool_success_rate"],
            "committed_action_count": metrics["committed_action_count"],
            "server_tool_execution_latency_ms_p50": percentile(tool_times, 0.5),
            "server_tool_execution_latency_ms_p95": percentile(tool_times, 0.95) if len(tool_times) >= 20 else None,
            "server_tool_execution_samples": len(tool_times),
            "confirmed_action_execution_latency_ms_p50": percentile(action_times, 0.5),
            "confirmed_action_execution_latency_ms_p95": percentile(action_times, 0.95) if len(action_times) >= 20 else None,
            "confirmed_action_execution_samples": len(action_times),
        },
        "scripted_workflows": workflows["summary"],
        "tool_assisted_response_latency_ms": None,
        "latency_boundary": "Server-side only; no PSTN transit or acoustic mouth-to-ear measurement",
    }
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", type=Path, default=LIVE_OUTPUT)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    result = asyncio.run(build_summary(args.live))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
