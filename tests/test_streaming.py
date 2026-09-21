import asyncio
import base64
import json
import time
from types import SimpleNamespace

import pytest

from omnivoice.config import Settings
from omnivoice.duplex import CancelReason
from omnivoice.models import Transcript
from omnivoice.providers import SarvamSTT, SarvamTTS
from omnivoice.session import CallSession
from omnivoice.transport import MediaTransport


class ProviderSocket:
    def __init__(self, incoming):
        self.incoming = iter(incoming)
        self.sent = []
        self.closed = False

    async def send(self, message):
        self.sent.append(json.loads(message))

    async def recv(self):
        return json.dumps(next(self.incoming))

    async def close(self):
        self.closed = True

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return json.dumps(next(self.incoming))
        except StopIteration:
            raise StopAsyncIteration from None


async def test_sarvam_realtime_interims_and_finals():
    provider = SarvamSTT(Settings(_env_file=None))
    provider.ws = ProviderSocket(
        [
            {"event": "transcript.partial", "text": "hello", "language": "en-IN"},
            {"event": "transcript.final", "text": "hello there", "language": "en-IN"},
        ]
    )
    await provider.send(b"\0\0")
    assert provider.ws.sent[0]["event"] == "audio_input"
    events = []
    with pytest.raises(ConnectionError):
        async for event in provider.events():
            events.append(event)
    assert [e.final for e in events] == [False, True]
    assert events[-1].text == "hello there"


async def test_sarvam_tts_reuses_socket_and_requires_raw_pcm():
    provider = SarvamTTS(Settings(_env_file=None), "en-IN")
    provider.active = ProviderSocket(
        [
            {
                "type": "audio",
                "data": {"content_type": "audio/pcm", "audio": base64.b64encode(b"\0" * 320).decode()},
            },
            {"type": "event", "data": {"event_type": "final"}},
        ]
    )
    output = [frame async for frame in provider.speak("Test-only utterance.")]
    assert len(output[0]) == 320
    assert [event["type"] for event in provider.active.sent] == ["text", "flush"]
    socket = provider.active
    await provider.cancel()
    assert socket.closed and provider.active is None


async def test_tts_rejects_encoded_audio_on_raw_telephony_path():
    provider = SarvamTTS(Settings(_env_file=None), "en-IN")
    provider.active = ProviderSocket(
        [{"type": "audio", "data": {"content_type": "audio/mp3", "audio": "AAAA"}}]
    )
    with pytest.raises(ValueError, match="raw PCM"):
        async for _ in provider.speak("Test"):
            pass


async def test_audio_dispatch_stops_mid_chunk_on_barge_in():
    class Socket:
        def __init__(self):
            self.sent = []

        async def send_json(self, value):
            self.sent.append(value)

    socket = Socket()
    transport = MediaTransport(socket, "twilio", "MZtest")
    task = asyncio.create_task(transport.audio(b"\0" * 6400, 0))
    await asyncio.sleep(0.035)
    await transport.clear()
    await task
    events = [item["event"] for item in socket.sent]
    assert events[-1] == "clear"
    assert len(events) < 20


async def test_audio_and_transcripts_continue_during_speech(monkeypatch):
    class STT:
        def __init__(self, *_):
            self.queue = asyncio.Queue()
            self.bytes = 0

        async def open(self):
            pass

        async def close(self):
            pass

        async def send(self, frame):
            self.bytes += len(frame)

        async def events(self):
            while True:
                yield await self.queue.get()

    class TTS:
        def __init__(self, *_):
            self.cancelled = False

        async def open(self):
            pass

        async def close(self):
            pass

        async def cancel(self):
            self.cancelled = True

        async def speak(self, text):
            for _ in range(100):
                await asyncio.sleep(0.002)
                yield b"\0" * 320

    class Socket:
        def __init__(self):
            self.queue = asyncio.Queue()
            self.sent = []

        async def receive_json(self):
            return await self.queue.get()

        async def send_json(self, item):
            self.sent.append(item)

    class VAD:
        def process(self, _):
            return [0.95]

    async def noop(*args):
        pass

    monkeypatch.setattr("omnivoice.session.SarvamSTT", STT)
    monkeypatch.setattr("omnivoice.session.SarvamTTS", TTS)
    settings = Settings(_env_file=None)
    services = SimpleNamespace(
        settings=settings,
        vad=SimpleNamespace(session=VAD),
        knowledge=SimpleNamespace(refresh=noop),
        actions=SimpleNamespace(cancel=noop),
    )
    tenant = {
        "id": "t",
        "config": {"language": "en-IN", "greeting": "Test greeting", "backchannels": ["yeah"]},
    }
    socket = Socket()
    session = CallSession("call", tenant, MediaTransport(socket, "exotel", "stream"), services)
    session.last_prediction = time.monotonic() + 100
    task = asyncio.create_task(session.run())
    try:
        await asyncio.sleep(0.05)
        await socket.queue.put(
            {"event": "media", "media": {"payload": base64.b64encode(b"\0" * 640).decode()}}
        )
        await asyncio.sleep(0.025)
        assert session.stt.bytes > 0
        await session.stt.queue.put(Transcript(text="wait stop", final=False))
        await asyncio.sleep(0.06)
        assert any(item["event"] == "clear" for item in socket.sent)
        assert session.tts.cancelled
        clear_index = next(i for i, item in enumerate(socket.sent) if item["event"] == "clear")
        assert not any(item["event"] == "media" for item in socket.sent[clear_index + 1 :])
    finally:
        await socket.queue.put({"event": "stop"})
        await asyncio.wait_for(task, 2)


async def test_turn_metrics_persist_user_transcript_and_agent_response(monkeypatch):
    class MockTTS:
        def __init__(self, *_):
            pass

        async def speak(self, text):
            yield b"\0" * 320

        async def cancel(self):
            pass

        async def close(self):
            pass

    class MockSocket:
        def __init__(self):
            self.sent = []

        async def send_json(self, item):
            self.sent.append(item)

    async def mock_confirm(*args, **kwargs):
        return None

    async def mock_cancel(*args, **kwargs):
        pass

    async def mock_fast_answer(tenant_id, text):
        if text == "cached question":
            return "Cached business answer.", "exact", 1.5
        return None, "miss", 0.1

    async def mock_retrieve(tenant_id, text):
        return [{"title": "Doc", "text": "OmniVoice details"}]

    async def mock_tools(tenant_id):
        return []

    async def mock_llm_stream(messages, tools):
        for chunk in ["OmniVoice is ", "a telephone ", "voice platform."]:
            yield {"content": chunk}

    monkeypatch.setattr("omnivoice.session.SarvamTTS", MockTTS)
    services = SimpleNamespace(
        settings=Settings(_env_file=None),
        actions=SimpleNamespace(confirm=mock_confirm, cancel=mock_cancel, tools=mock_tools),
        knowledge=SimpleNamespace(fast_answer=mock_fast_answer, retrieve=mock_retrieve),
        llm=SimpleNamespace(stream=mock_llm_stream),
        vad=SimpleNamespace(session=lambda: None),
    )
    tenant = {
        "id": "tenant-1",
        "config": {
            "language": "en-IN",
            "greeting": "Hi",
            "instructions": "Be helpful.",
            "confirmation_phrases": ["yes confirm"],
            "backchannels": ["yeah"],
        },
    }
    socket = MockSocket()
    session = CallSession("call-1", tenant, MediaTransport(socket, "exotel", "stream-1"), services)

    # Turn 1: fast answer cache hit
    await session.respond("cached question", time.perf_counter())
    assert len(session.metrics["turns"]) == 1
    t1 = session.metrics["turns"][0]
    assert t1["user_transcript"] == "cached question"
    assert t1["agent_response"] == "Cached business answer."
    assert t1["cache"] == "exact"

    # Turn 2: LLM streamed generation
    await session.respond("What is OmniVoice?", time.perf_counter())
    assert len(session.metrics["turns"]) == 2
    t2 = session.metrics["turns"][1]
    assert t2["user_transcript"] == "What is OmniVoice?"
    assert t2["agent_response"] == "OmniVoice is a telephone voice platform."
    assert t2["cache"] == "miss"
    assert "llm_first_token_ms" in t2


async def test_interrupted_turn_preserves_partial_response_and_valid_metric_structure(monkeypatch):
    class MockTTS:
        def __init__(self, *_):
            pass

        async def speak(self, text):
            while True:
                await asyncio.sleep(0.01)
                yield b"\0" * 320

        async def cancel(self):
            pass

        async def close(self):
            pass

    class MockSocket:
        def __init__(self):
            self.sent = []

        async def send_json(self, item):
            self.sent.append(item)

    async def mock_confirm(*args, **kwargs):
        return None

    async def mock_cancel(*args, **kwargs):
        pass

    async def mock_fast_answer(tenant_id, text):
        return None, "miss", 0.1

    async def mock_retrieve(tenant_id, text):
        return []

    async def mock_tools(tenant_id):
        return []

    async def mock_llm_stream(messages, tools):
        yield {"content": "Initial partial sentence. "}
        yield {"content": "Second sentence that gets "}
        await asyncio.sleep(1.0)
        yield {"content": "interrupted."}

    monkeypatch.setattr("omnivoice.session.SarvamTTS", MockTTS)
    services = SimpleNamespace(
        settings=Settings(_env_file=None),
        actions=SimpleNamespace(confirm=mock_confirm, cancel=mock_cancel, tools=mock_tools),
        knowledge=SimpleNamespace(fast_answer=mock_fast_answer, retrieve=mock_retrieve),
        llm=SimpleNamespace(stream=mock_llm_stream),
        vad=SimpleNamespace(session=lambda: None),
    )
    tenant = {
        "id": "tenant-1",
        "config": {
            "language": "en-IN",
            "greeting": "Hi",
            "instructions": "Be helpful.",
            "confirmation_phrases": ["yes confirm"],
            "backchannels": ["yeah"],
        },
    }
    socket = MockSocket()
    session = CallSession("call-2", tenant, MediaTransport(socket, "exotel", "stream-2"), services)

    # Launch respond as a task and cancel it after partial text is produced
    task = asyncio.create_task(session.respond("Tell me a long story", time.perf_counter()))
    await asyncio.sleep(0.05)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert len(session.metrics["turns"]) == 1
    t = session.metrics["turns"][0]
    assert t["user_transcript"] == "Tell me a long story"
    assert t["agent_response"] == "Initial partial sentence. Second sentence that gets "
    assert t["interrupted"] is True
    assert "started" not in t
    assert "last_voice" not in t
    assert isinstance(t["agent_response"], str)
    assert isinstance(t["user_transcript"], str)


async def test_tool_calls_preserve_response_accumulation(monkeypatch):
    class MockTTS:
        def __init__(self, *_):
            pass

        async def speak(self, text):
            yield b"\0" * 320

        async def cancel(self):
            pass

        async def close(self):
            pass

    class MockSocket:
        def __init__(self):
            self.sent = []

        async def send_json(self, item):
            self.sent.append(item)

    async def mock_confirm(*args, **kwargs):
        return None

    async def mock_cancel(*args, **kwargs):
        pass

    async def mock_fast_answer(tenant_id, text):
        return None, "miss", 0.1

    async def mock_retrieve(tenant_id, text):
        return []

    tools_list = [
        {"name": "book_slot", "kind": "write", "description": "Book a slot", "parameters": {}},
        {"name": "check_status", "kind": "read", "description": "Check status", "parameters": {}},
    ]

    async def mock_tools(tenant_id):
        return tools_list

    async def mock_get_tool(tenant_id, name):
        return next(t for t in tools_list if t["name"] == name)

    async def mock_stage(tenant_id, call_id, name, args):
        return {"id": "action-1", "summary": "Reserve slot 9 AM."}

    async def mock_read(tenant_id, name, args):
        return {"status": "available"}

    # Test 1: write tool with preamble
    async def mock_llm_write(messages, tools):
        if tools:
            yield {"content": "I can help with that. "}
            yield {
                "tool_calls": [
                    {
                        "index": 0,
                        "function": {"name": "book_slot", "arguments": '{"slot":"9am"}'},
                    }
                ]
            }

    monkeypatch.setattr("omnivoice.session.SarvamTTS", MockTTS)
    services = SimpleNamespace(
        settings=Settings(_env_file=None),
        actions=SimpleNamespace(
            confirm=mock_confirm,
            cancel=mock_cancel,
            tools=mock_tools,
            get_tool=mock_get_tool,
            stage=mock_stage,
            read=mock_read,
        ),
        knowledge=SimpleNamespace(fast_answer=mock_fast_answer, retrieve=mock_retrieve),
        llm=SimpleNamespace(stream=mock_llm_write),
        vad=SimpleNamespace(session=lambda: None),
    )
    tenant = {
        "id": "tenant-1",
        "config": {
            "language": "en-IN",
            "greeting": "Hi",
            "instructions": "Be helpful.",
            "confirmation_phrases": ["yes confirm"],
            "backchannels": ["yeah"],
        },
    }
    session = CallSession("call-write", tenant, MediaTransport(MockSocket(), "exotel", "s"), services)
    await session.respond("Book slot for me", time.perf_counter())
    assert len(session.metrics["turns"]) == 1
    t_write = session.metrics["turns"][0]
    assert t_write["user_transcript"] == "Book slot for me"
    assert "I can help with that." in t_write["agent_response"]
    assert 'Reserve slot 9 AM. To confirm, say: "yes confirm".' in t_write["agent_response"]

    # Test 2: read tool with preamble and recursive answer
    async def mock_llm_read(messages, tools):
        if tools:
            yield {"content": "Let me check the status. "}
            yield {
                "tool_calls": [
                    {
                        "index": 0,
                        "function": {"name": "check_status", "arguments": "{}"},
                    }
                ]
            }
        else:
            yield {"content": "The slot is available."}

    services.llm = SimpleNamespace(stream=mock_llm_read)
    session2 = CallSession("call-read", tenant, MediaTransport(MockSocket(), "exotel", "s"), services)
    await session2.respond("Check my status", time.perf_counter())
    assert len(session2.metrics["turns"]) == 1
    t_read = session2.metrics["turns"][0]
    assert t_read["user_transcript"] == "Check my status"
    assert t_read["agent_response"] == "Let me check the status. The slot is available."


async def test_playback_barge_in_wait_and_stop_sends_exactly_one_clear(monkeypatch):
    class MockSTT:
        def __init__(self, *_):
            self.queue = asyncio.Queue()
            self.bytes = 0

        async def open(self):
            pass

        async def close(self):
            pass

        async def send(self, frame):
            self.bytes += len(frame)

        async def events(self):
            while True:
                yield await self.queue.get()

    class MockTTS:
        def __init__(self, *_):
            self.cancelled = False

        async def open(self):
            pass

        async def close(self):
            pass

        async def cancel(self):
            self.cancelled = True

        async def speak(self, text):
            for _ in range(50):
                await asyncio.sleep(0.01)
                yield b"\0" * 320

    class MockSocket:
        def __init__(self):
            self.queue = asyncio.Queue()
            self.sent = []

        async def receive_json(self):
            return await self.queue.get()

        async def send_json(self, item):
            self.sent.append(item)

    class MockVAD:
        def process(self, _):
            return [0.95]

    async def noop(*args, **kwargs):
        pass

    monkeypatch.setattr("omnivoice.session.SarvamSTT", MockSTT)
    monkeypatch.setattr("omnivoice.session.SarvamTTS", MockTTS)

    for halt_word in ["Wait", "Stop"]:
        services = SimpleNamespace(
            settings=Settings(_env_file=None),
            vad=SimpleNamespace(session=MockVAD),
            knowledge=SimpleNamespace(refresh=noop),
            actions=SimpleNamespace(cancel=noop),
        )
        tenant = {
            "id": "tenant-test",
            "config": {"language": "en-IN", "greeting": "Hello caller", "backchannels": ["yeah"]},
        }
        sock = MockSocket()
        session = CallSession("call-halt", tenant, MediaTransport(sock, "exotel", "stream-1"), services)
        session.last_prediction = time.monotonic() + 100
        task = asyncio.create_task(session.run())
        try:
            await asyncio.sleep(0.04)
            # Provide VAD frame so session.fsm.candidate becomes True during greeting playback
            await sock.queue.put({"event": "media", "media": {"payload": base64.b64encode(b"\0" * 640).decode()}})
            await asyncio.sleep(0.02)
            assert session.fsm.playing is True

            # Send halt command during active playback
            await session.stt.queue.put(Transcript(text=halt_word, final=False))
            await asyncio.sleep(0.05)

            # Verification: exactly one clear frame, TTS cancelled, barge-in metric logged
            clear_events = [item for item in sock.sent if item.get("event") == "clear"]
            assert len(clear_events) == 1
            assert session.tts.cancelled is True
            assert len(session.metrics["barge_in"]) == 1
        finally:
            await sock.queue.put({"event": "stop"})
            await asyncio.wait_for(task, 2)


async def test_playback_backchannel_yeah_suppressed_no_clear(monkeypatch):
    class MockSTT:
        def __init__(self, *_):
            self.queue = asyncio.Queue()

        async def open(self):
            pass

        async def close(self):
            pass

        async def send(self, frame):
            pass

        async def events(self):
            while True:
                yield await self.queue.get()

    class MockTTS:
        def __init__(self, *_):
            self.cancelled = False

        async def open(self):
            pass

        async def close(self):
            pass

        async def cancel(self):
            self.cancelled = True

        async def speak(self, text):
            for _ in range(50):
                await asyncio.sleep(0.01)
                yield b"\0" * 320

    class MockSocket:
        def __init__(self):
            self.queue = asyncio.Queue()
            self.sent = []

        async def receive_json(self):
            return await self.queue.get()

        async def send_json(self, item):
            self.sent.append(item)

    class MockVAD:
        def process(self, _):
            return [0.95]

    async def noop(*args, **kwargs):
        pass

    monkeypatch.setattr("omnivoice.session.SarvamSTT", MockSTT)
    monkeypatch.setattr("omnivoice.session.SarvamTTS", MockTTS)

    services = SimpleNamespace(
        settings=Settings(_env_file=None),
        vad=SimpleNamespace(session=MockVAD),
        knowledge=SimpleNamespace(refresh=noop),
        actions=SimpleNamespace(cancel=noop),
    )
    tenant = {
        "id": "tenant-test",
        "config": {"language": "en-IN", "greeting": "Hello caller", "backchannels": ["yeah", "mm hmm"]},
    }
    sock = MockSocket()
    session = CallSession("call-bc", tenant, MediaTransport(sock, "exotel", "stream-1"), services)
    session.last_prediction = time.monotonic() + 100
    task = asyncio.create_task(session.run())
    try:
        await asyncio.sleep(0.04)
        await sock.queue.put({"event": "media", "media": {"payload": base64.b64encode(b"\0" * 640).decode()}})
        await asyncio.sleep(0.02)
        assert session.fsm.playing is True

        # Send backchannel "yeah" during active playback
        await session.stt.queue.put(Transcript(text="yeah", final=False))
        await asyncio.sleep(0.05)

        # Verification: NO clear sent, playback continues, TTS NOT cancelled
        clear_events = [item for item in sock.sent if item.get("event") == "clear"]
        assert len(clear_events) == 0
        assert session.tts.cancelled is False
        assert len(session.metrics["barge_in"]) == 0
    finally:
        await sock.queue.put({"event": "stop"})
        await asyncio.wait_for(task, 2)


async def test_fragmented_utterance_coalescing_and_superseded_invariants(monkeypatch):
    class MockSocket:
        def __init__(self):
            self.sent = []

        async def send_json(self, item):
            self.sent.append(item)

    class MockTTS:
        def __init__(self, *_):
            pass

        async def speak(self, text):
            yield b"\0" * 320

        async def cancel(self):
            pass

    async def mock_llm_stream(messages, tools):
        # Simulate LLM generation delay of 100ms
        await asyncio.sleep(0.1)
        yield {"content": "I can help with booking."}

    async def noop(*args, **kwargs):
        pass

    async def mock_fast_answer(*args, **kwargs):
        return None, "miss", 0.1

    async def mock_retrieve(*args, **kwargs):
        return []

    services = SimpleNamespace(
        settings=Settings(_env_file=None),
        actions=SimpleNamespace(confirm=noop, cancel=noop, tools=noop),
        knowledge=SimpleNamespace(fast_answer=mock_fast_answer, retrieve=mock_retrieve),
        llm=SimpleNamespace(stream=mock_llm_stream),
        vad=SimpleNamespace(session=lambda: None),
    )
    tenant = {
        "id": "tenant-test",
        "config": {
            "language": "en-IN",
            "greeting": "Hi",
            "instructions": "",
            "confirmation_phrases": ["yes"],
            "backchannels": ["yeah"],
            "continuation_interval_ms": 750,
        },
    }
    sock = MockSocket()
    session = CallSession("call-frag", tenant, MediaTransport(sock, "exotel", "s"), services)
    session.tts = MockTTS()

    async def event_generator():
        yield Transcript(text="Book me", final=True)
        await asyncio.sleep(0.03)  # Within 750ms continuation window
        yield Transcript(text="Uh, dedicate.", final=True)

    session.stt = SimpleNamespace(events=event_generator)
    transcripts_task = asyncio.create_task(session.transcripts())
    await asyncio.sleep(0.05)
    await transcripts_task
    # Await active response completion
    if session.response:
        await session.response

    # Verify invariants:
    # 1. Exactly one turn in metrics
    assert len(session.metrics["turns"]) == 1
    t = session.metrics["turns"][0]
    # 2. Coalesced text
    assert t["user_transcript"] == "Book me Uh, dedicate."
    assert t["agent_response"] == "I can help with booking."
    # 3. Not marked interrupted
    assert t.get("interrupted") is not True
    # 4. No carrier clear sent
    assert not any(item.get("event") == "clear" for item in sock.sent)
    # 5. No barge-in metrics logged
    assert len(session.metrics["barge_in"]) == 0
    # 6. Clean history (no orphan "Book me" entry)
    user_messages = [m for m in session.history if m["role"] == "user"]
    assert len(user_messages) == 1
    assert user_messages[0]["content"] == "Book me Uh, dedicate."


async def test_control_intent_during_generation_halts_cleanly(monkeypatch):
    class MockSocket:
        def __init__(self):
            self.sent = []

        async def send_json(self, item):
            self.sent.append(item)

    def make_services(llm_stream=None, fast_answer=None):
        async def mock_confirm(*args, **kwargs):
            return None

        async def mock_cancel(*args, **kwargs):
            pass

        async def mock_tools(tenant_id):
            return []

        async def mock_retrieve(tenant_id, text):
            return []

        async def default_fast_answer(*args, **kwargs):
            return None, "miss", 0.1

        return SimpleNamespace(
            settings=Settings(_env_file=None),
            actions=SimpleNamespace(confirm=mock_confirm, cancel=mock_cancel, tools=mock_tools),
            knowledge=SimpleNamespace(
                fast_answer=fast_answer or default_fast_answer,
                retrieve=mock_retrieve,
                refresh=mock_cancel,
            ),
            llm=SimpleNamespace(stream=llm_stream or (lambda m, t: iter([]))),
            vad=SimpleNamespace(session=lambda: None),
        )

    class MockTTS:
        def __init__(self, *_):
            pass

        async def speak(self, text):
            yield b"\0" * 320

        async def cancel(self):
            pass

    async def mock_slow_llm(messages, tools):
        await asyncio.sleep(0.2)
        yield {"content": "This should not be delivered."}

    async def mock_fast_llm(messages, tools):
        yield {"content": "Pricing is 10 dollars."}

    tenant = {
        "id": "tenant-test",
        "config": {
            "language": "en-IN",
            "greeting": "Hi",
            "instructions": "",
            "confirmation_phrases": ["yes"],
            "backchannels": ["yeah"],
        },
    }

    for control_word in ["Wait", "Stop", "Hold on", "Pause", "Cancel"]:
        services = make_services(llm_stream=mock_slow_llm)
        sock = MockSocket()
        session = CallSession("call-ctrl", tenant, MediaTransport(sock, "exotel", "s"), services)
        session.tts = MockTTS()

        async def event_generator():
            yield Transcript(text="What is OmniVoice?", final=True)
            await asyncio.sleep(0.02)  # During generation before playback
            yield Transcript(text=control_word, final=True)

        session.stt = SimpleNamespace(events=event_generator)
        await session.transcripts()
        await asyncio.sleep(0.05)

        # Invariants:
        # 1. Pending generation cancelled cleanly, no turns recorded
        assert len(session.metrics["turns"]) == 0
        # 2. No clear frame sent
        assert not any(item.get("event") == "clear" for item in sock.sent)
        # 3. No barge-in logged
        assert len(session.metrics["barge_in"]) == 0
        # 4. No pending response
        assert session.response is None or session.response.done()
        # 5. History has no orphan question
        assert len(session.history) == 0

        # Verify session remains usable for subsequent inquiry
        services.llm.stream = mock_fast_llm
        await session.respond("Tell me pricing", time.perf_counter())
        assert len(session.metrics["turns"]) == 1
        assert session.metrics["turns"][0]["user_transcript"] == "Tell me pricing"
        assert session.metrics["turns"][0]["agent_response"] == "Pricing is 10 dollars."


async def test_ordinary_complete_question_begins_immediately():
    class MockSocket:
        def __init__(self):
            self.sent = []

        async def send_json(self, item):
            self.sent.append(item)

    class MockTTS:
        def __init__(self, *_):
            pass

        async def speak(self, text):
            yield b"\0" * 320

        async def cancel(self):
            pass

    async def mock_llm(messages, tools):
        yield {"content": "OmniVoice is ready."}

    async def mock_confirm(*args, **kwargs):
        return None

    async def mock_cancel(*args, **kwargs):
        pass

    async def mock_tools(tenant_id):
        return []

    async def mock_retrieve(tenant_id, text):
        return []

    async def mock_fast_answer(*args, **kwargs):
        return None, "miss", 0.1

    services = SimpleNamespace(
        settings=Settings(_env_file=None),
        actions=SimpleNamespace(confirm=mock_confirm, cancel=mock_cancel, tools=mock_tools),
        knowledge=SimpleNamespace(fast_answer=mock_fast_answer, retrieve=mock_retrieve),
        llm=SimpleNamespace(stream=mock_llm),
        vad=SimpleNamespace(session=lambda: None),
    )
    tenant = {
        "id": "tenant-test",
        "config": {
            "language": "en-IN",
            "greeting": "Hi",
            "instructions": "",
            "confirmation_phrases": ["yes"],
            "backchannels": ["yeah"],
        },
    }
    sock = MockSocket()
    session = CallSession("call-norm", tenant, MediaTransport(sock, "exotel", "s"), services)
    session.tts = MockTTS()

    started_at = time.perf_counter()

    async def event_generator():
        yield Transcript(text="What is OmniVoice?", final=True)

    session.stt = SimpleNamespace(events=event_generator)
    await session.transcripts()
    if session.response:
        await session.response

    # Immediate start: response was created and completed without debounce penalty
    elapsed = time.perf_counter() - started_at
    assert elapsed < 0.5
    assert len(session.metrics["turns"]) == 1
    assert session.metrics["turns"][0]["user_transcript"] == "What is OmniVoice?"
    assert session.metrics["turns"][0]["agent_response"] == "OmniVoice is ready."


async def test_genuine_later_caller_turn_is_separate_and_bounded():
    class MockSocket:
        def __init__(self):
            self.sent = []

        async def send_json(self, item):
            self.sent.append(item)

    class MockTTS:
        def __init__(self, *_):
            pass

        async def speak(self, text):
            yield b"\0" * 320

        async def cancel(self):
            pass

    async def mock_llm(messages, tools):
        user_msg = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        yield {"content": f"Answer to {user_msg}"}

    async def mock_confirm(*args, **kwargs):
        return None

    async def mock_cancel(*args, **kwargs):
        pass

    async def mock_tools(tenant_id):
        return []

    async def mock_retrieve(tenant_id, text):
        return []

    async def mock_fast_answer(*args, **kwargs):
        return None, "miss", 0.1

    services = SimpleNamespace(
        settings=Settings(_env_file=None),
        actions=SimpleNamespace(confirm=mock_confirm, cancel=mock_cancel, tools=mock_tools),
        knowledge=SimpleNamespace(fast_answer=mock_fast_answer, retrieve=mock_retrieve),
        llm=SimpleNamespace(stream=mock_llm),
        vad=SimpleNamespace(session=lambda: None),
    )
    tenant = {
        "id": "tenant-test",
        "config": {
            "language": "en-IN",
            "greeting": "Hi",
            "instructions": "",
            "confirmation_phrases": ["yes"],
            "backchannels": ["yeah"],
            "continuation_interval_ms": 100,  # 100ms window
        },
    }
    sock = MockSocket()
    session = CallSession("call-multi", tenant, MediaTransport(sock, "exotel", "s"), services)
    session.tts = MockTTS()

    # Part A: Two sequential distinct turns after playback completion
    await session.respond("First question", time.perf_counter(), 1)
    session.fsm.played()  # Carrier mark arrived, audio finished
    await session.respond("Second question", time.perf_counter(), 2)

    assert len(session.metrics["turns"]) == 2
    assert session.metrics["turns"][0]["user_transcript"] == "First question"
    assert session.metrics["turns"][1]["user_transcript"] == "Second question"

    # Part B: Continuation interval expired during generation -> new turn supersedes without concatenation
    async def slow_llm(messages, tools):
        await asyncio.sleep(0.2)
        yield {"content": "Slow answer"}

    services.llm.stream = slow_llm
    session_b = CallSession("call-b", tenant, MediaTransport(sock, "exotel", "s"), services)
    session_b.tts = MockTTS()

    async def event_generator():
        yield Transcript(text="Initial question", final=True)
        # Wait longer than continuation_interval_ms (100ms)
        await asyncio.sleep(0.12)
        yield Transcript(text="Actually tell me pricing", final=True)

    session_b.stt = SimpleNamespace(events=event_generator)
    await session_b.transcripts()
    if session_b.response:
        await session_b.response

    assert len(session_b.metrics["turns"]) == 1
    # Bounded continuation: NOT concatenated because interval expired
    assert session_b.metrics["turns"][0]["user_transcript"] == "Actually tell me pricing"


async def test_stale_cancelled_generation_cannot_corrupt_newer_session_state():
    class MockSocket:
        def __init__(self):
            self.sent = []

        async def send_json(self, item):
            self.sent.append(item)

    class MockTTS:
        def __init__(self, *_):
            pass

        async def speak(self, text):
            yield b"\0" * 320

        async def cancel(self):
            pass

    task1_done = asyncio.Event()

    async def mock_llm(messages, tools):
        user_msg = messages[-1]["content"]
        if user_msg == "First":
            try:
                await asyncio.sleep(1.0)
            finally:
                task1_done.set()
        yield {"content": f"Answer to {user_msg}"}

    async def mock_confirm(*args, **kwargs):
        return None

    async def mock_cancel(*args, **kwargs):
        pass

    async def mock_tools(tenant_id):
        return []

    async def mock_retrieve(tenant_id, text):
        return []

    async def mock_fast_answer(*args, **kwargs):
        return None, "miss", 0.1

    services = SimpleNamespace(
        settings=Settings(_env_file=None),
        actions=SimpleNamespace(confirm=mock_confirm, cancel=mock_cancel, tools=mock_tools),
        knowledge=SimpleNamespace(fast_answer=mock_fast_answer, retrieve=mock_retrieve),
        llm=SimpleNamespace(stream=mock_llm),
        vad=SimpleNamespace(session=lambda: None),
    )
    tenant = {
        "id": "tenant-test",
        "config": {
            "language": "en-IN",
            "greeting": "Hi",
            "instructions": "",
            "confirmation_phrases": ["yes"],
            "backchannels": ["yeah"],
        },
    }
    session = CallSession("call-gen", tenant, MediaTransport(MockSocket(), "exotel", "s"), services)
    session.tts = MockTTS()

    # Launch Task 1 (gen_id=1)
    task1 = asyncio.create_task(session.respond("First", time.perf_counter(), 1))
    await asyncio.sleep(0.02)
    assert session.active_generation_id == 1

    # Launch Task 2 (gen_id=2) and supersede Task 1
    session.cancellation_reasons[1] = CancelReason.SUPERSEDED
    task1.cancel()
    task2 = asyncio.create_task(session.respond("Second", time.perf_counter(), 2))
    await asyncio.sleep(0.01)
    assert session.active_generation_id == 2

    await task1_done.wait()
    # Task 1 finally block ran, but must not overwrite Task 2's active generation
    assert session.active_generation_id == 2
    await task2

    # Exactly one turn persisted (Task 2)
    assert len(session.metrics["turns"]) == 1
    assert session.metrics["turns"][0]["user_transcript"] == "Second"


async def test_telemetry_persisted_format_compatible_with_store():
    class MockSocket:
        def __init__(self):
            self.sent = []

        async def send_json(self, item):
            self.sent.append(item)

    class MockTTS:
        def __init__(self, *_):
            pass

        async def speak(self, text):
            yield b"\0" * 320

        async def cancel(self):
            pass

    async def mock_llm(messages, tools):
        yield {"content": "Store compatible reply."}

    async def mock_confirm(*args, **kwargs):
        return None

    async def mock_cancel(*args, **kwargs):
        pass

    async def mock_tools(tenant_id):
        return []

    async def mock_retrieve(tenant_id, text):
        return []

    async def mock_fast_answer(*args, **kwargs):
        return None, "miss", 0.1

    services = SimpleNamespace(
        settings=Settings(_env_file=None),
        actions=SimpleNamespace(confirm=mock_confirm, cancel=mock_cancel, tools=mock_tools),
        knowledge=SimpleNamespace(fast_answer=mock_fast_answer, retrieve=mock_retrieve),
        llm=SimpleNamespace(stream=mock_llm),
        vad=SimpleNamespace(session=lambda: None),
    )
    tenant = {
        "id": "tenant-test",
        "config": {
            "language": "en-IN",
            "greeting": "Hi",
            "instructions": "",
            "confirmation_phrases": ["yes"],
            "backchannels": ["yeah"],
        },
    }
    session = CallSession("call-tel", tenant, MediaTransport(MockSocket(), "exotel", "s"), services)
    session.tts = MockTTS()
    await session.respond("Test query", time.perf_counter(), 1)

    # Validate JSON serializability and schema completeness
    serialized = json.dumps(session.metrics)
    data = json.loads(serialized)
    assert "turns" in data
    assert "barge_in" in data
    assert "cache_hits" in data
    assert "errors" in data
    assert len(data["turns"]) == 1
    turn = data["turns"][0]
    assert turn["user_transcript"] == "Test query"
    assert turn["agent_response"] == "Store compatible reply."
    assert "cache" in turn
    assert "retrieval_ms" in turn
