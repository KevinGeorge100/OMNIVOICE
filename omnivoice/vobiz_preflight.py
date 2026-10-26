"""Read-only Vobiz demo preflight; never return routing secrets or caller data."""

import asyncio
import ipaddress
import json
import re
import socket
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
from xml.etree import ElementTree

import httpx
import websockets

from .config import Settings
from .demo_fixture import LEAD_REFERENCE, MARKER
from .vobiz_url import public_https_origin, vobiz_answer_url


def _public_dns(host: str) -> bool:
    try:
        addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        return bool(addresses) and all(
            ipaddress.ip_address(address[4][0]).is_global for address in addresses
        )
    except (OSError, ValueError):
        return False


def _probe(client: httpx.Client, method: str, url: str) -> httpx.Response | None:
    try:
        return client.request(
            method, url,
            data={"CallUUID": "omnivoice-synthetic-preflight"} if method == "POST" else None,
        )
    except httpx.HTTPError:
        return None


def _status_ok(response: httpx.Response | None) -> bool:
    return response is not None and response.status_code == 200


def _wss_upgrade_ok(url: str) -> bool:
    async def probe() -> bool:
        # Close before sending start: this tests public WSS routing without
        # allocating a call session or requesting provider inference.
        async with websockets.connect(url, open_timeout=5, close_timeout=2):
            return True

    try:
        return asyncio.run(probe())
    except Exception:
        return False


def _answer_xml_ok(response: httpx.Response | None, expected_wss: str) -> bool:
    if not _status_ok(response) or not response.headers.get("content-type", "").startswith(
        "application/xml"
    ):
        return False
    try:
        root = ElementTree.fromstring(response.content)
        stream = root.find("Stream")
    except ElementTree.ParseError:
        return False
    return bool(
        root.tag == "Response" and len(root) == 1 and stream is not None
        and stream.attrib.get("bidirectional") == "true"
        and stream.attrib.get("keepCallAlive") == "true"
        and stream.attrib.get("audioTrack") == "inbound"
        and stream.attrib.get("contentType") == "audio/x-mulaw;rate=8000"
        and (stream.text or "").strip() == expected_wss
    )


def _demo_checks(db: sqlite3.Connection, line_tenant: str, *, required: bool) -> list[tuple[str, str]]:
    level = "FAIL" if required else "WARN"
    matches = []
    for tenant_id, raw in db.execute("SELECT id,config FROM tenants"):
        try:
            if json.loads(raw).get("demo_fixture") == MARKER:
                matches.append(tenant_id)
        except (TypeError, ValueError):
            continue
    if len(matches) != 1:
        return [(level, "Expected one marked synthetic sales-demo tenant; seed the demo fixture.")]
    tenant_id = matches[0]
    checks = [("PASS", "Marked synthetic sales-demo tenant exists.")]
    knowledge = db.execute(
        "SELECT count(*) FROM knowledge WHERE tenant_id=? AND approved=1", (tenant_id,)
    ).fetchone()[0]
    checks.append(("PASS" if knowledge >= 6 else level, "Approved demo FAQs: sufficient." if knowledge >= 6
                   else "Approved demo FAQs are missing."))
    leads = db.execute(
        "SELECT count(*) FROM leads WHERE tenant_id=? AND identifier=? AND source='synthetic_demo'",
        (tenant_id, LEAD_REFERENCE),
    ).fetchone()[0]
    checks.append(("PASS" if leads == 1 else level, "Synthetic demo lead is unique." if leads == 1
                   else "Synthetic demo lead is missing or duplicated."))
    future = 0
    for (start,) in db.execute(
        "SELECT start_at FROM demo_slots WHERE tenant_id=? AND status='available'", (tenant_id,)
    ):
        try:
            future += datetime.fromisoformat(start).astimezone(timezone.utc) > datetime.now(timezone.utc)
        except (TypeError, ValueError):
            continue
    checks.append(("PASS" if future >= 3 else level, "Future demo slots: sufficient." if future >= 3
                   else "Future available demo slots are insufficient; reset the marked fixture."))
    booked = db.execute(
        "SELECT count(*) FROM demo_bookings WHERE tenant_id=?", (tenant_id,)
    ).fetchone()[0]
    checks.append(("PASS" if booked == 0 else level, "No stale demo booking." if booked == 0
                   else "A prior demo booking exists; review before an action rehearsal."))
    checks.append(("PASS" if line_tenant == tenant_id else level,
                   "Vobiz line belongs to the synthetic demo tenant." if line_tenant == tenant_id
                   else "Vobiz line belongs to another tenant; only the basic media call is ready."))
    return checks


def run_vobiz_preflight(
    settings: Settings,
    database: Path,
    *,
    local_base: str = "http://127.0.0.1:8000",
    line_id: str | None = None,
    require_business_demo: bool = False,
) -> list[tuple[str, str]]:
    """Probe current service and synthetic callback only; never dial or mutate data."""
    checks: list[tuple[str, str]] = []

    def add(level: str, label: str) -> None:
        checks.append((level, label))

    try:
        local = urlsplit(local_base)
        if (
            local.scheme != "http" or local.hostname not in {"localhost", "127.0.0.1", "::1"}
            or local.username or local.password or local.path or local.query or local.fragment
        ):
            raise ValueError("Invalid local origin")
        public = public_https_origin(settings.public_base_url)
        public_parts = urlsplit(public)
    except ValueError:
        return [("FAIL", "Local loopback or public HTTPS origin is invalid.")]

    add("PASS" if settings.stt_provider == settings.tts_provider == "gnani" else "FAIL",
        "Gnani STT and TTS selected." if settings.stt_provider == settings.tts_provider == "gnani"
        else "Select Gnani for both STT and TTS for this demo.")
    missing = settings.missing_voice_settings()
    add("PASS" if "GNANI_API_KEY" not in missing else "FAIL", "Gnani credential configured."
        if "GNANI_API_KEY" not in missing else "Gnani credential missing.")
    add("PASS" if "GROQ_API_KEY" not in missing and settings.groq_model.strip() else "FAIL",
        "Groq credential and model configured." if "GROQ_API_KEY" not in missing
        and settings.groq_model.strip() else "Groq credential or model missing.")
    tts_missing = any(item in missing for item in (
        "GNANI_TTS_VOICE", "GNANI_TTS_MODEL", "GNANI_TTS_SAMPLE_RATE", "SILERO_MODEL"
    ))
    add("PASS" if not tts_missing else "FAIL", "TTS and VAD settings configured." if not tts_missing
        else "TTS or VAD setting is missing.")

    selected = None
    if not database.is_file():
        add("FAIL", "Configured database is unavailable.")
    else:
        try:
            with closing(sqlite3.connect(f"file:{database.resolve().as_posix()}?mode=ro", uri=True)) as db:
                db.execute("PRAGMA query_only=ON")
                rows = db.execute(
                    "SELECT id,stream_secret,tenant_id FROM lines WHERE provider='vobiz'"
                    + (" AND id=?" if line_id else ""),
                    (line_id,) if line_id else (),
                ).fetchall()
                if not line_id and len(rows) > 1:
                    fixture_ids = set()
                    for tenant_id, raw in db.execute("SELECT id,config FROM tenants"):
                        try:
                            if json.loads(raw).get("demo_fixture") == MARKER:
                                fixture_ids.add(tenant_id)
                        except (TypeError, ValueError):
                            continue
                    fixture_lines = [row for row in rows if row[2] in fixture_ids]
                    if len(fixture_lines) == 1:
                        rows = fixture_lines
                if len(rows) != 1:
                    add("FAIL", "Select one Vobiz line; use --line-id if no unique demo line exists.")
                else:
                    candidate = rows[0]
                    if re.fullmatch(r"[a-f0-9]{32}", candidate[0]) and len(candidate[1] or "") >= 32:
                        selected = candidate
                        add("PASS", "Registered Vobiz line and routing secret are valid.")
                    else:
                        add("FAIL", "Registered Vobiz line or routing secret is invalid.")
                    checks.extend(_demo_checks(db, candidate[2], required=require_business_demo))
        except (sqlite3.Error, ValueError, TypeError):
            add("FAIL", "Configured database could not be read safely.")

    answer_url = expected_wss = None
    if selected:
        try:
            answer_url = vobiz_answer_url(public, selected[0], selected[1])
            expected_wss = answer_url.replace("https://", "wss://", 1).replace(
                "/webhooks/vobiz/", "/ws/vobiz/", 1
            )
            add("PASS", "Protected Answer URL syntax is valid; secret remains hidden.")
        except ValueError:
            add("FAIL", "Protected Answer URL is invalid.")

    dns_ok = _public_dns(public_parts.hostname) if public_parts.port in (None, 443) else False
    add("PASS" if dns_ok else "FAIL", "Public hostname resolves globally." if dns_ok
        else "Public hostname does not resolve to a global HTTPS address.")
    with httpx.Client(timeout=5, follow_redirects=False, trust_env=False) as client:
        for label, base in (("Local", local_base), ("Public", public)):
            if label == "Public" and not dns_ok:
                add("FAIL", "Public /healthz and /readyz are unavailable.")
                continue
            for path in ("/healthz", "/readyz"):
                ok = _status_ok(_probe(client, "GET", base.rstrip("/") + path))
                add("PASS" if ok else "FAIL", f"{label} {path}: {'reachable' if ok else 'unavailable'}.")
        if answer_url and expected_wss:
            local_url = local_base.rstrip("/") + urlsplit(answer_url).path
            local_ok = _answer_xml_ok(_probe(client, "POST", local_url), expected_wss)
            add("PASS" if local_ok else "FAIL", "Local Vobiz POST returns valid XML and matching WSS host."
                if local_ok else "Local Vobiz POST/XML/WSS check failed.")
            public_ok = dns_ok and _answer_xml_ok(_probe(client, "POST", answer_url), expected_wss)
            add("PASS" if public_ok else "FAIL", "Public Vobiz POST returns valid XML and matching WSS host."
                if public_ok else "Public Vobiz POST/XML/WSS check failed.")
            upgrade_ok = public_ok and _wss_upgrade_ok(expected_wss)
            add("PASS" if upgrade_ok else "FAIL", "Public WSS upgrade reaches the protected media route."
                if upgrade_ok else "Public WSS upgrade could not be verified.")
    add("WARN", "No real PSTN call or carrier playback was tested by this preflight.")
    return checks
