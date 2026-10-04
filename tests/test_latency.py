"""Deterministic OV-006 projection, exclusion, and statistics coverage."""

import json
import sqlite3

from omnivoice.latency import exclusion_reason, project_turn, summarize
from scripts.export_latency_metrics import export


def test_legacy_projection_uses_existing_metrics_without_transcript():
    call = {"id": "call-1", "provider": "exotel", "started": 12.0,
            "status": "ended", "ended": 13.0}
    turn = {"user_transcript": "private question", "agent_response": "private answer",
            "cache": "exact", "first_tts_ttfa_ms": 7.5,
            "final_transcript_to_first_audio_sent_ms": 80,
            "last_vad_speech_to_first_audio_sent_ms": 95}
    row = project_turn(call, turn, 1)
    assert row["path"] == "fast_cache"
    assert row["tts_ttfa_ms"] == 7.5
    assert row["server_processing_turnaround_ms"] == 80
    assert row["server_voice_to_audio_ms"] == 95
    assert row["llm_ttft_ms"] is None
    assert "user_transcript" not in row and "agent_response" not in row
    assert exclusion_reason(call, row) is None
    assert project_turn(call, {"path": "confirmation"}, 2)["path"] == "confirmation"
    assert project_turn(call, {"rag_retrieval_ms": 3}, 3)["path"] == "foreground_rag"


def test_exclusions_and_nearest_rank_statistics():
    call = {"id": "c", "provider": "twilio", "started": 1.0,
            "status": "ended", "ended": 2.0}
    rows = [project_turn(call, {"final_transcript_to_first_audio_sent_ms": value,
                                "llm_ttft_ms": value / 2}, i)
            for i, value in enumerate((10, 20, 30, 40, 50), 1)]
    rows[0]["interrupted"] = True
    assert exclusion_reason(call, rows[0]) == "interrupted"
    result = summarize(rows[1:], {"interrupted": 1})
    assert result["metrics"]["server_processing_turnaround_ms"]["p95"] == 50
    assert result["metrics"]["server_processing_turnaround_ms"]["n"] == 4
    assert result["metrics"]["rag_retrieval_ms"]["n"] == 0
    assert result["exclusions"] == {"interrupted": 1}


def test_sqlite_export_filters_completed_valid_turns(tmp_path):
    database = tmp_path / "calls.db"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE calls (id TEXT, provider TEXT, status TEXT, "
                           "started REAL, ended REAL, metrics TEXT)")
        connection.execute("INSERT INTO calls VALUES (?, ?, ?, ?, ?, ?)", (
            "one", "exotel", "ended", 1_780_000_000.0, 1_780_000_020.0,
            json.dumps({"turns": [
                {"cache": "exact", "user_transcript": "secret", "llm_ttft_ms": None,
                 "final_transcript_to_first_audio_sent_ms": 100},
                {"interrupted": True, "final_transcript_to_first_audio_sent_ms": 120},
                {"agent_response": "missing audio"},
            ]}),
        ))
        connection.execute("INSERT INTO calls VALUES (?, ?, ?, ?, ?, ?)", (
            "two", "twilio", "active", 1_780_000_000.0, None,
            json.dumps({"turns": [{"final_transcript_to_first_audio_sent_ms": 90}]}),
        ))
    rows, summary = export(database, provider="exotel")
    assert len(rows) == 1 and rows[0]["path"] == "fast_cache"
    assert "secret" not in json.dumps(rows)
    assert summary["exclusions"] == {"interrupted": 1, "no_first_audio": 1}
    assert summary["metrics"]["llm_ttft_ms"]["n"] == 0
    assert len(export(database, session="two")[0]) == 0


def test_vad_speech_timestamp_does_not_leak_across_turns():
    """Verify last_voice consumption resets state so subsequent turns without VAD remain None."""
    call = {"id": "c1", "provider": "exotel", "started": 100.0, "status": "ended", "ended": 110.0}
    # Turn 1: has VAD speech frame
    turn1 = {
        "user_transcript": "hello",
        "stt_endpoint_delay_ms": 150.0,
        "final_transcript_to_first_audio_sent_ms": 300.0,
        "last_vad_speech_to_first_audio_sent_ms": 450.0,
    }
    # Turn 2: no new VAD speech frame (e.g. synthetic injection or silence), last_voice consumed in turn 1
    turn2 = {
        "user_transcript": "silent follow-up",
        "final_transcript_to_first_audio_sent_ms": 200.0,
    }
    r1 = project_turn(call, turn1, 1)
    r2 = project_turn(call, turn2, 2)
    assert r1["stt_endpoint_delay_ms"] == 150.0
    assert r1["server_voice_to_audio_ms"] == 450.0
    assert r2["stt_endpoint_delay_ms"] is None
    assert r2["server_voice_to_audio_ms"] is None
    assert r2["server_processing_turnaround_ms"] == 200.0

