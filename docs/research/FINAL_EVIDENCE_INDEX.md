# OmniVoice — Final Evidence Index (OV-033)

Each source is scoped to the claim it can support. The [canonical metric registry](FINAL_METRICS_REGISTRY.md) gives definitions and denominators; source artifacts remain unchanged.

| Source | What it supports | What it does **not** support |
|---|---|---|
| External base paper | **Not present in repository.** [OV-030 comparative notes](OV-030_COMPARATIVE_EVALUATION.md) document only the project's conversational baseline description. | A direct paper-vs-OmniVoice numerical comparison or unreported paper architecture. |
| [Architecture](../ARCHITECTURE.md) and [status](../PROJECT_STATUS.md) | Implemented path, provider defaults, historical OV-005 Exotel handset scope, known gaps. | Current agentic PSTN or cloud deployment. |
| [OV-006 benchmark](../OV006_BENCHMARK_RESULTS.md) | 56-turn server-observed live gateway distributions and methods. | Physical mouth-to-ear, carrier transit, real STT endpoint latency. |
| [OV-011B scripted report](OV-011B_AGENT_EVALUATION.md) and [artifact](../../data/research/agent_tool_eval.json) | 25 expected outcomes, confirmation/write safety and local tool execution. | Live model routing, speech or PSTN accuracy. |
| [OV-011B live smoke](OV-011B_LIVE_GROQ_SMOKE.md) | Three-case integration check. | Population accuracy estimate. |
| [OV-029 observability](OV-029_LANGFUSE_OBSERVABILITY.md) | Optional bounded exporter design, privacy allowlist and fail-open local tests. A later synthetic remote smoke is reported in [status](../PROJECT_STATUS.md). | Per-case remote receipt, production distributed tracing or authoritative research scoring. |
| [OV-030 agent report](OV-030_AGENT_EVALUATION.md), [live cases](../../data/research/ov030_live_selection_results.json), [summary](../../data/research/ov030_summary.json), [scripted samples](../../data/research/ov030_deterministic_results.json) and [workflow results](../../data/research/ov030_workflow_results.json) | Fixed 76-case first-proposal routing, failures, same-run local timing, 8 scripted workflows. | Completed model-led calls, tool-assisted spoken latency, real caller accuracy. |
| [OV-031 report](OV-031_VOICE_AGENT_REHEARSAL.md), [Level A artifact](../../data/research/ov031_voice_rehearsal.json) and [Level B retained record](../../data/research/ov031_live_provider_rehearsal.json) | 12 deterministic session scenarios; seven retained live-provider local attempts, safety, frames and server timings. | Physical PSTN Level C, human naturalness or production reliability. |
| [Contribution matrix](FINAL_CONTRIBUTION_MATRIX.md) | Explicit architectural additions and comparison boundaries. | Unmeasured performance improvement over a base paper. |
| [Metric registry](FINAL_METRICS_REGISTRY.md) | Canonical wording, denominator, environment, percentile and supersession rules. | Any new measurement beyond linked artifacts. |
| [Research conclusion](FINAL_RESEARCH_CONCLUSION.md) | Synthesized, bounded findings and threats to validity. | New experimental result. |
| [Demo script](../FINAL_DEMO_SCRIPT.md) and [checklist](../FINAL_DEMO_CHECKLIST.md) | A reproducible local presentation plan and fallback. | Proof that the future final presentation has already occurred. |
| OV-032 checkpoint branch `task/OV-032-cloud-deployment` at `9fe8240a28778218bca8e5287b6534889e8cd1d8` | Deferred preparation exists outside main. | A Railway deployment or merged cloud milestone. Its report is not copied into this branch. |

Use source artifacts for exact numbers; use this index to avoid treating a historical handset test, gateway timing, synthetic case, live model proposal, and live-provider loopback as one evaluation.
