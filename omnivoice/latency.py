"""Privacy-preserving projections and statistics for completed call turns."""

import math
import statistics

METRICS = (
    "stt_endpoint_delay_ms",
    "retrieval_ms",
    "rag_retrieval_ms",
    "llm_ttft_ms",
    "speech_buffer_delay_ms",
    "tts_ttfa_ms",
    "carrier_framing_delay_ms",
    "server_processing_turnaround_ms",
    "server_voice_to_audio_ms",
)

ALIASES = {
    "tts_ttfa_ms": "first_tts_ttfa_ms",
    "server_processing_turnaround_ms": "final_transcript_to_first_audio_sent_ms",
    "server_voice_to_audio_ms": "last_vad_speech_to_first_audio_sent_ms",
}


def project_turn(call, turn, index):
    """Expose numeric telemetry only; transcripts and provider payloads stay private."""
    row = {
        "session_id": call["id"],
        "turn_index": index,
        "provider": call["provider"],
        "call_started": call["started"],
        "interrupted": bool(turn.get("interrupted")),
        "error": bool(turn.get("error")),
    }
    for name in METRICS:
        value = turn.get(name, turn.get(ALIASES.get(name)))
        row[name] = value if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0 else None
    row["path"] = turn.get("path") or (
        "fast_cache" if turn.get("cache") in {"exact", "semantic"}
        else "foreground_rag" if row["rag_retrieval_ms"] is not None else "other"
    )
    return row


def exclusion_reason(call, row):
    if call["status"] == "active" or call["ended"] is None:
        return "call_incomplete"
    if row["interrupted"]:
        return "interrupted"
    if row["error"]:
        return "response_error"
    if row["server_processing_turnaround_ms"] is None:
        return "no_first_audio"
    return None


def summarize(rows, exclusions=None):
    result = {"turns_included": len(rows), "exclusions": exclusions or {}, "metrics": {}}
    for name in METRICS:
        values = sorted(row[name] for row in rows if row.get(name) is not None)
        if not values:
            result["metrics"][name] = {"n": 0, "mean": None, "std": None,
                                        "min": None, "p50": None, "p90": None,
                                        "p95": None, "max": None}
            continue
        def percentile(p):
            return values[max(0, math.ceil(p * len(values)) - 1)]
        result["metrics"][name] = {
            "n": len(values), "mean": statistics.mean(values),
            "std": statistics.stdev(values) if len(values) > 1 else None,
            "min": values[0], "p50": percentile(.5), "p90": percentile(.9),
            "p95": percentile(.95), "max": values[-1],
        }
    return result
