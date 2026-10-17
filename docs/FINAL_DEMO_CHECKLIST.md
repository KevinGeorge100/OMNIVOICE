# OmniVoice — Final Demo Readiness Checklist (OV-033)

Use [the single demo script](FINAL_DEMO_SCRIPT.md). Check actual state before presenting; do not infer provider or carrier availability from old artifacts.

**OV-033 local smoke, 2026-10-17:** A temporary FastAPI instance returned HTTP 200 for `/healthz`, `/readyz` and `/` (Operations Console HTML). The deterministic runner passed 12/12; `happy_path` created one booking, negative/ambiguous/stale/lead-not-found cases created none, and `duplicate_confirmation` retained one. A persisted **synthetic** happy-path fixture was also visible through the same server's authenticated tenant/call/action APIs (one tenant, one call, one action). One additional real Gnani STT → Groq → Gnani TTS **local loopback** run passed 20/20 acceptance checks, made one confirmed local booking, produced 106 valid carrier-shaped frames and spoke final success. These disposable outputs were written under the system temporary directory, not over the retained OV-031 artifacts. This is a readiness smoke, **not a new research benchmark or physical PSTN validation**. Provider availability can change; repeat the pre-demo checks on presentation day.

## Before the demo

- [ ] Repository is clean on the intended reviewed commit; record `git rev-parse HEAD`. The research baseline before OV-033 was `3e37f66c542917c346d3f86cc9eeb37920c6e146`.
- [ ] `.env` is present locally and excluded from Git; verify only **presence**, never print keys. Sarvam is the default STT/TTS; Gnani/Groq must be explicitly configured for the Level B variant.
- [ ] Synthetic lead/slot fixture is fresh, uses a future date, and has zero pre-existing bookings. Use temporary SQLite; do not touch customer records.
- [ ] Verify Gnani and Groq reachability if Level B is chosen. If unavailable, select the deterministic Level A fallback and label it clearly.
- [ ] Start the local FastAPI server; check `/health` or the repository's documented health endpoint. Load the Operations Console and sign in with local demo credentials.
- [ ] Check the audio route used by the demo: loopback carrier framing, speaker/microphone if a live audible walkthrough is used, and no unexpected device muting.
- [ ] Langfuse is optional. If enabled, confirm only anonymized metadata is exported; local JSON/SQLite remains authoritative. No trace dashboard is required for the demo to pass.
- [ ] Keep [OV-031 retained results](research/OV-031_VOICE_AGENT_REHEARSAL.md) and [metric registry](research/FINAL_METRICS_REGISTRY.md) open as backup evidence.

### Prepare same-call console evidence (synthetic fixture)

From the repository root in PowerShell, use a fresh disposable directory. This replays the **deterministic** `happy_path` once and leaves its SQLite file available for the console. It is not the live-provider or PSTN path.

```powershell
$demoDir = Join-Path $env:TEMP ("omnivoice-final-demo-" + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $demoDir | Out-Null
$env:OMNI_OV033_DEMO_DIR = $demoDir
@'
import asyncio, os
from pathlib import Path
from scripts.rehearse_voice_sales_agent import run_scenario
result = asyncio.run(run_scenario("happy_path", Path(os.environ["OMNI_OV033_DEMO_DIR"])))
assert result["passed"] and result["booking_count"] == 1 and result["spoken_success"]
print("synthetic happy path: PASS; one booking")
'@ | .\.venv\Scripts\python.exe -
$env:OMNI_DATABASE = Join-Path $demoDir 'sales-rehearsal.db'
.\.venv\Scripts\python.exe -m uvicorn omnivoice.app:create_app --factory --host 127.0.0.1 --port 8765
```

Open `http://127.0.0.1:8765/` in the browser and authenticate with the local admin token. Check the one synthetic tenant/call and its committed action. Stop this temporary server after the demonstration. The default runner's `--output` mode uses an auto-removed temporary database, so **do not** expect that mode's call to appear in a separately running console.

## During the demo

- [ ] State “local carrier-loopback” versus “physical PSTN” accurately.
- [ ] Narrate the `happy_path` fixture's approved FAQ/product question, lead lookup, slot lookup, booking proposal, replayed exact confirmation and stubbed final audio.
- [ ] Before confirmation: action is staged/armed only after prompt mark; booking count is **0**.
- [ ] After exact “Yes”: action is `committed`, booking count is **1**, and spoken success matches persisted result.
- [ ] Show the separate `duplicate_confirmation` scenario if repeat safety is requested: its booking count remains **1**, with no second commit.
- [ ] Inspect local Operations Console call/turn/action evidence and server timing/tool metrics. Do not describe synthetic stub timings as live-provider or mouth-to-ear latency.

## Backup if a live stage fails

1. Run the deterministic rehearsal with a **new temporary output path**: `.venv\Scripts\python.exe scripts/rehearse_voice_sales_agent.py --output <temporary-output.json>`. It must report 12/12 and the happy-path/duplicate safety assertions. The runner itself never calls a customer database or places a PSTN call.
2. Show the retained [Level B report](research/OV-031_VOICE_AGENT_REHEARSAL.md) and its seven-attempt record, including five failures. Do not show only the passing attempts.
3. Show the [OV-030 routing report](research/OV-030_AGENT_EVALUATION.md) and the [OV-011B safety report](research/OV-011B_AGENT_EVALUATION.md) as separate experiments.
4. Use verified screenshots or a backup recording only if produced and reviewed later; none is asserted here.

## After the demo

- [ ] Stop the local test server/loopback session and close any temporary fixture database.
- [ ] Remove only disposable demo output after confirming its path; preserve committed research artifacts.
- [ ] Check that no synthetic fixture was written into a customer tenant and that the repository remains clean.
- [ ] Record whether the demo used deterministic, live-provider local loopback, or physical PSTN evidence; never merge the categories in the final report.
