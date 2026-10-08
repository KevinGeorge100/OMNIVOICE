from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="OMNI_", env_file=".env", extra="ignore")
    admin_token: SecretStr = SecretStr("")
    database: Path = Path("data/omnivoice.db")
    public_base_url: str = ""
    sarvam_api_key: SecretStr = SecretStr("")
    gnani_api_key: SecretStr = Field(
        default=SecretStr(""), validation_alias=AliasChoices("GNANI_API_KEY", "OMNI_GNANI_API_KEY")
    )
    stt_provider: Literal["sarvam", "gnani"] = Field(
        default="sarvam", validation_alias=AliasChoices("STT_PROVIDER", "OMNI_STT_PROVIDER")
    )
    tts_provider: Literal["sarvam", "gnani"] = Field(
        default="sarvam", validation_alias=AliasChoices("TTS_PROVIDER", "OMNI_TTS_PROVIDER")
    )
    gnani_tts_model: str = Field(
        default="timbre-v2.5", validation_alias=AliasChoices("GNANI_TTS_MODEL", "OMNI_GNANI_TTS_MODEL")
    )
    gnani_tts_voice: str = Field(
        default="Pranav", validation_alias=AliasChoices("GNANI_TTS_VOICE", "OMNI_GNANI_TTS_VOICE")
    )
    gnani_tts_sample_rate: int = Field(
        default=8000, validation_alias=AliasChoices("GNANI_TTS_SAMPLE_RATE", "OMNI_GNANI_TTS_SAMPLE_RATE")
    )
    groq_api_key: SecretStr = SecretStr("")
    groq_model: str = "llama-3.1-8b-instant"
    stt_model: str = "saaras:v3-realtime"
    tts_model: str = "bulbul:v3"
    tts_speaker: str = "shubh"
    silero_model: Path = Path("models/silero_vad.onnx")
    semantic_enabled: bool = False
    embedding_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    embedding_cache: str = "models/embeddings"
    cache_threshold: float = Field(0.93, ge=0.8, le=1)
    cache_ttl_seconds: int = Field(300, ge=1)
    max_calls: int = Field(20, ge=1, le=1000)
    max_call_seconds: int = Field(1800, ge=30, le=14400)
    endpoint_silence_ms: int = Field(200, ge=100, le=2000)
    continuation_interval_ms: int = Field(750, ge=100, le=2000)
    provider_max_retries: int = Field(
        default=2, ge=0, le=5,
        validation_alias=AliasChoices("PROVIDER_MAX_RETRIES", "OMNI_PROVIDER_MAX_RETRIES"),
    )
    provider_backoff_base_ms: int = Field(
        default=150, ge=1, le=2000,
        validation_alias=AliasChoices("PROVIDER_BACKOFF_BASE_MS", "OMNI_PROVIDER_BACKOFF_BASE_MS"),
    )
    provider_backoff_max_ms: int = Field(
        default=1200, ge=1, le=5000,
        validation_alias=AliasChoices("PROVIDER_BACKOFF_MAX_MS", "OMNI_PROVIDER_BACKOFF_MAX_MS"),
    )
    exotel_account_sid: str = ""
    exotel_api_key: SecretStr = SecretStr("")
    exotel_api_token: SecretStr = SecretStr("")
    twilio_account_sid: str = ""
    twilio_auth_token: SecretStr = SecretStr("")
    enable_outbound: bool = False

    @model_validator(mode="after")
    def validate_provider_backoff(self):
        if self.provider_backoff_max_ms < self.provider_backoff_base_ms:
            raise ValueError("PROVIDER_BACKOFF_MAX_MS must be >= PROVIDER_BACKOFF_BASE_MS")
        return self

    def missing_voice_settings(self) -> list[str]:
        missing = []
        if "sarvam" in (self.stt_provider, self.tts_provider) and not self.sarvam_api_key.get_secret_value():
            missing.append("SARVAM_API_KEY")
        if "gnani" in (self.stt_provider, self.tts_provider):
            if not self.gnani_api_key.get_secret_value():
                missing.append("GNANI_API_KEY")
        if self.tts_provider == "gnani":
            if not self.gnani_tts_voice:
                missing.append("GNANI_TTS_VOICE")
            if not self.gnani_tts_model:
                missing.append("GNANI_TTS_MODEL")
            if self.gnani_tts_sample_rate not in (8000, 16000, 24000, 48000):
                missing.append("GNANI_TTS_SAMPLE_RATE")
        if not self.groq_api_key.get_secret_value():
            missing.append("GROQ_API_KEY")
        if not self.silero_model.is_file():
            missing.append("SILERO_MODEL")
        return missing
