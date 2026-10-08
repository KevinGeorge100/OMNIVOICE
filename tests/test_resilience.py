"""Fault injection for bounded provider recovery and call ownership."""

import asyncio
import base64
import json
import time
from types import SimpleNamespace

import httpx
import pytest
from pydantic import ValidationError

from omnivoice.config import Settings
from omnivoice.providers import GnaniSTT, GnaniTTS, Groq, SarvamSTT, SarvamTTS
from omnivoice.resilience import (
    ProviderAuthError,
    ProviderCancelledError,
    ProviderProtocolError,
    ProviderTransientError,
    RetryPolicy,
)
from omnivoice.session import LLM_FAILURE_REPLY, STT_FAILURE_REPLY, CallSession
from omnivoice.transport import MediaTransport


def settings(**overrides):
    values = {
        "sarvam_api_key": "test-sarvam-key",
        "gnani_api_key": "test-gnani-key",
        "groq_api_key": "test-groq-key",
        "provider_max_retries": 2,
        "provider_backoff_base_ms": 1,
        "provider_backoff_max_ms": 4,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


class ScriptSocket:
    def __init__(self, events=()):
        self.events = list(events)
        self.sent = []
        self.closed = False

    async def send(self, value):
        self.sent.append(json.loads(value))

    async def recv(self):
        if not self.events:
            raise ConnectionResetError()
        event = self.events.pop(0)
        if isinstance(event, Exception):
            raise event
        return event if isinstance(event, str) else json.dumps(event)

    async def close(self):
        self.closed = True

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self.events:
            raise StopAsyncIteration
        return await self.recv()


def tts_events(provider):
    pcm = b"\x01\x00" * 160
    audio = {"type": "audio", "data": {"audio": base64.b64encode(pcm).decode()}}
    final = (
        {"type": "event", "data": {"event_type": "final"}}
        if provider == "sarvam" else {"type": "complete", "data": {"is_final": True}}
    )
    return pcm, audio, final


@pytest.mark.asyncio
async def test_retry_policy_transient_count_backoff_and_limit():
    policy = RetryPolicy(settings(), jitter=lambda: 0)
    delays = []

    async def record(delay):
        delays.append(delay)

    policy.sleep = record
    attempts = 0

    async def operation():
        nonlocal attempts
        attempts += 1
        if attempts <= 2:
            raise ConnectionResetError("test secret must not be copied")
        return 42

    assert await policy.call(operation, "sarvam", "STT") == 42
    assert attempts == 3
    assert delays == [0.001, 0.002]
    assert policy.delay_ms(10) <= policy.max_ms

    attempts = 0

    async def always_fails():
        nonlocal attempts
        attempts += 1
        raise ConnectionResetError()

    with pytest.raises(ProviderTransientError):
        await policy.call(always_fails, "sarvam", "STT")
    assert attempts == 3


@pytest.mark.asyncio
async def test_nonretryable_failure_and_secret_redaction(caplog):
    policy = RetryPolicy(settings())
    attempts = 0
    secret = "test-secret-do-not-log"

    async def operation():
        nonlocal attempts
        attempts += 1
        raise ProviderAuthError("gnani", "STT", "HTTP error: 401") from ValueError(secret)

    with pytest.raises(ProviderAuthError) as found:
        await policy.call(operation, "gnani", "STT")
    assert attempts == 1
    assert secret not in str(found.value)
    assert secret not in caplog.text


@pytest.mark.asyncio
async def test_cancellation_interrupts_backoff_without_leaked_sleep_task():
    policy = RetryPolicy(settings(provider_backoff_base_ms=200, provider_backoff_max_ms=200))
    entered = asyncio.Event()
    cancelled = asyncio.Event()

    async def sleep_forever(_):
        entered.set()
        await asyncio.Future()

    policy.sleep = sleep_forever

    async def failure():
        raise ConnectionResetError()

    task = asyncio.create_task(policy.call(failure, "sarvam", "STT", cancel_event=cancelled))
    await asyncio.wait_for(entered.wait(), 1)
    cancelled.set()
    with pytest.raises(ProviderCancelledError):
        await asyncio.wait_for(task, 1)


@pytest.mark.parametrize(
    "options",
    [
        {"provider_max_retries": -1},
        {"provider_max_retries": 6},
        {"provider_backoff_base_ms": 0},
        {"provider_backoff_base_ms": 3000},
        {"provider_backoff_max_ms": 6000},
        {"provider_backoff_base_ms": 300, "provider_backoff_max_ms": 200},
    ],
)
def test_retry_settings_reject_invalid_values(options):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **options)


def test_zero_retries_keeps_readiness_configuration_valid(tmp_path):
    state = Settings(_env_file=None, provider_max_retries=0, silero_model=tmp_path / "missing")
    assert state.provider_max_retries == 0
    assert "PROVIDER_MAX_RETRIES" not in state.missing_voice_settings()


def test_retry_configuration_parses_exact_environment_names(monkeypatch):
    monkeypatch.setenv("PROVIDER_MAX_RETRIES", "0")
    monkeypatch.setenv("PROVIDER_BACKOFF_BASE_MS", "120")
    monkeypatch.setenv("PROVIDER_BACKOFF_MAX_MS", "500")
    state = Settings(_env_file=None)
    assert (state.provider_max_retries, state.provider_backoff_base_ms, state.provider_backoff_max_ms) == (
        0, 120, 500,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["timeout", 429, 503])
async def test_gnani_stt_transient_then_success_emits_one_final(failure):
    attempts = 0

    def handler(_):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            if failure == "timeout":
                raise httpx.TimeoutException("test timeout")
            return httpx.Response(failure)
        return httpx.Response(200, json={"success": True, "transcript": "one result"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        stt = GnaniSTT(settings(), http=http)
        await stt._transcribe_and_emit(b"\0" * 1600)
        await stt.close()
        events = [event async for event in stt.events()]
    assert attempts == 2
    assert len(events) == 1
    assert events[0].final and events[0].text == "one result"


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", [401, "malformed"])
async def test_gnani_stt_nonretryable_response(failure):
    attempts = 0

    def handler(_):
        nonlocal attempts
        attempts += 1
        return httpx.Response(401) if failure == 401 else httpx.Response(200, content=b"no json")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        stt = GnaniSTT(settings(), http=http)
        with pytest.raises(ProviderAuthError if failure == 401 else ProviderProtocolError):
            await stt.transcribe_wav(b"RIFF")
    assert attempts == 1


@pytest.mark.asyncio
async def test_gnani_stt_exhaustion_emits_no_final():
    attempts = 0

    def handler(_):
        nonlocal attempts
        attempts += 1
        return httpx.Response(503)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        stt = GnaniSTT(settings(), http=http)
        await stt._transcribe_and_emit(b"\0" * 1600)
        assert stt._events.qsize() == 1
        with pytest.raises(ProviderTransientError):
            async for _ in stt.events():
                pass
        await stt.close()
    assert attempts == 3


@pytest.mark.asyncio
async def test_sarvam_stt_disconnect_reconnects_without_replaying_final(monkeypatch):
    stt = SarvamSTT(settings())
    first = ScriptSocket([{"event": "transcript.final", "text": "first"}])
    second = ScriptSocket([{"event": "transcript.final", "text": "second"}])
    stt.ws = first
    connections = 0

    async def connect():
        nonlocal connections
        connections += 1
        return second

    monkeypatch.setattr(stt, "_connect", connect)
    results = []
    async for event in stt.events():
        results.append(event.text)
        if len(results) == 2:
            await stt.close()
    assert results == ["first", "second"]
    assert connections == 1
    assert first.closed


@pytest.mark.asyncio
async def test_sarvam_stt_reconnect_exhaustion_is_bounded(monkeypatch):
    stt = SarvamSTT(settings())
    stt.ws = ScriptSocket()
    attempts = 0

    async def disconnect():
        nonlocal attempts
        attempts += 1
        raise ConnectionResetError()

    monkeypatch.setattr(stt, "_connect", disconnect)
    with pytest.raises(ProviderTransientError):
        async for _ in stt.events():
            pass
    assert attempts == 2
    await stt.close()


@pytest.mark.asyncio
async def test_sarvam_send_reconnect_exhaustion_does_not_spin_events(monkeypatch):
    stt = SarvamSTT(settings())
    socket = ScriptSocket()

    async def failed_send(_):
        raise ConnectionResetError()

    async def failed_connect():
        raise ConnectionResetError()

    socket.send = failed_send
    stt.ws = socket
    monkeypatch.setattr(stt, "_connect", failed_connect)
    with pytest.raises(ProviderTransientError):
        await stt.send(b"\0\0")
    assert stt.ws is None

    async def consume():
        async for _ in stt.events():
            pass

    with pytest.raises(ProviderTransientError):
        await asyncio.wait_for(consume(), 1)
    await stt.close()


@pytest.mark.asyncio
async def test_sarvam_stt_close_interrupts_reconnect_backoff(monkeypatch):
    stt = SarvamSTT(settings())
    stt.ws = ScriptSocket()
    entered = asyncio.Event()

    async def sleep_forever(_):
        entered.set()
        await asyncio.Future()

    stt.retry.sleep = sleep_forever

    async def consume():
        async for _ in stt.events():
            pass

    task = asyncio.create_task(consume())
    await asyncio.wait_for(entered.wait(), 1)
    await stt.close()
    with pytest.raises(ProviderCancelledError):
        await asyncio.wait_for(task, 1)


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", ["sarvam", "gnani"])
async def test_tts_retries_before_first_audio_only(provider, monkeypatch):
    tts = SarvamTTS(settings(), "en-IN") if provider == "sarvam" else GnaniTTS(settings())
    pcm, audio, final = tts_events(provider)
    first = ScriptSocket([ConnectionResetError()])
    second = ScriptSocket([audio, final])
    tts.active = first
    connects = 0

    async def connect():
        nonlocal connects
        connects += 1
        return second

    async def no_refill():
        return None

    monkeypatch.setattr(tts, "connect", connect)
    monkeypatch.setattr(tts, "_refill", no_refill)
    chunks = [chunk async for chunk in tts.speak("one phrase")]
    assert chunks == [pcm]
    assert connects == 1
    assert first.closed
    assert second.sent
    await tts.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", ["sarvam", "gnani"])
async def test_tts_never_replays_after_partial_audio(provider, monkeypatch):
    tts = SarvamTTS(settings(), "en-IN") if provider == "sarvam" else GnaniTTS(settings())
    pcm, audio, _ = tts_events(provider)
    tts.active = ScriptSocket([audio, ConnectionResetError()])
    connects = 0

    async def unexpected_connect():
        nonlocal connects
        connects += 1
        raise AssertionError("A partial phrase must not reconnect and replay")

    monkeypatch.setattr(tts, "connect", unexpected_connect)
    chunks = []
    with pytest.raises(ProviderTransientError):
        async for chunk in tts.speak("one phrase"):
            chunks.append(chunk)
    assert chunks == [pcm]
    assert connects == 0
    await tts.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", ["sarvam", "gnani"])
async def test_tts_cancel_wins_during_retry_backoff(provider):
    tts = SarvamTTS(settings(), "en-IN") if provider == "sarvam" else GnaniTTS(settings())
    tts.active = ScriptSocket([ConnectionResetError()])
    entered = asyncio.Event()

    async def sleep_forever(_):
        entered.set()
        await asyncio.Future()

    tts.retry.sleep = sleep_forever

    async def speak():
        return [chunk async for chunk in tts.speak("cancel me")]

    task = asyncio.create_task(speak())
    await asyncio.wait_for(entered.wait(), 1)
    await tts.cancel()
    with pytest.raises(ProviderCancelledError):
        await asyncio.wait_for(task, 1)
    await tts.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", ["sarvam", "gnani"])
async def test_tts_cancel_during_connect_closes_late_socket(provider, monkeypatch):
    tts = SarvamTTS(settings(), "en-IN") if provider == "sarvam" else GnaniTTS(settings())
    entered = asyncio.Event()
    resume = asyncio.Event()
    late_socket = ScriptSocket()

    async def connect():
        entered.set()
        await resume.wait()
        return late_socket

    monkeypatch.setattr(tts, "connect", connect)

    async def speak():
        return [chunk async for chunk in tts.speak("do not speak")]

    task = asyncio.create_task(speak())
    await asyncio.wait_for(entered.wait(), 1)
    await tts.cancel()
    resume.set()
    with pytest.raises(ProviderCancelledError):
        await asyncio.wait_for(task, 1)
    assert late_socket.closed
    assert tts.active is None
    await tts.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", ["sarvam", "gnani"])
async def test_tts_standby_failure_does_not_kill_active(provider, monkeypatch):
    config = settings(provider_max_retries=0)
    tts = SarvamTTS(config, "en-IN") if provider == "sarvam" else GnaniTTS(config)
    pcm, audio, final = tts_events(provider)
    active = ScriptSocket([audio, final])
    calls = 0

    async def connect():
        nonlocal calls
        calls += 1
        if calls == 1:
            return active
        raise ProviderProtocolError(provider, "TTS", "standby unavailable")

    monkeypatch.setattr(tts, "connect", connect)
    await tts.open()
    await tts.refill
    assert tts.active is active and tts.spare is None
    assert [chunk async for chunk in tts.speak("healthy")] == [pcm]
    await tts.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", ["sarvam", "gnani"])
async def test_tts_new_turn_can_use_spare_after_cancel(provider, monkeypatch):
    tts = SarvamTTS(settings(), "en-IN") if provider == "sarvam" else GnaniTTS(settings())
    pcm, audio, final = tts_events(provider)
    tts.active = ScriptSocket()
    tts.spare = ScriptSocket([audio, final])

    async def no_refill():
        return None

    monkeypatch.setattr(tts, "_refill", no_refill)
    await tts.cancel()
    assert [chunk async for chunk in tts.speak("new turn")] == [pcm]
    await tts.close()


def sse(*deltas, done=True):
    lines = ["data: " + json.dumps({"choices": [{"delta": delta}]}) for delta in deltas]
    if done:
        lines.append("data: [DONE]")
    return ("\n\n".join(lines) + "\n\n").encode()


@pytest.mark.asyncio
@pytest.mark.parametrize("first", [429, 503, "timeout"])
async def test_groq_retries_before_first_token(first):
    attempts = 0

    def handler(_):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            if first == "timeout":
                raise httpx.TimeoutException("temporary")
            return httpx.Response(first)
        return httpx.Response(200, content=sse({"content": "hello"}))

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        outputs = [delta async for delta in Groq(settings(), http).stream([{"role": "user", "content": "hi"}])]
    assert attempts == 2
    assert outputs == [{"content": "hello"}]


@pytest.mark.asyncio
async def test_groq_partial_token_does_not_replay():
    attempts = 0

    def handler(_):
        nonlocal attempts
        attempts += 1
        return httpx.Response(200, content=sse({"content": "partial"}, done=False))

    outputs = []
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        with pytest.raises(ProviderTransientError):
            async for delta in Groq(settings(), http).stream([{"role": "user", "content": "hi"}]):
                outputs.append(delta)
    assert attempts == 1
    assert outputs == [{"content": "partial"}]


@pytest.mark.asyncio
@pytest.mark.parametrize("status, error_type", [(401, ProviderAuthError), (400, ProviderProtocolError)])
async def test_groq_auth_and_request_errors_never_retry(status, error_type):
    attempts = 0

    def handler(_):
        nonlocal attempts
        attempts += 1
        return httpx.Response(status)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        with pytest.raises(error_type):
            async for _ in Groq(settings(), http).stream([]):
                pass
    assert attempts == 1


@pytest.mark.asyncio
async def test_groq_malformed_stream_does_not_retry():
    attempts = 0

    def handler(_):
        nonlocal attempts
        attempts += 1
        return httpx.Response(200, content=b"data: not-json\n\n")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        with pytest.raises(ProviderProtocolError):
            async for _ in Groq(settings(), http).stream([]):
                pass
    assert attempts == 1


class CarrierSocket:
    def __init__(self):
        self.sent = []
        self.closed = False

    async def send_json(self, item):
        self.sent.append(item)

    async def close(self, **_):
        self.closed = True


def make_session(llm, tts):
    async def none(*_):
        return None

    async def tools(*_):
        return []

    async def fast(*_):
        return None, "miss", 0.0

    socket = CarrierSocket()
    services = SimpleNamespace(
        settings=settings(),
        actions=SimpleNamespace(confirm=none, cancel=none, tools=tools),
        knowledge=SimpleNamespace(fast_answer=fast, retrieve=tools, corpora={}),
        llm=SimpleNamespace(stream=llm),
        vad=SimpleNamespace(session=lambda: None),
    )
    tenant = {
        "id": "tenant-test",
        "config": {
            "language": "en-IN", "greeting": "Hi", "instructions": "Be helpful",
            "confirmation_phrases": ["yes confirm"], "backchannels": [],
        },
    }
    session = CallSession("call", tenant, MediaTransport(socket, "exotel", "stream"), services)
    session.tts = tts
    return session, socket


@pytest.mark.asyncio
async def test_session_llm_exhaustion_speaks_bounded_fallback_and_keeps_generation_clean(monkeypatch):
    monkeypatch.setattr("omnivoice.session.missing_fact_reply", lambda *_: None)
    monkeypatch.setattr("omnivoice.session.unsupported_action_reply", lambda *_: None)

    async def llm(*_):
        raise ProviderTransientError("groq", "LLM", "connection error")
        yield

    class TTS:
        async def stream_text(self, texts):
            async for _ in texts:
                yield b"\0" * 3200

        async def cancel(self):
            return None

    session, socket = make_session(llm, TTS())
    await asyncio.wait_for(session.respond("Tell me more", time.perf_counter(), 1), 2)
    assert sum(item["event"] == "media" for item in socket.sent) == 1
    assert session.metrics["turns"][0]["agent_response"] == LLM_FAILURE_REPLY
    assert session.active_generation_id is None
    assert not socket.closed


@pytest.mark.asyncio
async def test_session_partial_tts_failure_clears_and_never_replays(monkeypatch):
    monkeypatch.setattr("omnivoice.session.missing_fact_reply", lambda *_: None)
    monkeypatch.setattr("omnivoice.session.unsupported_action_reply", lambda *_: None)

    async def llm(*_):
        yield {"content": "A brief answer."}

    class TTS:
        async def stream_text(self, texts):
            async for _ in texts:
                yield b"\0" * 3200
                raise ProviderTransientError("gnani", "TTS", "connection error")

        async def cancel(self):
            return None

    session, socket = make_session(llm, TTS())
    await asyncio.wait_for(session.respond("Tell me more", time.perf_counter(), 1), 2)
    assert sum(item["event"] == "media" for item in socket.sent) == 1
    assert sum(item["event"] == "clear" for item in socket.sent) == 1
    assert socket.closed
    assert session.metrics["turns"][0]["agent_response"] != LLM_FAILURE_REPLY


@pytest.mark.asyncio
async def test_stt_exhaustion_sends_honest_reply_and_stops():
    async def llm(*_):
        yield {"content": "unused"}

    class TTS:
        async def stream_text(self, texts):
            async for _ in texts:
                yield b"\0" * 3200

        async def cancel(self):
            return None

    session, socket = make_session(llm, TTS())
    error = ProviderTransientError("sarvam", "STT", "connection error")
    await asyncio.wait_for(session._stt_unavailable(error), 2)
    assert session._stt_failed
    assert session.metrics["provider_failures"][0]["category"] == "transient"
    assert sum(item["event"] == "media" for item in socket.sent) == 1
    assert STT_FAILURE_REPLY == "I'm having trouble hearing you right now. Please try again."


@pytest.mark.asyncio
async def test_stt_exhaustion_ends_running_session_and_closes_providers():
    async def llm(*_):
        yield {"content": "unused"}

    class STT:
        closed = False

        async def open(self):
            return None

        async def send(self, _):
            return None

        async def events(self):
            raise ProviderTransientError("sarvam", "STT", "connection error")
            yield

        async def close(self):
            self.closed = True

    class TTS:
        closed = False

        async def open(self):
            return None

        async def stream_text(self, texts):
            async for _ in texts:
                yield b"\0" * 3200

        async def cancel(self):
            return None

        async def close(self):
            self.closed = True

    session, socket = make_session(llm, TTS())
    stt = STT()
    session.stt = stt

    async def receive_forever():
        await asyncio.Future()

    async def refresh(*_):
        return None

    socket.receive_json = receive_forever
    session.services.knowledge.refresh = refresh
    await asyncio.wait_for(session.run(), 2)
    assert stt.closed and session.tts.closed
    assert session.metrics["provider_failures"][0]["modality"] == "STT"


@pytest.mark.asyncio
async def test_llm_retry_does_not_duplicate_action_proposal(monkeypatch):
    monkeypatch.setattr("omnivoice.session.missing_fact_reply", lambda *_: None)
    monkeypatch.setattr("omnivoice.session.unsupported_action_reply", lambda *_: None)
    attempts = 0
    staged = []
    tool = {
        "name": "reserve", "description": "Propose a reservation", "kind": "write",
        "parameters": {"type": "object", "properties": {"slot": {"type": "string"}}},
    }

    def handler(_):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(503)
        return httpx.Response(
            200,
            content=sse({"tool_calls": [{"index": 0, "function": {
                "name": "reserve", "arguments": '{"slot":"A"}',
            }}]}),
        )

    async def llm_placeholder(*_):
        yield {"content": "unused"}

    class TTS:
        async def stream_text(self, texts):
            async for _ in texts:
                yield b"\0" * 3200

        async def cancel(self):
            return None

    session, _ = make_session(llm_placeholder, TTS())

    async def tools(*_):
        return [tool]

    async def get_tool(*_):
        return tool

    async def stage(*args):
        staged.append(args)
        return {"id": "proposal-1", "summary": "Reserve slot A."}

    session.services.actions.tools = tools
    session.services.actions.get_tool = get_tool
    session.services.actions.stage = stage
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        session.services.llm = Groq(settings(), http)
        await asyncio.wait_for(session.respond("Reserve A", time.perf_counter(), 1), 2)
    assert attempts == 2
    assert len(staged) == 1
    assert session.metrics["turns"][0]["tool_called"] is True
