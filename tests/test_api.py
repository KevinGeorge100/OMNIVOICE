import base64
import hashlib
import hmac

import pytest
from fastapi.testclient import TestClient

from omnivoice.app import create_app
from omnivoice.config import Settings


@pytest.fixture
def client(tmp_path):
    settings = Settings(
        _env_file=None,
        database=tmp_path / "api.db",
        silero_model=tmp_path / "missing.onnx",
        admin_token="test-administrator-token",
        public_base_url="https://voice.example.com",
        twilio_auth_token="test-twilio-secret",
    )
    with TestClient(create_app(settings)) as client:
        yield client


ADMIN = {"Authorization": "Bearer test-administrator-token"}


def create(client, name):
    result = client.post("/api/tenants", headers=ADMIN, json={"name": name, "greeting": "Test greeting"})
    assert result.status_code == 201
    return result.json()


def test_console_and_readiness_are_honest_without_credentials(client):
    assert client.get("/").status_code == 200
    assert client.get("/healthz").status_code == 200
    assert client.get("/readyz").status_code == 503
    assert client.get("/api/tenants").status_code == 401
    assert "SILERO_MODEL" in client.get("/api/status", headers=ADMIN).json()["missing"]


def test_tenant_keys_cannot_access_other_tenants_or_create_tenants(client):
    a, b = create(client, "A"), create(client, "B")
    headers = {"Authorization": "Bearer " + a["api_token"]}
    assert len(client.get("/api/tenants", headers=headers).json()) == 1
    assert client.get(f"/api/tenants/{b['id']}/knowledge", headers=headers).status_code == 404
    assert (
        client.post("/api/tenants", headers=headers, json={"name": "C", "greeting": "Hi"}).status_code == 403
    )


def test_document_ingestion_and_deletion(client):
    tenant = create(client, "Ingestion test")
    prefix = f"/api/tenants/{tenant['id']}"
    response = client.post(
        prefix + "/documents",
        headers=ADMIN,
        files={"file": ("manual.txt", b"Test-only office hours are 9 to 5", "text/plain")},
    )
    assert response.status_code == 201
    items = client.get(prefix + "/knowledge", headers=ADMIN).json()
    assert items[0]["title"] == "manual.txt"
    assert client.delete(prefix + "/knowledge/" + items[0]["id"], headers=ADMIN).status_code == 200
    assert client.get(prefix + "/knowledge", headers=ADMIN).json() == []


def test_invalid_document_does_not_create_knowledge(client):
    tenant = create(client, "Invalid ingestion")
    prefix = f"/api/tenants/{tenant['id']}"
    assert (
        client.post(
            prefix + "/documents",
            headers=ADMIN,
            files={"file": ("bad.exe", b"no", "application/octet-stream")},
        ).status_code
        == 422
    )
    assert client.get(prefix + "/knowledge", headers=ADMIN).json() == []


def test_outbound_is_disabled_and_does_not_call_provider(client):
    tenant = create(client, "Outbound test")
    assert (
        client.post(
            f"/api/tenants/{tenant['id']}/dial",
            headers=ADMIN,
            json={"line_id": "x", "to": "+919876543210", "consent_confirmed": True},
        ).status_code
        == 409
    )


def test_twilio_signature_and_escaped_stream_parameters(client):
    tenant = create(client, "Twilio test")
    line = client.post(
        f"/api/tenants/{tenant['id']}/lines",
        headers=ADMIN,
        json={"provider": "twilio", "number": "+12025550101"},
    ).json()
    path = "/telephony/twilio/" + line["id"]
    assert client.post(path, data={"CallSid": "CA123"}).status_code == 403
    signed = "https://voice.example.com" + path + "CallSidCA123"
    signature = base64.b64encode(
        hmac.new(b"test-twilio-secret", signed.encode(), hashlib.sha1).digest()
    ).decode()
    response = client.post(path, data={"CallSid": "CA123"}, headers={"X-Twilio-Signature": signature})
    assert response.status_code == 200
    assert "<Connect><Stream" in response.text


def test_websocket_rejects_missing_authentication(client):
    with client.websocket_connect("/ws/twilio") as ws:
        ws.send_json(
            {
                "event": "start",
                "start": {
                    "streamSid": "MZtest",
                    "mediaFormat": {"sampleRate": 8000, "channels": 1, "encoding": "audio/x-mulaw"},
                },
            }
        )
        result = ws.receive()
        assert result["type"] == "websocket.close"
        assert result["code"] == 1008


def test_carrier_connection_endpoints_twilio_and_exotel(client):
    tenant = create(client, "Carrier connection test")
    prefix = f"/api/tenants/{tenant['id']}"

    # Twilio line returns correct HTTP webhook URL
    t_line = client.post(
        prefix + "/lines",
        headers=ADMIN,
        json={"provider": "twilio", "number": "+12025550101"},
    ).json()
    t_conn = client.get(prefix + f"/lines/{t_line['id']}/connection", headers=ADMIN).json()
    assert t_conn["provider"] == "twilio"
    assert t_conn["webhook_url"] == f"https://voice.example.com/telephony/twilio/{t_line['id']}"
    assert "/api/webhooks/" not in t_conn["webhook_url"]

    # Exotel line returns correct WebSocket stream URL with stream secret
    e_line = client.post(
        prefix + "/lines",
        headers=ADMIN,
        json={"provider": "exotel", "number": "+918012345678"},
    ).json()
    e_conn = client.get(prefix + f"/lines/{e_line['id']}/connection", headers=ADMIN).json()
    assert e_conn["provider"] == "exotel"
    assert e_conn["stream_url"].startswith(f"wss://voice.example.com/ws/exotel/{e_line['id']}/")
    assert "/api/webhooks/" not in e_conn["stream_url"]


def test_carrier_connection_tenant_isolation_and_missing_url(tmp_path):
    # Test unconfigured public_base_url returns 409
    settings_no_base = Settings(
        _env_file=None,
        database=tmp_path / "no_base.db",
        admin_token="test-token",
        public_base_url="",
    )
    with TestClient(create_app(settings_no_base)) as unconfigured_client:
        auth = {"Authorization": "Bearer test-token"}
        t = unconfigured_client.post(
            "/api/tenants", headers=auth, json={"name": "No Base", "greeting": "Hi"}
        ).json()
        line = unconfigured_client.post(
            f"/api/tenants/{t['id']}/lines",
            headers=auth,
            json={"provider": "twilio", "number": "+12025550199"},
        ).json()
        resp = unconfigured_client.get(
            f"/api/tenants/{t['id']}/lines/{line['id']}/connection", headers=auth
        )
        assert resp.status_code == 409
        assert "OMNI_PUBLIC_BASE_URL" in resp.json()["detail"]

    # Test tenant isolation: Tenant B cannot access Tenant A's connection details
    settings_configured = Settings(
        _env_file=None,
        database=tmp_path / "isolation.db",
        admin_token="test-token",
        public_base_url="https://voice.example.com",
    )
    with TestClient(create_app(settings_configured)) as isolation_client:
        auth = {"Authorization": "Bearer test-token"}
        t_a = isolation_client.post(
            "/api/tenants", headers=auth, json={"name": "Tenant A", "greeting": "Hi"}
        ).json()
        t_b = isolation_client.post(
            "/api/tenants", headers=auth, json={"name": "Tenant B", "greeting": "Hi"}
        ).json()
        line_a = isolation_client.post(
            f"/api/tenants/{t_a['id']}/lines",
            headers={"Authorization": f"Bearer {t_a['api_token']}"},
            json={"provider": "twilio", "number": "+12025550111"},
        ).json()

        # Tenant B accessing Tenant A's line connection returns 404
        b_headers = {"Authorization": f"Bearer {t_b['api_token']}"}
        resp = isolation_client.get(
            f"/api/tenants/{t_b['id']}/lines/{line_a['id']}/connection", headers=b_headers
        )
        assert resp.status_code == 404

