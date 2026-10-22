"""Read-only, privacy-safe checks for a local or carrier-backed demo."""

import ipaddress
import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from .config import Settings
from .demo_fixture import DEFAULT_DATABASE, LEAD_REFERENCE, MARKER


def _check_url(value: str) -> bool:
    parts = urlsplit(value)
    host = parts.hostname or ""
    if host in {"localhost", "127.0.0.1", "::1"} or host.endswith((".local", ".localhost")):
        return False
    try:
        if not ipaddress.ip_address(host).is_global:
            return False
    except ValueError:
        pass
    return (parts.scheme == "https" and bool(host) and not parts.username
            and not parts.password and parts.path in ("", "/") and not parts.query
            and not parts.fragment)


def _placeholder(value: str) -> bool:
    value = value.strip().lower()
    return value in {"", "changeme", "change-me", "placeholder", "your-key", "test"} or (
        value.startswith("<") and value.endswith(">")
    )


def run_preflight(
    database: Path = DEFAULT_DATABASE,
    *,
    settings: Settings | None = None,
    server_url: str = "http://127.0.0.1:8000",
    carrier: str = "loopback",
    skip_server: bool = False,
) -> list[tuple[str, str]]:
    """Return PASS/WARN/FAIL findings without returning credentials or identifiers."""
    if carrier not in {"loopback", "exotel", "kookoo"}:
        raise ValueError("Unsupported carrier selection")
    settings = settings or Settings()
    checks = []

    def add(level, message):
        checks.append((level, message))

    database = Path(database)
    if database.is_file():
        add("PASS", "Demo database file exists.")
    else:
        add("FAIL", "Demo database missing. Run scripts/seed_demo.py.")

    if settings.silero_model.is_file():
        add("PASS", "Silero model file exists.")
    else:
        add("FAIL", "Silero model missing. Run `python -m omnivoice.cli models`.")

    if _placeholder(settings.admin_token.get_secret_value()):
        add("FAIL", "Administrator token is missing or a placeholder.")
    else:
        add("PASS", "Administrator token configured.")
    missing = settings.missing_voice_settings()
    for name in missing:
        add("WARN" if carrier == "loopback" else "FAIL", f"Voice setting unavailable: {name}.")
    if not missing:
        add("PASS", "Selected speech providers and Groq are configured.")
    selected_keys = {"Groq": settings.groq_api_key.get_secret_value()}
    if "gnani" in (settings.stt_provider, settings.tts_provider):
        selected_keys["Gnani"] = settings.gnani_api_key.get_secret_value()
    if "sarvam" in (settings.stt_provider, settings.tts_provider):
        selected_keys["Sarvam"] = settings.sarvam_api_key.get_secret_value()
    for provider, key in selected_keys.items():
        if key and _placeholder(key):
            add("FAIL", f"{provider} credential is an obvious placeholder.")
    if settings.stt_provider != "gnani" or settings.tts_provider != "gnani":
        add("WARN", "Gnani is not selected for both STT and TTS; verify the intended demo variant.")
    if not settings.groq_model.strip():
        add("FAIL", "Groq model name is empty.")

    if carrier == "loopback":
        add("PASS", "Synthetic local loopback selected; no public carrier URL needed.")
    elif _check_url(settings.public_base_url):
        add("PASS", "Public HTTPS origin is configured.")
    else:
        add("FAIL", "Set OMNI_PUBLIC_BASE_URL to an HTTPS origin without a path or credentials.")
    if carrier != "loopback":
        from .app import create_app

        routes = {route.path for route in create_app(settings).routes}
        required = ({"/ws/exotel/{line_id}/{token}"} if carrier == "exotel" else
                    {"/webhooks/kookoo/{line_id}/{token}", "/ws/kookoo/{line_id}/{token}"})
        if required <= routes:
            add("PASS", f"{carrier.title()} webhook/media routes are registered in this build.")
        else:
            add("FAIL", f"{carrier.title()} webhook/media routes are absent in this build.")

    if database.is_file():
        try:
            uri = f"file:{database.resolve().as_posix()}?mode=ro"
            with closing(sqlite3.connect(uri, uri=True, timeout=2)) as db:
                db.execute("PRAGMA query_only=ON")
                fixtures = []
                for tenant_id, raw in db.execute("SELECT id,config FROM tenants"):
                    try:
                        if json.loads(raw).get("demo_fixture") == MARKER:
                            fixtures.append(tenant_id)
                    except (TypeError, ValueError):
                        continue
                if len(fixtures) != 1:
                    add("FAIL", "Expected exactly one marked synthetic demo tenant.")
                else:
                    tenant_id = fixtures[0]
                    count = db.execute(
                        "SELECT count(*) FROM knowledge WHERE tenant_id=? AND approved=1",
                        (tenant_id,),
                    ).fetchone()[0]
                    add("PASS" if count >= 6 else "FAIL", f"Approved demo FAQs: {count}.")
                    count = db.execute(
                        "SELECT count(*) FROM leads WHERE tenant_id=? AND identifier=? AND source='synthetic_demo'",
                        (tenant_id, LEAD_REFERENCE),
                    ).fetchone()[0]
                    add("PASS" if count == 1 else "FAIL", "Synthetic demo lead present." if count == 1
                        else "Synthetic demo lead missing or duplicated.")
                    future = sum(
                        datetime.fromisoformat(start).astimezone(timezone.utc) > datetime.now(timezone.utc)
                        for (start,) in db.execute(
                            "SELECT start_at FROM demo_slots WHERE tenant_id=? AND status='available'",
                            (tenant_id,),
                        )
                    )
                    add("PASS" if future >= 3 else "FAIL", f"Future available demo slots: {future}.")
                    booked = db.execute(
                        "SELECT count(*) FROM demo_bookings WHERE tenant_id=?", (tenant_id,)
                    ).fetchone()[0]
                    add("PASS" if booked == 0 else "FAIL", "No stale demo booking." if booked == 0
                        else "Demo booking already exists. Run scripts/reset_demo.py before presenting.")
                    if carrier != "loopback":
                        lines = db.execute(
                            "SELECT count(*) FROM lines WHERE tenant_id=? AND provider=?",
                            (tenant_id, carrier),
                        ).fetchone()[0]
                        add("PASS" if lines else "FAIL", f"{carrier.title()} line registered."
                            if lines else f"No {carrier.title()} line registered for the demo tenant.")
                        if carrier == "kookoo" and not getattr(settings, "kookoo_sip_number", "").strip():
                            add("FAIL", "KooKoo SIP registration number is not configured.")
        except (sqlite3.Error, ValueError, TypeError):
            add("FAIL", "Demo database cannot be read or has invalid fixture data.")

    if skip_server:
        add("WARN", "Server checks skipped; /healthz and /readyz remain unverified.")
    else:
        if settings.database.resolve() != database.resolve():
            add("FAIL", "Running service database setting differs from the selected demo database.")
        with httpx.Client(timeout=3, trust_env=False) as client:
            for path in ("/healthz", "/readyz"):
                try:
                    response = client.get(server_url.rstrip("/") + path)
                    add("PASS" if response.status_code == 200 else "FAIL",
                        f"Server {path}: HTTP {response.status_code}.")
                except httpx.HTTPError:
                    add("FAIL", f"Server {path} unreachable; start the local service.")
        if carrier != "loopback" and _check_url(settings.public_base_url):
            with httpx.Client(timeout=10, trust_env=False) as client:
                for path in ("/healthz", "/readyz"):
                    try:
                        response = client.get(settings.public_base_url.rstrip("/") + path)
                        add("PASS" if response.status_code == 200 else "FAIL",
                            f"Public {path}: HTTP {response.status_code}.")
                    except httpx.HTTPError:
                        add("FAIL", f"Public {path} unreachable; check the tunnel or deployment.")
    return checks
