/* Tenant-scoped operations views. The existing console forms and API contracts stay intact. */
let operationTenant = null;
let operationAnalytics = null;
let historyRows = [];
let historyHasMore = false;
let historyOffset = 0;
let knowledgeKind = "all";
let liveCalls = new Map();
let liveController = null;
let liveKey = "";
let liveRetry = null;
let historyDebounce = null;
let historyRequestId = 0;
let actionFilter = "all";

const opsEsc = value => esc(String(value ?? ""));
const opsDate = value => Number.isFinite(value) ? new Date(value * 1000).toLocaleString() : "Not recorded";
const opsDuration = seconds => {
  if (!Number.isFinite(seconds)) return "—";
  const total = Math.max(0, Math.floor(seconds));
  return `${Math.floor(total / 60)}m ${String(total % 60).padStart(2, "0")}s`;
};
const opsNumber = value => Number.isFinite(value) ? Math.round(value).toLocaleString() : "—";
const opsLatency = value => Number.isFinite(value) ? `${Math.round(value)} ms` : "—";
const opsMetric = (label, value, note = "") => `<article class="ops-metric"><span>${opsEsc(label)}</span><strong>${opsEsc(value)}</strong><small>${opsEsc(note)}</small></article>`;
const opsPill = (label, tone = "neutral") => `<span class="state-pill ${tone}">${opsEsc(label)}</span>`;
const opsEmpty = (title, description) => `<div class="ops-empty"><h3>${opsEsc(title)}</h3><p>${opsEsc(description)}</p></div>`;
const opsTable = (headers, rows) => `<div class="table-scroll"><table><thead><tr>${headers.map(h => `<th scope="col">${opsEsc(h)}</th>`).join("")}</tr></thead><tbody>${rows.join("")}</tbody></table></div>`;

function findOperationCall(id) {
  return historyRows.find(c => c.id === id) || calls.find(c => c.id === id);
}

async function loadOperations() {
  if (!token || !tenantId) {
    operationTenant = null;
    operationAnalytics = null;
    historyRows = [];
    liveCalls.clear();
    disconnectLiveStream();
    return;
  }
  const requestedTenant = tenantId;
  const [tenant, analytics, active] = await Promise.all([
    api(route("")), api(route("analytics")), api(route("calls?status=active&limit=100"))
  ]);
  if (requestedTenant !== tenantId) return;
  operationTenant = tenant;
  operationAnalytics = analytics;
  liveCalls = new Map(active.map(call => [call.id, call]));
  historyRows = calls.slice();
  historyOffset = historyRows.length;
  historyHasMore = historyRows.length === 25;
  if ($("call-search")?.value || $("call-provider")?.value || $("call-status")?.value || $("call-period")?.value) {
    await loadHistory(false);
  }
}

function renderOperations() {
  renderOverviewOperations();
  renderWorkspace();
  renderKnowledgeOperations();
  renderLinesOperations();
  renderLiveCalls();
  renderHistory();
  renderActionsOperations();
  renderAnalyticsOperations();
  renderSettingsOperations();
}

function renderOverviewOperations() {
  const metrics = $("overview-real-metrics");
  const summary = operationAnalytics || {};
  if (metrics) metrics.innerHTML = [
    opsMetric("Total calls", tenantId ? opsNumber(summary.total_calls) : "—", "All recorded sessions"),
    opsMetric("Phone lines", tenantId ? lines.length : "—", "Registered, not carrier-verified"),
    opsMetric("Average duration", opsDuration(summary.avg_duration_seconds), "Completed sessions"),
    opsMetric("Avg. turns / call", Number.isFinite(summary.avg_turns_per_call) ? summary.avg_turns_per_call.toFixed(1) : "—", "Persisted sessions")
  ].join("");
  $("stat-active").textContent = tenantId ? String(liveCalls.size) : "0";
  $("live-nav-count").textContent = String(liveCalls.size);
  const health = $("ops-health-badge");
  if (health) {
    health.textContent = !token ? "Connect to inspect" : state.voice_ready ? "Configured" : "Setup required";
    health.className = `state-pill ${!token ? "" : state.voice_ready ? "good" : "warning"}`;
  }
  const detail = $("ops-health-details");
  if (detail) detail.innerHTML = [
    ["Speech", state.providers?.speech || "Unavailable"],
    ["Reasoning", state.providers?.reasoning || "Unavailable"],
    ["Retrieval", state.retrieval_mode || "Unavailable"],
    ["Capacity", state.max_calls ? `${liveCalls.size} / ${state.max_calls} calls` : "Unavailable"]
  ].map(([label, value]) => `<div><span>${opsEsc(label)}</span><b>${opsEsc(value)}</b></div>`).join("");
  const runtime = $("runtime-title");
  if (runtime) runtime.textContent = !token ? "Status unavailable" : state.voice_ready ? "Voice configured" : "Setup required";
  const runtimeDot = document.querySelector(".runtime-status .pulse-dot");
  if (runtimeDot) runtimeDot.classList.toggle("green", !!(token && state.voice_ready));
  const retrieval = $("runtime-retrieval");
  if (retrieval) retrieval.textContent = state.retrieval_mode || "Connect to inspect retrieval";
  const recent = $("recent-calls");
  if (recent) recent.innerHTML = calls.length ? opsTable(
    ["Session", "Carrier", "Status", "Started", ""], calls.slice(0, 5).map(call => `<tr><td><b class="mono">${opsEsc((call.id || "").slice(0, 10))}</b></td><td>${opsEsc(call.provider)}</td><td>${opsPill(call.status, call.status === "active" ? "good" : call.status === "failed" ? "danger" : "neutral")}</td><td>${opsDate(call.started)}</td><td><button class="secondary-btn btn-sm" data-call="${opsEsc(call.id)}" type="button">Inspect</button></td></tr>`)
  ) : opsEmpty("No call activity yet", "Connected phone sessions will appear here. No sample calls are shown.");
  const setup = $("setup-button");
  if (setup) setup.hidden = !!tenantId;
}

function renderWorkspace() {
  const target = $("workspace-details");
  if (!target) return;
  if (!operationTenant) {
    target.innerHTML = opsEmpty("Select a workspace", "Connect and select an enterprise to inspect its voice agent.");
    return;
  }
  const config = operationTenant.config || {};
  const row = (label, value) => `<div class="config-row"><span>${opsEsc(label)}</span><b>${opsEsc(value)}</b></div>`;
  target.innerHTML = `
    <article class="panel ops-detail-panel"><div class="panel-heading"><div><h3>${opsEsc(operationTenant.name)}</h3><p>Current tenant configuration</p></div>${opsPill("Read only")}</div>
      ${row("Response language", config.language || "Not set")}
      ${row("Voice", "Server default; no tenant voice edit API")}
      ${row("Write confirmation", `${(config.confirmation_phrases || []).length} configured phrase(s)`)}</article>
    <article class="panel ops-detail-panel"><div class="panel-heading"><div><h3>Opening greeting</h3><p>Spoken at the start of a call</p></div></div><div class="agent-greeting">${opsEsc(config.greeting || "No greeting configured")}</div></article>
    <article class="panel ops-detail-panel"><div class="panel-heading"><div><h3>Providers and resources</h3><p>Configured components, not live health checks</p></div></div>
      ${row("Speech", state.providers?.speech || "Unavailable")}
      ${row("Reasoning", state.providers?.reasoning || "Unavailable")}
      ${row("Knowledge", `${knowledge.length} entries`)}
      ${row("Phone numbers", lines.length ? lines.map(l => `${l.provider.toUpperCase()} ${l.number}`).join(" · ") : "None")}</article>`;
}

function renderKnowledgeOperations() {
  const target = $("knowledge-list");
  if (!target) return;
  const search = $("knowledge-search")?.value.toLocaleLowerCase().trim() || "";
  const matching = knowledge.filter(item => (knowledgeKind === "all" || item.kind === knowledgeKind) && item.title.toLocaleLowerCase().includes(search));
  document.querySelectorAll("[data-knowledge-kind]").forEach(button => {
    button.classList.toggle("selected", button.dataset.knowledgeKind === knowledgeKind);
    button.setAttribute("aria-pressed", String(button.dataset.knowledgeKind === knowledgeKind));
  });
  target.innerHTML = matching.length ? opsTable(
    ["Source", "Type", "Use", "Added", ""],
    matching.map(item => `<tr><td><b>${opsEsc(item.title)}</b></td><td>${opsEsc(item.kind === "faq" ? "FAQ" : "Document")}</td><td>${opsPill(item.approved ? "Approved direct answer" : "Retrieval source", item.approved ? "good" : "neutral")}</td><td>${opsDate(item.created)}</td><td><button class="secondary-btn btn-sm btn-danger" data-delete="${opsEsc(item.id)}" type="button">Remove</button></td></tr>`)
  ) : opsEmpty(search || knowledgeKind !== "all" ? "No matching knowledge" : "No knowledge yet", search ? "Try another title." : "Add an FAQ or upload a document. Retrieval quality depends on configured backends.");
  const degraded = state.retrieval_mode?.includes("degraded");
  target.insertAdjacentHTML("afterbegin", `<p class="ops-context">${degraded ? "Semantic retrieval degraded; lexical document retrieval and exact FAQs remain available." : opsEsc(state.retrieval_mode || "Retrieval status unavailable until connected.")}</p>`);
}

function renderLinesOperations() {
  const target = $("lines-list");
  if (!target) return;
  target.innerHTML = lines.length ? opsTable(
    ["Registered number", "Carrier", "State", "Language", "Setup"],
    lines.map(line => `<tr><td><b class="mono">${opsEsc(line.number)}</b></td><td>${opsEsc(line.provider.toUpperCase())}</td><td>${opsPill("Registered")}</td><td>${opsEsc(operationTenant?.config?.language || "—")}</td><td><button class="secondary-btn btn-sm" data-connection="${opsEsc(line.id)}" type="button" aria-label="Connection details for ${opsEsc(line.number)}">Connection details ↗</button></td></tr>`)
  ) : opsEmpty("No numbers registered", "Register an existing Exotel or Twilio number, then configure the carrier using its protected connection details.");
  target.insertAdjacentHTML("afterbegin", `<p class="ops-context">Registration is local configuration. Carrier connection is verified only by a successful live call.</p>`);
}

function opsCallRow(call) {
  const turns = call.metrics?.turns || [];
  const timings = turns.map(turn => turn.final_transcript_to_first_audio_sent_ms).filter(Number.isFinite);
  const mean = timings.length ? timings.reduce((sum, value) => sum + value, 0) / timings.length : null;
  const duration = (call.ended || (call.status === "active" ? Date.now() / 1000 : null)) - call.started;
  return `<tr><td><b class="mono">${opsEsc((call.id || "").slice(0, 10))}</b></td><td>${opsEsc(call.provider)}</td><td class="mono">${opsDuration(duration)}</td><td>${turns.length}</td><td>${opsPill(call.status, call.status === "active" ? "good" : call.status === "failed" ? "danger" : "neutral")}</td><td>${opsDate(call.started)}</td><td><button class="secondary-btn btn-sm" data-call="${opsEsc(call.id)}" type="button" aria-label="Inspect call ${opsEsc((call.id || "").slice(0, 10))}">Inspect ↗</button></td><td class="mono">${opsLatency(mean)}</td></tr>`;
}

function renderHistory() {
  const target = $("calls-list");
  if (!target) return;
  target.removeAttribute("data-loading");
  target.dataset.search = $("call-search")?.value.trim() || "";
  target.innerHTML = historyRows.length ? opsTable(
    ["Session ID", "Carrier", "Duration", "Turns", "Outcome", "Started", "Inspect", "First audio"], historyRows.map(opsCallRow)
  ) : opsEmpty("No matching calls", "Adjust the filters or connect a phone line to begin recording sessions.");
  $("calls-load-more").hidden = !historyHasMore;
  $("calls-load-more").disabled = false;
}

async function loadHistory(append = false) {
  if (!tenantId || !token) return;
  const target = $("calls-list");
  if (target) target.setAttribute("data-loading", "true");
  const loadMoreBtn = $("calls-load-more");
  if (loadMoreBtn) loadMoreBtn.disabled = true;
  const requestId = ++historyRequestId;
  const requestedTenant = tenantId;
  const params = new URLSearchParams({ limit: "25", offset: String(append ? historyOffset : 0) });
  const search = $("call-search")?.value.trim();
  if (search) params.set("search", search);
  const provider = $("call-provider")?.value;
  const status = $("call-status")?.value;
  const period = $("call-period")?.value;
  if (provider) params.set("provider", provider);
  if (status) params.set("status", status);
  if (period) params.set("since", String(Date.now() / 1000 - Number(period) * 86400));
  try {
    const page = await api(route(`calls?${params}`));
    if (requestedTenant !== tenantId || requestId !== historyRequestId) return;
    historyRows = append ? historyRows.concat(page) : page;
    historyOffset = historyRows.length;
    historyHasMore = page.length === 25;
    renderHistory();
  } finally {
    if (requestId === historyRequestId && target) {
      target.removeAttribute("data-loading");
      if (loadMoreBtn) loadMoreBtn.disabled = false;
    }
  }
}

function renderLiveCalls() {
  const target = $("live-calls-list");
  if (!target) return;
  $("live-nav-count").textContent = String(liveCalls.size);
  $("stat-active").textContent = tenantId ? String(liveCalls.size) : "0";
  target.innerHTML = liveCalls.size ? [...liveCalls.values()].map(call => {
    const turns = call.metrics?.turns || [];
    const last = turns.at(-1) || {};
    const latest = call.recent_transcript || last.user_transcript;
    const reply = call.recent_response || last.agent_response;
    const firstAudio = call.first_audio_ms ?? last.final_transcript_to_first_audio_sent_ms;
    return `<article class="panel live-card"><div class="live-card-top">${opsPill("Live", "good")}<b class="mono">${opsEsc((call.id || "").slice(0, 10))}</b><span class="mono" data-live-duration="${opsEsc(call.started)}">${opsDuration(Date.now() / 1000 - call.started)}</span></div><div class="live-attributes"><span>${opsEsc(call.provider || "Carrier unavailable")}</span><span>Line: ${opsEsc(call.line_number || "Not recorded")}</span><span>Phase: ${opsEsc(call.state || "Connected")}</span><span>${opsNumber(call.turn_count ?? turns.length)} turns</span></div><div class="live-exchange"><p><small>CALLER · LAST RECORDED TURN</small>${opsEsc(latest || "No transcript recorded yet")}</p><p><small>AGENT · LAST RECORDED TURN</small>${opsEsc(reply || "No response recorded yet")}</p></div><div class="live-card-foot"><span>Server first audio: ${opsLatency(firstAudio)}</span><button class="text-button" type="button" data-live-inspect="${opsEsc(call.id)}">Inspect session →</button></div></article>`;
  }).join("") : opsEmpty("No live calls", "This view updates automatically when a connected carrier session starts. No simulated calls are shown.");
}

function openLiveInspector(call) {
  const turns = call.metrics?.turns || [];
  const last = turns.at(-1) || {};
  const trace = [
    ["STT endpoint · VAD proxy", last.stt_endpoint_delay_ms],
    ["Retrieval", last.retrieval_ms], ["LLM TTFT", last.llm_ttft_ms],
    ["TTS TTFA", last.first_tts_ttfa_ms],
    ["First outbound audio", call.first_audio_ms ?? last.final_transcript_to_first_audio_sent_ms]
  ].filter(([, value]) => Number.isFinite(value));
  modal(`Live call ${opsEsc((call.id || "").slice(0, 10))}`, `<div class="live-inspector">
    <section><h3>Session</h3><div class="config-row"><span>Carrier</span><b>${opsEsc(call.provider || "Unavailable")}</b></div><div class="config-row"><span>Line</span><b>${opsEsc(call.line_number || "Not recorded")}</b></div><div class="config-row"><span>State</span><b>${opsEsc(call.state || "Connected")}</b></div><div class="config-row"><span>Turns</span><b>${opsNumber(call.turn_count ?? turns.length)}</b></div></section>
    <section><h3>Latest recorded exchange</h3><div class="speech-bubble caller"><small>CALLER</small><p>${opsEsc(call.recent_transcript || last.user_transcript || "No transcript recorded yet")}</p></div><div class="speech-bubble agent"><small>AGENT</small><p>${opsEsc(call.recent_response || last.agent_response || "No response recorded yet")}</p></div></section>
    <section><h3>Latest server trace</h3>${trace.length ? trace.map(([label, value]) => `<div class="config-row"><span>${opsEsc(label)}</span><b class="mono">${opsLatency(value)}</b></div>`).join("") : '<p class="ops-context">No turn timing recorded yet.</p>'}<p class="help">Server timings exclude carrier transit and acoustic playback.</p></section>
  </div>`, null);
}

function renderActionsOperations() {
  const toolTarget = $("tools-list");
  if (toolTarget) toolTarget.innerHTML = tools.length ? opsTable(
    ["Tool", "Operation", "Confirmation", "Endpoint host"],
    tools.map(tool => {
      let host = tool.transport === "local" ? "Local SQLite" : "Unavailable";
      try { host = new URL(tool.url).hostname; } catch (_) { /* invalid legacy URL */ }
      return `<tr><td><b>${opsEsc(tool.name)}</b><small class="row-note">${opsEsc(tool.description)}</small></td><td>${opsPill(tool.kind)}</td><td>${opsEsc(tool.kind === "write" ? "Required before write" : "Read-only; no write")}</td><td class="mono">${opsEsc(host)}</td></tr>`;
    })
  ) : opsEmpty("No tools registered", "Read tools may run speculatively; write tools require an explicit caller confirmation.");
  const actionTarget = $("actions-list");
  document.querySelectorAll("[data-action-filter]").forEach(button => {
    button.classList.toggle("selected", button.dataset.actionFilter === actionFilter);
    button.setAttribute("aria-pressed", String(button.dataset.actionFilter === actionFilter));
  });
  const matching = actions.filter(action => actionFilter === "all" || action.status === actionFilter);
  if (actionTarget) actionTarget.innerHTML = matching.length ? opsTable(
    ["Action", "Call", "Summary", "State", "Created", ""], matching.map(action => {
      const tone = action.status === "committed" ? "good" : action.status === "armed" || action.status === "staged" ? "warning" : action.status === "failed" ? "danger" : "neutral";
      const label = action.status === "armed" ? "Awaiting confirmation" : action.status;
      return `<tr><td><b>${opsEsc(action.tool)}</b></td><td class="mono">${opsEsc((action.call_id || "").slice(0, 10) || "—")}</td><td>${opsEsc(action.summary)}</td><td>${opsPill(label, tone)}</td><td>${opsDate(action.created)}</td><td><button type="button" class="secondary-btn btn-sm" data-action-id="${opsEsc(action.id)}">Inspect</button></td></tr>`;
    })
  ) : opsEmpty(actionFilter === "all" ? "No action history" : "No actions in this state", actionFilter === "all" ? "Caller-confirmed writes and cancelled proposals will appear here." : "Select another state to review the action audit trail.");
}

function openActionInspector(action) {
  const states = ["staged", "armed", "committed"];
  const reached = states.indexOf(action.status);
  const steps = states.map((stateName, index) => {
    const current = action.status === stateName;
    const done = reached > index || (action.status === "cancelled" && index === 0);
    return `<li class="${current ? "current" : done ? "done" : ""}"><span>${index + 1}</span><b>${opsEsc(stateName === "armed" ? "Awaiting confirmation" : stateName)}</b></li>`;
  }).join("");
  modal(`Action ${opsEsc((action.id || "").slice(0, 10))}`, `<div class="action-detail">
    <div class="inspector-summary"><div><small>Tool</small><b>${opsEsc(action.tool)}</b></div><div><small>Current state</small><b>${opsEsc(action.status)}</b></div><div><small>Call</small><b class="mono">${opsEsc(action.call_id || "Not recorded")}</b></div><div><small>Created</small><b>${opsDate(action.created)}</b></div></div>
    <h3>Confirmation lifecycle</h3><ol class="action-lifecycle">${steps}</ol>
    ${action.status === "cancelled" ? '<p class="action-result cancelled">Cancelled before commit.</p>' : action.status === "failed" ? '<p class="action-result failed">Action failed.</p>' : action.status === "committed" ? '<p class="action-result committed">Write committed after confirmation.</p>' : '<p class="ops-context">No write is committed while confirmation is pending.</p>'}
    <div class="action-summary"><small>Recorded summary</small><p>${opsEsc(action.summary || "No summary recorded")}</p></div>
  </div>`, null);
}

function opsBars(rows, labelKey, valueKey) {
  if (!rows?.length) return `<p class="ops-context">No recorded values yet.</p>`;
  const max = Math.max(1, ...rows.map(row => row[valueKey]));
  return rows.map(row => `<div class="bar-row"><span>${opsEsc(row[labelKey])}</span><div class="bar-track"><span style="width:${Math.round(100 * row[valueKey] / max)}%"></span></div><b>${opsNumber(row[valueKey])}</b></div>`).join("");
}

function renderAnalyticsOperations() {
  const summary = operationAnalytics || {};
  const target = $("analytics-summary");
  if (target) target.innerHTML = [
    opsMetric("Total calls", opsNumber(summary.total_calls), "Tenant total"),
    opsMetric("Average duration", opsDuration(summary.avg_duration_seconds), "Ended calls"),
    opsMetric("Average turns", Number.isFinite(summary.avg_turns_per_call) ? summary.avg_turns_per_call.toFixed(1) : "—", "Per persisted call"),
    opsMetric("Average server first audio", opsLatency(summary.avg_server_first_audio_ms), "Transcript → first outbound packet"),
    opsMetric("Interrupted turns", opsNumber(summary.interruptions), "Recorded turn flags")
  ].join("");
  const charts = $("analytics-charts");
  if (charts) charts.innerHTML = [
    ["Calls · last 30 days", opsBars(summary.daily, "day", "calls")],
    ["Carrier mix", opsBars(summary.providers, "provider", "calls")],
    ["Outcomes", opsBars(summary.outcomes, "status", "calls")]
  ].map(([title, body]) => `<article class="panel ops-chart"><h3>${opsEsc(title)}</h3>${body}</article>`).join("");
}

function renderSettingsOperations() {
  const target = $("configuration");
  if (!target) return;
  const row = (label, value) => `<div class="config-row"><span>${opsEsc(label)}</span><b>${opsEsc(value)}</b></div>`;
  const group = (title, description, rows) => `<section class="settings-group"><div class="panel-heading"><div><h3>${opsEsc(title)}</h3><p>${opsEsc(description)}</p></div></div>${rows.join("")}</section>`;
  target.innerHTML = [
    group("Workspace", "Selected tenant and conversation defaults", [
      row("Enterprise", operationTenant?.name || "No workspace selected"),
      row("Response language", operationTenant?.config?.language || "Not set")
    ]),
    group("Providers", "Configured adapters; live availability requires a call", [
      row("Speech to text", state.providers?.stt || "Unavailable"),
      row("Reasoning", state.providers?.reasoning_model || state.providers?.reasoning || "Unavailable"),
      row("Text to speech", state.providers?.tts || "Unavailable")
    ]),
    group("Telephony and retrieval", "Current server capabilities", [
      row("Phone numbers", `${lines.length} registered`),
      row("Outbound calls", state.outbound_enabled ? "Enabled" : "Disabled"),
      row("Retrieval", state.retrieval_mode || "Unavailable"),
      row("Neural VAD", state.missing?.includes("SILERO_MODEL") ? "Model unavailable" : "Silero ONNX configured")
    ]),
    group("Runtime", "Operational limits and readiness", [
      row("Voice engine", state.voice_ready ? "Configured; call validation required" : "Setup required"),
      row("Capacity", Number.isFinite(state.max_calls) ? `${state.max_calls} concurrent calls on this worker` : "Unavailable"),
      row("Readiness blockers", state.missing?.join(", ") || "None reported")
    ])
  ].join("");
}

function openCallInspector(call) {
  const turns = call.metrics?.turns || [];
  const duration = (call.ended || (call.status === "active" ? Date.now() / 1000 : null)) - call.started;
  const summary = [
    ["Status", call.status], ["Carrier", call.provider], ["Duration", opsDuration(duration)],
    ["Line", call.line_number || "Not recorded"], ["Started", opsDate(call.started)],
    ["Ended", opsDate(call.ended)], ["Turns", turns.length], ["End reason", "Not recorded by current runtime"]
  ].map(([label, value]) => `<div><small>${opsEsc(label)}</small><b>${opsEsc(value)}</b></div>`).join("");
  const conversation = turns.map((turn, index) => `<article class="inspector-turn">
    <div class="turn-index">TURN ${index + 1}${turn.interrupted ? " · INTERRUPTED" : ""}</div>
    <div class="speech-bubble caller"><small>CALLER</small><p>${opsEsc(turn.user_transcript || "Transcript not recorded")}</p></div>
    <div class="speech-bubble agent"><small>AGENT</small><p>${opsEsc(turn.agent_response || "Response not recorded")}</p></div>
  </article>`).join("") || opsEmpty("No recorded turns", "The call may have ended before a transcript was available.");
  const metrics = turns.map((turn, index) => {
    const rows = [
      ["STT endpoint · VAD proxy", turn.stt_endpoint_delay_ms],
      ["Fast lookup", turn.retrieval_ms], ["RAG", turn.rag_retrieval_ms],
      ["LLM TTFT", turn.llm_ttft_ms], ["Speech buffer", turn.speech_buffer_delay_ms],
      ["TTS TTFA", turn.first_tts_ttfa_ms], ["Carrier framing + send", turn.carrier_framing_delay_ms],
      ["Transcript → audio sent", turn.final_transcript_to_first_audio_sent_ms],
      ["VAD → audio sent · proxy", turn.last_vad_speech_to_first_audio_sent_ms]
    ].filter(([, value]) => Number.isFinite(value));
    return `<article class="inspector-turn"><div class="turn-index">TURN ${index + 1}</div><div class="turn-technical">${rows.map(([label, value]) => `<span>${opsEsc(label)} ${opsLatency(value)}</span>`).join("") || "No timing recorded"}</div></article>`;
  }).join("") || opsEmpty("No turn metrics", "Timing appears after a recorded voice turn.");
  const callActions = actions.filter(action => action.call_id === call.id);
  const actionPane = callActions.length ? opsTable(["Tool", "State", "Created"], callActions.map(action => `<tr><td>${opsEsc(action.tool)}</td><td>${opsPill(action.status, action.status === "committed" ? "good" : "warning")}</td><td>${opsDate(action.created)}</td></tr>`)) : opsEmpty("No actions recorded", "No business action is attached to this call.");
  const tabs = [["conversation", "Conversation"], ["metrics", "Metrics"], ["actions", "Actions"], ["technical", "Technical"]];
  const tabButtons = tabs.map(([id, title], index) => `<button id="inspector-tab-${id}" type="button" role="tab" aria-controls="inspector-pane-${id}" aria-selected="${index === 0}" data-inspector-tab="${id}">${title}</button>`).join("");
  modal(`Call Session ${opsEsc((call.id || "").slice(0, 10))}`, `<div class="inspector"><div class="inspector-summary">${summary}</div>
    <div class="inspector-tabs" role="tablist" aria-label="Call details">${tabButtons}</div>
    <section id="inspector-pane-conversation" class="inspector-pane" role="tabpanel" aria-labelledby="inspector-tab-conversation">${conversation}</section>
    <section id="inspector-pane-metrics" class="inspector-pane" role="tabpanel" aria-labelledby="inspector-tab-metrics" hidden><p class="ops-context">Server timings; carrier transit and acoustic playback are excluded.</p>${metrics}</section>
    <section id="inspector-pane-actions" class="inspector-pane" role="tabpanel" aria-labelledby="inspector-tab-actions" hidden>${actionPane}</section>
    <section id="inspector-pane-technical" class="inspector-pane" role="tabpanel" aria-labelledby="inspector-tab-technical" hidden>
      <div class="config-row"><span>Session ID</span><b class="mono">${opsEsc(call.id || "Not recorded")}</b></div>
      <div class="config-row"><span>Carrier</span><b>${opsEsc(call.provider || "Not recorded")}</b></div>
      <div class="config-row"><span>Line</span><b>${opsEsc(call.line_number || "Not recorded")}</b></div>
      <div class="config-row"><span>Recorded response segments</span><b>${opsNumber(turns.reduce((total, turn) => total + (turn.response_segment_count || 0), 0))}</b></div>
    </section>
  </div>`, null);
}

function disconnectLiveStream() {
  if (liveController) liveController.abort();
  if (liveRetry) clearTimeout(liveRetry);
  liveController = null;
  liveRetry = null;
  liveKey = "";
  const status = $("live-connection");
  if (status) status.textContent = "Disconnected";
}

function connectLiveStream() {
  if (!token || !tenantId) return disconnectLiveStream();
  const key = `${tenantId}:${token}`;
  if (liveController && liveKey === key) return;
  disconnectLiveStream();
  liveKey = key;
  const controller = new AbortController();
  liveController = controller;
  const status = $("live-connection");
  if (status) status.textContent = "Connecting";
  (async () => {
    try {
      const response = await fetch(route("events"), { headers: { Authorization: `Bearer ${token}` }, signal: controller.signal, cache: "no-store" });
      if (response.status === 401 || response.status === 404) throw new Error("Authentication required");
      if (!response.ok || !response.body) throw new Error(`Event stream unavailable (${response.status})`);
      if (status) status.textContent = "Connected · single worker";
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, "\n");
        let boundary;
        while ((boundary = buffer.indexOf("\n\n")) >= 0) {
          const packet = buffer.slice(0, boundary);
          buffer = buffer.slice(boundary + 2);
          const type = packet.match(/^event: (.+)$/m)?.[1];
          const data = packet.match(/^data: (.+)$/m)?.[1];
          if (type && data && liveKey === key) handleLiveEvent(type, JSON.parse(data));
        }
      }
    } catch (error) {
      if (!controller.signal.aborted && status) status.textContent = error.message === "Authentication required" ? "Unauthorized" : "Reconnecting";
      if (error.message === "Authentication required") return;
    }
    if (!controller.signal.aborted && liveKey === key) {
      liveController = null;
      liveRetry = setTimeout(() => { liveKey = ""; connectLiveStream(); }, 3000);
    }
  })();
}

function handleLiveEvent(type, event) {
  if (type === "call.started") liveCalls.set(event.id, event);
  if (type === "call.turn" && liveCalls.has(event.id)) liveCalls.set(event.id, { ...liveCalls.get(event.id), ...event });
  if (type === "call.ended") {
    liveCalls.delete(event.id);
    Promise.all([api(route("calls?limit=25")), api(route("analytics"))]).then(([recent, analytics]) => {
      calls = recent;
      operationAnalytics = analytics;
      historyRows = recent;
      historyOffset = recent.length;
      historyHasMore = recent.length === 25;
      renderOperations();
    }).catch(error => notify(error.message));
  }
  renderLiveCalls();
  renderOverviewOperations();
}

document.addEventListener("click", event => {
  const inspectorTab = event.target.closest("[data-inspector-tab]")?.dataset.inspectorTab;
  if (inspectorTab) {
    document.querySelectorAll("[data-inspector-tab]").forEach(button => button.setAttribute("aria-selected", String(button.dataset.inspectorTab === inspectorTab)));
    document.querySelectorAll(".inspector-pane").forEach(pane => { pane.hidden = pane.id !== `inspector-pane-${inspectorTab}`; });
  }
  const kind = event.target.closest("[data-knowledge-kind]")?.dataset.knowledgeKind;
  if (kind) { knowledgeKind = kind; renderKnowledgeOperations(); }
  const filter = event.target.closest("[data-action-filter]")?.dataset.actionFilter;
  if (filter) { actionFilter = filter; renderActionsOperations(); }
  const actionId = event.target.closest("[data-action-id]")?.dataset.actionId;
  if (actionId) {
    const action = actions.find(item => item.id === actionId);
    if (action) openActionInspector(action);
  }
  const liveId = event.target.closest("[data-live-inspect]")?.dataset.liveInspect;
  if (liveId && liveCalls.has(liveId)) openLiveInspector(liveCalls.get(liveId));
});
document.addEventListener("DOMContentLoaded", () => {
  $("upload-document")?.addEventListener("click", upload);
  $("knowledge-search")?.addEventListener("input", renderKnowledgeOperations);
  ["call-provider", "call-status", "call-period"].forEach(id => $(id)?.addEventListener("change", () => loadHistory().catch(error => notify(error.message))));
  $("call-search")?.addEventListener("input", () => {
    historyRequestId++;
    const target = $("calls-list");
    if (target) target.setAttribute("data-loading", "true");
    clearTimeout(historyDebounce);
    historyDebounce = setTimeout(() => loadHistory().catch(error => notify(error.message)), 250);
  });
  $("call-search")?.addEventListener("keydown", event => {
    if (event.key === "Enter") {
      event.preventDefault();
      clearTimeout(historyDebounce);
      loadHistory().catch(error => notify(error.message));
    }
  });
  $("calls-load-more")?.addEventListener("click", () => loadHistory(true).catch(error => notify(error.message)));
  setInterval(() => document.querySelectorAll("[data-live-duration]").forEach(node => {
    node.textContent = opsDuration(Date.now() / 1000 - Number(node.dataset.liveDuration));
  }), 1000);
});
