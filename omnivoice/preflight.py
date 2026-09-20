"""Read-only review checks; never places calls or sends audio to providers."""

import asyncio
import json
import sqlite3

import httpx
from websockets.asyncio.client import connect

from .config import Settings


async def main():
    settings = Settings()
    failures = []
    async with httpx.AsyncClient(timeout=10, trust_env=False) as client:
        try:
            response = await client.get(
                "http://127.0.0.1:8000/api/status",
                headers={"Authorization": "Bearer " + settings.admin_token.get_secret_value()},
            )
            response.raise_for_status()
            status = response.json()
            print("Local voice engine:", "READY" if status["voice_ready"] else "NOT READY")
            if not status["voice_ready"]:
                failures.append("Voice configuration is incomplete")
            if status["active_calls"]:
                print("Active calls present: do not restart services.")
        except Exception as error:
            failures.append("Local engine unavailable: " + type(error).__name__)
        try:
            with sqlite3.connect(settings.database) as db:
                rows = db.execute(
                    "SELECT id,number,stream_secret FROM lines WHERE provider='exotel'"
                ).fetchall()
                count = db.execute("SELECT count(*) FROM knowledge").fetchone()[0]
            print("Knowledge entries:", count)
            if not count:
                failures.append("Knowledge base is empty")
            if not rows:
                failures.append("No Exotel line registered")
            if not settings.public_base_url.startswith("https://"):
                raise ValueError("Public origin missing")
            for line_id, number, secret in rows:
                url = settings.public_base_url.replace("https://", "wss://", 1)
                url += f"/ws/exotel/{line_id}/{secret}"
                async with connect(url, proxy=None, open_timeout=10) as ws:
                    # Stop before session admission: no STT/TTS or billable outbound call.
                    await ws.send(json.dumps({"event": "stop"}))
                print("Public authenticated media connection:", number, "REACHABLE")
            for path in ("/", "/api/tenants", "/docs"):
                response = await client.get(settings.public_base_url + path)
                if response.status_code != 404:
                    failures.append("Public management-route isolation needs checking")
                    break
        except Exception as error:
            failures.append("Public media check failed: " + type(error).__name__)
    for failure in failures:
        print("ATTENTION:", failure)
    print("Carrier routing, audible greeting and conversation require a real rehearsal call.")
    print("RESULT:", "FIX ITEMS BEFORE REVIEW" if failures else "TECHNICAL PREFLIGHT PASSED")
    return bool(failures)


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
