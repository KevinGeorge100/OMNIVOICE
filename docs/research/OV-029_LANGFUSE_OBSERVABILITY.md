# OV-029 Langfuse Research Observability

## Scope and evidence

The optional adapter has two sources. The offline source is the existing 25-case scripted sales-tool evaluation: it runs the real local `ToolRegistry`, `ActionEngine`, and isolated SQLite stores, but does not exercise model tool selection, speech, or PSTN. Each case creates an `agent` observation, each invoked tool creates a `tool` observation, and action confirmation creates a separate span. `scripted_task_completed` and `unsafe_commit_count` scores come from the measured case record. A safe rejection counts as expected task completion when the case label requires it. No model-selection accuracy score is emitted because the model did not select tools in this harness.

The live source is a post-call numeric projection of existing server metrics. It is enqueued only after the call's persisted status and metrics are finalized. The WebSocket/audio path never waits for Langfuse. The exporter stores at most 64 queued calls; overflow drops telemetry and increments `dropped`. At most the latest 20 turns are exported per call, with `turns_recorded`, `turns_exported`, and `turns_truncated` indicating coverage. `exported` counts local SDK submissions, **not confirmed remote ingestion**. `failures` counts local projection/export exceptions. All state is process-local.

## Data boundary

The live projection is built from an explicit numeric field allowlist: STT endpoint delay, retrieval/RAG duration, LLM TTFT, TTS first-audio time, carrier framing delay, final-transcript-to-first-outbound-audio, VAD-to-audio proxy, and segment counts. It also includes bounded counts of errors, cache hits, barge-ins, and tool/action outcomes, plus fixed categories for carrier, status, and path. Values with invalid numeric types, negative values, or non-finite values are omitted. Raw session metrics are never passed to the SDK. The export omits call/tenant IDs, phone numbers, transcripts, audio, prompts, responses, document text, tool arguments, and provider credentials. The offline source exports only fixture case IDs/categories and allowlisted tool labels; the fixture's lead names and numbers remain local.

The SDK exporter filters OpenTelemetry spans by the five explicit research observation names, so unrelated process instrumentation is not forwarded to Langfuse by this client. Live observations use manual start/end calls, avoiding automatic exception capture from the call path.

## Interpretation and limitations

These observations are research summaries, not a replayable conversation log. The post-call Langfuse child spans mark when recorded metrics were exported; their span durations do **not** reconstruct the original turn duration. Timing fields retain the definitions in [LATENCY_EVALUATION.md](../LATENCY_EVALUATION.md) and cannot establish acoustic mouth-to-ear performance or carrier transit. The scripted evaluation cannot establish live model-selection accuracy or PSTN sales-workflow quality. No Langfuse account, remote ingest response, or physical PSTN call was used for this milestone's local tests.

The exporter is disabled by default. Use the optional `research` dependency and private `OMNI_LANGFUSE_*` credentials to opt in. The tests use a fake client to verify the schema, redaction, queue bound, tenant status isolation, and carrier teardown hook without external calls. The repository's general release gate validates that the baseline product still works. Production distributed tracing remains the separate OV-017 backlog item; OV-012 retains PostgreSQL migration.
