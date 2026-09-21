# ADR-001: State-Aware Turn-Taking and Continuation Coalescing

Status: Accepted
Date: 2026-09-21
Deciders: Kevin George, DeepMind Antigravity Engineering Team

## Context
During OV-005 PSTN validation on physical mobile and landline telephone networks (Call #2), 8 of 10 conversational turns were falsely classified as `interrupted: true`. While intentional barge-in (`"Wait"`) and configured backchannel suppression (`"yeah"`) functioned correctly, natural intra-utterance pauses by callers (e.g. 200–300ms hesitation gaps) triggered sequential `transcript.final` events from Sarvam STT (`endpoint_silence_ms = 200`).

Under the previous runtime architecture, `Session.transcripts()` unconditionally invoked `await self.interrupt()` whenever any `transcript.final` was received while an existing response task was in flight. Because RAG retrieval and Groq LLM TTFT require ~500–800ms before first audio synthesis, rapid continuation fragments from the same caller thought (e.g., `"Book me"` followed 400ms later by `"Uh, dedicate."`, or `"Hello"` followed by `"I would like to book an Omni voice subscription."`) arrived while generation was active (`self.response and not self.response.done()`) but before any audio reached the carrier (`self.fsm.playing == False`).

This caused severe turn-taking thrashing:
1. In-flight LLM generations were repeatedly cancelled before sending any audio to the caller.
2. Cancelled tasks were erroneously persisted in `self.metrics["turns"]` as interrupted turns.
3. Spurious carrier `{"event": "clear"}` frames were dispatched over WebSocket to Exotel despite empty carrier buffers.
4. False entries were recorded in `self.metrics["barge_in"]`.
5. Leading context was discarded, causing the model to answer trailing speech fragments in isolation.

## Decision
We establish an explicit architectural distinction between **playback-stage acoustic barge-in** and **generation-stage turn formulation**:

1. **Carrier Clear & Barge-In Invariant**: Carrier `clear` events and `barge_in` telemetry are strictly coupled to active acoustic playback (`self.fsm.playing == True`). Collisions during generation (`self.fsm.playing == False`) represent utterance formulation or pre-speech control and must never dispatch carrier clear events or record false barge-in latency metrics.
2. **Immediate Turn Initialization**: The initial `transcript.final` launches response generation immediately (zero arbitrary debounce latency).
3. **Bounded Generation Continuation**: If a subsequent `transcript.final` arrives while generation is active and before audio playback begins:
   - If the elapsed time since the previous final is within the configurable continuation window (`continuation_interval_ms`, default 750ms), the pending generation is cleanly superseded without carrier clear or barge-in metrics, caller text fragments are concatenated, and generation is restarted with the unified thought.
   - If outside the continuation window, the pending generation is superseded without concatenation, restarting on the new conversational query.
4. **Generation Control Intent**: Explicit halt tokens (`wait`, `stop`, `hold on`, `pause`, `cancel`) received while generation is active but before playback begins are treated as control intent. The pending generation is cancelled cleanly without carrier clear, without barge-in telemetry, without generating an AI answer, and without persisting an aborted turn, leaving the session idle and ready for the caller's next utterance.
5. **State Ownership & Generation Isolation**: A monotonically increasing `generation_id` and explicit cancellation reasons (`PLAYBACK_INTERRUPT`, `SUPERSEDED`, `CONTROL_HALT`) ensure that stale cancelled tasks never corrupt the state or history of newer generation tasks.

## State Invariant
* Carrier `clear` frames and `barge_in` telemetry records must correspond solely to the interruption of audible agent playback (`self.fsm.playing == True`).
* An uncompleted generation cancelled prior to audio output (`self.fsm.playing == False`) is not a conversational turn and must not be persisted as an interrupted turn in `metrics["turns"]` or leave uncompleted user entries in `self.history`.

## Generation-Stage Continuation Behavior
* If `response_active and not self.fsm.playing`:
  * If `is_control_halt(text)`: Generation is cancelled with `CONTROL_HALT`. Pending text is cleared.
  * If `now - self.pending_final_time <= continuation_interval_s`: Generation is cancelled with `SUPERSEDED`. Pending text is coalesced (`f"{pending} {text}"`). Generation restarts on coalesced text with an incremented `generation_id`.
  * If `now - self.pending_final_time > continuation_interval_s`: Generation is cancelled with `SUPERSEDED`. Pending text is replaced with `text`. Generation restarts on the new query.

## Playback-Stage Barge-In Behavior
* Preserves existing `FlexDuo` acoustic-to-semantic arbitration:
  * While `self.fsm.playing == True`, non-backchannel semantic speech detected with VAD candidate sets `self.fsm.transcript(text) == True`.
  * `interrupt()` cancels response, sends carrier `clear`, cancels TTS, records true `barge_in` decision-to-clear latency, and sets `metric["interrupted"] = True`.

## Backchannel Behavior
* Configured tenant backchannels (`"yeah"`, `"mm hmm"`) received during active playback are suppressed by `FlexDuo`.
* Playback continues uninterrupted without carrier clear or response cancellation.

## Control-Intent Behavior
* Recognized control phrases: `wait`, `stop`, `hold on`, `pause`, `cancel` (case- and punctuation-normalized).
* When received during generation: Cancels in-flight generation cleanly, suppresses audio output, records no barge-in, does not query LLM for a substantive answer to the control word, and keeps session in `LISTEN` state for subsequent input.
* When received during active playback: Immediately halts audible speech via the standard playback barge-in path.

## Consequences

### Positive
* Eliminates turn-taking thrashing on rapid continuation speech.
* Corrects turn metrics: only genuine caller interruptions during active playback are flagged `interrupted: true`.
* Prevents spurious carrier `clear` WebSocket messages.
* Eliminates false `barge_in` latency telemetry.
* Preserves zero added latency for ordinary single-utterance turns.
* Preserves immediate legitimate barge-in during playback.

### Negative / Trade-offs
* If a caller speaks a multi-part thought with micro-pauses, the initial generation started on the first fragment is discarded and restarted when the continuation arrives within 750ms. This consumes minor additional LLM token quota for in-flight tokens before cancellation, which is an acceptable trade-off for natural conversational turn-taking.

## Rejected Alternatives
1. **Ignoring all short transcripts (< 2 words)**:
   * Rejected: Destroys single-word legitimate utterances such as `"Wait"`, `"Stop"`, `"No"`, `"Yes"`, `"Hello"`, `"Repeat"`, and `"Why?"`.
2. **Arbitrary global debounce before every response**:
   * Rejected: Adds 300–500ms of unconditional latency to every single turn, degrading the platform's sub-second target TTFA.
3. **Treating every `transcript.final` as a new acoustic barge-in**:
   * Rejected: Conflates generation with playback; caused 80% false interruption rates in Call #2.
4. **Indefinitely concatenating every final received during generation**:
   * Rejected: Merges unrelated intents if generation takes longer, combining distinct queries (e.g. `"What are your hours?"` followed 2s later by `"Actually, what about pricing?"`).

## Follow-up & Dependencies
* Backlog Item: `OV-005` (Real PSTN Telephony Validation)
* Regression Suite: `tests/test_streaming.py` (15 deterministic turn-taking and duplex test cases)
