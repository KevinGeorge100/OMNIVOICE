from typing import Literal

from pydantic import BaseModel, Field, field_validator

LANGUAGES = {
    "en-IN",
    "hi-IN",
    "bn-IN",
    "gu-IN",
    "kn-IN",
    "ml-IN",
    "mr-IN",
    "od-IN",
    "pa-IN",
    "ta-IN",
    "te-IN",
}


class TenantInput(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    language: str = "en-IN"
    greeting: str = Field(min_length=1, max_length=400)
    instructions: str = Field(default="", max_length=3000)
    confirmation_phrases: list[str] = Field(
        default_factory=lambda: ["yes confirm", "i confirm", "yes please proceed"]
    )
    backchannels: list[str] = Field(default_factory=lambda: ["mm hmm", "mhm", "uh huh", "yeah", "okay", "ok"])

    @field_validator("language")
    @classmethod
    def supported_language(cls, value):
        if value not in LANGUAGES:
            raise ValueError("Unsupported TTS language code")
        return value

    @field_validator("confirmation_phrases", "backchannels")
    @classmethod
    def bounded_phrases(cls, value):
        if not 1 <= len(value) <= 30 or any(not s.strip() or len(s) > 100 for s in value):
            raise ValueError("Provide 1–30 nonempty phrases, each at most 100 characters")
        return value


class FAQInput(BaseModel):
    question: str = Field(min_length=3, max_length=500)
    answer: str = Field(min_length=1, max_length=2000)
    approved: bool = False


class LineInput(BaseModel):
    provider: Literal["exotel", "twilio"]
    number: str = Field(pattern=r"^\+[1-9]\d{7,14}$")


class DialInput(BaseModel):
    line_id: str
    to: str = Field(pattern=r"^\+[1-9]\d{7,14}$")
    consent_confirmed: bool = False


class ToolInput(BaseModel):
    name: str = Field(pattern=r"^[a-z][a-z0-9_]{1,40}$")
    description: str = Field(min_length=5, max_length=500)
    kind: Literal["read", "write"]
    url: str = Field(max_length=2000)
    parameters: dict
    auth_env: str = Field(default="", pattern=r"^(|OMNI_TOOL_[A-Z0-9_]+)$")
    # Server-owned template; the model supplies values, never executable SQL or URLs.
    confirmation_template: str = Field(default="", max_length=1000)


class Transcript(BaseModel):
    text: str
    final: bool = False
    language: str | None = None
