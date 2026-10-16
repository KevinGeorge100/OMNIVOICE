from datetime import datetime
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, Field, field_validator, model_validator

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
    timezone: str = "Asia/Kolkata"
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

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value):
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError):
            if value != "Asia/Kolkata":
                raise ValueError("Use an IANA time zone") from None
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


class SalesLeadInput(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    identifier: str = Field(min_length=1, max_length=80)
    email: str | None = Field(default=None, max_length=254)
    status: str = Field(default="new", min_length=1, max_length=40)
    source: str = Field(default="operator", min_length=1, max_length=40)
    notes: str = Field(default="", max_length=240)


class DemoSlotInput(BaseModel):
    start_at: datetime
    end_at: datetime

    @model_validator(mode="after")
    def ordered_with_timezone(self):
        if (self.start_at.tzinfo is None or self.end_at.tzinfo is None
                or self.end_at <= self.start_at):
            raise ValueError("Slots require ordered timezone-aware datetimes")
        return self


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
