# OmniVoice — Engineering Backlog

**Document Status:** Canonical backlog tracker  
**Status Key:** `Planned` | `In Progress` | `Blocked` | `Done`  
**Priority Key:** `P0` (Critical) | `P1` (High) | `P2` (Medium) | `P3` (Low)  

---

## Backlog Index

| ID | Title | Type | Priority | Status |
| :--- | :--- | :--- | :--- | :--- |
| **OV-001** | Establish OmniVoice Engineering Project Control | Task | P0 | **Done** |
| **OV-002** | Fix Console Call Details TypeError (`call.session_id`) | Bug | P0 | **Done** |
| **OV-003** | Fix Carrier Webhook URL Display in Console Modal | Bug | P0 | **Done** |
| **OV-004** | Audit & Reconcile Landing Page Marketing Claims | TechDebt | P1 | **Done** |
| **OV-005** | Real PSTN End-to-End Telephone Validation Test | Spike | P0 | **Done** |
| **OV-006** | Instrument & Evaluate Server-Observed Voice Latency | Task | P1 | **Done** |
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
| **OV-020** | Harden Exotel WebSocket Stream Authentication | Security | P2 | Planned |
| **OV-021** | Antigravity Engineering Environment Hardening | Tooling | P0 | **Done** |
| **OV-022** | Landing Page Premium UI/UX & Frontend Upgrade | Enhancement | P2 | **Done** |
| **OV-023** | Voice Continuity & Natural TTS Pipeline | Enhancement | P1 | **Done** (Gateway Validated) |
| **OV-024** | Natural Dialogue & Graceful Limitation Handling | Enhancement | P1 | **Done** (Gateway Validated) |
| **OV-025** | Unblock Windows Release Gate & Make Semantic Retrieval Loading Resilient | Bug | P0 | **Done** |
| **OV-026** | Premium Real-Time Operations Console | Enhancement | P1 | COMPLETE |
| **OV-027** | Persistent Cloud Backend & Operations Console Deployment | DevOps | P0 | In Progress |
| **OV-028** | GitHub Repository Experience & Documentation Navigation | Documentation | P2 | **Done** |

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
* **Status:** **Done**
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
* **Status:** **Done**
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
* **Status:** **Done**
* **Dependencies:** OV-001
* **Description:** Reconcile unsupported claims on `landing/` (including unverified PSTN latency SLAs, fictional SDK packages, compliance certifications, production pricing tiers, and unmeasured concurrency) so that marketing copy accurately represents current verified repository capabilities and clearly qualifies roadmap offerings.
* **Acceptance Criteria:**
  1. No customer-facing text presents unimplemented capabilities as available today.
  2. No unverified real-PSTN latency metric is presented as measured fact.
  3. Pricing is clearly identified as indicative/pilot/planned where enforcement does not exist.
  4. Fictional SDK packages replaced by real FastAPI REST endpoints with planned SDK roadmap notes.
  5. Compliance claims (SOC2/HIPAA) removed and replaced by factual security architecture descriptions.
  6. Private VPC/on-prem availability presented as enterprise roadmap items.
  7. Voice sandbox clearly identified as a browser simulation/prototype.
  8. Existing verified capabilities remain confidently presented with clean Next.js build.

---

### [OV-005] Real PSTN End-to-End Telephone Validation Test
* **Type:** Spike
* **Priority:** P0
* **Status:** **Done**
* **Dependencies:** OV-002, OV-003
* **Description:** Place authentic telephone calls from physical mobile handsets over a carrier network (Exotel) through an HTTPS/WSS tunnel to the OmniVoice engine.
* **Acceptance Criteria:**
  1. Real phone call connects and plays greeting within 1500 ms of answer. *(Verified: consistently ~250 ms across 3 physical calls; Call #3: 252.78 ms)*
  2. Caller speech is transcribed and answered by AI with grounded context. *(Verified: Sarvam STT -> FAISS/RAG -> Groq LLM -> Sarvam TTS -> Exotel full-duplex loop across 4 turns in Call #3)*
  3. Call audio is clean without carrier packet underruns. *(Verified: continuous 3200-byte linear16 8kHz framing)*
  4. Complete call record and turn metrics logged in SQLite. *(Verified: persisted in `data/omnivoice.db` with `user_transcript`, `agent_response`, latency percentiles, and zero unhandled errors)*
* **Validation Evidence & Operational Findings:**
  * **3 Physical PSTN Validation Calls**: Executed over Exotel carrier line `+914954269065` to local server via Cloudflare tunnel.
  * **Call #1**: Verified basic inbound media ingress, greeting audio, STT/TTS pipeline, and graceful termination.
  * **Call #2**: Identified turn-taking thrashing where generation-stage transcript collisions caused false `interrupted: true` flags (8/10 turns). Successfully proved true playback barge-in ("Wait") and backchannel suppression ("yeah").
  * **Call #3**: Validated ADR-001 turn-taking stabilization commit (`f1fec4aae6fda87c3280cd5d09e52f76366c0d59`). 109.77-second call, 4 completed conversational turns, 0 false interrupted turns, 0 false carrier clears, 0 false barge-in telemetry events, 0 socket/runtime errors, and full SQLite persistence.
  * **Remaining Quality Scope**: Speech naturalness/choppiness tracked in OV-023; dialogue refusal naturalness tracked in OV-024. PSTN transport, WebSocket lifecycle, and turn-taking repeatability are proven.

---

### [OV-006] Instrument & Evaluate Server-Observed Voice Latency
* **Type:** Task
* **Priority:** P1
* **Status:** **Done**
* **Dependencies:** OV-005
* **Description:** Instrument server-observed stage durations and export privacy-preserving per-turn data. Collect at least 50 valid turns across multiple live sessions for an empirical baseline; physical acoustic mouth-to-ear timing requires a separate synchronized measurement protocol.
* **Acceptance Criteria:**
  1. Record per-stage N, mean, sample standard deviation, min, p50, p90, p95, and max on at least 50 valid turns. *(Verified: 56 valid turns across 6 sessions; 0 exclusions; detailed summary in `docs/OV006_BENCHMARK_RESULTS.md`)*
  2. Label VAD speech-end estimates as proxies and do not infer carrier network transit or acoustic playback from server-only timestamps. *(Verified: explicit research caveats and proxy labelling documented)*
  3. Document boundaries, exclusions, and measurement protocol in `docs/LATENCY_EVALUATION.md` and `docs/OV006_BENCHMARK_RESULTS.md`. *(Verified)*
* **Benchmark Results Summary:**
  * **Dataset Label**: `LIVE GATEWAY SERVER-LATENCY BENCHMARK` (56 valid turns / 6 sessions / 0 exclusions).
  * **Overall Server Turnaround (`final_transcript_to_first_audio_sent_ms`)**: P50 = 774.76 ms, P90 = 1019.79 ms, P95 = 1466.88 ms, Mean = 714.23 ms.
  * **Fast FAQ Cache Turnaround**: P50 = 261.12 ms (3.26x faster than RAG).
  * **Foreground RAG Turnaround**: P50 = 850.21 ms.
  * **Decomposition**: LLM TTFT P50 = 616.00 ms (Groq `openai/gpt-oss-20b`), TTS TTFA P50 = 218.35 ms (Sarvam `bulbul:v3`), Speech Buffering P50 = 17.86 ms, RAG Retrieval P50 = 0.64 ms, Carrier Framing P50 = 0.09 ms.
  * **Research Caveats**: Exotel live PSTN re-validation deferred due to external credit/KYC constraints; physical acoustic mouth-to-ear latency not claimed; 120 ms STT endpoint delay transparently recorded as a test harness offset.

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

### [OV-020] Harden Exotel WebSocket Stream Authentication
* **Type:** Security
* **Priority:** P2
* **Status:** Planned
* **Dependencies:** OV-003
* **Description:**
  * The current Exotel stream secret is embedded in the WebSocket URL path (`/ws/exotel/{line_id}/{token}`).
  * URLs may be captured in reverse-proxy, gateway, firewall, or infrastructure access logs.
  * A production-ready design must minimize credential exposure while remaining compatible with Exotel's actual carrier capabilities (as Exotel audio stream applets do not support custom WebSocket handshake authorization headers).
* **Potential Approaches to Investigate:**
  * Short-lived or single-use stream tickets.
  * Signed expiring tokens.
  * Aggressive token rotation.
  * Reverse-proxy / access-log redaction.
  * Gateway-mediated token exchange.
  * Any authentication mechanism officially supported by Exotel.
* **Acceptance Criteria:**
  1. Permanent line credentials are no longer exposed in plaintext across infrastructure logs.
  2. Carrier connectivity remains fully compatible with Exotel's real carrier capabilities.

---

### [OV-021] Antigravity Engineering Environment Hardening
* **Type:** Tooling
* **Priority:** P0
* **Status:** **Done**
* **Dependencies:** None
* **Description:** Upgrade the repository's Antigravity development environment with a minimal set of deterministic engineering safeguards, project-specific workspace skills, CodeRabbit CLI review integration, and automated Definition of Done release gates before real PSTN validation.
* **Acceptance Criteria:**
  1. GSD Core remains absent; no parallel task trackers created.
  2. Official CodeRabbit CLI installed and verified.
  3. Telephony validation workspace skill (`telephony-validation`) created.
  4. Tenant security audit workspace skill (`tenant-security-audit`) created.
  5. Release gate workspace skill (`release-gate`) and deterministic script `scripts/verify-dod.ps1` created.
  6. Release gate script passes all 6 gates (pytest, ruff, Next.js build, browser E2E, git hygiene, whitespace check).
  7. CodeRabbit CLI review executed against uncommitted task diff with findings triaged.
  8. Governance workflow documented with authoritative engineering lifecycle.
  9. Zero secrets exposed; no product/runtime behavior modified.

---

### [OV-022] Landing Page Premium UI/UX & Frontend Upgrade
* **Type:** Enhancement
* **Priority:** P2
* **Status:** **Done**
* **Dependencies:** OV-004
* **Description:** Transform the OmniVoice public landing page from a clean developer-project website into a polished, distinctive enterprise Voice AI infrastructure product website. Redesign focuses on presentation, hierarchy, interaction and layout — not new product claims. All OV-004 truthfulness requirements are preserved.
* **Acceptance Criteria:**
  1. Hero redesigned as editorial split with realtime call visualization on the right.
  2. Architecture section shows a connected pipeline (not disconnected cards).
  3. Developer section rendered as a dark ink high-contrast section.
  4. FeatureGrid replaced by 3 capability pillars with hierarchy.
  5. Navbar simplified to 5 items, version pill removed.
  6. All section backgrounds alternate rhythmically (white / mint / dark).
  7. Typography scale: hero headline ≥ 64px, section headings ≥ 42px, body ≥ 17px.
  8. `prefers-reduced-motion` respected for all animations.
  9. No OV-004 claim qualifications removed or weakened.
  10. `npm run build` passes, all backend tests pass.

---

### [OV-023] Voice Continuity & Natural TTS Pipeline
* **Type:** Enhancement
* **Priority:** P1
* **Status:** **COMPLETE — LIVE TELEPHONY GATEWAY VALIDATED (REAL PSTN RE-VALIDATION DEFERRED)**
* **Dependencies:** OV-005
* **Problem:** Real PSTN audio is intelligible and transport-stable, but long responses sound assembled/choppy. Evidence from PSTN Call #3:
  * Sentence-by-sentence regex splitting triggers discrete TTS WebSocket flush cycles.
  * Long architecture answer produced 7 separate, isolated TTS cycles with zero cross-sentence prosodic continuity.
  * Raw Markdown formatting (`*`, `**`, `–`) reaches TTS and degrades vocalization.
  * Blocking inter-sentence synthesis introduces audible gaps while downstream carrier buffers drain.
  * Exotel 3200-byte partial frame null padding injects up to 137.5 ms of artificial silence per sentence fragment.
  * Per-segment TTS continuity telemetry is currently missing from session metrics.
* **Goal:** Make OmniVoice speech sound like one continuous natural telephone conversation while preserving low first-audio latency and full-duplex barge-in. Require architectural investigation before changing framing or provider behavior.
* **Acceptance Criteria:**
  1. Investigate and document TTS streaming, pipelining, and framing options before implementation.
  2. Strip raw Markdown artifacts and formatting symbols before sending text to speech synthesis.
  3. Eliminate audible artificial sentence-boundary acoustic gaps.
  4. Implement continuous PCM handling without avoidable injected digital null silence.
  5. Preserve low first-audio dispatch latency (<500 ms).
  6. Preserve acoustic playback interruption and carrier clear dispatch.
  7. Validate speech continuity subjectively on authentic physical PSTN calls (deferred pending carrier credit / commercial KYC).
* **Validation Note:**
  * Live bidirectional telephony gateway validation passed (`/ws/audio`).
  * Real carrier/PSTN re-validation is deferred because Exotel trial credit is exhausted and additional credit requires commercial GST/KYC (academic/student project constraint). Historical OV-005 real PSTN evidence preserved.

---

### [OV-024] Natural Dialogue & Graceful Limitation Handling
* **Type:** Enhancement
* **Priority:** P1
* **Status:** **COMPLETE — LIVE TELEPHONY GATEWAY VALIDATED (REAL PSTN RE-VALIDATION DEFERRED)**
* **Dependencies:** OV-005
* **Problem:** Anti-hallucination grounding behavior is factual but conversationally mechanical. Observed failure pattern in PSTN Call #3:
  * Caller asks unavailable fact (pricing) -> assistant states limitation -> assistant asks clarification (organization name) -> caller provides clarification -> assistant repeats essentially the same limitation.
* **Goal:** Preserve strict factual grounding while making limitations and refusals natural, conversational, and helpful.
* **Target Dialogue Policy:**
  * `ACKNOWLEDGE -> STATE LIMITATION NATURALLY -> OFFER AVAILABLE HELP / NEXT BEST ACTION`
* **Acceptance Criteria:**
  1. Never fabricate unavailable information or hallucinate capabilities.
  2. Avoid repetitive refusal loops and robotic verbatim reiteration.
  3. Do not prompt the caller for clarification when the missing information cannot change the outcome.
  4. Gracefully redirect the caller toward capabilities and business knowledge actually available on the line.
  5. Maintain concise, telephone-friendly phrasing appropriate for voice dialogue.
* **Validation Note:**
  * Live bidirectional telephony gateway validation passed (`/ws/audio`).
  * Real carrier/PSTN re-validation is deferred because Exotel trial credit is exhausted and additional credit requires commercial GST/KYC. Historical OV-005 real PSTN evidence preserved.

---

### [OV-025] Unblock Windows Release Gate & Make Semantic Retrieval Loading Resilient
* **Type:** Bug
* **Priority:** P0
* **Status:** **Done**
* **Dependencies:** None
* **Description:**
  * FAISS was eagerly imported at top-level module import time in `omnivoice/rag.py`.
  * On the Windows development host, OS Application Control (WDAC/AppLocker) prevents `_swigfaiss.pyd` from loading, raising `ImportError` on any import of `omnivoice.app` or `omnivoice.rag` even when `OMNI_SEMANTIC_ENABLED=false`.
  * This blocked `tests/test_api.py`, `tests/test_core.py`, `tests/browser_check.py`, and `scripts/verify-dod.ps1`.
* **Acceptance Criteria:**
  1. Module import of `omnivoice.rag` and `omnivoice.app` does not eagerly import FAISS.
  2. When `semantic_enabled=False`, OmniVoice starts normally with exact FAQ and lexical document retrieval, never importing FAISS.
  3. When `semantic_enabled=True` and FAISS is available, semantic retrieval behavior and indexing operate unchanged.
  4. When `semantic_enabled=True` but FAISS is unavailable, the system explicitly reports degraded retrieval in readiness and diagnostics (`SEMANTIC_BACKEND_UNAVAILABLE`) while safely degrading to lexical retrieval without crashing.
  5. Deterministic unit and integration tests verify all semantic states and module import independence.
  6. All 6 release gates in `scripts/verify-dod.ps1` pass on Windows.

---

### [OV-026] Premium Real-Time Operations Console
* **Type:** Enhancement
* **Priority:** P1
* **Status:** COMPLETE
* **Dependencies:** OV-025
* **Purpose:** Turn the existing vanilla console into an operations surface grounded in actual tenant data, with an authenticated single-worker live call event stream.
* **Scope:** Overview, voice-agent workspace, phone numbers, knowledge, live calls, paginated history, call inspector, actions, analytics, and responsive/accessibility improvements. No voice-engine, billing, recording, RBAC, or multi-worker implementation.
* **APIs:** Existing tenant APIs are reused. `GET /api/tenants/{tenant_id}/calls` gains optional bounded filters/pagination while preserving the default JSON-list response. `GET /api/tenants/{tenant_id}/analytics` returns database-aggregated call metrics. `GET /api/tenants/{tenant_id}/events` streams tenant-scoped SSE events over bearer-authenticated fetch.
* **Realtime behavior:** `call.started`, `call.turn`, and `call.ended` events contain bounded session metadata and recorded turn previews; no audio, carrier secret, or action arguments. A bounded in-memory queue per listener supports this single-worker prototype. The browser reconnects after transient stream loss and fetches a snapshot for current active calls on workspace refresh.
* **Limitations:** Caller number, historical line association, detailed end reason, and production uptime are not stored. Live events do not cross workers or survive restart. First-audio values are server outbound timing, not acoustic mouth-to-ear measurements. Carrier connection is not inferred from local number registration.
* **Acceptance:** Tenant isolation and authentication tests pass, browser workflows cover the new screens and legacy metrics, and the repository release gate passes before review.

---

### [OV-027] Persistent Cloud Backend & Operations Console Deployment
* **Type:** DevOps
* **Priority:** P0
* **Status:** In Progress
* **Dependencies:** OV-025, OV-026
* **Purpose:** Deploy OmniVoice backend and Operations Console to persistent public cloud infrastructure with stable HTTPS/WSS endpoints and durable volume storage.
* **Scope:** Single-service container hardening, Silero model baking, persistent volume specification for SQLite, deployment guide documentation, health/readiness endpoints, and Exotel cutover procedure.
* **Acceptance:** Container builds self-contained, `/healthz` and `/readyz` pass remotely, Operations Console loads securely, and deployment documentation is complete.

---

### [OV-028] GitHub Repository Experience & Documentation Navigation
* **Type:** Documentation
* **Priority:** P2
* **Status:** **Done**
* **Dependencies:** None
* **Purpose:** Make the public repository immediately understandable without presenting targets, gateway benchmarks, or planned production features as achieved facts.
* **Scope:** README hierarchy and diagrams, a lightweight static visual, linked developer details, contribution guidance, and a review template. No application behavior changes.
* **Acceptance:** Local links and heading anchors resolve, Mermaid blocks parse, existing setup/action details remain available, and benchmark claims retain their measurement boundary.
