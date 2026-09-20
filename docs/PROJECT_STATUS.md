# OmniVoice — Project Status

**Current Maturity Level:** **FUNCTIONAL PROTOTYPE — advancing toward MVP**  
**Document Status:** Living reality baseline  
**Last Updated:** 2026-09-20  

---

## 1. Executive Summary & Reality Statement

> [!IMPORTANT]
> **The project has not yet completed a validated real PSTN end-to-end telephone conversation.**
> All telephony validations performed to date have utilized local HTTP/WebSocket test harnesses, synthetic mock sockets, and isolated audio replay files. Real-world mouth-to-ear latency, cellular carrier jitter, and ambient acoustic interruption on live phone lines remain unverified.

OmniVoice is currently an **asynchronous, single-worker Python 3.11 voice application and media server**. It demonstrates a working integration between telephony WebSockets (Exotel/Twilio) and AI cloud providers (Sarvam AI for regional STT/TTS, Groq for Llama-3 LLM reasoning). It features a local neural VAD (Silero ONNX), an in-memory document vector index (FAISS), and an embedded administrative console.

---

## 2. Subsystem Status Matrix

### Working Subsystems (Verified in Local Test Environment)
* **Neural VAD (`omnivoice/vad.py`)**: Local Silero VAD v4 ONNX model running on CPU via ONNX Runtime. Evaluates 32 ms PCM frames with isolated recurrent state per call.
* **Full-Duplex Interruption State Machine (`omnivoice/duplex.py`)**: `FlexDuo` acoustic candidate + transcript validation with backchannel suppression (e.g., *"yeah"*, *"mm hmm"*).
* **Carrier Barge-in Clear Dispatch (`omnivoice/transport.py`)**: Transmits `{"event": "clear"}` envelopes to carrier WebSockets to purge pending audio buffers upon interruption.
* **Write Action Safety Gating (`omnivoice/actions.py`)**: Two-phase execution framework (`staged` $\rightarrow$ `armed` $\rightarrow$ `confirm` $\rightarrow$ `committed`). Requires exact match against tenant's configured confirmation phrases. Includes SSRF prevention against private IP addresses.
* **Audio Transcoding & Causal Upsampling (`omnivoice/audio.py`)**: G.711 $\mu$-law decode/encode and stateful 8 kHz to 16 kHz causal linear interpolation.
* **Customer Landing Website (`landing/`)**: Next.js 16 App Router website with Tailwind CSS v4, interactive Web Audio API acoustic synthesis demo, and ROI calculator. Deployed live on Vercel at `https://omnivoice-self.vercel.app/`.

### Partial Subsystems
* **Exotel & Twilio Integration**: Inbound webhook handshakes and WebSocket media loops are implemented. Outbound dialing endpoint exists (`/api/tenants/{id}/dial`), but call progress analysis (answering machine detection, busy signals) is not implemented.
* **Regional Multilingual Speech**: Supported at the model parameter level (11 Indian language codes accepted by Sarvam TTS and model validators). However, system prompts, error fallbacks, and write-confirmation prompts remain hardcoded in English.
* **Enterprise Operations Console (`omnivoice/static/`)**: Dual-theme UI operational. However, bugs exist in call transcript inspection and webhook connection modal URL display.
* **Observability & Evaluation**: Structured JSON metrics logged upon call completion. Offline evaluation script calculates WER and TTFA percentiles from supplied JSONL files. No live distributed tracing or OpenTelemetry instrumentation exists.

### Missing Subsystems (Planned / Not Implemented)
* **SaaS Billing & Metering**: Zero call minute accounting, zero payment gateway integration (Razorpay/Stripe), zero tier enforcement.
* **Distributed Architecture**: No Redis or message broker; all active call sessions and WebSocket references reside in process RAM.
* **Production Database**: Uses local SQLite. No PostgreSQL support or database migration tooling (Alembic).
* **Call Audio Storage**: Zero audio recording persistence. Audio is streamed ephemerally in-memory and discarded.
* **Client SDKs**: The Python `Client` and TypeScript `@omnivoice/sdk` shown on the marketing site do not exist in the repository.
* **Granular RBAC**: Access control is binary (`admin` vs `tenant_id`). No user accounts, teams, or audit logs.

---

## 3. Known Bugs & Deficiencies

1. ~~**Console Call Session ID TypeError**~~: *(Resolved in OV-002)* In `omnivoice/static/app.js:629`, clicking a call record referenced `call.session_id.slice(...)`. Reconciled to use `(call.id || "").slice(...)` matching the API response schema.
2. **Incorrect Carrier Webhook URL in Console**: In `omnivoice/static/app.js:617`, the connection modal displays a non-existent URL (`/api/webhooks/${line.provider}/${line.id}`). The real endpoints are `/telephony/twilio/{line_id}` and `/ws/exotel/{line_id}/{token}`.
3. **Exotel Token in URL Path**: In `omnivoice/app.py:465`, the streaming secret is passed in the URL path (`/ws/exotel/{line_id}/{token}`), risking exposure in proxy and intermediate gateway access logs.
4. **Database Lock Contention**: In `omnivoice/store.py:48`, all database operations are serialized through a single `asyncio.Lock()`, creating potential event loop latency spikes during concurrent call activity.

---

## 4. Current Deployment State

* **Local Machine**: Fully operational via `start.ps1` on Windows PowerShell and Unix (`uvicorn` on `http://127.0.0.1:8000`).
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

* **Unit & Streaming Tests**: 26 automated tests passing via `pytest tests/`.
* **Browser Test**: Playwright E2E script `tests/browser_check.py` validates console login, tenant creation, FAQ addition, line setup, and responsive layout.
* **Model Check**: `tests/model_check.py` validates local Silero ONNX silence processing and FAISS retrieval.
* **Testing Reality**: All 26 tests use mocks for external cloud providers (Sarvam and Groq) or run against synthetic in-memory fixtures. No live network call has been executed within automated CI.

---

## 7. Current MVP Blocker

The singular critical blocker preventing transition from **Functional Prototype** to **Minimum Viable Product (MVP)** is:

> **Execution and validation of an authentic PSTN telephone call over a live carrier network (Exotel or Twilio), verifying that caller speech triggers audible AI speech with acceptable latency (<1000 ms real-world) and stable barge-in interruption.**
