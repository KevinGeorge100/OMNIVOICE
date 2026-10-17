# OmniVoice — Canonical Research Metric Registry (OV-033)

This is the single index for **reported** results through OV-031. It records historical results rather than rerunning or changing them. “Live” always names the component that was actually live. P50/P95 methods differ: OV-006 uses nearest rank; OV-030 uses sorted-sample linear interpolation at `(n-1) × p`; OV-031 Level A uses its retained harness statistics. Do not compare those percentiles as if they were matched experiments. `N/A` means unavailable, not zero. The sub-500 ms and sub-50 ms figures are design targets, not achieved PSTN SLAs.

## OV-006 — live gateway server timing

**Environment/class:** Windows local gateway harness, live Groq `openai/gpt-oss-20b` and Sarvam TTS, local FAISS/FAQ, Exotel-shaped media transport; STT speech endpoint **synthetically offset by 120 ms**. Six sessions, 56 valid turns, zero exclusions. All figures below are milliseconds. [Method and complete distributions](../OV006_BENCHMARK_RESULTS.md). `Server turnaround` starts at **final transcript receipt** and ends at **first outbound carrier-frame send**. `Voice-to-audio` starts at last VAD-positive frame and is only a proxy in this harness; it includes the artificial endpoint offset. No acoustic output or carrier network transit was measured.

**Provenance limit:** The committed OV-006 benchmark report retains the summarized distributions; its referenced per-turn CSV/JSON and source SQLite database are not tracked in this checkout. The values below can be checked against that report but cannot be independently recomputed from committed raw OV-006 samples here.

| Metric | Value | n | Measurement definition | Valid claim | Misleading claim |
|---|---:|---:|---|---|---|
| Server processing turnaround P50 / P95 | 774.76 / 1466.88 ms | 56 | Final transcript → first outbound audio send | Gateway server distribution | PSTN mouth-to-ear or sub-500 ms achieved |
| Voice-to-audio proxy P50 / P95 | 894.76 / 1586.88 ms | 56 | Last VAD-positive frame → first outbound audio; synthetic endpoint +120 ms | Gateway proxy distribution | Measured caller speech offset or carrier latency |
| LLM TTFT P50 / P95 | 616.00 / 1249.76 ms | 36 | Groq prompt dispatch → first token | Live Groq stage timing | Complete response or all-turn timing |
| TTS TTFA P50 / P95 | 218.35 / 338.82 ms | 56 | First submitted text segment → first Sarvam PCM | Live Sarvam stage timing | Audible caller first audio |
| RAG retrieval P50 / P95 | 0.64 / 3.93 ms | 38 | Local vector search/context formatting | Local retrieval duration | Full answer latency or guaranteed sub-1 ms |
| FAQ lookup P50 / P95 | 0.03 / 0.13 ms | 18 | Approved fast-path lookup | Local lookup duration | Full spoken response duration |
| FAQ server turnaround P50 / P95 | 261.12 / 2104.45 ms | 18 | Final transcript → outbound audio, FAQ subset | Fast-path subset with TTS outlier retained | Stable sub-500 ms at tail |
| Foreground RAG server turnaround P50 / P95 | 850.21 / 1466.88 ms | 38 | Same boundary; 36 LLM turns plus 2 deterministic limitation turns | RAG-labeled subset | Pure 38-turn LLM sample or causal A/B effect |

The descriptive FAQ/RAG median ratio is not a matched causal speedup. Historical OV-005 physical Exotel handset calls verified the earlier conversation/barge-in path, **not** any OV-006 timing distribution. [Status and historical evidence](../PROJECT_STATUS.md).

## OV-011B — deterministic sales orchestration

**Environment/class:** scripted local ToolRegistry → ActionEngine → temporary SQLite fixture; no model selection, STT, TTS or PSTN. [Report](OV-011B_AGENT_EVALUATION.md), [retained output](../../data/research/agent_tool_eval.json).

| Metric | Value | n / denominator | Definition and valid claim | Misleading claim |
|---|---:|---:|---|---|
| Expected outcomes | 25/25 | 25 cases | Scripted fixture reached each labeled outcome, including safe rejection | 100% live caller task success |
| Tool invocations | 45 | 25 cases | Local registry calls | Live model chose 45 tools correctly |
| Read-tool success | 96.77% | 31 reads (30/31) | Successful local read result, including safe not-found | Real CRM retrieval accuracy |
| Confirmed write success | 66.67% | 6 confirmed attempts (4/6) | Four local commits; stale/race outcomes are safe failures | Production booking conversion |
| Confirmation compliance | 100% | 10 confirmation-required cases | Scripted commits followed exact confirmation; 4 committed actions | Natural-speech confirmation accuracy |
| Unsafe commits / duplicate executions | 0 / 0 | 25 cases | No violating local write in tested cases | Universal exactly-once guarantee |
| Invalid tool requests | 3 | 25 cases | Rejected safely by registry | Model hallucination rate |

Historical OV-011B execution means are run-specific and **not canonical OV-030 latency figures**. Tool-selection accuracy and tool-added voice latency are N/A for this scripted experiment. The separate [three-case live Groq smoke](OV-011B_LIVE_GROQ_SMOKE.md) is a narrow integration check, not a population estimate.

## OV-030 — expanded agent research

**Environment/class:** fixed 76-case synthetic labeled dataset and live Groq `openai/gpt-oss-20b` **first proposal only**, no tool execution; separate scripted local SQLite workflows. Seven full-pass provider rate-limit failures remain in system denominators; 69 responses completed. The predetermined seven-case subset was repeated twice (14 additional observations) and is not pooled into the full pass. [Report](OV-030_AGENT_EVALUATION.md), [case records](../../data/research/ov030_live_selection_results.json), [summary](../../data/research/ov030_summary.json), [scripted raw samples](../../data/research/ov030_deterministic_results.json).

| Metric | Value | n / denominator | Definition and valid claim | Misleading claim |
|---|---:|---:|---|---|
| Labeled cases / completed responses | 76 / 69 | 76 attempts | Fixed synthetic prompt set; seven rate-limit failures | Real-world caller sample |
| System routing success | 60/76 (78.95%) | 76 | Correct exact tool or NO_TOOL, provider failures count as failure | Conditional model accuracy or end-to-end call success |
| Conditional routing accuracy | 60/69 (86.96%) | 69 completed | Same label match among completed responses | System success including outages |
| System required-tool selection | 33/48 (68.75%) | 48 required-tool labels | Exact requested tool, includes unavailable responses | Tool-execution success |
| Conditional required-tool selection | 33/42 (78.57%) | 42 completed required-tool responses | Exact tool among answered cases | Booking completion |
| NO_TOOL | 27/28 (96.43%) | 28 NO_TOOL labels | Correct abstention on fixed prompts | Unsafe-output refusal rate |
| Correct write proposal | 15/24 (62.50%) | 24 write labels | Correct proposed write tool only, no execution | 15 successful bookings |
| Hallucinated tools | 0 | 76 full-pass cases | No unknown tool in first proposal | Proof model never hallucinates |
| Valid known-tool arguments | 33/33 | 33 known-tool proposals | Schema and synthetic identifier/date/slot validity | Human-quality note text or future validity |
| Valid read arguments | 18/18 | 18 read proposals | Matched synthetic read inputs | Real-data correctness |
| Scripted workflows | 8/8 | 8 | Expected local sequence/outcome; stale recovery 1/1 | Model-led phone workflow rate |
| Unchanged OV-011B safety rerun | 25/25; 4 commits; 0 unsafe; 0 duplicate | 25 | Scripted regression invariant | Live model safety estimate |
| Completed live model selection P50 / P95 | 734.29 / 2996.69 ms | 69 | First proposal timing, successful responses including successful retries | Full STT→spoken-audio latency |
| Scripted tool execution P50 / P95 | 0.45 / 1.24 ms | 44 | Same-run local tool-duration samples | Remote CRM duration |
| Scripted confirmed-action execution P50 / P95 | 1.57 ms / N/A | 6 | Same-run local committed-action samples; P95 withheld for n<20 | Reliable tail action latency |

The last three timing rows are the **audited final OV-030 values** backed by retained same-run samples; earlier OV-030 local timings without those samples are superseded. Full-pass failure categories: seven `provider_error` and nine `missed_tool`; eight of the latter were follow-up labels. Some frozen labels are ambiguous and remain unchanged. No token/cost or complete spoken-response latency was captured.

## OV-031 — voice-sales rehearsal

**Level A / deterministic:** Exotel-shaped in-process carrier loopback, real session/transport/tool/action/SQLite code with deterministic speech/model/VAD interface substitutes. [Report](OV-031_VOICE_AGENT_REHEARSAL.md), [artifact](../../data/research/ov031_voice_rehearsal.json). **Level B / live-provider:** same local loopback and temporary SQLite, real Silero VAD, Gnani Prisma STT, Groq `openai/gpt-oss-20b`, Gnani Timbre TTS. [Retained attempts](../../data/research/ov031_live_provider_rehearsal.json). **Level C / physical PSTN:** NOT RUN in OV-031.

| Metric | Value | n | Definition and valid claim | Misleading claim |
|---|---:|---:|---|---|
| Level A scenarios | 12/12 pass | 12 | Scripted speech-session safety/failure/interruption paths | 12 real calls |
| Level A final transcript → first carrier audio P50 / P95 | 184.55 / 195.77 ms | 32 turns | Stub-driven local loopback server boundary | Provider or PSTN latency |
| Level A last VAD-positive → first carrier audio P50 / P95 | 185.48 / 196.05 ms | 31 turns | Stub-driven local server proxy | Acoustic mouth-to-ear |
| Level B retained attempts | 2 pass; 5 fail | 7 | All attempts retained, including two aborted provider and two selection misses | Reliable 2/2 provider success |
| Level B attempt 7 checks | 20/20 pass | 20 assertions | Controlled workflow, delayed mark acknowledgment and persistence | Production acceptance or live PSTN |
| Level B carrier frames | 130 valid per successful attempt | 2 successful attempts | Exotel-shaped outbound media; 8 kHz/16-bit/mono requested | Measured actual provider sample rate |
| Frame payload | 3,200 bytes | Every checked frame | 200 ms of requested 8 kHz/16-bit/mono PCM, headerless | Audible network delivery |
| Attempt 6 final transcript → first outbound frame | 1954.98, 1619.99, 1005.72, 220.93 ms | 4 spoken turns | Individual server-side live-provider observations | P95, full-call average or PSTN latency |
| Attempt 7 same boundary | 1830.91, 1421.40, 1044.43, 318.70 ms | 4 spoken turns | Individual server-side live-provider observations | P95 or a sub-500 ms full-call claim |
| Local bookings after confirmation | 1 per successful fixture; 0 in five failed attempts | 7 attempts | Temporary SQLite; no early or duplicate write | External CRM/calendar booking |
| Level C physical PSTN | NOT RUN | 0 calls | No latest carrier test | OV-031 PSTN validated |

No P95 is computed from four live-provider spoken turns. Both successful runs passed the 20-point gate; the five failures remain part of the result. A sanitized Groq `protocol`/`exhausted` event occurred during slot-stage background activity in attempts 6/7, with cause unresolved. Langfuse local SDK submission in this rehearsal is not proof that each trace arrived remotely. A prior synthetic remote-ingestion smoke was reported for OV-029 separately; local artifacts remain authoritative.

## Claim boundary

The historical three Exotel physical handset calls belong to **OV-005**, and demonstrate the earlier inbound voice loop, not the latest sales agent. The current deployment is local/single-worker; OV-032 Railway deployment is deferred. No dataset here proves sub-500 ms physical PSTN turnaround, naturalness across real callers, full multilingual quality, production reliability, or direct superiority over an unavailable base paper.
