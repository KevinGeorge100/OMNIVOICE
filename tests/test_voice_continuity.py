"""Deterministic speech and carrier continuity checks; no provider calls."""

import asyncio
import base64
import json
import time
from types import SimpleNamespace

import pytest

from omnivoice.audio import PCMFrameBuffer
from omnivoice.config import Settings
from omnivoice.duplex import CancelReason
from omnivoice.providers import SarvamTTS
from omnivoice.session import CallSession
from omnivoice.speech import SpeechSegmenter, normalize_speech
from omnivoice.transport import MediaTransport


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("**OmniVoice Architecture:**", "OmniVoice Architecture."),
        ("## About\nOmniVoice *listens* to callers.", "About. OmniVoice listens to callers."),
        ("[Our guide](https://example.com/guide) is available.", "Our guide is available."),
        ("```python\nprint('hello')\n```", "print('hello')"),
        ("---\nHelpful   answer.\n***", "Helpful answer."),
    ],
)
def test_speech_normalization_preserves_words_without_visual_markers(source, expected):
    assert normalize_speech(source) == expected


def test_bullets_become_a_spoken_list_and_urls_are_readable():
    assert normalize_speech("* STT\n* RAG\n* TTS") == "STT, RAG, and TTS."
    assert normalize_speech("See https://example.com/deep/path") == "See example dot com"
    assert normalize_speech("Visit https://example.com/path?x=1.") == "Visit example dot com."
    assert normalize_speech("AI → speech & action 🚀") == "AI to speech and action"


def test_segmenter_emits_first_phrase_before_stream_ends_and_keeps_tiny_fragments():
    segmenter = SpeechSegmenter()
    assert segmenter.feed("OmniVoice.") == []
    first = segmenter.feed(" It connects business knowledge to live telephone calls.")
    assert first == ["OmniVoice. It connects business knowledge to live telephone calls."]
    assert segmenter.feed(" Another short line.") == []
    assert segmenter.finish() == "Another short line."


def test_segmenter_bounds_long_stream_without_one_word_synthesis():
    segmenter = SpeechSegmenter()
    chunks = ["This is a longer natural sentence with enough context to start speaking. "]
    chunks += ["The caller can ask another complete question and hear a useful answer. "] * 4
    output = []
    for chunk in chunks:
        output.extend(segmenter.feed(chunk))
    if tail := segmenter.finish():
        output.append(tail)
    assert 2 <= len(output) <= 4
    assert all(len(chunk.split()) >= 6 for chunk in output)


@pytest.mark.parametrize("frame_size", [320, 3200])
def test_pcm_frames_continue_across_segments_and_pad_only_true_tail(frame_size):
    buffer = PCMFrameBuffer(frame_size)
    a = b"\x11\x22" * (frame_size // 4)
    b = b"\x33\x44" * (frame_size // 4)
    assert buffer.push(a) == []
    assert buffer.push(b) == [a + b]
    assert buffer.finish() == (None, 0)
    assert buffer.push(b"\x55\x66") == []
    tail, padding = buffer.finish()
    assert len(tail) == frame_size
    assert tail[:2] == b"\x55\x66"
    assert padding == frame_size - 2
    assert not any(buffer.pending)


def test_pcm_rejects_half_samples_and_cancellation_discards_tail():
    buffer = PCMFrameBuffer(3200)
    with pytest.raises(ValueError, match="complete"):
        buffer.push(b"\x01")
    buffer.push(b"\x11\x22" * 40)
    buffer.clear()
    assert buffer.finish() == (None, 0)


class CarrierSocket:
    def __init__(self):
        self.sent = []

    async def send_json(self, packet):
        self.sent.append(packet)


def media_payloads(socket):
    return [base64.b64decode(p["media"]["payload"]) for p in socket.sent if p["event"] == "media"]


async def test_carrier_epoch_discards_stale_frame_after_clear():
    socket = CarrierSocket()
    transport = MediaTransport(socket, "exotel", "sid")
    frame = b"\x11\x22" * 1600
    assert await transport.send_frame(frame, 0)
    await transport.clear()
    assert not await transport.send_frame(frame, 0)
    assert len(media_payloads(socket)) == 1
    assert socket.sent[-1]["event"] == "clear"


async def test_sarvam_stream_uses_one_flush_and_yields_audio_before_text_is_complete():
    class Socket:
        def __init__(self):
            self.sent = []
            self.incoming = asyncio.Queue()
            self.closed = False

        async def send(self, raw):
            packet = json.loads(raw)
            self.sent.append(packet)
            if packet["type"] == "text" and len([p for p in self.sent if p["type"] == "text"]) == 1:
                await self.incoming.put(
                    {"type": "audio", "data": {"content_type": "audio/pcm", "audio": "AAABAA=="}}
                )
            if packet["type"] == "flush":
                await self.incoming.put({"type": "event", "data": {"event_type": "final"}})

        async def recv(self):
            return json.dumps(await self.incoming.get())

        async def close(self):
            self.closed = True

    socket = Socket()
    provider = SarvamTTS(Settings(_env_file=None), "en-IN")
    provider.active = socket
    release_second = asyncio.Event()

    async def texts():
        yield "First useful phrase."
        await release_second.wait()
        yield "Second connected phrase."

    stream = provider.stream_text(texts())
    first_audio = await asyncio.wait_for(anext(stream), 1)
    assert first_audio == b"\0\0\1\0"
    assert [p["type"] for p in socket.sent] == ["text"]
    release_second.set()
    assert [pcm async for pcm in stream] == []
    assert [p["type"] for p in socket.sent] == ["text", "text", "flush"]
    assert not socket.closed


async def test_sarvam_rejects_final_before_flush_and_closes_stale_socket():
    class Socket:
        def __init__(self):
            self.sent = []
            self.closed = False
            self.incoming = asyncio.Queue()

        async def send(self, raw):
            packet = json.loads(raw)
            self.sent.append(packet)
            if packet["type"] == "text":
                await self.incoming.put({"type": "event", "data": {"event_type": "final"}})

        async def recv(self):
            return json.dumps(await self.incoming.get())

        async def close(self):
            self.closed = True

    socket = Socket()
    provider = SarvamTTS(Settings(_env_file=None), "en-IN")
    provider.active = socket

    async def texts():
        yield "The first complete phrase."
        await asyncio.sleep(10)

    with pytest.raises(RuntimeError, match="before the utterance flush"):
        async for _ in provider.stream_text(texts()):
            pass
    assert socket.closed
    assert provider.active is None


def make_session(llm_stream, tts, provider="exotel"):
    async def none(*args, **kwargs):
        return None

    async def no_items(*args, **kwargs):
        return []

    async def miss(*args, **kwargs):
        return None, "miss", 0.1

    socket = CarrierSocket()
    services = SimpleNamespace(
        settings=Settings(_env_file=None),
        actions=SimpleNamespace(confirm=none, cancel=none, tools=no_items),
        knowledge=SimpleNamespace(fast_answer=miss, retrieve=no_items),
        llm=SimpleNamespace(stream=llm_stream),
        vad=SimpleNamespace(session=lambda: None),
    )
    tenant = {
        "id": "synthetic",
        "config": {
            "language": "en-IN",
            "greeting": "Hello",
            "instructions": "",
            "confirmation_phrases": ["yes confirm"],
            "backchannels": ["yeah"],
        },
    }
    session = CallSession("test-call", tenant, MediaTransport(socket, provider, "sid"), services)
    session.tts = tts
    return session, socket


async def test_live_pipeline_sends_normalized_text_and_one_continuous_carrier_frame():
    class TTS:
        def __init__(self):
            self.texts = []

        async def stream_text(self, texts):
            async for text in texts:
                self.texts.append(text)
                yield b"\x11\x22" * 800

    async def llm(*args):
        yield {"content": "**OmniVoice** connects private knowledge to real telephone conversations. "}
        yield {"content": "It helps teams answer questions while respecting explicit confirmation for business actions."}

    tts = TTS()
    session, socket = make_session(llm, tts)
    await session.respond("What is OmniVoice?", time.perf_counter(), 1)
    assert len(tts.texts) == 2
    assert "*" not in "".join(tts.texts)
    assert media_payloads(socket) == [b"\x11\x22" * 1600]
    assert [p["event"] for p in socket.sent] == ["media", "mark"]
    turn = session.metrics["turns"][0]
    assert turn["response_segment_count"] == 2
    assert turn["tts_segment_count"] == 2
    assert turn["first_segment_chars"] > 30
    assert turn["speech_normalization_changed"]
    assert turn["total_speech_chars"] == sum(map(len, tts.texts))
    assert turn["outbound_audio_bytes"] == 3200
    assert turn.get("padded_tail_bytes", 0) == 0
    assert turn["first_tts_ttfa_ms"] >= 0
    assert json.loads(json.dumps(session.metrics))["turns"][0]["agent_response"].startswith("**")


async def test_interruption_drops_pending_pcm_and_partial_metrics_survive():
    class TTS:
        def __init__(self):
            self.waiting = asyncio.Event()
            self.cancelled = False
            self.texts = []

        async def stream_text(self, texts):
            async for text in texts:
                self.texts.append(text)
                yield b"\x11\x22" * 1600  # First frame reaches playback.
                yield b"\x33\x44" * 800  # Unsent half-frame must be discarded.
                await self.waiting.wait()

        async def cancel(self):
            self.cancelled = True
            self.waiting.set()

    async def llm(*args):
        yield {"content": "A complete first phrase about our enterprise telephone service."}
        yield {"content": " A second phrase has enough context to be queued, but must never reach the carrier after the caller interrupts the ongoing reply."}
        await asyncio.sleep(10)

    tts = TTS()
    session, socket = make_session(llm, tts)
    session.generation_id = 1
    session.response = asyncio.create_task(session.respond("Tell me more", time.perf_counter(), 1))
    for _ in range(100):
        if session.fsm.playing:
            break
        await asyncio.sleep(.001)
    assert session.fsm.playing
    await session.interrupt()
    assert tts.cancelled
    assert len(tts.texts) == 1
    assert media_payloads(socket) == [b"\x11\x22" * 1600]
    assert [p["event"] for p in socket.sent] == ["media", "clear"]
    turn = session.metrics["turns"][0]
    assert turn["interrupted"]
    assert turn["agent_response"].startswith("A complete")
    assert turn["response_segment_count"] == 1
    assert turn.get("padded_tail_bytes", 0) == 0
    assert not any(packet["event"] == "mark" for packet in socket.sent)


async def test_generation_supersession_preserves_adr001_without_carrier_clear():
    class TTS:
        async def stream_text(self, texts):
            async for _ in texts:
                yield b"\0" * 3200

        async def cancel(self):
            pass

    started = asyncio.Event()

    async def llm(messages, _):
        if messages[-1]["content"] == "first":
            started.set()
            await asyncio.sleep(10)
        yield {"content": "A complete reply that is only spoken for the current caller turn."}

    session, socket = make_session(llm, TTS())
    session.generation_id = 1
    session.response = asyncio.create_task(session.respond("first", time.perf_counter(), 1))
    await started.wait()
    assert not session.fsm.playing
    await session._cancel_pending_generation(CancelReason.SUPERSEDED)
    session.generation_id = 2
    session.response = asyncio.create_task(session.respond("second", time.perf_counter(), 2))
    await session.response
    assert not any(p["event"] == "clear" for p in socket.sent)
    assert len(session.metrics["turns"]) == 1
    assert session.metrics["turns"][0]["user_transcript"] == "second"


async def test_superseded_generation_cannot_send_audio_after_pacing_wait():
    class TTS:
        def __init__(self):
            self.produced = asyncio.Event()

        async def stream_text(self, texts):
            async for _ in texts:
                self.produced.set()
                yield b"\x11\x22" * 1600

    async def unused_llm(*args):
        if False:
            yield {}

    tts = TTS()
    session, socket = make_session(unused_llm, tts)
    session.active_generation_id = 1
    session.transport.next_send_at = time.monotonic() + .08
    task = asyncio.create_task(session.say("A complete phrase."))
    await tts.produced.wait()
    await asyncio.sleep(.005)
    session.active_generation_id = 2
    await asyncio.wait_for(task, 1)
    assert socket.sent == []
    assert session.marks == {}


async def test_early_tts_completion_cancels_bounded_llm_producer():
    class TTS:
        async def stream_text(self, texts):
            async for _ in texts:
                break
            if False:
                yield b""

    async def llm(*args):
        yield {"content": "This first useful phrase arrives before the answer is complete."}
        while True:
            yield {"content": " Another useful phrase continues the reply with context."}
            await asyncio.sleep(0)

    session, _ = make_session(llm, TTS())
    await asyncio.wait_for(session.respond("question", time.perf_counter(), 1), 1)
    assert len(session.metrics["turns"]) == 1


def test_legacy_metrics_with_no_voice_fields_remain_readable():
    legacy = {"turns": [{"final_transcript_to_first_audio_sent_ms": 712.4, "agent_response": "Hi"}]}
    loaded = json.loads(json.dumps(legacy))
    assert loaded["turns"][0].get("response_segment_count") is None
