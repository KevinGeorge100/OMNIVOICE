"""Bounded, cancellation-aware recovery for speech and inference providers."""

import asyncio
import logging
import random

import httpx
from websockets.exceptions import ConnectionClosed


class ProviderError(RuntimeError):
    category = "provider"
    retryable = False

    def __init__(self, provider: str, modality: str, detail: str):
        self.provider = provider
        self.modality = modality
        super().__init__(f"{modality} provider {detail}")


class ProviderTransientError(ProviderError):
    category = "transient"
    retryable = True


class ProviderTimeoutError(ProviderTransientError):
    category = "timeout"


class ProviderRateLimitError(ProviderTransientError):
    category = "rate_limit"


class ProviderUnavailableError(ProviderTransientError):
    category = "unavailable"


class ProviderAuthError(ProviderError):
    category = "auth"


class ProviderProtocolError(ProviderError):
    category = "protocol"


class ProviderCancelledError(ProviderError):
    category = "cancelled"


def classify_error(error: Exception, provider: str, modality: str) -> ProviderError:
    """Never copy upstream response bodies, URLs, headers, or exception text."""
    if isinstance(error, ProviderError):
        return error
    status = None
    if isinstance(error, httpx.HTTPStatusError):
        status = error.response.status_code
    elif hasattr(error, "response"):
        status = getattr(error.response, "status_code", None)
    if status == 429:
        return ProviderRateLimitError(provider, modality, "HTTP error: 429")
    if status in (502, 503, 504):
        return ProviderUnavailableError(provider, modality, f"HTTP error: {status}")
    if status in (401, 403):
        return ProviderAuthError(provider, modality, f"HTTP error: {status}")
    if status is not None:
        return ProviderProtocolError(provider, modality, f"HTTP error: {status}")
    if isinstance(error, (TimeoutError, httpx.TimeoutException)):
        return ProviderTimeoutError(provider, modality, "timeout")
    if isinstance(error, (ConnectionClosed, ConnectionError, OSError, httpx.RequestError)):
        return ProviderTransientError(provider, modality, "connection error")
    return ProviderProtocolError(provider, modality, "invalid response")


class RetryPolicy:
    def __init__(self, settings, *, jitter=None, sleep=None):
        self.max_retries = settings.provider_max_retries
        self.base_ms = settings.provider_backoff_base_ms
        self.max_ms = settings.provider_backoff_max_ms
        self.jitter = jitter or random.random
        self.sleep = sleep or asyncio.sleep

    def delay_ms(self, retry_number: int) -> float:
        exponential = min(self.max_ms, self.base_ms * (2 ** (retry_number - 1)))
        return min(self.max_ms, exponential * (1 + 0.2 * self.jitter()))

    async def _backoff(self, delay_ms: float, cancel_event, provider, modality):
        if cancel_event is None:
            await self.sleep(delay_ms / 1000)
            return
        if cancel_event.is_set():
            raise ProviderCancelledError(provider, modality, "cancelled")
        sleeper = asyncio.create_task(self.sleep(delay_ms / 1000))
        cancelled = asyncio.create_task(cancel_event.wait())
        try:
            done, _ = await asyncio.wait({sleeper, cancelled}, return_when=asyncio.FIRST_COMPLETED)
            if cancelled in done or cancel_event.is_set():
                raise ProviderCancelledError(provider, modality, "cancelled")
            await sleeper
        finally:
            for task in (sleeper, cancelled):
                if not task.done():
                    task.cancel()
            await asyncio.gather(sleeper, cancelled, return_exceptions=True)

    async def _failure(self, error, provider, modality, attempt, emitted, cancel_event):
        if cancel_event is not None and cancel_event.is_set():
            raise ProviderCancelledError(provider, modality, "cancelled") from None
        failure = classify_error(error, provider, modality)
        retry = failure.retryable and not emitted and attempt <= self.max_retries
        delay = self.delay_ms(attempt) if retry else 0
        logging.getLogger("omnivoice.resilience").warning(
            "provider_failure provider=%s modality=%s attempt_number=%d "
            "failure_category=%s recovered=false retry_delay_ms=%.0f final_outcome=%s",
            provider, modality, attempt, failure.category, delay,
            "retrying" if retry else "exhausted",
        )
        if not retry:
            raise failure from None
        await self._backoff(delay, cancel_event, provider, modality)

    async def _check_success(self, value, provider, modality, cancel_event):
        if cancel_event is None or not cancel_event.is_set():
            return value
        close = getattr(value, "close", None)
        if close is not None:
            try:
                await close()
            except Exception:
                pass
        raise ProviderCancelledError(provider, modality, "cancelled")

    async def call(self, operation, provider, modality, *, cancel_event=None):
        for attempt in range(1, self.max_retries + 2):
            if cancel_event is not None and cancel_event.is_set():
                raise ProviderCancelledError(provider, modality, "cancelled")
            try:
                value = await operation()
            except Exception as error:
                await self._failure(error, provider, modality, attempt, False, cancel_event)
            else:
                value = await self._check_success(value, provider, modality, cancel_event)
                if attempt > 1:
                    logging.getLogger("omnivoice.resilience").info(
                        "provider_recovered provider=%s modality=%s attempt_number=%d recovered=true",
                        provider, modality, attempt,
                    )
                return value

    async def recover(self, error, operation, provider, modality, *, cancel_event=None):
        """A live stream's failed socket is the initial attempt, not a free retry."""
        await self._failure(error, provider, modality, 1, False, cancel_event)
        for retry_number in range(1, self.max_retries + 1):
            if cancel_event is not None and cancel_event.is_set():
                raise ProviderCancelledError(provider, modality, "cancelled")
            try:
                value = await operation()
            except Exception as failure:
                await self._failure(
                    failure, provider, modality, retry_number + 1, False, cancel_event
                )
            else:
                value = await self._check_success(value, provider, modality, cancel_event)
                logging.getLogger("omnivoice.resilience").info(
                    "provider_recovered provider=%s modality=%s attempt_number=%d recovered=true",
                    provider, modality, retry_number + 1,
                )
                return value

    async def stream(self, factory, provider, modality, *, cancel_event=None):
        for attempt in range(1, self.max_retries + 2):
            if cancel_event is not None and cancel_event.is_set():
                raise ProviderCancelledError(provider, modality, "cancelled")
            emitted = False
            iterator = factory()
            try:
                async for item in iterator:
                    if cancel_event is not None and cancel_event.is_set():
                        raise ProviderCancelledError(provider, modality, "cancelled")
                    emitted = True
                    yield item
            except Exception as error:
                await self._failure(error, provider, modality, attempt, emitted, cancel_event)
            else:
                if cancel_event is not None and cancel_event.is_set():
                    raise ProviderCancelledError(provider, modality, "cancelled")
                if attempt > 1:
                    logging.getLogger("omnivoice.resilience").info(
                        "provider_recovered provider=%s modality=%s attempt_number=%d recovered=true",
                        provider, modality, attempt,
                    )
                return
            finally:
                if hasattr(iterator, "aclose"):
                    await iterator.aclose()


class ReplayableText:
    """Keep a streaming text source alive while an unspoken TTS attempt reconnects."""

    def __init__(self, source):
        self.source = source
        self.cache = []
        self.condition = asyncio.Condition()
        self.done = False
        self.error = None
        self.producer = asyncio.create_task(self._collect())

    async def _collect(self):
        try:
            async for text in self.source:
                async with self.condition:
                    self.cache.append(text)
                    self.condition.notify_all()
        except Exception as error:
            self.error = error
        finally:
            async with self.condition:
                self.done = True
                self.condition.notify_all()

    async def iterate(self):
        index = 0
        while True:
            async with self.condition:
                while index >= len(self.cache) and not self.done:
                    await self.condition.wait()
                if index < len(self.cache):
                    item = self.cache[index]
                    index += 1
                elif self.error is not None:
                    raise self.error
                else:
                    return
            yield item

    async def close(self):
        if not self.producer.done():
            self.producer.cancel()
        await asyncio.gather(self.producer, return_exceptions=True)
