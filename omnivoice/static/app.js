let token = sessionStorage.getItem("omni-token") || "";
let tenantId = sessionStorage.getItem("omni-tenant") || "";
let currentPage = "overview";
let state = {};
let tenants = [];
let knowledge = [];
let lines = [];
let calls = [];
let actions = [];
let tools = [];
let submitHandler = null;
let refreshInProgress = false;
let modalReturnFocus = null;
let navCloseTimer = null;

const $ = id => document.getElementById(id);
const esc = text => (text || "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const route = path => `/api/tenants/${tenantId}/${path}`;

function showPage(page) {
  currentPage = page;
  document.querySelectorAll(".page").forEach(p => p.classList.remove("active"));
  const activePage = $(page);
  if (activePage) activePage.classList.add("active");
  document.querySelectorAll(".nav").forEach(b => {
    b.classList.toggle("active", b.dataset.page === page);
    if (b.dataset.page === page) b.setAttribute("aria-current", "page");
    else b.removeAttribute("aria-current");
  });
  const titles = {
    overview: ["Call operations", "Live calls, recent sessions, and workspace readiness.", "＋ New enterprise"],
    workspace: ["Voice agent", "Current workspace configuration and line association.", "View knowledge"],
    knowledge: ["Knowledge", "Private documents and approved FAQ answers.", "Upload document"],
    lines: ["Phone numbers", "Existing Exotel and Twilio numbers registered for inbound routing.", "Connect number"],
    live: ["Live calls", "Current single-worker call activity, updated by authenticated events.", "View history"],
    calls: ["Call history", "Search sessions and inspect persisted conversation and timing data.", "Place call"],
    actions: ["Actions", "Caller confirmation gates state-changing business operations.", "Register tool"],
    analytics: ["Analytics", "Aggregates calculated from real tenant call records.", "Refresh analytics"],
    settings: ["Settings", "Runtime readiness, providers, and retrieval mode.", "Refresh status"]
  };
  const [title, desc, action] = titles[page] || titles.overview;
  const crumb = $("crumb");
  if (crumb) crumb.textContent = title;
  const pageTitle = $("page-title");
  if (pageTitle) pageTitle.textContent = title;
  const pageDesc = $("page-description");
  if (pageDesc) pageDesc.textContent = desc;
  const primaryAction = $("primary-action");
  if (primaryAction) {
    primaryAction.textContent = action;
    primaryAction.hidden = page === "knowledge";
  }
  const toast = $("toast");
  if (toast) toast.hidden = true;
}

function modal(title, body, onSave, saveLabel = "Save") {
  modalReturnFocus = document.activeElement;
  $("modal-title").textContent = title;
  $("modal-body").innerHTML = body;
  $("submit-modal").textContent = saveLabel;
  $("submit-modal").style.display = onSave ? "inline-block" : "none";
  $("cancel-modal").textContent = onSave ? "Cancel" : "Close";
  $("form-error").textContent = "";
  submitHandler = onSave;
  $("modal").showModal();
  $("close-modal").focus();
}

function field(label, name, type = "text", placeholder = "", value = "") {
  return `<label class="field">${label}<input name="${name}" type="${type}" placeholder="${placeholder}" value="${value}" required></label>`;
}

function area(label, name, placeholder = "", required = true) {
  return `<label class="field">${label}<textarea name="${name}" placeholder="${placeholder}" ${required ? "required" : ""}></textarea></label>`;
}

function notify(message) {
  const toast = $("toast");
  if (!toast) return;
  toast.textContent = message;
  toast.hidden = false;
  setTimeout(() => toast.hidden = true, 3500);
}

async function api(path, options = {}) {
  const headers = { ...options.headers };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  if (!(options.body instanceof FormData)) headers["Content-Type"] = "application/json";
  const res = await fetch(path, { ...options, headers });
  if (res.status === 401) {
    token = "";
    sessionStorage.removeItem("omni-token");
    render();
    throw new Error("Authentication required. Please connect your console with a valid token.");
  }
  if (!res.ok) {
    const data = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(data.detail || `Request failed (${res.status})`);
  }
  return res.headers.get("content-type")?.includes("json") ? res.json() : res.text();
}

function requireTenant() {
  if (!tenantId) {
    notify("Please select or create an enterprise workspace first.");
    return false;
  }
  return true;
}

function login() {
  modal("Connect to OmniVoice Console", `${field("API token", "token", "password", "Enter your admin or enterprise API token")}<p class="help">Use your configured server admin token to manage all enterprises, or an enterprise token to view scoped resources.</p>`, form => {
    token = form.get("token").trim();
    sessionStorage.setItem("omni-token", token);
    refresh();
  }, "Connect console");
}

function createTenant() {
  if (!token) return login();
  modal("Create an enterprise", `${field("Enterprise name", "name", "text", "Your business name")}<label class="field">Primary response language<select name="language">${[["en-IN", "English (India)"], ["hi-IN", "Hindi"], ["ml-IN", "Malayalam"], ["ta-IN", "Tamil"], ["te-IN", "Telugu"], ["kn-IN", "Kannada"], ["mr-IN", "Marathi"], ["bn-IN", "Bengali"], ["gu-IN", "Gujarati"], ["pa-IN", "Punjabi"], ["od-IN", "Odia"]].map(([id, name]) => `<option value="${id}">${name}</option>`).join("")}</select></label>${area("Opening greeting", "greeting", "Write the exact greeting in your chosen language.")}${area("Business instructions", "instructions", "Scope, escalation rules, and conversation style.", false)}${field("Explicit confirmation phrase", "phrase", "text", "e.g. Yes, confirm the action")}<p class="help">Use a clear phrase in the selected language. Avoid a bare “yes” that could be a backchannel.</p>`, async form => {
    const result = await api("/api/tenants", {
      method: "POST",
      body: JSON.stringify({
        name: form.get("name"),
        language: form.get("language"),
        greeting: form.get("greeting"),
        instructions: form.get("instructions"),
        confirmation_phrases: [form.get("phrase")]
      })
    });
    tenantId = result.id;
    sessionStorage.setItem("omni-tenant", tenantId);
    await refresh();
    setTimeout(() => modal("Enterprise created", `<p>Save this enterprise API token securely. It is shown once.</p><div class="secret-output">${esc(result.api_token)}</div><p class="help">This token only accesses ${esc(result.name)}.</p>`, null), 0);
  }, "Create enterprise");
}

function addFAQ() {
  if (!requireTenant()) return;
  modal("Add an approved answer", `${field("Caller question", "question")}${area("Business-approved answer", "answer")}<label class="checkbox-label"><input name="approved" type="checkbox"> I approve this answer for direct playback on matching questions.</label><p class="help">Unapproved answers can support retrieval but cannot bypass inference.</p>`, async form => {
    await api(route("faqs"), {
      method: "POST",
      body: JSON.stringify({
        question: form.get("question"),
        answer: form.get("answer"),
        approved: form.has("approved")
      })
    });
    await refresh();
    notify("FAQ saved.");
  });
}

function upload() {
  if (!requireTenant()) return;
  modal("Upload business knowledge", `<p class="help">PDF, TXT, Markdown, JSON, or SQL schema · up to 5 MiB. Documents remain private to this enterprise. SQL files are read as knowledge, never executed.</p>${field("Document", "file", "file")}`, async form => {
    const data = new FormData();
    data.append("file", form.get("file"));
    await api(route("documents"), { method: "POST", body: data });
    await refresh();
    notify("Document ingested.");
  }, "Upload & index");
}

function addLine() {
  if (!requireTenant()) return;
  modal("Connect a phone number", `<p class="help">Register a number you already own. This does not purchase or provision a carrier number.</p><label class="field">Carrier<select name="provider"><option value="exotel">Exotel · India</option><option value="twilio">Twilio</option></select></label>${field("Phone number (E.164)", "number", "tel", "+91…")}`, async form => {
    await api(route("lines"), {
      method: "POST",
      body: JSON.stringify(Object.fromEntries(form))
    });
    await refresh();
    notify("Number registered. Open Connection details to configure the carrier.");
  });
}

function dial() {
  if (!requireTenant()) return;
  if (!lines.length) return notify("Connect a phone number first.");
  modal("Place an outbound call", `<label class="field">From line<select name="line_id">${lines.map(l => `<option value="${l.id}">${esc(l.number)} · ${esc(l.provider)}</option>`).join("")}</select></label>${field("Recipient number", "to", "tel", "+91…")}<label class="checkbox-label"><input type="checkbox" name="consent_confirmed" required> I have the recipient’s consent and intend to place this real phone call.</label><p class="help">Carrier charges apply. Outbound calling must be enabled on the server.</p>`, async form => {
    await api(route("dial"), {
      method: "POST",
      body: JSON.stringify({
        line_id: form.get("line_id"),
        to: form.get("to"),
        consent_confirmed: form.has("consent_confirmed")
      })
    });
    notify("Call request submitted to carrier.");
    await refresh();
  }, "Place call");
}

function addTool() {
  if (!requireTenant()) return;
  modal("Register a business tool", `${field("Tool name", "name", "text", "check_availability")}${field("Description", "description")}<label class="field">Operation<select name="kind"><option value="read">Read-only · may run speculatively</option><option value="write">Write · requires caller confirmation</option></select></label>${field("Public HTTPS endpoint", "url", "url")}${area("Parameter JSON schema", "parameters", '{"type":"object","properties":{},"additionalProperties":false}')}${area("Write confirmation template", "confirmation_template", "Include every argument as a {field} placeholder.", false)}<p class="help">Administrator access required. Register only trusted endpoints. Write endpoints must honor the Idempotency-Key header.</p>`, async form => {
    await api(route("tools"), {
      method: "POST",
      body: JSON.stringify({
        name: form.get("name"),
        description: form.get("description"),
        kind: form.get("kind"),
        url: form.get("url"),
        parameters: JSON.parse(form.get("parameters") || "{}"),
        confirmation_template: form.get("confirmation_template") || null
      })
    });
    await refresh();
    notify("Tool registered.");
  });
}

function badge(text) {
  return `<span class="badge">${esc(text)}</span>`;
}

function empty(title, text) {
  return `<div class="empty"><span>⌁</span><h4>${esc(title)}</h4><p>${esc(text)}</p></div>`;
}

function table(headers, rows) {
  return `<table><thead><tr>${headers.map(h => `<th>${h}</th>`).join("")}</tr></thead><tbody>${rows.join("")}</tbody></table>`;
}

function callRows(items) {
  return items.map(c => {
    const turns = c.metrics?.turns || [];
    const timings = turns.map(t => t.final_transcript_to_first_audio_sent_ms).filter(Number.isFinite);
    return `<tr>
      <td><b>${esc((c.id || "").slice(0, 10))}…</b></td>
      <td>${esc(c.provider)}</td>
      <td>${badge(c.status)}</td>
      <td>${turns.length}</td>
      <td>${timings.length ? Math.round(timings.reduce((a, b) => a + b, 0) / timings.length) + " ms" : "--"}</td>
      <td><button class="secondary-btn btn-sm" data-call="${c.id}">Details ↗</button></td>
    </tr>`;
  });
}

function setupThemeToggle() {
  const toggleBtn = $("theme-toggle");
  const savedTheme = localStorage.getItem("omni-theme-v3") || "light";

  function applyTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    document.body.setAttribute("data-theme", theme);
    localStorage.setItem("omni-theme-v3", theme);
    if (toggleBtn) {
      toggleBtn.setAttribute("data-active-theme", theme);
      const label = toggleBtn.querySelector(".theme-toggle-text");
      if (label) label.textContent = theme === "light" ? "Dark mode" : "Light mode";
      const icon = toggleBtn.querySelector(".theme-toggle-icon");
      if (icon) {
        icon.innerHTML = theme === "light"
          ? `<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>`
          : `<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>`;
      }
    }
  }

  applyTheme(savedTheme);

  if (toggleBtn) {
    toggleBtn.onclick = () => {
      const current = document.documentElement.getAttribute("data-theme") || "light";
      const next = current === "light" ? "dark" : "light";
      applyTheme(next);
    };
  }
}

function render() {
  const authGate = $("auth-gate");
  if (authGate) authGate.hidden = !!token;
  document.body.classList.toggle("console-locked", !token);
  const statusKey = token ? "ready" : "locked";
  const statusText = token ? "Console connected" : "Console locked";

  const statusIcon = statusKey === "locked"
    ? `<svg class="badge-icon lock-icon" viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>`
    : (statusKey === "ready"
      ? `<span class="signal-dot green" aria-hidden="true"></span>`
      : `<svg class="badge-icon alert-icon" viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>`);

  const connState = $("connection-state");
  if (connState) {
    connState.className = `badge status-${statusKey}`;
    connState.dataset.status = statusKey;
    connState.innerHTML = `${statusIcon}<span class="badge-text">${statusText}</span>`;
  }

  const loginBtn = $("login-button");
  if (loginBtn) {
    loginBtn.textContent = token ? "Disconnect" : "Connect console ↗";
  }

  const allTurns = calls.flatMap(c => c.metrics?.turns || []);
  const latencies = allTurns.map(t => t.final_transcript_to_first_audio_sent_ms).filter(Number.isFinite).sort((a, b) => a - b);
  const hits = calls.reduce((n, c) => n + (c.metrics?.cache_hits || 0), 0);

  // Actionable zero-states
  const statActive = $("stat-active");
  if (statActive) statActive.textContent = tenantId ? String(calls.filter(c => c.status === "active").length) : "0";
  const statKnowledge = $("stat-knowledge");
  if (statKnowledge) statKnowledge.textContent = tenantId ? String(knowledge.length) : "0";
  const statLatency = $("stat-latency");
  if (statLatency) statLatency.textContent = latencies.length ? `${Math.round(latencies[Math.ceil(latencies.length * 0.95) - 1])} ms` : "—";
  const statCache = $("stat-cache");
  if (statCache) statCache.textContent = allTurns.length ? `${Math.round(100 * hits / allTurns.length)}%` : "0%";

  // Contextual setup hints
  const hintActive = $("hint-active");
  if (hintActive) hintActive.textContent = tenantId ? (calls.some(c => c.status === "active") ? "Active session" : "No live calls") : "Connect line →";
  const hintKnowledge = $("hint-knowledge");
  if (hintKnowledge) hintKnowledge.textContent = tenantId ? (knowledge.length ? `${knowledge.length} indexed entries` : "Upload docs →") : "+ Upload docs";
  const hintLatency = $("hint-latency");
  if (hintLatency) hintLatency.textContent = latencies.length ? `${latencies.length} recorded turns` : "Measured on calls";
  const hintCache = $("hint-cache");
  if (hintCache) hintCache.textContent = allTurns.length ? `${hits} hits recorded` : "+ Add approved FAQ";

  // Interactive Checklist with Progress Bar
  const steps = [
    { done: !!tenantId, label: "Create your enterprise workspace", action: "createTenant", btn: "Create" },
    { done: knowledge.length > 0, label: "Add business knowledge & approved FAQs", action: "upload", btn: "Upload" },
    { done: lines.length > 0, label: "Connect an Exotel or Twilio phone line", action: "addLine", btn: "Connect" },
    { done: !!state.voice_ready, label: "Configure regional speech & reasoning runtime", action: "settings", btn: "Configure" }
  ];
  const completed = steps.filter(s => s.done).length;
  const fillEl = $("checklist-fill");
  if (fillEl) fillEl.style.width = `${(completed / 4) * 100}%`;
  const pctEl = $("checklist-pct");
  if (pctEl) pctEl.textContent = `${Math.round((completed / 4) * 100)}%`;
  const progressLabel = $("checklist-progress-label");
  if (progressLabel) progressLabel.textContent = `${completed} of 4 steps completed`;

  const checklistEl = $("checklist");
  if (checklistEl) {
    checklistEl.innerHTML = steps.map(s => `
      <div class="check-item ${s.done ? "done" : ""}">
        <div class="check-left">
          <span class="check-circle" aria-hidden="true">${s.done ? "✓" : ""}</span>
          <span>${s.label}</span>
        </div>
        <button class="check-btn" type="button" data-check-action="${s.action}" ${s.done ? "disabled" : ""}>${s.done ? "Done" : s.btn}</button>
      </div>
    `).join("");
  }

  const callTable = items => items.length ? table(["Session", "Carrier", "Status", "Turns", "Mean response", ""], callRows(items)) : empty("No calls yet.", "Call activity appears here after a connected phone session.");

  const recentCalls = $("recent-calls");
  if (recentCalls) {
    recentCalls.innerHTML = calls.length ? callTable(calls.slice(0, 4)) : empty("No call activity yet", "Connected phone sessions will appear here.");
  }
  const callsList = $("calls-list");
  if (callsList) callsList.innerHTML = callTable(calls);

  const knowledgeList = $("knowledge-list");
  if (knowledgeList) {
    knowledgeList.innerHTML = knowledge.length ? table(["Source", "Type", "Direct answer", "Added", ""], knowledge.map(k => `<tr><td><b>${esc(k.title)}</b></td><td>${esc(k.kind)}</td><td>${badge(k.approved ? "Approved" : "Retrieval only")}</td><td>${new Date(k.created * 1000).toLocaleDateString()}</td><td><button class="secondary-btn btn-sm btn-danger" data-delete="${k.id}">Remove</button></td></tr>`)) : empty("A blank slate for your business knowledge.", "Upload a document or add your first approved FAQ.");
  }

  const linesList = $("lines-list");
  if (linesList) {
    linesList.innerHTML = lines.length ? table(["Number", "Carrier", "Routing"], lines.map(l => `<tr><td><b>${esc(l.number)}</b></td><td>${esc(l.provider)}</td><td><button class="secondary-btn btn-sm" data-connection="${l.id}">Connection details ↗</button></td></tr>`)) : empty("Bring your existing number.", "Register an Exotel or Twilio phone line to configure inbound routing.");
  }

  const toolsList = $("tools-list");
  if (toolsList) {
    toolsList.innerHTML = tools.length ? table(["Tool", "Operation", "Description"], tools.map(t => `<tr><td><b>${esc(t.name)}</b></td><td>${badge(t.kind)}</td><td>${esc(t.description)}</td></tr>`)) : empty("Your business systems, connected deliberately.", "Register a trusted read or write endpoint to enable operational actions.");
  }

  const actionsList = $("actions-list");
  if (actionsList) {
    actionsList.innerHTML = actions.length ? table(["Action", "Summary", "Status", "Created"], actions.map(a => `<tr><td><b>${esc(a.tool)}</b></td><td>${esc(a.summary)}</td><td>${badge(a.status)}</td><td>${new Date(a.created * 1000).toLocaleString()}</td></tr>`)) : empty("No staged or executed actions.", "The audit trail records caller-confirmed writes and cancelled proposals.");
  }

  const configEl = $("configuration");
  if (configEl) {
    configEl.innerHTML = [
      ["Speech providers", state.providers?.stt && state.providers?.tts ? `STT: ${state.providers.stt} · TTS: ${state.providers.tts}` : "Connect console to inspect"],
      ["Reasoning", state.providers?.reasoning_model ? "Groq · " + state.providers.reasoning_model : "Connect console to inspect"],
      ["Retrieval", state.retrieval_mode || "Connect console to inspect"],
      ["Neural VAD", state.missing?.includes("SILERO_MODEL") ? "Model not installed" : "Silero ONNX (<20ms)"],
      ["Voice engine", state.voice_ready ? "Configured; live-call validation required" : "Not ready"],
      ["Readiness blockers", state.missing?.join(", ") || "None"],
      ["Outbound calls", state.outbound_enabled ? "Enabled" : "Disabled"],
      ["Deployment", "Single-worker development runtime"]
    ].map(([k, v]) => `<div class="config-row"><span>${esc(k)}</span><b>${esc(v)}</b></div>`).join("");
  }
  if (typeof renderOperations === "function") renderOperations();
}

async function refresh() {
  if (refreshInProgress || !token) return;
  refreshInProgress = true;
  try {
    [state, tenants] = await Promise.all([api("/api/status"), api("/api/tenants")]);
    if (!tenants.some(t => t.id === tenantId)) tenantId = tenants[0]?.id || "";
    const picker = $("tenant-picker");
    if (picker) {
      picker.innerHTML = '<option value="">Select an enterprise</option>' + tenants.map(t => `<option value="${t.id}">${esc(t.name)}</option>`).join("");
      picker.value = tenantId;
    }
    if (tenantId) {
      [knowledge, lines, calls, actions, tools] = await Promise.all(["knowledge", "lines", "calls?limit=25", "actions", "tools"].map(s => api(route(s))));
    } else {
      knowledge = []; lines = []; calls = []; actions = []; tools = [];
    }
    if (typeof loadOperations === "function") await loadOperations();
    render();
    if (typeof connectLiveStream === "function") connectLiveStream();
  } catch (error) {
    notify(error.message);
  } finally {
    refreshInProgress = false;
  }
}

$("modal-form").addEventListener("submit", async event => {
  event.preventDefault();
  if (!submitHandler) return;
  $("submit-modal").disabled = true;
  try {
    await submitHandler(new FormData(event.target));
    $("modal").close();
  } catch (error) {
    $("form-error").textContent = error.message;
  } finally {
    $("submit-modal").disabled = false;
  }
});

$("close-modal").onclick = $("cancel-modal").onclick = () => $("modal").close();
$("modal").addEventListener("close", () => {
  if (modalReturnFocus?.isConnected) modalReturnFocus.focus();
  modalReturnFocus = null;
});

$("login-button").onclick = () => {
  if (token) {
    token = "";
    tenantId = "";
    sessionStorage.clear();
    const toast = $("toast");
    if (toast) toast.hidden = true;
    state = {}; knowledge = []; lines = []; calls = []; actions = []; tools = [];
    if (typeof disconnectLiveStream === "function") disconnectLiveStream();
    const picker = $("tenant-picker");
    if (picker) picker.innerHTML = '<option value="">Select an enterprise</option>';
    render();
  } else {
    login();
  }
};

const tenantPicker = $("tenant-picker");
if (tenantPicker) {
  tenantPicker.onchange = event => {
    tenantId = event.target.value;
    sessionStorage.setItem("omni-tenant", tenantId);
    refresh();
  };
}

$("primary-action").onclick = () => ({
  overview: createTenant,
  workspace: () => showPage("knowledge"),
  knowledge: upload,
  lines: addLine,
  live: () => showPage("calls"),
  calls: dial,
  actions: addTool,
  analytics: refresh,
  settings: refresh
}[currentPage])();

const setupBtn = $("setup-button");
if (setupBtn) setupBtn.onclick = createTenant;
const addFaqBtn = $("add-faq");
if (addFaqBtn) addFaqBtn.onclick = addFAQ;

document.addEventListener("click", async event => {
  const target = event.target.closest("button, article[data-go]");
  if (!target) return;
  try {
    if (target.dataset.page) showPage(target.dataset.page);
    if (target.dataset.go) showPage(target.dataset.go);
    if (target.dataset.page || target.dataset.go) closeMobileNavigation();
    if (target.dataset.checkAction === "createTenant") createTenant();
    if (target.dataset.checkAction === "upload") upload();
    if (target.dataset.checkAction === "addLine") addLine();
    if (target.dataset.checkAction === "settings") showPage("settings");
    if (target.dataset.delete) {
      modal("Remove this knowledge entry?", "<p>This removes the source and invalidates its cached answers.</p>", async () => {
        await api(route(`knowledge/${target.dataset.delete}`), { method: "DELETE" });
        await refresh();
        notify("Knowledge entry removed.");
      }, "Remove");
    }
    if (target.dataset.connection) {
      const line = lines.find(l => l.id === target.dataset.connection);
      if (!line) return;
      try {
        const info = await api(route(`lines/${line.id}/connection`));
        if (line.provider === "twilio") {
          modal(
            "Twilio connection details",
            `<div class="code-box">
              <strong>Inbound Voice Webhook URL (HTTP POST)</strong>
              <code>${esc(info.webhook_url)}</code>
              <p class="help">Configure this URL in your Twilio Console under Phone Numbers &gt; Configure &gt; Voice &amp; Fax (A CALL COMES IN: Webhook).</p>
            </div>`,
            null
          );
        } else {
          const streamAddress = new URL(info.stream_url);
          const maskedStream = `${streamAddress.origin}/ws/exotel/••••/••••••••`;
          modal(
            "Exotel connection details",
            `<div class="code-box">
              <strong>Voice stream endpoint</strong>
              <code>${esc(maskedStream)}</code>
              <p class="help">The stream credential is configured and hidden here. Copy the protected URL to configure your Exotel Voicebot flow.</p>
              <button id="copy-connection-url" class="secondary-btn" type="button">Copy protected URL</button>
            </div>`,
            null
          );
          $("copy-connection-url")?.addEventListener("click", async () => {
            try { await navigator.clipboard.writeText(info.stream_url); notify("Protected URL copied."); }
            catch (_) { notify("Clipboard unavailable. Use the authenticated connection API for carrier setup."); }
          });
        }
      } catch (error) {
        modal(
          "Carrier connection details",
          `<div class="code-box">
            <p class="help" style="color: var(--danger);">${esc(error.message)}</p>
            <p class="help">Configure <code>OMNI_PUBLIC_BASE_URL</code> (e.g. <code>https://voice.yourdomain.com</code>) in your server environment to generate valid carrier webhook and stream endpoints.</p>
          </div>`,
          null
        );
      }
    }
    if (target.dataset.call || target.dataset.mobileCall) {
      const callId = target.dataset.call || target.dataset.mobileCall;
      const call = (typeof findOperationCall === "function" ? findOperationCall(callId) : null) || calls.find(c => c.id === callId);
      if (!call) return;
      if (typeof openCallInspector === "function") {
        openCallInspector(call);
        return;
      }
      const turns = (call.metrics?.turns || []).map((t, idx) => {
        const voice = [
          ["Knowledge", t.knowledge_status],
          ["Limitation", t.limitation_used ? "Yes" : null],
          ["Clarification", t.clarification_requested ? "Yes" : null],
          ["Speech segments", t.response_segment_count],
          ["TTS segments", t.tts_segment_count],
          ["First TTS audio", Number.isFinite(t.first_tts_ttfa_ms) ? `${Math.round(t.first_tts_ttfa_ms)} ms` : null],
          ["Audio sent", Number.isFinite(t.outbound_audio_bytes) ? `${t.outbound_audio_bytes} bytes` : null],
          ["Final padding", Number.isFinite(t.padded_tail_bytes) ? `${t.padded_tail_bytes} bytes` : null],
          ["Interrupted", t.interrupted ? "Yes" : null]
        ].filter(([, value]) => value !== null && value !== undefined);
        return `
        <div class="turn-record">
          <div class="turn-head"><b>Turn ${idx + 1}</b><span>${Number.isFinite(t.final_transcript_to_first_audio_sent_ms) ? `${Math.round(t.final_transcript_to_first_audio_sent_ms)} ms server TTFA` : "TTFA unavailable"}</span></div>
          <p><strong>Caller:</strong> ${esc(t.user_transcript || "—")}</p>
          <p><strong>Reply:</strong> ${esc(t.agent_response || "—")}</p>
          ${voice.length ? `<div class="turn-voice">${voice.map(([label, value]) => `<span>${esc(label)}: <b>${esc(value)}</b></span>`).join("")}</div>` : ""}
        </div>
      `;
      }).join("");
      modal(`Call Session ${esc((call.id || "").slice(0, 10))}`, turns || "<p>No recorded turns.</p>", null);
    }
  } catch (error) {
    notify(error.message);
  }
});

function closeMobileNavigation() {
  document.body.classList.remove("nav-open");
  const toggle = $("mobile-menu-toggle");
  if (toggle) {
    toggle.setAttribute("aria-expanded", "false");
    toggle.setAttribute("aria-label", "Open navigation");
  }
  const scrim = $("nav-scrim");
  if (navCloseTimer) clearTimeout(navCloseTimer);
  if (scrim) navCloseTimer = setTimeout(() => {
    if (!document.body.classList.contains("nav-open")) scrim.hidden = true;
    const sidebar = document.querySelector(".sidebar");
    if (sidebar && window.innerWidth <= 800 && !document.body.classList.contains("nav-open")) sidebar.inert = true;
    navCloseTimer = null;
  }, 240);
}

function setupMobileNavigation() {
  const toggle = $("mobile-menu-toggle");
  if (!toggle) return;
  const sidebar = document.querySelector(".sidebar");
  if (sidebar) sidebar.inert = window.innerWidth <= 800;
  toggle.addEventListener("click", () => {
    const open = !document.body.classList.contains("nav-open");
    if (!open) return closeMobileNavigation();
    if (navCloseTimer) clearTimeout(navCloseTimer);
    navCloseTimer = null;
    $("nav-scrim").hidden = false;
    if (sidebar) sidebar.inert = false;
    document.body.classList.toggle("nav-open", open);
    toggle.setAttribute("aria-expanded", String(open));
    toggle.setAttribute("aria-label", open ? "Close navigation" : "Open navigation");
  });
  $("nav-scrim")?.addEventListener("click", closeMobileNavigation);
  $("mobile-menu-close")?.addEventListener("click", closeMobileNavigation);
  document.addEventListener("keydown", event => {
    if (event.key === "Escape") closeMobileNavigation();
  });
  window.addEventListener("resize", () => {
    if (window.innerWidth > 800) {
      closeMobileNavigation();
      if (sidebar) sidebar.inert = false;
    } else if (sidebar && !document.body.classList.contains("nav-open")) {
      sidebar.inert = true;
    }
  });
}

function setupCommandPalette() {
  const palette = $("command-palette");
  const input = $("command-input");
  const list = $("command-list");
  const trigger = $("command-trigger");
  const pages = [
    ["overview", "Overview", "Operate"], ["live", "Live calls", "Operate"],
    ["calls", "Call history", "Operate"], ["actions", "Actions", "Operate"],
    ["workspace", "Voice agent", "Configure"], ["knowledge", "Knowledge", "Configure"],
    ["lines", "Phone numbers", "Configure"], ["analytics", "Analytics", "Insights"],
    ["settings", "Settings", "System"]
  ];
  let selected = 0;
  const visible = () => pages.filter(([, title]) => title.toLowerCase().includes(input.value.trim().toLowerCase()));
  function renderCommands() {
    const matches = visible();
    if (selected >= matches.length) selected = 0;
    list.innerHTML = matches.length ? matches.map(([id, title, group], index) =>
      `<button type="button" role="option" data-command-page="${id}" aria-selected="${index === selected}"><span>${title}</span><small>${group}</small></button>`
    ).join("") : '<p class="ops-context">No matching page</p>';
  }
  function open() {
    if (!token || $("modal").open || palette.open) return;
    input.value = "";
    selected = 0;
    renderCommands();
    palette.showModal();
    input.focus();
  }
  trigger?.addEventListener("click", open);
  $("command-close")?.addEventListener("click", () => palette.close());
  input?.addEventListener("input", () => { selected = 0; renderCommands(); });
  input?.addEventListener("keydown", event => {
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      const count = visible().length;
      if (count) selected = (selected + (event.key === "ArrowDown" ? 1 : -1) + count) % count;
      renderCommands();
    }
    if (event.key === "Enter" && visible()[selected]) {
      event.preventDefault();
      showPage(visible()[selected][0]);
      palette.close();
    }
  });
  list?.addEventListener("click", event => {
    const page = event.target.closest("[data-command-page]")?.dataset.commandPage;
    if (page) { showPage(page); palette.close(); }
  });
  document.addEventListener("keydown", event => {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
      event.preventDefault();
      open();
    }
    if ((event.key === "Enter" || event.key === " ") && event.target.matches("article[data-go]")) {
      event.preventDefault();
      showPage(event.target.dataset.go);
    }
  });
  palette?.addEventListener("close", () => trigger?.focus());
}

document.addEventListener("DOMContentLoaded", () => {
  setupMobileNavigation();
  setupThemeToggle();
  $("auth-connect")?.addEventListener("click", login);
  setupCommandPalette();
  showPage(currentPage);
  render();
  if (token) refresh();
});
