# Vobiz real PSTN validation — evidence template

**Status: NOT RUN.** This file is a blank record for a future, manually placed call. Synthetic adapter tests and public webhook probes do not satisfy this validation.

## Test identity

| Field | Value to record after the call |
| --- | --- |
| Test date and time (with timezone) | Pending |
| Test level | First-call basic media / second-call business action |
| Provider | Vobiz |
| OmniVoice session ID | Pending — use the random internal session ID only |
| Carrier call-log outcome | Pending — inspect Vobiz Console separately |
| Local call status | Pending — this is not itself carrier-confirmed completion |
| Public endpoint class | Temporary Quick Tunnel / persistent deployment; no protected URL |
| Operator | Pending — use a role or pseudonym, not a personal identifier |

## Basic media-path evidence

| Check | Observation |
| --- | --- |
| Inbound DID reached the intended Voice Application | Pending |
| Answer callback returned valid XML | Pending |
| WSS stream opened with μ-law/8 kHz inbound audio | Pending |
| Greeting heard at handset | Pending |
| “Hello” recognized | Pending |
| “What is OmniVoice?” received a spoken answer | Pending |
| “What languages do you support?” received a spoken answer | Pending |
| Session appeared Live in Console, then in Call history | Pending |
| No unexpected booking or other write | Pending |
| Carrier log and local session agree on end state | Pending |

## Safe numerical evidence

| Metric | Value / source |
| --- | --- |
| Start time, end time and duration | Pending |
| Recorded turn count | Pending |
| Server final-transcript-to-first-outbound-audio latency (per turn; P50/P95 only with sufficient samples) | Pending |
| Tool names and read/write classification | Pending; first call should have no write |
| Action state and confirmed/committed counts | Pending; first call should have zero commits |
| Carrier-side status | Pending |

Server timing is **not** mouth-to-ear timing. Do not infer production reliability or a sub-500 ms PSTN result from a single call. If a stage fails, keep the failure in the record and state whether the result came from OmniVoice telemetry, the Vobiz call log, or operator observation.

## Second-call action safety (complete only after basic media passes)

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

**Final verdict:** PENDING — do not change to PASS until a real inbound PSTN call has succeeded and the carrier-side record has been checked.
