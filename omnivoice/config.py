from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="OMNI_", env_file=".env", extra="ignore")
    admin_token: SecretStr = SecretStr("")
    database: Path = Path("data/omnivoice.db")
    public_base_url: str = ""
    sarvam_api_key: SecretStr = SecretStr("")
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
    exotel_account_sid: str = ""
    exotel_api_key: SecretStr = SecretStr("")
    exotel_api_token: SecretStr = SecretStr("")
    twilio_account_sid: str = ""
    twilio_auth_token: SecretStr = SecretStr("")
    enable_outbound: bool = False

    def missing_voice_settings(self) -> list[str]:
        missing = []
        for name in ("sarvam_api_key", "groq_api_key"):
            if not getattr(self, name).get_secret_value():
                missing.append(name.upper())
        if not self.silero_model.is_file():
            missing.append("SILERO_MODEL")
        return missing
