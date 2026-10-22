import json
import sqlite3
import sys
import time

import pytest
from pydantic import SecretStr

from omnivoice import cli
from omnivoice.config import Settings
from omnivoice.demo_fixture import LEAD_REFERENCE, MARKER, prepare_demo
from omnivoice.demo_preflight import _check_url, run_preflight


def _count(db, table, tenant_id):
    return db.execute(f"SELECT count(*) FROM {table} WHERE tenant_id=?", (tenant_id,)).fetchone()[0]


def test_seed_reset_is_deterministic_and_tenant_scoped(tmp_path):
    path = tmp_path / "demo.db"
    assert prepare_demo(path, dry_run=True)["operation"] == "create"
    assert not path.exists()
    result = prepare_demo(path)
    tenant_id = result["tenant_id"]
    assert result["knowledge"] == 6 and result["slots"] == 3
    assert prepare_demo(path)["operation"] == "exists"
    with sqlite3.connect(path) as db:
        db.execute(
            "INSERT INTO tenants VALUES (?,?,?,?,0,?)",
            ("other", "Real tenant", "unrelated-hash", json.dumps({"name": "Real tenant"}), time.time()),
        )
        db.execute(
            "INSERT INTO knowledge VALUES (?,?,?,?,?,?,?)",
            ("keep", "other", "faq", "Keep", "Unrelated", 1, time.time()),
        )
        lead = db.execute("SELECT id FROM leads WHERE tenant_id=?", (tenant_id,)).fetchone()[0]
        slot = db.execute("SELECT id FROM demo_slots WHERE tenant_id=?", (tenant_id,)).fetchone()[0]
        db.execute(
            "INSERT INTO demo_bookings VALUES (?,?,?,?,?,?,?)",
            ("demo-booking", tenant_id, lead, slot, "synthetic-call", "booked", time.time()),
        )
        db.execute("UPDATE demo_slots SET status='booked' WHERE id=?", (slot,))
        db.commit()
    assert prepare_demo(path, reset=True, dry_run=True)["operation"] == "reset"
    with sqlite3.connect(path) as db:
        assert _count(db, "demo_bookings", tenant_id) == 1
    assert prepare_demo(path, reset=True)["tenant_id"] == tenant_id
    with sqlite3.connect(path) as db:
        assert _count(db, "demo_bookings", tenant_id) == 0
        assert _count(db, "knowledge", tenant_id) == 6
        assert _count(db, "leads", tenant_id) == 1
        assert _count(db, "demo_slots", tenant_id) == 3
        assert _count(db, "knowledge", "other") == 1
        assert db.execute("SELECT text FROM knowledge WHERE id='keep'").fetchone()[0] == "Unrelated"
        assert db.execute(
            "SELECT identifier FROM leads WHERE tenant_id=?", (tenant_id,)
        ).fetchone()[0] == LEAD_REFERENCE


def test_reset_refuses_unmarked_carrier_or_active_call(tmp_path):
    path = tmp_path / "demo.db"
    with pytest.raises(ValueError, match="seed first"):
        prepare_demo(path, reset=True)
    tenant_id = prepare_demo(path)["tenant_id"]
    with sqlite3.connect(path) as db:
        db.execute(
            "INSERT INTO lines VALUES (?,?,?,?,?)",
            ("line", tenant_id, "exotel", "+919999000001", "test-only-secret"),
        )
        db.commit()
    with pytest.raises(ValueError, match="carrier line"):
        prepare_demo(path, reset=True)
    with sqlite3.connect(path) as db:
        db.execute("DELETE FROM lines WHERE tenant_id=?", (tenant_id,))
        db.execute(
            "INSERT INTO calls (id,tenant_id,provider,status,started) VALUES (?,?,?,?,?)",
            ("active", tenant_id, "exotel", "active", time.time()),
        )
        db.commit()
    with pytest.raises(ValueError, match="active call"):
        prepare_demo(path, reset=True)
    with sqlite3.connect(path) as db:
        assert _count(db, "knowledge", tenant_id) == 6


def test_preflight_reports_fixture_and_never_prints_credentials(tmp_path):
    path = tmp_path / "demo.db"
    prepare_demo(path)
    model = tmp_path / "silero.onnx"
    model.write_bytes(b"test fixture only")
    settings = Settings(
        _env_file=None, database=path, silero_model=model, admin_token="private-test-token",
        stt_provider="gnani", tts_provider="gnani", gnani_api_key="private-gnani-key",
        groq_api_key="private-groq-key",
    )
    checks = run_preflight(path, settings=settings, skip_server=True)
    assert not any(level == "FAIL" for level, _ in checks)
    output = "\n".join(message for _, message in checks)
    assert "private-" not in output
    assert MARKER not in output
    with sqlite3.connect(path) as db:
        db.execute("UPDATE demo_slots SET status='booked'")
        db.commit()
    checks = run_preflight(path, settings=settings, skip_server=True)
    assert any(level == "FAIL" and "slots" in message for level, message in checks)
    checks = run_preflight(path, settings=settings, carrier="kookoo", skip_server=True)
    assert any(level == "FAIL" and "KooKoo" in message for level, message in checks)
    assert any(level == "FAIL" and "routes are absent" in message for level, message in checks)
    settings.groq_api_key = SecretStr("changeme")
    checks = run_preflight(path, settings=settings, skip_server=True)
    assert any(level == "FAIL" and "Groq credential" in message for level, message in checks)
    assert "changeme" not in "\n".join(message for _, message in checks)


def test_serve_uses_platform_port_without_overriding_explicit_port(monkeypatch):
    called = []
    monkeypatch.setattr("uvicorn.run", lambda *args, **kwargs: called.append(kwargs))
    monkeypatch.setenv("PORT", "9123")
    monkeypatch.setattr(sys, "argv", ["omnivoice", "serve"])
    cli.main()
    assert called[-1]["port"] == 9123
    monkeypatch.setattr(sys, "argv", ["omnivoice", "serve", "--port", "8765"])
    cli.main()
    assert called[-1]["port"] == 8765


def test_public_origin_check_rejects_local_and_embedded_credentials():
    assert _check_url("https://voice.example.com")
    assert not _check_url("https://127.0.0.1")
    assert not _check_url("https://voice.example.com/secret")
    assert not _check_url("https://user:password@voice.example.com")
