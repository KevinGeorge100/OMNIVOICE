import asyncio
import json

import numpy as np
import pytest

from omnivoice.actions import ActionEngine, validate_tool
from omnivoice.audio import Upsample8k, mulaw_decode, mulaw_encode
from omnivoice.duplex import FlexDuo, State
from omnivoice.evaluation import evaluate
from omnivoice.rag import Knowledge
from omnivoice.store import Store
from omnivoice.transport import MediaTransport


@pytest.fixture
async def store(tmp_path):
    db = Store(tmp_path / "test.db")
    await db.open()
    yield db
    await db.close()


async def tenant(store, name="Test enterprise"):
    return (await store.create_tenant({"name": name}))["id"]


def test_codec_known_silence_and_sign():
    assert mulaw_decode(b"\xff\x7f") == b"\0\0\0\0"
    samples = np.array([-20000, -1000, 0, 1000, 20000], dtype="<i2")
    decoded = np.frombuffer(mulaw_decode(mulaw_encode(samples.tobytes())), dtype="<i2")
    assert np.max(np.abs(samples.astype(int) - decoded)) < 700


def test_resampling_is_packet_boundary_invariant():
    samples = np.array([100, -100, 32000, -32000, 20, 50], dtype="<i2").tobytes()
    whole = Upsample8k().process(samples)
    chunked = Upsample8k()
    assert whole == chunked.process(samples[:4]) + chunked.process(samples[4:])


def test_noise_and_backchannel_do_not_interrupt():
    fsm = FlexDuo(["mm hmm", "yeah"])
    fsm.speaking()
    fsm.voice(0.2)
    assert not fsm.transcript("noise")
    fsm.voice(0.9)
    assert fsm.state == State.IDLE
    assert not fsm.transcript("Yeah.")
    assert fsm.playing
    fsm.voice(0.95)
    assert fsm.transcript("Wait, I need a different date")
    assert fsm.state == State.LISTEN


async def test_knowledge_isolation_approval_and_invalidation(store):
    a, b = await tenant(store, "A"), await tenant(store, "B")
    key = await store.add_knowledge(a, "faq", "Office hours?", "Nine to five", True)
    await store.add_knowledge(b, "faq", "Office hours?", "Never open", True)
    await store.add_knowledge(a, "faq", "Fees?", "Unapproved answer", False)
    rag = Knowledge(store)
    await rag.refresh(a)
    await rag.refresh(b)
    assert (await rag.fast_answer(a, "Office hours?"))[0] == "Nine to five"
    assert (await rag.fast_answer(b, "Office hours?"))[0] == "Never open"
    assert (await rag.fast_answer(a, "Fees?"))[0] is None
    await store.delete_knowledge(a, key)
    rag.invalidate(a)
    assert (await rag.fast_answer(a, "Office hours?"))[0] is None


async def register_write(store, tenant_id):
    tool = {
        "name": "reserve",
        "kind": "write",
        "url": "https://example.com/reserve",
        "description": "Reserve an appointment",
        "parameters": {
            "type": "object",
            "properties": {"slot": {"type": "string"}},
            "required": ["slot"],
            "additionalProperties": False,
        },
        "confirmation_template": "Reserve slot {slot}",
    }
    await store.execute("INSERT INTO tools VALUES (?,?,?)", (tenant_id, "reserve", json.dumps(tool)))


async def test_write_requires_final_confirmation_after_playback_and_is_once(store):
    tid = await tenant(store)
    await register_write(store, tid)
    engine = ActionEngine(store, None)
    executed = []

    async def invoke(tool, arguments, action_id=None):
        executed.append(action_id)
        await asyncio.sleep(0.01)
        return {"ok": True}

    engine.invoke = invoke
    action = await engine.stage(tid, "call-1", "reserve", {"slot": "A"})
    assert not executed
    assert await engine.confirm(tid, "call-1", "yes confirm", True, ["yes confirm"]) is None
    await engine.arm(action["id"], "call-1")
    assert await engine.confirm(tid, "call-1", "yes confirm", False, ["yes confirm"]) is None
    assert (
        await engine.confirm(tid, "call-1", "yes confirm but change the date", True, ["yes confirm"]) is None
    )
    assert await engine.confirm(tid, "other-call", "yes confirm", True, ["yes confirm"]) is None
    results = await asyncio.gather(
        *(engine.confirm(tid, "call-1", "yes confirm", True, ["yes confirm"]) for _ in range(2))
    )
    assert len(executed) == 1
    assert sum(r is not None for r in results) == 1


async def test_cancelled_and_expired_actions_cannot_be_armed(store):
    tid = await tenant(store)
    await register_write(store, tid)
    engine = ActionEngine(store, None)
    action = await engine.stage(tid, "c", "reserve", {"slot": "A"})
    await engine.cancel("c")
    assert not await engine.arm(action["id"], "c")
    action = await engine.stage(tid, "c", "reserve", {"slot": "A"})
    await store.execute("UPDATE actions SET expires=0 WHERE id=?", (action["id"],))
    assert not await engine.arm(action["id"], "c")


async def test_speculation_cannot_execute_write_tools(store):
    tid = await tenant(store)
    await register_write(store, tid)
    with pytest.raises(ValueError, match="read tools"):
        await ActionEngine(store, None).read(tid, "reserve", {"slot": "A"})


async def test_uncertain_external_write_is_not_retried(store):
    tid = await tenant(store)
    await register_write(store, tid)
    engine = ActionEngine(store, None)

    async def fail(*args):
        raise TimeoutError()

    engine.invoke = fail
    action = await engine.stage(tid, "c", "reserve", {"slot": "A"})
    await engine.arm(action["id"], "c")
    assert (await engine.confirm(tid, "c", "confirm", True, ["confirm"]))["status"] == "unknown"
    assert await engine.confirm(tid, "c", "confirm", True, ["confirm"]) is None


def test_confirmation_template_must_disclose_all_arguments():
    with pytest.raises(ValueError):
        validate_tool(
            {
                "kind": "write",
                "parameters": {"type": "object", "properties": {"price": {"type": "number"}}},
                "confirmation_template": "Please confirm",
            }
        )


async def test_clear_invalidates_old_audio_even_if_producer_finishes_late():
    class Socket:
        def __init__(self):
            self.sent = []

        async def send_json(self, value):
            self.sent.append(value)

    socket = Socket()
    transport = MediaTransport(socket, "exotel", "s")
    await transport.clear()
    await transport.audio(b"\0" * 320, 0)
    assert [m["event"] for m in socket.sent] == ["clear"]
    await transport.audio(b"\0" * 320, 1)
    assert socket.sent[-1]["stream_sid"] == "s"


def test_evaluation_uses_weighted_wer_and_labeled_denominators():
    result = evaluate(
        [
            {
                "reference": "one two three",
                "hypothesis": "one three",
                "should_interrupt": False,
                "did_interrupt": True,
                "end_of_speech_to_first_audio_ms": 400,
            },
            {
                "reference": "four",
                "hypothesis": "four",
                "should_interrupt": True,
                "did_interrupt": True,
                "end_of_speech_to_first_audio_ms": 600,
            },
        ]
    )
    assert result["word_error_rate"] == 0.25
    assert result["false_interruption_rate"] == 1
    assert result["missed_interruption_rate"] == 0
    assert result["ttfa_ms"]["p95"] == 600


def test_evaluation_does_not_invent_empty_results():
    result = evaluate([])
    assert result["word_error_rate"] is None
    assert result["ttfa_ms"]["p95"] is None


async def test_call_metrics_sqlite_roundtrip_and_console_compatibility(store):
    tid = await tenant(store)
    call_id = "test-call-telemetry"
    metrics_payload = {
        "turns": [
            {
                "user_transcript": "What is OmniVoice?",
                "agent_response": "OmniVoice is a voice platform.",
                "final_transcript_to_first_audio_sent_ms": 450.2,
                "retrieval_ms": 12.5,
                "interrupted": False,
            },
            {
                "user_transcript": "Wait, one more thing",
                "agent_response": "Sure, go ahead.",
                "final_transcript_to_first_audio_sent_ms": 380.0,
                "interrupted": True,
            },
        ],
        "barge_in": [{"decision_to_clear_sent_ms": 0.5}],
        "greeting_audio_sent": True,
        "greeting_first_audio_ms": 250.0,
    }
    await store.execute(
        "INSERT INTO calls (id, tenant_id, provider, status, started, ended, metrics) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (call_id, tid, "exotel", "completed", 1000.0, 1060.0, json.dumps(metrics_payload)),
    )
    row = await store.one("SELECT * FROM calls WHERE id=?", (call_id,))
    assert row is not None
    loaded_metrics = json.loads(row["metrics"])
    assert len(loaded_metrics["turns"]) == 2
    for orig, loaded in zip(metrics_payload["turns"], loaded_metrics["turns"]):
        assert loaded["user_transcript"] == orig["user_transcript"]
        assert loaded["agent_response"] == orig["agent_response"]
        assert loaded["final_transcript_to_first_audio_sent_ms"] == orig["final_transcript_to_first_audio_sent_ms"]
        assert loaded["interrupted"] == orig["interrupted"]
