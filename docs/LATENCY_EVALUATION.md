# OV-006 Latency Evaluation Protocol

**Status: instrumentation implemented; live-gateway baseline recorded.** The [56-turn benchmark](OV006_BENCHMARK_RESULTS.md) used real Groq and Sarvam provider calls but a gateway harness and synthetic STT endpoint offset. It is not a PSTN or physical acoustic latency distribution. The sub-500 ms end-to-end objective remains a design target, not a measured result.

## Clock and measurement boundaries

All durations use the server's `time.perf_counter()` monotonic clock. Only numeric elapsed milliseconds are persisted; raw monotonic timestamps are removed before storage. Calls persist their turn metrics in `calls.metrics` at completion. The Operations Console shows the same turn data and renders absent fields as `—`.

| Export field | Persisted source | Boundary and classification |
| --- | --- | --- |
| `stt_endpoint_delay_ms` | Same | Last Silero VAD speech-positive frame processed → final STT event received. **Proxy:** VAD-positive frame is not a verified physical speech endpoint. Missing if no VAD-positive frame was observed. |
| `retrieval_ms` | Same | Existing `fast_answer` exact/semantic lookup duration; includes embedding work when semantic. Measured on all turns that reach lookup, including misses. |
| `rag_retrieval_ms` | Same | Dispatch of foreground `knowledge.retrieve` → returned context. Absent on fast answer and confirmation paths. |
| `llm_ttft_ms` | Same | Start of LLM stream iteration → first nonempty content delta. Absent on FAQ, scripted limitation, confirmation, and failures without content. Multiple model invocations in one turn retain the first measurement. |
| `speech_buffer_delay_ms` | Same | First non-whitespace model content observed → first speech segment emitted by the segmenter. This includes waiting for a usable punctuation/length boundary. Absent if no model speech is emitted. |
| `tts_ttfa_ms` | `first_tts_ttfa_ms` | First normalized speech segment prepared for provider streaming → first provider PCM chunk yielded. This is a server-observed proxy for provider first audio; it can include event-loop scheduling and does not identify provider receipt time. |
| `carrier_framing_delay_ms` | Same | First PCM chunk received → first carrier WebSocket media send completion. Includes PCM accumulation to frame size, pacing, encoding, and socket send; it does **not** isolate carrier-network transit. |
| `server_processing_turnaround_ms` | `final_transcript_to_first_audio_sent_ms` | Final STT event handling → first outbound carrier media send completion. Observed server interval. |
| `server_voice_to_audio_ms` | `last_vad_speech_to_first_audio_sent_ms` | Last VAD-positive frame processed → first outbound carrier media send completion. **Proxy**, not acoustic mouth-to-ear. Missing without VAD-positive frame. |

Existing persisted field names are retained for compatibility; the export uses the canonical names above. No metric measures the caller's physical speech endpoint, carrier downlink, jitter buffer, handset playback, or the listener's ear. A separate synchronized acoustic capture on the live phone is required for physical mouth-to-ear latency.

## Export and statistics

From the repository root, run:

```powershell
.venv\Scripts\python.exe -m scripts.export_latency_metrics --database data\omnivoice.db --from-date 2026-10-04 --provider exotel --output latency.csv --summary-output latency-summary.json
.venv\Scripts\python.exe -m scripts.summarize_latency_metrics latency.csv --output latency-summary-recheck.json
```

The export supports `--session`, `--to-date`, `--format json`, and `--include-incomplete`. It includes only session ID, turn index, provider, call start, path classification (`fast_cache`, `foreground_rag`, `confirmation`, or `other`), flags, and numeric durations. Older records infer the path from available metrics; `other` remains ambiguous. It omits transcripts, audio, phone numbers, carrier credentials, tool arguments, and provider payloads. Keep export files outside tracked repository paths when using live data.

Default inclusion requires a completed call, a non-interrupted, error-free turn, and successful first outbound audio timing. Superseded or control-halt generations are not persisted as turns. The export reports exclusion counts by reason (`call_incomplete`, `interrupted`, `response_error`, `no_first_audio`, malformed data). `--include-incomplete` allows audit of excluded rows, but those rows must not be mixed into a valid-turn baseline. Per-metric nulls are ignored; each statistic carries its own `n`. Standard deviation is sample standard deviation and is null for `n < 2`. Percentiles use nearest rank; p99 is deliberately omitted for the initial 50-turn protocol.

## Next PSTN and acoustic benchmark acceptance

1. Capture at least **50 valid completed turns** across **multiple physical PSTN sessions**, recording provider, date, and code revision outside the export if available. The live-gateway harness baseline cannot substitute for this dataset.
2. Separate fast-cache, foreground-RAG, and action paths. Confirm FAQ turns have no LLM TTFT and that interrupted or superseded turns never contribute a false first-audio sample.
3. Publish per-stage `n`, mean, sample standard deviation, min, p50, p90, p95, and max, with exclusion counts and collection conditions. Do not claim statistical significance or an SLA from 50 turns.
4. Compare any intervention to a separately captured baseline with matching provider, network, and call mix. Retain raw numeric exports for audit under appropriate access control.
5. For a physical mouth-to-ear result, create a separate synchronized acoustic experiment (injected audible stimulus at caller handset and recorded response at receiver), including clock calibration and carrier/playback uncertainty. Server timing alone cannot satisfy this criterion.
