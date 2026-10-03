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
const opsEmpty = (title, description) => `<div class="ops-empty"><span aria-hidden="true">◎</span><h3>${opsEsc(title)}</h3><p>${opsEsc(description)}</p></div>`;
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
    health.className = `state-pill ${state.voice_ready ? "good" : "warning"}`;
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
  const retrieval = $("runtime-retrieval");
  if (retrieval) retrieval.textContent = state.retrieval_mode || "Connect to inspect retrieval";
  const recent = $("recent-calls");
  if (recent) recent.innerHTML = calls.length ? opsTable(
    ["Session", "Carrier", "Duration", "Turns", "Outcome", "Started", "Inspect", "First audio"], calls.slice(0, 5).map(opsCallRow)
  ) : opsEmpty("No call activity yet", "Connected phone sessions will appear here. No sample calls are shown.");
  const sandbox = $("test-sandbox-btn");
  if (sandbox) sandbox.hidden = true;
}

function renderWorkspace() {
  const target = $("workspace-details");
  if (!target) return;
  if (!operationTenant) {
    target.innerHTML = opsEmpty("Select a workspace", "Connect and select an enterprise to inspect its voice agent.");
    return;
  }
  const config = operationTenant.config || {};
  const entries = [
    ["Enterprise", operationTenant.name],
    ["Response language", config.language || "Not set"],
    ["Greeting", config.greeting || "Not set"],
    ["Registered lines", lines.length ? lines.map(l => `${l.provider.toUpperCase()} ${l.number}`).join(" · ") : "None"],
    ["Knowledge sources", `${knowledge.length} entries`],
    ["Write confirmation", `${(config.confirmation_phrases || []).length} configured phrase(s)`],
    ["Voice selection", "Server default; no tenant voice edit API"]
  ];
  target.innerHTML = `<article class="panel ops-detail-panel"><div class="panel-heading"><div><h3>${opsEsc(operationTenant.name)}</h3><p>Current tenant configuration · read-only</p></div>${opsPill("Read only")}</div>${entries.map(([label, value]) => `<div class="config-row"><span>${opsEsc(label)}</span><b>${opsEsc(value)}</b></div>`).join("")}</article>`;
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
  target.innerHTML = historyRows.length ? opsTable(
    ["Session ID", "Carrier", "Duration", "Turns", "Outcome", "Started", "Inspect", "First audio"], historyRows.map(opsCallRow)
  ) : opsEmpty("No matching calls", "Adjust the filters or connect a phone line to begin recording sessions.");
  $("calls-load-more").hidden = !historyHasMore;
}

async function loadHistory(append = false) {
  if (!tenantId || !token) return;
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
  const page = await api(route(`calls?${params}`));
  if (requestedTenant !== tenantId) return;
  historyRows = append ? historyRows.concat(page) : page;
  historyOffset = historyRows.length;
  historyHasMore = page.length === 25;
  renderHistory();
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
    return `<article class="panel live-card"><div class="live-card-top">${opsPill("Live", "good")}<b class="mono">${opsEsc((call.id || "").slice(0, 10))}</b><span class="mono" data-live-duration="${opsEsc(call.started)}">${opsDuration(Date.now() / 1000 - call.started)}</span></div><div class="live-attributes"><span>${opsEsc(call.provider || "Carrier unavailable")}</span><span>${opsEsc(call.line_number || "Line not recorded")}</span><span>Phase: ${opsEsc(call.state || "Connected")}</span><span>${opsNumber(call.turn_count ?? turns.length)} turns</span></div><div class="live-exchange"><p><small>CALLER · LAST RECORDED TURN</small>${opsEsc(latest || "No transcript recorded yet")}</p><p><small>AGENT · LAST RECORDED TURN</small>${opsEsc(reply || "No response recorded yet")}</p></div><div class="live-card-foot"><span>Server first audio: ${opsLatency(firstAudio)}</span><span>${call.interrupted || last.interrupted ? "Interrupted turn recorded" : "No interruption in latest turn"}</span></div></article>`;
  }).join("") : opsEmpty("No live calls", "This view updates automatically when a connected carrier session starts. No simulated calls are shown.");
}

function renderActionsOperations() {
  const toolTarget = $("tools-list");
  if (toolTarget) toolTarget.innerHTML = tools.length ? opsTable(
    ["Tool", "Operation", "Confirmation", "Endpoint host"],
    tools.map(tool => {
      let host = "Unavailable";
      try { host = new URL(tool.url).hostname; } catch (_) { /* invalid legacy URL */ }
      return `<tr><td><b>${opsEsc(tool.name)}</b><small class="row-note">${opsEsc(tool.description)}</small></td><td>${opsPill(tool.kind)}</td><td>${opsEsc(tool.kind === "write" ? "Required before write" : "Read-only; no write")}</td><td class="mono">${opsEsc(host)}</td></tr>`;
    })
  ) : opsEmpty("No tools registered", "Read tools may run speculatively; write tools require an explicit caller confirmation.");
  const actionTarget = $("actions-list");
  if (actionTarget) actionTarget.innerHTML = actions.length ? opsTable(
    ["Tool", "Summary", "State", "Created"], actions.map(action => `<tr><td>${opsEsc(action.tool)}</td><td>${opsEsc(action.summary)}</td><td>${opsPill(action.status, action.status === "committed" ? "good" : "neutral")}</td><td>${opsDate(action.created)}</td></tr>`)
  ) : opsEmpty("No action history", "Staged, confirmed, cancelled and committed actions will appear here.");
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

function openCallInspector(call) {
  const turns = call.metrics?.turns || [];
  const duration = (call.ended || (call.status === "active" ? Date.now() / 1000 : null)) - call.started;
  const summary = [
    ["Status", call.status], ["Carrier", call.provider], ["Duration", opsDuration(duration)],
    ["Line", call.line_number || "Not recorded"], ["Started", opsDate(call.started)],
    ["Ended", opsDate(call.ended)], ["Turns", turns.length], ["End reason", "Not recorded by current runtime"]
  ].map(([label, value]) => `<div><small>${opsEsc(label)}</small><b>${opsEsc(value)}</b></div>`).join("");
  const timeline = turns.map((turn, index) => {
    const timings = [
      ["STT", turn.stt_final_ms], ["RAG", turn.retrieval_ms], ["LLM", turn.llm_first_token_ms],
      ["TTS", turn.first_tts_ttfa_ms], ["First audio", turn.final_transcript_to_first_audio_sent_ms]
    ].filter(([, value]) => Number.isFinite(value)).map(([label, value]) => `<span>${opsEsc(label)} ${opsLatency(value)}</span>`).join("");
    const voice = [
      Number.isFinite(turn.response_segment_count) ? `${turn.response_segment_count} speech segments` : "",
      Number.isFinite(turn.tts_segment_count) ? `${turn.tts_segment_count} TTS segments` : "",
      Number.isFinite(turn.padded_tail_bytes) ? `${turn.padded_tail_bytes} padding bytes` : "",
      turn.speech_normalization_changed ? "Speech text normalized" : "",
      turn.interrupted ? "Interrupted" : ""
    ].filter(Boolean).map(value => `<span>${opsEsc(value)}</span>`).join("");
    return `<article class="inspector-turn"><div class="turn-index">TURN ${index + 1}</div><div class="speech-bubble caller"><small>CALLER</small><p>${opsEsc(turn.user_transcript || "Transcript not recorded")}</p></div><div class="speech-bubble agent"><small>AGENT</small><p>${opsEsc(turn.agent_response || "Response not recorded")}</p></div>${timings || voice ? `<div class="turn-technical">${timings}${voice}</div>` : ""}</article>`;
  }).join("");
  modal(`Call Session ${opsEsc((call.id || "").slice(0, 10))}`, `<div class="inspector"><div class="inspector-summary">${summary}</div><h3>Conversation timeline</h3>${timeline || opsEmpty("No recorded turns", "The call may have ended before a transcript was available.")}</div>`, null);
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
  const kind = event.target.closest("[data-knowledge-kind]")?.dataset.knowledgeKind;
  if (kind) { knowledgeKind = kind; renderKnowledgeOperations(); }
});
document.addEventListener("DOMContentLoaded", () => {
  $("upload-document")?.addEventListener("click", upload);
  $("knowledge-search")?.addEventListener("input", renderKnowledgeOperations);
  ["call-provider", "call-status", "call-period"].forEach(id => $(id)?.addEventListener("change", () => loadHistory().catch(error => notify(error.message))));
  $("call-search")?.addEventListener("input", () => {
    clearTimeout(historyDebounce);
    historyDebounce = setTimeout(() => loadHistory().catch(error => notify(error.message)), 250);
  });
  $("calls-load-more")?.addEventListener("click", () => loadHistory(true).catch(error => notify(error.message)));
  setInterval(() => document.querySelectorAll("[data-live-duration]").forEach(node => {
    node.textContent = opsDuration(Date.now() / 1000 - Number(node.dataset.liveDuration));
  }), 1000);
});
