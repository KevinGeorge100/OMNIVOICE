# OmniVoice — Engineering Backlog

**Document Status:** Canonical backlog tracker  
**Status Key:** `Planned` | `In Progress` | `Blocked` | `Done`  
**Priority Key:** `P0` (Critical) | `P1` (High) | `P2` (Medium) | `P3` (Low)  

---

## Backlog Index

| ID | Title | Type | Priority | Status |
| :--- | :--- | :--- | :--- | :--- |
| **OV-001** | Establish OmniVoice Engineering Project Control | Task | P0 | **Done** |
| **OV-002** | Fix Console Call Details TypeError (`call.session_id`) | Bug | P0 | Planned |
| **OV-003** | Fix Carrier Webhook URL Display in Console Modal | Bug | P0 | Planned |
| **OV-004** | Audit & Reconcile Landing Page Marketing Claims | TechDebt | P1 | Planned |
| **OV-005** | Real PSTN End-to-End Telephone Validation Test | Spike | P0 | Planned |
| **OV-006** | Instrument & Record Real-World Mouth-to-Ear Latency | Task | P1 | Planned |
| **OV-007** | Real Acoustic Barge-in & Background Noise Rehearsal | Task | P1 | Planned |
| **OV-008** | Real Multilingual Telephone Turn Verification | Task | P1 | Planned |
| **OV-009** | Upstream Provider Disconnect & Recovery Handlers | Feature | P1 | Planned |
| **OV-010** | LLM & STT Rate-Limit Handling & Graceful Backoff | Feature | P1 | Planned |
| **OV-011** | Database Migration Framework (Alembic) | TechDebt | P2 | Planned |
| **OV-012** | Relational Database Migration (SQLite to PostgreSQL) | Feature | P2 | Planned |
| **OV-013** | Distributed Session Registry & State Hub (Redis) | Architecture | P2 | Planned |
| **OV-014** | Call Second Metering & Quota Enforcement Engine | Feature | P2 | Planned |
| **OV-015** | SaaS Subscription Billing Integration (Razorpay/Stripe) | Feature | P3 | Planned |
| **OV-016** | Backend Production Cloud Container Deployment | Devops | P2 | Planned |
| **OV-017** | Production Observability & OpenTelemetry Tracing | Feature | P2 | Planned |
| **OV-018** | Reconcile SDK Discrepancy (Build Python & TS SDKs) | Feature | P3 | Planned |
| **OV-019** | Granular Multi-Tenant Role-Based Access Control | Security | P3 | Planned |
| **OV-020** | Exotel WebSocket Token Query-to-Header Migration | Security | P2 | Planned |

---

## Detailed Backlog Items

### [OV-001] Establish OmniVoice Engineering Project Control
* **Type:** Task
* **Priority:** P0
* **Status:** **Done**
* **Dependencies:** None
* **Description:** Establish project governance, audit-based reality documentation, phased roadmaps, strict definition of done, and AI agent execution rules.
* **Acceptance Criteria:**
  1. `PROJECT_STATUS.md`, `ROADMAP.md`, `ARCHITECTURE.md`, `DEFINITION_OF_DONE.md`, and `BACKLOG.md` created.
  2. Architecture Decision Record system initialized in `docs/adr/README.md`.
  3. AI workflow rules established in `.agents/rules/`.
  4. No application code modified.

---

### [OV-002] Fix Console Call Details TypeError (`call.session_id`)
* **Type:** Bug
* **Priority:** P0
* **Status:** Planned
* **Dependencies:** OV-001
* **Description:** In `omnivoice/static/app.js:629`, clicking a call record causes an unhandled JavaScript exception because it references `call.session_id` instead of `call.id`.
* **Acceptance Criteria:**
  1. Replace `call.session_id` with `call.id` in `app.js`.
  2. Safe fallback when turns array is empty or undefined.
  3. Browser E2E check verifies clicking a call row opens the modal without console errors.

---

### [OV-003] Fix Carrier Webhook URL Display in Console Modal
* **Type:** Bug
* **Priority:** P0
* **Status:** Planned
* **Dependencies:** OV-001
* **Description:** In `omnivoice/static/app.js:617`, the connection modal displays `${window.location.origin}/api/webhooks/${line.provider}/${line.id}` which does not exist in FastAPI routes.
* **Acceptance Criteria:**
  1. Update connection modal to fetch real URLs from `/api/tenants/{tenant_id}/lines/{line_id}/connection`.
  2. Twilio lines display `/telephony/twilio/{line_id}`.
  3. Exotel lines display `/ws/exotel/{line_id}/{token}`.

---

### [OV-004] Audit & Reconcile Landing Page Marketing Claims
* **Type:** TechDebt
* **Priority:** P1
* **Status:** Planned
* **Dependencies:** OV-001
* **Description:** Reconcile unsupported claims on `landing/` (such as published SDKs, SLA guarantees, and pricing tiers) so that marketing copy clearly distinguishes between current capabilities and enterprise roadmap offerings.
* **Acceptance Criteria:**
  1. Code showcase clarifies that SDK snippets represent upcoming client libraries.
  2. SLA and compliance badges labeled as enterprise deployment capabilities.
  3. All CTA links point to functional destinations.

---

### [OV-005] Real PSTN End-to-End Telephone Validation Test
* **Type:** Spike
* **Priority:** P0
* **Status:** Planned
* **Dependencies:** OV-002, OV-003
* **Description:** Place an authentic telephone call from a mobile handset over a carrier network (Exotel or Twilio) through an HTTPS/WSS tunnel to the OmniVoice engine.
* **Acceptance Criteria:**
  1. Real phone call connects and plays greeting within 1500 ms of answer.
  2. Caller speech is transcribed and answered by AI with grounded context.
  3. Call audio is clean without carrier packet underruns.
  4. Complete call record and turn metrics logged in SQLite.

---

### [OV-006] Instrument & Record Real-World Mouth-to-Ear Latency
* **Type:** Task
* **Priority:** P1
* **Status:** Planned
* **Dependencies:** OV-005
* **Description:** Measure and record acoustic mouth-to-ear latency across 50+ real PSTN dialogue turns to establish an empirical baseline.
* **Acceptance Criteria:**
  1. Record p50, p95, and p99 mouth-to-ear latency on real phone lines.
  2. Isolate carrier network transit time from engine processing time.
  3. Document findings in `docs/EVALUATION.md`.

---

### [OV-007] Real Acoustic Barge-in & Background Noise Rehearsal
* **Type:** Task
* **Priority:** P1
* **Status:** Planned
* **Dependencies:** OV-005
* **Description:** Test the `FlexDuo` full-duplex engine under authentic cellular noise conditions (traffic, indoor reverberation, coughing, spoken backchannels).
* **Acceptance Criteria:**
  1. Verify backchannels ("yeah", "ok") do not clear agent speech.
  2. Verify genuine spoken interruption stops agent speech within 500 ms audible time.
  3. Calculate false-interruption and missed-interruption rates.

---

### [OV-008] Real Multilingual Telephone Turn Verification
* **Type:** Task
* **Priority:** P1
* **Status:** Planned
* **Dependencies:** OV-005
* **Description:** Validate live telephony conversations in Hindi (`hi-IN`) and English (`en-IN`), confirming prompt localization and regional pronunciation.
* **Acceptance Criteria:**
  1. Native Hindi speech transcribed accurately by Sarvam STT.
  2. Grounded answers synthesized naturally via Sarvam TTS `shubh` voice.
  3. Confirmation gating phrases operate in native Hindi script and transliteration.

---

### [OV-009] Upstream Provider Disconnect & Recovery Handlers
* **Type:** Feature
* **Priority:** P1
* **Status:** Planned
* **Dependencies:** OV-005
* **Description:** Implement resilient reconnection loops for Sarvam STT WebSocket dropouts and TTS socket failures mid-call.
* **Acceptance Criteria:**
  1. STT socket reconnects automatically within 500 ms if dropped.
  2. Active call is preserved during brief provider hiccups.
  3. If unrecoverable, caller hears a polite apology before call is hung up.

---

### [OV-010] LLM & STT Rate-Limit Handling & Graceful Backoff
* **Type:** Feature
* **Priority:** P1
* **Status:** Planned
* **Dependencies:** OV-009
* **Description:** Handle Groq HTTP 429 rate-limiting and Sarvam quota exhaustion with exponential backoff and fallback responses.
* **Acceptance Criteria:**
  1. Intercept HTTP 429 and retry with jitter up to 2 times.
  2. Fallback to approved FAQ answers when LLM is unavailable.
  3. Log rate-limit events into call metrics JSON.

---

### [OV-011] Database Migration Framework (Alembic)
* **Type:** TechDebt
* **Priority:** P2
* **Status:** Planned
* **Dependencies:** OV-001
* **Description:** Introduce Alembic to manage database schema evolution declaratively instead of raw string scripts in `store.py`.
* **Acceptance Criteria:**
  1. Alembic initialized with initial migration matching current SQLite schema.
  2. Automated test validates upgrade and downgrade paths.

---

### [OV-012] Relational Database Migration (SQLite to PostgreSQL)
* **Type:** Feature
* **Priority:** P2
* **Status:** Planned
* **Dependencies:** OV-011
* **Description:** Migrate storage layer from local SQLite to PostgreSQL using `asyncpg` with connection pooling, removing the global `asyncio.Lock()` bottleneck.
* **Acceptance Criteria:**
  1. `Store` class abstracted to support PostgreSQL.
  2. Connection pooling configured with configurable pool size.
  3. All 26 tests passing against PostgreSQL test container.

---

### [OV-013] Distributed Session Registry & State Hub (Redis)
* **Type:** Architecture
* **Priority:** P2
* **Status:** Planned
* **Dependencies:** OV-012
* **Description:** Decouple active call sessions from local Python process memory by introducing Redis for call registration, active marks, and cross-worker pub/sub.
* **Acceptance Criteria:**
  1. Active call metadata published to Redis key-value store with TTL.
  2. Multiple Uvicorn workers can query active calls across instances.

---

### [OV-014] Call Second Metering & Quota Enforcement Engine
* **Type:** Feature
* **Priority:** P2
* **Status:** Planned
* **Dependencies:** OV-012
* **Description:** Track billable call duration down to the second per tenant, enforcing monthly minute quotas.
* **Acceptance Criteria:**
  1. `call_usage` records created with exact start and end timestamps.
  2. Outbound/inbound calls blocked with 1013 code when tenant quota is exhausted.

---

### [OV-015] SaaS Subscription Billing Integration (Razorpay/Stripe)
* **Type:** Feature
* **Priority:** P3
* **Status:** Planned
* **Dependencies:** OV-014
* **Description:** Implement subscription plans, payment checkout links, and automatic minute allotment upon webhook confirmation.
* **Acceptance Criteria:**
  1. Razorpay subscription webhook handler updates tenant plan.
  2. Invoices and payment history viewable in console.

---

### [OV-016] Backend Production Cloud Container Deployment
* **Type:** Devops
* **Priority:** P2
* **Status:** Planned
* **Dependencies:** OV-005, OV-012
* **Description:** Package and deploy the backend container to a managed cloud environment (e.g. Render / AWS ECS / Koyeb) with automated model downloading at build time.
* **Acceptance Criteria:**
  1. Dockerfile builds Silero model directly into image.
  2. Cloud health probe passes on `/healthz` and `/readyz`.
  3. Public HTTPS/WSS origin linked to carrier dashboards.

---

### [OV-017] Production Observability & OpenTelemetry Tracing
* **Type:** Feature
* **Priority:** P2
* **Status:** Planned
* **Dependencies:** OV-016
* **Description:** Instrument call pipelines with OpenTelemetry spans tracking audio arrival, VAD decision, STT event, RAG latency, LLM TTFT, and TTS TTFA.
* **Acceptance Criteria:**
  1. Distributed spans exported to OTLP collector.
  2. Prometheus metrics endpoint for active calls and turn latencies.

---

### [OV-018] Reconcile SDK Discrepancy (Build Python & TS SDKs)
* **Type:** Feature
* **Priority:** P3
* **Status:** Planned
* **Dependencies:** OV-012
* **Description:** Create real, tested Python and TypeScript client SDK libraries matching the examples on the marketing website.
* **Acceptance Criteria:**
  1. Python `omnivoice-sdk` package with typed API client.
  2. TypeScript `@omnivoice/sdk` published or structured in monorepo.
  3. Automated integration tests validating SDK against REST endpoints.

---

### [OV-019] Granular Multi-Tenant Role-Based Access Control
* **Type:** Security
* **Priority:** P3
* **Status:** Planned
* **Dependencies:** OV-012
* **Description:** Upgrade binary admin/tenant tokens to an organization membership model with roles (Owner, Admin, Operator, Viewer).
* **Acceptance Criteria:**
  1. User accounts with hashed passwords and session cookies/JWTs.
  2. Scoped permissions on tool registration and document uploads.

---

### [OV-020] Exotel WebSocket Token Query-to-Header Migration
* **Type:** Security
* **Priority:** P2
* **Status:** Planned
* **Dependencies:** OV-003
* **Description:** Migrate Exotel stream secrets from URL path parameters to secure header/ticket exchange to prevent credential leakage in proxy access logs.
* **Acceptance Criteria:**
  1. Single-use short-lived ticket generated for carrier connection.
  2. URL path no longer exposes permanent stream secrets.
