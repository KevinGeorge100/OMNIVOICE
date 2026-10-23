"""Check one Vobiz Answer URL without printing its routing secret or full URL."""

import argparse
import ipaddress
import socket
import sqlite3
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote, urlsplit
from xml.etree import ElementTree

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from omnivoice.config import Settings  # noqa: E402
from omnivoice.vobiz_url import vobiz_answer_url  # noqa: E402


def _probe(url: str, *, method: str = "GET", data: dict | None = None) -> httpx.Response | None:
    try:
        with httpx.Client(timeout=5, follow_redirects=False, trust_env=False) as client:
            return client.request(method, url, data=data)
    except httpx.HTTPError:
        return None


def _resolves_publicly(host: str, port: int) -> bool:
    try:
        addresses = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        return bool(addresses) and all(
            ipaddress.ip_address(address[4][0]).is_global for address in addresses
        )
    except (OSError, ValueError):
        return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--line-id", help="Select one registered Vobiz line if more than one exists")
    parser.add_argument("--local-base", default="http://127.0.0.1:8000")
    parser.add_argument("--copy", action="store_true", help="Copy only after public and local checks pass")
    args = parser.parse_args(argv)

    env_file = args.env_file.resolve()
    if not env_file.is_file():
        print("Configuration: FAIL (.env unavailable; pass --env-file)")
        return 2
    settings = Settings(_env_file=env_file)
    database = settings.database
    if not database.is_absolute():
        database = env_file.parent / database
    if not database.is_file():
        print("Vobiz line: FAIL (configured database unavailable)")
        return 2
    with sqlite3.connect(f"file:{database.as_posix()}?mode=ro", uri=True) as conn:
        rows = conn.execute(
            "SELECT id, stream_secret FROM lines WHERE provider='vobiz'"
            + (" AND id=?" if args.line_id else ""),
            (args.line_id,) if args.line_id else (),
        ).fetchall()
    if len(rows) != 1:
        print("Vobiz line: FAIL (select exactly one registered line with --line-id)")
        return 2
    line_id, secret = rows[0]
    try:
        answer_url = vobiz_answer_url(settings.public_base_url, line_id, secret)
        local = urlsplit(args.local_base)
        if (
            local.scheme != "http" or local.hostname not in {"localhost", "127.0.0.1", "::1"}
            or local.path or local.query or local.fragment or local.username or local.password
        ):
            raise ValueError("Local route probe must target loopback HTTP")
    except ValueError:
        print("Vobiz Answer URL\nSyntax: FAIL (public HTTPS origin or route invalid)")
        return 2

    parsed = urlsplit(answer_url)
    route = "/webhooks/vobiz/" + quote(line_id, safe="") + "/<REDACTED>"
    print("Vobiz Answer URL")
    print("Scheme: HTTPS")
    print(f"Host: {parsed.hostname}")
    print(f"Route: {route}")
    print(f"Length: {len(answer_url)}")
    print("Syntax: PASS")

    health = _probe(f"{parsed.scheme}://{parsed.netloc}/healthz") if _resolves_publicly(
        parsed.hostname, parsed.port or 443
    ) else None
    health_ok = health is not None and health.status_code == 200
    print(f"Public health: {'PASS' if health_ok else 'FAIL'}")

    local_url = args.local_base.rstrip("/") + parsed.path
    def valid_xml_response(response: httpx.Response | None) -> bool:
        if response is None or response.status_code != 200:
            return False
        try:
            return (
                response.headers.get("content-type", "").startswith("application/xml")
                and ElementTree.fromstring(response.content).tag == "Response"
            )
        except ElementTree.ParseError:
            return False

    local_ok = valid_xml_response(_probe(
        local_url, method="POST", data={"CallUUID": "synthetic-url-check"}
    ))
    print(f"Local route: {'PASS' if local_ok else 'FAIL'}")
    public_ok = valid_xml_response(_probe(
        answer_url, method="POST", data={"CallUUID": "synthetic-public-url-check"}
    )) if health_ok else False
    print(f"Webhook route: {'PASS' if public_ok else 'FAIL'}")

    ready = health_ok and local_ok and public_ok
    print(f"Clipboard: {'READY' if ready else 'BLOCKED'}")
    if args.copy and ready:
        if sys.platform != "win32":
            print("Copy: FAIL (automatic clipboard copy is supported on Windows only)")
            return 2
        try:
            subprocess.run(["clip.exe"], input=answer_url, text=True, check=True, capture_output=True)
        except (OSError, subprocess.CalledProcessError):
            print("Copy: FAIL (clipboard unavailable)")
            return 2
        print("Copy: PASS (full protected URL copied; keep it private)")
    return 0 if ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
