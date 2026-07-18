const state = { ledger: null, selectedCommand: 0 };

const commands = [
  { label: "Load demonstration ledger", detail: "Use the fictional sample project", action: loadDemo },
  { label: "Simulate file collision", detail: "Show protection from overlapping edits", action: simulateConflict },
  { label: "Export latest handoff", detail: "Download a portable markdown note", action: exportHandoff }
];

const byId = (id) => document.getElementById(id);
const dialog = byId("command-dialog");
const search = byId("command-search");

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;"
  }[char]));
}

function formatDate(value) {
  if (!value) return "unknown time";
  return new Intl.DateTimeFormat("en", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

function activeClaims() {
  return (state.ledger?.claims || []).filter((claim) => claim.status === "active");
}

function latestVerification() {
  const items = state.ledger?.verifications || [];
  return items.length ? items[items.length - 1] : null;
}

function render() {
  const ledger = state.ledger;
  if (!ledger) return;
  const active = activeClaims();
  const verification = latestVerification();
  const handoffs = ledger.handoffs || [];
  byId("project-title").textContent = ledger.project?.name || "Untitled relay";
  byId("project-meta").textContent = "Ledger created " + formatDate(ledger.project?.created_at) + " · schema v" + (ledger.schema_version || 1);
  byId("active-count").textContent = active.length;
  byId("verification-state").textContent = verification ? verification.status : "waiting";
  byId("verification-time").textContent = verification ? formatDate(verification.created_at) : "run relay.py verify";
  byId("handoff-count").textContent = handoffs.length;

  byId("claims-list").innerHTML = active.length ? active.map((claim) =>
    '<article class="claim-row"><div><span class="agent-dot" aria-hidden="true"></span><strong>' +
    escapeHtml(claim.agent) + '</strong><p>' + escapeHtml(claim.task) + '</p></div><ul>' +
    claim.files.map((file) => '<li><code>' + escapeHtml(file) + '</code></li>').join("") +
    '</ul><time datetime="' + escapeHtml(claim.created_at) + '">' + formatDate(claim.created_at) + '</time></article>'
  ).join("") : '<p class="empty-state">No active boundaries. Claim files before changing them.</p>';

  byId("verification-card").innerHTML = verification ?
    '<div class="verification-status ' + escapeHtml(verification.status) + '"><span aria-hidden="true">✓</span><strong>' +
    escapeHtml(verification.status) + '</strong></div><div><code>' + escapeHtml(verification.command) +
    '</code><p>exit ' + escapeHtml(verification.exit_code) + ' · ' + escapeHtml(verification.agent) +
    ' · ' + formatDate(verification.created_at) + '</p></div><pre><code>' +
    escapeHtml(verification.output || "No captured output") + '</code></pre>' :
    '<p class="empty-state">Run a verification command to create auditable evidence.</p>';

  byId("handoff-list").innerHTML = handoffs.length ? handoffs.slice().reverse().map((handoff) =>
    '<article class="handoff-row"><div><strong>' + escapeHtml(handoff.title) + '</strong><p><code>' +
    escapeHtml(handoff.path) + '</code></p></div><div><span>' + escapeHtml(handoff.agent) +
    '</span><time datetime="' + escapeHtml(handoff.created_at) + '">' + formatDate(handoff.created_at) +
    '</time></div></article>'
  ).join("") : '<p class="empty-state">No handoffs exported yet.</p>';
}

async function loadDemo() {
  const response = await fetch("../demo/ledger.json");
  state.ledger = await response.json();
  render();
}

function showToast(message) {
  const toast = byId("toast");
  toast.textContent = message;
  toast.classList.add("visible");
  window.setTimeout(() => toast.classList.remove("visible"), 2600);
}

function simulateConflict() {
  const claim = activeClaims()[0];
  if (!claim) {
    showToast("Load a ledger with an active file claim first.");
    return;
  }
  showToast("Blocked: " + claim.files[0] + " is actively claimed by " + claim.agent + ".");
}

function exportHandoff() {
  const handoffs = state.ledger?.handoffs || [];
  const latest = handoffs[handoffs.length - 1];
  if (!latest) {
    showToast("No handoff is available to export.");
    return;
  }
  const content = "# " + latest.title + "\n\n" +
    "- Prepared by: " + latest.agent + "\n" +
    "- Recorded: " + latest.created_at + "\n" +
    "- Path: " + latest.path + "\n\n" +
    "## Active boundaries\n" +
    activeClaims().map((claim) => "- " + claim.agent + ": " + claim.files.join(", ")).join("\n") +
    "\n\n## Latest verification\n" +
    ((latestVerification()?.status || "waiting") + ": " + (latestVerification()?.command || "No command recorded")) + "\n";
  const blob = new Blob([content], { type: "text/markdown" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "evidence-relay-handoff.md";
  link.click();
  URL.revokeObjectURL(url);
  showToast("Handoff exported as Markdown.");
}

function renderCommands() {
  const query = search.value.trim().toLowerCase();
  const visible = commands.filter((command) => (command.label + command.detail).toLowerCase().includes(query));
  state.selectedCommand = Math.min(state.selectedCommand, Math.max(visible.length - 1, 0));
  byId("command-options").innerHTML = visible.length ? visible.map((command, index) =>
    '<button type="button" role="option" aria-selected="' + (index === state.selectedCommand) +
    '" class="command-option ' + (index === state.selectedCommand ? "selected" : "") + '" data-index="' + index +
    '"><span>' + escapeHtml(command.label) + '</span><small>' + escapeHtml(command.detail) + '</small></button>'
  ).join("") : '<p class="empty-state">No matching command.</p>';
  document.querySelectorAll(".command-option").forEach((option) => {
    option.addEventListener("click", () => runCommand(visible[Number(option.dataset.index)]));
  });
  return visible;
}

function runCommand(command) {
  if (!command) return;
  dialog.close();
  command.action();
}

function openCommands() {
  state.selectedCommand = 0;
  search.value = "";
  renderCommands();
  dialog.showModal();
  search.focus();
}

byId("command-trigger").addEventListener("click", openCommands);
byId("load-demo").addEventListener("click", loadDemo);
byId("simulate-conflict").addEventListener("click", simulateConflict);
byId("export-handoff").addEventListener("click", exportHandoff);
byId("ledger-input").addEventListener("change", async (event) => {
  const file = event.target.files[0];
  if (!file) return;
  try {
    state.ledger = JSON.parse(await file.text());
    render();
  } catch {
    showToast("That file is not a valid ledger JSON document.");
  }
});
search.addEventListener("input", () => {
  state.selectedCommand = 0;
  renderCommands();
});
search.addEventListener("keydown", (event) => {
  const visible = renderCommands();
  if (event.key === "ArrowDown") {
    event.preventDefault();
    state.selectedCommand = (state.selectedCommand + 1) % Math.max(visible.length, 1);
    renderCommands();
  } else if (event.key === "ArrowUp") {
    event.preventDefault();
    state.selectedCommand = (state.selectedCommand - 1 + Math.max(visible.length, 1)) % Math.max(visible.length, 1);
    renderCommands();
  } else if (event.key === "Enter") {
    event.preventDefault();
    runCommand(visible[state.selectedCommand]);
  }
});
dialog.addEventListener("click", (event) => {
  if (event.target === dialog) dialog.close();
});
window.addEventListener("keydown", (event) => {
  if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
    event.preventDefault();
    if (!dialog.open) openCommands();
  }
});

loadDemo().catch(() => {
  byId("project-meta").textContent = "Use Open ledger to inspect a local JSON ledger.";
});
