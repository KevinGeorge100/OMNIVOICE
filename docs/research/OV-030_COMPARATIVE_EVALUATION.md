# OV-030 Comparative Research Evidence

## Comparison boundary

The conversational baseline in OmniVoice can answer from approved knowledge and continue a telephone dialogue. OV-011A/B extend that architecture with tenant-scoped typed sales tools, server-verified state, and confirmation-gated actions. This document compares *capabilities on the same local synthetic fixture*, not numerical accuracy against an external paper or a production carrier.

| Dimension | Conversational baseline | Agentic OmniVoice extension | Evidence boundary |
|---|---|---|---|
| Sales record lookup | No registered lead tool | Exact tenant-scoped `lookup_lead` read | OV-011B scripted cases; OV-030 live routing proposals |
| Demo availability | Could discuss documented information only | Date-filtered `check_demo_slots` read | Local SQLite fixture, not external calendar |
| Booking | Could discuss a booking but not commit it | `schedule_demo` stages through ActionEngine, then commits only after exact verbal confirmation | Scripted local action tests, not physical PSTN sales call |
| Follow-up | No persistent sales follow-up | `create_followup` uses the same gated write lifecycle | Scripted local action tests |
| Duplicate prevention | No business write lifecycle | Conditional slot update and unique booking constraint | Local race/duplicate cases |
| Tool observability | Dialogue/call timing only | Local tool/action metrics and opt-in research-safe Langfuse metadata | Server-side and synthetic; no caller payload export |

The deterministic OV-011B suite evaluates orchestration once tool calls are chosen. It cannot establish model-selection accuracy. The OV-030 Groq experiment evaluates model proposals without invoking any write. Its routing figures and the scripted business outcomes are therefore **separate estimands**, not a single end-to-end completion rate. The eight OV-030 multi-step workflows run ToolRegistry, ActionEngine, and SQLite programmatically; they do not test speech recognition, carrier transport, or natural caller dialogue.

No direct numerical comparison with a base paper is possible from these fixtures. The cited baseline architecture does not provide matching synthetic sales prompts, tool schemas, outcome definitions, provider/model, or latency measurement points. OmniVoice extends the baseline architecture by adding measurable business action capability and explicit write safety; this does not establish global superiority or sub-500 ms PSTN performance.

See [OV-030_AGENT_EVALUATION.md](OV-030_AGENT_EVALUATION.md) for the measured counts, confusion matrix, failures, and limitations. The historical [OV-011B_AGENT_EVALUATION.md](OV-011B_AGENT_EVALUATION.md) remains unchanged.
