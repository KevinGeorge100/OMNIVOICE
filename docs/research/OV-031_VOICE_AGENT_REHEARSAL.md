# OV-031 — Full Voice Sales-Agent Rehearsal

## 1. Objective

Validate the spoken sales-agent workflow through the production call session: caller audio, STT, dialogue and tool selection, read tools, confirmation-gated write, TTS, carrier-ready frames, persistence, and research telemetry. This is a validation milestone, not a claim of deployment readiness. Evidence is retained in the two OV-031 JSON files under `data/research/`.

## 2. Validation levels and verdict

| Level | Boundary | Result |
|---|---|---|
| A | Exotel-shaped local loopback, real session/business code, deterministic STT/LLM/TTS/VAD interfaces | **PASS: 12/12 scenarios** |
| B | Local carrier loopback and SQLite, real Silero, Gnani Prisma STT, Groq `openai/gpt-oss-20b`, Gnani Timbre TTS | **PASS: two complete 20/20 attempts retained** |
| C | Physical PSTN/SIP telephone call | **NOT RUN: carrier access/credits were not verified** |

The task's acceptance rule requires a completed Level B rehearsal when live credentials are configured. Two retained attempts meet all 20 checks. This is a live-provider, local-carrier-loopback result; it is not a PSTN or population-reliability result.

## 3. Environment, configuration, and production path

The task branch started at `a35158b6bafcfb8dd4c5de88846eb06ee594344b`. Level A uses a temporary SQLite database, synthetic fixture knowledge, a synthetic lead and demo slot, and an in-memory Exotel-shaped carrier socket. It replaces only provider interfaces, including VAD; it does not call a real speech or model API. Level B uses the configured Gnani STT/TTS and Groq model with a locally generated, non-PII Windows SAPI caller WAV at 8 kHz/16-bit/mono, Silero VAD, and a temporary SQLite store. No external CRM/calendar write occurs.

The production route in `omnivoice/app.py` authenticates `/ws/exotel/{line_id}/{token}`, creates `CallSession`, and persists call status/metrics after `session.run`. In `omnivoice/session.py`, `MediaTransport` receives carrier media, resamples input for streaming STT and Silero, and feeds final transcripts into the dialogue loop. `Groq.stream` chooses registered `ToolRegistry` tools. `SalesService` reads lead/slot data; `ActionEngine` stages writes until an explicit confirmation is spoken and the confirmation prompt has been acknowledged. TTS PCM is framed by the transport for the carrier. Barge-in cancels the active response/TTS and clears outbound carrier playback. The post-call `ResearchObserver` exports an allowlisted numeric projection if enabled. The rehearsal scripts use `CallSession.run` rather than calling a happy-path sales tool directly.

The live continuation identified an implementation defect in `GnaniTTS`: its WebSocket request put `sample_rate` at the top level and sent multiple phrase requests before consuming completion. [Gnani's realtime protocol](https://docs.gnani.ai/api/TTS/tts-websocket) specifies `audio_config.sample_rate` and one request at a time. The adapter now requests 8 kHz mono 16-bit raw PCM in `audio_config` and awaits each phrase's completion before sending the next. This changed no booking, confirmation, carrier, or LLM logic. The earlier overlong PCM streams are consistent with the documented 48 kHz default being misframed as 8 kHz; the provider's actual output sample rate was not independently measured. A transport close after partial audio is still deliberately not replayed by the retry policy.

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

The schema-2 Level B JSON retains **seven attempts**: the original six, including one checkpoint failure, plus one independent-review evidence recheck. The first two continuation attempts stopped during the second spoken turn; the next four completed their scripted turns. All five failed attempts remain in the denominator.

| Retained attempt | Observed result | Classification |
|---|---|---|
| 1 — checkpoint | Lead lookup resolved; second turn emitted audio, then Gnani TTS transient failure; old harness timed out waiting for playback after call closure | Provider failure plus harness diagnostic gap |
| 2 | Lead and slot tools succeeded; Gnani TTS connection failed after partial audio; session closed and all tasks drained | Provider failure with pre-fix adapter |
| 3 | Lead and slot tools succeeded; another partial-audio Gnani TTS transient failure | Provider failure with pre-fix adapter |
| 4 | Corrected Gnani protocol; STT, slot lookup, and TTS worked, but Groq did not select lead lookup for vague fixture wording | Model selection miss; no write |
| 5 | Explicit lead request resolved; Groq did not select slot lookup | Model selection miss; no write |
| 6 | Lead lookup → slot lookup → booking proposal → live confirmation TTS → live “yes” STT → one ActionEngine commit → final Gnani TTS | **PASS: 20/20 checks** |
| 7 — independent review | Repeated the complete live-provider path with a delayed carrier mark acknowledgement and privacy-safe checks of staged arguments, booking relations, slot state, and committed result | **PASS: 20/20 checks** |

In attempt 6, Gnani transcribed four locally synthesized utterances without forced flush. Groq selected `lookup_lead`, `check_demo_slots`, and `schedule_demo` in order; the local tool results were successful, and one slot was offered. The action status was `armed` after the confirmation prompt, while booking count was still zero. Gnani synthesized that prompt into 36 carrier frames. Gnani then recognized “yes”; the existing confirmation path committed exactly once. The final spoken response was “Done. Your demo is booked.” and produced 12 carrier frames. The full call emitted 130 valid outbound frames.

Attempt 7 repeated the workflow and retained stronger evidence. The loopback withheld the booking prompt's carrier mark acknowledgement after all prompt frames were sent. The action remained `staged`, its mark remained pending, and the booking count remained zero. After the harness delivered that mark acknowledgement, the action became `armed`; only the subsequent live Gnani “yes” transcript committed it. Privacy-safe Boolean checks confirm that the staged arguments matched the synthetic lead and selected slot, the single booking belonged to the fixture tenant, lead, slot, and call, the slot became `booked`, and the committed action result named the persisted booking. The final success sentence followed that commit. This verifies mark-gated ordering in the local carrier simulation; the simulation does not prove physical playback or that a human heard the prompt. No real customer data or external CRM/calendar system was used. Both passing attempts and all failures are retained in the JSON artifact.

A Groq `protocol`/`exhausted` event was logged during the slot stage of attempts 6 and 7, while the foreground slot tool and both complete workflows succeeded with no turn-level provider failure. Background speculation can fail open on this same provider path, but the sanitized event does not identify its request source or raw response. The exact cause is therefore unresolved; no protocol defect or user-visible failure is established by these records. The passing verdicts rely on tool/action/audio/persistence evidence, not on absence of every supplemental provider warning.

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

The STT stub timer is an internal harness observation, **not** a real speech-recognition latency. Attempt 6 has these individual live-provider, server-side timings (ms):

| Spoken turn | STT endpoint-to-final proxy | LLM TTFT | Tool/action duration | TTS first PCM | Final transcript to first carrier audio |
|---|---:|---:|---:|---:|---:|
| Lead lookup | 717.81 | 677.69 | lookup 21.61 | 213.56 | 1,954.98 |
| Slot lookup | 762.28 | 594.61 | slots 5.56 | 231.17 | 1,619.99 |
| Booking proposal | 1,021.35 | N/A | proposal duration not retained | 205.72 | 1,005.72 |
| Exact confirmation | 690.49 | N/A | commit 13.78 | 175.19 | 220.93 |

The STT field is the existing last-VAD-positive-to-final-transcript proxy, not network-only STT latency. No P95 is calculated from four turns. These are **not mouth-to-ear PSTN measurements**, and the sub-500 ms target is not established by this rehearsal.

Attempt 7's corresponding final-transcript-to-first-carrier-audio values were 1,830.91, 1,421.40, 1,044.43, and 318.70 ms. The JSON retains per-turn durations calculated from `time.perf_counter()` at transcript receipt and first carrier-frame send; it does not retain the underlying monotonic timestamps for independent subtraction. The four attempt-6 values have min 220.93 ms, median 1,312.85 ms, and max 1,954.98 ms; no P95 is inferred.

## 14. Audio and framing

Level A asserted all outbound media payloads decode to exactly 3,200 bytes, with no `RIFF` WAV header, for 8 kHz, 16-bit, mono PCM at 200 ms per frame. Every scenario produced at least one frame; the happy path produced 12. Both successful Level B attempts requested 8 kHz raw PCM through Gnani's documented `audio_config` and verified all 130 outbound carrier frames were 3,200 bytes without a WAV header. Attempt 6's 130 frames comprise nine greeting frames plus 44, 29, 36, and 12 turn frames. Attempt 7 comprises nine greeting frames plus 43, 27, 39, and 12 turn frames. The local caller WAV was also verified as 8 kHz/16-bit/mono before ingestion. Actual provider sample rate cannot be measured from headerless PCM alone; 8 kHz is the requested format and carrier framing assumption.

## 15. Persistence and action safety

All business records were isolated in temporary SQLite databases, reset for each live attempt. Level A recorded one booking only for the happy path and duplicate-confirmation scenarios; negative, ambiguous, stale-slot, failure, and interruption scenarios recorded zero. There was no unsafe early commit, duplicate booking, or action left executing. In both successful Level B attempts, the call row and four turn metrics persisted, zero bookings existed before verbal confirmation, the action transitioned through `armed` to `committed`, and exactly one booking row existed afterward. Attempt 7 additionally verified the exact tenant/lead/slot/call relationships, slot state, and action-result equality inside the temporary database without recording identifiers. All five failed attempts had zero bookings. No external business write was attempted.

## 16. Qualitative turn behavior and telemetry

The Level A JSON carries a per-scenario checklist for response relevance, fixture grounding, false capability claims, confirmation clarity, interruption handling, repetition/awkwardness, and task continuity. Values indicate scripted assertions or “not human rated”; no human-likeness score or acoustic naturalness claim is made. The live run showed a relevant lead lookup, but was not long enough to grade natural conversation quality.

Local session/tool metrics include timing, tool names/outcomes, confirmation/commit counts, error categories, and interruption counts. Each continuation attempt submitted one safe post-call projection to the optional Langfuse exporter (`langfuse_exported_locally=1`); several shutdowns logged a sanitized exporter timeout. This is **local SDK submission, not proof of remote receipt**, and did not fail the call. The authoritative evidence remains the local metrics and deterministic harness. The Level B artifact retains recognized text from SAPI-generated synthetic utterances only, as requested for audit. Langfuse receives no transcript or audio; neither artifact contains a real caller identifier, tenant/lead ID, tool arguments, business record, or secret.

## 17. Limitations and next validation

Level A substitutes model, speech, and VAD interfaces and uses an in-memory carrier, so its clean dialogue cannot establish recognition quality, naturalness, provider availability, or physical call latency. Level B passed twice after two aborted provider attempts and two model-selection misses, so it is not a reliability estimate. The recorded Groq protocol-category event, Langfuse shutdown timeout, natural speech quality, carrier network transit, physical confirmation-prompt playback, underlying latency timestamps, and actual Gnani sample-rate verification beyond the requested config remain open. Verify carrier credits/account state before any Level C test. Retain the full failed-attempt series when presenting the successful runs.

## 18. Conclusion

The real session/business path passed all 12 deterministic spoken-session scenarios and preserved confirmation safety, persistence, carrier framing, and barge-in cancellation. Two complete live Gnani/Groq/Gnani local-loopback sales rehearsals passed the 20-point Level B gate with a confirmation-gated local booking. Level C remains untested. This evidence does not establish sub-500 ms PSTN latency or production reliability.

Post-review validation: OV-031 targeted tests 15/15; focused voice/agent/sales/resilience/Gnani/streaming/OV-030 suites 150/150; OV-011B offline evaluation 25/25 with four confirmed commits, zero unsafe commits, and zero duplicates; full pytest 279/279; Ruff clean; browser E2E 20/20; `scripts/verify-dod.ps1` 6/6 gates; `git diff --check` clean. These checks support the local-loopback rehearsals but do not establish provider reliability or PSTN latency.
