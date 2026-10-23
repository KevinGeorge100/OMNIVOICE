"""Vobiz carrier contract and SYNTHETIC / NON-PSTN loopback checks."""

import asyncio
import base64
import hashlib
import hmac
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock
from xml.etree import ElementTree

import httpx
import numpy as np
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from starlette.websockets import WebSocketDisconnect

from omnivoice.app import create_app
from omnivoice.audio import mulaw_encode
from omnivoice.config import Settings
from omnivoice.session import CallEnded, CallSession
from omnivoice.transport import MediaTransport
from omnivoice.vobiz_url import public_https_origin, vobiz_answer_url

ADMIN = {"Authorization": "Bearer synthetic-admin-token"}


@pytest.fixture
def client(tmp_path, monkeypatch):
    settings = Settings(
        _env_file=None,
        database=tmp_path / "vobiz.db",
        silero_model=tmp_path / "missing.onnx",
        admin_token="synthetic-admin-token",
        public_base_url="https://voice.example.test",
    )
    monkeypatch.setattr(Settings, "missing_voice_settings", lambda self: [])
    app = create_app(settings)
    with TestClient(app) as test_client:
        app.state.services.vad = SimpleNamespace(session=lambda: SimpleNamespace())
        yield test_client


def tenant_and_line(client, provider="vobiz", number="+919000000001"):
    tenant = client.post(
        "/api/tenants", headers=ADMIN, json={"name": "Synthetic Vobiz", "greeting": "Hello"}
    ).json()
    prefix = f"/api/tenants/{tenant['id']}"
    line = client.post(
        prefix + "/lines", headers=ADMIN, json={"provider": provider, "number": number}
    ).json()
    assert "id" in line
    return tenant, line, prefix


def connection(client, prefix, line):
    return client.get(prefix + f"/lines/{line['id']}/connection", headers=ADMIN).json()


def test_vobiz_registration_connection_is_tenant_scoped(client):
    _, line, prefix = tenant_and_line(client)
    result = connection(client, prefix, line)
    assert result["provider"] == "vobiz"
    assert result["webhook_url"].startswith(
        f"https://voice.example.test/webhooks/vobiz/{line['id']}/"
    )
    other = client.post(
        "/api/tenants", headers=ADMIN, json={"name": "Other", "greeting": "Hi"}
    ).json()
    assert client.get(
        f"/api/tenants/{other['id']}/lines/{line['id']}/connection",
        headers={"Authorization": "Bearer " + other["api_token"]},
    ).status_code == 404
    assert client.get(prefix + "/calls?provider=vobiz", headers=ADMIN).status_code == 200


def test_vobiz_answer_url_normalizes_origin_and_encodes_only_segments():
    assert public_https_origin("https://voice.example.test///") == "https://voice.example.test"
    assert vobiz_answer_url("https://voice.example.test/", "line+id", "secret/?#") == (
        "https://voice.example.test/webhooks/vobiz/line%2Bid/secret%2F%3F%23"
    )


@pytest.mark.parametrize("base", [
    "http://voice.example.test", "ws://voice.example.test", "wss://voice.example.test",
    "https://localhost", "https://127.0.0.1", "https://voice.example.test/path",
    "https://voice.example.test?x=1", "https://user@voice.example.test",
    "https://voice.example.test ", "https://voice.example.test\n",
    "https://voice.example.test:bad", "https://", "",
])
def test_vobiz_answer_url_rejects_invalid_public_origin(base):
    with pytest.raises(ValueError):
        vobiz_answer_url(base, "line", "secret")


@pytest.mark.parametrize("line_id,secret", [
    ("", "secret"), ("line", ""), ("line", "••••"), ("line", "***"),
    ("line", "<REDACTED>"), ("line\n", "secret"), ("line", "secret "),
])
def test_vobiz_answer_url_rejects_missing_masked_or_whitespace_segments(line_id, secret):
    with pytest.raises(ValueError):
        vobiz_answer_url("https://voice.example.test", line_id, secret)


def test_vobiz_webhook_auth_provider_xml_and_escaping(client):
    _, line, prefix = tenant_and_line(client)
    webhook = connection(client, prefix, line)["webhook_url"].removeprefix("https://voice.example.test")
    assert client.post(webhook + "wrong", data={"CallUUID": "synthetic"}).status_code == 403
    assert client.post("/webhooks/vobiz/" + "0" * 32 + "/guess", data={}).status_code == 403
    assert client.post(webhook, json={}).status_code == 415
    response = client.post(webhook, data={
        "CallUUID": "synthetic-call", "From": "+919000000002", "To": "+919000000001",
        "Direction": "inbound",
    })
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/xml")
    root = ElementTree.fromstring(response.text)
    stream = root.find("Stream")
    assert root.tag == "Response"
    assert stream.attrib == {
        "bidirectional": "true", "keepCallAlive": "true", "audioTrack": "inbound",
        "contentType": "audio/x-mulaw;rate=8000",
    }
    assert stream.text.startswith(f"wss://voice.example.test/ws/vobiz/{line['id']}/")
    assert "&" not in stream.text
    assert response.headers["cache-control"] == "no-store"
    _, wrong, wrong_prefix = tenant_and_line(client, "exotel", "+919000000003")
    exotel_secret = connection(client, wrong_prefix, wrong)["stream_url"].rsplit("/", 1)[-1]
    assert client.post(f"/webhooks/vobiz/{wrong['id']}/{exotel_secret}", data={}).status_code == 403


def test_vobiz_optional_v3_signature_verification(client):
    _, line, prefix = tenant_and_line(client)
    path = connection(client, prefix, line)["webhook_url"].removeprefix("https://voice.example.test")
    client.app.state.services.settings.vobiz_auth_token = SecretStr("synthetic-signing-key")
    nonce = "12345678901234567890"
    signature = base64.b64encode(hmac.new(
        b"synthetic-signing-key", ("https://voice.example.test" + path + "." + nonce).encode(),
        hashlib.sha256,
    ).digest()).decode()
    headers = {"X-Vobiz-Signature-V3": signature, "X-Vobiz-Signature-V3-Nonce": nonce}
    assert client.post(path, data={"CallUUID": "synthetic"}, headers=headers).status_code == 200
    assert client.post(path, data={"CallUUID": "synthetic"}, headers={**headers, "X-Vobiz-Signature-V3": "bad"}).status_code == 403


def test_vobiz_secret_is_not_logged_on_rejection(client, caplog):
    _, line, prefix = tenant_and_line(client)
    path = connection(client, prefix, line)["webhook_url"].removeprefix("https://voice.example.test")
    secret = path.rsplit("/", 1)[-1]
    assert client.post(path + "bad", data={"CallUUID": "synthetic"}).status_code == 403
    assert secret not in caplog.text


def test_vobiz_public_base_url_must_be_safe_https_origin(tmp_path, monkeypatch):
    monkeypatch.setattr(Settings, "missing_voice_settings", lambda self: [])
    for index, base in enumerate(("http://voice.example.test", "https://voice.example.test/path", "https://voice.example.test&bad")):
        settings = Settings(
            _env_file=None, database=tmp_path / f"invalid-{index}.db",
            silero_model=tmp_path / "missing.onnx", admin_token="synthetic-admin-token",
            public_base_url="https://voice.example.test",
        )
        with TestClient(create_app(settings)) as client:
            _, line, prefix = tenant_and_line(client)
            webhook = connection(client, prefix, line)["webhook_url"]
            path = "/webhooks/vobiz/" + "/".join(webhook.rsplit("/", 2)[-2:])
            settings.public_base_url = base
            assert client.get(prefix + f"/lines/{line['id']}/connection", headers=ADMIN).status_code == 409
            assert client.post(path, data={}).status_code == 409


def test_vobiz_websocket_rejects_bad_secret_before_accept(client):
    _, line, prefix = tenant_and_line(client)
    path = connection(client, prefix, line)["webhook_url"].replace(
        "https://voice.example.test/webhooks/", "/ws/"
    )
    with pytest.raises(WebSocketDisconnect) as caught:
        with client.websocket_connect(path + "bad"):
            pass
    assert caught.value.code == 1008


def test_vobiz_rejects_wrong_format_before_call_admission(client):
    _, line, prefix = tenant_and_line(client)
    secret = connection(client, prefix, line)["webhook_url"].rsplit("/", 1)[-1]
    with client.websocket_connect(f"/ws/vobiz/{line['id']}/{secret}") as ws:
        ws.send_json({
            "event": "start", "start": {
                "callId": "synthetic", "streamId": "stream", "tracks": ["inbound"],
                "mediaFormat": {"encoding": "audio/x-l16", "sampleRate": 8000},
            },
        })
        result = ws.receive()
        assert result["type"] == "websocket.close" and result["code"] == 1003
    assert client.app.state.services.capacity.snapshot()["active_calls"] == 0


@pytest.mark.asyncio
async def test_vobiz_codec_frames_and_clear_ack_gate():
    class Socket:
        def __init__(self):
            self.sent = []

        async def send_json(self, packet):
            self.sent.append(packet)

    socket = Socket()
    transport = MediaTransport(socket, "vobiz", "synthetic-stream")
    pcm = (np.arange(160, dtype="<i2") * 100).tobytes()
    encoded = mulaw_encode(pcm)
    decoded = transport.decode({"media": {"payload": base64.b64encode(encoded).decode()}})
    assert len(decoded) == 320
    assert np.max(np.abs(np.frombuffer(decoded, dtype="<i2").astype(int) - np.frombuffer(pcm, dtype="<i2").astype(int))) < 600
    assert transport.frame_size == 320
    assert await transport.send_frame(pcm, 0)
    packet = socket.sent[-1]
    assert packet["event"] == "playAudio" and packet["streamId"] == "synthetic-stream"
    assert packet["media"]["contentType"] == "audio/x-mulaw"
    assert packet["media"]["sampleRate"] == 8000
    assert base64.b64decode(packet["media"]["payload"]) == encoded
    assert await transport.mark("synthetic-checkpoint", 0)
    assert socket.sent[-1] == {
        "event": "checkpoint", "streamId": "synthetic-stream", "name": "synthetic-checkpoint"
    }
    await transport.clear()
    assert socket.sent[-1] == {"event": "clearAudio", "streamId": "synthetic-stream"}
    assert not transport.clear_ack.is_set()
    blocked = asyncio.create_task(transport.send_frame(pcm, 1))
    await asyncio.sleep(0.02)
    assert not blocked.done()
    transport.acknowledge_clear({"event": "clearedAudio", "streamId": "other-stream"})
    assert not blocked.done()
    transport.acknowledge_clear({"event": "clearedAudio", "streamId": "synthetic-stream"})
    assert await blocked
    assert socket.sent[-1]["event"] == "playAudio"
    assert not await transport.send_frame(pcm, 0)


@pytest.mark.asyncio
async def test_vobiz_invalid_media_is_rejected():
    transport = MediaTransport(SimpleNamespace(), "vobiz", "stream")
    for payload in ("!", base64.b64encode(b"x" * 16001).decode(), None):
        with pytest.raises((ValueError, TypeError)):
            transport.decode({"media": {"payload": payload}})


def test_vobiz_synthetic_non_pstn_websocket_rehearsal(client, monkeypatch):
    """SYNTHETIC / NON-PSTN: real FastAPI routes, mocked AI session only."""
    _, line, prefix = tenant_and_line(client)
    secret = connection(client, prefix, line)["webhook_url"].rsplit("/", 1)[-1]
    webhook = f"/webhooks/vobiz/{line['id']}/{secret}"
    assert ElementTree.fromstring(client.post(webhook, data={"CallUUID": "synthetic"}).text).tag == "Response"
    completed = []

    async def synthetic_run(self):
        media = await self.transport.ws.receive_json()
        pcm = self.transport.decode(media)
        assert len(pcm) == 320
        assert await self.transport.send_frame(pcm, 0)
        assert await self.transport.mark("synthetic-greeting", 0)
        assert await self.transport.ws.receive_json() == {
            "event": "playedStream", "name": "synthetic-greeting"
        }
        await self.transport.clear()
        ack = await self.transport.ws.receive_json()
        self.transport.acknowledge_clear(ack)
        assert self.transport.clear_ack.is_set()
        assert await self.transport.ws.receive_json() == {"event": "stop"}
        completed.append(self.id)

    monkeypatch.setattr(CallSession, "run", synthetic_run)
    with client.websocket_connect(f"/ws/vobiz/{line['id']}/{secret}") as ws:
        ws.send_json({
            "event": "start", "start": {
                "callId": "synthetic-call", "streamId": "synthetic-stream",
                "tracks": ["inbound"],
                "mediaFormat": {"encoding": "audio/x-mulaw", "sampleRate": 8000},
            },
        })
        ws.send_json({
            "event": "media", "streamId": "synthetic-stream",
            "media": {"track": "inbound", "payload": base64.b64encode(b"\xff" * 160).decode()},
        })
        assert ws.receive_json()["event"] == "playAudio"
        assert ws.receive_json() == {
            "event": "checkpoint", "streamId": "synthetic-stream", "name": "synthetic-greeting"
        }
        ws.send_json({"event": "playedStream", "name": "synthetic-greeting"})
        assert ws.receive_json()["event"] == "clearAudio"
        ws.send_json({"event": "clearedAudio", "streamId": "synthetic-stream"})
        ws.send_json({"event": "stop"})
        ws.receive()
    assert len(completed) == 1
    assert client.app.state.services.capacity.snapshot()["active_calls"] == 0
    calls = client.get(prefix + "/calls?provider=vobiz", headers=ADMIN).json()
    assert len(calls) == 1
    assert calls[0]["provider"] == "vobiz"
    assert "synthetic-call" not in json.dumps(calls)


def test_vobiz_provider_failure_releases_capacity_and_marks_failed(client, monkeypatch):
    _, line, prefix = tenant_and_line(client)
    secret = connection(client, prefix, line)["webhook_url"].rsplit("/", 1)[-1]

    async def failing_run(self):
        raise RuntimeError("synthetic provider failure")

    monkeypatch.setattr(CallSession, "run", failing_run)
    with client.websocket_connect(f"/ws/vobiz/{line['id']}/{secret}") as ws:
        ws.send_json({
            "event": "start", "start": {
                "callId": "synthetic", "streamId": "stream", "tracks": ["inbound"],
                "mediaFormat": {"encoding": "audio/x-mulaw", "sampleRate": 8000},
            },
        })
        assert ws.receive()["type"] == "websocket.close"
    assert client.app.state.services.capacity.snapshot()["active_calls"] == 0
    calls = client.get(prefix + "/calls?provider=vobiz", headers=ADMIN).json()
    assert len(calls) == 1 and calls[0]["status"] == "failed"
    assert "synthetic provider failure" not in json.dumps(calls)


@pytest.mark.asyncio
async def test_vobiz_only_named_playback_ack_can_arm_once():
    class Socket:
        def __init__(self, incoming):
            self.incoming = iter(incoming)

        async def receive_json(self):
            return next(self.incoming)

    armed = []

    async def arm(action, call):
        armed.append((action, call))

    socket = Socket([
        {"event": "clearedAudio", "streamId": "stream"},
        {"event": "playedStream", "name": "wrong"},
        {"event": "playedStream", "name": "confirmed"},
        {"event": "playedStream", "name": "confirmed"},
        {"event": "stop"},
    ])
    session = SimpleNamespace(
        id="call", transport=MediaTransport(socket, "vobiz", "stream"),
        marks={"confirmed": "write-action"},
        fsm=SimpleNamespace(played=lambda: None),
        services=SimpleNamespace(actions=SimpleNamespace(arm=arm)),
        metrics={},
    )
    with pytest.raises(CallEnded):
        await CallSession.receive(session)
    assert armed == [("write-action", "call")]
    assert session.marks == {}


@pytest.mark.asyncio
async def test_vobiz_disconnect_and_bad_media_end_without_arming():
    async def never_arm(*_):
        raise AssertionError("Unexpected action arming")

    for incoming in (
        [WebSocketDisconnect(code=1006)],
        [{"event": "media", "streamId": "other", "media": {"track": "inbound", "payload": "AAAA"}}],
    ):
        class Socket:
            def __init__(self, events):
                self.events = iter(events)

            async def receive_json(self):
                item = next(self.events)
                if isinstance(item, Exception):
                    raise item
                return item

        session = SimpleNamespace(
            id="call", transport=MediaTransport(Socket(incoming), "vobiz", "stream"),
            marks={"confirmation": "write"},
            services=SimpleNamespace(actions=SimpleNamespace(arm=never_arm)),
            metrics={},
        )
        if isinstance(incoming[0], WebSocketDisconnect):
            with pytest.raises(CallEnded):
                await CallSession.receive(session)
            assert session.metrics["end_reason"] == "carrier_disconnect"
        else:
            with pytest.raises(ValueError, match="Invalid carrier media frame"):
                await CallSession.receive(session)


def test_vobiz_outbound_requires_consent_and_uses_official_rest_shape(client, monkeypatch):
    _, line, prefix = tenant_and_line(client)
    settings = client.app.state.services.settings
    settings.enable_outbound = True
    settings.vobiz_auth_id = SecretStr("MA_SYNTHETIC")
    settings.vobiz_auth_token = SecretStr("synthetic-token")
    post = AsyncMock(return_value=httpx.Response(200, json={"request_uuid": "synthetic"}, request=httpx.Request("POST", "https://api.vobiz.ai")))
    monkeypatch.setattr(client.app.state.services.http, "post", post)
    path = prefix + "/dial"
    assert client.post(path, headers=ADMIN, json={
        "line_id": line["id"], "to": "+919000000002", "consent_confirmed": False,
    }).status_code == 409
    assert post.await_count == 0
    response = client.post(path, headers=ADMIN, json={
        "line_id": line["id"], "to": "+919000000002", "consent_confirmed": True,
    })
    assert response.status_code == 200
    assert response.json() == {"submitted": True}
    args, kwargs = post.await_args
    assert args[0] == "https://api.vobiz.ai/api/v1/Account/MA_SYNTHETIC/Call/"
    assert kwargs["json"]["to"] == "+919000000002"
    assert kwargs["json"]["answer_method"] == "POST"
    assert kwargs["headers"]["X-Auth-Token"] == "synthetic-token"
