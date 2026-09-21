import re
import time
from enum import StrEnum


def normalize(text: str) -> str:
    return " ".join(re.sub(r"[^\w\s]", " ", text.casefold()).split())


class CancelReason(StrEnum):
    PLAYBACK_INTERRUPT = "playback_interrupt"
    SUPERSEDED = "superseded"
    CONTROL_HALT = "control_halt"


CONTROL_HALT_PHRASES: frozenset[str] = frozenset(
    {"wait", "stop", "hold on", "pause", "cancel"}
)


def is_control_halt(text: str) -> bool:
    return normalize(text) in CONTROL_HALT_PHRASES


class State(StrEnum):
    IDLE = "Idle"
    LISTEN = "Listen"
    SPEAK = "Speak"


class FlexDuo:
    """Acoustic candidate -> semantic decision. VAD alone never clears playback."""

    def __init__(self, backchannels: list[str]):
        self.state = State.LISTEN
        self.playing = False
        self.candidate = False
        self.last_voice = 0.0
        self.backchannels = {normalize(s) for s in backchannels}

    def voice(self, probability: float, now: float | None = None):
        now = time.monotonic() if now is None else now
        if probability >= 0.6:
            self.last_voice = now
            if self.playing:
                self.candidate = True
                self.state = State.IDLE
            else:
                self.state = State.LISTEN
        elif self.candidate and now - self.last_voice > 0.6:
            self.candidate = False
            self.state = State.SPEAK if self.playing else State.LISTEN

    def transcript(self, text: str) -> bool:
        value = normalize(text)
        if not value:
            return False
        if self.playing and value in self.backchannels:
            self.state = State.SPEAK
            self.candidate = False
            return False
        if self.playing and self.candidate:
            self.playing = False
            self.candidate = False
            self.state = State.LISTEN
            return True
        return False

    def speaking(self):
        self.playing = True
        self.state = State.SPEAK

    def played(self):
        self.playing = False
        self.candidate = False
        self.state = State.LISTEN
