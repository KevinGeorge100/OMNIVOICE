import asyncio
import base64
import json
import time
from types import SimpleNamespace

import pytest

from omnivoice.config import Settings
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
