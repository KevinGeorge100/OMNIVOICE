"""Deterministic validation for OV-010 capacity, admission, and overload controls."""

import asyncio
import time
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient

from omnivoice.app import create_app
from omnivoice.capacity import Capacity, ProviderCapacityError
from omnivoice.config import Settings
from omnivoice.providers import GnaniSTT
from omnivoice.resilience import (
    ProviderCancelledError,
    ProviderRateLimitError,
    RetryPolicy,
    classify_error,
)
from omnivoice.session import CallEnded, CallSession
from omnivoice.transport import MediaTransport


def make_settings(**overrides):
    defaults = {
        "sarvam_api_key": "test-sarvam-key",
        "gnani_api_key": "test-gnani-key",
        "groq_api_key": "test-groq-key",
        "admin_token": "test-admin-token",
        "max_calls": 10,
        "tenant_max_calls": 3,
        "max_llm_inflight": 4,
        "max_tts_inflight": 4,
        "max_stt_inflight": 2,
        "provider_max_retries": 2,
        "provider_backoff_base_ms": 10,
        "provider_backoff_max_ms": 100,
    }
    defaults.update(overrides)
    return Settings(_env_file=None, **defaults)


# ==============================================================================
# CALL ADMISSION (1 - 10)
# ==============================================================================


@pytest.mark.asyncio
async def test_below_global_limit_admitted():
    capacity = Capacity(make_settings(max_calls=5, tenant_max_calls=3))
    assert await capacity.admit("call-1", "tenant-1") is None
    assert capacity.snapshot()["active_calls"] == 1


@pytest.mark.asyncio
async def test_global_max_rejected():
    capacity = Capacity(make_settings(max_calls=2, tenant_max_calls=2))
    assert await capacity.admit("c1", "t1") is None
    assert await capacity.admit("c2", "t2") is None
    assert await capacity.admit("c3", "t3") == "local_capacity_exhausted"
    assert capacity.snapshot()["active_calls"] == 2
    assert capacity.snapshot()["rejected_calls_by_reason"]["global"] == 1


@pytest.mark.asyncio
async def test_tenant_max_rejected():
    capacity = Capacity(make_settings(max_calls=10, tenant_max_calls=2))
    assert await capacity.admit("c1", "t1") is None
    assert await capacity.admit("c2", "t1") is None
    assert await capacity.admit("c3", "t1") == "tenant_capacity_exhausted"
    assert capacity.snapshot()["rejected_calls_by_reason"]["tenant"] == 1


@pytest.mark.asyncio
async def test_tenant_b_still_admitted_while_tenant_a_saturated():
    capacity = Capacity(make_settings(max_calls=10, tenant_max_calls=2))
    assert await capacity.admit("c1", "t1") is None
    assert await capacity.admit("c2", "t1") is None
    assert await capacity.admit("c3", "t1") == "tenant_capacity_exhausted"
    assert await capacity.admit("c4", "t2") is None
    assert capacity.tenant_calls("t2") == 1


@pytest.mark.asyncio
async def test_release_frees_global_slot():
    capacity = Capacity(make_settings(max_calls=1, tenant_max_calls=1))
    assert await capacity.admit("c1", "t1") is None
    assert await capacity.admit("c2", "t2") == "local_capacity_exhausted"
    assert await capacity.release("c1") is True
    assert await capacity.admit("c2", "t2") is None


@pytest.mark.asyncio
async def test_release_frees_tenant_slot():
    capacity = Capacity(make_settings(max_calls=10, tenant_max_calls=1))
    assert await capacity.admit("c1", "t1") is None
    assert await capacity.admit("c2", "t1") == "tenant_capacity_exhausted"
    assert await capacity.release("c1") is True
    assert await capacity.admit("c2", "t1") is None


@pytest.mark.asyncio
async def test_duplicate_release_is_safe():
    capacity = Capacity(make_settings())
    assert await capacity.admit("c1", "t1") is None
    assert await capacity.release("c1") is True
    assert await capacity.release("c1") is False
    assert capacity.tenant_calls("t1") == 0


@pytest.mark.asyncio
async def test_counts_never_become_negative():
    capacity = Capacity(make_settings())
    assert await capacity.release("non-existent") is False
    assert capacity.tenant_calls("t1") == 0
    assert capacity.snapshot()["active_calls"] == 0


@pytest.mark.asyncio
async def test_concurrent_admissions_cannot_exceed_global_limit():
    capacity = Capacity(make_settings(max_calls=5, tenant_max_calls=10))
    results = await asyncio.gather(
        *(capacity.admit(f"c-{i}", f"t-{i}") for i in range(20))
    )
    admitted = sum(r is None for r in results)
    rejected = sum(r == "local_capacity_exhausted" for r in results)
    assert admitted == 5
    assert rejected == 15
    assert capacity.snapshot()["active_calls"] == 5


@pytest.mark.asyncio
async def test_concurrent_admissions_cannot_exceed_tenant_limit():
    capacity = Capacity(make_settings(max_calls=20, tenant_max_calls=3))
    results = await asyncio.gather(
        *(capacity.admit(f"c-{i}", "same-tenant") for i in range(10))
    )
    admitted = sum(r is None for r in results)
    rejected = sum(r == "tenant_capacity_exhausted" for r in results)
    assert admitted == 3
    assert rejected == 7
    assert capacity.tenant_calls("same-tenant") == 3


# ==============================================================================
# PROVIDER CAPACITY (11 - 17)
# ==============================================================================


@pytest.mark.asyncio
async def test_llm_provider_slot_acquired_and_released():
    capacity = Capacity(make_settings(max_llm_inflight=2))
    assert capacity.snapshot()["provider_inflight"]["LLM"] == 0
    async with capacity.provider_slot("LLM", "groq"):
        assert capacity.snapshot()["provider_inflight"]["LLM"] == 1
    assert capacity.snapshot()["provider_inflight"]["LLM"] == 0


@pytest.mark.asyncio
async def test_tts_slot_acquired_and_released():
    capacity = Capacity(make_settings(max_tts_inflight=2))
    async with capacity.provider_slot("TTS", "sarvam"):
        assert capacity.snapshot()["provider_inflight"]["TTS"] == 1
    assert capacity.snapshot()["provider_inflight"]["TTS"] == 0


@pytest.mark.asyncio
async def test_stt_slot_acquired_and_released():
    capacity = Capacity(make_settings(max_stt_inflight=1))
    async with capacity.provider_slot("STT", "gnani"):
        assert capacity.snapshot()["provider_inflight"]["STT"] == 1
    assert capacity.snapshot()["provider_inflight"]["STT"] == 0


@pytest.mark.asyncio
async def test_capacity_timeout_raises_provider_capacity_error():
    capacity = Capacity(make_settings(max_llm_inflight=1))
    acquired = asyncio.Event()

    async def hold():
        async with capacity.provider_slot("LLM", "groq"):
            acquired.set()
            await asyncio.sleep(0.1)

    task = asyncio.create_task(hold())
    await acquired.wait()

    with pytest.raises(ProviderCapacityError) as exc_info:
        async with capacity.provider_slot("LLM", "groq"):
            pass

    assert exc_info.value.category == "local_capacity"
    assert exc_info.value.retryable is False
    await task


@pytest.mark.asyncio
async def test_cancellation_while_waiting_releases_resources():
    capacity = Capacity(make_settings(max_llm_inflight=1))
    acquired = asyncio.Event()

    async def hold():
        async with capacity.provider_slot("LLM", "groq"):
            acquired.set()
            await asyncio.sleep(0.08)

    holder = asyncio.create_task(hold())
    await acquired.wait()

    async def waiter():
        async with capacity.provider_slot("LLM", "groq"):
            pass

    wait_task = asyncio.create_task(waiter())
    await asyncio.sleep(0.01)
    wait_task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await wait_task

    await holder
    assert capacity.snapshot()["provider_inflight"]["LLM"] == 0

    # Ensure slot is fully functional after cancellation
    async with capacity.provider_slot("LLM", "groq"):
        assert capacity.snapshot()["provider_inflight"]["LLM"] == 1


@pytest.mark.asyncio
async def test_inflight_count_returns_to_zero():
    capacity = Capacity(make_settings(max_tts_inflight=2))

    async def op(fail=False):
        async with capacity.provider_slot("TTS", "gnani"):
            if fail:
                raise RuntimeError("failure during slot")

    await op(fail=False)
    with pytest.raises(RuntimeError):
        await op(fail=True)
    assert capacity.snapshot()["provider_inflight"]["TTS"] == 0


@pytest.mark.asyncio
async def test_rejection_counter_increments_correctly():
    capacity = Capacity(make_settings(max_stt_inflight=1))
    started = asyncio.Event()

    async def hold():
        async with capacity.provider_slot("STT", "gnani"):
            started.set()
            await asyncio.sleep(0.08)

    t = asyncio.create_task(hold())
    await started.wait()
    with pytest.raises(ProviderCapacityError):
        async with capacity.provider_slot("STT", "gnani"):
            pass
    await t
    assert capacity.snapshot()["provider_concurrency_rejected"]["STT"] == 1


# ==============================================================================
# API RATE LIMITING (18 - 23)
# ==============================================================================


def test_requests_below_limit_allowed():
    capacity = Capacity(make_settings())
    for _ in range(5):
        assert capacity.allow_api("scope-a", "key-1", 10) is True


def test_request_exceeding_limit_rejected():
    capacity = Capacity(make_settings())
    for _ in range(3):
        assert capacity.allow_api("scope-b", "key-1", 3) is True
    assert capacity.allow_api("scope-b", "key-1", 3) is False


def test_windows_expire_correctly(monkeypatch):
    capacity = Capacity(make_settings())
    current_time = 1000.0
    monkeypatch.setattr(time, "monotonic", lambda: current_time)

    assert capacity.allow_api("scope-c", "key-1", 1) is True
    assert capacity.allow_api("scope-c", "key-1", 1) is False

    current_time += 61.0
    assert capacity.allow_api("scope-c", "key-1", 1) is True


def test_separate_tenants_keys_do_not_interfere():
    capacity = Capacity(make_settings())
    assert capacity.allow_api("scope-d", "tenant-1", 1) is True
    assert capacity.allow_api("scope-d", "tenant-1", 1) is False
    assert capacity.allow_api("scope-d", "tenant-2", 1) is True


def test_limiter_key_storage_remains_bounded():
    capacity = Capacity(make_settings())
    capacity._api_max_keys = 50
    for i in range(100):
        capacity.allow_api("scope-e", f"key-{i}", 5)
    assert len(capacity._api_hits) <= 50


def test_expired_entries_are_pruned(monkeypatch):
    capacity = Capacity(make_settings())
    capacity._api_max_keys = 5
    current_time = 100.0
    monkeypatch.setattr(time, "monotonic", lambda: current_time)

    for i in range(5):
        assert capacity.allow_api("scope-f", f"key-{i}", 5) is True

    current_time += 65.0
    # Next call triggers cleanup of expired keys
    assert capacity.allow_api("scope-f", "new-key", 5) is True
    assert ("scope-f", "new-key") in capacity._api_hits
    assert ("scope-f", "key-0") not in capacity._api_hits


# ==============================================================================
# STATUS (24 - 29)
# ==============================================================================


@pytest.mark.asyncio
async def test_snapshot_reports_active_calls_correctly():
    capacity = Capacity(make_settings())
    await capacity.admit("call-x", "tenant-x")
    assert capacity.snapshot()["active_calls"] == 1
    await capacity.release("call-x")
    assert capacity.snapshot()["active_calls"] == 0


def test_snapshot_reports_limits():
    settings = make_settings(max_calls=15, tenant_max_calls=4)
    capacity = Capacity(settings)
    snap = capacity.snapshot()
    assert snap["global_call_limit"] == 15
    assert snap["tenant_call_limit"] == 4
    assert snap["provider_limits"]["LLM"] == settings.max_llm_inflight


@pytest.mark.asyncio
async def test_saturation_true_only_when_global_capacity_full():
    capacity = Capacity(make_settings(max_calls=2))
    assert capacity.snapshot()["saturated"] is False
    await capacity.admit("c1", "t1")
    assert capacity.snapshot()["saturated"] is False
    await capacity.admit("c2", "t2")
    assert capacity.snapshot()["saturated"] is True
    await capacity.release("c1")
    assert capacity.snapshot()["saturated"] is False


@pytest.mark.asyncio
async def test_rejected_call_counters_correct():
    capacity = Capacity(make_settings(max_calls=1, tenant_max_calls=1))
    await capacity.admit("c1", "t1")
    await capacity.admit("c2", "t1")  # tenant reject
    await capacity.admit("c3", "t2")  # global reject
    snap = capacity.snapshot()
    assert snap["rejected_calls_by_reason"]["tenant"] == 1
    assert snap["rejected_calls_by_reason"]["global"] == 1
    assert snap["rejected_calls_total"] == 2


@pytest.mark.asyncio
async def test_provider_inflight_counters_correct():
    capacity = Capacity(make_settings())
    assert capacity.snapshot()["provider_inflight"]["LLM"] == 0
    async with capacity.provider_slot("LLM", "groq"):
        assert capacity.snapshot()["provider_inflight"]["LLM"] == 1
    assert capacity.snapshot()["provider_inflight"]["LLM"] == 0


@pytest.mark.asyncio
async def test_provider_rate_limit_events_correct():
    capacity = Capacity(make_settings())
    policy = RetryPolicy(make_settings(), capacity=capacity)
    error = httpx.HTTPStatusError("429", request=httpx.Request("GET", "https://api.groq.com"), response=httpx.Response(429))
    with pytest.raises(ProviderRateLimitError):
        await policy._failure(error, "groq", "LLM", 3, False, None)
    assert capacity.provider_rate_limit_events == 1


# ==============================================================================
# TENANT ISOLATION (30 - 32)
# ==============================================================================


@pytest.mark.asyncio
async def test_status_admin_sees_full_capacity_data(tmp_path):
    settings = make_settings(database=tmp_path / "test.db", admin_token="admin-secret")
    app = create_app(settings)
    with TestClient(app) as client:
        res = client.get("/api/status", headers={"Authorization": "Bearer admin-secret"})
        assert res.status_code == 200
        data = res.json()
        assert "capacity" in data
        assert "global_call_limit" in data["capacity"]
        assert "provider_limits" in data["capacity"]
        assert data["capacity"]["scope"] == "single_process"


@pytest.mark.asyncio
async def test_status_tenant_sees_only_own_count_and_limit(tmp_path):
    settings = make_settings(database=tmp_path / "test.db", admin_token="admin-secret")
    app = create_app(settings)
    with TestClient(app) as client:
        tenant_res = client.post(
            "/api/tenants",
            headers={"Authorization": "Bearer admin-secret"},
            json={"name": "Tenant A", "greeting": "Hello"},
        )
        token = tenant_res.json()["api_token"]
        res = client.get("/api/status", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200
        data = res.json()
        assert data["capacity"]["scope"] == "tenant_single_process"
        assert data["capacity"]["tenant_call_limit"] == settings.tenant_max_calls
        assert "global_call_limit" not in data["capacity"]
        assert "provider_limits" not in data["capacity"]


@pytest.mark.asyncio
async def test_tenant_cannot_infer_other_tenant_usage(tmp_path):
    settings = make_settings(database=tmp_path / "test.db", admin_token="admin-secret")
    app = create_app(settings)
    with TestClient(app) as client:
        t1 = client.post("/api/tenants", headers={"Authorization": "Bearer admin-secret"}, json={"name": "T1", "greeting": "Hi"}).json()
        t2 = client.post("/api/tenants", headers={"Authorization": "Bearer admin-secret"}, json={"name": "T2", "greeting": "Hi"}).json()

        # Simulate active call under T1
        await app.state.services.capacity.admit("call-t1", t1["id"])

        t2_status = client.get("/api/status", headers={"Authorization": f"Bearer {t2['api_token']}"}).json()
        assert t2_status["active_calls"] == 0
        assert t2_status["capacity"]["active_calls"] == 0


# ==============================================================================
# RETRY-AFTER TESTS (33 - 40)
# ==============================================================================


def test_retry_after_integer_seconds():
    req = httpx.Request("GET", "https://api.vachana.ai")
    resp = httpx.Response(429, headers={"Retry-After": "3"})
    err = httpx.HTTPStatusError("Rate limited", request=req, response=resp)
    classified = classify_error(err, "gnani", "STT")
    assert isinstance(classified, ProviderRateLimitError)
    assert classified.retry_after_ms == 3000.0


def test_retry_after_decimal_seconds():
    req = httpx.Request("GET", "https://api.vachana.ai")
    resp = httpx.Response(429, headers={"Retry-After": "1.5"})
    err = httpx.HTTPStatusError("Rate limited", request=req, response=resp)
    classified = classify_error(err, "gnani", "STT")
    assert isinstance(classified, ProviderRateLimitError)
    assert classified.retry_after_ms == 1500.0


def test_retry_after_http_date():
    req = httpx.Request("GET", "https://api.vachana.ai")
    future_date = format_datetime(datetime.now(timezone.utc) + timedelta(seconds=5), usegmt=True)
    resp = httpx.Response(429, headers={"Retry-After": future_date})
    err = httpx.HTTPStatusError("Rate limited", request=req, response=resp)
    classified = classify_error(err, "gnani", "STT")
    assert isinstance(classified, ProviderRateLimitError)
    assert classified.retry_after_ms is not None
    assert 3000.0 <= classified.retry_after_ms <= 6000.0


def test_missing_retry_after_falls_back_to_exponential_backoff():
    req = httpx.Request("GET", "https://api.vachana.ai")
    resp = httpx.Response(429)
    err = httpx.HTTPStatusError("Rate limited", request=req, response=resp)
    classified = classify_error(err, "gnani", "STT")
    assert isinstance(classified, ProviderRateLimitError)
    assert classified.retry_after_ms is None


@pytest.mark.asyncio
async def test_excessive_retry_after_capped_at_max_ms():
    settings = make_settings(provider_backoff_max_ms=50)
    policy = RetryPolicy(settings, jitter=lambda: 0)
    delays = []

    async def mock_sleep(secs):
        delays.append(secs * 1000)

    policy.sleep = mock_sleep
    req = httpx.Request("GET", "https://api.vachana.ai")
    resp = httpx.Response(429, headers={"Retry-After": "9999"})
    err = httpx.HTTPStatusError("Rate limited", request=req, response=resp)

    with pytest.raises(ProviderRateLimitError):
        # 3 attempts
        for attempt in range(1, 4):
            await policy._failure(err, "gnani", "STT", attempt, False, None)

    assert all(d <= 50.0 for d in delays)


def test_malformed_retry_after_safely_falls_back():
    req = httpx.Request("GET", "https://api.vachana.ai")
    resp = httpx.Response(429, headers={"Retry-After": "invalid-value"})
    err = httpx.HTTPStatusError("Rate limited", request=req, response=resp)
    classified = classify_error(err, "gnani", "STT")
    assert isinstance(classified, ProviderRateLimitError)
    assert classified.retry_after_ms is None


@pytest.mark.asyncio
async def test_cancellation_interrupts_retry_after_sleep():
    settings = make_settings(provider_backoff_max_ms=5000)
    policy = RetryPolicy(settings)
    cancel_event = asyncio.Event()

    async def run_retry():
        req = httpx.Request("GET", "https://api.vachana.ai")
        resp = httpx.Response(429, headers={"Retry-After": "10"})
        err = httpx.HTTPStatusError("Rate limited", request=req, response=resp)
        await policy._failure(err, "gnani", "STT", 1, False, cancel_event)

    task = asyncio.create_task(run_retry())
    await asyncio.sleep(0.01)
    cancel_event.set()
    with pytest.raises(ProviderCancelledError):
        await task


@pytest.mark.asyncio
async def test_retry_after_does_not_increase_retry_count_beyond_max():
    settings = make_settings(provider_max_retries=2)
    policy = RetryPolicy(settings)
    attempts = 0

    async def flaky():
        nonlocal attempts
        attempts += 1
        req = httpx.Request("GET", "https://api.vachana.ai")
        resp = httpx.Response(429, headers={"Retry-After": "0.001"})
        raise httpx.HTTPStatusError("429", request=req, response=resp)

    with pytest.raises(ProviderRateLimitError):
        await policy.call(flaky, "gnani", "STT")

    assert attempts == 3  # initial + 2 retries


# ==============================================================================
# GNANI BACKPRESSURE TESTS (41 - 44)
# ==============================================================================


@pytest.mark.asyncio
async def test_gnani_stt_events_queue_bounded_and_drops_oldest_on_close():
    settings = make_settings()
    stt = GnaniSTT(settings)
    assert stt._events.maxsize == 8

    # Fill queue to maximum capacity
    for i in range(8):
        stt._events.put_nowait(SimpleNamespace(text=f"item-{i}"))
    assert stt._events.full()

    # close() must drop one to place the terminal None without hanging
    await asyncio.wait_for(stt.close(), timeout=1.0)
    assert stt._events.get_nowait().text == "item-1"  # item-0 was dropped


@pytest.mark.asyncio
async def test_gnani_stt_pending_tasks_bounded_to_two():
    settings = make_settings()
    stt = GnaniSTT(settings)
    stt.vad = SimpleNamespace(process=lambda pcm: [0.9] * 5)
    stt.endpoint_silence_s = 0.01

    # Mock transcribe that holds indefinitely
    async def hold(*_):
        await asyncio.sleep(10)

    stt._transcribe_and_emit = hold

    # Utterance 1
    await stt.send(b"\x00\x01" * 800)
    stt.vad.process = lambda pcm: [0.0] * 5
    await asyncio.sleep(0.02)
    await stt.send(b"\x00" * 320)
    assert len(stt._pending_tasks) == 1

    # Utterance 2
    stt.vad.process = lambda pcm: [0.9] * 5
    await stt.send(b"\x00\x01" * 800)
    stt.vad.process = lambda pcm: [0.0] * 5
    await asyncio.sleep(0.02)
    await stt.send(b"\x00" * 320)
    assert len(stt._pending_tasks) == 2

    # Utterance 3 must be rejected with ProviderCapacityError
    stt.vad.process = lambda pcm: [0.9] * 5
    await stt.send(b"\x00\x01" * 800)
    stt.vad.process = lambda pcm: [0.0] * 5
    await asyncio.sleep(0.02)
    with pytest.raises(ProviderCapacityError):
        await stt.send(b"\x00" * 320)

    await stt.close()


@pytest.mark.asyncio
async def test_gnani_stt_teardown_cancels_pending_tasks_cleanly():
    settings = make_settings()
    stt = GnaniSTT(settings)

    async def long_running(*_):
        await asyncio.sleep(10)

    stt._transcribe_and_emit = long_running
    task = asyncio.create_task(stt._transcribe_and_emit(b"\x00" * 1600))
    stt._pending_tasks.add(task)
    task.add_done_callback(stt._pending_tasks.discard)

    await asyncio.wait_for(stt.close(), timeout=1.0)
    assert len(stt._pending_tasks) == 0
    assert task.cancelled()


# ==============================================================================
# AUDIO QUEUE BACKPRESSURE TESTS (45 - 48)
# ==============================================================================


class MockWebSocket:
    def __init__(self, messages=None):
        self.closed_code = None
        self.messages = list(messages or [])

    async def close(self, code=1000, **_):
        self.closed_code = code

    async def send_json(self, *_):
        pass

    async def receive_json(self):
        if self.messages:
            return self.messages.pop(0)
        from starlette.websockets import WebSocketDisconnect

        raise WebSocketDisconnect(code=1000)


@pytest.mark.asyncio
async def test_audio_queue_overflow_byte_limit_terminates_call():
    ws = MockWebSocket(messages=[{"event": "media", "media": {"payload": "..."}}])
    settings = make_settings()
    services = SimpleNamespace(
        settings=settings,
        vad=SimpleNamespace(session=lambda: SimpleNamespace(process=lambda _: [])),
        capacity=Capacity(settings),
    )
    transport = MediaTransport(ws, "exotel", "stream-1")
    tenant = {"id": "t-1", "config": {"language": "en-IN", "backchannels": []}}
    session = CallSession("call-overflow", tenant, transport, services)

    # 32,000 bytes is the backlog ceiling. Exceeding it must raise CallEnded with code 1013
    huge_pcm = b"\x01\x00" * 16001  # 32,002 bytes (even number for 16-bit samples)
    transport.decode = lambda _: huge_pcm

    with pytest.raises(CallEnded):
        await session.receive()

    assert ws.closed_code == 1013
    assert session.metrics["end_reason"] == "audio_queue_overflow"


def test_audio_queue_overflow_releases_capacity_slot(tmp_path):
    from unittest.mock import patch

    dummy_model = tmp_path / "model.onnx"
    dummy_model.write_text("dummy")
    settings = make_settings(
        database=tmp_path / "test.db",
        admin_token="admin-token",
        public_base_url="https://voice.example.com",
        silero_model=dummy_model,
        max_calls=1,
    )
    app = create_app(settings)

    async def mock_run(self):
        try:
            await self.receive()
        except CallEnded:
            pass

    with patch.object(CallSession, "run", mock_run):
        with TestClient(app) as client:
            app.state.services.vad = SimpleNamespace(
                session=lambda: SimpleNamespace(process=lambda _: [])
            )
            t = client.post(
                "/api/tenants",
                headers={"Authorization": "Bearer admin-token"},
                json={"name": "T1", "greeting": "Hi"},
            ).json()
            line = client.post(
                f"/api/tenants/{t['id']}/lines",
                headers={"Authorization": "Bearer admin-token"},
                json={"provider": "exotel", "number": "+911234567890"},
            ).json()

            conn = client.get(
                f"/api/tenants/{t['id']}/lines/{line['id']}/connection",
                headers={"Authorization": "Bearer admin-token"},
            ).json()
            stream_path = conn["stream_url"].split("voice.example.com")[-1]

            # Connect WebSocket and simulate media queue overflow
            with client.websocket_connect(stream_path) as ws:
                ws.send_json({"event": "connected"})
                ws.send_json({"event": "start", "start": {"stream_sid": "stream-sid"}})
                for _ in range(50):
                    if app.state.services.capacity.snapshot()["active_calls"] == 1:
                        break
                    time.sleep(0.02)
                assert app.state.services.capacity.snapshot()["active_calls"] == 1

                # Send excessive media to trigger 32000-byte queue overflow
                # In base64, 48000 bytes payload decodes to 36000 bytes > 32000
                import base64

                payload = base64.b64encode(b"\x00" * 36000).decode()
                ws.send_json({"event": "media", "media": {"payload": payload}})

                for _ in range(50):
                    if app.state.services.capacity.snapshot()["active_calls"] == 0:
                        break
                    time.sleep(0.02)

            # Capacity slot must be released
            assert app.state.services.capacity.snapshot()["active_calls"] == 0
