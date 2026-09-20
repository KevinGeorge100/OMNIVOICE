# OmniVoice — Product Requirements Document

Version: 1.3  
Updated: 2026-09-20  
Status: Living product baseline; engineering targets are not certification claims  
Related document: [Project Vision & Mission](VISION_AND_MISSION.md)

## 1. Product definition

OmniVoice is an enterprise Voice AI telephony infrastructure platform for live PSTN/SIP mobile and landline calls. Organizations subscribe to or purchase access, connect existing numbers, supply private knowledge, and configure authorized business workflows.

The S7 project establishes a working, evaluated implementation. Commercial release requires additional reliability, security, operational and performance validation.

## 2. Problem statement

Sequential voice pipelines create long silences. Remote retrieval introduces blocking delays. Acoustic thresholds alone confuse noise, acknowledgements and genuine interruptions. Rigid IVRs cannot handle contextual enquiries or safely complete flexible workflows.

OmniVoice addresses these problems through concurrent streaming, neural VAD, speculative retrieval and explicitly confirmed actions.

## 3. Customers and users

| Group | Intended use |
|---|---|
| Educational institutions | Admissions enquiries and student services |
| Healthcare organizations and clinics | Appointment scheduling and administrative enquiries |
| Real estate organizations | Lead qualification and inventory enquiries |
| Customer support organizations | Conversational alternatives to DTMF menus |
| Enterprise administrators | Agent, knowledge, line and workflow configuration |
| Callers | Accurate information and task completion through speech |

The initial commercial customer segment has not been selected.

## 4. Customer experience

Administrators create an organization workspace, configure agents, ingest knowledge, register integrations, connect numbers, test workflows and review operations.

Callers hear an automatic greeting, ask contextual questions, receive grounded answers, interrupt naturally, and explicitly confirm proposed state changes before execution. Completion responses must reflect actual integration outcomes.

## 5. Functional requirements

### 5.1 Telephony

Support concurrent inbound and outbound audio over real PSTN/SIP calls through carrier-specific adapters. Exotel and Twilio are in scope. The current India-focused implementation uses Exotel, Sarvam speech services and Groq inference.

Media ingestion, recognition, reasoning, retrieval, synthesis and playback must remain asynchronous. Background work must not block foreground audio processing.

Connection requirements:

- Maintain authenticated streaming connections for active speech sessions.
- Reuse HTTP connections where HTTP requests are required.
- Avoid unnecessary connection establishment between turns.
- Respect provider concurrency, keepalive and cancellation constraints.
- Authenticate media connections and isolate calls and tenants.
- Distinguish carrier, transport, recognition, inference and synthesis failures.

Correlate these observable events by call and turn: connection accepted, first incoming audio, caller end-of-speech reference, STT partial/final arrival, retrieval start/end, first inference token, first TTS audio, first carrier-bound audio and first caller-audible audio where independently measurable.

Use monotonic clocks for local durations. Cross-system timings require synchronized clocks or a documented alignment method. Never substitute transcript-to-audio-sent timing for end-of-speech-to-audible-response timing.

Next-sprint acceptance:

- Emit an automatic greeting without caller speech.
- Demonstrate simultaneous incoming audio processing and outgoing speech.
- Verify connection reuse across normal turns where supported.
- Produce correlated timings for successful and failed calls.
- Separate cold-start and warm-session behavior.
- Identify unavailable measurements instead of estimating them.

### 5.2 Conversation behavior

The agent must maintain context, respond concisely in natural spoken language, avoid repeated introductions, handle greetings and acknowledgements, and ask useful clarifying questions. When business facts are missing, explain the specific limitation rather than repeatedly saying only “I do not know.” Never invent facts or promise an unavailable handoff.

Evaluate naturalness independently from factual accuracy and speed. Validate follow-up questions, repetition requests, interruptions, ambiguous enquiries and missing-information cases.

### 5.3 Full-duplex interruption engine

Retain the Speak/Listen/Idle finite state machine and Silero neural VAD:

- Speak: generate/play agent audio while processing caller audio.
- Idle: evaluate acoustic and transcript evidence to distinguish interruption from noise or backchannels.
- Listen: process meaningful caller input.

A confirmed interruption must cancel the active response, invalidate stale output and dispatch carrier playback clearing. Cancelled output must not resume into the next turn.

Measure interruption onset-to-decision, decision-to-cancellation/clear dispatch, dispatch-to-audible cessation where observable, false interruptions, missed interruptions and next-turn recovery separately. Under 50ms applies to decision-to-cancellation/clear dispatch, not total audible interruption latency.

Next-sprint acceptance:

- Test genuine interruptions, acknowledgements, background noise and overlapping speech.
- Verify labelled non-interrupting backchannels do not clear playback.
- Verify confirmed interruptions invalidate stale audio and pending unconfirmed actions.
- Verify coherent next-turn recovery.
- Report false/missed interruption counts with denominators and conditions.
- Separate dispatch timing from audible playback cessation.

### 5.4 Enterprise knowledge

Support tenant-isolated documents, approved FAQs and source-associated retrieval. Refresh or invalidate knowledge caches after changes. Ground business answers in supplied knowledge or authorized tool results. Retrieved content is data, not authority to override policies.

Database schemas may describe available data; actual access requires a configured integration. No customer-specific business facts may be fabricated for demonstrations.

### 5.5 Dual-agent speculative retrieval

Retain VoiceAgentRAG: the background Slow Thinker predicts three to five likely follow-up topics and prefetches tenant-scoped knowledge into an in-memory semantic cache. The foreground Fast Talker checks that cache before the cache-miss retrieval path.

Speculative work must be bounded, cancellable or supersedable, and must not monopolize foreground resources.

Correctness requirements:

- Isolate entries by tenant and associate them with source and knowledge revision.
- Invalidate or refresh entries after relevant updates.
- Prevent superseded predictions from publishing obsolete results.
- Apply freshness limits to live read results.
- Never treat speculative retrieval as authorization for a write.
- Bypass generation only for eligible approved cached answers.

A cached knowledge chunk can accelerate grounding without eliminating generation. Measure query embedding, index lookup, complete cache path, hit/miss rate, approved-answer reuse, prediction utility, unused prefetch, remote retrieval, foreground contention, stale answers and tenant-isolation failures separately.

The sub-millisecond target applies to in-memory lookup; embedding and generation remain visible costs.

Next-sprint acceptance:

- Compare equivalent conversations with speculation enabled and disabled.
- Demonstrate a predicted follow-up cache hit and a grounded cache miss.
- Update knowledge and verify superseded answers are no longer eligible.
- Verify cross-tenant retrieval is denied.
- Measure foreground impact of prefetch; do not assume it always improves latency.

### 5.6 Business actions

Permit speculative non-blocking reads during partial transcription. Require registered tools, validated arguments and restricted permissions.

Stage state-changing actions without executing them. Execute only after explicit end-of-turn caller verbal confirmation. Cancel unconfirmed staged actions, protect against duplicate execution, and report successful, failed or uncertain outcomes honestly.

The staging buffer does not guarantee reversibility after an external write. Never automatically retry an uncertain write as though it had failed safely.

Acceptance includes zero business writes without confirmation, no write after cancellation, and truthful outcome reporting.

### 5.7 Administration and observability

Provide organization and agent configuration, knowledge management, phone-line settings, registered workflows, call outcomes, performance metrics, failure diagnostics and integration readiness.

The console is an administrative interface; the caller experience remains telephony.

## 6. Technical architecture

| Layer | Required foundation |
|---|---|
| Transport | Bidirectional SIP/carrier media streaming |
| Core | FastAPI asynchronous engine |
| Speech | Streaming STT and TTS |
| Connections | Persistent authenticated sessions and appropriate pooling |
| Turn-taking | FlexDuo-style FSM and Silero VAD |
| Retrieval | Slow Thinker prefetch and Fast Talker cache-first path |
| Knowledge | In-memory FAISS; FAISS and/or Qdrant for deployment storage needs |
| Reasoning | Streaming foreground responses and background prediction |
| Actions | Speculative reads, confirmation-gated writes |
| Evaluation | Instrumented calls, Fisher Corpus and FD-Bench |

Keep reception, recognition, retrieval, reasoning and playback independently scheduled. Referenced research architectures and datasets must be credited; research novelty requires comparison with prior work.

## 7. Performance and quality requirements

### 7.1 Measurement contract

The primary conversational objective is under 500ms from caller end of speech to first audible agent response over the telephone connection.

| Measure | Boundary |
|---|---|
| Greeting startup | Declared call/media start to first greeting audio |
| STT finalization | End-of-speech reference to final transcript arrival |
| Internal response | Final transcript arrival to first audio sent |
| End-to-end response | Caller end of speech to first audible response |
| Cache lookup | Prepared query vector to in-memory result |
| Complete cache path | Foreground query arrival to usable context/approved answer |
| Interruption dispatch | Confirmed decision to cancellation/clear dispatch |
| Audible interruption | Caller interruption onset to playback cessation |

A last-positive-VAD timestamp is a proxy, not an independently verified end-of-speech reference.

### 7.2 Targets

- End-to-end conversational response: under 500ms.
- Interruption decision-to-cancellation/clear dispatch: under 50ms.
- In-memory semantic lookup: under 1ms.
- Eligible approved cached-answer internal path: under 20ms.
- State-changing business actions without explicit caller confirmation: zero.

Report P50/P95/P99, sample size, calculation method, failure rate and conditions. A formal percentile-based release gate remains undecided. Do not silently relax targets or invent an approved release gate.

### 7.3 Current evidence

User-reported findings: unoptimized telephony/STT round-trip latency of 15–25s; optimized latency of 3–6s after pooling and non-blocking I/O; approximately 650ms attributed to persistent aiohttp pooling. Measurement boundaries and conditions are insufficient for direct comparison with the end-to-end target. Pooling alone does not explain the full improvement.

The current implementation uses persistent WebSockets and httpx, not aiohttp. No verified Sarvam-versus-Deepgram comparison or isolated live STT benchmark is available.

Historical development observations:

- Nine final-transcript-to-first-audio-sent observations: approximately 736–1,723ms.
- Corresponding last-VAD-speech-to-first-audio-sent observations: approximately 1,218–2,316ms.
- One interruption decision-to-clear dispatch: approximately 0.86ms.
- One simulated unsolicited-greeting test: approximately 1,753ms from start event to first received audio.

These are small-sample observations, not representative percentiles or caller-audible results. They do not establish achievement of the sub-500ms target. Preserve historical results when adding newer runs.

### 7.4 Next-sprint benchmark acceptance

Deliver a reproducible report with carrier, provider, model, audio format, deployment location, connection mode, cold/warm results, cache-hit/miss results, stage timings, sample counts, distributions, errors, timeouts, disconnects and labelled interruption outcomes.

Compare speculation enabled versus disabled. State unavailable measurements. Instrumentation completion and target achievement are separate decisions. If a target is missed, record contributors, mitigation and the next experiment while preserving the target.

## 8. Security and deployment

Enterprise release requires tenant-scoped authorization, protected knowledge and media access, secure credentials, encrypted external communication, restricted tools, auditable confirmed actions, defined retention/recording policies, stable hosting, monitoring and recovery procedures.

A temporary tunnel and an awake developer computer are prototype facilities, not enterprise deployment. Availability commitments, concurrency gates, retention periods and pricing remain decisions to be made.

## 9. Release acceptance and sprint scope

S7 commitments: a real inbound call, automatic greeting, grounded multi-turn conversation, genuine interruption and recovery, observable speculative cache hit, speculative read, confirmation-gated staged write and measured evaluation with limitations.

Current sprint: naturalness refinement, latency instrumentation, connection reuse, live-call stage decomposition, speculative retrieval comparison and labelled interruption testing.

Enterprise release: sustained multi-tenant load, broader provider/carrier coverage, failover, production hosting, operational commitments and security validation. Deferral does not remove S7 architecture or demonstration commitments.

Use Fisher Corpus and FD-Bench where accessible under applicable usage conditions; supplement with clearly labelled live/scripted tests. Measure WER, grounding correctness, task completion and conversation quality alongside latency. Do not fabricate corpus results.

## 10. Current implementation status

User-confirmed: the real Exotel test line connects, introduces itself first, supports spoken conversation and answers supplied OmniVoice information. Naturalness needs refinement.

Seven project-grounded FAQs are loaded. Customer-specific documents and business integrations are not yet supplied. Real interruption quality, speculative retrieval benefits and production performance require further validation. Automated checks and simulated audio tests do not certify enterprise readiness.

## 11. Scope boundaries

Never dilute the five invariants: sub-500ms telephony objective; true full-duplex Speak/Listen/Idle with Silero; dual-agent speculative retrieval; explicit confirmation before business writes; real PSTN/SIP infrastructure rather than a browser chatbot or sequential REST wrapper.

## 12. Agile documentation protocol

For each reported implementation outcome, benchmark, constraint or trade-off:

1. Classify the issue and identify infrastructure, provider or algorithmic dependencies.
2. Propose mitigation preserving all five invariants.
3. Identify affected sections and record baseline versus updated acceptance criteria.
4. State current-sprint versus enterprise scope changes without removing S7 commitments.
5. Update complete affected sections and their testable next-sprint criteria.
6. Record evidence source, measurement boundary, environment, sample size and limitations; mark unknowns explicitly.
7. Update this changelog. Update Vision & Mission only where product intent or execution framing changes; do not rewrite invariants to accommodate a failure.

Treat user-reported, instrumented, simulated and independently verified results as distinct evidence classes. Keep targets separate from achieved results. This protocol is applied when engineering updates are processed; it does not imply unattended monitoring.

## 13. Changelog

| Version | Date | Sections | Baseline → update | Scope effect |
|---|---|---|---|---|
| 1.0 | 2026-09-19 | 1–11 | Initial PRD from locked master scope | S7 demonstration distinguished from enterprise release |
| 1.1 | 2026-09-19 | 5.1, 5.3, 5.5, 7, 9–12 | General streaming/performance requirements → explicit stage boundaries, evidence classes, percentile reporting, cache comparison and interruption acceptance tests | Instrumentation and controlled comparisons enter current sprint; production load/failover remain enterprise validation; all targets preserved |

Version 1.1 also records user-confirmed greeting/conversation functionality, ongoing naturalness work and the agile update protocol. The reported 15–25s/3–6s figures are not adopted as achieved OmniVoice end-to-end benchmarks.


### Interim Review 2 milestone — version 1.2

The user delegated selection of demonstration modules. Define the review's 50% milestone as the working inbound vertical slice: telephony, streaming speech, grounded knowledge, conversation orchestration and monitoring. This is a scope allocation, not a measured percentage of implementation effort or a guarantee of rubric approval.

Section 9 delta: prioritize repeatable demonstration readiness, a guided console page, protected public-connection preflight and a seven-minute presenter guide. Retain S7 commitments for speculative retrieval, interruption handling and confirmed actions; they are not removed by narrowing this interim demonstration.

Acceptance: pass technical preflight, complete the real-call rehearsal checklist in INTERIM_REVIEW_2.md, show actual session evidence, and label unvalidated targets and modules. Technical preflight and 26 automated tests passed during preparation; a fresh real-phone rehearsal of the complete review sequence remains required.

Changelog 1.2 (2026-09-19): added Review 2 console flow, read-only preflight and demonstration guide; preserved all five invariants. No production-readiness or end-to-end latency claim added.


### Product interface separation — version 1.3

2026-09-20: Per user direction, the website contains product operations only. Removed Interim Review navigation, content and its dedicated renderer. Review preparation remains in separate local documentation; use the regular Knowledge base, Phone lines and Call activity pages for any presentation. Visual refinements preserve core product IDs, workflows and API calls. No architectural or performance targets changed.
