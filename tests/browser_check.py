"""Isolated browser workflow check. It never modifies the user's enterprise DB."""

import json
import socket
import sqlite3
import sys
import tempfile
import threading
import time
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

import uvicorn
from playwright.sync_api import sync_playwright


def main():
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from omnivoice.app import create_app
    from omnivoice.config import Settings

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
            listener = socket.socket()
            listener.bind(("127.0.0.1", 0))
            listener.listen(128)
            port = listener.getsockname()[1]
            server = uvicorn.Server(
                uvicorn.Config(
                    create_app(settings), host="127.0.0.1", port=port, access_log=False, log_level="warning"
                )
            )
            thread = threading.Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
            thread.start()
            try:
                for _ in range(60):
                    try:
                        urllib.request.urlopen(f"http://127.0.0.1:{port}/healthz", timeout=0.5)
                        break
                    except OSError:
                        time.sleep(0.25)
                with sync_playwright() as playwright:
                    browser = playwright.chromium.launch(channel="msedge", headless=True)
                    page = browser.new_page(viewport={"width": 1440, "height": 1100})
                    errors = []
                    page.on("pageerror", lambda error: errors.append(str(error)))
                    page.goto(f"http://127.0.0.1:{port}")
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

                    # Seed synthetic calls for inspector, legacy metrics, and pagination (OV-002 / OV-026)
                    conn = sqlite3.connect(Path(directory) / "browser.db")
                    try:
                        tenant_row = conn.execute("SELECT id FROM tenants LIMIT 1").fetchone()
                        assert tenant_row, "Tenant was not created"
                        now = time.time()
                        conn.execute(
                            "INSERT INTO calls (id, tenant_id, provider, status, started, ended, metrics) VALUES (?, ?, ?, ?, ?, ?, ?)",
                            (
                                "c1234567890abcdef",
                                tenant_row[0],
                                "twilio",
                                "completed",
                                now - 60,
                                now,
                                json.dumps(
                                    {
                                        "turns": [
                                            {
                                                "stt_endpoint_delay_ms": 80,
                                                "retrieval_ms": 12,
                                                "rag_retrieval_ms": 18,
                                                "llm_ttft_ms": 140,
                                                "speech_buffer_delay_ms": 21,
                                                "first_tts_ttfa_ms": 90,
                                                "carrier_framing_delay_ms": 200,
                                                "final_transcript_to_first_audio_sent_ms": 320,
                                                "user_transcript": (
                                                    "<img src=x onerror=window.__xss=1>What are your business hours?"
                                                ),
                                                "agent_response": "We are open 9am to 6pm Monday to Friday.",
                                            }
                                        ]
                                    }
                                ),
                            ),
                        )
                        conn.execute(
                            "INSERT INTO calls (id, tenant_id, provider, status, started, ended, metrics) VALUES (?, ?, ?, ?, ?, ?, ?)",
                            (
                                "legacy0000001",
                                tenant_row[0],
                                "exotel",
                                "completed",
                                now - 90,
                                now - 30,
                                json.dumps({"turns": [{}]}),
                            ),
                        )
                        conn.execute(
                            "INSERT INTO calls (id, tenant_id, provider, status, started, ended, metrics) VALUES (?, ?, ?, ?, ?, ?, ?)",
                            (
                                "vobizcall0001",
                                tenant_row[0],
                                "vobiz",
                                "completed",
                                now - 75,
                                now - 15,
                                json.dumps({"turns": []}),
                            ),
                        )
                        conn.executemany(
                            "INSERT INTO calls (id, tenant_id, provider, status, started, ended, metrics) VALUES (?, ?, ?, ?, ?, ?, ?)",
                            [
                                (
                                    f"hist{index:02d}aaaaaaaaaa",
                                    tenant_row[0],
                                    "exotel",
                                    "completed",
                                    now - 200 - index,
                                    now - 100 - index,
                                    json.dumps({"turns": []}),
                                )
                                for index in range(26)
                            ],
                        )
                        conn.execute(
                            "INSERT INTO actions (id, tenant_id, call_id, tool, arguments, tool_config, summary, status, created, expires) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                            (
                                "qaact123456789", tenant_row[0], "c1234567890abcdef",
                                "schedule_demo", "{}", "{}", "Synthetic browser QA booking",
                                "committed", now - 20, now + 1000,
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
                    page.locator("#upload-document").click()
                    page.locator('input[name="file"]').set_input_files(
                        {"name": "qa.txt", "mimeType": "text/plain", "buffer": b"Isolated QA document."}
                    )
                    page.locator("#submit-modal").click()
                    page.get_by_role("cell", name="qa.txt", exact=True).wait_for()
                    page.locator('[data-knowledge-kind="faq"]').click()
                    page.get_by_role("cell", name="What is this test?", exact=True).wait_for()
                    assert page.get_by_role("cell", name="qa.txt", exact=True).count() == 0
                    page.locator('[data-knowledge-kind="document"]').click()
                    page.get_by_role("cell", name="qa.txt", exact=True).wait_for()
                    assert page.get_by_role("cell", name="What is this test?", exact=True).count() == 0
                    page.locator('[data-knowledge-kind="all"]').click()
                    page.get_by_role("cell", name="What is this test?", exact=True).wait_for()
                    page.get_by_role("cell", name="qa.txt", exact=True).wait_for()
                    page.locator('[data-page="lines"]').click()

                    # Register Exotel line and verify connection modal
                    page.get_by_role("button", name="Connect number").click()
                    page.get_by_role("heading", name="Connect a phone number", exact=True).wait_for()
                    assert page.locator('select[name="provider"] option').evaluate_all(
                        "options => options.map(option => [option.value, option.textContent])"
                    ) == [
                        ["exotel", "Exotel · India"],
                        ["vobiz", "Vobiz · India"],
                        ["twilio", "Twilio"],
                    ]
                    assert page.get_by_label("Phone number", exact=True).get_attribute("placeholder") == "+91 98765 43210"
                    assert "OmniVoice does not purchase or provision carrier numbers" in page.locator("#modal-body").inner_text()
                    page.get_by_label("Phone number", exact=True).fill("+12025550199")
                    page.locator("#submit-modal").click()
                    page.get_by_role("cell", name="+12025550199", exact=True).wait_for()
                    page.locator('tr:has-text("+12025550199") button:has-text("Connection details")').click()
                    page.get_by_role("heading", name="Exotel connection details", exact=True).wait_for()
                    exotel_content = page.locator("#modal-body").inner_text()
                    assert "wss://voice.example.com/ws/exotel/" in exotel_content
                    assert "••••" in exotel_content
                    verify_conn = sqlite3.connect(Path(directory) / "browser.db")
                    try:
                        stream_secret = verify_conn.execute(
                            "SELECT stream_secret FROM lines WHERE number=?", ("+12025550199",)
                        ).fetchone()[0]
                    finally:
                        verify_conn.close()
                    assert stream_secret not in exotel_content
                    assert "/api/webhooks/" not in exotel_content
                    page.locator("#close-modal").click()

                    # Register Twilio line and verify connection modal
                    page.get_by_role("button", name="Connect number").click()
                    page.locator('select[name="provider"]').select_option("twilio")
                    page.get_by_label("Phone number", exact=True).fill("+12025550188")
                    page.locator("#submit-modal").click()
                    page.get_by_role("cell", name="+12025550188", exact=True).wait_for()
                    page.locator('tr:has-text("+12025550188") button:has-text("Connection details")').click()
                    page.get_by_role("heading", name="Twilio connection details", exact=True).wait_for()
                    twilio_content = page.locator("#modal-body").inner_text()
                    assert "https://voice.example.com/telephony/twilio/" in twilio_content
                    assert "/api/webhooks/" not in twilio_content
                    page.locator("#close-modal").click()

                    # Vobiz uses a protected HTTP Answer URL, not an Exotel stream URL.
                    page.get_by_role("button", name="Connect number").click()
                    page.locator('select[name="provider"]').select_option("vobiz")
                    page.get_by_label("Phone number", exact=True).fill("+919876543210")
                    page.locator("#submit-modal").click()
                    vobiz_row = page.locator('tr:has-text("+919876543210")')
                    vobiz_row.get_by_role("cell", name="Vobiz", exact=True).wait_for()
                    verify_conn = sqlite3.connect(Path(directory) / "browser.db")
                    try:
                        vobiz_line = verify_conn.execute(
                            "SELECT id, provider, stream_secret FROM lines WHERE number=?", ("+919876543210",)
                        ).fetchone()
                    finally:
                        verify_conn.close()
                    assert vobiz_line and vobiz_line[1] == "vobiz"
                    vobiz_row.get_by_role("button", name="Connection details", exact=False).click()
                    page.get_by_role("heading", name="Vobiz connection details", exact=True).wait_for()
                    vobiz_content = page.locator("#modal-body").inner_text()
                    assert "https://voice.example.com/webhooks/vobiz/" in vobiz_content
                    assert "HTTP POST" in vobiz_content
                    assert page.locator("#copy-connection-url").is_visible()
                    assert vobiz_line[2] not in vobiz_content
                    assert vobiz_line[2] not in page.locator("#modal").inner_html()
                    page.evaluate("""() => {
                      window.__copiedConnection = null;
                      Object.defineProperty(navigator, 'clipboard', {
                        configurable: true,
                        value: {writeText: async value => { window.__copiedConnection = value; }}
                      });
                    }""")
                    page.locator("#copy-connection-url").click()
                    copied = page.evaluate("window.__copiedConnection")
                    assert copied == (
                        f"https://voice.example.com/webhooks/vobiz/{vobiz_line[0]}/{vobiz_line[2]}"
                    )
                    parsed_copy = urlsplit(copied)
                    assert parsed_copy.scheme == "https" and parsed_copy.hostname == "voice.example.com"
                    assert parsed_copy.path.startswith("/webhooks/vobiz/")
                    assert not any(char.isspace() for char in copied)
                    assert not any(marker in copied for marker in ("•", "***", "<REDACTED>"))
                    page.locator("#close-modal").click()

                    for name in ["workspace", "knowledge", "lines", "live", "analytics", "calls", "actions", "settings", "overview"]:
                        page.locator(f'[data-page="{name}"]').click()
                        assert page.locator(f"#{name}").is_visible()
                        if name == "workspace":
                            workspace = page.locator("#workspace-details").inner_text()
                            assert "Browser QA — synthetic only" in workspace
                            assert "This is an isolated browser test." in workspace
                        if name == "live":
                            assert "No live calls" in page.locator("#live-calls-list").inner_text()
                        if name == "analytics":
                            charts = page.locator("#analytics-summary").inner_text().lower()
                            assert "total calls" in charts
                            assert "average server first audio" in charts
                            assert "twilio" in page.locator("#analytics-charts").inner_text().lower()
                            assert "Vobiz" in page.locator("#analytics-charts").inner_text()
                        if name == "actions":
                            page.locator('[data-action-filter="committed"]').click()
                            page.locator('[data-action-id="qaact123456789"]').click()
                            assert "Write committed after confirmation" in page.locator("#modal-body").inner_text()
                            page.locator("#close-modal").click()
                            page.locator('[data-action-filter="all"]').click()
                        if name == "calls":
                            assert page.locator('#call-provider option[value="vobiz"]').inner_text() == "Vobiz"
                            page.locator("#call-provider").select_option("vobiz")
                            page.locator('#calls-list [data-call="vobizcall0001"]').wait_for()
                            vobiz_call_row = page.locator('tr:has([data-call="vobizcall0001"])')
                            assert "Vobiz" in vobiz_call_row.inner_text()
                            vobiz_call_row.locator('[data-call="vobizcall0001"]').click()
                            assert "Vobiz" in page.locator("#modal-body").inner_text()
                            page.locator("#close-modal").click()
                            page.locator("#call-provider").select_option("twilio")
                            page.locator('#calls-list [data-call="c1234567890abcdef"]').wait_for()
                            page.locator("#call-status").select_option("completed")
                            page.locator("#call-period").select_option("7")
                            page.locator('#calls-list [data-call="c1234567890abcdef"]').wait_for()
                            page.locator("#call-provider").select_option("")
                            page.locator("#call-status").select_option("")
                            page.locator("#call-period").select_option("")
                            page.locator("#call-search").click()
                            page.locator("#call-search").fill("legacy0000001")
                            page.locator("#call-search").press("Enter")
                            page.locator('#calls-list[data-search="legacy0000001"]:not([data-loading])').wait_for()
                            page.locator('#calls-list [data-call="legacy0000001"]').wait_for()
                            page.locator('#calls-list [data-call="legacy0000001"]').click()
                            page.get_by_role("heading", name="Call Session legacy0000", exact=True).wait_for()
                            legacy_text = page.locator("#modal-body").inner_text()
                            assert "Transcript not recorded" in legacy_text
                            page.locator("#close-modal").click()
                            page.locator("#modal").wait_for(state="hidden")
                            page.locator("#call-search").click()
                            page.locator("#call-search").fill("")
                            page.locator("#call-search").press("Enter")
                            page.locator('#calls-list[data-search=""]:not([data-loading])').wait_for()
                            page.locator('#calls-list [data-call="c1234567890abcdef"]').wait_for()
                            page.locator("#calls-load-more").click()
                            page.locator('#calls-list [data-call="hist25aaaaaaaaaa"]').wait_for()
                            assert "sessions shown" in page.locator("#call-results-status").inner_text()
                            page.locator('#calls-list [data-call="c1234567890abcdef"]').click()
                            page.get_by_role("heading", name="Call Session c123456789", exact=True).wait_for()
                            assert page.locator(".speech-bubble.caller").is_visible()
                            assert page.locator(".speech-bubble.agent").is_visible()
                            modal_text = page.locator("#modal-body").inner_text()
                            assert "What are your business hours?" in modal_text
                            assert "We are open 9am to 6pm Monday to Friday." in modal_text
                            assert "TURN 1" in modal_text
                            page.screenshot(path=str(artifacts / "console-call-detail.png"), full_page=True)
                            page.get_by_role("tab", name="Conversation").focus()
                            page.keyboard.press("ArrowRight")
                            assert page.get_by_role("tab", name="Metrics").get_attribute("aria-selected") == "true"
                            assert page.locator("#inspector-pane-metrics").is_visible()
                            page.keyboard.press("Home")
                            assert page.get_by_role("tab", name="Conversation").get_attribute("aria-selected") == "true"
                            page.get_by_role("tab", name="Metrics").click()
                            assert page.locator(".turn-technical").is_visible()
                            modal_text = page.locator("#modal-body").inner_text()
                            assert "STT endpoint · VAD proxy 80 ms" in modal_text
                            assert "RAG 18 ms" in modal_text
                            assert "LLM TTFT 140 ms" in modal_text
                            assert "Carrier framing + send 200 ms" in modal_text
                            assert "Transcript → audio sent 320 ms" in modal_text
                            assert "VAD → audio sent · proxy —" not in modal_text
                            assert page.evaluate("window.__xss") is None
                            page.locator("#close-modal").click()
                        page.wait_for_timeout(220)
                        page.screenshot(path=str(artifacts / f"console-{name}.png"), full_page=True)
                    page.keyboard.press("Control+k")
                    assert page.evaluate("""() => { const box = document.querySelector('#command-palette').getBoundingClientRect(); return Math.abs((box.left + box.right) / 2 - innerWidth / 2) < 2 && Math.abs((box.top + box.bottom) / 2 - innerHeight / 2) < 2; }""")
                    page.locator("#command-input").fill("Analytics")
                    page.locator("#command-input").press("Enter")
                    assert page.locator("#analytics").is_visible()
                    page.locator('[data-page="overview"]').click()
                    assert page.locator("html").get_attribute("data-theme") == "light"
                    page.wait_for_timeout(220)
                    page.screenshot(path=str(artifacts / "console-overview-light.png"), full_page=True)
                    page.locator("#theme-toggle").click()
                    assert page.locator("html").get_attribute("data-theme") == "dark"
                    page.wait_for_timeout(280)
                    for width in (1440, 1024, 768, 390):
                        page.set_viewport_size({"width": width, "height": 900})
                        page.wait_for_timeout(280)
                        page.screenshot(path=str(artifacts / f"console-overview-dark-{width}.png"), full_page=True)
                        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
                    page.locator("#theme-toggle").click()
                    for width in (1920, 1024, 768, 390):
                        page.set_viewport_size({"width": width, "height": 900})
                        page.wait_for_timeout(280)
                        page.screenshot(path=str(artifacts / f"console-overview-{width}.png"), full_page=True)
                        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), (
                            f"Horizontal overflow at {width}px: "
                            f"{page.evaluate('''() => ({scroll: document.documentElement.scrollWidth, offenders: [...document.querySelectorAll('*')].filter(el => el.getBoundingClientRect().right > innerWidth + 1).slice(0, 8).map(el => [el.tagName, el.id, el.className, Math.round(el.getBoundingClientRect().right)])})''')}"
                        )
                    page.keyboard.press("Control+k")
                    assert page.evaluate("""() => { const box = document.querySelector('#command-palette').getBoundingClientRect(); return Math.abs((box.left + box.right) / 2 - innerWidth / 2) < 2 && Math.abs((box.top + box.bottom) / 2 - innerHeight / 2) < 2; }""")
                    page.keyboard.press("Escape")
                    page.locator("#mobile-menu-toggle").click()
                    assert page.locator("#mobile-menu-toggle").get_attribute("aria-expanded") == "true"
                    page.locator('[data-page="live"]').click()
                    assert page.locator("#live").is_visible()
                    assert page.locator("#mobile-menu-toggle").get_attribute("aria-expanded") == "false"
                    page.locator("#nav-scrim").wait_for(state="hidden")
                    page.locator("#mobile-menu-toggle").click()
                    page.locator('[data-page="calls"]').click()
                    assert page.locator(".mobile-call-list").is_visible()
                    page.wait_for_timeout(280)
                    page.screenshot(path=str(artifacts / "console-mobile-calls.png"), full_page=True)
                    page.locator('[data-mobile-call="c1234567890abcdef"]').click()
                    page.get_by_role("heading", name="Call Session c123456789", exact=True).wait_for()
                    assert page.locator("#modal").is_visible()
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
                        "workspace navigation",
                        "live calls empty state",
                        "analytics rendering",
                        "knowledge filters",
                        "call search and filters",
                        "call history pagination",
                        "call inspector timeline",
                        "technical latency metrics",
                        "legacy call compatibility",
                        "call details modal",
                        "mobile navigation",
                        "mobile call inspection",
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
                listener.close()
                assert not thread.is_alive(), "Test server did not shut down"


if __name__ == "__main__":
    main()
