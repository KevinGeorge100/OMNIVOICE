# OV-011B Agent Evaluation

The offline suite runs labeled scripted intents against the real local ToolRegistry, ActionEngine and isolated SQLite stores. No Groq or PSTN calls are made. It extends the baseline architecture; it does not prove global superiority.

Scenarios: 25

Category distribution: {"AMBIGUOUS_CONFIRMATION": 1, "BOOKING": 1, "CROSS_TENANT": 4, "DUPLICATE_CONFIRMATION": 1, "FAQ_ONLY": 2, "FOLLOWUP": 1, "HALLUCINATED_TOOL": 1, "INVALID_ARGUMENT": 2, "INVALID_WRITE_WITHOUT_CONFIRMATION": 1, "LEAD_LOOKUP": 3, "NEGATIVE_CONFIRMATION": 2, "SLOT_SEARCH": 4, "STALE_SLOT": 2}

| Metric | Measured value |
|---|---:|
| tool_selection_accuracy | N/A |
| tool_invocation_count | 45 |
| read_tool_success_rate | 0.967741935483871 |
| write_tool_success_rate | 0.6666666666666666 |
| task_completion_rate | 1.0 |
| confirmation_required_count | 10 |
| confirmation_compliance_rate | 1.0 |
| unsafe_commit_count | 0 |
| committed_action_count | 4 |
| duplicate_execution_count | 0 |
| invalid_tool_request_count | 3 |
| server_side_tool_duration_ms_mean | 0.6142954545454545 |
| confirmed_action_duration_ms_mean | 1.2168333333333332 |
| action_end_to_end_duration_ms_mean | 3.7575 |
| tool_added_response_latency_ms | N/A |

Tool-selection accuracy and tool-added response latency are N/A: this is scripted orchestration, not a live model or voice timing experiment. Confirmation compliance measures the share of commits following exact yes confirmation in the scripted cases. Reported durations are server-side tool/action execution, not mouth-to-ear latency. The action end-to-end duration includes scripted staging and immediate arming; it does not represent the time a caller spends confirming.

Read success includes safe not-found results. Write success is commits per confirmed write attempt; stale/raced slots are expected safe failures. Task completion means the labeled expected outcome, including safe rejection, was observed.

The non-agent baseline answered conversational questions but had no completed sales tool workflow. The agentic extension adds typed reads, confirmation-gated writes, and observable business completion. The two are not directly comparable on this fixture.

The optional live model-selection check is reported separately in [OV-011B_LIVE_GROQ_SMOKE.md](OV-011B_LIVE_GROQ_SMOKE.md).

Failure cases: none.
