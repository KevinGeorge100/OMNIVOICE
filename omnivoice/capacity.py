"""Single-process admission and bounded provider/API work for the voice runtime."""

import asyncio
import logging
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager

from .resilience import ProviderError

LOG = logging.getLogger("omnivoice.capacity")


class ProviderCapacityError(ProviderError):
    category = "local_capacity"

    def __init__(self, provider: str, modality: str):
        super().__init__(provider, modality, "concurrency exhausted")


class Capacity:
    """Reservations are process-local and never inferred from the sessions dict."""

    def __init__(self, settings):
        self.global_limit = settings.max_calls
        self.tenant_limit = settings.tenant_max_calls
        self._lock = asyncio.Lock()
        self._calls: dict[str, str] = {}
        self._tenant_counts: dict[str, int] = defaultdict(int)
        self.rejected = {"global": 0, "tenant": 0}
        self.provider_rate_limit_events = 0
        self._limits = {
            "LLM": settings.max_llm_inflight,
            "TTS": settings.max_tts_inflight,
            "STT": settings.max_stt_inflight,
        }
        self._semaphores = {name: asyncio.Semaphore(limit) for name, limit in self._limits.items()}
        self._inflight = {name: 0 for name in self._limits}
        self._provider_rejected = {name: 0 for name in self._limits}
        self._last_wait_ms = {name: 0.0 for name in self._limits}
        self._api_hits: dict[tuple[str, str], deque[float]] = {}
        self._api_window = 60.0
        self._api_max_keys = 4096

    async def admit(self, call_id: str, tenant_id: str) -> str | None:
        async with self._lock:
            if call_id in self._calls:
                raise ValueError("Call already admitted")
            if self._tenant_counts.get(tenant_id, 0) >= self.tenant_limit:
                self.rejected["tenant"] += 1
                reason = "tenant_capacity_exhausted"
                count, limit = self._tenant_counts[tenant_id], self.tenant_limit
            elif len(self._calls) >= self.global_limit:
                self.rejected["global"] += 1
                reason = "local_capacity_exhausted"
                count, limit = len(self._calls), self.global_limit
            else:
                self._calls[call_id] = tenant_id
                self._tenant_counts[tenant_id] += 1
                return None
        LOG.warning(
            "call_admission_rejected tenant_id=%s reason=%s current=%d limit=%d",
            tenant_id, reason, count, limit,
        )
        return reason

    async def release(self, call_id: str) -> bool:
        async with self._lock:
            tenant_id = self._calls.pop(call_id, None)
            if tenant_id is None:
                return False
            count = self._tenant_counts[tenant_id] - 1
            if count:
                self._tenant_counts[tenant_id] = count
            else:
                del self._tenant_counts[tenant_id]
            return True

    def tenant_calls(self, tenant_id: str) -> int:
        return self._tenant_counts.get(tenant_id, 0)

    def snapshot(self) -> dict:
        return {
            "active_calls": len(self._calls),
            "global_call_limit": self.global_limit,
            "tenant_call_limit": self.tenant_limit,
            "saturated": len(self._calls) >= self.global_limit,
            "rejected_calls_total": sum(self.rejected.values()),
            "rejected_calls_by_reason": dict(self.rejected),
            "provider_rate_limit_events_total": self.provider_rate_limit_events,
            "provider_inflight": dict(self._inflight),
            "provider_limits": dict(self._limits),
            "provider_concurrency_rejected": dict(self._provider_rejected),
            "provider_last_wait_ms": dict(self._last_wait_ms),
            "scope": "single_process",
        }

    @asynccontextmanager
    async def provider_slot(self, modality: str, provider: str):
        semaphore = self._semaphores[modality]
        started = time.perf_counter()
        try:
            await asyncio.wait_for(semaphore.acquire(), timeout=0.05)
        except TimeoutError:
            self._provider_rejected[modality] += 1
            LOG.warning(
                "provider_concurrency_rejected provider=%s modality=%s current=%d limit=%d reason=local_capacity_exhausted",
                provider, modality, self._inflight[modality], self._limits[modality],
            )
            raise ProviderCapacityError(provider, modality) from None
        wait_ms = (time.perf_counter() - started) * 1000
        self._last_wait_ms[modality] = wait_ms
        if wait_ms >= 1:
            LOG.info(
                "provider_concurrency_wait provider=%s modality=%s wait_ms=%.1f",
                provider, modality, wait_ms,
            )
        self._inflight[modality] += 1
        try:
            yield
        finally:
            self._inflight[modality] -= 1
            semaphore.release()

    def allow_api(self, scope: str, key: str, limit: int) -> bool:
        """Fixed 60-second window; prune expired keys and cap memory."""
        now = time.monotonic()
        if len(self._api_hits) >= self._api_max_keys:
            self._api_hits = {
                name: hits for name, hits in self._api_hits.items()
                if hits and hits[-1] > now - self._api_window
            }
            if len(self._api_hits) >= self._api_max_keys and (scope, key) not in self._api_hits:
                return False
        hits = self._api_hits.setdefault((scope, key), deque())
        while hits and hits[0] <= now - self._api_window:
            hits.popleft()
        if len(hits) >= limit:
            return False
        hits.append(now)
        return True
