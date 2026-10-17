"""Render a reproducible research report from OV-030 machine-readable evidence."""

import argparse
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/research"
OUT = ROOT / "docs/research/OV-030_AGENT_EVALUATION.md"
TOOL_ORDER = ("NO_TOOL", "lookup_lead", "check_demo_slots", "schedule_demo",
              "create_followup", "INVALID/UNKNOWN", "MULTIPLE", "UNAVAILABLE")
RQS = [
    "RQ1: Can the model decide whether an enterprise tool is needed?",
    "RQ2: When needed, can it select the correct registered tool?",
    "RQ3: Are read-tool arguments valid and semantically matched to the request?",
    "RQ4: Are mutating proposals contained behind explicit caller confirmation?",
    "RQ5: Can the scripted sales workflow complete without unsafe or duplicate writes?",
    "RQ6: What server-side model-selection and tool/action durations can be measured, and what added response latency remains unmeasured?",
    "RQ7: What failure categories remain?",
]
EXPLANATIONS = {
    "unnecessary_tool": "Tool proposed for a no-tool request",
    "missed_tool": "No tool proposed where one was labeled necessary",
    "wrong_tool": "Registered but incorrect tool proposed",
    "hallucinated_tool": "Unregistered tool name proposed",
    "invalid_arguments": "Schema or synthetic fixture argument mismatch",
    "model_output_parse_failure": "Tool arguments were not valid JSON object",
    "multiple_calls": "More than one tool proposed",
    "provider_error": "Provider did not complete after bounded retries",
}


def percent(value):
    return "N/A" if value is None else f"{100 * value:.2f}%"


def number(value, suffix=""):
    return "N/A" if value is None else f"{value}{suffix}"


def render(live_path=DATA / "ov030_live_selection_results.json",
           summary_path=DATA / "ov030_summary.json", output=OUT):
    cases = json.loads((DATA / "agent_eval_cases.json").read_text(encoding="utf-8"))
    live = json.loads(Path(live_path).read_text(encoding="utf-8"))
    summary = json.loads(Path(summary_path).read_text(encoding="utf-8"))
    if summary["dataset_size"] != len(cases) or len(live["records"]) < summary["live_model"]["full_pass_cases"]:
        raise ValueError("OV-030 report inputs do not match")
    model = summary["live_model"]
    det = summary["deterministic_orchestration"]
    flows = summary["scripted_workflows"]
    categories = Counter(row["category"] for row in cases)
    denominators = model["denominators"]
    lines = [
        "# OV-030 Agent Evaluation Expansion",
        "",
        f"Generated: {summary['generated_at']}. This report uses the retained synthetic case records; failed cases are included.",
        "",
        "## Objective and research questions",
        "",
        "Measure live model tool routing separately from deterministic business-action safety, then document their limits.",
        "",
        *[f"- {question}" for question in RQS],
        "",
        "## Dataset and methodology",
        "",
        f"The fixed dataset contains **{len(cases)}** synthetic, labeled single-turn routing cases: "
        + ", ".join(f"{category} {count}" for category, count in categories.items()) + ".",
        "",
        "The local dataset contains synthetic identifiers only. No customer prompts, caller data, or tool arguments are sent to Langfuse.",
        f"The live selector called **Groq / {summary['model']}** using OmniVoice's `Groq.stream`, "
        "`build_system_prompt`, and actual ToolRegistry schemas. The supplied lead and offered slot lived in a temporary SQLite fixture. "
        "Only the first model response/tool proposal was scored; no ToolRegistry invocation or write execution occurred in this phase.",
        "The prior three-case OV-011B live smoke was a narrow integration check; its 3/3 result is not treated as a population accuracy estimate or combined with these denominators.",
        "",
        f"Pass 1 attempted {model['full_pass_cases']} of {len(cases)} cases and received "
        f"{model['full_pass_model_responses']} completed model responses; "
        f"{model['provider_failures']} provider failures remain in the denominator. "
        "Provider failure types: " + (", ".join(f"{key} {value}" for key, value in model["provider_failure_types"].items()) or "none") + ". "
        f"The predetermined seven-case stratified subset was scheduled for two additional passes "
        f"({model['repeat_observations']} actual additional observations). "
        "Every case was checkpointed; the raw result file contains all attempted failures and their fixed error categories. "
        "The existing provider adapter performed bounded transport retries; no failed case result was removed from the full-pass denominator.",
        "",
        "## Live model selection metrics",
        "",
        "| Metric | Value | Denominator |",
        "|---|---:|---:|",
        f"| Tool-required decision accuracy | {percent(model['tool_required_accuracy'])} | {denominators['tool_required_decision']} |",
        f"| NO_TOOL accuracy | {percent(model['no_tool_accuracy'])} | {denominators['no_tool']} |",
        f"| System-level correct tool selection | {percent(model['tool_selection_accuracy'])} | {denominators['tool_selection']} |",
        f"| Conditional correct tool selection (completed required-tool responses) | {percent(model['answered_tool_selection_accuracy'])} | {denominators['answered_tool_selection']} |",
        f"| System-level routing success | {percent(model['overall_routing_accuracy'])} | {denominators['overall_routing']} |",
        f"| Conditional-on-response routing accuracy | {percent(model['answered_routing_accuracy'])} | {model['full_pass_model_responses']} |",
        f"| Hallucinated tool rate | {percent(model['hallucinated_tool_rate'])} | {denominators['hallucinated_tool']} |",
        f"| Invalid argument rate among known-tool proposals | {percent(model['invalid_argument_rate'])} | {denominators['argument_proposals']} |",
        f"| Valid read arguments among read proposals | {percent(model['read_argument_valid_rate'])} | {denominators['read_argument_proposals']} |",
        f"| Correct write proposal, with no execution | {percent(model['write_proposal_correctness_rate'])} | {denominators['write_cases']} |",
        f"| Accidental write execution attempts | {model['accidental_write_execution_attempts']} | all passes |",
        "",
        "A model selection counts as correct only for the exact labeled tool (or NO_TOOL). System-level rates include provider failures as unsuccessful requests; conditional rates exclude requests with no completed model response. "
        "A known-tool argument is valid only if it passes the JSON schema and matches the relevant synthetic identifier/date/slot; free-text follow-up note quality is not graded. "
        "The write-proposal measure is **not** a completed or confirmation-safe live booking rate.",
        "",
        "## Routing confusion matrix",
        "",
        "Rows are expected; columns are predicted. `UNAVAILABLE` includes provider failures.",
        "",
        "| Expected \\ Predicted | " + " | ".join(TOOL_ORDER) + " |",
        "|---|" + "---:|" * len(TOOL_ORDER),
    ]
    for expected in TOOL_ORDER[:5]:
        counts = model["confusion_matrix"].get(expected, {})
        lines.append(f"| {expected} | " + " | ".join(str(counts.get(predicted, 0)) for predicted in TOOL_ORDER) + " |")
    lines += [
        "", "## Failure analysis and repeated runs", "",
        "Full-pass failure categories: " + (", ".join(f"{key} {value}" for key, value in model["failure_categories"].items()) or "none") + ".",
        "",
        "| Case | Category | Expected | Predicted | Failure category | Explanation |",
        "|---|---|---|---|---|---|",
    ]
    for error in model["errors"]:
        lines.append(f"| {error['case_id']} | {error['category']} | {error['expected']} | "
                     f"{error['predicted']} | {error['failure_type']} | "
                     f"{EXPLANATIONS.get(error['failure_type'], 'Scored mismatch')} |")
    if not model["errors"]:
        lines.append("| None | — | — | — | — | — |")
    lines += [
        "", "Per-pass routing accuracy: " + ", ".join(
            f"pass {key}: {percent(value['routing_accuracy'])} ({value['cases']} cases)"
            for key, value in model["per_run"].items()) + ".",
        f"Repeat consistency (identical predicted tool across available observations): "
        f"{percent(model['repeat_consistency'])} over {model['repeat_case_count']} cases. "
        "This small stratified subset is a prompt-stability check, not a confidence interval for all industries or callers.",
        "",
        "### Post-hoc label audit",
        "",
        "The independent audit did not silently relabel any of the 76 frozen cases. "
        "`schedule_demo_12` asks to *confirm the booking flow*, which could mean an explanation rather than a booking instruction. "
        "`create_followup_02`, `_04`, `_06`, `_08`, and `_11` can imply actual human outreach, while the registered tool only saves a follow-up note; `_08` was a successful proposal, so the ambiguity is not selected solely from failures. "
        "These cases need prospective adjudication before a new accuracy claim. "
        "The missed explicit note requests (`create_followup_05`, `_09`, `_10`) show that the follow-up routing weakness is not only a labeling artifact. "
        "The primary rates above retain the original labels and therefore are conditional on that labeling policy. "
        "The evaluator checks tool proposals, not whether a NO_TOOL text response correctly refuses an adversarial request or avoids an unsupported promise.",
        "", "## Deterministic orchestration and multi-step workflows", "",
        f"The unchanged OV-011B scripted harness produced {det['scenario_count']}/{det['scenario_count']} expected outcomes, "
        f"{det['committed_action_count']} confirmed commits, {det['unsafe_commit_count']} unsafe commits, "
        f"and {det['duplicate_booking_count']} duplicate bookings. Confirmation compliance was "
        f"{percent(det['confirmation_compliance_rate'])}. Read-tool success was "
        f"{percent(det['read_tool_success_rate'])}; confirmed write success was "
        f"{percent(det['confirmed_write_success_rate'])}. Expected stale/race failures remain safe outcomes, "
        "not successful business writes.",
        f"Eight scripted multi-step workflows completed {flows['expected_outcome_count']}/{flows['flow_count']} expected outcomes "
        f"with {flows['correct_tool_sequence_count']}/{flows['flow_count']} expected tool sequences, "
        f"{flows['unsafe_write_count']} unsafe writes, and {flows['duplicate_write_count']} duplicate writes. "
        f"One stale-slot workflow re-read availability, staged an alternative, and committed only after a fresh confirmation "
        f"(recovery {flows['recovery_success_count']}/{flows['recovery_attempt_count']} attempted). "
        "These are scripted programmatic workflows, not model-driven multi-turn phone conversations.",
        "", "## Latency and cost boundary", "",
        f"Completed live model selections: P50 {number(model['llm_selection_latency_ms_p50'], ' ms')}, "
        f"P95 {number(model['llm_selection_latency_ms_p95'], ' ms')} "
        f"(n={model['llm_selection_latency_sample_count']}; includes any successful provider retries).",
        f"Scripted server-side tool execution: P50 {number(det['server_tool_execution_latency_ms_p50'], ' ms')}, "
        f"P95 {number(det['server_tool_execution_latency_ms_p95'], ' ms')} "
        f"(n={det['server_tool_execution_samples']}).",
        f"Scripted confirmed action execution: P50 {number(det['confirmed_action_execution_latency_ms_p50'], ' ms')}, "
        f"P95 {number(det['confirmed_action_execution_latency_ms_p95'], ' ms')} "
        f"(n={det['confirmed_action_execution_samples']}; P95 requires at least 20 samples).",
        "Percentiles use sorted samples and linear interpolation at index `(n-1) × p`. "
        f"The exact local tool/action samples for this summary are retained in `{det['evidence_file']}`; "
        "the historical OV-011B JSON was not reused for these audit-run timings. "
        "The original OV-030 local latency figures lacked retained same-run samples, so this audit replaced them with a fresh scripted run and its saved raw samples. "
        "Failed Groq requests are excluded from completed-selection latency percentiles and remain counted in system-level routing outcomes.",
        "Tool-assisted response latency and token/cost per case are **N/A**: this experiment did not measure a complete STT→tool→LLM→TTS response or capture comparable usage accounting. "
        "All values here are server-side; none measure carrier transit or acoustic mouth-to-ear delay.",
        "", "## Langfuse, limitations, and threats to validity", "",
        "OV-029 Langfuse export was opt-in and supplemental. This live run used `--langfuse`; no local exporter exception was observed, but remote receipt of each case was not independently queried. "
        "The selection exporter sends only allowlisted synthetic case ID/category, expected/predicted tool, correctness, fixed failure category, model/provider and measured latency. "
        "It does not send raw utterances, prompts, audio, transcripts, caller/tenant IDs, business records, tool arguments or secret credentials. "
        "Local JSON records and the deterministic harness remain the authoritative evidence; Langfuse does not alter scores. "
        "Export errors are sanitized and fail open. A successful SDK call alone does not prove every trace was ingested remotely.",
        "Synthetic prompts, correlated paraphrases within each category, one model and one provider limit generalization. The fixture uses local SQLite rather than an external CRM/calendar. "
        "Prompt phrasing, date and synthetic sales state can change model decisions; repeated observations show only a small subset. "
        "The dataset is not a statistically representative sample of real callers, industries, languages, accents or noisy lines. Three historical PSTN calls validated earlier voice behavior, but no physical PSTN sales-tool call was part of this evaluation. "
        "The live selector does not exercise STT, TTS, barge-in, carrier framing, confirmed writes or end-to-end user task completion. "
        "Provider rate limits and transient failures can lower observed completion. Server-side timing is not mouth-to-ear latency. "
        "No direct numerical comparison to a base paper is supported by matching fixtures or measurements.",
        "", "## Defensible conclusion", "",
        "This evaluation provides a larger, reproducible account of where the current Groq model routes synthetic sales requests correctly and where it fails. "
        "The separate deterministic tests demonstrate confirmation-gated local business writes and duplicate prevention under specified cases. "
        "It does not establish a production error rate, universal tool-selection accuracy, or the platform's sub-500 ms PSTN target.",
        "", "## Reproduction", "",
        "From the repository root, use the pinned environment and private local Groq credentials. "
        "The live evaluator checkpoints each case; choose a new output path for an independent run:",
        "",
        "```text",
        ".venv\\Scripts\\python.exe scripts/build_ov030_cases.py",
        ".venv\\Scripts\\python.exe scripts/evaluate_agent_workflows.py",
        ".venv\\Scripts\\python.exe scripts/evaluate_live_agent_selection.py --output data/research/ov030_replicate.json --delay 8",
        ".venv\\Scripts\\python.exe scripts/summarize_ov030.py --live data/research/ov030_replicate.json --output data/research/ov030_replicate_summary.json --deterministic-output data/research/ov030_replicate_deterministic.json",
        ".venv\\Scripts\\python.exe scripts/report_ov030.py --live data/research/ov030_replicate.json --summary data/research/ov030_replicate_summary.json --output docs/research/OV-030_REPLICATE.md",
        "```",
        "", "Machine-readable evidence: `data/research/agent_eval_cases.json`, "
        "`data/research/ov030_live_selection_results.json`, `data/research/ov030_workflow_results.json`, "
        "`data/research/ov030_deterministic_results.json`, and `data/research/ov030_summary.json`. Historical OV-011B files were not overwritten.",
    ]
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", type=Path, default=DATA / "ov030_live_selection_results.json")
    parser.add_argument("--summary", type=Path, default=DATA / "ov030_summary.json")
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()
    print(render(args.live, args.summary, args.output))
