# OmniVoice — Project Status

**Current Maturity Level:** **MINIMUM VIABLE PRODUCT (MVP) — Real PSTN Verified**
**Document Status:** Living reality baseline
**Last Updated:** 2026-09-21

---

## 1. Executive Summary & Reality Statement

> [!IMPORTANT]
> **Real PSTN end-to-end telephone validation successfully completed (OV-005).**
> Live telephone validation has been proven across 3 physical mobile telephone calls on the Exotel carrier network (`+914954269065`) via secure WebSocket tunnel. Inbound carrier lifecycle, greeting dispatch (~250 ms), STT -> RAG -> LLM -> TTS -> PSTN audio loop, true acoustic barge-in, backchannel suppression, and full SQLite telemetry persistence are operational and repeatable.
> Realtime turn-taking has been stabilized via ADR-001 (0 false interrupted turns, 0 false carrier clears, and 0 false barge-in events in Call #3; Call #2 turn-thrashing regression eliminated). Remaining active quality frontiers are voice continuity / natural TTS pipelining (OV-023) and graceful dialogue limitation handling (OV-024).

OmniVoice is currently an **asynchronous, single-worker Python 3.11 voice application and media server**. It demonstrates a working integration between telephony WebSockets (Exotel/Twilio) and AI cloud providers (Sarvam AI for regional STT/TTS, Groq for Llama-3 LLM reasoning). It features a local neural VAD (Silero ONNX), an in-memory document vector index (FAISS), and an embedded administrative console.

---

## 2. Subsystem Status Matrix

### Working Subsystems (Verified in Local Test Environment & Live PSTN)
* **Real PSTN Inbound Telephony (`omnivoice/app.py`, `omnivoice/session.py`)**: Verified live over Exotel PSTN lines. Inbound audio ingress, causal transcoding, greeting synthesis (~250 ms), full-duplex session loop, and carrier hang-up handling validated across 3 physical mobile phone calls (OV-005).
* **Neural VAD (`omnivoice/vad.py`)**: Local Silero VAD v4 ONNX model running on CPU via ONNX Runtime. Evaluates 32 ms PCM frames with isolated recurrent state per call.
* **Full-Duplex Interruption State Machine (`omnivoice/duplex.py`, `omnivoice/session.py`)**: `FlexDuo` acoustic candidate + transcript validation with backchannel suppression (e.g., *"yeah"*, *"mm hmm"*). Stabilized via ADR-001 with 750 ms bounded continuation coalescing and generation-stage control-intent suppression to prevent false interrupted turns and spurious carrier clears.
* **Carrier Barge-in Clear Dispatch (`omnivoice/transport.py`)**: Transmits `{"event": "clear"}` envelopes to carrier WebSockets to purge pending audio buffers upon true acoustic interruption of active playback.
* **Write Action Safety Gating (`omnivoice/actions.py`)**: Two-phase execution framework (`staged` $\rightarrow$ `armed` $\rightarrow$ `confirm` $\rightarrow$ `committed`). Requires exact match against tenant's configured confirmation phrases. Includes SSRF prevention against private IP addresses.
* **Audio Transcoding & Causal Upsampling (`omnivoice/audio.py`)**: G.711 $\mu$-law decode/encode and stateful 8 kHz to 16 kHz causal linear interpolation.
* **Customer Landing Website (`landing/`)**: Next.js 16 App Router website with Tailwind CSS v4, interactive Web Audio API acoustic synthesis demo, and ROI calculator. Marketing claims, code showcase, indicative pricing, and latency targets reconciled to match verified repository capabilities (OV-004). Premium enterprise visual design overhaul completed with editorial split hero, connected architectural pipeline, high-contrast dark developer console, structured ROI comparison, and light/mint/dark rhythmic sections (OV-022). Deployed live on Vercel at `https://omnivoice-self.vercel.app/`.

### Partial Subsystems
* **Exotel & Twilio Integration**: Inbound Exotel WebSocket media stream is fully validated on physical PSTN lines (OV-005). Outbound dialing endpoint exists (`/api/tenants/{id}/dial`), but call progress analysis (answering machine detection, busy signals) remains unverified. Twilio live PSTN calls remain to be tested.
* **Regional Multilingual Speech**: Supported at the model parameter level (11 Indian language codes accepted by Sarvam TTS and model validators). System prompts, error fallbacks, and write-confirmation prompts remain hardcoded in English (OV-008 planned).
* **Enterprise Operations Console (`omnivoice/static/`)**: Dual-theme UI operational. Historical call details runtime error resolved (OV-002); carrier connection URLs aligned with real FastAPI endpoints (OV-003); call transcripts and turn metrics visible.
* **Observability & Evaluation**: Structured JSON metrics logged upon call completion into SQLite (`data/omnivoice.db`). Turn-level `user_transcript` and `agent_response` persisted. No live distributed tracing or OpenTelemetry instrumentation exists (OV-017 planned).

### Missing Subsystems (Planned / Not Implemented)
* **SaaS Billing & Metering**: Zero call minute accounting, zero payment gateway integration (Razorpay/Stripe), zero tier enforcement. Indicative tiers on landing page qualified as roadmap/pilot estimates.
* **Distributed Architecture**: No Redis or message broker; all active call sessions and WebSocket references reside in process RAM.
* **Production Database**: Uses local SQLite. No PostgreSQL support or database migration tooling (Alembic).
* **Call Audio Storage**: Zero audio recording persistence. Audio is streamed ephemerally in-memory and discarded.
* **Client SDKs**: No standalone Python or npm SDK packages currently exist in the repository; marketing code showcase displays direct REST API integrations (OV-004), and SDK packages remain planned for OV-018.
* **Granular RBAC**: Access control is binary (`admin` vs `tenant_id`). No user accounts, teams, or audit logs.

---

## 3. Known Bugs & Deficiencies

1. ~~**Console Call Session ID TypeError**~~: *(Resolved in OV-002)* In `omnivoice/static/app.js:629`, clicking a call record referenced `call.session_id.slice(...)`. Reconciled to use `(call.id || "").slice(...)` matching the API response schema.
2. ~~**Incorrect Carrier Webhook URL in Console**~~: *(Resolved in OV-003)* In `omnivoice/static/app.js:617`, the connection modal previously displayed a non-existent `/api/webhooks/...` path. Reconciled to fetch carrier-specific configurations from `/api/tenants/{tenant_id}/lines/{line_id}/connection` (`/telephony/twilio/{line_id}` for Twilio and `/ws/exotel/{line_id}/{stream_secret}` for Exotel) using configured `OMNI_PUBLIC_BASE_URL`.
3. ~~**Generation-Stage Turn-Taking Collisions**~~: *(Resolved in OV-005 / ADR-001)* Rapid sequential STT final fragments arriving before agent playback began previously triggered false interrupted turns and spurious carrier clears. Stabilized via bounded continuation coalescing and control-intent suppression.
4. **Voice Synthesis Continuity / Choppiness**: *(Tracked in OV-023)* Sentence-by-sentence TTS synthesis and null-byte frame padding create audible sentence-boundary gaps during multi-sentence responses.
5. **Conversational Limitation Loops**: *(Tracked in OV-024)* Anti-hallucination grounding policy produces repetitive refusal phrasing when callers ask for missing facts (e.g. pricing).
6. **Exotel Token in URL Path**: In `omnivoice/app.py:465`, the streaming secret is passed in the URL path (`/ws/exotel/{line_id}/{token}`), risking exposure in proxy and intermediate gateway access logs.
7. **Database Lock Contention**: In `omnivoice/store.py:48`, all database operations are serialized through a single `asyncio.Lock()`, creating potential event loop latency spikes during concurrent call activity.

---

## 4. Current Deployment State

* **Local Machine**: Fully operational via `start.ps1` on Windows PowerShell and Unix (`uvicorn` on `http://127.0.0.1:8000`).
* **Carrier Gateway**: Live Exotel virtual line (`+914954269065`) connected via Cloudflare WSS quick tunnel.
* **Docker**: `Dockerfile` exists but does not download Silero ONNX weights during image build. Containers launched without mounting `./models` fail readiness checks.
* **Docker Compose**: `compose.yaml` successfully mounts `./data` and `./models:ro`, provided weights are downloaded beforehand.
* **Vercel**: Customer landing page is live at `https://omnivoice-self.vercel.app/`.
* **Backend Cloud Hosting**: Not configured. No cloud manifests, Helm charts, or managed database connections exist.

---

## 5. Current Persistence Architecture

* **Engine**: Local file-based SQLite database via `aiosqlite` (`data/omnivoice.db`).
* **Configuration**: `PRAGMA journal_mode=WAL; PRAGMA foreign_keys=ON;`.
* **Tables**: `tenants`, `knowledge`, `lines`, `tools`, `calls`, `actions`.
* **In-Memory Volatility**: Active call sessions (`services.active`), conversation history (rolling 20 turns), and FAISS vector indices exist strictly in local process memory. A process restart terminates all active calls.

---

## 6. Current Testing Baseline

* **Unit & Streaming Tests**: 40 automated tests passing via `pytest tests/`.
* **Automated Release Gate**: `scripts/verify-dod.ps1` runs 6 deterministic gates (pytest, ruff, Next.js build, browser E2E, git hygiene, and whitespace check).
* **Browser Test**: Playwright E2E script `tests/browser_check.py` validates console login, tenant creation, FAQ addition, line setup, and responsive layout.
* **Model Check**: `tests/model_check.py` validates local Silero ONNX silence processing and FAISS retrieval.
* **Real Telephony Testing**: 3 authentic physical mobile handset calls completed and verified on live PSTN (OV-005).

---

## 7. Current MVP Frontier

The primary MVP technical validation hurdle (real PSTN carriage and turn-taking) is **RESOLVED**. The active engineering priorities are:

1. **Voice Continuity & Natural TTS Pipelining (OV-023)**: Eliminating sentence-boundary choppiness and markdown artifacts to achieve natural spoken cadence.
2. **Natural Dialogue & Graceful Limitation Handling (OV-024)**: Transforming robotic refusals into conversational redirection while preserving factual grounding.
