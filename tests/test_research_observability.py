"""Payload safety and opt-in Langfuse research export without a network account."""

import json
from contextlib import contextmanager
from unittest.mock import MagicMock, patch
from urllib.parse import urlsplit

import pytest
from fastapi.testclient import TestClient

from omnivoice.app import create_app
from omnivoice.config import Settings
from omnivoice.research_observability import QUEUE_LIMIT, ResearchObserver, live_projection
from omnivoice.session import CallSession
from scripts.evaluate_agent_tools import CASES, evaluate


class FakeSpan:
    def __init__(self, record, client):
        self.record = record
        self.client = client

    def update(self, **data):
        self.record.setdefault("updates", []).append(data)

    def score_trace(self, **data):
        self.record.setdefault("scores", []).append(data)

    def end(self):
        self.record["ended"] = True

    def start_observation(self, **data):
        return self.client.start_observation(**data)


class FakeLangfuse:
    def __init__(self):
        self.records = []
        self.shutdowns = 0

    @contextmanager
    def start_as_current_observation(self, **data):
        record = dict(data)
        self.records.append(record)
        yield FakeSpan(record, self)

    def start_observation(self, **data):
        record = dict(data)
        self.records.append(record)
        return FakeSpan(record, self)

    def shutdown(self):
        self.shutdowns += 1


def test_projection_drops_all_payloads_and_limits_turn_count():
    secret = "PRIVATE TRANSCRIPT +919876543210"
    turn = {
        "user_transcript": secret, "agent_response": secret,
        "tool_name": secret, "path": secret, "llm_ttft_ms": 123.5,
        "stt_endpoint_delay_ms": float("nan"), "interrupted": True,
    }
    metrics = {
        "turns": [turn] * 25, "errors": 1, "cache_hits": 0,
        "barge_in": [{"caller": secret}],
        "tool_summary": {"invocations": 2, "arguments": secret},
        "api_key": secret,
    }
    projection = live_projection(metrics, "exotel", "completed")
    assert projection["turns_recorded"] == 25
    assert projection["turns_exported"] == 20
    assert projection["turns_truncated"] is True
    assert projection["turns"][0] == {"llm_ttft_ms": 123.5, "interrupted": True}
    assert projection["tool_summary"] == {"invocations": 2}
    assert secret not in json.dumps(projection)


def test_research_export_requires_explicit_credentials_and_https():
    settings = Settings(_env_file=None, research_observability_enabled=True)
    with pytest.raises(ValueError, match="requires public and secret keys"):
        ResearchObserver.from_settings(settings)
    settings = Settings(
        _env_file=None, research_observability_enabled=True,
        langfuse_public_key="public", langfuse_secret_key="secret",
        langfuse_base_url="http://localhost:3000",
    )
    with pytest.raises(ValueError, match="HTTPS"):
        ResearchObserver.from_settings(settings)
    assert ResearchObserver.from_settings(Settings(_env_file=None)).client is None


@pytest.mark.asyncio
async def test_offline_evaluation_exports_only_synthetic_labels_and_measured_scores():
    client = FakeLangfuse()
    observer = ResearchObserver(client, enabled=True)
    result = await evaluate(observer)
    assert result["scenario_count"] == len(CASES)
    roots = [row for row in client.records if row["name"] == "omnivoice.scripted_sales_case"]
    tools = [row for row in client.records if row["name"] == "scripted_tool_invocation"]
    actions = [row for row in client.records if row["name"] == "scripted_action_confirmation"]
    assert len(roots) == len(CASES)
    assert len(tools) == result["metrics"]["tool_invocation_count"]
    assert actions
    assert all(any(score["name"] == "scripted_task_completed" for score in root["scores"])
               for root in roots)
    payload = json.dumps(client.records)
    for forbidden in ("+910000000001", "Verified business answer", "Send brochure", "api_token"):
        assert forbidden not in payload
    await observer.close()
    assert client.shutdowns == 1


@pytest.mark.asyncio
async def test_live_queue_is_bounded_and_export_is_payload_free():
    client = FakeLangfuse()
    observer = ResearchObserver(client, enabled=True)
    observer.worker = object()  # Keep the test queue undrained to exercise its bound.
    for _ in range(QUEUE_LIMIT + 1):
        observer.submit_live({"turns": [{"user_transcript": "SECRET", "llm_ttft_ms": 12}]},
                             "twilio", "completed")
    assert observer.queue.qsize() == QUEUE_LIMIT
    assert observer.dropped == 1
    observer.worker = None
    observer._emit_live(observer.queue.get_nowait())
    assert "SECRET" not in json.dumps(client.records)


def test_live_websocket_teardown_queues_metrics_and_keeps_tenant_status_private(tmp_path):
    client = FakeLangfuse()
    model = tmp_path / "silero.onnx"
    model.write_bytes(b"isolated-test-model")
    settings = Settings(
        _env_file=None, database=tmp_path / "research.db", admin_token="test-admin",
        public_base_url="https://voice.example.com", research_observability_enabled=True,
        sarvam_api_key="test-speech", groq_api_key="test-reasoning", silero_model=model,
    )
    app = create_app(settings, research_client=client)

    async def mock_run(self):
        self.metrics["turns"].append({
            "user_transcript": "PRIVATE CALLER +919876543210", "agent_response": "PRIVATE ANSWER",
            "llm_ttft_ms": 18, "path": "foreground_rag",
        })

    with patch.object(CallSession, "run", mock_run):
        with TestClient(app) as browser:
            app.state.services.vad = MagicMock()
            app.state.services.vad.session.return_value = MagicMock()
            admin = {"Authorization": "Bearer test-admin"}
            tenant = browser.post("/api/tenants", headers=admin,
                                  json={"name": "Research tenant", "greeting": "Hello"}).json()
            tenant_auth = {"Authorization": "Bearer " + tenant["api_token"]}
            assert "research_observability" in browser.get("/api/status", headers=admin).json()
            assert "research_observability" not in browser.get(
                "/api/status", headers=tenant_auth
            ).json()
            line = browser.post(f"/api/tenants/{tenant['id']}/lines", headers=admin,
                                json={"provider": "exotel", "number": "+12025550191"}).json()
            connection = browser.get(
                f"/api/tenants/{tenant['id']}/lines/{line['id']}/connection", headers=admin
            ).json()
            path = urlsplit(connection["stream_url"]).path
            with browser.websocket_connect(path) as ws:
                ws.send_json({"event": "start", "start": {"stream_sid": "test-stream"}})
                assert ws.receive()["type"] == "websocket.close"

    roots = [row for row in client.records if row["name"] == "omnivoice.completed_call_metrics"]
    assert len(roots) == 1
    assert roots[0]["metadata"]["turns_recorded"] == 1
    assert "PRIVATE" not in json.dumps(client.records)
    assert "+12025550191" not in json.dumps(client.records)
    assert client.shutdowns == 1
