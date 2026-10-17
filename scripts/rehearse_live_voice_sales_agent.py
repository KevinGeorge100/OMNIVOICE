"""Optional Level B voice rehearsal through CallSession with live Gnani/Groq APIs.

The only business effects are isolated SQLite rows in a temporary directory.
No carrier account or customer records are touched. Output is an allowlisted,
non-PII research summary, never transcripts or raw audio.
"""

import argparse
import asyncio
import base64
import json
import logging
import subprocess
import sys
import tempfile
import time
import wave
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import httpx

from omnivoice.actions import ActionEngine
from omnivoice.config import Settings
from omnivoice.providers import Groq
from omnivoice.rag import Knowledge
from omnivoice.research_observability import ResearchObserver, live_projection
from omnivoice.sales import SalesService, register_sales_tools
from omnivoice.session import CallSession
from omnivoice.store import Store
from omnivoice.tools import ToolRegistry
from omnivoice.transport import MediaTransport
from omnivoice.vad import SileroFactory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.rehearse_voice_sales_agent import (  # noqa: E402
    ZONE,
    CarrierSocket,
    TimedEvents,
    next_friday,
    until,
)

OUTPUT = ROOT / "data/research/ov031_live_provider_rehearsal.json"
SAPI_SCRIPT = ROOT / "scripts/synthesize_caller_sapi.ps1"


def synthesize_caller(text):
    """Generate synthetic caller speech locally; agent TTS remains live Gnani."""
    with tempfile.TemporaryDirectory() as folder:
        text_path = Path(folder) / "caller.txt"
        wave_path = Path(folder) / "caller.wav"
        text_path.write_text(text, encoding="utf-8")
        result = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(SAPI_SCRIPT),
             "-TextPath", str(text_path), "-WavePath", str(wave_path)],
            capture_output=True, timeout=30, check=False,
        )
        if result.returncode or not wave_path.is_file():
            raise RuntimeError("Synthetic caller speech unavailable")
        with wave.open(str(wave_path), "rb") as source:
            if (source.getframerate(), source.getnchannels(), source.getsampwidth()) != (8000, 1, 2):
                raise ValueError("Synthetic caller speech format mismatch")
            return source.readframes(source.getnframes())


async def send_spoken_turn(carrier, session, text, progress, label):
    before = len(session.metrics["turns"])
    prior_tools = len(session.services.events.tool_events)
    progress["stage"] = f"{label}_synthesizing_caller_audio"
    audio = await asyncio.wait_for(asyncio.to_thread(synthesize_caller, text), 35)
    progress["caller_audio_bytes_generated"] = len(audio)
    progress["stage"] = f"{label}_feeding_caller_audio"
    for offset in range(0, len(audio), 3200):
        frame = audio[offset:offset + 3200]
        await carrier.incoming.put({"event": "media", "media": {
            "payload": base64.b64encode(frame).decode("ascii"),
        }})
        await asyncio.sleep(len(frame) / 16000)
    # Real elapsed silence exercises Gnani's endpointing in the session.
    for _ in range(2):
        await carrier.incoming.put({"event": "media", "media": {
            "payload": base64.b64encode(b"\0" * 3200).decode("ascii"),
        }})
        await asyncio.sleep(0.25)
    forced_flush = False
    progress["stage"] = f"{label}_awaiting_stt_and_agent"
    try:
        await until(lambda: len(session.metrics["turns"]) > before, seconds=35)
    except TimeoutError:
        # A forced provider flush is recorded explicitly; it does not masquerade
        # as natural VAD endpointing.
        forced_flush = True
        progress["stage"] = f"{label}_forced_stt_flush"
        await session.stt.flush()
        await until(lambda: len(session.metrics["turns"]) > before, seconds=35)
    await until(lambda: not session.fsm.playing, seconds=10)
    await until(lambda: session.response is None or session.response.done(), seconds=10)
    await until(lambda: not session.stt._pending_tasks, seconds=10)
    metric = session.metrics["turns"][-1]
    recognized = metric.get("user_transcript", "").casefold()
    return {
        "stt_nonempty": bool(metric.get("user_transcript", "").strip()),
        "stt_intent_flags": {
            "lead": "lead" in recognized or "spoken" in recognized,
            "slot": "slot" in recognized or "afternoon" in recognized,
            "booking": "book" in recognized,
            "confirmation": recognized.strip(" .!?") == "yes",
        },
        "stt_forced_flush": forced_flush,
        "caller_audio_bytes": len(audio),
        "path": metric.get("path"),
        "first_carrier_audio_ms": metric.get("final_transcript_to_first_audio_sent_ms"),
        "tts_ttfa_ms": metric.get("first_tts_ttfa_ms"),
        "stt_endpoint_delay_ms": metric.get("stt_endpoint_delay_ms"),
        "llm_ttft_ms": metric.get("llm_ttft_ms"),
        "tool_requests": [event["tool"] for event in session.services.events.tool_events[prior_tools:]
                          if event["event"] == "tool.requested"],
        "lead_resolved": bool(session.sales_state.get("lead_id")),
        "offered_slot_count": len(session.sales_state.get("offered_slots", [])),
    }


async def run_live(*, export_langfuse=False):
    settings = Settings()
    if (settings.stt_provider, settings.tts_provider) != ("gnani", "gnani"):
        return {"status": "BLOCKED_BY_CONFIGURATION", "reason": "Gnani STT and TTS are not selected"}
    if not settings.gnani_api_key.get_secret_value() or not settings.groq_api_key.get_secret_value():
        return {"status": "BLOCKED_BY_CONFIGURATION", "reason": "Gnani or Groq credentials missing"}
    if settings.groq_model != "openai/gpt-oss-20b" or not settings.silero_model.is_file():
        return {"status": "BLOCKED_BY_CONFIGURATION", "reason": "Required model or Silero file unavailable"}

    result = {"status": "FAIL", "validation_level": "B_live_provider_non_pstn",
              "providers": {"stt": "Gnani Prisma", "llm": settings.groq_model,
                            "tts": "Gnani Timbre", "caller_audio": "local_Windows_SAPI"},
              "turns": [], "tool_names": [],
              "external_business_writes": 0, "stage": "provisioning"}
    with tempfile.TemporaryDirectory() as directory:
        store = Store(Path(directory) / "isolated-sales.db")
        await store.open()
        async with httpx.AsyncClient(trust_env=False, follow_redirects=False) as http:
            session = None
            task = None
            observer = ResearchObserver()
            carrier = CarrierSocket()
            try:
                tenant = await store.create_tenant({
                    "name": "Synthetic Live Rehearsal", "language": "en-IN",
                    "greeting": "Hello, this is OmniVoice.", "confirmation_phrases": ["yes"],
                    "backchannels": ["mm hmm"], "instructions": "Offer sales demos.",
                })
                tenant_id = tenant["id"]
                sales = SalesService(store)
                lead_id = await sales.add_lead(tenant_id, "Synthetic Lead", "demo")
                date = next_friday()
                start = datetime(date.year, date.month, date.day, 16, tzinfo=ZONE)
                await sales.add_slot(tenant_id, start.isoformat(),
                                     (start + timedelta(minutes=30)).isoformat())
                actions = ActionEngine(store, http)
                events = TimedEvents()
                registry = ToolRegistry(store, actions, events=events)
                register_sales_tools(registry, sales)
                services = SimpleNamespace(
                    settings=settings, http=http, actions=actions, tool_registry=registry,
                    knowledge=Knowledge(store), llm=Groq(settings, http), events=events,
                    vad=SileroFactory(settings.silero_model),
                )
                session = CallSession(
                    "synthetic-live-call", await store.tenant(tenant_id),
                    MediaTransport(carrier, "exotel", "synthetic-live-stream"), services,
                )
                await store.execute(
                    "INSERT INTO calls (id,tenant_id,provider,status,started) VALUES (?,?,?,?,?)",
                    (session.id, tenant_id, "exotel", "active", time.time()),
                )
                if export_langfuse:
                    observer = ResearchObserver.from_settings(settings, explicit=True)
                    observer.start_live()
                task = asyncio.create_task(session.run())
                result["stage"] = "awaiting_session_greeting"
                await until(lambda: any(p["event"] == "mark" for p in carrier.sent), seconds=45)
                await until(lambda: not session.fsm.playing, seconds=10)
                prompts = (
                    "Find lead reference demo.",
                    f"Check demo slots on Friday {date:%d %B %Y} afternoon.",
                    "Book the four PM demo slot you offered.",
                )
                for index, prompt in enumerate(prompts, 1):
                    label = f"spoken_tool_turn_{index}"
                    result["turns"].append(await send_spoken_turn(
                        carrier, session, prompt, result, label,
                    ))
                staged = await store.rows("SELECT status FROM actions WHERE call_id=?", (session.id,))
                result["write_before_confirmation"] = bool(await store.rows("SELECT id FROM demo_bookings"))
                result["action_staged_or_armed"] = any(row["status"] in {"staged", "armed"} for row in staged)
                if result["action_staged_or_armed"]:
                    result["turns"].append(await send_spoken_turn(
                        carrier, session, "Yes.", result, "spoken_confirmation_turn",
                    ))
                result["tool_names"] = [event["tool"] for event in events.tool_events
                                        if event["event"] == "tool.requested"]
                bookings = await store.rows("SELECT id FROM demo_bookings WHERE tenant_id=?", (tenant_id,))
                result["booking_count"] = len(bookings)
                result["confirmed_commits"] = session.metrics["tool_summary"]["committed"]
                result["final_spoken_success"] = (
                    bool(session.metrics["turns"])
                    and session.metrics["turns"][-1].get("agent_response") == "Done. Your demo is booked."
                    and bool(session.metrics["turns"][-1].get("outbound_audio_bytes"))
                )
                result["carrier_frame_count"] = sum(p["event"] == "media" for p in carrier.sent)
                result["carrier_frames_valid"] = all(
                    len(base64.b64decode(p["media"]["payload"])) == 3200
                    and not base64.b64decode(p["media"]["payload"]).startswith(b"RIFF")
                    for p in carrier.sent if p["event"] == "media"
                )
                result["status"] = "PASS" if (
                    all(turn["stt_nonempty"] for turn in result["turns"])
                    and {"lookup_lead", "check_demo_slots", "schedule_demo"}.issubset(result["tool_names"])
                    and not result["write_before_confirmation"]
                    and result["booking_count"] == result["confirmed_commits"] == 1
                    and result["final_spoken_success"] and result["carrier_frames_valid"]
                ) else "FAIL"
                result["stage"] = "completed"
                result["synthetic_lead_count"] = int(bool(lead_id))
            except Exception as error:
                # No exception bodies, URLs, transcripts or provider credentials in research output.
                result["failure_type"] = type(error).__name__
            finally:
                if task:
                    await carrier.incoming.put({"event": "stop"})
                    try:
                        await asyncio.wait_for(task, 10)
                    except Exception:
                        task.cancel()
                        await asyncio.gather(task, return_exceptions=True)
                if session:
                    result["greeting_audio_sent"] = bool(session.metrics.get("greeting_audio_sent"))
                    result["carrier_frames_observed"] = sum(p["event"] == "media" for p in carrier.sent)
                    result["end_reason"] = session.metrics.get("end_reason")
                    result["provider_failures"] = session.metrics.get("provider_failures", [])
                    result["stt_speech_buffer_bytes"] = len(getattr(session.stt, "_speech_buffer", b""))
                    result["stt_preroll_bytes"] = len(getattr(session.stt, "_preroll", b""))
                    result["stt_pending_tasks"] = len(getattr(session.stt, "_pending_tasks", ()))
                    result["tool_names"] = [event["tool"] for event in events.tool_events
                                            if event["event"] == "tool.requested"]
                    result["turn_provider_failures"] = [
                        turn["provider_failure"] for turn in session.metrics["turns"]
                        if isinstance(turn.get("provider_failure"), dict)
                    ]
                    result["local_trace"] = live_projection(
                        session.metrics, "exotel", "failed" if session.metrics["errors"] else "completed"
                    )
                    await store.execute(
                        "UPDATE calls SET status=?,ended=?,metrics=? WHERE id=?",
                        ("failed" if session.metrics["errors"] else "completed",
                         time.time(), json.dumps(session.metrics), session.id),
                    )
                    saved = await store.one("SELECT status,metrics FROM calls WHERE id=?", (session.id,))
                    result["call_row_persisted"] = saved is not None
                    result["turn_metrics_persisted"] = saved is not None and bool(json.loads(saved["metrics"])["turns"])
                    result["booking_count"] = len(await store.rows(
                        "SELECT id FROM demo_bookings WHERE tenant_id=?", (session.tenant["id"],)
                    ))
                    result["action_statuses"] = [row["status"] for row in await store.rows(
                        "SELECT status FROM actions WHERE call_id=?", (session.id,)
                    )]
                    if export_langfuse:
                        observer.submit_live(session.metrics, "exotel", saved["status"])
                await observer.close()
                result["langfuse_export_attempted"] = export_langfuse
                result["langfuse_exported_locally"] = observer.exported
                await store.close()
    return result


if __name__ == "__main__":
    logging.getLogger("omnivoice.media").setLevel(logging.ERROR)
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--langfuse", action="store_true")
    args = parser.parse_args()
    result = asyncio.run(run_live(export_langfuse=args.langfuse))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: result.get(key) for key in (
        "status", "failure_type", "tool_names", "booking_count", "carrier_frame_count",
    )}))
    raise SystemExit(0 if result["status"] in {"PASS", "BLOCKED_BY_CONFIGURATION"} else 1)
