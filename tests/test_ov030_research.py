"""Deterministic scoring/privacy checks for the synthetic OV-030 research suite."""

import json
import math
import re
from types import SimpleNamespace

import pytest
from pydantic import SecretStr

from omnivoice.research_observability import ResearchObserver
from scripts import evaluate_live_agent_selection as live_eval
from scripts.build_ov030_cases import build_cases
from scripts.evaluate_agent_tools import evaluate as evaluate_ov011b
from scripts.evaluate_agent_workflows import evaluate as evaluate_workflows
from scripts.evaluate_agent_workflows import score_workflows
from scripts.evaluate_live_agent_selection import (
    REPEAT_IDS,
    ROOT,
    load_cases,
    parse_selection,
    score_case,
    summarize,
)


@pytest.fixture
def fixture_data():
    schema = {"type": "object", "properties": {"identifier": {"type": "string"}},
              "additionalProperties": False}
    return {"lookup_lead": schema}, {"lead_id": "a" * 32, "slot_id": "b" * 32}


def test_dataset_schema_uniqueness_and_synthetic_content():
    cases = load_cases()
    assert cases == build_cases()
    assert len(cases) == 76
    assert len({row["case_id"] for row in cases}) == len(cases)
    normalized = [" ".join(re.findall(r"[a-z0-9]+", row["user_utterance"].lower())) for row in cases]
    assert len(set(normalized)) == len(cases)
    assert {row["category"] for row in cases} == {
        "NO_TOOL", "LOOKUP_LEAD", "CHECK_DEMO_SLOTS", "SCHEDULE_DEMO",
        "CREATE_FOLLOWUP", "AMBIGUOUS", "ADVERSARIAL",
    }
    assert set(REPEAT_IDS).issubset({row["case_id"] for row in cases})
    for case in cases:
        text = case["user_utterance"]
        assert not re.search(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b", text)
        assert not re.search(r"(?<!\d)(?:\+91[- ]?)?[6-9]\d{9}(?!\d)", text)
        assert "DEMO-ALPHA-001" in text or case["category"] != "LOOKUP_LEAD"


def test_no_tool_and_correct_selection(fixture_data):
    schemas, fixture = fixture_data
    case = {"expected_tool": None}
    predicted, args, error = parse_selection([{"content": "A brief answer"}])
    assert (predicted, args, error) == ("NO_TOOL", None, None)
    assert score_case(case, predicted, args, error, schemas, fixture)["routing_correct"]
    case["expected_tool"] = "lookup_lead"
    deltas = [{"tool_calls": [{"index": 0, "function": {"name": "lookup_", "arguments": '{"identifier":"'}}]},
              {"tool_calls": [{"index": 0, "function": {"name": "lead", "arguments": 'DEMO-ALPHA-001"}'}}]}]
    predicted, args, error = parse_selection(deltas)
    scored = score_case(case, predicted, args, error, schemas, fixture)
    assert scored["routing_correct"] and scored["arguments_valid"]


def test_hallucinated_tool_and_malformed_arguments(fixture_data):
    schemas, fixture = fixture_data
    case = {"expected_tool": "lookup_lead"}
    hallucinated = score_case(case, "erase_database", {}, None, schemas, fixture)
    assert hallucinated["failure_type"] == "hallucinated_tool"
    predicted, args, error = parse_selection([{"tool_calls": [{"index": 0, "function": {
        "name": "lookup_lead", "arguments": "{bad"}}]}])
    malformed = score_case(case, predicted, args, error, schemas, fixture)
    assert malformed["failure_type"] == "model_output_parse_failure"
    assert malformed["arguments_valid"] is False


def test_metric_denominators_confusion_repeats_and_failures():
    rows = [
        {"pass": 1, "case_id": "a", "category": "NO_TOOL", "expected": "NO_TOOL",
         "predicted": "NO_TOOL", "status": "ok", "routing_correct": True,
         "arguments_valid": None, "proposal_correct": True, "write_execution_attempts": 0,
         "failure_type": None, "selection_latency_ms": 10},
        {"pass": 1, "case_id": "b", "category": "LOOKUP_LEAD", "expected": "lookup_lead",
         "predicted": "UNAVAILABLE", "status": "provider_error", "routing_correct": False,
         "arguments_valid": None, "proposal_correct": False, "write_execution_attempts": 0,
         "failure_type": "provider_error", "selection_latency_ms": 20},
        {"pass": 2, "case_id": "a", "category": "NO_TOOL", "expected": "NO_TOOL",
         "predicted": "NO_TOOL", "status": "ok", "routing_correct": True,
         "arguments_valid": None, "proposal_correct": True, "write_execution_attempts": 0,
         "failure_type": None, "selection_latency_ms": 11},
    ]
    summary = summarize(rows)
    assert summary["overall_routing_accuracy"] == 0.5
    assert summary["tool_selection_accuracy"] == 0
    assert summary["answered_tool_selection_accuracy"] is None
    assert summary["no_tool_accuracy"] == 1
    assert summary["provider_failures"] == 1
    assert summary["confusion_matrix"]["lookup_lead"] == {"UNAVAILABLE": 1}
    assert summary["errors"][0]["case_id"] == "b"
    assert summary["repeat_consistency"] == 1
    assert summary["llm_selection_latency_ms_p95"] is None
    assert summary["tool_assisted_response_latency_ms"] is None


def test_persisted_research_counts_and_same_run_latency_evidence():
    research = ROOT / "data/research"
    live = json.loads((research / "ov030_live_selection_results.json").read_text(encoding="utf-8"))
    summary = json.loads((research / "ov030_summary.json").read_text(encoding="utf-8"))
    deterministic = json.loads((research / "ov030_deterministic_results.json").read_text(encoding="utf-8"))
    rows = [row for row in live["records"] if row["pass"] == 1]
    responded = [row for row in rows if row["status"] == "ok"]
    required = [row for row in rows if row["expected"] != "NO_TOOL"]
    responded_required = [row for row in required if row["status"] == "ok"]
    writes = [row for row in rows if row["expected"] in {"schedule_demo", "create_followup"}]
    assert len(rows) == 76 and len(responded) == 69 and len(live["records"]) == 90
    assert sum(row["routing_correct"] for row in rows) == 60
    assert sum(row["routing_correct"] for row in responded) == 60
    assert len(required) == 48 and len(responded_required) == 42
    assert sum(row["routing_correct"] for row in responded_required) == 33
    assert sum(row["proposal_correct"] for row in writes) == 15 and len(writes) == 24
    metrics = summary["live_model"]
    assert metrics["overall_routing_accuracy"] == round(60 / 76, 4)
    assert metrics["answered_routing_accuracy"] == round(60 / 69, 4)
    assert metrics["answered_tool_selection_accuracy"] == round(33 / 42, 4)
    assert metrics["write_proposal_correctness_rate"] == round(15 / 24, 4)
    assert "write_proposal_safety_rate" not in metrics

    def independent_percentile(values, quantile):
        values = sorted(values)
        position = (len(values) - 1) * quantile
        low, high = math.floor(position), math.ceil(position)
        return round(values[low] + (values[high] - values[low]) * (position - low), 2)

    case_rows = deterministic["cases"]
    tool_times = [value for row in case_rows for value in row["tool_duration_ms"]]
    action_times = [value for row in case_rows for value in row["action_duration_ms"]]
    local = summary["deterministic_orchestration"]
    assert local["evidence_file"] == "data/research/ov030_deterministic_results.json"
    assert len(case_rows) == 25 and len(tool_times) == local["server_tool_execution_samples"]
    assert len(action_times) == local["confirmed_action_execution_samples"]
    assert independent_percentile(tool_times, 0.5) == local["server_tool_execution_latency_ms_p50"]
    assert independent_percentile(tool_times, 0.95) == local["server_tool_execution_latency_ms_p95"]
    assert independent_percentile(action_times, 0.5) == local["confirmed_action_execution_latency_ms_p50"]
    assert local["confirmed_action_execution_latency_ms_p95"] is None


@pytest.mark.asyncio
async def test_stream_failure_is_counted_but_evaluator_failure_surfaces(fixture_data):
    schemas, fixture = fixture_data
    case = {"expected_tool": "lookup_lead"}

    class FailedStream:
        async def stream(self, messages, tools):
            yield {"content": "partial"}
            raise RuntimeError("synthetic provider failure")

    status, error, scored, _ = await live_eval.select_case(
        FailedStream(), [], [], case, schemas, fixture,
    )
    assert (status, error, scored["predicted"]) == ("provider_error", "RuntimeError", "UNAVAILABLE")

    class CompletedStream:
        async def stream(self, messages, tools):
            yield {"tool_calls": [{"index": 0, "function": {
                "name": "lookup_lead", "arguments": '{"identifier":"DEMO-ALPHA-001"}',
            }}]}

    with pytest.raises(KeyError):
        await live_eval.select_case(CompletedStream(), [], [], case, {}, fixture)

    class EmptyStream:
        async def stream(self, messages, tools):
            if False:
                yield None

    status, error, scored, _ = await live_eval.select_case(
        EmptyStream(), [], [], {"expected_tool": None}, schemas, fixture,
    )
    assert (status, error, scored["failure_type"]) == ("ok", None, "model_output_parse_failure")
    assert not scored["routing_correct"]


def test_workflow_score_keeps_safe_failures_and_missing_recovery():
    rows = [{"flow_id": "booking_stale", "task_completed": True,
             "correct_tool_sequence": True, "unsafe_commits": 0, "duplicate_executions": 0}]
    result = score_workflows(rows)
    assert result["expected_outcome_count"] == 1
    assert result["safe_failure_count"] == 1
    assert result["recovery_after_safe_failure_rate"] is None


def test_langfuse_export_is_allowlisted_and_fail_open():
    observations = []

    class Span:
        def end(self):
            pass

    class Client:
        def start_observation(self, **kwargs):
            observations.append(kwargs)
            return Span()

    row = {"case_id": "lookup_lead_01", "category": "LOOKUP_LEAD",
           "expected": "lookup_lead", "predicted": "lookup_lead", "routing_correct": True,
           "selection_latency_ms": 12.3, "pass": 1, "transcript": "private utterance",
           "arguments": {"identifier": "private"}, "api_key": "secret"}
    observer = ResearchObserver(Client(), enabled=True)
    observer.export_selection(row, "openai/gpt-oss-20b")
    assert len(observations) == 1
    observer.export_selection({**row, "case_id": "john_smith_01"}, "openai/gpt-oss-20b")
    assert len(observations) == 1
    payload = str(observations[0])
    assert all(value not in payload for value in ("private", "secret", "transcript", "identifier"))

    class Broken:
        def start_observation(self, **kwargs):
            raise RuntimeError("sensitive message")

    broken = ResearchObserver(Broken(), enabled=True)
    broken.export_selection(row, "openai/gpt-oss-20b")
    assert broken.failures == 1
    assert row["routing_correct"] is True


@pytest.mark.asyncio
async def test_selection_only_evaluator_never_stages_or_commits(monkeypatch, tmp_path):
    class FakeGroq:
        def __init__(self, settings, http):
            pass

        async def stream(self, messages, tools):
            yield {"tool_calls": [{"index": 0, "function": {
                "name": "schedule_demo", "arguments": "{}"}}]}

    monkeypatch.setattr(live_eval, "Settings", lambda: SimpleNamespace(
        groq_model="openai/gpt-oss-20b", groq_api_key=SecretStr("synthetic-test-key"),
    ))
    monkeypatch.setattr(live_eval, "Groq", FakeGroq)
    result = await live_eval.evaluate(tmp_path / "results.json", delay=0)
    assert len(result["records"]) == 90
    assert result["selection_write_boundary"] == {
        "staged_actions": 0, "bookings": 0, "followups": 0,
    }
    assert result["summary"]["accidental_write_execution_attempts"] == 0


@pytest.mark.asyncio
async def test_prior_invariants_and_eight_workflows():
    prior = await evaluate_ov011b()
    metrics = prior["metrics"]
    assert prior["scenario_count"] == 25
    assert metrics["task_completion_rate"] == 1
    assert metrics["committed_action_count"] == 4
    assert metrics["confirmation_compliance_rate"] == 1
    assert metrics["unsafe_commit_count"] == 0
    assert metrics["duplicate_execution_count"] == 0
    flows = await evaluate_workflows()
    assert flows["summary"]["expected_outcome_count"] == 8
    assert flows["summary"]["correct_tool_sequence_count"] == 8
    assert flows["summary"]["unsafe_write_count"] == 0
    assert flows["summary"]["recovery_after_safe_failure_rate"] == 1
