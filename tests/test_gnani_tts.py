import asyncio
import base64
import json
from types import SimpleNamespace

import pytest

from omnivoice.config import Settings
from omnivoice.providers import (
    GnaniTTS,
    SarvamTTS,
)
from omnivoice.session import CallSession


def make_test_settings(gnani_key="test-gnani-secret", voice="Pranav", model="timbre-v2.5", rate=8000):
    return Settings(
        _env_file=None,
        gnani_api_key=gnani_key,
        sarvam_api_key="test-sarvam-key",
        groq_api_key="test-groq-key",
        stt_provider="gnani",
        tts_provider="gnani",
        gnani_tts_voice=voice,
        gnani_tts_model=model,
        gnani_tts_sample_rate=rate,
    )


class MockWebSocket:
    def __init__(self, incoming=None):
        self.sent = []
        self.closed = False
        self.incoming = asyncio.Queue()
        if incoming:
            for item in incoming:
                self.incoming.put_nowait(item)

    async def send(self, message):
        self.sent.append(json.loads(message))

    async def recv(self):
        item = await self.incoming.get()
        if isinstance(item, Exception):
            raise item
        return json.dumps(item) if not isinstance(item, str) else item

    async def close(self):
        self.closed = True

    async def ping(self):
        fut = asyncio.get_running_loop().create_future()
        fut.set_result(None)
        return fut


def make_session(settings):
    services = SimpleNamespace(
        settings=settings,
        vad=SimpleNamespace(session=lambda: None),
    )
    tenant = {"config": {"backchannels": [], "language": "en-IN"}}
    return CallSession("test-call", tenant, object(), services)


def test_provider_selection_routes_correctly():
    # 1. Gnani TTS selected correctly
    gnani_settings = make_test_settings()
    session = make_session(gnani_settings)
    assert isinstance(session.tts, GnaniTTS)

    # 2. Sarvam TTS still default
    default_settings = Settings(_env_file=None)
    default_session = make_session(default_settings)
    assert isinstance(default_session.tts, SarvamTTS)


def test_key_never_appears_in_repr_or_str():
    secret = "secret-key-that-must-never-leak-45678"
    settings = make_test_settings(gnani_key=secret)
    tts = GnaniTTS(settings, language="en-IN")
    assert secret not in repr(tts)
    assert secret not in str(tts)


@pytest.mark.asyncio
async def test_auth_headers_use_bearer_and_x_api_key(monkeypatch):
    secret = "super-secret-gnani-bearer-token"
    settings = make_test_settings(gnani_key=secret)
    captured_headers = None

    async def mock_connect(url, additional_headers=None, **kwargs):
        nonlocal captured_headers
        captured_headers = additional_headers
        return MockWebSocket()

    monkeypatch.setattr("websockets.connect", mock_connect)
    tts = GnaniTTS(settings, language="en-IN")
    ws = await tts.connect()
    await ws.close()

    assert captured_headers is not None
    assert captured_headers.get("Authorization") == f"Bearer {secret}"
    assert captured_headers.get("X-API-Key-ID") == secret


@pytest.mark.asyncio
async def test_request_payload_and_progressive_audio():
    settings = make_test_settings()
    tts = GnaniTTS(settings, language="en-IN")

    sample_pcm_1 = b"\x01\x00" * 160  # 320 bytes 8kHz linear PCM
    sample_pcm_2 = b"\x02\x00" * 160
    b64_1 = base64.b64encode(sample_pcm_1).decode("ascii")
    b64_2 = base64.b64encode(sample_pcm_2).decode("ascii")

    incoming = [
        {"type": "start", "message": "Streaming started", "request_id": "req-1"},
        {"type": "audio", "data": {"chunk_index": 1, "audio": b64_1, "is_final": False}},
        {"type": "audio", "data": {"chunk_index": 2, "audio": b64_2, "is_final": False}},
        {"type": "complete", "data": {"chunk_index": 3, "audio": "", "is_final": True}},
        {"type": "complete", "message": "Streaming completed", "request_id": "req-1"},
    ]
    mock_ws = MockWebSocket(incoming)
    tts.active = mock_ws

    chunks = [pcm async for pcm in tts.speak("Hello OmniVoice")]
    assert len(chunks) == 2
    assert chunks[0] == sample_pcm_1
    assert chunks[1] == sample_pcm_2

    assert len(mock_ws.sent) == 1
    sent_req = mock_ws.sent[0]
    assert sent_req["text"] == "Hello OmniVoice"
    assert sent_req["model"] == "timbre-v2.5"
    assert sent_req["language"] == "en-IN"
    assert sent_req["voice"] == "Pranav"
    assert sent_req["sample_rate"] == 8000


@pytest.mark.asyncio
async def test_ordered_text_frames_and_completion():
    settings = make_test_settings()
    tts = GnaniTTS(settings, language="en-IN")

    pcm_chunk = b"\x05\x00" * 80
    b64 = base64.b64encode(pcm_chunk).decode("ascii")

    incoming = [
        {"type": "start", "message": "Streaming started", "request_id": "req-1"},
        {"type": "audio", "data": {"chunk_index": 1, "audio": b64, "is_final": False}},
        {"type": "complete", "data": {"chunk_index": 2, "audio": "", "is_final": True}},
        {"type": "complete", "message": "Streaming completed", "request_id": "req-1"},
        {"type": "start", "message": "Streaming started", "request_id": "req-2"},
        {"type": "audio", "data": {"chunk_index": 1, "audio": b64, "is_final": False}},
        {"type": "complete", "data": {"chunk_index": 2, "audio": "", "is_final": True}},
        {"type": "complete", "message": "Streaming completed", "request_id": "req-2"},
    ]
    mock_ws = MockWebSocket(incoming)
    tts.active = mock_ws

    async def text_stream():
        yield "Phrase one."
        yield "Phrase two."

    received = [pcm async for pcm in tts.stream_text(text_stream())]
    assert len(received) == 2
    assert len(mock_ws.sent) == 2
    assert mock_ws.sent[0]["text"] == "Phrase one."
    assert mock_ws.sent[1]["text"] == "Phrase two."


@pytest.mark.asyncio
async def test_empty_text_handled_safely():
    settings = make_test_settings()
    tts = GnaniTTS(settings, language="en-IN")
    mock_ws = MockWebSocket()
    tts.active = mock_ws

    async def empty_stream():
        yield ""
        yield "   "

    received = [pcm async for pcm in tts.stream_text(empty_stream())]
    assert received == []
    assert len(mock_ws.sent) == 0


@pytest.mark.asyncio
async def test_malformed_json_and_non_pcm_codecs_rejected():
    settings = make_test_settings()
    tts = GnaniTTS(settings, language="en-IN")

    # Malformed JSON string
    mock_ws1 = MockWebSocket(["{not valid json}"])
    tts.active = mock_ws1
    with pytest.raises(RuntimeError, match="malformed JSON"):
        async for _ in tts.speak("Test"):
            pass

    # Non-PCM content_type like mp3
    mock_ws2 = MockWebSocket([
        {"type": "audio", "data": {"content_type": "audio/mp3", "audio": "AAAA"}}
    ])
    tts.active = mock_ws2
    with pytest.raises(ValueError, match="raw PCM"):
        async for _ in tts.speak("Test"):
            pass

    # RIFF WAV header rejected
    riff_bytes = b"RIFF" + b"\x00" * 40
    mock_ws3 = MockWebSocket([
        {"type": "audio", "data": {"audio": base64.b64encode(riff_bytes).decode()}}
    ])
    tts.active = mock_ws3
    with pytest.raises(ValueError, match="Invalid raw PCM"):
        async for _ in tts.speak("Test"):
            pass


@pytest.mark.asyncio
async def test_provider_error_frame_raises():
    settings = make_test_settings()
    tts = GnaniTTS(settings, language="en-IN")
    mock_ws = MockWebSocket([
        {"type": "error", "message": "Voice quota exhausted"}
    ])
    tts.active = mock_ws
    with pytest.raises(RuntimeError, match="Voice quota exhausted"):
        async for _ in tts.speak("Test"):
            pass


@pytest.mark.asyncio
async def test_cancellation_closes_socket_and_standby_rotates():
    settings = make_test_settings()
    tts = GnaniTTS(settings, language="en-IN")

    active_ws = MockWebSocket()
    standby_ws = MockWebSocket()
    tts.active = active_ws
    tts.spare = standby_ws

    await tts.cancel()
    assert active_ws.closed is True
    assert tts.active is None

    # Next call to _voice_socket should promote spare
    promoted = await tts._voice_socket()
    assert promoted is standby_ws
    assert tts.active is standby_ws
    assert not standby_ws.closed

    await tts.close()
    assert standby_ws.closed is True


@pytest.mark.asyncio
async def test_stale_audio_after_cancel_is_discarded():
    settings = make_test_settings()
    tts = GnaniTTS(settings, language="en-IN")

    active_ws = MockWebSocket()
    tts.active = active_ws
    standby_ws = MockWebSocket([
        {"type": "start", "message": "Streaming started", "request_id": "fresh-1"},
        {"type": "audio", "data": {"audio": base64.b64encode(b"\x10\x00" * 80).decode()}},
        {"type": "complete", "message": "Streaming completed", "request_id": "fresh-1"},
    ])
    tts.spare = standby_ws

    # Cancel active
    await tts.cancel()
    assert active_ws.closed is True

    # Next generation speech uses fresh standby socket
    chunks = [pcm async for pcm in tts.speak("New generation speech")]
    assert len(chunks) == 1
    assert chunks[0] == b"\x10\x00" * 80


def test_unsupported_language_and_voice_fail_fast():
    settings = make_test_settings()
    with pytest.raises(ValueError, match="Unsupported Gnani TTS language"):
        GnaniTTS(settings, language="de-DE")

    invalid_voice_settings = make_test_settings(voice="InvalidVoiceName")
    with pytest.raises(ValueError, match="Unsupported Gnani TTS voice"):
        GnaniTTS(invalid_voice_settings, language="en-IN")
