# OmniVoice final demo runbook

**Evidence boundary:** the seeded fixture is synthetic. The OV-031 live-provider rehearsal used a local carrier-shaped loopback, not PSTN. Historical OV-005 Exotel handset calls validated an earlier voice path. No current Vobiz PSTN, sales-agent PSTN, acoustic mouth-to-ear latency, KooKoo PSTN, or Railway deployment is claimed.

## Before the demo

1. In a disposable copy of the repository, verify the intended commit and configure private `.env` values. Use Gnani for both `STT_PROVIDER` and `TTS_PROVIDER` if demonstrating the Gnani variant, and configure Groq. Never display or commit `.env`.
2. Seed once: `.\.venv\Scripts\python.exe scripts/seed_demo.py`. Inspect the reset plan with `.\.venv\Scripts\python.exe scripts/reset_demo.py --dry-run`, then run `scripts/reset_demo.py` when you need a fresh synthetic lead, six approved FAQs and three future slots. The default database is `data/demo/omnivoice-demo.db`, separate from `data/omnivoice.db`. Reset refuses any marked tenant with a registered carrier line or active call; it never modifies another tenant, `.env`, carrier settings or research files.
3. Set the process variable `OMNI_DATABASE` to the **absolute path** of that demo database before starting the app. In a PowerShell session: `$env:OMNI_DATABASE = (Resolve-Path data/demo/omnivoice-demo.db).Path`. Start `.\.venv\Scripts\python.exe -m omnivoice.cli serve --host 127.0.0.1 --port 8000`.
4. In another terminal run `.\.venv\Scripts\python.exe scripts/demo_preflight.py --carrier loopback`. It checks fixture, model, settings, `/healthz` and `/readyz` without printing credentials or making provider calls. Fix every `FAIL`; investigate `WARN`. Open the console at `http://127.0.0.1:8000/` using the private administrator token.
5. For the Vobiz carrier branch, use the separate [Vobiz integration guide](integrations/VOBIZ.md) and its single-command preflight. A registered number is local configuration, not proof of a live carrier path. KooKoo remains in a separate parked worktree and is not the final carrier for this runbook.

### Temporary public endpoint when Railway is unavailable

For Vobiz, install `cloudflared`, stop any stale server on port 8000, then run `powershell -ExecutionPolicy Bypass -File .\scripts\start_demo_local.ps1 -EnvFile C:\Projects\OMNIVOICE\.env` from the Vobiz branch. This starts a temporary Cloudflare Quick Tunnel and the local service with the **same process-only public origin**, then runs the read-only Vobiz preflight. It does not edit `.env` or the carrier dashboard. Copy the protected URL from the authenticated Console after preflight, paste it into the Vobiz Voice Application as a POST Answer URL, and attach the purchased DID yourself. The Quick Tunnel hostname changes on restart; update the Voice Application URL after every restart. Keep the launcher and computer awake through the call. This is a temporary development path, not production deployment.

For Railway, use the Dockerfile with the platform `PORT`, bind `0.0.0.0`, mount a persistent volume at `/app/data`, set `OMNI_DATABASE=/app/data/omnivoice.db`, configure private environment variables and a stable HTTPS `OMNI_PUBLIC_BASE_URL`. A single worker is required. No Railway service has been deployed or carrier cutover performed in this work.

## First Vobiz PSTN validation: media only

The first real call is a **new validation**, not a repetition of the synthetic fixture. After the Vobiz preflight has no `FAIL`, manually call the purchased DID. Say “Hello”, “What is OmniVoice?”, and “What languages do you support?”, then hang up. Verify greeting, inbound transcription, spoken replies, Live → Call History transition, and the Vobiz Console call log. Do not request booking on this first call. Use the [blank PSTN evidence template](research/VOBIZ_PSTN_VALIDATION_TEMPLATE.md); do not mark it successful until the call actually works.

## Subsequent business-action presentation sequence

Use this sequence only after basic Vobiz media succeeds and `scripts/vobiz_demo_preflight.py --require-business-demo` passes. The marked synthetic lead, slots, FAQs and Vobiz line must share one tenant. A separate call is required.

| Step | Caller/operator | Show in console |
| --- | --- | --- |
| 1 | User-initiated call to a validated number; ask “What is OmniVoice?” | Live call, provider, greeting and grounded FAQ. |
| 2 | Ask “Do you have my details?”; provide synthetic reference `DEMO-ALPHA-001`. | Tenant-scoped `lookup_lead` result. Do not infer identity from caller ID. |
| 3 | Ask for a demo next Friday afternoon. | `check_demo_slots` results; availability is read-only. |
| 4 | Choose the 4 PM slot. | `schedule_demo` proposal; no booking yet. |
| 5 | Listen to the full confirmation prompt, then say “Yes.” | Only a verified playback receipt may arm the action; one explicit confirmation commits once. |
| 6 | After hangup, inspect Call History, Actions and Analytics. | Completed call, transcript/turn metrics where captured, tool events and one committed booking. Never label server timing as acoustic latency. |

If the carrier or speech provider fails, show the actual failure state; do not narrate a booking that was not committed. A local `completed` status means the WebSocket session ended without a recorded local error; carrier completion must be checked separately in Vobiz's call log.

## Backups in evidence order

1. **Real carrier:** only a user-initiated controlled call after carrier/account validation. Historical Exotel evidence does not validate the current sales path.
2. **Live-provider local loopback:** run the documented OV-031 controlled rehearsal if Gnani and Groq are reachable. Label it non-PSTN and retain failed attempts alongside passes.
3. **Deterministic rehearsal:** `.\.venv\Scripts\python.exe scripts/rehearse_voice_sales_agent.py --output <new-temporary-json-path>`. It uses synthetic providers and local SQLite; its 12 scenarios exercise safe action behavior. The [existing checklist](FINAL_DEMO_CHECKLIST.md) shows how to keep a disposable happy-path database open in the console.
4. **Recording:** show one only if an actual, reviewed recording exists. None is created or claimed here.

## Freeze and claim boundaries

Ready now: local synthetic fixture/reset/preflight, deterministic action rehearsal, documented local provider-loopback fallback and deployment configuration. On the Vobiz branch, the carrier adapter and temporary local launcher are locally testable; real Vobiz PSTN remains pending an attachable purchased DID and a controlled call. Railway remains deferred. Optional after demo: production database migration, distributed scale and external CRM/calendar connectors. Do not change research measurements or present local server timing as mouth-to-ear latency.
