# OV-030 Agent Evaluation Expansion

Generated: 2026-10-16T18:05:33.295502+00:00. This report uses the retained synthetic case records; failed cases are included.

## Objective and research questions

Measure live model tool routing separately from deterministic business-action safety, then document their limits.

- RQ1: Can the model decide whether an enterprise tool is needed?
- RQ2: When needed, can it select the correct registered tool?
- RQ3: Are read-tool arguments valid and semantically matched to the request?
- RQ4: Are mutating proposals contained behind explicit caller confirmation?
- RQ5: Can the scripted sales workflow complete without unsafe or duplicate writes?
- RQ6: What server-side model-selection and tool/action durations can be measured, and what added response latency remains unmeasured?
- RQ7: What failure categories remain?

## Dataset and methodology

The fixed dataset contains **76** synthetic, labeled single-turn routing cases: NO_TOOL 12, LOOKUP_LEAD 12, CHECK_DEMO_SLOTS 12, SCHEDULE_DEMO 12, CREATE_FOLLOWUP 12, AMBIGUOUS 8, ADVERSARIAL 8.

The local dataset contains synthetic identifiers only. No customer prompts, caller data, or tool arguments are sent to Langfuse.
The live selector called **Groq / openai/gpt-oss-20b** using OmniVoice's `Groq.stream`, `build_system_prompt`, and actual ToolRegistry schemas. The supplied lead and offered slot lived in a temporary SQLite fixture. Only the first model response/tool proposal was scored; no ToolRegistry invocation or write execution occurred in this phase.
The prior three-case OV-011B live smoke was a narrow integration check; its 3/3 result is not treated as a population accuracy estimate or combined with these denominators.

Pass 1 attempted 76 of 76 cases and received 69 completed model responses; 7 provider failures remain in the denominator. Provider failure types: ProviderRateLimitError 7. The predetermined seven-case stratified subset was scheduled for two additional passes (14 actual additional observations). Every case was checkpointed; the raw result file contains all attempted failures and their fixed error categories. The existing provider adapter performed bounded transport retries; no failed case result was removed from the full-pass denominator.

## Live model selection metrics

| Metric | Value | Denominator |
|---|---:|---:|
| Tool-required decision accuracy | 78.95% | 76 |
| NO_TOOL accuracy | 96.43% | 28 |
| System-level correct tool selection | 68.75% | 48 |
| Conditional correct tool selection (completed required-tool responses) | 78.57% | 42 |
| System-level routing success | 78.95% | 76 |
| Conditional-on-response routing accuracy | 86.96% | 69 |
| Hallucinated tool rate | 0.00% | 76 |
| Invalid argument rate among known-tool proposals | 0.00% | 33 |
| Valid read arguments among read proposals | 100.00% | 18 |
| Correct write proposal, with no execution | 62.50% | 24 |
| Accidental write execution attempts | 0 | all passes |

A model selection counts as correct only for the exact labeled tool (or NO_TOOL). System-level rates include provider failures as unsuccessful requests; conditional rates exclude requests with no completed model response. A known-tool argument is valid only if it passes the JSON schema and matches the relevant synthetic identifier/date/slot; free-text follow-up note quality is not graded. The write-proposal measure is **not** a completed or confirmation-safe live booking rate.

## Routing confusion matrix

Rows are expected; columns are predicted. `UNAVAILABLE` includes provider failures.

| Expected \ Predicted | NO_TOOL | lookup_lead | check_demo_slots | schedule_demo | create_followup | INVALID/UNKNOWN | MULTIPLE | UNAVAILABLE |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| NO_TOOL | 27 | 0 | 0 | 0 | 0 | 0 | 0 | 1 |
| lookup_lead | 0 | 6 | 0 | 0 | 0 | 0 | 0 | 6 |
| check_demo_slots | 0 | 0 | 12 | 0 | 0 | 0 | 0 | 0 |
| schedule_demo | 1 | 0 | 0 | 11 | 0 | 0 | 0 | 0 |
| create_followup | 8 | 0 | 0 | 0 | 4 | 0 | 0 | 0 |

## Failure analysis and repeated runs

Full-pass failure categories: provider_error 7, missed_tool 9.

| Case | Category | Expected | Predicted | Failure category | Explanation |
|---|---|---|---|---|---|
| no_tool_11 | NO_TOOL | NO_TOOL | UNAVAILABLE | provider_error | Provider did not complete after bounded retries |
| lookup_lead_01 | LOOKUP_LEAD | lookup_lead | UNAVAILABLE | provider_error | Provider did not complete after bounded retries |
| lookup_lead_03 | LOOKUP_LEAD | lookup_lead | UNAVAILABLE | provider_error | Provider did not complete after bounded retries |
| lookup_lead_05 | LOOKUP_LEAD | lookup_lead | UNAVAILABLE | provider_error | Provider did not complete after bounded retries |
| lookup_lead_07 | LOOKUP_LEAD | lookup_lead | UNAVAILABLE | provider_error | Provider did not complete after bounded retries |
| lookup_lead_09 | LOOKUP_LEAD | lookup_lead | UNAVAILABLE | provider_error | Provider did not complete after bounded retries |
| lookup_lead_11 | LOOKUP_LEAD | lookup_lead | UNAVAILABLE | provider_error | Provider did not complete after bounded retries |
| schedule_demo_12 | SCHEDULE_DEMO | schedule_demo | NO_TOOL | missed_tool | No tool proposed where one was labeled necessary |
| create_followup_02 | CREATE_FOLLOWUP | create_followup | NO_TOOL | missed_tool | No tool proposed where one was labeled necessary |
| create_followup_04 | CREATE_FOLLOWUP | create_followup | NO_TOOL | missed_tool | No tool proposed where one was labeled necessary |
| create_followup_05 | CREATE_FOLLOWUP | create_followup | NO_TOOL | missed_tool | No tool proposed where one was labeled necessary |
| create_followup_06 | CREATE_FOLLOWUP | create_followup | NO_TOOL | missed_tool | No tool proposed where one was labeled necessary |
| create_followup_09 | CREATE_FOLLOWUP | create_followup | NO_TOOL | missed_tool | No tool proposed where one was labeled necessary |
| create_followup_10 | CREATE_FOLLOWUP | create_followup | NO_TOOL | missed_tool | No tool proposed where one was labeled necessary |
| create_followup_11 | CREATE_FOLLOWUP | create_followup | NO_TOOL | missed_tool | No tool proposed where one was labeled necessary |
| create_followup_12 | CREATE_FOLLOWUP | create_followup | NO_TOOL | missed_tool | No tool proposed where one was labeled necessary |

Per-pass routing accuracy: pass 1: 78.95% (76 cases), pass 2: 85.71% (7 cases), pass 3: 100.00% (7 cases).
Repeat consistency (identical predicted tool across available observations): 71.43% over 7 cases. This small stratified subset is a prompt-stability check, not a confidence interval for all industries or callers.

### Post-hoc label audit

The independent audit did not silently relabel any of the 76 frozen cases. `schedule_demo_12` asks to *confirm the booking flow*, which could mean an explanation rather than a booking instruction. `create_followup_02`, `_04`, `_06`, `_08`, and `_11` can imply actual human outreach, while the registered tool only saves a follow-up note; `_08` was a successful proposal, so the ambiguity is not selected solely from failures. These cases need prospective adjudication before a new accuracy claim. The missed explicit note requests (`create_followup_05`, `_09`, `_10`) show that the follow-up routing weakness is not only a labeling artifact. The primary rates above retain the original labels and therefore are conditional on that labeling policy. The evaluator checks tool proposals, not whether a NO_TOOL text response correctly refuses an adversarial request or avoids an unsupported promise.

## Deterministic orchestration and multi-step workflows

The unchanged OV-011B scripted harness produced 25/25 expected outcomes, 4 confirmed commits, 0 unsafe commits, and 0 duplicate bookings. Confirmation compliance was 100.00%. Read-tool success was 96.77%; confirmed write success was 66.67%. Expected stale/race failures remain safe outcomes, not successful business writes.
Eight scripted multi-step workflows completed 8/8 expected outcomes with 8/8 expected tool sequences, 0 unsafe writes, and 0 duplicate writes. One stale-slot workflow re-read availability, staged an alternative, and committed only after a fresh confirmation (recovery 1/1 attempted). These are scripted programmatic workflows, not model-driven multi-turn phone conversations.

## Latency and cost boundary

Completed live model selections: P50 734.29 ms, P95 2996.69 ms (n=69; includes any successful provider retries).
Scripted server-side tool execution: P50 0.45 ms, P95 1.24 ms (n=44).
Scripted confirmed action execution: P50 1.57 ms, P95 N/A (n=6; P95 requires at least 20 samples).
Percentiles use sorted samples and linear interpolation at index `(n-1) × p`. The exact local tool/action samples for this summary are retained in `data/research/ov030_deterministic_results.json`; the historical OV-011B JSON was not reused for these audit-run timings. The original OV-030 local latency figures lacked retained same-run samples, so this audit replaced them with a fresh scripted run and its saved raw samples. Failed Groq requests are excluded from completed-selection latency percentiles and remain counted in system-level routing outcomes.
Tool-assisted response latency and token/cost per case are **N/A**: this experiment did not measure a complete STT→tool→LLM→TTS response or capture comparable usage accounting. All values here are server-side; none measure carrier transit or acoustic mouth-to-ear delay.

## Langfuse, limitations, and threats to validity

OV-029 Langfuse export was opt-in and supplemental. This live run used `--langfuse`; no local exporter exception was observed, but remote receipt of each case was not independently queried. The selection exporter sends only allowlisted synthetic case ID/category, expected/predicted tool, correctness, fixed failure category, model/provider and measured latency. It does not send raw utterances, prompts, audio, transcripts, caller/tenant IDs, business records, tool arguments or secret credentials. Local JSON records and the deterministic harness remain the authoritative evidence; Langfuse does not alter scores. Export errors are sanitized and fail open. A successful SDK call alone does not prove every trace was ingested remotely.
Synthetic prompts, correlated paraphrases within each category, one model and one provider limit generalization. The fixture uses local SQLite rather than an external CRM/calendar. Prompt phrasing, date and synthetic sales state can change model decisions; repeated observations show only a small subset. The dataset is not a statistically representative sample of real callers, industries, languages, accents or noisy lines. Three historical PSTN calls validated earlier voice behavior, but no physical PSTN sales-tool call was part of this evaluation. The live selector does not exercise STT, TTS, barge-in, carrier framing, confirmed writes or end-to-end user task completion. Provider rate limits and transient failures can lower observed completion. Server-side timing is not mouth-to-ear latency. No direct numerical comparison to a base paper is supported by matching fixtures or measurements.

## Defensible conclusion

This evaluation provides a larger, reproducible account of where the current Groq model routes synthetic sales requests correctly and where it fails. The separate deterministic tests demonstrate confirmation-gated local business writes and duplicate prevention under specified cases. It does not establish a production error rate, universal tool-selection accuracy, or the platform's sub-500 ms PSTN target.

## Reproduction

From the repository root, use the pinned environment and private local Groq credentials. The live evaluator checkpoints each case; choose a new output path for an independent run:

```text
.venv\Scripts\python.exe scripts/build_ov030_cases.py
.venv\Scripts\python.exe scripts/evaluate_agent_workflows.py
.venv\Scripts\python.exe scripts/evaluate_live_agent_selection.py --output data/research/ov030_replicate.json --delay 8
.venv\Scripts\python.exe scripts/summarize_ov030.py --live data/research/ov030_replicate.json --output data/research/ov030_replicate_summary.json --deterministic-output data/research/ov030_replicate_deterministic.json
.venv\Scripts\python.exe scripts/report_ov030.py --live data/research/ov030_replicate.json --summary data/research/ov030_replicate_summary.json --output docs/research/OV-030_REPLICATE.md
```

Machine-readable evidence: `data/research/agent_eval_cases.json`, `data/research/ov030_live_selection_results.json`, `data/research/ov030_workflow_results.json`, `data/research/ov030_deterministic_results.json`, and `data/research/ov030_summary.json`. Historical OV-011B files were not overwritten.
