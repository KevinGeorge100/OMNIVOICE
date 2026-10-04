# OV-006 Live Gateway Server-Latency Benchmark

> [!IMPORTANT]
> **RESEARCH LABELLING & SCOPE CAVEAT**
> This dataset is strictly a **LIVE GATEWAY SERVER-LATENCY BENCHMARK**.
> It measures server-side turnaround, upstream neural provider delays (LLM TTFT & TTS TTFA), local RAG retrieval, speech buffering, and gateway transport serialization.
>
> It is **NOT**:
> - Physical acoustic mouth-to-ear latency (no acoustic coupler hardware used).
> - PSTN end-to-end latency or carrier network transit delay.
> - Certified carrier latency (Exotel live carrier PSTN re-validation was unavailable due to trial credit exhaustion and commercial GST/KYC requirements for replenishment).
>
> Historical OV-005 PSTN validation remains separate historical evidence.

---

## Method
The benchmark exercises live, bidirectional conversational voice turns through the full OmniVoice server stack:
1. **Turn Orchestration**: Inbound conversational turns driven through `CallSession` with active `Silero` VAD, `Groq` LLM streaming, `Sarvam` streaming TTS WebSocket, and FAISS vector RAG / Exact keyword caching.
2. **Gateway Transport**: Full `MediaTransport` media framing engine packaging linear PCM audio into Exotel-standard 3200-byte (200 ms) carrier frames over WebSocket channels.
3. **Telemetry Capture**: Server timestamps recorded using monotonic high-resolution hardware counters (`time.perf_counter()`), calculating exact phase boundaries and privacy-preserving numeric telemetry.

---

## Environment
- **Platform**: Windows 11 (AMD64), Python 3.11.9
- **Storage / Database**: SQLite 3 (`data/omnivoice.db`), FAISS L2 Vector Index (`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`)
- **LLM Provider & Model**: Groq Cloud (`openai/gpt-oss-20b`), temperature 0.1, streaming JSON / SSE
- **TTS Provider & Voice**: Sarvam AI Streaming WebSocket (`bulbul:v3`, speaker `shubh`, 8 kHz 16-bit linear PCM mono)
- **VAD Provider**: Silero VAD v5 (ONNX Runtime, 512-sample frame window)
- **Carrier Framing**: Exotel AudioStreams specification (3200 bytes per frame, 8 kHz 16-bit mono PCM = 200 ms per frame payload)

---

## Provider Realism Matrix

| Pipeline Component | Execution Mode | Description |
| :--- | :--- | :--- |
| **LLM Generation** | **REAL PROVIDER** | Live streaming inference against Groq Cloud API (`openai/gpt-oss-20b`). |
| **TTS Synthesis** | **REAL PROVIDER** | Live streaming synthesis over Sarvam AI WebSocket (`bulbul:v3`). |
| **RAG Retrieval** | **LOCAL PROCESS** | Live in-memory FAISS L2 vector similarity search + SQLite exact match lookup. |
| **Speech Segmenter** | **LOCAL PROCESS** | Live sentence/clause accumulation buffer (`SpeechSegmenter`, OV-023). |
| **Carrier Media Transport** | **GATEWAY HARNESS** | Live `MediaTransport` frame buffer, pacing, and WebSocket dispatch. |
| **VAD / STT Endpointing** | **HARNESS OFFSET** | 120 ms synthetic trailing silence offset representing speech finalization. |
| **Limitation Responses** | **DETERMINISTIC** | Bounded dialogue handling for unsupported actions / missing facts (OV-024). |

---

## Dataset
- **Total Sessions**: 6 unique conversational calls (IDs: `712b7a42`, `8fca32b2`, `0793163d`, `58157f9a`, `2df0eef6`, `1084adc7`).
- **Total Turns Collected**: 56 turns across diverse enterprise university support scenarios.
- **Valid Turns Accepted**: 56 turns (100% completion yield).
- **Excluded Turns**: 0 turns (no runtime errors, transport aborts, or incomplete telemetry).

### Path Breakdown
- **Fast FAQ Cache (`fast_cache`)**: 18 turns (32.1%) — Direct keyword match bypassing LLM.
- **Foreground RAG (`foreground_rag`)**: 38 turns (67.9%)
  - *Standard RAG + LLM streaming*: 36 turns (64.3%) — Retrieval + Groq generation + Sarvam TTS.
  - *Deterministic Scripted Limitation*: 2 turns (3.6%) — Direct refusal rule before LLM invocation.

---

## Metric Definitions

- `stt_endpoint_delay_ms`: Elapsed time between user speech offset and STT final transcript event (configured at 120 ms in test harness).
- `retrieval_ms`: High-resolution lookup duration for exact/semantic cache layer.
- `rag_retrieval_ms`: Vector similarity search and context formatting duration in FAISS/SQLite.
- `llm_ttft_ms`: Upstream LLM Time-To-First-Token from prompt dispatch to first token reception.
- `speech_buffer_delay_ms`: Time spent accumulating tokens until the first stable speech clause boundary is formed (OV-023).
- `tts_ttfa_ms`: Upstream TTS Time-To-First-Audio from text segment submission to first PCM chunk reception.
- `carrier_framing_delay_ms`: Local frame buffering and base64 packet preparation delay before socket dispatch.
- `server_processing_turnaround_ms`: Total server response latency from final transcript reception to first outbound audio frame transmission (`final_transcript_to_first_audio_sent_ms`).
- `server_voice_to_audio_ms`: Server-side proxy turnaround from last VAD-positive speech frame to first outbound audio frame transmission (`last_vad_speech_to_first_audio_sent_ms`).

---

## Overall Results (N=56)

All percentiles computed using nearest-rank formulation ($k = \lceil P \times N \rceil$):

| Metric | N | Mean (ms) | Std (ms) | Min (ms) | P50 (ms) | P90 (ms) | P95 (ms) | Max (ms) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `stt_endpoint_delay_ms` | 56 | 120.00 | 0.00 | 120.00 | 120.00 | 120.00 | 120.00 | 120.00 |
| `retrieval_ms` | 56 | 0.05 | 0.05 | 0.01 | 0.03 | 0.13 | 0.15 | 0.18 |
| `rag_retrieval_ms` | 38 | 1.07 | 1.13 | 0.24 | 0.64 | 3.30 | 3.93 | 5.06 |
| `llm_ttft_ms` | 36 | 666.55 | 262.52 | 418.26 | 616.00 | 819.49 | 1249.76 | 1954.99 |
| `speech_buffer_delay_ms` | 36 | 19.11 | 10.19 | 3.67 | 17.86 | 30.50 | 42.51 | 46.74 |
| `tts_ttfa_ms` | 56 | 270.49 | 251.96 | 202.71 | 218.35 | 302.33 | 338.82 | 2103.26 |
| `carrier_framing_delay_ms` | 56 | 0.15 | 0.11 | 0.06 | 0.09 | 0.37 | 0.43 | 0.48 |
| `server_processing_turnaround_ms` | 56 | 714.23 | 428.02 | 210.62 | 774.76 | 1019.79 | 1466.88 | 2210.50 |
| `server_voice_to_audio_ms` | 56 | 834.23 | 428.02 | 330.62 | 894.76 | 1139.79 | 1586.88 | 2330.50 |

---

## Fast FAQ Results (`fast_cache`, N=18)

| Metric | N | Mean (ms) | Std (ms) | Min (ms) | P50 (ms) | P90 (ms) | P95 (ms) | Max (ms) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `retrieval_ms` | 18 | 0.05 | 0.04 | 0.01 | 0.03 | 0.12 | 0.13 | 0.13 |
| `tts_ttfa_ms` | 18 | 354.87 | 437.99 | 209.99 | 260.24 | 338.82 | 2103.26 | 2103.26 |
| `carrier_framing_delay_ms` | 18 | 0.17 | 0.13 | 0.06 | 0.09 | 0.43 | 0.44 | 0.44 |
| `server_processing_turnaround_ms` | 18 | 356.21 | 438.00 | 210.62 | 261.12 | 341.61 | 2104.45 | 2104.45 |
| `server_voice_to_audio_ms` | 18 | 476.21 | 438.00 | 330.62 | 381.12 | 461.61 | 2224.45 | 2224.45 |

---

## RAG Results (`foreground_rag`, N=38)

| Metric | N | Mean (ms) | Std (ms) | Min (ms) | P50 (ms) | P90 (ms) | P95 (ms) | Max (ms) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `retrieval_ms` | 38 | 0.06 | 0.05 | 0.02 | 0.03 | 0.14 | 0.17 | 0.18 |
| `rag_retrieval_ms` | 38 | 1.07 | 1.13 | 0.24 | 0.64 | 3.30 | 3.93 | 5.06 |
| `llm_ttft_ms` | 36 | 666.55 | 262.52 | 418.26 | 616.00 | 819.49 | 1249.76 | 1954.99 |
| `speech_buffer_delay_ms` | 36 | 19.11 | 10.19 | 3.67 | 17.86 | 30.50 | 42.51 | 46.74 |
| `tts_ttfa_ms` | 38 | 230.51 | 33.52 | 202.71 | 215.40 | 262.36 | 319.80 | 348.27 |
| `carrier_framing_delay_ms` | 38 | 0.14 | 0.10 | 0.06 | 0.09 | 0.36 | 0.38 | 0.48 |
| `server_processing_turnaround_ms` | 38 | 883.82 | 303.77 | 215.49 | 850.21 | 1060.47 | 1466.88 | 2210.50 |
| `server_voice_to_audio_ms` | 38 | 1003.82 | 303.77 | 335.49 | 970.21 | 1180.47 | 1586.88 | 2330.50 |

---

## Deterministic Dialogue Results (Scripted Fallbacks, N=2)

| Metric | N | Mean (ms) | Std (ms) | Min (ms) | P50 (ms) | P90 (ms) | P95 (ms) | Max (ms) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `rag_retrieval_ms` | 2 | 0.71 | 0.20 | 0.57 | 0.57 | 0.85 | 0.85 | 0.85 |
| `tts_ttfa_ms` | 2 | 214.07 | 1.70 | 212.87 | 212.87 | 215.28 | 215.28 | 215.28 |
| `server_processing_turnaround_ms` | 2 | 216.23 | 1.04 | 215.49 | 215.49 | 216.97 | 216.97 | 216.97 |
| `server_voice_to_audio_ms` | 2 | 336.23 | 1.04 | 335.49 | 335.49 | 336.97 | 336.97 | 336.97 |

---

## Latency Decomposition

For standard document-grounded dialogue (`foreground_rag`), latency is partitioned across pipeline stages as follows:

```
[User Utterance Finalized]
    │
    ├─▶ RAG Retrieval (FAISS L2)        :   0.64 ms  (P50)   [  0.1% ]
    ├─▶ LLM Time-To-First-Token (Groq)  : 616.00 ms  (P50)   [ 72.4% ]
    ├─▶ Speech Buffering (OV-023)       :  17.86 ms  (P50)   [  2.1% ]
    ├─▶ TTS Time-To-First-Audio (Sarvam): 215.40 ms  (P50)   [ 25.3% ]
    └─▶ Carrier Media Framing / Socket  :   0.09 ms  (P50)   [ <0.1% ]
    │
[First 200ms PCM Frame Transmitted] — Total Server Turnaround: 850.21 ms (P50)
```

---

## Outliers

1. **Session 2, Turn 7** (`8fca32b2...`, `foreground_rag`): Turnaround **2210.5 ms**
   - Stage breakdown: LLM TTFT = **1955.0 ms**, TTS TTFA = **213.5 ms**, RAG = **5.1 ms**, Framing = **0.36 ms**.
   - Cause: Upstream Groq cloud provider queuing delay on multi-paragraph prompt. Local processing remained $<6$ ms.
2. **Session 6, Turn 7** (`1084adc7...`, `fast_cache`): Turnaround **2104.5 ms**
   - Stage breakdown: Cache Retrieval = **0.03 ms**, TTS TTFA = **2103.3 ms**, Framing = **0.43 ms**.
   - Cause: Upstream Sarvam TTS WebSocket initial connection establishment / chunk delay.

---

## Interpretation

1. **Upstream Inference Dominance**: Server latency is overwhelmingly dominated by upstream cloud neural inference (~72% LLM TTFT + ~25% TTS TTFA).
2. **Fast Cache Acceleration**: Exact FAQ caching cuts median server turnaround from **850.21 ms** to **261.12 ms** (a **3.26x speedup** / $589$ ms reduction).
3. **Local Pipeline Efficiency**: Local server operations (FAISS retrieval $\le 5.1$ ms, OV-023 speech segmentation $\le 46.7$ ms, carrier media framing $\le 0.48$ ms) contribute negligibly to total latency.
4. **Tail Latency Driver**: Tail latency variance (P95 of 1466.88 ms) is governed by upstream cloud provider network jitter and inference queuing.

---

## Research Limitations

1. **Synthetic STT Endpoint Offset**: `stt_endpoint_delay_ms` was set to a constant 120.0 ms test harness offset rather than an acoustic microphone measurement.
2. **Proxy Metric**: `server_voice_to_audio_ms` is an upper-bound proxy based on the last local VAD-positive frame before STT finalization.
3. **Carrier Transit Excluded**: Mobile cellular propagation, carrier jitter buffering, and handset speaker transducer delays are outside server boundary measurement.
4. **Exotel Re-Validation Blocker**: Real Exotel PSTN live re-validation was blocked by commercial GST/KYC requirements for credit replenishment.

---

## Reproducibility

To re-export and re-summarize benchmark telemetry from `data/omnivoice.db`:
```bash
python scripts/export_latency_metrics.py --output artifacts/ov006_live_gateway_latency.csv --format csv
python scripts/export_latency_metrics.py --output artifacts/ov006_live_gateway_latency.json --format json
python scripts/summarize_latency_metrics.py artifacts/ov006_live_gateway_latency.json
```
