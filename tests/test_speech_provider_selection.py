from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from omnivoice.app import create_app
from omnivoice.config import Settings
from omnivoice.providers import (
    GnaniSTT,
    GnaniTTS,
    SarvamSTT,
    SarvamTTS,
    SpeechProviderUnavailable,
    select_speech_provider,
)
from omnivoice.session import CallSession


def make_session(settings):
    services = SimpleNamespace(
        settings=settings,
        vad=SimpleNamespace(session=lambda: None),
    )
    tenant = {"config": {"backchannels": [], "language": "en-IN"}}
    return CallSession("test-call", tenant, object(), services)


def test_default_selection_preserves_sarvam_session(monkeypatch):
    for name in ("STT_PROVIDER", "TTS_PROVIDER", "OMNI_STT_PROVIDER", "OMNI_TTS_PROVIDER"):
        monkeypatch.delenv(name, raising=False)
    settings = Settings(_env_file=None)
    assert settings.stt_provider == settings.tts_provider == "sarvam"
    session = make_session(settings)
    assert isinstance(session.stt, SarvamSTT)
    assert isinstance(session.tts, SarvamTTS)


def test_explicit_sarvam_selection_preserves_session():
    settings = Settings(_env_file=None, stt_provider="sarvam", tts_provider="sarvam")
    session = make_session(settings)
    assert isinstance(session.stt, SarvamSTT)
    assert isinstance(session.tts, SarvamTTS)


def test_gnani_environment_configuration_is_parsed_and_redacted(monkeypatch):
    test_key = "test-only-gnani-secret"
    monkeypatch.setenv("GNANI_API_KEY", test_key)
    monkeypatch.setenv("STT_PROVIDER", "gnani")
    monkeypatch.setenv("TTS_PROVIDER", "sarvam")
    settings = Settings(_env_file=None)
    assert settings.gnani_api_key.get_secret_value() == test_key
    assert settings.stt_provider == "gnani"
    assert settings.tts_provider == "sarvam"
    assert test_key not in repr(settings)
    assert test_key not in str(settings.model_dump(mode="json"))


@pytest.mark.parametrize("modality", ["stt", "tts"])
def test_gnani_selection_requires_key(tmp_path, modality):
    kwargs = {f"{modality}_provider": "gnani"}
    settings = Settings(
        _env_file=None,
        gnani_api_key="",
        sarvam_api_key="test-sarvam-key",
        groq_api_key="test-groq-key",
        silero_model=tmp_path / "missing.onnx",
        **kwargs,
    )
    blockers = settings.missing_voice_settings()
    assert "GNANI_API_KEY" in blockers
    assert "GNANI_STT_API_CONTRACT_UNAVAILABLE" not in blockers
    assert "GNANI_TTS_API_CONTRACT_UNAVAILABLE" not in blockers
    assert "SARVAM_API_KEY" not in blockers


def test_gnani_stt_and_tts_are_constructed_and_voice_ready(tmp_path):
    key = "test-only-gnani-secret"
    settings = Settings(
        _env_file=None,
        database=tmp_path / "provider.db",
        admin_token="test-admin-token",
        gnani_api_key=key,
        groq_api_key="test-groq-key",
        stt_provider="gnani",
        tts_provider="gnani",
        silero_model=Path("models/silero_vad.onnx"),
    )
    session = make_session(settings)
    assert isinstance(session.stt, GnaniSTT)
    assert isinstance(session.tts, GnaniTTS)
    with TestClient(create_app(settings)) as client:
        assert client.get("/readyz").status_code == 200
        response = client.get("/api/status", headers={"Authorization": "Bearer test-admin-token"})
        assert response.status_code == 200
        state = response.json()
        assert state["voice_ready"] is True
        assert state["providers"]["stt"] == "gnani"
        assert state["providers"]["tts"] == "gnani"
        assert "GNANI_API_KEY" not in state["missing"]
        assert "GNANI_TTS_API_CONTRACT_UNAVAILABLE" not in state["missing"]
        assert key not in response.text
        assert key not in client.get("/readyz").text


def test_gnani_stt_with_sarvam_tts_is_constructed_and_voice_ready(tmp_path):
    key = "test-only-gnani-secret"
    settings = Settings(
        _env_file=None,
        database=tmp_path / "provider.db",
        admin_token="test-admin-token",
        gnani_api_key=key,
        sarvam_api_key="test-sarvam-key",
        groq_api_key="test-groq-key",
        stt_provider="gnani",
        tts_provider="sarvam",
        silero_model=Path("models/silero_vad.onnx"),
    )
    session = make_session(settings)
    assert isinstance(session.stt, GnaniSTT)
    assert isinstance(session.tts, SarvamTTS)
    with TestClient(create_app(settings)) as client:
        response = client.get("/api/status", headers={"Authorization": "Bearer test-admin-token"})
        state = response.json()
        assert state["providers"]["stt"] == "gnani"
        assert state["providers"]["tts"] == "sarvam"
        assert "GNANI_STT_API_CONTRACT_UNAVAILABLE" not in state["missing"]
        assert "GNANI_TTS_API_CONTRACT_UNAVAILABLE" not in state["missing"]
        assert "GNANI_API_KEY" not in state["missing"]
        assert state["voice_ready"] is True
        assert client.get("/readyz").status_code == 200


def test_selector_does_not_construct_sarvam_when_gnani_is_selected():
    def unexpected_sarvam():
        raise AssertionError("Sarvam should not be constructed for Gnani")

    with pytest.raises(SpeechProviderUnavailable, match="Gnani STT"):
        select_speech_provider("gnani", "STT", unexpected_sarvam)


@pytest.mark.parametrize("field", ["stt_provider", "tts_provider"])
def test_invalid_provider_names_are_rejected(field):
    with pytest.raises(ValidationError, match="sarvam.*gnani"):
        Settings(_env_file=None, **{field: "unknown"})
