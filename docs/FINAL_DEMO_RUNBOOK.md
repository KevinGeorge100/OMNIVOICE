# OmniVoice final demo runbook

**Evidence boundary:** the seeded fixture is synthetic. The OV-031 live-provider rehearsal used a local carrier-shaped loopback, not PSTN. Historical OV-005 Exotel handset calls validated an earlier voice path. No current sales-agent PSTN, acoustic mouth-to-ear latency, KooKoo PSTN, or Railway deployment is claimed.

## Before the demo

1. In a disposable copy of the repository, verify the intended commit and configure private `.env` values. Use Gnani for both `STT_PROVIDER` and `TTS_PROVIDER` if demonstrating the Gnani variant, and configure Groq. Never display or commit `.env`.
2. Seed once: `.\.venv\Scripts\python.exe scripts/seed_demo.py`. Inspect the reset plan with `.\.venv\Scripts\python.exe scripts/reset_demo.py --dry-run`, then run `scripts/reset_demo.py` when you need a fresh synthetic lead, six approved FAQs and three future slots. The default database is `data/demo/omnivoice-demo.db`, separate from `data/omnivoice.db`. Reset refuses any marked tenant with a registered carrier line or active call; it never modifies another tenant, `.env`, carrier settings or research files.
3. Set the process variable `OMNI_DATABASE` to the **absolute path** of that demo database before starting the app. In a PowerShell session: `$env:OMNI_DATABASE = (Resolve-Path data/demo/omnivoice-demo.db).Path`. Start `.\.venv\Scripts\python.exe -m omnivoice.cli serve --host 127.0.0.1 --port 8000`.
4. In another terminal run `.\.venv\Scripts\python.exe scripts/demo_preflight.py --carrier loopback`. It checks fixture, model, settings, `/healthz` and `/readyz` without printing credentials or making provider calls. Fix every `FAIL`; investigate `WARN`. Open the console at `http://127.0.0.1:8000/` using the private administrator token.
5. If a real carrier is available, use `--carrier exotel` or `--carrier kookoo`. The app must have a registered line for the marked demo tenant and an HTTPS `OMNI_PUBLIC_BASE_URL`. KooKoo requires a DID, SIP registration, verified account-specific stream protocol and a public HTTP webhook **plus** WSS route. Do not use KooKoo for a write-action demo until reliable playback completion is verified; its current adapter intentionally leaves writes unarmed.

### Temporary public endpoint when Railway is unavailable

Install `cloudflared` locally, then run `powershell -ExecutionPolicy Bypass -File .\scripts\start-demo-tunnel.ps1` after seeding. The launcher starts a temporary Cloudflare Quick Tunnel and the app with matching `OMNI_PUBLIC_BASE_URL` and demo database. It prints only the public origin, never a stream secret. It does **not** change a carrier dashboard. In the separate preflight terminal, set `OMNI_DATABASE` to the same absolute demo database path and `OMNI_PUBLIC_BASE_URL` to the printed origin; process variables from the launcher do not propagate to another terminal. Copy the protected connection URL from the authenticated OmniVoice console into the carrier dashboard yourself, then run preflight with `--carrier exotel` or `--carrier kookoo`. A Quick Tunnel URL changes on restart; the computer and tunnel must remain awake. Stop the launcher after the demo. This is a temporary fallback, not a persistent production deployment.

For Railway, use the Dockerfile with the platform `PORT`, bind `0.0.0.0`, mount a persistent volume at `/app/data`, set `OMNI_DATABASE=/app/data/omnivoice.db`, configure private environment variables and a stable HTTPS `OMNI_PUBLIC_BASE_URL`. A single worker is required. No Railway service has been deployed or carrier cutover performed in this work.

## Live presentation sequence

| Step | Caller/operator | Show in console |
| --- | --- | --- |
| 1 | User-initiated call to a validated number; ask “What is OmniVoice?” | Live call, provider, greeting and grounded FAQ. |
| 2 | Ask “Do you have my details?”; provide synthetic reference `DEMO-ALPHA-001`. | Tenant-scoped `lookup_lead` result. Do not infer identity from caller ID. |
| 3 | Ask for a demo next Friday afternoon. | `check_demo_slots` results; availability is read-only. |
| 4 | Choose the 4 PM slot. | `schedule_demo` proposal; no booking yet. |
| 5 | Listen to the full confirmation prompt, then say “Yes.” | Only a verified playback receipt may arm the action; one explicit confirmation commits once. |
| 6 | After hangup, inspect Call History, Actions and Analytics. | Completed call, transcript/turn metrics where captured, tool events and one committed booking. Never label server timing as acoustic latency. |

If the carrier or speech provider fails, show the actual failure state; do not narrate a booking that was not committed. A KooKoo call can demonstrate read-only conversation and barge-in after account validation, but cannot yet demonstrate a confirmed write.

## Backups in evidence order

1. **Real carrier:** only a user-initiated controlled call after carrier/account validation. Historical Exotel evidence does not validate the current sales path.
2. **Live-provider local loopback:** run the documented OV-031 controlled rehearsal if Gnani and Groq are reachable. Label it non-PSTN and retain failed attempts alongside passes.
3. **Deterministic rehearsal:** `.\.venv\Scripts\python.exe scripts/rehearse_voice_sales_agent.py --output <new-temporary-json-path>`. It uses synthetic providers and local SQLite; its 12 scenarios exercise safe action behavior. The [existing checklist](FINAL_DEMO_CHECKLIST.md) shows how to keep a disposable happy-path database open in the console.
4. **Recording:** show one only if an actual, reviewed recording exists. None is created or claimed here.

## Freeze and claim boundaries

Ready now: local synthetic fixture/reset/preflight, deterministic action rehearsal, documented local provider-loopback fallback and deployment configuration. Waiting on external providers: Exotel credits/account readiness, KooKoo KYC/DID/protocol confirmation, and Railway plan/platform readiness. Optional after demo: production database migration, distributed scale and external CRM/calendar connectors. Do not change research measurements or present local server timing as mouth-to-ear latency.
