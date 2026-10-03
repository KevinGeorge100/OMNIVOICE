"""Bounded, tenant-scoped operations data and live event safety."""

import json
import sqlite3
import time
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from omnivoice.app import create_app
from omnivoice.config import Settings
from omnivoice.events import TenantEvents
from omnivoice.session import CallSession
from omnivoice.transport import MediaTransport

ADMIN = {"Authorization": "Bearer operations-admin-token"}


def test_call_history_filters_analytics_and_tenant_isolation(tmp_path):
    database = tmp_path / "operations.db"
    settings = Settings(
        _env_file=None,
        database=database,
        admin_token="operations-admin-token",
        semantic_enabled=False,
        silero_model=tmp_path / "missing.onnx",
    )
    with TestClient(create_app(settings)) as client:
        a = client.post("/api/tenants", headers=ADMIN, json={"name": "A", "greeting": "Hi"}).json()
        b = client.post("/api/tenants", headers=ADMIN, json={"name": "B", "greeting": "Hi"}).json()
        now = time.time()
        records = [
            (
                "a-exotel-1", a["id"], "exotel", "completed", now - 90, now - 30,
                json.dumps({"turns": [{"final_transcript_to_first_audio_sent_ms": 300,
                                       "interrupted": True}]}),
            ),
            ("a-twilio-2", a["id"], "twilio", "failed", now - 50, now - 20,
             json.dumps({"turns": []})),
            ("b-exotel-1", b["id"], "exotel", "completed", now - 40, now - 10,
             json.dumps({"turns": [{"final_transcript_to_first_audio_sent_ms": 900}]})),
        ]
        with sqlite3.connect(database) as connection:
            connection.executemany(
                "INSERT INTO calls (id,tenant_id,provider,status,started,ended,metrics) "
                "VALUES (?,?,?,?,?,?,?)", records,
            )
        tenant_auth = {"Authorization": "Bearer " + a["api_token"]}
        prefix = f"/api/tenants/{a['id']}"
        assert client.get(prefix + "/calls", headers=tenant_auth).status_code == 200
        assert [row["id"] for row in client.get(prefix + "/calls?limit=1", headers=tenant_auth).json()] == ["a-twilio-2"]
        assert [row["id"] for row in client.get(prefix + "/calls?limit=1&offset=1", headers=tenant_auth).json()] == ["a-exotel-1"]
        assert [row["id"] for row in client.get(prefix + "/calls?provider=exotel&status=completed&search=exotel", headers=tenant_auth).json()] == ["a-exotel-1"]
        assert client.get(prefix + "/calls?status=unknown", headers=tenant_auth).status_code == 422
        assert client.get(prefix + "/calls?status=interrupted", headers=tenant_auth).status_code == 200
        summary = client.get(prefix + "/analytics", headers=tenant_auth).json()
        assert summary["total_calls"] == 2
        assert summary["avg_duration_seconds"] == 45
        assert summary["avg_turns_per_call"] == 0.5
        assert summary["avg_server_first_audio_ms"] == 300
        assert summary["interruptions"] == 1
        assert {row["provider"] for row in summary["providers"]} == {"exotel", "twilio"}
        assert client.get(f"/api/tenants/{b['id']}/analytics", headers=tenant_auth).status_code == 404
        encoded = json.dumps(summary) + json.dumps(client.get(prefix + "/calls", headers=tenant_auth).json())
        assert "api_token" not in encoded
        assert "stream_secret" not in encoded
        assert "api_key" not in encoded
        assert client.get(prefix + "/events", headers={}).status_code == 401
        assert client.get(prefix + "/events", headers={"Authorization": "Bearer invalid-token"}).status_code == 401
        assert client.get(
            prefix + "/events", headers={"Authorization": "Bearer " + b["api_token"]}
        ).status_code == 404


def test_tenant_events_are_isolated_bounded_and_cleaned_up():
    hub = TenantEvents()
    a = hub.subscribe("a")
    b = hub.subscribe("b")
    for index in range(40):
        hub.publish("a", "call.turn", {"id": str(index)})
    assert a.qsize() == 32
    assert a.get_nowait()["call"]["id"] == "8"
    assert b.empty()
    hub.unsubscribe("a", a)
    hub.unsubscribe("b", b)
    assert not hub.listeners


async def test_call_turn_publish_failure_preserves_turn_and_generation_cleanup():
    """Verify B: call.turn publication failure does not alter completed turn state or generation cleanup."""
    class MockSocket:
        def __init__(self):
            self.sent = []

        async def send_json(self, item):
            self.sent.append(item)

        async def close(self, code=1000):
            pass

    class MockTTS:
        def __init__(self, *_):
            pass

        async def speak(self, text):
            yield b"\0" * 320

        async def cancel(self):
            pass

    class BrokenEvents:
        def __init__(self):
            self.call_count = 0

        def publish(self, *args, **kwargs):
            self.call_count += 1
            raise RuntimeError("event bus unreachable")

    broken_events = BrokenEvents()

    async def mock_llm(messages, tools):
        yield {"content": "Hello caller"}

    async def mock_confirm(*a, **k):
        return None

    async def mock_cancel(*a, **k):
        pass

    async def mock_tools(*a, **k):
        return []

    async def mock_fast_answer(*a, **k):
        return None, "miss", 0.0

    async def mock_retrieve(*a, **k):
        return []

    services = SimpleNamespace(
        events=broken_events,
        settings=Settings(_env_file=None),
        actions=SimpleNamespace(
            confirm=mock_confirm,
            cancel=mock_cancel,
            tools=mock_tools,
        ),
        knowledge=SimpleNamespace(
            fast_answer=mock_fast_answer,
            retrieve=mock_retrieve,
        ),
        llm=SimpleNamespace(stream=mock_llm),
        vad=SimpleNamespace(session=lambda: None),
    )
    tenant = {
        "id": "tenant-telemetry-test",
        "config": {
            "language": "en-IN",
            "greeting": "Hi",
            "instructions": "",
            "confirmation_phrases": [],
            "backchannels": [],
        },
    }
    session = CallSession("call-turn-err", tenant, MediaTransport(MockSocket(), "exotel", "s"), services)
    session.tts = MockTTS()

    await session.respond("User speaking", time.perf_counter(), 1)

    assert broken_events.call_count >= 1
    assert len(session.metrics["turns"]) == 1
    assert session.metrics["turns"][0]["user_transcript"] == "User speaking"
    assert session.metrics["turns"][0]["agent_response"] == "Hello caller"
    assert session.active_generation_id is None


def test_call_lifecycle_event_publish_failures_do_not_abort_session_or_cleanup(tmp_path):
    """Verify A and C: call.started failure does not prevent execution; call.ended failure does not prevent cleanup."""
    database = tmp_path / "telemetry_failures.db"
    dummy_model = tmp_path / "model.onnx"
    dummy_model.write_text("dummy")
    settings = Settings(
        _env_file=None,
        database=database,
        admin_token="operations-admin-token",
        sarvam_api_key="mock-key",
        groq_api_key="mock-key",
        silero_model=dummy_model,
        semantic_enabled=False,
    )
    app = create_app(settings)

    session_executed = []

    async def mock_run(self):
        session_executed.append(self.id)

    with patch.object(CallSession, "run", mock_run):
        with TestClient(app) as client:
            app.state.services.vad = MagicMock()
            app.state.services.vad.session.return_value = MagicMock()

            published_events = []

            def failing_publish(tenant_id, event_name, payload):
                published_events.append(event_name)
                raise RuntimeError(f"event {event_name} publication crashed")

            app.state.services.events.publish = failing_publish

            tenant = client.post("/api/tenants", headers=ADMIN, json={"name": "FailTest", "greeting": "Hi"}).json()
            line = client.post(
                f"/api/tenants/{tenant['id']}/lines",
                headers=ADMIN,
                json={"provider": "twilio", "number": "+12025550188"},
            ).json()

            with sqlite3.connect(database) as conn:
                token = conn.execute("SELECT stream_secret FROM lines WHERE id=?", (line["id"],)).fetchone()[0]

            with client.websocket_connect("/ws/twilio") as ws:
                ws.send_json({
                    "event": "start",
                    "start": {
                        "streamSid": "MZfailtest",
                        "mediaFormat": {"sampleRate": 8000, "channels": 1, "encoding": "audio/x-mulaw"},
                        "customParameters": {"line_id": line["id"], "token": token},
                    },
                })
                resp = ws.receive()
                assert resp["type"] == "websocket.close"

            # Requirement A: call.started failure did NOT prevent call/session execution
            assert len(session_executed) == 1
            call_id = session_executed[0]
            assert "call.started" in published_events

            # Requirement C: call.ended failure did NOT prevent final cleanup / WebSocket closure
            assert "call.ended" in published_events
            assert call_id not in app.state.services.active
            with sqlite3.connect(database) as conn:
                row = conn.execute("SELECT status, ended FROM calls WHERE id=?", (call_id,)).fetchone()
                assert row is not None
                assert row[0] == "completed"
                assert row[1] is not None

