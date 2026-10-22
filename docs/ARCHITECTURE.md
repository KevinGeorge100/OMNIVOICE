# OmniVoice — Architecture Specification

**Document Version:** 1.1 (OV-033 evidence consolidation)
**Status:** Canonical architectural reference  
**Scope:** Contrasts Current Working Architecture vs. Target Production Architecture  

---

## 1. Current Working Architecture

### Architecture version of record (2026-10-17)

The **implemented single-worker local path** is: caller/carrier → Exotel or Twilio media WebSocket → capacity admission and bounded audio buffers → parallel Silero VAD and STT (Sarvam by default; Gnani optional) → FlexDuo Speak/Listen/Idle and backchannel/barge-in decision → pending-action confirmation check → approved FAQ fast answer or tenant-local lexical/FAISS retrieval → streamed Groq response and bounded ToolRegistry loop (optional read-only MCP reference) → ActionEngine staged/armed/explicit-confirmed local writes → SpeechSegmenter → streaming TTS (Sarvam default; Gnani optional) → carrier-specific PCM/μ-law frames and playback marks/clear → caller. Reads and speculative context may run concurrently; writes cannot bypass confirmation. SQLite stores tenants, knowledge, calls, tools and local sales records. The Operations Console reads local state/telemetry. Optional Langfuse research export runs in a bounded background queue after calls and is not authoritative or on the audio hot path. Provider retry/fallback and call/queue capacity controls bound overload.

This is the code's current capability map, **not** a claim that all variants have physical PSTN validation. OV-005 historically verified Exotel handset conversations; OV-031 validated the newer sales path using local carrier loopback with real Gnani/Groq/Gnani providers, without a phone call. PostgreSQL, Redis, external CRM/calendar, production observability and final Railway deployment remain future or deferred. [Research evidence](research/FINAL_EVIDENCE_INDEX.md) · [metric boundaries](research/FINAL_METRICS_REGISTRY.md).

The KooKoo/Ozonetel adapter is currently **parked on `codex/kookoo-carrier-adapter`**, not merged into this branch or `main`. Its linked SDK describes PCM16 sample arrays on the application WebSocket even though Ozonetel describes PCMU on the SIP leg. It has synthetic coverage but no DID/PSTN acceptance and no verified playback-complete receipt for confirmation-gated writes. See the KooKoo integration note on that branch. The [demo runbook](FINAL_DEMO_RUNBOOK.md) keeps Exotel, KooKoo and loopback evidence separate.

OV-011A inserts `ToolRegistry` between Groq function calls and `ActionEngine`. Its typed definitions include tenant-authorized metadata, strict JSON input and bounded output conventions. A read capability can invoke a local handler, the existing administrator-owned HTTPS read adapter, or an explicitly allowed MCP read. A write definition has no direct handler: the registry stages it through `ActionEngine`, whose persisted, playback-armed and caller-confirmed lifecycle remains the sole commit path. The official MCP 2.3.0 adapter currently connects only to a bundled in-process read-only reference server when opted in; it is a protocol integration proof, not an external business connector. The model/tool loop has a configurable limit and returns structured tool-role results. Tool events exclude arguments and result payloads.

OV-011B extends the baseline architecture with local SQLite sales handlers. `lookup_lead` and `check_demo_slots` are read tools; `schedule_demo` and `create_followup` are local writes routed through the same persisted ActionEngine lifecycle. A call-scoped, bounded selection state holds the resolved lead and last offered slots; the model cannot submit an arbitrary lead/slot pair for staging. Confirmation claims the action once; booking then conditionally changes an available tenant slot to booked and inserts a booking in one transaction. A stale or competing reservation returns a definite failure. The local evaluation is scripted orchestration, not measured LLM selection.

OV-029 adds an opt-in research observation adapter. The offline sales evaluation can emit synthetic case, tool, and confirmation observations to Langfuse. Completed live calls enqueue an allowlisted numeric projection after persistence; a 64-item process-local background queue isolates export from real-time media. The adapter sends no transcripts, caller or tenant identifiers, audio, prompts, knowledge text, or tool arguments. It is not the production distributed tracing design tracked by OV-017, and its post-call observation durations do not reconstruct original turn durations.

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
                         │    Silero VAD (ONNX)        │       │   Sarvam / Gnani STT       │
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
                         │   - Configured model       │                      │
                         │   - Sentence Punctuation    │                      │
                         └──────────────┬──────────────┘                      │
                                        │ (Streamed Sentences)                │
                                        └──────────────┬──────────────────────┘
                                                       │
                                                       ▼
                                       ┌─────────────────────────────────────────┐
                                       │       Sarvam / Gnani TTS Provider       │
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
3. **Dual Concurrency Queues**: Decoded 16 kHz PCM is placed into bounded VAD and provider-audio queues with the OV-010 32-packet / 32,000-byte backlog ceiling and overload teardown.
4. **Silero Neural VAD (`omnivoice/vad.py`)**:
   * Runs local ONNX model `models/silero_vad.onnx` using CPUExecutionProvider.
   * Processes 1024-byte (512-sample / 32 ms) frames, tracking recurrent hidden states per call.
5. **STT Providers (`omnivoice/providers.py`)**:
   * Bounded audio frames are streamed via WebSocket to Sarvam AI (`wss://api.sarvam.ai/speech-to-text-realtime/ws`).
   * Emits partial and final transcript events.
   * Gnani Prisma is an optional utterance-buffered STT adapter; Sarvam remains the default.
6. **Full-Duplex Decision Engine (`omnivoice/duplex.py`)**:
   * `FlexDuo` state machine evaluates acoustic probability and incoming transcripts.
   * Suppresses interruption for recognized backchannel words (*"yeah"*, *"mm hmm"*, *"ok"*).
   * Triggers barge-in cancellation when genuine speech is confirmed.
7. **RAG & Fast-Path Retrieval (`omnivoice/rag.py`)**:
   * Evaluates exact match against approved FAQs (response time $<10\text{ ms}$).
   * Searches in-memory `faiss.IndexFlatIP` across 1000-character document chunks.
8. **Groq LLM Reasoning (`omnivoice/providers.py`)**:
   * Sends conversation history and grounded context to the configured `groq_model` (default `llama-3.1-8b-instant`; OV-030/031 used `openai/gpt-oss-20b`).
   * Preserves the raw answer for transcripts while a deterministic speech normalizer removes visual Markdown and symbols before TTS.
   * Streams useful phrases with punctuation and minimum length thresholds; the first phrase can begin before the full answer exists.
9. **TTS Providers (`omnivoice/providers.py`)**:
   * Sends adjacent phrases as text chunks on one Sarvam TTS WebSocket (`wss://api.sarvam.ai/text-to-speech/ws`) and flushes once at the end of the utterance.
   * The provider's configured minimum buffer can begin synthesis before the final flush; audio reception and text production run concurrently.
   * Operates an active socket and a warm standby socket to allow instantaneous turn cancellation without socket renegotiation.
   * Gnani Timbre is an optional streaming TTS adapter with the same carrier-framing boundary; Sarvam remains the default.
10. **Carrier Playback Egress (`omnivoice/transport.py`)**:
   * Accumulates 8 kHz linear PCM across provider chunks and phrases; Exotel sends 3200-byte PCM frames, while Twilio sends 320-byte PCM frames encoded as 160-byte G.711 mu-law payloads. Only the final incomplete utterance frame is padded.
   * Sends playback marks to synchronize write-action arming.
   * Sends `{"event": "clear"}` envelopes upon interruption to clear carrier audio buffers.
   * Cancellation discards unsent PCM and text for that generation; generation-stage supersession remains distinct from playback interruption (ADR-001).

OV-023 continuity changes have deterministic local tests. Their effect on audible cadence, physical first-audio latency and barge-in timing still requires a real PSTN comparison; server TTFA is not a physical mouth-to-ear measurement.

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
