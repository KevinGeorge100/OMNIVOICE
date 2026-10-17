"""Session-level synthetic audio rehearsal; no provider network or PSTN."""

import asyncio
import json
from pathlib import Path

import pytest

from scripts.rehearse_live_voice_sales_agent import ATTEMPT_OUTPUT
from scripts.rehearse_live_voice_sales_agent import OUTPUT as LIVE_AGGREGATE_OUTPUT
from scripts.rehearse_voice_sales_agent import OUTPUT, SCENARIOS, Rehearsal, run_scenario, until


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


@pytest.mark.asyncio
async def test_booking_waits_for_prompt_mark_and_matches_fixture(tmp_path):
    async with Rehearsal(tmp_path) as rehearsal:
        await rehearsal.turn(
            "Have I spoken with your team before? My reference is DEMO-ALPHA-001."
        )
        await rehearsal.turn("Do you have a demo Friday afternoon?")
        rehearsal.carrier.auto_mark = False
        marks_before = sum(p["event"] == "mark" for p in rehearsal.carrier.sent)
        await rehearsal.carrier.caller_audio("Book the 4 PM slot.")
        await until(
            lambda: sum(p["event"] == "mark" for p in rehearsal.carrier.sent) > marks_before
        )
        action = await rehearsal.wait_staged()
        assert action["status"] == "staged"
        assert await rehearsal.store.rows("SELECT id FROM demo_bookings") == []
        assert await rehearsal.actions.confirm(
            rehearsal.tenant_id, rehearsal.session.id, "Yes", True, ["yes"]
        ) is None
        mark = next(
            p["mark"]["name"] for p in reversed(rehearsal.carrier.sent) if p["event"] == "mark"
        )
        await rehearsal.carrier.incoming.put({"event": "mark", "mark": {"name": mark}})

        async def armed():
            return await rehearsal.store.one("SELECT status FROM actions WHERE id=?", (action["id"],))

        async with asyncio.timeout(5):
            while (await armed())["status"] != "armed":
                await asyncio.sleep(0.01)
        await until(lambda: not rehearsal.session.fsm.playing)
        rehearsal.carrier.auto_mark = True
        final = await rehearsal.turn("Yes")
        assert final["agent_response"] == "Done. Your demo is booked."
        bookings = await rehearsal.store.rows("SELECT * FROM demo_bookings")
        assert len(bookings) == 1
        assert bookings[0]["tenant_id"] == rehearsal.tenant_id
        assert bookings[0]["lead_id"] == rehearsal.lead_id
        assert bookings[0]["slot_id"] == rehearsal.slot_id
        assert bookings[0]["call_id"] == rehearsal.session.id
        slot = await rehearsal.store.one("SELECT status FROM demo_slots WHERE id=?", (rehearsal.slot_id,))
        assert slot["status"] == "booked"
        action = await rehearsal.store.one("SELECT status,result FROM actions WHERE id=?", (action["id"],))
        assert action["status"] == "committed"
        assert json.loads(action["result"])["booking_id"] == bookings[0]["id"]


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
    assert path == LIVE_AGGREGATE_OUTPUT
    assert ATTEMPT_OUTPUT != path
    raw = path.read_text(encoding="utf-8")
    artifact = json.loads(raw)
    assert artifact["schema_version"] == 2
    assert artifact["validation_level"] == "B_live_provider_non_pstn"
    assert artifact["summary"]["retained_attempts"] == len(artifact["attempts"]) == 7
    assert artifact["summary"]["passed_attempts"] == 2
    assert [row["result"]["status"] for row in artifact["attempts"]] == [
        "FAIL", "FAIL", "FAIL", "FAIL", "FAIL", "PASS", "PASS",
    ]
    winner = artifact["attempts"][-1]["result"]
    assert winner["status"] == "PASS"
    assert len(winner["acceptance_checks"]) == 20
    assert all(winner["acceptance_checks"].values())
    assert winner["action_status_before_prompt_ack"] == ["staged"]
    assert winner["prompt_mark_pending_before_ack"] is True
    assert winner["booking_count_before_prompt_ack"] == 0
    assert winner["action_status_before_confirmation"] == ["armed"]
    assert winner["staged_selection_matches_fixture"] is True
    assert winner["booking_selection_matches_fixture"] is True
    assert winner["selected_slot_booked"] is True
    assert winner["committed_result_matches_booking"] is True
    for attempt in artifact["attempts"]:
        result = attempt["result"]
        assert result["external_business_writes"] == 0
        assert result.get("booking_count", 0) <= 1
    for forbidden in (
        "user_transcript", "agent_response", "api_key", "authorization", "bearer",
        "tenant_id", "lead_id", "caller_phone", "DEMO-ALPHA-001", "Synthetic Lead",
    ):
        assert forbidden.casefold() not in raw.casefold()
