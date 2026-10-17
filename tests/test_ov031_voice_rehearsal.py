"""Session-level synthetic audio rehearsal; no provider network or PSTN."""

import json
from pathlib import Path

import pytest

from scripts.rehearse_voice_sales_agent import OUTPUT, SCENARIOS, run_scenario


@pytest.mark.parametrize("scenario", SCENARIOS)
async def test_real_session_path_with_stubbed_providers(tmp_path, scenario):
    result = await run_scenario(scenario, tmp_path / scenario)
    assert result["passed"]
    assert result["input_pcm16k_bytes"] >= 6400
    assert result["frame_count"] >= 1
    assert result["frame_bytes"] == 3200
    assert result["local_trace"]["turns_recorded"] == result["turn_count"]
    assert result["booking_count"] <= 1
    if scenario == "happy_path":
        assert result["tool_choices"] == ["lookup_lead", "check_demo_slots", "schedule_demo"]
        assert result["booking_count"] == 1 and result["spoken_success"]
        assert result["action_statuses"] == ["committed"]
    elif scenario in {"negative_confirmation", "ambiguous_confirmation", "stale_slot",
                      "confirmation_barge_in"}:
        assert result["booking_count"] == 0 and not result["spoken_success"]
    if scenario in {"ordinary_barge_in", "confirmation_barge_in"}:
        assert result["barge_in_count"] == 1 and result["tts_cancel_count"] >= 1


def test_research_artifact_is_synthetic_and_stage_metrics_are_bounded():
    assert OUTPUT == Path(__file__).resolve().parents[1] / "data/research/ov031_voice_rehearsal.json"
    raw = OUTPUT.read_text(encoding="utf-8")
    artifact = json.loads(raw)
    assert artifact["schema_version"] == 1
    assert artifact["validation_level"] == "A_deterministic_synthetic_voice_path"
    assert artifact["summary"] == {"count": 12, "passed": 12}
    assert {row["scenario"] for row in artifact["scenarios"]} == set(SCENARIOS)
    assert artifact["frame_format"] == {
        "sample_rate_hz": 8000, "sample_width_bits": 16, "channels": 1,
        "bytes_per_frame": 3200, "ms_per_frame": 200,
    }
    assert artifact["stage_latency_ms"]["stt_stub_completion"]["samples"] >= 12
    assert artifact["stage_latency_ms"]["confirmed_action_execution"]["p95_ms"] is None
    for forbidden in ("user_transcript", "api_key", "authorization", "DEMO-ALPHA-001", "Synthetic Lead"):
        assert forbidden.casefold() not in raw.casefold()


def test_live_artifact_uses_sanitized_metadata_only():
    path = OUTPUT.with_name("ov031_live_provider_rehearsal.json")
    raw = path.read_text(encoding="utf-8")
    artifact = json.loads(raw)
    assert artifact["validation_level"] == "B_live_provider_non_pstn"
    assert artifact["status"] in {"PASS", "FAIL", "BLOCKED_BY_CONFIGURATION"}
    assert artifact["external_business_writes"] == 0
    assert artifact.get("booking_count", 0) <= 1
    for forbidden in (
        "user_transcript", "agent_response", "api_key", "authorization", "bearer",
        "tenant_id", "lead_id", "caller_phone", "DEMO-ALPHA-001", "Synthetic Lead",
    ):
        assert forbidden.casefold() not in raw.casefold()
