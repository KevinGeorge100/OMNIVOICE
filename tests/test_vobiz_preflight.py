"""Read-only Vobiz demo preflight and privacy/tenant-boundary checks."""

import sqlite3
from pathlib import Path

import httpx
import pytest

from omnivoice.config import Settings
from omnivoice.demo_fixture import prepare_demo
from omnivoice.vobiz_preflight import run_vobiz_preflight
from omnivoice.vobiz_url import vobiz_answer_url


def _setup(tmp_path: Path, monkeypatch, *, wrong_wss: bool = False, wrong_tenant: bool = False):
    database = tmp_path / "demo.db"
    prepare_demo(database)
    line_id = "a" * 32
    secret = "private-routing-value-" + "b" * 32
    with sqlite3.connect(database) as db:
        tenant_id = db.execute("SELECT id FROM tenants").fetchone()[0]
        if wrong_tenant:
            db.execute(
                "INSERT INTO tenants VALUES (?,?,?,?,0,?)",
                ("c" * 32, "Other", "token-hash", "{}", 1.0),
            )
            tenant_id = "c" * 32
        db.execute(
            "INSERT INTO lines VALUES (?,?,?,?,?)",
            (line_id, tenant_id, "vobiz", "+919000000000", secret),
        )
    model = tmp_path / "vad.onnx"
    model.write_bytes(b"synthetic")
    settings = Settings(
        _env_file=None, database=database, public_base_url="https://voice.example.com",
        stt_provider="gnani", tts_provider="gnani", gnani_api_key="synthetic-credential",
        groq_api_key="synthetic-credential", silero_model=model,
    )
    answer_url = vobiz_answer_url(settings.public_base_url, line_id, secret)
    expected_wss = answer_url.replace("https://", "wss://", 1).replace(
        "/webhooks/vobiz/", "/ws/vobiz/", 1
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path in ("/healthz", "/readyz"):
            return httpx.Response(200)
        if request.url.path.startswith("/webhooks/vobiz/"):
            stream_url = "wss://wrong.example.com/ws" if wrong_wss else expected_wss
            xml = (
                '<Response><Stream bidirectional="true" keepCallAlive="true" '
                'audioTrack="inbound" contentType="audio/x-mulaw;rate=8000">'
                f"{stream_url}</Stream></Response>"
            )
            return httpx.Response(200, headers={"content-type": "application/xml"}, text=xml)
        return httpx.Response(404)

    client_type = httpx.Client
    monkeypatch.setattr("omnivoice.vobiz_preflight._public_dns", lambda host: True)
    monkeypatch.setattr("omnivoice.vobiz_preflight._wss_upgrade_ok", lambda url: True)
    monkeypatch.setattr(
        "omnivoice.vobiz_preflight.httpx.Client",
        lambda **kwargs: client_type(transport=httpx.MockTransport(handler), **kwargs),
    )
    return settings, database, line_id, secret


def test_vobiz_preflight_passes_synthetic_rehearsal_without_exposing_secret(tmp_path, monkeypatch):
    settings, database, line_id, secret = _setup(tmp_path, monkeypatch)
    checks = run_vobiz_preflight(settings, database, line_id=line_id, require_business_demo=True)
    assert not any(level == "FAIL" for level, _ in checks)
    assert all(text not in str(checks) for text in (secret, line_id, "+919000000000"))
    assert ("PASS", "Public Vobiz POST returns valid XML and matching WSS host.") in checks
    assert ("WARN", "No real PSTN call or carrier playback was tested by this preflight.") in checks


def test_vobiz_preflight_rejects_wrong_wss_host(tmp_path, monkeypatch):
    settings, database, _, _ = _setup(tmp_path, monkeypatch, wrong_wss=True)
    checks = run_vobiz_preflight(settings, database)
    assert ("FAIL", "Local Vobiz POST/XML/WSS check failed.") in checks
    assert ("FAIL", "Public Vobiz POST/XML/WSS check failed.") in checks


def test_vobiz_preflight_prefers_unique_marked_demo_line(tmp_path, monkeypatch):
    settings, database, _, _ = _setup(tmp_path, monkeypatch)
    with sqlite3.connect(database) as db:
        db.execute(
            "INSERT INTO tenants VALUES (?,?,?,?,0,?)",
            ("c" * 32, "Other", "token-hash", "{}", 1.0),
        )
        db.execute(
            "INSERT INTO lines VALUES (?,?,?,?,?)",
            ("d" * 32, "c" * 32, "vobiz", "+919000000003", "e" * 40),
        )
    checks = run_vobiz_preflight(settings, database, require_business_demo=True)
    assert not any(level == "FAIL" for level, _ in checks)


@pytest.mark.parametrize("required,expected", [(False, "WARN"), (True, "FAIL")])
def test_vobiz_preflight_requires_same_tenant_for_business_actions(
    tmp_path, monkeypatch, required, expected
):
    settings, database, _, _ = _setup(tmp_path, monkeypatch, wrong_tenant=True)
    checks = run_vobiz_preflight(settings, database, require_business_demo=required)
    assert (
        expected, "Vobiz line belongs to another tenant; only the basic media call is ready."
    ) in checks
