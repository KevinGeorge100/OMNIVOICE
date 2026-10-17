# OmniVoice — Final Research Conclusion (OV-033)

## 1. Research objective

Test whether a telephony-first asynchronous voice system can combine grounded answers, full-duplex interruption, bounded model-selected tools and confirmation-gated local business writes, while recording the limits of its latency and reliability evidence. The product target remains sub-500 ms voice turnaround across PSTN/SIP; the current experiments do not establish that target.

## 2. What OmniVoice extends

The documented conversational baseline could answer from approved knowledge and continue a telephone dialogue. OmniVoice adds tenant-scoped typed sales reads, a bounded model/tool loop, persisted action state, playback acknowledgment before arming, exact caller confirmation before commit, local duplicate prevention, provider recovery and research-safe telemetry. The external base paper is absent from the repository, so its other capabilities and numerical outcomes are **not directly reported** here. See the [contribution matrix](FINAL_CONTRIBUTION_MATRIX.md).

## 3. Key contributions

The working FastAPI media path joins carrier WebSockets, Silero neural VAD, FlexDuo state transitions, STT, FAQ/FAISS retrieval, Groq generation, streaming speech segmentation, TTS and carrier framing. Sarvam is the default speech pair; Gnani is optional. ToolRegistry restricts model-selected capabilities. The local sales workflow reads leads/slots and gates SQLite booking/follow-up writes through ActionEngine. Langfuse is an opt-in, bounded, fail-open supplement to local evidence.

## 4. Main evaluation results

The unchanged deterministic OV-011B suite reached **25/25 expected outcomes**, four confirmed commits, zero unsafe commits and zero duplicate bookings. OV-030 measured **60/76** system routing and **60/69** conditional routing on synthetic prompts with live Groq first proposals; **33/48** required-tool choices were correct at system level. It also completed **8/8** separate scripted multi-step workflows. These denominators measure different components and are not an end-to-end completion rate. Exact definitions and failure counts appear in the [metric registry](FINAL_METRICS_REGISTRY.md).

## 5. Live-provider validation

OV-031 Level A passed **12/12** deterministic speech-session scenarios through the real session and business code. Level B ran seven retained local carrier-loopback attempts with real Gnani STT, Groq and Gnani TTS: **five failed, two passed**, and attempt 7 passed **20/20** acceptance checks. Both passing fixtures produced one booking only after verbal confirmation. This was not a physical PSTN call. Historical OV-005 Exotel handset calls verified the earlier conversation path, separately.

## 6. Safety findings

No tested local fixture committed before explicit exact confirmation. Negative/ambiguous confirmations, stale slots and duplicate confirmation remained safe in the scripted scenarios. The conditional SQLite booking and uniqueness constraint provided one booking in each successful controlled fixture and none in failed Level B attempts. This is not a universal distributed exactly-once or external CRM guarantee.

## 7. Latency findings

OV-006's live-gateway harness measured final-transcript-to-first-outbound-audio P50 **774.76 ms** and P95 **1466.88 ms** across 56 turns. Its last-VAD-positive-to-first-audio proxy included a synthetic 120 ms endpoint offset; it measured neither physical carrier transit nor mouth-to-ear delay. OV-030 first tool-proposal latency was P50 **734.29 ms**, P95 **2996.69 ms** among 69 completed live Groq responses. OV-031 live-provider loopback had four individual spoken-turn first-frame times in each successful attempt, including values above one second. No complete physical PSTN distribution or sub-500 ms achievement is established.

## 8. Failure findings

The full OV-030 pass retained seven Groq rate-limit failures and nine completed responses that missed a required tool, concentrated in follow-up requests. Five of seven OV-031 Level B attempts failed; failed records were not discarded. A sanitized Groq `protocol`/`exhausted` event occurred during successful attempt slot stages, but its source remains unresolved. Provider and speech quality require further testing before reliability claims.

## 9. Comparison boundaries

The base paper itself, matching sales prompts, tool schemas, provider/model, measurement points and outcome definitions are not available together. The project may say it **extends** the documented conversational baseline with controlled local sales actions. It may not say it numerically outperforms the paper. Langfuse submission is supplemental; local records and deterministic assertions are the authoritative sources.

## 10. Limitations and threats to validity

- Synthetic, correlated paraphrases and one primary Groq/model configuration limit generalization to real callers, accents, industries and noise. Frozen labels contain ambiguities; no retrospective relabeling was used.
- The sales backend is local temporary SQLite; there is no external CRM/calendar integration. Exactly-once findings apply to this implementation and tested conditions only.
- The latest agentic workflow was not physically revalidated over PSTN. Historical Exotel calls predate this path. No acoustic mouth-to-ear latency, carrier transit or full multilingual quality distribution exists.
- Malayalam provider smoke was narrow and had documented quality weakness; English-only fallback/confirmation language remains a limitation. The ability to configure languages is not quality validation.
- OV-030 rate-limit failures and OV-031 failed attempts bound the live result. Two passing controlled rehearsals are insufficient for production reliability.
- The Groq telemetry event and per-case Langfuse remote receipt remain unresolved. Langfuse does not replace local evaluation.
- Railway deployment is deferred on OV-032; this branch contains no deployed service. PostgreSQL, Redis, production metering/RBAC and external business connectors remain future work.

## 11. Future work

First resolve any actual final-demo blocker identified by the [readiness checklist](../FINAL_DEMO_CHECKLIST.md), then resume OV-032 only when Railway account/plan and carrier prerequisites are available. Subsequent research should run physical PSTN agentic calls with acoustic latency instrumentation, natural-speech and multilingual callers, noise/barge-in evaluation, repeatable provider-failure characterization and prospectively adjudicated labels. Production work then needs durable/distributed state and external action reconciliation.

## 12. Defensible conclusion

OmniVoice demonstrates that a modular telephony voice architecture can be extended with grounded retrieval, bounded tool use, confirmation-gated actions, provider resilience and observable agent workflows while preserving single-commit behavior in controlled local evaluations. Its strongest present evidence is deterministic action safety and two successful live-provider local-loopback sales rehearsals **with five retained failed attempts**. This does not prove sub-500 ms PSTN latency, production reliability, human-like naturalness or superiority to an unavailable base paper.
