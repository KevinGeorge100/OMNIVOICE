# OmniVoice developer guide

This guide carries the implementation and setup details condensed from the repository's [README](../README.md). The [architecture reference](ARCHITECTURE.md), [project status](PROJECT_STATUS.md), and [deployment guide](DEPLOYMENT.md) are the deeper sources of record. OmniVoice remains a single-worker development/MVP system; nothing here implies a certified production deployment.

## Local environment

Python 3.11 is used for native FAISS and ONNX dependencies. On Windows, `.\start.ps1` from the repository root creates a virtual environment when absent, installs from `requirements.lock`, calls `omnivoice init`, and starts the server. Install the local Silero model with `omnivoice.cli models` once before the first start; the startup script does not download it. The embedded operations console is at `http://127.0.0.1:8000`.

For a manual setup from the repository root:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -c requirements.lock -e '.[dev,semantic]'
.\.venv\Scripts\python.exe -m omnivoice.cli init
.\.venv\Scripts\python.exe -m omnivoice.cli models --semantic
.\.venv\Scripts\python.exe -m omnivoice.cli serve
```

`init` generates a private `.env` with `OMNI_ADMIN_TOKEN`; it is not printed and `.env` is ignored by Git. Use that token to connect the console. Creating an enterprise shows its scoped API token once. Keep both tokens private. `models --semantic` downloads Silero and optional embedding weights for local use. Enable `OMNI_SEMANTIC_ENABLED=true` only after the semantic model is installed. Without it, approved exact FAQ lookup and lexical document retrieval remain available; the console must not claim semantic indexing is active.

Speech selection defaults to Sarvam for both directions. `STT_PROVIDER=gnani` enables Gnani Prisma transcription via its verified REST STT endpoint (`https://api.vachana.ai/stt/v3`), buffering utterances with VAD/energy thresholding and packaging them into standard 16 kHz WAV containers; streaming Prisma WebSocket support remains future work pending verified streaming protocol contracts. `TTS_PROVIDER=gnani` remains unimplemented and fails closed. Keep `TTS_PROVIDER=sarvam` for working calls. No Gnani TTS endpoint or streaming schema is assumed until an official API contract is verified.

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

Register business adapters through **Actions & tools** or the authenticated API. Tool URLs and schemas are administrator-owned; the model cannot supply an arbitrary destination or execute SQL from uploaded schemas. Calls use JSON POST against the registered schema. Read tools must truly be side-effect free.

Write tools must forbid additional properties, require every declared argument, and provide a confirmation template containing every argument as a simple `{field}` placeholder in the caller's language. The downstream service must honor `Idempotency-Key` durably and perform its own atomic transaction and availability revalidation. Return `{"ok": true, ...}` only after a confirmed commit. A timeout, malformed response, or missing positive acknowledgment is an **unknown** outcome to reconcile, not a reason for automatic retry.

An action proposal is bound to a tenant, call, arguments, and frozen tool configuration for 120 seconds. A completed playback mark arms it. Partial speech cannot commit it; an exact configured phrase on a subsequent completed caller turn can commit once. Interruption, another request, or call termination cancels uncommitted proposals. Once an external write has been dispatched, OmniVoice does not claim to roll it back.

`auth_env` can name an `OMNI_TOOL_...` environment variable; its value is sent as a bearer credential and not exposed through the console. The adapter requires public HTTPS endpoints, rejects private DNS results, pins the validated IP while preserving TLS SNI, and does not follow redirects. No clinic, CRM, calendar, or SMS account connector is fabricated in this repository.

## Evaluation and development checks

Call telemetry records final-transcript-to-first-outbound-audio time, a VAD-based voice-to-audio proxy, interruption-decision-to-carrier-clear time, retrieval, LLM, TTS, and other stage durations. These are server boundaries, not physical mouth-to-ear or carrier transit. Read [latency metric definitions](LATENCY_EVALUATION.md), the [56-turn live-gateway benchmark](OV006_BENCHMARK_RESULTS.md), and the [licensed corpus/replay contract](EVALUATION.md). Fisher and FD-Bench data are neither bundled nor fabricated.

```powershell
.\.venv\Scripts\python.exe -m pytest tests/ -q
.\.venv\Scripts\python.exe -m ruff check omnivoice tests
.\.venv\Scripts\python.exe tests/browser_check.py
.\.venv\Scripts\python.exe -m omnivoice.evaluation path\to\annotated-runs.jsonl --output artifacts\evaluation.json
```

The last command requires your own annotated input; it is not a benchmark result. `scripts/verify-dod.ps1` runs the repository's six-check release gate.

## Deployment boundary and open work

The backend has one process/worker, SQLite WAL, and process-local sessions and FAISS state. `Dockerfile` and `compose.yaml` package that architecture; they do not implement Kubernetes, distributed session routing, PostgreSQL, billing, granular RBAC, or compliance certification. Other open work includes Twilio live-call verification, multilingual and noise/overlap evaluation, provider recovery, action connector integration, call transfer, load testing, encrypted backups, and physical acoustic latency measurement. Track exact status in the [backlog](BACKLOG.md).

## Provider references

- [Exotel AgentStream](https://docs.exotel.com/exotel-agentstream), [VoiceBot flow](https://docs.exotel.com/exotel-agentstream/voicebot-applet), and [Exotel starter](https://github.com/exotel/voicebot-quick-starter).
- [Twilio Media Streams messages](https://www.twilio.com/docs/voice/media-streams/websocket-messages) and [request validation](https://www.twilio.com/docs/usage/security).
- [Sarvam realtime STT](https://docs.sarvam.ai/api/api-guides-tutorials/speech-to-text/realtime-streaming) and [TTS WebSocket](https://docs.sarvam.ai/api-reference/text-to-speech/stream). Verify raw linear16 behavior with your provider account before a live call.
- [Groq streaming](https://console.groq.com/docs/text-chat) and [model availability](https://console.groq.com/docs/models).
- [Gnani STT and Timbre TTS](https://docs.gnani.ai/api/TTS/tts-inference). Configure `GNANI_API_KEY`, `STT_PROVIDER=gnani`, and `TTS_PROVIDER=gnani` for optional Gnani speech services.
- [Silero VAD](https://github.com/snakers4/silero-vad), [FAISS](https://github.com/facebookresearch/faiss), and [FastEmbed](https://github.com/qdrant/fastembed).
