# OmniVoice — Final Demo Script (OV-033)

**Duration:** 2–4 minutes including explanation and inspection. **Evidence level:** local controlled synthetic fixture. The primary repeatable presentation replays the deterministic Level A caller utterances automatically through the real session/business path; the presenter narrates them rather than speaking into a microphone. When Gnani/Groq connectivity is verified, the already validated Level B local carrier-loopback result may be shown separately. Neither is a fresh physical PSTN call. Use synthetic lead/slot data only. For same-call Operations Console evidence, persist the synthetic happy-path fixture and point the local server at that disposable database as described in the [checklist](FINAL_DEMO_CHECKLIST.md). [Rehearsal evidence](research/OV-031_VOICE_AGENT_REHEARSAL.md).

| Time | Presenter action / sample caller intent | Show and verify |
|---|---|---|
| 0:00–0:20 | State the boundary: “This replays synthetic caller speech through the real OmniVoice session/action path on a local carrier-shaped loopback, not the public phone network.” Run the persisted happy-path fixture. | Server health and outbound greeting frame. |
| 0:20–0:40 | Narrate the fixture's approved FAQ: “What does OmniVoice do?” | Grounded `fast_cache` response; do not claim independent answer-quality scoring. |
| 0:40–1:10 | Narrate the synthetic lead-reference utterance. | `lookup_lead` read succeeds and tenant-scoped lead resolves. |
| 1:10–1:35 | Narrate the fixture's Friday-afternoon slot request. | `check_demo_slots` returns an offered slot; no write yet. |
| 1:35–2:10 | Narrate “Book the 4 PM slot.” Point to the recorded confirmation-prompt event. | `schedule_demo` proposal staged; booking count **0** before playback acknowledgment; action becomes `armed` only after mark acknowledgment. |
| 2:10–2:35 | Show the fixture's exact replayed **“Yes.”** | One `committed` action, one local SQLite booking, final spoken success and carrier-framed audio. |
| 2:35–3:00 | Show the separately labeled deterministic `duplicate_confirmation` case if challenged. | Booking remains exactly **1**; no second commit. Do not imply this case is part of the persisted happy-path call. |
| 3:00–3:30 | Open the Operations Console on the **same disposable fixture database**, then inspect the saved local metric projection. | Synthetic call/action record visible; tool names/outcomes, confirmation and commit status. Optional Langfuse metadata is supplemental. |
| 3:30–4:00 | State the evidence boundary. | OV-031: 12/12 deterministic scenarios, seven retained live-provider attempts with five failures/two passes, no Level C PSTN. Point to [metric registry](research/FINAL_METRICS_REGISTRY.md). |

The [existing deterministic runner](../scripts/rehearse_voice_sales_agent.py) includes the approved FAQ turn **inside** its `happy_path` scenario. Its twelve labels are sales/safety scenario names rather than twelve FAQ test cases. A separate `duplicate_confirmation` scenario establishes repeat safety. Do not describe the automatic replay as a live microphone or physical telephone conversation.

## Controlled fallback branches

Use the existing Level A named scenarios to show one branch on demand. Keep the main demo on the happy path.

| Branch | Expected behavior / evidence |
|---|---|
| Lead not found | `lead_not_found`: no fabricated lead and no booking. |
| No slots | If fixture offers none, agent must not stage an arbitrary slot; use the documented tool result. This is not one of the 12 separately labeled Level A scenarios, so do not claim a retained dedicated pass. |
| Negative confirmation | `negative_confirmation`: staged action is not committed; zero booking. |
| Ambiguous confirmation | `ambiguous_confirmation`: no commit until exact final-turn confirmation. |
| Stale slot | `stale_slot`: conditional booking fails safely; no duplicate or false success. |
| Repeated “yes” | `duplicate_confirmation`: the first valid confirmation commits once; the repetition does not duplicate. |
| Provider/tool failure | `tool_failure`, `llm_failure`, `stt_failure`, `tts_failure`: fail safely and report limitation. The Level B provider record also retains failures. |

Run with a fresh temporary output path to preserve canonical evidence. The local script uses temporary SQLite and writes only synthetic fixture data. Do not reset or edit the retained `data/research/ov031_*` artifacts for the presentation.
