"""Deterministic scoring/privacy checks for the synthetic OV-030 research suite."""

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
    assert summary["no_tool_accuracy"] == 1
    assert summary["provider_failures"] == 1
    assert summary["confusion_matrix"]["lookup_lead"] == {"UNAVAILABLE": 1}
    assert summary["errors"][0]["case_id"] == "b"
    assert summary["repeat_consistency"] == 1
    assert summary["llm_selection_latency_ms_p95"] is None
    assert summary["tool_assisted_response_latency_ms"] is None


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
