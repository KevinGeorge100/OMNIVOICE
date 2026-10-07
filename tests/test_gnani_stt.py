import asyncio
import io
import wave

import httpx
import numpy as np
import pytest

from omnivoice.config import Settings
from omnivoice.models import Transcript
from omnivoice.providers import (
    GnaniSTT,
    SpeechProviderUnavailable,
    pcm_to_wav,
    select_speech_provider,
)


def make_test_settings(gnani_key="test-gnani-secret", endpoint_silence_ms=200):
    return Settings(
        _env_file=None,
        gnani_api_key=gnani_key,
        sarvam_api_key="test-sarvam-key",
        groq_api_key="test-groq-key",
        stt_provider="gnani",
        tts_provider="sarvam",
        endpoint_silence_ms=endpoint_silence_ms,
    )


def make_sine_pcm(duration_s=0.2, sample_rate=16000, freq=440.0, amplitude=5000):
    t = np.linspace(0, duration_s, int(sample_rate * duration_s), endpoint=False)
    samples = (amplitude * np.sin(2 * np.pi * freq * t)).astype("<i2")
    return samples.tobytes()


def make_silence_pcm(duration_s=0.2, sample_rate=16000):
    return b"\x00" * int(sample_rate * duration_s * 2)


def test_pcm_to_wav_format():
    pcm = make_sine_pcm(duration_s=0.1)
    wav_bytes = pcm_to_wav(pcm, sample_rate=16000)
    assert wav_bytes.startswith(b"RIFF")
    with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
        assert wf.getnchannels() == 1
        assert wf.getsampwidth() == 2
        assert wf.getframerate() == 16000
        assert wf.getnframes() == len(pcm) // 2


@pytest.mark.asyncio
async def test_gnani_stt_request_and_headers_safety():
    secret_key = "super-secret-gnani-credential-12345"
    settings = make_test_settings(gnani_key=secret_key)
    captured_request = None

    def handler(request: httpx.Request):
        nonlocal captured_request
        captured_request = request
        return httpx.Response(
            200,
            json={
                "success": True,
                "request_id": "test-req-1",
                "timestamp": "2026-10-07T00:00:00Z",
                "transcript": "Namaste OmniVoice",
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    stt = GnaniSTT(settings, http=client, language="en-IN")
    wav = pcm_to_wav(make_sine_pcm(0.1))
    transcript = await stt.transcribe_wav(wav)

    assert isinstance(transcript, Transcript)
    assert transcript.text == "Namaste OmniVoice"
    assert transcript.final is True
    assert transcript.language == "en-IN"

    assert captured_request is not None
    assert captured_request.headers.get("X-API-Key-ID") == secret_key
    assert secret_key not in str(stt)
    assert secret_key not in repr(stt)


@pytest.mark.asyncio
async def test_gnani_stt_multipart_payload_structure():
    settings = make_test_settings()
    captured_body = None

    def handler(request: httpx.Request):
        nonlocal captured_body
        captured_body = request.read()
        return httpx.Response(
            200,
            json={"success": True, "request_id": "req-42", "transcript": "Verified fields test"},
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    stt = GnaniSTT(settings, http=client, language="hi-IN")
    wav = pcm_to_wav(make_sine_pcm(0.1))
    await stt.transcribe_wav(wav)

    assert captured_body is not None
    body_text = captured_body.decode("utf-8", errors="ignore")
    assert 'name="language_code"' in body_text
    assert "hi-IN" in body_text
    assert 'name="preferred_language"' in body_text
    assert 'name="format"' in body_text
    assert "transcribe" in body_text
    assert 'name="itn_native_numerals"' in body_text
    assert "true" in body_text
    assert 'filename="audio.wav"' in body_text
    assert "Content-Type: audio/wav" in body_text


def test_gnani_stt_unsupported_language_fails_fast():
    settings = make_test_settings()
    with pytest.raises(ValueError, match="Unsupported Gnani STT language"):
        GnaniSTT(settings, language="fr-FR")


@pytest.mark.asyncio
async def test_gnani_stt_empty_transcript_handled_safely():
    settings = make_test_settings()

    def handler(request: httpx.Request):
        return httpx.Response(200, json={"success": True, "request_id": "req-empty", "transcript": ""})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    stt = GnaniSTT(settings, http=client)
    wav = pcm_to_wav(make_sine_pcm(0.1))
    transcript = await stt.transcribe_wav(wav)
    assert transcript.text == ""
    assert transcript.final is True


@pytest.mark.asyncio
async def test_gnani_stt_timeout_handled_cleanly():
    secret_key = "secret-key-for-timeout"
    settings = make_test_settings(gnani_key=secret_key)

    def handler(request: httpx.Request):
        raise httpx.TimeoutException("Network timed out")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    stt = GnaniSTT(settings, http=client)
    wav = pcm_to_wav(make_sine_pcm(0.1))

    with pytest.raises(RuntimeError, match="timeout") as exc_info:
        await stt.transcribe_wav(wav)
    assert secret_key not in str(exc_info.value)


@pytest.mark.asyncio
async def test_gnani_stt_http_error_handled_cleanly():
    secret_key = "secret-key-for-http-err"
    settings = make_test_settings(gnani_key=secret_key)

    def handler(request: httpx.Request):
        return httpx.Response(401, json={"message": "Unauthorized"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    stt = GnaniSTT(settings, http=client)
    wav = pcm_to_wav(make_sine_pcm(0.1))

    with pytest.raises(RuntimeError, match="HTTP error: 401") as exc_info:
        await stt.transcribe_wav(wav)
    assert secret_key not in str(exc_info.value)


@pytest.mark.asyncio
async def test_gnani_stt_malformed_json_handled_cleanly():
    settings = make_test_settings()

    def handler(request: httpx.Request):
        return httpx.Response(200, content=b"invalid-json-body")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    stt = GnaniSTT(settings, http=client)
    wav = pcm_to_wav(make_sine_pcm(0.1))

    with pytest.raises(RuntimeError, match="malformed JSON"):
        await stt.transcribe_wav(wav)


@pytest.mark.asyncio
async def test_gnani_stt_unsuccessful_payload_handled_cleanly():
    settings = make_test_settings()

    def handler(request: httpx.Request):
        return httpx.Response(200, json={"success": False, "message": "Internal processing failure"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    stt = GnaniSTT(settings, http=client)
    wav = pcm_to_wav(make_sine_pcm(0.1))

    with pytest.raises(RuntimeError, match="Internal processing failure"):
        await stt.transcribe_wav(wav)


@pytest.mark.asyncio
async def test_gnani_stt_utterance_lifecycle_emits_final_transcript():
    settings = make_test_settings(endpoint_silence_ms=100)

    def handler(request: httpx.Request):
        return httpx.Response(
            200, json={"success": True, "request_id": "req-flow", "transcript": "Caller speech detected"}
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    stt = GnaniSTT(settings, http=client)

    # 1. Send silence
    silence_chunk = make_silence_pcm(0.05)
    for _ in range(3):
        await stt.send(silence_chunk)

    # 2. Send speech frames
    speech_chunk = make_sine_pcm(0.05, amplitude=6000)
    for _ in range(4):
        await stt.send(speech_chunk)

    # 3. Send silence exceeding endpoint_silence_ms
    await asyncio.sleep(0.15)
    for _ in range(4):
        await stt.send(silence_chunk)

    # Wait for the emitted transcript
    transcript = None
    async for event in stt.events():
        transcript = event
        break

    assert transcript is not None
    assert transcript.text == "Caller speech detected"
    assert transcript.final is True

    await stt.close()


def test_gnani_tts_fails_closed():
    def dummy_sarvam():
        return "sarvam"

    with pytest.raises(SpeechProviderUnavailable, match="Gnani TTS"):
        select_speech_provider("gnani", "TTS", dummy_sarvam)


def test_sarvam_stt_still_selected_by_default():
    assert select_speech_provider("sarvam", "STT", lambda: "sarvam_stt") == "sarvam_stt"
    assert select_speech_provider("sarvam", "TTS", lambda: "sarvam_tts") == "sarvam_tts"
