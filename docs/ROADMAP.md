# OmniVoice — Strategic Engineering Roadmap

**Document Status:** Living roadmap  
**Planning Mode:** Dependency-ordered phases (No speculative completion dates)  

---

## Roadmap Overview

```text
┌────────────────────────────────────────────────────────┐
│  PHASE 0: Project Control & Truthfulness               │
│  - Engineering governance & project truth baselines    │
│  - Console bug fixes & landing page audit              │
└───────────────────────────┬────────────────────────────┘
                            ▼
┌────────────────────────────────────────────────────────┐
│  PHASE 1: Real PSTN MVP Validation                     │
│  - Live Exotel/Twilio telephone rehearsal              │
│  - Real-world mouth-to-ear latency measurement         │
│  - Acoustic barge-in & multilingual validation         │
└───────────────────────────┬────────────────────────────┘
                            ▼
┌────────────────────────────────────────────────────────┐
│  PHASE 2: Reliability & Provider Resilience            │
│  - Upstream provider disconnect recovery & fallbacks   │
│  - Groq & Sarvam rate-limiting & backoff handlers      │
│  - Structured error reporting & call recovery          │
└───────────────────────────┬────────────────────────────┘
                            ▼
┌────────────────────────────────────────────────────────┐
│  PHASE 3: Production Data Architecture                 │
│  - PostgreSQL migration & Alembic schema management    │
│  - Redis distributed state & session hub               │
│  - Persistent pgvector indexing & S3 document storage  │
└───────────────────────────┬────────────────────────────┘
                            ▼
┌────────────────────────────────────────────────────────┐
│  PHASE 4: SaaS Platform Capabilities                   │
│  - Minute-level usage metering & billing (Razorpay)    │
│  - Granular RBAC, organization teams & audit logs      │
│  - Verified Python & TypeScript Client SDKs            │
└───────────────────────────┬────────────────────────────┘
                            ▼
┌────────────────────────────────────────────────────────┐
│  PHASE 5: Production Scaling & Commercial Readiness    │
│  - Multi-region Kubernetes deployment & auto-scaling   │
│  - Production OpenTelemetry tracing & SLA alerts       │
│  - SOC2 / DPDP Act compliance hardening                │
└────────────────────────────────────────────────────────┘
```

---

## Phase Breakdown & Objectives

### PHASE 0 — Project Control & Truthfulness
* **Goal**: Align the repository with factual reality, establish strict AI-agent governance, and fix surface bugs that compromise trust.
* **Key Deliverables**:
  * Establish engineering control documentation (`PROJECT_STATUS.md`, `ROADMAP.md`, `BACKLOG.md`, `DEFINITION_OF_DONE.md`, `ARCHITECTURE.md`).
  * Fix developer console bugs (`call.session_id` JavaScript TypeError).
  * Fix carrier webhook connection modal URL display in console.
  * Audit and align customer-facing marketing claims with actual codebase capabilities.

### PHASE 1 — Real PSTN MVP Validation
* **Goal**: Validate an authentic telephone conversation from a real cellular/landline phone across public PSTN networks.
* **Key Deliverables**:
  * Procure and configure a live Exotel virtual number or Twilio SIP line.
  * Execute end-to-end inbound and outbound telephone calls through public carrier gateways.
  * Instrument and record real-world mouth-to-ear latency across 100+ live turns.
  * Verify acoustic barge-in interruption against real background noise and cellular compression.
  * Verify speech accuracy across primary regional languages (Hindi and English (India)).

### PHASE 2 — Reliability & Provider Resilience
* **Goal**: Prevent dropped calls and broken dialogues caused by upstream network jitter, rate-limiting, and cloud provider timeouts.
* **Key Deliverables**:
  * Implement automated reconnect and recovery for Sarvam STT WebSocket dropouts.
  * Implement fallback logic for Groq rate-limiting (HTTP 429) or token latency spikes.
  * Handle carrier WebSocket disconnects with graceful call cleanup and accounting.
  * Implement caller-facing graceful apology prompts during downstream API degradation.

### PHASE 3 — Production Data Architecture
* **Goal**: Decouple the platform from single-worker SQLite and local in-process memory.
* **Key Deliverables**:
  * Migrate relational persistence from local SQLite to managed **PostgreSQL**.
  * Introduce **Alembic** for tracked, reversible database schema migrations.
  * Implement **Redis** for distributed active call registry and cross-worker signaling.
  * Replace in-memory FAISS with persistent **pgvector** or managed vector store.
  * Integrate cloud object storage (Amazon S3 / Google Cloud Storage) for uploaded documents.

### PHASE 4 — SaaS Platform Capabilities
* **Goal**: Enable self-service multi-tenant business operations and commercial monetization.
* **Key Deliverables**:
  * Implement real-time call second metering and quota enforcement per tenant.
  * Integrate Indian payment gateway (**Razorpay**) and international billing (**Stripe**).
  * Implement granular Role-Based Access Control (Owner, Admin, Member, Auditor).
  * Build, test, and publish official Python and TypeScript client SDK packages.

### PHASE 5 — Production Scaling & Commercial Readiness
* **Goal**: Scale platform to handle thousands of concurrent calls with enterprise-grade SLAs.
* **Key Deliverables**:
  * Multi-region Kubernetes deployment with automated horizontal pod autoscaling.
  * End-to-end distributed tracing using OpenTelemetry and Prometheus exporters.
  * Implement compliance hardening for India's Digital Personal Data Protection (DPDP) Act.
  * Deploy automated carrier health-check probes and failover SIP routing.
