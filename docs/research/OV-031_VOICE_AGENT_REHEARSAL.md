# OV-031 — Full Voice Sales-Agent Rehearsal

## 1. Objective

Validate the spoken sales-agent workflow through the production call session: caller audio, STT, dialogue and tool selection, read tools, confirmation-gated write, TTS, carrier-ready frames, persistence, and research telemetry. This is a validation milestone, not a claim of deployment readiness. Evidence is retained in the two OV-031 JSON files under `data/research/`.

## 2. Validation levels and verdict

| Level | Boundary | Result |
|---|---|---|
| A | Exotel-shaped local loopback, real session/business code, deterministic STT/LLM/TTS/VAD interfaces | **PASS: 12/12 scenarios** |
| B | Local carrier loopback and SQLite, real Silero, Gnani Prisma STT, Groq `openai/gpt-oss-20b`, Gnani Timbre TTS | **FAIL: partial spoken path only** |
| C | Physical PSTN/SIP telephone call | **NOT RUN: carrier access/credits were not verified** |

The task's acceptance rule requires a completed Level B rehearsal when live credentials are configured. They were configured; therefore **OV-031 has not passed overall**. The deterministic result must not be read as live-provider or PSTN success.

## 3. Environment, configuration, and production path

The task branch started at `a35158b6bafcfb8dd4c5de88846eb06ee594344b`. Level A uses a temporary SQLite database, synthetic fixture knowledge, a synthetic lead and demo slot, and an in-memory Exotel-shaped carrier socket. It replaces only provider interfaces, including VAD; it does not call a real speech or model API. Level B uses the configured Gnani STT/TTS and Groq model with a locally generated, non-PII Windows SAPI caller WAV at 8 kHz/16-bit/mono, Silero VAD, and a temporary SQLite store. No external CRM/calendar write occurs.

The production route in `omnivoice/app.py` authenticates `/ws/exotel/{line_id}/{token}`, creates `CallSession`, and persists call status/metrics after `session.run`. In `omnivoice/session.py`, `MediaTransport` receives carrier media, resamples input for streaming STT and Silero, and feeds final transcripts into the dialogue loop. `Groq.stream` chooses registered `ToolRegistry` tools. `SalesService` reads lead/slot data; `ActionEngine` stages writes until an explicit confirmation is spoken and the confirmation prompt has been acknowledged. TTS PCM is framed by the transport for the carrier. Barge-in cancels the active response/TTS and clears outbound carrier playback. The post-call `ResearchObserver` exports an allowlisted numeric projection if enabled. The rehearsal scripts use `CallSession.run` rather than calling a happy-path sales tool directly.

## 4. Happy path

Level A answered an approved FAQ via `fast_cache`, then selected `lookup_lead`, `check_demo_slots`, and `schedule_demo` in separate spoken turns. The booking action reached `armed` after a spoken confirmation prompt. The harness asserted zero bookings before the caller's exact “Yes.” Following confirmation, one action became `committed`, exactly one booking existed, the spoken final response said the demo was booked, and carrier media frames were emitted. This is a scripted dialogue result; model reasoning and acoustic recognition were stubbed at Level A.

## 5. Negative confirmation

“No” cancelled the proposed action. Booking count remained zero and no spoken booking-success claim occurred. The scripted agent continued with a refusal acknowledgement.

## 6. Ambiguous confirmation

“Maybe” did not authorize a write. The action was cancelled, booking count stayed zero, and the scripted response stated it was not booked.

## 7. Duplicate confirmation

A second “Yes” after a committed booking produced no second booking or second committed action. The persisted count remained one.

## 8. Stale slot

The offered slot was marked unavailable between proposal and confirmation. Commit-time validation failed the action, created no booking, and the spoken response said the slot was no longer available.

## 9. Lead-not-found and failure handling

The missing-lead case did not fabricate an existing lead and proceeded to slot availability. A controlled read-tool timeout yielded a safe spoken fallback and zero writes. Injected LLM, STT, and pre-PCM TTS failures followed the existing fallback/termination policy without staging an action or falsely claiming success. These are deterministic fault injections, not provider outage-rate measurements.

## 10. Barge-in

Ordinary-response and confirmation-prompt interruptions each produced one recorded barge-in, cancelled TTS, and issued a carrier `clear`. The interrupted utterance's sample marker did not reappear after `clear`. The replacement caller turn was processed. In the confirmation-prompt case, the unacknowledged proposal became `cancelled` and no booking was made. This validates the session's cancellation behavior under scripted VAD; it does not measure noisy PSTN interruption accuracy.

## 11. Live provider rehearsal

The retained Level B run sent locally synthesized caller speech through the Exotel-shaped media socket. The greeting emitted audio. Gnani STT produced a nonempty lead-request transcript without a forced flush; Groq requested `lookup_lead`; the real local tool resolved the synthetic lead. The second spoken turn did not complete within the bounded wait. The local trace recorded a transient Gnani TTS failure on a turn; the attempt ended with `TimeoutError`. The result file records `FAIL`, zero bookings, no action rows, and 243 observed outbound carrier media frames. A prior local attempt reached slot lookup, but no live attempt completed proposal, confirmation, and final spoken success. Those attempts are not counted as a passing Level B run. The live JSON retains only the last bounded attempt and sanitized metadata, not transcript text or raw audio.

## 12. Physical PSTN status

No telephone call was placed for OV-031. Exotel line configuration exists in the local environment, but carrier credits and commercial readiness were not established during this task. Level C is **NOT RUN**, with no fresh physical-call evidence claimed here. Historical Exotel evidence, if any, is separate.

## 13. Latency evidence

The Level A artifact records server-side synthetic loopback stage samples and percentile calculations. P95 is reported only for at least 20 samples. Provider stubs, local scheduling, and frame pacing make these values unsuitable for provider or PSTN SLO claims.

| Level A stage | Samples | P50 ms | P95 ms |
|---|---:|---:|---:|
| STT stub completion | 33 | 0.66 | 1.25 |
| LLM first token (stub) | 20 | 0.02 | 0.03 |
| Tool execution | 14 | 1.88 | N/A |
| Confirmed action execution | 2 | 5.27 | N/A |
| TTS first PCM (stub) | 32 | 0.05 | 0.17 |
| Final transcript to first carrier audio | 32 | 184.55 | 195.77 |
| Last VAD-positive speech to first carrier audio | 31 | 185.48 | 196.05 |

The STT stub timer is an internal harness observation, **not** a real speech-recognition latency. The Level B partial trace records a first completed lead-turn STT endpoint delay of 620.46 ms and LLM TTFT of 557.36 ms. The second recorded turn has 634.71 ms STT endpoint delay, 648.11 ms LLM TTFT, and 676.58 ms final-transcript-to-first-outbound-audio; it did not complete the required booking workflow. These are local server-side metrics, **not mouth-to-ear latency**. Sample count is too small for a Level B P50 or P95.

## 14. Audio and framing

Level A asserted all outbound media payloads decode to exactly 3,200 bytes, with no `RIFF` WAV header, for 8 kHz, 16-bit, mono PCM at 200 ms per frame. Every scenario produced at least one frame; the happy path produced 12. The carrier-shaped Level B run observed 243 outbound media frames, but its incomplete workflow is not a passed end-to-end audio validation. The live harness verifies the locally generated caller WAV format before input.

## 15. Persistence and action safety

All business records were isolated in temporary SQLite databases. Level A recorded one booking only for the happy path and duplicate-confirmation scenarios; negative, ambiguous, stale-slot, failure, and interruption scenarios recorded zero. There was no unsafe early commit, duplicate booking, or action left executing. Call rows were updated with final status/metrics. Level B persisted the call row and turn metrics; it created zero bookings and zero actions. No external business write was attempted.

## 16. Qualitative turn behavior and telemetry

The Level A JSON carries a per-scenario checklist for response relevance, fixture grounding, false capability claims, confirmation clarity, interruption handling, repetition/awkwardness, and task continuity. Values indicate scripted assertions or “not human rated”; no human-likeness score or acoustic naturalness claim is made. The live run showed a relevant lead lookup, but was not long enough to grade natural conversation quality.

Local session/tool metrics include timing, tool names/outcomes, confirmation/commit counts, error categories, and interruption counts. Level B submitted one safe post-call projection to the optional Langfuse exporter (`langfuse_exported_locally=1`); this is **local SDK submission, not proof of remote receipt**. The authoritative evidence remains the local metrics and deterministic harness. The JSON exports omit transcript text, audio, caller identifiers, tenant identifiers, lead identifiers, tool arguments, and secrets.

## 17. Limitations and next validation

Level A substitutes model, speech, and VAD interfaces and uses an in-memory carrier, so its clean dialogue cannot establish recognition quality, naturalness, provider availability, or physical call latency. Level B remains incomplete due to a bounded second-turn timeout and observed transient TTS failure. A later controlled run must finish spoken slot lookup, proposal, prompt acknowledgement, exact confirmation, single booking commit, truthful spoken success, and carrier framing with the live providers. Record sanitized provider categories and numeric timing; retain no caller data. Verify carrier credits/account state before any Level C test.

## 18. Conclusion

The real session/business path passed all 12 deterministic spoken-session scenarios and preserved confirmation safety, persistence, carrier framing, and barge-in cancellation. The live Gnani/Groq/Gnani full booking rehearsal failed, so the OV-031 acceptance gate is **not met**. Keep the evidence and harness for replay; **do not fast-forward merge this milestone as complete** until a passing Level B run is retained and reviewed.

Validation of the retained code and evidence: OV-031 targeted tests 14/14; focused voice/agent/sales/resilience/Gnani/streaming/OV-030 suites 191/191; OV-011B offline evaluation 25/25 with four confirmed commits, zero unsafe commits, and zero duplicates; full pytest 277/277; Ruff clean; browser E2E 20/20; `scripts/verify-dod.ps1` 6/6 gates; `git diff --check` clean. The release gate verifies engineering hygiene and regression tests; it does not convert the failed live rehearsal into an acceptance pass.
