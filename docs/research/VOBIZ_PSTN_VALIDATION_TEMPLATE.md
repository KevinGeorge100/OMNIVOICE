# Vobiz real PSTN validation — first-call evidence

**Status: ONE successful controlled real inbound PSTN call (2026-10-26).** This is a bounded first-call observation, not a repeated-call reliability or latency study. No business action was attempted.

## Test identity

| Field | Observed value |
| --- | --- |
| Test date and time (with timezone) | 2026-10-26 12:48:49–12:49:30 IST; carrier CDR and local session timestamps |
| Test level | Real inbound PSTN, basic voice path |
| Provider | Vobiz |
| OmniVoice session ID | `b9d522814d5e43e4a4c77b5d08f12d19` (random internal ID) |
| Carrier call-log outcome | Answered inbound; cause `4000` / `Normal Hangup`, source `Caller`; 39 billed seconds |
| Local call status | `completed`, `carrier_disconnect`, approximately 39.2 seconds |
| Public endpoint class | Temporary Cloudflare Quick Tunnel; no protected URL retained |
| Operator | Project operator; caller identity omitted |

## Basic media-path evidence

| Check | Observation |
| --- | --- |
| Inbound DID reached the intended Voice Application | Yes; Vobiz CDR identifies an answered inbound call to the configured DID, and OmniVoice persisted the corresponding Vobiz media session. The DID is omitted here. |
| Answer callback returned valid XML | Real call proceeded to WSS; public synthetic preflight separately returned valid XML. Exact real callback body was not retained. |
| WSS stream opened with μ-law/8 kHz inbound audio | Vobiz media session established through the configured μ-law/8 kHz adapter; raw carrier audio was not retained. |
| Greeting heard at handset | Yes; operator confirmed the OmniVoice greeting was audible. |
| “Hello” recognized | Not independently verified. |
| OmniVoice overview question received a spoken answer | Yes; operator heard an answer after the greeting. No verbatim call content is retained. The operator also reported some stuttering and an unnatural conversational tone; speech quality was not formally scored. |
| “What languages do you support?” received a spoken answer | Not independently verified. |
| Session appeared Live in Console, then in Call history | Local record transitioned from active to completed; visual Console inspection was not part of this call record. |
| No unexpected booking or other write | Verified in local SQLite: zero tool invocations, zero staged actions, zero committed actions. |
| Carrier log and local session agree on end state | Yes: Vobiz reported normal caller hangup; OmniVoice recorded completed carrier disconnect. |

## Safe numerical evidence

| Metric | Value / source |
| --- | --- |
| Start time, end time and duration | Carrier: start 12:48:49 IST, 40-second duration, 39 billed seconds. Local: 12:48:51–12:49:30 IST, approximately 39.2 seconds. |
| Recorded turn count | 2 local turns; both show outbound audio bytes. Operator independently confirmed hearing at least one spoken answer after the greeting. |
| Barge-in count | 1 local event; acoustic quality not independently scored. |
| Server final-transcript-to-first-outbound-audio latency (per turn; P50/P95 only with sufficient samples) | Not reported as a PSTN latency statistic. |
| Tool names and read/write classification | No tool invoked. |
| Action state and confirmed/committed counts | 0 actions; 0 commits. |
| Carrier-side status | Answered; `4000` / `Normal Hangup`, source `Caller`. |

Server timing is **not** mouth-to-ear timing. Do not infer production reliability or a sub-500 ms PSTN result from a single call. The observations above distinguish local telemetry, the Vobiz CDR, and operator confirmation.

## Engineering observation and regression

A preceding real inbound attempt reached a Vobiz media session but ended before the greeting. OmniVoice recorded `audio_queue_overflow` after approximately 2.6 seconds. The receive loop could reject buffered frames before STT and VAD consumers drained its bounded queues; the exact carrier frame pattern was not retained. Commit `361e528` adds a maximum 250 ms wait for transient consumer backpressure while retaining the 32,000-byte per-queue ceiling and overload teardown; it adds deterministic buffered-frame coverage for Exotel and Vobiz. After the fix, the controlled call above completed. Focused validation passed 152 tests, the full suite passed 329 tests, Ruff and browser E2E passed, and the release gate passed 6/6. These checks do not establish population reliability.

## Business-action safety (not run over PSTN)

| Check | Observation |
| --- | --- |
| Demo line, lead, FAQs and future slots belong to the same tenant | Pending |
| Read-only lead and slot lookups | Pending |
| Booking proposal staged before any write | Pending |
| Matching uninterrupted playback receipt armed the proposal | Pending |
| Explicit caller verbal confirmation | Pending |
| Exactly one booking committed | Pending |
| Unsafe commits and duplicate bookings | Pending; expected zero |

## Privacy and claim boundary

Keep only provider, random session ID, timestamps, duration, turn count, tool names, action states, category-level errors, server latency metrics, and carrier outcome. Do **not** paste protected URLs, API keys, raw phone numbers, raw audio, transcripts, customer names, lead identifiers, tool arguments, or business records here. If transcript excerpts are essential to an academic report, obtain separate consent and anonymize them outside this template.

**Final verdict:** PASS for **one controlled inbound PSTN voice call only**. Carrier routing, media arrival, audible greeting and answer, recorded conversational turn handling, outbound audio dispatch, and normal termination were observed. The operator reported stuttering and unnatural tone; conversation tuning is deferred to separate work. Repeated-call reliability, PSTN latency performance, answer quality across callers, and business-action execution over PSTN remain unverified.

## Next manual validation sequence

1. **Call A — basic knowledge:** Say “Hello,” ask “What is OmniVoice?”, then ask “What languages do you support?” Record whether each answer is audible and grounded. No business action.
2. **Call B — barge-in:** Ask one normal question, interrupt OmniVoice once while it is speaking, then continue. Check playback clearing and conversational recovery. No business action.
3. **Call C — safe action:** Defer until Calls A and B are stable. In a separate controlled fixture, test a staged action, explicit verbal confirmation, one commit, and duplicate prevention.

No additional PSTN call was placed to create this evidence record.
