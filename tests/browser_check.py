"""Isolated browser workflow check. It never modifies the user's enterprise DB."""

import json
import sqlite3
import tempfile
import threading
import time
import urllib.request
from pathlib import Path

import uvicorn
from playwright.sync_api import sync_playwright

from omnivoice.app import create_app
from omnivoice.config import Settings


def main():
    root = Path(__file__).resolve().parents[1]
    artifacts = root / "artifacts"
    artifacts.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as directory:
        settings = Settings(
            _env_file=None,
            database=Path(directory) / "browser.db",
            admin_token="isolated-browser-test-token",
            semantic_enabled=False,
            public_base_url="https://voice.example.com",
        )
        with (artifacts / "browser-server.log").open("w") as log:
            log.write("Browser workflow uses an isolated in-process ASGI server.\n")
            server = uvicorn.Server(
                uvicorn.Config(
                    create_app(settings), host="127.0.0.1", port=8001, access_log=False, log_level="warning"
                )
            )
            thread = threading.Thread(target=server.run, daemon=True)
            thread.start()
            try:
                for _ in range(60):
                    try:
                        urllib.request.urlopen("http://127.0.0.1:8001/healthz", timeout=0.5)
                        break
                    except OSError:
                        time.sleep(0.25)
                with sync_playwright() as playwright:
                    browser = playwright.chromium.launch(channel="msedge", headless=True)
                    page = browser.new_page(viewport={"width": 1440, "height": 1100})
                    errors = []
                    page.on("pageerror", lambda error: errors.append(str(error)))
                    page.goto("http://127.0.0.1:8001")
                    page.screenshot(path=str(artifacts / "console-desktop.png"), full_page=True)
                    page.get_by_role("button", name="Connect console").click()
                    page.get_by_label("API token", exact=True).fill("isolated-browser-test-token")
                    page.locator("#submit-modal").click()
                    page.get_by_role("button", name="Disconnect", exact=True).wait_for()
                    page.get_by_role("button", name="New enterprise").click()
                    page.get_by_label("Enterprise name").fill("Browser QA — synthetic only")
                    page.get_by_label("Opening greeting").fill("This is an isolated browser test.")
                    page.get_by_label("Explicit confirmation phrase").fill("yes confirm this test")
                    page.locator("#submit-modal").click()
                    page.get_by_role("heading", name="Enterprise created", exact=True).wait_for()
                    page.locator("#close-modal").click()

                    # Seed synthetic call record for call-details modal verification (OV-002)
                    conn = sqlite3.connect(Path(directory) / "browser.db")
                    try:
                        tenant_row = conn.execute("SELECT id FROM tenants LIMIT 1").fetchone()
                        assert tenant_row, "Tenant was not created"
                        conn.execute(
                            "INSERT INTO calls (id, tenant_id, provider, status, started, ended, metrics) VALUES (?, ?, ?, ?, ?, ?, ?)",
                            (
                                "c1234567890abcdef",
                                tenant_row[0],
                                "twilio",
                                "completed",
                                time.time() - 60,
                                time.time(),
                                json.dumps(
                                    {
                                        "turns": [
                                            {
                                                "final_transcript_to_first_audio_sent_ms": 320,
                                                "user_transcript": "What are your business hours?",
                                                "agent_response": "We are open 9am to 6pm Monday to Friday.",
                                            }
                                        ]
                                    }
                                ),
                            ),
                        )
                        conn.commit()
                    finally:
                        conn.close()

                    page.locator('[data-page="knowledge"]').click()
                    page.get_by_role("button", name="Add FAQ").click()
                    page.get_by_label("Caller question").fill("What is this test?")
                    page.get_by_label("Business-approved answer").fill(
                        "This is a synthetic UI test, not business knowledge."
                    )
                    page.get_by_label("I approve this answer").check()
                    page.locator("#submit-modal").click()
                    page.get_by_role("cell", name="What is this test?", exact=True).wait_for()
                    page.get_by_role("button", name="Upload document").click()
                    page.locator('input[name="file"]').set_input_files(
                        {"name": "qa.txt", "mimeType": "text/plain", "buffer": b"Isolated QA document."}
                    )
                    page.locator("#submit-modal").click()
                    page.get_by_role("cell", name="qa.txt", exact=True).wait_for()
                    page.locator('[data-page="lines"]').click()

                    # Register Exotel line and verify connection modal
                    page.get_by_role("button", name="Connect number").click()
                    page.get_by_label("Phone number (E.164)").fill("+12025550199")
                    page.locator("#submit-modal").click()
                    page.get_by_role("cell", name="+12025550199", exact=True).wait_for()
                    page.locator('tr:has-text("+12025550199") button:has-text("Connection details")').click()
                    page.get_by_role("heading", name="Exotel connection details", exact=True).wait_for()
                    exotel_content = page.locator("#modal-body").inner_text()
                    assert "wss://voice.example.com/ws/exotel/" in exotel_content
                    assert "/api/webhooks/" not in exotel_content
                    page.locator("#close-modal").click()

                    # Register Twilio line and verify connection modal
                    page.get_by_role("button", name="Connect number").click()
                    page.locator('select[name="provider"]').select_option("twilio")
                    page.get_by_label("Phone number (E.164)").fill("+12025550188")
                    page.locator("#submit-modal").click()
                    page.get_by_role("cell", name="+12025550188", exact=True).wait_for()
                    page.locator('tr:has-text("+12025550188") button:has-text("Connection details")').click()
                    page.get_by_role("heading", name="Twilio connection details", exact=True).wait_for()
                    twilio_content = page.locator("#modal-body").inner_text()
                    assert "https://voice.example.com/telephony/twilio/" in twilio_content
                    assert "/api/webhooks/" not in twilio_content
                    page.locator("#close-modal").click()

                    for name in ["calls", "actions", "settings", "overview"]:
                        page.locator(f'[data-page="{name}"]').click()
                        assert page.locator(f"#{name}").is_visible()
                        if name == "calls":
                            page.locator('#calls-list [data-call="c1234567890abcdef"]').click()
                            page.get_by_role("heading", name="Call Session c123456789", exact=True).wait_for()
                            modal_text = page.locator("#modal-body").inner_text()
                            assert "What are your business hours?" in modal_text
                            assert "We are open 9am to 6pm Monday to Friday." in modal_text
                            page.locator("#close-modal").click()
                    page.get_by_role("button", name="Disconnect", exact=True).click()
                    page.set_viewport_size({"width": 390, "height": 844})
                    page.screenshot(path=str(artifacts / "console-mobile.png"), full_page=True)
                    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
                    assert not errors, errors
                    browser.close()
                report = {
                    "result": "passed",
                    "checks": [
                        "login",
                        "enterprise creation",
                        "FAQ approval",
                        "document upload",
                        "line registration",
                        "carrier connection modal",
                        "navigation",
                        "call details modal",
                        "logout",
                        "mobile overflow",
                        "JavaScript errors",
                    ],
                    "data": "temporary SQLite database, removed after test",
                }
                (artifacts / "browser-check.json").write_text(json.dumps(report, indent=2))
                print(json.dumps(report))
            finally:
                server.should_exit = True
                thread.join(timeout=10)
                assert not thread.is_alive(), "Test server did not shut down"


if __name__ == "__main__":
    main()
