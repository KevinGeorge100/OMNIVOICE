"""OV-031 isolated carrier-shaped rehearsal through the production CallSession.

Deterministic mode substitutes only STT/LLM/TTS/VAD provider interfaces. All
session, transport, retrieval, tool, action, and SQLite paths are real. It never
uses a customer database or places a PSTN call.
"""

import argparse
import asyncio
import base64
import json
import logging
import math
import tempfile
import time
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from omnivoice.actions import ActionEngine
from omnivoice.config import Settings
from omnivoice.events import TenantEvents
from omnivoice.models import Transcript
from omnivoice.rag import Knowledge
from omnivoice.research_observability import live_projection
from omnivoice.resilience import ProviderTransientError
from omnivoice.sales import SalesService, register_sales_tools
from omnivoice.session import CallSession
from omnivoice.store import Store
from omnivoice.tools import ToolRegistry
from omnivoice.transport import MediaTransport

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data/research/ov031_voice_rehearsal.json"
ZONE = timezone(timedelta(hours=5, minutes=30))


def next_friday():
    today = datetime.now(ZONE).date()
    return today + timedelta(days=(4 - today.weekday()) % 7 or 7)


class CarrierSocket:
    """Exotel-shaped carrier endpoint; mark acknowledgements are controllable."""

    def __init__(self):
        self.incoming = asyncio.Queue()
        self.sent = []
        self.auto_mark = True
        self.closed = False

    async def receive_json(self):
        return await self.incoming.get()

    async def send_json(self, value):
        self.sent.append(value)
        if value.get("event") == "mark" and self.auto_mark:
            await self.incoming.put({"event": "mark", "mark": value["mark"]})

    async def close(self, code=1000):
        self.closed = True
        await self.incoming.put({"event": "stop"})

    async def caller_audio(self, text):
        # A deterministic audio surrogate reaches STT only through MediaTransport.
        self.pending_text.put_nowait(text)
        pcm = np.full(1600, 1200, dtype="<i2").tobytes()
        await self.incoming.put({"event": "media", "media": {
            "payload": base64.b64encode(pcm).decode("ascii"),
        }})


class ScriptedSTT:
    def __init__(self, pending_text):
        self.pending_text = pending_text
        self.queue = asyncio.Queue()
        self.input_bytes = 0
        self.fail_next = False
        self.closed = False
        self.completion_ms = []

    async def open(self):
        pass

    async def send(self, pcm16k):
        started = time.perf_counter()
        self.input_bytes += len(pcm16k)
        if self.fail_next:
            self.fail_next = False
            raise ProviderTransientError("synthetic_stt", "STT", "injected failure")
        if not pcm16k or not any(pcm16k):
            return
        try:
            text = self.pending_text.get_nowait()
        except asyncio.QueueEmpty:
            return
        # Give the parallel VAD consumer time to observe the same caller frame.
        await asyncio.sleep(0.015)
        await self.queue.put(Transcript(text=text, final=True, language="en-IN"))
        self.completion_ms.append(round((time.perf_counter() - started) * 1000, 2))

    async def events(self):
        while True:
            item = await self.queue.get()
            if item is None:
                return
            yield item

    async def close(self):
        self.closed = True
        await self.queue.put(None)


class ScriptedTTS:
    def __init__(self):
        self.spoken = []
        self.cancel_count = 0
        self.fail_next = False
        self.long_next = False
        self.closed = False

    async def open(self):
        pass

    async def stream_text(self, texts):
        async for text in texts:
            self.spoken.append(text)
            if self.fail_next:
                self.fail_next = False
                raise ProviderTransientError("synthetic_tts", "TTS", "injected failure")
            length = 16000 if self.long_next else 3600
            self.long_next = False
            pcm = (1000 + len(self.spoken)).to_bytes(2, "little", signed=True) * (length // 2)
            for offset in range(0, len(pcm), 800):
                await asyncio.sleep(0)
                yield pcm[offset:offset + 800]

    async def cancel(self):
        self.cancel_count += 1

    async def close(self):
        self.closed = True


class ScriptedVAD:
    def process(self, pcm):
        return [0.95 if any(pcm) else 0.0]


class TimedEvents(TenantEvents):
    def __init__(self):
        super().__init__()
        self.tool_events = []

    def publish(self, tenant_id, kind, call):
        if kind.startswith("tool."):
            self.tool_events.append({
                "event": kind, "tool": call.get("tool_name"), "kind": call.get("kind"),
                "duration_ms": call.get("duration_ms"),
                "outcome": call.get("result_status") or call.get("error_category"),
                "action_end_to_end_ms": call.get("action_end_to_end_ms"),
            })
        super().publish(tenant_id, kind, call)


def percentile(values, quantile):
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * quantile
    low, high = math.floor(position), math.ceil(position)
    return round(ordered[low] + (ordered[high] - ordered[low]) * (position - low), 2)


def stage_stats(values):
    values = [value for value in values if isinstance(value, (int, float))]
    return {"samples": len(values), "p50_ms": percentile(values, 0.5),
            "p95_ms": percentile(values, 0.95) if len(values) >= 20 else None}


class ScriptedLLM:
    def __init__(self, lead_id, slot_id, date_text):
        self.lead_id, self.slot_id, self.date_text = lead_id, slot_id, date_text
        self.fail_next = False
        self.choices = []

    async def predict(self, history, tools):
        return [], []

    async def stream(self, messages, tools):
        if self.fail_next:
            self.fail_next = False
            raise ProviderTransientError("synthetic_llm", "LLM", "injected failure")
        if messages[-1]["role"] == "tool":
            result = json.loads(messages[-1]["content"])
            data = result.get("data") or {}
            if "lead" in data:
                reply = "Yes, I found your existing lead record."
            elif data.get("reason") == "not_found":
                reply = "I couldn't find a lead under that reference, but I can check demo times."
            elif "slots" in data:
                reply = "A Friday 4 PM demo slot is available."
            else:
                reply = "I can help with another option."
            yield {"content": reply}
            return
        user = next(m["content"] for m in reversed(messages) if m["role"] == "user").casefold()
        if "spoken with your team" in user:
            identifier = "MISSING-LEAD-001" if "missing" in user else "DEMO-ALPHA-001"
            name, args = "lookup_lead", {"identifier": identifier}
        elif "demo friday afternoon" in user:
            name, args = "check_demo_slots", {"date": self.date_text, "time_preference": "afternoon"}
        elif "book the 4 pm" in user:
            name, args = "schedule_demo", {"lead_id": self.lead_id, "slot_id": self.slot_id}
        else:
            reply = (
                "No problem. I won't book that demo." if user == "no" else
                "I have not booked it. Please say yes only when you're sure." if user == "maybe" else
                "The demo is already booked; no further booking was made." if user == "yes" else
                "Of course. I can help with another question."
            )
            yield {"content": reply}
            return
        self.choices.append(name)
        yield {"tool_calls": [{"index": 0, "id": name, "function": {
            "name": name, "arguments": json.dumps(args),
        }}]}


async def until(predicate, seconds=5):
    async with asyncio.timeout(seconds):
        while not predicate():
            await asyncio.sleep(0.005)


class Rehearsal:
    def __init__(self, directory):
        self.directory = Path(directory)

    async def __aenter__(self):
        self.store = Store(self.directory / "sales-rehearsal.db")
        await self.store.open()
        self.tenant = await self.store.create_tenant({
            "name": "Synthetic Rehearsal", "language": "en-IN",
            "greeting": "Hello, this is OmniVoice.", "confirmation_phrases": ["yes"],
            "backchannels": ["mm hmm"], "instructions": "Offer sales demos.",
        })
        self.tenant_id = self.tenant["id"]
        await self.store.add_knowledge(
            self.tenant_id, "faq", "What does OmniVoice do?",
            "OmniVoice handles enterprise phone calls with AI.", approved=True,
        )
        self.sales = SalesService(self.store)
        self.lead_id = await self.sales.add_lead(
            self.tenant_id, "Synthetic Lead", "DEMO-ALPHA-001",
        )
        self.date = next_friday()
        start = datetime(self.date.year, self.date.month, self.date.day, 16, tzinfo=ZONE)
        self.slot_id = await self.sales.add_slot(
            self.tenant_id, start.isoformat(), (start + timedelta(minutes=30)).isoformat(),
        )
        self.actions = ActionEngine(self.store, None)
        self.events = TimedEvents()
        self.event_queue = self.events.subscribe(self.tenant_id)
        self.registry = ToolRegistry(self.store, self.actions, events=self.events)
        register_sales_tools(self.registry, self.sales)
        self.knowledge = Knowledge(self.store)
        self.llm = ScriptedLLM(self.lead_id, self.slot_id, self.date.isoformat())
        self.carrier = CarrierSocket()
        self.carrier.pending_text = asyncio.Queue()
        self.stt = ScriptedSTT(self.carrier.pending_text)
        self.tts = ScriptedTTS()
        settings = Settings(
            _env_file=None, stt_provider="gnani", tts_provider="gnani",
            gnani_api_key="synthetic-only", groq_api_key="synthetic-only",
        )
        services = SimpleNamespace(
            settings=settings, actions=self.actions, tool_registry=self.registry,
            knowledge=self.knowledge, llm=self.llm, events=self.events,
            vad=SimpleNamespace(session=ScriptedVAD), http=None,
        )
        self.session = CallSession(
            "synthetic-call", await self.store.tenant(self.tenant_id),
            MediaTransport(self.carrier, "exotel", "synthetic-stream"), services,
        )
        self.session.stt, self.session.tts = self.stt, self.tts
        await self.store.execute(
            "INSERT INTO calls (id,tenant_id,provider,status,started) VALUES (?,?,?,?,?)",
            (self.session.id, self.tenant_id, "exotel", "active", time.time()),
        )
        self.task = asyncio.create_task(self.session.run())
        await until(lambda: any(p["event"] == "mark" for p in self.carrier.sent))
        await until(lambda: not self.session.fsm.playing)
        return self

    async def __aexit__(self, *_):
        await self.carrier.incoming.put({"event": "stop"})
        await asyncio.wait_for(self.task, 5)
        self.status = "failed" if self.session.metrics["errors"] else "completed"
        await self.store.execute(
            "UPDATE calls SET status=?,ended=?,metrics=? WHERE id=?",
            (self.status, time.time(), json.dumps(self.session.metrics), self.session.id),
        )
        self.persisted = await self.store.one("SELECT * FROM calls WHERE id=?", (self.session.id,))
        self.bookings = await self.store.rows("SELECT * FROM demo_bookings WHERE tenant_id=?", (self.tenant_id,))
        self.actions_rows = await self.store.rows("SELECT * FROM actions WHERE call_id=?", (self.session.id,))
        self.events.unsubscribe(self.tenant_id, self.event_queue)
        await self.store.close()

    async def turn(self, text):
        before = len(self.session.metrics["turns"])
        await self.carrier.caller_audio(text)
        await until(lambda: len(self.session.metrics["turns"]) > before)
        await until(lambda: not self.session.fsm.playing)
        return self.session.metrics["turns"][-1]

    async def wait_staged(self):
        async def staged():
            return await self.store.one(
                "SELECT * FROM actions WHERE call_id=? ORDER BY created DESC LIMIT 1", (self.session.id,)
            )
        async with asyncio.timeout(5):
            while not (row := await staged()):
                await asyncio.sleep(0.005)
        return row

    def frames(self):
        return [base64.b64decode(p["media"]["payload"], validate=True)
                for p in self.carrier.sent if p["event"] == "media"]


async def run_scenario(name, directory):
    async with Rehearsal(directory) as r:
        faq = "What does OmniVoice do?"
        lead = "Have I spoken with your team before? My reference is DEMO-ALPHA-001."
        slots = "Do you have a demo Friday afternoon?"
        book = "Book the 4 PM slot."
        if name == "happy_path":
            faq_turn = await r.turn(faq)
            assert faq_turn["path"] == "fast_cache"
            await r.turn(lead)
            await r.turn(slots)
            await r.turn(book)
            staged = await r.wait_staged()
            assert staged["status"] == "armed"
            assert not await r.store.rows("SELECT id FROM demo_bookings")
            final = await r.turn("Yes")
            assert final["path"] == "confirmation"
            assert final["agent_response"] == "Done. Your demo is booked."
            assert len(await r.store.rows("SELECT id FROM demo_bookings")) == 1
        elif name in {"negative_confirmation", "ambiguous_confirmation", "duplicate_confirmation", "stale_slot"}:
            await r.turn(lead)
            await r.turn(slots)
            await r.turn(book)
            assert not await r.store.rows("SELECT id FROM demo_bookings")
            if name == "stale_slot":
                await r.store.execute("UPDATE demo_slots SET status='booked' WHERE id=?", (r.slot_id,))
            response = await r.turn("No" if name == "negative_confirmation" else
                                    "Maybe" if name == "ambiguous_confirmation" else "Yes")
            if name == "duplicate_confirmation":
                await r.turn("Yes")
                assert len(await r.store.rows("SELECT id FROM demo_bookings")) == 1
            elif name == "stale_slot":
                assert "no longer available" in response["agent_response"]
                assert not await r.store.rows("SELECT id FROM demo_bookings")
            else:
                assert not await r.store.rows("SELECT id FROM demo_bookings")
                assert ("won't book" if name == "negative_confirmation" else "not booked") in response["agent_response"].casefold()
        elif name == "lead_not_found":
            await r.turn("Have I spoken with your team before? My reference is MISSING-LEAD-001.")
            assert "couldn't find" in r.session.metrics["turns"][-1]["agent_response"]
            assert "lead_id" not in r.session.sales_state
            await r.turn(slots)
            assert r.slot_id in r.session.sales_state["offered_slots"]
        elif name == "tool_failure":
            async def fail_read(ctx, args):
                raise TimeoutError("synthetic tool failure")
            definition = r.registry._local["lookup_lead"]
            r.registry._local["lookup_lead"] = replace(definition, handler=fail_read)
            await r.turn(lead)
            assert "couldn't complete" in r.session.metrics["turns"][-1]["agent_response"]
            assert r.session.metrics["tool_summary"]["failed"] == 1
        elif name == "llm_failure":
            r.llm.fail_next = True
            await r.turn(lead)
            assert "trouble responding" in r.session.metrics["turns"][-1]["agent_response"]
            assert not await r.store.rows("SELECT id FROM actions")
        elif name == "stt_failure":
            r.stt.fail_next = True
            await r.carrier.caller_audio(lead)
            await until(lambda: r.stt.closed)
            assert any("trouble hearing" in text for text in r.tts.spoken)
            assert not await r.store.rows("SELECT id FROM actions")
        elif name == "tts_failure":
            r.tts.fail_next = True
            await r.carrier.caller_audio(faq)
            await until(lambda: r.carrier.closed)
            assert not await r.store.rows("SELECT id FROM actions")
        elif name in {"ordinary_barge_in", "confirmation_barge_in"}:
            if name == "confirmation_barge_in":
                await r.turn(lead)
                await r.turn(slots)
                before_turns = len(r.session.metrics["turns"])
                r.carrier.auto_mark = False
                r.tts.long_next = True
                before = len(r.frames())
                await r.carrier.caller_audio(book)
                await until(lambda: len(r.frames()) > before and r.session.fsm.playing)
                assert (await r.wait_staged())["status"] == "staged"
            else:
                before_turns = len(r.session.metrics["turns"])
                r.carrier.auto_mark = False
                r.tts.long_next = True
                before = len(r.frames())
                await r.carrier.caller_audio("Tell me more about OmniVoice.")
                await until(lambda: len(r.frames()) > before and r.session.fsm.playing)
            await r.carrier.caller_audio("Wait, please stop.")
            await until(lambda: any(p["event"] == "clear" for p in r.carrier.sent))
            await until(lambda: len(r.session.metrics["barge_in"]) == 1)
            await until(lambda: len(r.session.metrics["turns"]) >= before_turns + 2)
            assert r.session.metrics["turns"][before_turns]["interrupted"] is True
            assert r.tts.cancel_count >= 1
            if name == "confirmation_barge_in":
                assert not await r.store.rows("SELECT id FROM demo_bookings")
                assert (await r.wait_staged())["status"] == "cancelled"
        else:
            raise ValueError(f"Unknown scenario: {name}")
    turns = r.session.metrics["turns"]
    frames = r.frames()
    assert frames and all(len(frame) == 3200 and not frame.startswith(b"RIFF") for frame in frames)
    assert r.persisted["status"] == r.status
    assert len(r.bookings) <= 1
    assert all(row["status"] != "executing" for row in r.actions_rows)
    projection = live_projection(r.session.metrics, "exotel", r.status)
    if name in {"ordinary_barge_in", "confirmation_barge_in"}:
        clear_index = next(i for i, item in enumerate(r.carrier.sent) if item["event"] == "clear")
        old_media = next(item for item in reversed(r.carrier.sent[:clear_index]) if item["event"] == "media")
        old_sample = base64.b64decode(old_media["media"]["payload"])[:2]
        assert all(base64.b64decode(item["media"]["payload"])[:2] != old_sample
                   for item in r.carrier.sent[clear_index + 1:] if item["event"] == "media")
    return {
        "scenario": name, "passed": True,
        "turn_count": len(turns), "frame_count": len(frames), "frame_bytes": 3200,
        "input_pcm16k_bytes": r.stt.input_bytes,
        "booking_count": len(r.bookings), "action_statuses": [row["status"] for row in r.actions_rows],
        "tool_choices": r.llm.choices, "barge_in_count": len(r.session.metrics["barge_in"]),
        "tts_cancel_count": r.tts.cancel_count,
        "spoken_success": any("demo is booked" in text.casefold() for text in r.tts.spoken),
        "stt_stub_completion_ms": r.stt.completion_ms,
        "tool_events": r.events.tool_events,
        "local_trace": projection,
        "qualitative": {
            "response_relevance": "scripted_assertion_passed",
            "groundedness": "synthetic_fixture_only",
            "fake_capability_claim": "not_observed_in_scripted_output",
            "confirmation_clarity": (
                "asserted" if name in {"happy_path", "negative_confirmation", "ambiguous_confirmation",
                                       "duplicate_confirmation", "stale_slot", "confirmation_barge_in"}
                else "not_applicable"
            ),
            "interruption_handling": (
                "asserted" if name in {"ordinary_barge_in", "confirmation_barge_in"}
                else "not_applicable"
            ),
            "repetition_or_awkwardness": "not_human_rated",
            "task_continuity": "scripted_assertion_passed" if name not in {"stt_failure", "tts_failure"}
                               else "provider_failure_terminates_turn",
        },
    }


SCENARIOS = (
    "happy_path", "negative_confirmation", "ambiguous_confirmation",
    "duplicate_confirmation", "stale_slot", "lead_not_found", "tool_failure",
    "llm_failure", "stt_failure", "tts_failure", "ordinary_barge_in",
    "confirmation_barge_in",
)


async def run_all():
    results = []
    with tempfile.TemporaryDirectory() as directory:
        for scenario in SCENARIOS:
            try:
                result = await run_scenario(scenario, Path(directory) / scenario)
            except Exception as error:
                result = {"scenario": scenario, "passed": False, "failure_type": type(error).__name__}
            results.append(result)
    stages = {
        "stt_stub_completion": [value for row in results if row["passed"] for value in row["stt_stub_completion_ms"]],
        "llm_first_token": [turn["llm_ttft_ms"] for row in results if row["passed"]
                            for turn in row["local_trace"]["turns"] if "llm_ttft_ms" in turn],
        "tool_execution": [event["duration_ms"] for row in results if row["passed"]
                           for event in row["tool_events"] if event["event"] == "tool.succeeded"],
        "confirmed_action_execution": [event["duration_ms"] for row in results if row["passed"]
                                       for event in row["tool_events"] if event["event"] == "tool.committed"],
        "tts_first_pcm": [turn["first_tts_ttfa_ms"] for row in results if row["passed"]
                          for turn in row["local_trace"]["turns"] if "first_tts_ttfa_ms" in turn],
        "final_transcript_to_first_carrier_audio": [
            turn["final_transcript_to_first_audio_sent_ms"] for row in results if row["passed"]
            for turn in row["local_trace"]["turns"]
            if "final_transcript_to_first_audio_sent_ms" in turn
        ],
        "last_vad_speech_to_first_carrier_audio": [
            turn["last_vad_speech_to_first_audio_sent_ms"] for row in results if row["passed"]
            for turn in row["local_trace"]["turns"]
            if "last_vad_speech_to_first_audio_sent_ms" in turn
        ],
    }
    return {
        "schema_version": 1, "validation_level": "A_deterministic_synthetic_voice_path",
        "carrier": "exotel_shaped_loopback_not_pstn", "providers": "deterministic_interface_stubs",
        "frame_format": {"sample_rate_hz": 8000, "sample_width_bits": 16,
                         "channels": 1, "bytes_per_frame": 3200, "ms_per_frame": 200},
        "scenarios": results,
        "summary": {"count": len(results), "passed": sum(row["passed"] for row in results)},
        "stage_latency_ms": {key: stage_stats(values) for key, values in stages.items()},
        "latency_boundary": "server-side synthetic loopback only; not mouth-to-ear",
    }


if __name__ == "__main__":
    logging.getLogger("omnivoice.media").setLevel(logging.ERROR)
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    evidence = asyncio.run(run_all())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence["summary"]))
    raise SystemExit(0 if evidence["summary"]["passed"] == evidence["summary"]["count"] else 1)
