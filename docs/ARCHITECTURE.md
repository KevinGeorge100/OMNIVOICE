# OmniVoice — Architecture Specification

**Document Version:** 1.0  
**Status:** Canonical architectural reference  
**Scope:** Contrasts Current Working Architecture vs. Target Production Architecture  

---

## 1. Current Working Architecture

OmniVoice is currently implemented as a **stateful, single-worker asynchronous voice application** running on Python 3.11 with FastAPI and Uvicorn.

```text
                                 ┌─────────────────────────────────────────────────────────────┐
                                 │                   PSTN TELEPHONY CARRIERS                   │
                                 │                 [Exotel]            [Twilio]                │
                                 └────────────────────┬───────────────────┬────────────────────┘
                                                      │ (8kHz Linear PCM) │ (8kHz G.711 u-law)
                                                      ▼                   ▼
                                       ┌─────────────────────────────────────────┐
                                       │     FastAPI WebSocket Media Ingress     │
                                       │  (/ws/exotel/{id}/{token} | /ws/twilio) │
                                       └────────────────────┬────────────────────┘
                                                            │
                                                            ▼
                                       ┌─────────────────────────────────────────┐
                                       │       omnivoice.transport / audio       │
                                       │  - G.711 Decode / Frame Alignment       │
                                       │  - Upsample8k (8kHz -> 16kHz Causal)    │
                                       └─────────────┬───────────────────┬───────┘
                                                     │                   │
                                    (16kHz Audio)    │                   │ (16kHz Audio)
                                                     ▼                   ▼
                         ┌─────────────────────────────┐       ┌─────────────────────────────┐
                         │    Silero VAD v4 (ONNX)     │       │     Sarvam STT Provider     │
                         │    - 32ms Frame Inference   │       │   - Persistent WebSocket    │
                         │    - Recurrent Call State   │       │   - Partial & Final Events  │
                         └──────────────┬──────────────┘       └──────────────┬──────────────┘
                                        │ (Prob >= 0.6)                       │ (Transcripts)
                                        └──────────────┐       ┌──────────────┘
                                                       ▼       ▼
                                       ┌─────────────────────────────────────────┐
                                       │            FlexDuo (FSM)                │
                                       │  - Listen / Speak / Idle Logic          │
                                       │  - Backchannel Filter ("yeah","ok")     │
                                       │  - Confirmed Barge-in -> Send Clear     │
                                       └────────────────────┬────────────────────┘
                                                            │ (Final Transcript)
                                                            ▼
                                       ┌─────────────────────────────────────────┐
                                       │       omnivoice.session.CallSession     │
                                       │  1. Check Pending Action Confirmation   │
                                       │  2. Knowledge.fast_answer() [Exact FAQ] │
                                       └─────────────┬───────────────────┬───────┘
                                                     │                   │
                                      (Cache Miss)   ▼                   ▼  (Exact Match / <10ms)
                         ┌─────────────────────────────┐       ┌─────────────────────────────┐
                         │   In-Memory FAISS Index     │       │     Direct FAQ Playback     │
                         │   - Sentence-Transformers   │       └──────────────┬──────────────┘
                         │   - Multilingual MiniLM-L12 │                      │
                         └──────────────┬──────────────┘                      │
                                        │ (Retrieved Context)                 │
                                        ▼                                     │
                         ┌─────────────────────────────┐                      │
                         │     Groq LLM Provider       │                      │
                         │   - Llama-3.1-8b-instant    │                      │
                         │   - Sentence Punctuation    │                      │
                         └──────────────┬──────────────┘                      │
                                        │ (Streamed Sentences)                │
                                        └──────────────┬──────────────────────┘
                                                       │
                                                       ▼
                                       ┌─────────────────────────────────────────┐
                                       │          Sarvam TTS Provider            │
                                       │   - Dual WSS (Active + Warm Standby)    │
                                       │   - 8kHz Linear PCM Stream              │
                                       └────────────────────┬────────────────────┘
                                                            │ (8kHz Output PCM)
                                                            ▼
                                       ┌─────────────────────────────────────────┐
                                       │            Carrier Egress               │
                                       │   - Media framing (3200B / 320B)        │
                                       │   - Playback Marks & Clear Signals      │
                                       └─────────────────────────────────────────┘
```

### 1.1 Real Audio Pipeline
1. **PSTN Ingress**: Exotel or Twilio streams inbound call audio over WebSocket connections to FastAPI.
2. **Decoding & Upsampling (`omnivoice/audio.py`)**:
   * Twilio 8 kHz $\mu$-law payloads are decoded to 16-bit linear PCM.
   * Exotel 8 kHz 16-bit PCM payloads are validated directly.
   * Audio is upsampled from 8 kHz to 16 kHz using `Upsample8k`, a causal linear interpolation algorithm carrying the preceding sample across packet boundaries.
3. **Dual Concurrency Queues**: Decoded 16 kHz PCM is placed into two bounded queues: `vad_queue` (maxsize=100) and `audio_queue` (maxsize=100).
4. **Silero Neural VAD (`omnivoice/vad.py`)**:
   * Runs local ONNX model `models/silero_vad.onnx` using CPUExecutionProvider.
   * Processes 1024-byte (512-sample / 32 ms) frames, tracking recurrent hidden states per call.
5. **Sarvam STT Streaming (`omnivoice/providers.py`)**:
   * Bounded audio frames are streamed via WebSocket to Sarvam AI (`wss://api.sarvam.ai/speech-to-text-realtime/ws`).
   * Emits partial and final transcript events.
6. **Full-Duplex Decision Engine (`omnivoice/duplex.py`)**:
   * `FlexDuo` state machine evaluates acoustic probability and incoming transcripts.
   * Suppresses interruption for recognized backchannel words (*"yeah"*, *"mm hmm"*, *"ok"*).
   * Triggers barge-in cancellation when genuine speech is confirmed.
7. **RAG & Fast-Path Retrieval (`omnivoice/rag.py`)**:
   * Evaluates exact match against approved FAQs (response time $<10\text{ ms}$).
   * Searches in-memory `faiss.IndexFlatIP` across 1000-character document chunks.
8. **Groq LLM Reasoning (`omnivoice/providers.py`)**:
   * Sends conversation history and grounded context to `llama-3.1-8b-instant`.
   * Buffers streaming tokens and splits text into discrete sentences upon punctuation (`[.!?।]\s`).
9. **Sarvam TTS Synthesis (`omnivoice/providers.py`)**:
   * Dispatches sentences to Sarvam TTS WebSocket (`wss://api.sarvam.ai/text-to-speech/ws`).
   * Operates an active socket and a warm standby socket to allow instantaneous turn cancellation without socket renegotiation.
10. **Carrier Playback Egress (`omnivoice/transport.py`)**:
    * Frames linear PCM into carrier-specific chunks (3200 bytes for Exotel, 320 bytes for Twilio).
    * Sends playback marks to synchronize write-action arming.
    * Sends `{"event": "clear"}` envelopes upon interruption to clear carrier audio buffers.

### 1.2 Persistence & In-Memory State
* **Local SQLite Store (`omnivoice/store.py`)**:
  * Single file `data/omnivoice.db` in WAL mode (`PRAGMA journal_mode=WAL;`).
  * Operations are serialized through an in-process `asyncio.Lock()`.
  * Schema manages `tenants`, `knowledge`, `lines`, `tools`, `calls`, and `actions`.
* **Process-Local Call Sessions (`omnivoice/session.py`)**:
  * Active calls are stored in a local dictionary `services.active = {}`.
  * Conversation history is stored in process memory (`CallSession.history`, rolling 20 turns).
  * Not shared across processes or machines.
* **In-Memory FAISS (`omnivoice/rag.py`)**:
  * Vector matrices are built dynamically in RAM on tenant knowledge refresh.
  * Indices are not serialized to disk; they are rebuilt upon worker startup.
* **Enterprise Action Engine (`omnivoice/actions.py`)**:
  * Preflight verification (`validate_public_url`) restricts tool endpoints to public HTTPS on port 443.
  * Two-phase commit: tool is `staged`, `armed` after audio mark playback, and `committed` only after the caller speaks an exact matching confirmation phrase.
* **Tenant Isolation**:
  * Enforced via SQLite foreign keys and FastAPI route dependencies (`tenant_access`).
* **Frontends**:
  * **Operations Console (`omnivoice/static/`)**: Vanilla HTML5/CSS3/JavaScript SPA served directly by FastAPI at `/` and `/static`.
  * **Landing Website (`landing/`)**: Next.js 16 App Router application deployed separately on Vercel.

---

## 2. Target Production Architecture (PLANNED / FUTURE)

> [!CAUTION]
> Everything in this section represents **TARGET / PLANNED** architecture for future scaling phases.
> None of the following components are currently implemented in the codebase.

```text
                                  ┌────────────────────────┐
                                  │      Cloud PSTN        │
                                  │   (Exotel / Twilio)    │
                                  └───────────┬────────────┘
                                              │ WSS (Encrypted SIP Media)
                                              ▼
                                  ┌────────────────────────┐
                                  │   Cloud Load Balancer  │
                                  │   (AWS ALB / GCP LB)   │
                                  └───────────┬────────────┘
                                              │ Sticky Session / WSS
                                              ▼
                       ┌──────────────────────────────────────────────┐
                       │       Distributed Voice Media Pods           │
                       │   - FastAPI Audio Workers (Horizontally Scaled)
                       │   - Silero VAD Local ONNX                    │
                       └──────────────┬──────────────┬────────────────┘
                                      │              │
                   ┌──────────────────┘              └──────────────────┐
                   ▼                                                    ▼
    ┌─────────────────────────────┐                      ┌─────────────────────────────┐
    │     Redis Cluster [PLANNED] │                      │  Managed PostgreSQL [PLANNED│
    │  - Distributed Session Hub  │                      │  - Multi-tenant Data Store  │
    │  - Call Pub/Sub & Marks     │                      │  - Call Records & Audit Logs│
    │  - Rate Limiting & Quotas   │                      │  - Vector Store (pgvector)  │
    └─────────────────────────────┘                      └─────────────────────────────┘
                   ▲                                                    ▲
                   │                                                    │
    ┌──────────────┴──────────────┐                      ┌──────────────┴──────────────┐
    │ Cloud Object Store [PLANNED]│                      │   Billing & SaaS [PLANNED]  │
    │  - S3 / GCS Audio Archive   │                      │  - Razorpay / Stripe Engine │
    │  - Raw Document PDFs        │                      │  - Minute-by-minute Metering│
    └─────────────────────────────┘                      └─────────────────────────────┘
```

### 2.1 Planned Architectural Transitions
1. **Database Layer (TARGET / PLANNED)**:
   * Replace local SQLite with **PostgreSQL** using `asyncpg` and connection pooling.
   * Manage schema migrations using **Alembic**.
   * Replace in-memory FAISS with **pgvector** or managed vector indexing to allow cross-worker retrieval consistency.
2. **Session & Concurrency Layer (TARGET / PLANNED)**:
   * Introduce **Redis** for distributed state management, live call registry, and carrier webhook routing.
   * Implement sticky WebSocket session routing via an external ingress controller (Envoy / Traefik / NGINX).
3. **Storage & Recording Layer (TARGET / PLANNED)**:
   * Introduce cloud object storage (Amazon S3 / Google Cloud Storage) for tenant-uploaded documents and compliance call recordings.
4. **SaaS Infrastructure (TARGET / PLANNED)**:
   * Implement a dedicated metering engine tracking billed call seconds.
   * Integrate webhook-driven payment processing via **Razorpay** (India) and **Stripe** (International).
   * Implement granular Role-Based Access Control (RBAC) with organization invites and audit logging.
5. **Observability Layer (TARGET / PLANNED)**:
   * Export OpenTelemetry distributed traces to a collector (Datadog / Prometheus / Grafana Tempo).
   * Emit structured metrics for mouth-to-ear latency, carrier jitter, and VAD false-interruption rates.
