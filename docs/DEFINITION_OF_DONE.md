# OmniVoice — Definition of Done (DoD)

**Scope:** All software engineering tasks, AI agent implementations, and pull requests.  
**Principle:** **A task is NOT DONE simply because code exists or a file was created.**  

---

## 1. Universal Engineering Requirements

Every backlog item or feature implementation must satisfy all applicable criteria before being marked as **Done**:

### 1.1 Implementation Integrity
- [ ] **Acceptance Criteria Met**: Every acceptance criterion specified in the backlog item is explicitly satisfied and verified.
- [ ] **No Scope Creep**: The changes address only the explicit task requirements. Unrelated bugs, refactoring, or new features discovered during work are logged as new backlog items, not silently folded into the PR.
- [ ] **Architectural Honesty**: Implementation matches documented reality. Incomplete, synthetic, or planned features must not be documented or marked as complete.

### 1.2 Quality & Automated Testing
- [ ] **Automated Tests Added/Updated**: New capabilities or bug fixes are accompanied by unit tests, integration tests, or regression tests covering both the happy path and edge cases.
- [ ] **Zero Regressions**: All existing test suites pass completely (`pytest tests/` exits with code 0).
- [ ] **Failure Paths Verified**: Error conditions (timeouts, network dropouts, 4xx/5xx responses, malformed inputs) are tested and handled gracefully without unhandled exceptions or server crashes.
- [ ] **Build & Lint Verification**: Code passes static analysis without errors (`ruff check omnivoice` and `npm run build` in `landing/`).

### 1.3 Security & Multi-Tenancy
- [ ] **Zero Secret Leakage**: No API keys, carrier credentials, tokens, or private secrets are committed to git, logged in server output, or exposed in URLs.
- [ ] **Tenant Isolation Preserved**: Every data read, write, tool invocation, and vector search is strictly scoped to the authenticated `tenant_id`. No cross-tenant data leaks.
- [ ] **Input & SSRF Validation**: All external URLs, user inputs, and JSON schemas are validated against strict type and schema constraints.

### 1.4 Documentation & Reporting
- [ ] **Documentation Updated**: Relevant architectural documents (`docs/ARCHITECTURE.md`, `docs/PROJECT_STATUS.md`, `docs/BACKLOG.md`) reflect the new state.
- [ ] **No Unsupported Marketing Claims**: Marketing copy, code examples, and UI copy must not claim capabilities that do not exist in the working codebase.
- [ ] **Completion Report Generated**: A structured task completion report is provided, documenting what changed, how it was verified, and any remaining risks.

---

## 2. Telephony & Media Specific Requirements

For any task that modifies or introduces telephony, audio, or speech pipeline components, the following additional requirements are mandatory:

- [ ] **Real Carrier Protocol Fidelity**: Packet schemas and framing strictly adhere to carrier specifications (e.g., 3200-byte PCM alignment for Exotel; 8 kHz G.711 $\mu$-law framing for Twilio).
- [ ] **Full-Duplex & Barge-in Integrity**: Interruption behavior is tested. Incoming caller speech must cleanly clear pending agent audio without packet clipping, buffer leakage, or audio stutter.
- [ ] **Audio Resampling Invariants**: Audio sample rate conversions (e.g., 8 kHz to 16 kHz) must be stateful and causal, maintaining waveform continuity across packet boundaries without clicking or phase distortion.
- [ ] **Latency Instrumentation**: Any change impacting the audio turn path must measure and document its latency contribution (VAD detection, STT transit, inference TTFT, TTS TTFA).
- [ ] **Graceful Call Termination**: When calls end or fail, all WebSocket connections, active provider sockets, in-memory queues, and background tasks are cleanly cancelled and closed without leaking memory or file descriptors.
