---
name: telephony-validation
description: >-
  Validates carrier media framing, audio transcoding, full-duplex interruption, VAD, and barge-in invariants when modifying or validating omnivoice/audio.py, omnivoice/media_gateway.py, omnivoice/duplex.py, omnivoice/transport.py, carrier webhook/WebSocket handling, STT/TTS streaming, or audio resampling.
---

# Telephony & Realtime Audio Validation Skill

Authoritative engineering invariants, carrier media requirements, full-duplex interruption protocols, and verification standards for OmniVoice audio pipelines.

Derived strictly from the working repository (`omnivoice/audio.py`, `omnivoice/transport.py`, `omnivoice/duplex.py`, `omnivoice/vad.py`, `omnivoice/providers.py`), existing tests (`tests/test_streaming.py`, `tests/test_media_gateway.py`), `docs/ARCHITECTURE.md`, and `docs/DEFINITION_OF_DONE.md`.

---

## 1. Classification of Telephony Claims

When evaluating, modifying, or reviewing telephony code, strictly categorize all metrics and behaviors:

* `[VERIFIED INVARIANT]`: Mathematically enforced or unit/integration tested in code (e.g. 3200-byte Exotel chunking, 8kHz-to-16kHz causal interpolation, two-phase action gating).
* `[DESIGN TARGET]`: Architectural goals documented in `docs/ARCHITECTURE.md` (e.g. sub-800ms mouth-to-ear latency, multi-provider failover).
* `[LOCAL BENCHMARK]`: Measured solely in local synthetic/loopback harnesses (e.g. exact FAQ cache hit < 10ms, local Silero VAD CPU inference ~2-5ms).
* `[UNVERIFIED PSTN BEHAVIOR]`: Real-world carrier phenomena that remain unvalidated until OV-005 real PSTN trials (e.g. cellular jitter buffers, PSTN echo cancellation, network packet loss).

> [!CAUTION]
> Never turn marketing targets or design goals into engineering acceptance criteria without empirical validation.

---

## 2. Carrier Ingress & Egress Invariants

### 2.1 Exotel Telephony (`omnivoice/transport.py`)
* **Media Format `[VERIFIED INVARIANT]`**: 8 kHz 16-bit linear PCM (`pcm_s16le`), mono, little-endian.
* **Framing Chunk Size `[VERIFIED INVARIANT]`**: Exactly **3200 bytes** per outbound media chunk (corresponding to 200 ms of audio at 1600 samples per chunk, 2 bytes/sample). Incoming audio chunks must be buffered and aligned to sample boundaries.
* **WebSocket Ingress `[VERIFIED INVARIANT]`**: Endpoint `/ws/exotel/{line_id}/{token}`. Exotel connects and exchanges JSON envelopes with `event`:
  - `start`: Initializes call metadata and stream SID.
  - `media`: Contains audio chunk data in base64 payload.
  - `stop`: Marks carrier disconnection and terminates audio streaming loops.
* **Interruption Clearing `[VERIFIED INVARIANT]`**: Upon interruption, the transport MUST immediately send `{"event": "clear"}` over the WebSocket to instruct the carrier gateway to flush unplayed audio packets from its buffer.

### 2.2 Twilio Telephony (`omnivoice/transport.py`, `omnivoice/audio.py`)
* **Media Format `[VERIFIED INVARIANT]`**: 8 kHz 8-bit G.711 $\mu$-law (`audio/x-mulaw`).
* **Framing Chunk Size `[VERIFIED INVARIANT]`**: Exactly **320 bytes** per frame (corresponding to 20 ms / 160 samples at 8 kHz).
* **Transcoding `[VERIFIED INVARIANT]`**:
  - Ingress: 8-bit $\mu$-law is decoded to 16-bit linear PCM via `audioop`/`omnivoice.audio.decode_mulaw`.
  - Egress: 16-bit linear PCM is transcoded to 8-bit $\mu$-law via `omnivoice.audio.encode_mulaw`.
* **Payload Envelopes `[VERIFIED INVARIANT]`**: Enclosed in JSON:
  - `{"event": "media", "streamSid": sid, "media": {"payload": base64_mulaw}}`
  - Playback synchronization: `{"event": "mark", "streamSid": sid, "mark": {"name": mark_id}}`
  - Interruption clearing: `{"event": "clear", "streamSid": sid}`
* **Authentication `[VERIFIED INVARIANT]`**: Webhooks authenticate via `X-Twilio-Signature` HMAC-SHA1 where configured.

---

## 3. Audio Resampling & Continuity

### 3.1 Causal Upsampling (`omnivoice/audio.py:Upsample8k`)
* **Invariant `[VERIFIED INVARIANT]`**: Conversion from 8 kHz to 16 kHz (required by Silero VAD and Sarvam STT) MUST be causal and stateful.
* **Phase Continuity `[VERIFIED INVARIANT]`**:
  - `Upsample8k` maintains the last sample of packet $N$ to interpolate the first sample of packet $N+1$.
  - State must **NOT** be reset across packet boundaries within the same call session. Resetting state per packet creates audible high-frequency clicks and phase discontinuities that degrade STT accuracy and VAD predictions.
  - State is reset ONLY when a session terminates or when explicitly re-initialized for a new call.

---

## 4. Full-Duplex Interruption & VAD Engine

### 4.1 Neural VAD (`omnivoice/vad.py`)
* **Frame Specification `[VERIFIED INVARIANT]`**: Silero VAD v4 ONNX model operates on CPU with 16 kHz audio in **1024-byte** frames (512 samples / 32 ms).
* **Isolated Recurrent State `[VERIFIED INVARIANT]`**: The recurrent hidden state tensor `(2, 1, 64)` must be preserved per-call and isolated across concurrent calls.
* **Speech Threshold `[VERIFIED INVARIANT]`**: Speech probability $\ge 0.6$ triggers acoustic speech detection.

### 4.2 Duplex State Machine (`omnivoice/duplex.py:FlexDuo`)
* **State Invariants `[VERIFIED INVARIANT]`**:
  - States: `IDLE`, `LISTENING`, `SPEAKING`.
  - Backchannel Filter: Spoken utterances matching configured backchannel tokens (e.g., *"yeah"*, *"ok"*, *"right"*, *"mm hmm"*, *"acha"*) MUST NOT interrupt active agent playback.
  - Genuine Interruption: When incoming caller speech is verified beyond backchannel tokens while in `SPEAKING` state, `FlexDuo` immediately transitions to interrupt state.
* **Buffer Purging `[VERIFIED INVARIANT]`**:
  1. Carrier buffer: Dispatches `{"event": "clear"}` to carrier WebSocket.
  2. Local egress queue: Flushes pending unplayed audio chunks from `audio_queue`.
  3. Upstream TTS provider: Instantly swaps from active to warm-standby Sarvam TTS WebSocket connection to abort generation without TCP/TLS re-handshake.

---

## 5. Session Lifecycle & Observability

* **Queue Bounding `[VERIFIED INVARIANT]`**: Audio queues (`vad_queue`, `audio_queue`) MUST have explicit bounds (e.g. `maxsize=100`) to prevent memory leaks during slow consumer scenarios.
* **Graceful Teardown `[VERIFIED INVARIANT]`**: When a call terminates (`stop` event, socket close, or error):
  - Background async tasks (`vad_loop`, `stt_loop`, `tts_loop`, `egress_loop`) must be cancelled and awaited.
  - WebSockets (carrier, Sarvam STT, Sarvam TTS) must be cleanly closed.
  - Temporary buffers and recurrent VAD states must be dereferenced.
* **Timing Telemetry `[VERIFIED INVARIANT]`**: Call metrics must record:
  - Turn transition timestamp.
  - `final_transcript_to_first_audio_sent_ms`.
  - Latency contributions from VAD, STT, LLM TTFT, and TTS TTFA.

---

## 6. Verification Checklist

Before accepting changes to telephony or audio code:
- [ ] `tests/test_streaming.py` passes.
- [ ] `tests/test_media_gateway.py` passes.
- [ ] Carrier payload framing matches exact byte alignments (3200 bytes for Exotel, 320 bytes for Twilio).
- [ ] Causal resampler preserves state across packet chunks without resets.
- [ ] Barge-in clear signal is dispatched upon confirmed interruption.
- [ ] No unhandled exceptions on unexpected socket closures.
