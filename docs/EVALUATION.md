# Evaluation contract

Use legally obtained Fisher/FD-Bench samples. Preserve corpus identifiers, language, speaker/channel selection, transcript normalization policy, noise/overlap conditions, and provider/model versions with each run. Do not infer WER from a response transcript or claim a corpus result from synthetic fixtures.

## Replay

`python -m omnivoice.replay recording.wav --channel 0 --output artifacts/replay.json`

Set `OMNI_REPLAY_URL` to the authenticated Exotel/gateway media URL. The utility accepts 8kHz 16-bit PCM WAV (mono, or a selected stereo channel), sends 20ms frames in real time, receives outbound audio concurrently, emulates playback marks, and records outgoing audio and clear timing. This **uses configured live speech/LLM APIs** and may incur charges, but it does not originate a PSTN call. Never include the private URL in a report.

Output is a transport trace, not WER or automatic ground-truth TTFA. Align the input corpus's annotated speech-end/barge-in events with the output trace; capture provider recognition hypotheses separately with appropriate data handling. On real PSTN calls, instrument receiver-side playback as well as server timestamps.

## Score annotated runs

One JSON object per line:

```json
{"corpus":"your licensed corpus","sample_id":"your sample id","reference":"actual reference words","hypothesis":"actual STT hypothesis","end_of_speech_to_first_audio_ms":520.1,"barge_in_decision_to_clear_ms":12.0,"should_interrupt":true,"did_interrupt":true}
```

The numbers above illustrate the schema only. They are not results. Omit measurements that are unavailable; do not put zero in their place.

```powershell
.\.venv\Scripts\python.exe -m omnivoice.evaluation runs.jsonl --output artifacts\report.json
```

WER uses corpus-wide edit errors divided by reference word count, with Unicode word tokenization and case normalization. Language-specific segmentation/tokenization may be needed for final academic reporting. False interruption rate uses annotated non-interruption opportunities as its denominator; missed interruption rate uses annotated genuine interruptions. Report both and keep corpus/language/noise partitions separate.

Report p50/p95/p99 TTFA and sample counts, plus speech onset → semantic decision and semantic decision → playback stopped separately. A fast clear dispatch does not establish fast acoustic onset-to-stop behavior.
