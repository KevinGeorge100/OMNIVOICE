"""Small, deterministic streaming text preparation for telephone speech."""

import re
from urllib.parse import urlsplit


def normalize_speech(text: str) -> str:
    """Remove visual markup while keeping the words and their order."""
    def spoken_url(match):
        raw = match.group()
        url = raw.rstrip(".,!?।;:")
        punctuation = raw[len(url) :]
        try:
            host = (urlsplit(url).hostname or "").removeprefix("www.")
        except ValueError:
            host = "link"
        return host.replace(".", " dot ") + punctuation

    text = re.sub(r"(?m)^\s*```[^\n]*$", "", text)
    text = re.sub(r"\[([^\]]+)\]\(https?://[^)]+\)", r"\1", text)
    text = re.sub(r"https?://[^\s<>()]+", spoken_url, text)
    lines = []
    bullets = []

    def finish_bullets():
        if not bullets:
            return
        if len(bullets) == 1:
            lines.append(bullets[0] + ".")
        elif len(bullets) == 2:
            lines.append(f"{bullets[0]} and {bullets[1]}.")
        else:
            lines.append(", ".join(bullets[:-1]) + f", and {bullets[-1]}.")
        bullets.clear()

    for raw in text.splitlines():
        line = raw.strip()
        if re.fullmatch(r"[-*_\s]{3,}", line):
            continue
        heading = bool(re.match(r"^#{1,6}\s+", line))
        line = re.sub(r"^#{1,6}\s*", "", line)
        is_bullet = bool(re.match(r"(?:[-*+]\s+|\d+[.)]\s+)", line))
        line = re.sub(r"^(?:[-*+]\s+|\d+[.)]\s+)", "", line)
        line = line.replace("**", "").replace("__", "").replace("`", "")
        line = re.sub(r"(?<!\w)[*_](?=\w)|(?<=\w)[*_](?!\w)", "", line)
        line = line.replace("→", " to ").replace("↔", " and ").replace("&", " and ")
        line = line.replace("—", ", ").replace("–", ", ").replace("|", ", ")
        line = re.sub(r"[\u2600-\u27bf\U0001f300-\U0001faff]", "", line)
        line = re.sub(r"\s+", " ", line).strip(" •|~")
        if not line:
            continue
        if line.endswith(":"):
            line = line[:-1] + "."
        if heading and not line.endswith((".", "!", "?", "।")):
            line += "."
        if is_bullet:
            bullets.append(line.rstrip(".!?।"))
        else:
            finish_bullets()
            lines.append(line)
    finish_bullets()
    return re.sub(r"\s+", " ", " ".join(lines)).strip()


class SpeechSegmenter:
    """Emit useful phrases early; retain tiny sentences for adjacent context."""

    def __init__(self, first_min: int = 32, next_min: int = 96, max_chars: int = 220):
        self.buffer = ""
        self.count = 0
        self.first_min = first_min
        self.next_min = next_min
        self.max_chars = max_chars

    def feed(self, delta: str) -> list[str]:
        self.buffer += delta
        ready = []
        while self.buffer:
            minimum = self.first_min if self.count == 0 else self.next_min
            boundary = None
            for match in re.finditer(r"[.!?।](?=\s|$)", self.buffer):
                if len(self.buffer[: match.end()].strip()) >= minimum:
                    boundary = match.end()
                    break
            if boundary is None and len(self.buffer) >= self.max_chars:
                boundary = self.buffer.rfind(" ", 0, self.max_chars + 1)
                if boundary < minimum:
                    boundary = None
            if boundary is None:
                break
            segment = self.buffer[:boundary].strip()
            self.buffer = self.buffer[boundary:].lstrip()
            if segment:
                ready.append(segment)
                self.count += 1
        return ready

    def finish(self) -> str:
        segment = self.buffer.strip()
        self.buffer = ""
        if segment:
            self.count += 1
        return segment
