# OmniVoice developer guide

This guide carries the implementation and setup details condensed from the repository's [README](../README.md). The [architecture reference](ARCHITECTURE.md), [project status](PROJECT_STATUS.md), and [deployment guide](DEPLOYMENT.md) are the deeper sources of record. OmniVoice remains a single-worker development/MVP system; nothing here implies a certified production deployment.

## Local environment

Python 3.11 is used for native FAISS and ONNX dependencies. On Windows, `.\start.ps1` from the repository root creates a virtual environment when absent, installs from `requirements.lock`, calls `omnivoice init`, and starts the server. Install the local Silero model with `omnivoice.cli models` once before the first start; the startup script does not download it. The embedded operations console is at `http://127.0.0.1:8000`.

For a manual setup from the repository root:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -c requirements.lock -e '.[dev,semantic,mcp]'
.\.venv\Scripts\python.exe -m omnivoice.cli init
.\.venv\Scripts\python.exe -m omnivoice.cli models --semantic
.\.venv\Scripts\python.exe -m omnivoice.cli serve
```

`init` generates a private `.env` with `OMNI_ADMIN_TOKEN`; it is not printed and `.env` is ignored by Git. Use that token to connect the console. Creating an enterprise shows its scoped API token once. Keep both tokens private. `models --semantic` downloads Silero and optional embedding weights for local use. Enable `OMNI_SEMANTIC_ENABLED=true` only after the semantic model is installed. Without it, approved exact FAQ lookup and lexical document retrieval remain available; the console must not claim semantic indexing is active.

For a repeatable local presentation, use the isolated synthetic fixture and read-only preflight in the [final demo runbook](FINAL_DEMO_RUNBOOK.md). `scripts/seed_demo.py` creates `data/demo/omnivoice-demo.db`; `scripts/reset_demo.py --dry-run` previews a reset, and `scripts/demo_preflight.py` checks readiness. The app does not silently seed sample customers on startup. The fixture is not research evidence or a real caller record.

Speech selection defaults to Sarvam for both directions. `STT_PROVIDER=gnani` enables Gnani Prisma transcription via its verified REST STT endpoint (`https://api.vachana.ai/stt/v3`), buffering utterances with VAD/energy thresholding and packaging them into standard 16 kHz WAV containers; streaming Prisma WebSocket support remains future work pending verified streaming protocol contracts. `TTS_PROVIDER=gnani` enables Gnani Timbre streaming synthesis via its verified WebSocket endpoint (`wss://api.vachana.ai/api/v1/tts`), with dual-socket warm rotation for low-latency phrase streaming and immediate barge-in cancellation. Sarvam remains the default provider for both STT and TTS.

## Provider failure recovery

`PROVIDER_MAX_RETRIES=2`, `PROVIDER_BACKOFF_BASE_MS=150`, and `PROVIDER_BACKOFF_MAX_MS=1200` configure retries after the initial attempt. Limits are validated at startup; zero retries is valid. Classified timeouts, connection failures, HTTP 429, and HTTP 502/503/504 may retry with capped exponential backoff and jitter. Authentication failures, invalid requests, unsupported configuration, malformed payloads, and explicit cancellation do not retry. Failure and recovery logs contain provider, modality, attempt number, category, and delay, without credentials, caller audio, or transcript text.

Sarvam STT reconnects without replaying previously sent audio or transcript events. Gnani Prisma can resubmit the same buffered utterance, but produces one final transcript only after a successful response. Sarvam and Gnani TTS may retry a phrase only before yielding its first PCM; after partial PCM, they abort rather than replay speech. Groq may restart only before its first meaningful streamed delta; after a partial token or tool-call fragment, it aborts. Barge-in cancellation interrupts backoff, closes the active synthesis socket, and invalidates the carrier playback epoch. A failed standby socket never blocks an otherwise healthy active turn.

When STT recovery is exhausted, the session attempts a brief hearing-trouble message and ends the call; if synthesis is unavailable, it ends without waiting indefinitely. An exhausted LLM generation may speak a brief response-trouble message only if no audio from that generation reached the carrier. TTS failure after output clears playback and closes the call without repeating the phrase. Retry logic is confined to speech and LLM providers: it never repeats an action write. The existing staged → armed → confirmed → committed path and durable idempotency requirement remain in force. These are deterministic local failure-injection guarantees, not a measured physical PSTN outage-recovery latency.

## First live phone call

1. Set `OMNI_SARVAM_API_KEY` and `OMNI_GROQ_API_KEY` in your private `.env`. Confirm your accounts can access the configured `OMNI_STT_MODEL`, `OMNI_TTS_MODEL`, and `OMNI_GROQ_MODEL`; the defaults in [`.env.example`](../.env.example) are configuration, not a guarantee of provider availability.
2. Start the service and expose it through a public HTTPS origin that supports persistent WSS. Set `OMNI_PUBLIC_BASE_URL` to the origin with no path suffix, then restart.
3. Create an enterprise with its primary language, greeting, confirmation phrase, business documents, and approved FAQs. The repository does not seed invented customer facts.
4. For Exotel, register an existing number in **Phone lines**, retrieve its private WSS URL from **Connection details**, and configure that URL in an enabled AgentStream/VoiceBot flow. Registering a line does not buy a number or change carrier routing automatically.
5. Call the configured Exophone. Inspect call activity and carrier logs. A local readiness check confirms required settings/models, not remote credential validity or latency.

Twilio uses the signed `/telephony/twilio/{line_id}` webhook shown in **Connection details**. Set `OMNI_TWILIO_AUTH_TOKEN` for webhook validation. The resulting `<Connect><Stream>` uses the Twilio adapter; speech and inference still use Sarvam and Groq. Twilio live PSTN behavior remains to be verified.

Outbound dialing is opt-in. Set the Exotel account SID/API credentials and `OMNI_ENABLE_OUTBOUND=true`, restart, then use **Place a call** with an intended recipient and consent confirmation. Setup and automated tests do not place a call. See [deployment](DEPLOYMENT.md) for persistent single-worker hosting, TLS/WSS, and volume requirements.

## Media and duplex invariants

| Adapter | Carrier media | Outbound frame | Entry point |
| --- | --- | --- | --- |
| Exotel | 8 kHz signed 16-bit little-endian PCM, mono | 3,200 bytes = 200 ms | `/ws/exotel/{line_id}/{token}` |
| Twilio | 8 kHz G.711 μ-law | 320 bytes = 20 ms | Signed `/telephony/twilio/{line_id}` webhook → `/ws/twilio` |
| Generic gateway | Exotel-format PCM envelopes | 3,200 bytes = 200 ms | `/ws/audio` with line headers and bearer stream secret |

`omnivoice.audio.Upsample8k` carries interpolation state across inbound packet boundaries while converting to 16 kHz PCM for Silero and Sarvam. Per-call `vad_queue` and `audio_queue` are bounded. The Speak / Listen / Idle state machine combines acoustic candidates with transcript-level backchannel checks. An accepted interruption cancels response work, invalidates the carrier send epoch, and dispatches a `clear` envelope. The server cannot infer when a physical handset actually stops playback from that dispatch timestamp.

Both Sarvam TTS and Gnani Timbre TTS use an active WebSocket and warm standby socket. Closing the active socket on barge-in invalidates in-flight audio and rotates to the warm standby, preventing stale audio from leaking into subsequent turns. Closing the active socket and clearing carrier playback does not prove provider-side billed computation stopped. No model or carrier latency target should be presented as verified without measured call evidence. Sarvam remains the default provider.

## Knowledge and inference

`omnivoice.rag.Knowledge` maintains tenant-specific corpus snapshots and bounded speculative FAQ caches. Exact approved FAQs can bypass the foreground LLM. When optional embeddings are enabled and a semantic FAQ match is sufficiently confident, that path can also answer directly. Documents supply retrieved context, not arbitrary direct answers; the foreground answer can use Groq streaming inference. A background prediction task may warm up to five likely topics. Cache TTL and tenant revision checks prevent stale snapshots from being published after ingestion.

The Groq model defaults to `llama-3.1-8b-instant`, but availability is provider-account dependent. A sentence/clause segmenter and speech normalizer prepare streamed text for Sarvam TTS while preserving the raw agent response for call telemetry. The system does not guarantee a specific accent, language quality, or latency across all lines.

## Enterprise action contract

The agent-facing `ToolRegistry` describes capabilities with name, JSON input schema, kind, transport, timeout and optional output schema. A tool is a capability; an `ActionEngine` action is a persisted proposed invocation. The registry merges its built-in tenant read `get_business_profile` with administrator-registered HTTPS tools for that tenant. The built-in returns only the stored tenant business name and configured language; it does not invent sales hours or booking policy. The Groq model sees only this authorized catalog. A tool result is bounded to 4 KiB and malformed inputs, unknown names, oversized results and internal exceptions yield safe error codes rather than raw failures.

Read tools execute with a per-tool deadline (`OMNI_TOOL_TIMEOUT_MS`, default 3000, range 100–10000). Call interruption cancels in-flight reads. `OMNI_AGENT_MAX_TOOL_STEPS` defaults to 3 (range 1–8); after the last read the model gets one final pass without tools. Unexpected further calls receive a deterministic limitation response. The Groq tool result is returned as a tool-role message for the next reasoning pass. Tool events contain tenant/call, name, kind, transport, duration and status, without raw arguments or results.

Completed calls also persist a payload-free `tool_summary` in call metrics: invocation, success, failure, cancellation, confirmation-required, committed, unknown-outcome and speculative-cache-hit counts, plus total tool duration. These counters support later aggregate research. The `actions` table is authoritative for final write status, including a commit that finishes after call interruption; the external service must provide its own evidence for downstream duplicate execution.

Write tools continue through the existing `ActionEngine` staged → playback-armed → exact caller-confirmed → atomically claimed → committed/failed/unknown path. The registry only stages a write through ActionEngine; it never invokes a write handler itself. The external HTTPS service must honor `Idempotency-Key`. Timeouts after dispatch remain unknown and must be reconciled, not retried.

The optional `mcp==2.3.0` extra provides an official SDK client adapter. Set `OMNI_MCP_ENABLED=true` to connect to the bundled in-process reference server and set `OMNI_MCP_ALLOWED_TOOLS` to a comma-separated explicit allowlist (default `get_current_demo_policy`). Discovery is not authorization: only allowlisted tools with an MCP read-only annotation are exposed. The reference server returns a deterministic integration policy, no tenant data and no writes. MCP calls and discovery are bounded and cancelled with the turn; startup and shutdown own the provider. External MCP servers and MCP writes are not configured. They need a trusted transport/endpoint policy and an `ActionEngine`-backed write adapter in future work.

Register business adapters through **Actions & tools** or the authenticated API. Tool URLs and schemas are administrator-owned; the model cannot supply an arbitrary destination or execute SQL from uploaded schemas. Calls use JSON POST against the registered schema. Read tools must truly be side-effect free.

Write tools must forbid additional properties, require every declared argument, and provide a confirmation template containing every argument as a simple `{field}` placeholder in the caller's language. The downstream service must honor `Idempotency-Key` durably and perform its own atomic transaction and availability revalidation. Return `{"ok": true, ...}` only after a confirmed commit. A timeout, malformed response, or missing positive acknowledgment is an **unknown** outcome to reconcile, not a reason for automatic retry.

An action proposal is bound to a tenant, call, arguments, and frozen tool configuration for 120 seconds. A completed playback mark arms it. Partial speech cannot commit it; an exact configured phrase on a subsequent completed caller turn can commit once. Interruption, another request, or call termination cancels uncommitted proposals. Once an external write has been dispatched, OmniVoice does not claim to roll it back.

`auth_env` can name an `OMNI_TOOL_...` environment variable; its value is sent as a bearer credential and not exposed through the console. The adapter requires public HTTPS endpoints, rejects private DNS results, pins the validated IP while preserving TLS SNI, and does not follow redirects. No clinic, CRM, calendar, or SMS account connector is fabricated in this repository.

## OV-011B local sales workflow

The sales tools are enabled with normal application startup and use the existing SQLite database. Seed test/demo data explicitly with `SalesService.add_lead()` and `SalesService.add_slot()`; startup does not insert sample customers or appointments. Tenant-authenticated operators can create leads with `POST /api/tenants/{tenant_id}/leads` and timezone-aware available slots with `POST /api/tenants/{tenant_id}/demo-slots`. A lead must be found by an exact caller-supplied identifier, and an available slot must be offered during the current call before `schedule_demo` can stage. Booking and follow-up require the tenant's exact confirmation phrase after the confirmation prompt has finished playing. `schedule_demo` makes one conditional, tenant-scoped slot update and booking insert in a SQLite transaction. Stale slots return a definite failure and are never spoken as booked.

Run the offline evaluation with `python scripts/evaluate_agent_tools.py`. It writes measured results to `data/research/agent_tool_eval.json` and the accompanying methodology to `docs/research/OV-011B_AGENT_EVALUATION.md`. The JSON contains no raw transcript or caller identifiers. The harness uses scripted tool requests and isolated tenant fixtures; live Groq model selection and PSTN timing remain separate validation tasks. The Operations Console lists local tools and the existing action timeline; no new connector or MCP network capability is enabled.

## OV-029 opt-in Langfuse research observations

The research exporter is off by default. Install the optional SDK with `python -m pip install -e '.[research]'`, configure `OMNI_LANGFUSE_PUBLIC_KEY`, `OMNI_LANGFUSE_SECRET_KEY`, and an HTTPS `OMNI_LANGFUSE_BASE_URL` in the private `.env`, then run `python scripts/evaluate_agent_tools.py --langfuse` to export the 25 scripted cases. This exports static case/category labels, tool names from an allowlist, measured tool/action status, and numeric case scores. It does not export synthetic lead names, phone numbers, tool arguments, answers, or any private business knowledge. Without `--langfuse`, the evaluation behaves as before and performs no Langfuse setup.

To add completed-call metric summaries, set `OMNI_RESEARCH_OBSERVABILITY_ENABLED=true` and restart the backend. On call teardown, an allowlisted projection enters a 64-item process-local queue; a background worker emits numeric server timing/proxy values, counts, fixed carrier/status categories, and at most 20 recent turns. Queue saturation drops research telemetry and increments a counter. Exporter setup or delivery failure does not affect call admission, audio streaming, action confirmation, or `/readyz`. Administrators can inspect `research_observability` in `/api/status`; tenant tokens cannot see that global exporter state. The export contains no call ID, tenant ID, caller identifier, transcript, audio, tool payload, or knowledge text.

Langfuse is an external destination. Enable it only for data you intend to send there. SDK v5 requires Langfuse Cloud v4 or a compatible self-hosted v4 server; see the [Langfuse SDK compatibility guide](https://langfuse.com/docs/observability/sdk/overview). The current integration is research telemetry, not distributed production tracing (OV-017). A later **synthetic, non-PII remote ingestion smoke** was reported for OV-029; the repository does not retain per-case remote receipt evidence for OV-030 or OV-031, so local artifacts remain authoritative. The timing values remain server-observed boundaries rather than physical mouth-to-ear latency. See [OV-029 research observability methodology](research/OV-029_LANGFUSE_OBSERVABILITY.md) and the [final evidence index](research/FINAL_EVIDENCE_INDEX.md).

## Evaluation and development checks

Call telemetry records final-transcript-to-first-outbound-audio time, a VAD-based voice-to-audio proxy, interruption-decision-to-carrier-clear time, retrieval, LLM, TTS, and other stage durations. These are server boundaries, not physical mouth-to-ear or carrier transit. Read [latency metric definitions](LATENCY_EVALUATION.md), the [56-turn live-gateway benchmark](OV006_BENCHMARK_RESULTS.md), and the [licensed corpus/replay contract](EVALUATION.md). Fisher and FD-Bench data are neither bundled nor fabricated.

```powershell
.\.venv\Scripts\python.exe -m pytest tests/ -q
.\.venv\Scripts\python.exe -m ruff check omnivoice tests
.\.venv\Scripts\python.exe tests/browser_check.py
.\.venv\Scripts\python.exe -m omnivoice.evaluation path\to\annotated-runs.jsonl --output artifacts\evaluation.json
```

The last command requires your own annotated input; it is not a benchmark result. `scripts/verify-dod.ps1` runs the repository's six-check release gate.

## Capacity and overload controls

OmniVoice implements local process-level admission, provider concurrency gating, audio backpressure, and API rate limiting via `omnivoice.capacity.Capacity`. These controls protect the single Python process against exhaustion under high load:

- **Single-process scope**: All limits and meters are held in memory within the local process. They are NOT distributed rate limits across multiple workers, Redis, or cloud instances. Multi-worker coordination and PostgreSQL-backed quotas remain future work.
- **Call admission**: Global concurrent calls are bounded by `MAX_CALLS` (default 20). Per-tenant active calls are bounded by `TENANT_MAX_CALLS` (default 5). Inbound WebSockets (`/ws/exotel`, `/ws/twilio`, `/ws/audio`) atomically acquire capacity before session startup; saturated requests are rejected with WebSocket close code 1013 (`local_capacity_exhausted` or `tenant_capacity_exhausted`). Releasing a call decrements counters exactly once and cleans up tenant map entries.
- **Outbound dial admission pre-check**: `POST /api/tenants/{tenant_id}/dial` performs a best-effort pre-check against global saturation and `tenant_max_calls`, returning HTTP 503 (`Retry-After: 1`) if exhausted. Because carrier media streams connect asynchronously after dialing, actual admission is authoritatively enforced when the inbound carrier WebSocket arrives. Concurrent dial requests could both pass the initial check before either WebSocket connects; carrier WebSocket admission remains the authoritative gatekeeper.
- **Provider concurrency gating**: External provider calls are gated by modality-scoped asyncio semaphores:
  - `MAX_LLM_INFLIGHT` (default 12)
  - `MAX_TTS_INFLIGHT` (default 12)
  - `MAX_STT_INFLIGHT` (default 8)
  Acquiring a provider slot enforces a bounded wait timeout of 50 ms. If no slot becomes free within 50 ms, `ProviderCapacityError` is raised immediately to prevent unserviced queue pileups. When cancelled during wait, resources and waiters are cleanly released without leaking counters.
- **Audio queue backpressure**: Session `audio_queue` and `vad_queue` enforce `maxsize=32` packets and an aggregate byte ceiling of 32,000 bytes. When incoming audio backpressure exceeds 32,000 bytes without being drained, the call is terminated deterministically with WebSocket close code 1013 and `end_reason="audio_queue_overflow"`. The call slot is released immediately in the `finally` block.
- **Gnani STT backpressure**: `GnaniSTT._events` is capped at `maxsize=8` (dropping the oldest entry if full on close to avoid deadlocks). Concurrently running background transcription tasks are limited to 2 (`_pending_tasks`); a third concurrent attempt raises `ProviderCapacityError`. All pending tasks are cleanly cancelled on session teardown without unretrieved task exception warnings.
- **HTTP 429 Retry-After parsing**: Provider rate limits parsing handles integer seconds, decimal seconds, and RFC 7231 HTTP-date formats. If `Retry-After` is missing or malformed, the system falls back to configured exponential backoff. Excessive `Retry-After` delays are capped at `PROVIDER_BACKOFF_MAX_MS`. Explicit cancellation interrupts the retry sleep immediately.
- **API rate limits**: REST API routes enforce fixed 60-second sliding window limits with automatic memory pruning (capped at 2,048 keys):
  - Failed authentication: 20/min per client IP (HTTP 429)
  - Tenant creation: 30/min for administrators (HTTP 429)
  - FAQ and document writes: 12/min per tenant (HTTP 429)
  - Analytics queries: 60/min per tenant (HTTP 429)
  - Outbound dialing: 6/min per tenant (HTTP 429)
- **Readiness vs. saturation**: `/readyz` evaluates whether required models and provider configurations are present (`voice_ready`). Saturated call capacity returns 200 on `/readyz` but rejects incoming calls with 1013 / 503, ensuring orchestrators (e.g. Kubernetes, Docker) do not restart healthy saturated instances.
- **Observability and tenant isolation**: `GET /api/status` for administrators includes the full process capacity snapshot (`global_call_limit`, `tenant_call_limit`, active calls, rejection counters, provider in-flight counts, provider concurrency rejections, and last wait latencies). Tenant tokens see only their own tenant's active call count and `tenant_call_limit` (`scope="tenant_single_process"`), preventing cross-tenant information leakage.

## Deployment boundary and open work

The backend has one process/worker, SQLite WAL, and process-local sessions and FAISS state. `Dockerfile` and `compose.yaml` package that architecture; they do not implement Kubernetes, distributed session routing, PostgreSQL, billing, granular RBAC, or compliance certification. Other open work includes Twilio live-call verification, multilingual and noise/overlap evaluation, live PSTN provider-outage rehearsal, action connector integration, call transfer, load testing, encrypted backups, and physical acoustic latency measurement. Track exact status in the [backlog](BACKLOG.md).

## Provider references

- [Exotel AgentStream](https://docs.exotel.com/exotel-agentstream), [VoiceBot flow](https://docs.exotel.com/exotel-agentstream/voicebot-applet), and [Exotel starter](https://github.com/exotel/voicebot-quick-starter).
- [Twilio Media Streams messages](https://www.twilio.com/docs/voice/media-streams/websocket-messages) and [request validation](https://www.twilio.com/docs/usage/security).
- [Sarvam realtime STT](https://docs.sarvam.ai/api/api-guides-tutorials/speech-to-text/realtime-streaming) and [TTS WebSocket](https://docs.sarvam.ai/api-reference/text-to-speech/stream). Verify raw linear16 behavior with your provider account before a live call.
- [Groq streaming](https://console.groq.com/docs/text-chat) and [model availability](https://console.groq.com/docs/models).
- [Gnani STT and Timbre TTS](https://docs.gnani.ai/api/TTS/tts-inference). Configure `GNANI_API_KEY`, `STT_PROVIDER=gnani`, and `TTS_PROVIDER=gnani` for optional Gnani speech services.
- [Silero VAD](https://github.com/snakers4/silero-vad), [FAISS](https://github.com/facebookresearch/faiss), and [FastEmbed](https://github.com/qdrant/fastembed).
