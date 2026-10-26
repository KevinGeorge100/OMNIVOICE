"""Bounded, short-lived masked caller correlation for Vobiz callbacks."""

import hashlib
import re
import time
from collections import OrderedDict


class PendingVobizCallers:
    def __init__(self, *, limit: int = 100, ttl_seconds: float = 60):
        self.limit = limit
        self.ttl_seconds = ttl_seconds
        self._entries: OrderedDict[tuple[str, str], tuple[float, str]] = OrderedDict()

    def _key(self, line_id: str, call_id: str) -> tuple[str, str]:
        return line_id, hashlib.sha256(call_id.encode()).hexdigest()

    def _expire(self, now: float) -> None:
        for key, (created, _) in list(self._entries.items()):
            if now - created >= self.ttl_seconds:
                del self._entries[key]

    def remember(self, line_id: str, call_id: object, caller: object) -> None:
        if (
            not isinstance(call_id, str) or not 1 <= len(call_id) <= 128
            or not isinstance(caller, str) or not re.fullmatch(r"\+?[0-9]{8,15}", caller)
        ):
            return
        now = time.monotonic()
        self._expire(now)
        key = self._key(line_id, call_id)
        self._entries[key] = (now, "••••" + caller[-4:])
        self._entries.move_to_end(key)
        while len(self._entries) > self.limit:
            self._entries.popitem(last=False)

    def take(self, line_id: str, call_id: str) -> str | None:
        self._expire(time.monotonic())
        entry = self._entries.pop(self._key(line_id, call_id), None)
        return entry[1] if entry else None
