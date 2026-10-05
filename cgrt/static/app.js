const numbersBody = document.getElementById("numbersBody");
const sheetSummary = document.getElementById("sheetSummary");
const jobSummary = document.getElementById("jobSummary");
const modalJobSummary = document.getElementById("modalJobSummary");
const runStatusNote = document.getElementById("runStatusNote");
const messageEl = document.getElementById("message");
const startBtn = document.getElementById("startBtn");
const refreshBtn = document.getElementById("refreshBtn");
const selectAll = document.getElementById("selectAll");
const batchSizeSelect = document.getElementById("batchSize");
const selectionSummary = document.getElementById("selectionSummary");
const batchHint = document.getElementById("batchHint");
const routeModeInputs = Array.from(document.querySelectorAll('input[name="routeMode"]'));
const manualRoutePresetSelect = document.getElementById("manualRoutePreset");
const manualRouteTargetInput = document.getElementById("manualRouteTarget");
const routeHint = document.getElementById("routeHint");
const progressBar = document.getElementById("progressBar");
const modalProgressBar = document.getElementById("modalProgressBar");
const resultsList = document.getElementById("resultsList");
const openRunStatusBtn = document.getElementById("openRunStatusBtn");
const closeRunStatusBtn = document.getElementById("closeRunStatusBtn");
const runStatusModal = document.getElementById("runStatusModal");
const statusPanel = document.querySelector(".panel-status");
const numbersHead = document.querySelector(".numbers-head");

const counterElements = {
  waiting: [document.getElementById("waitingCount"), document.getElementById("modalWaitingCount")],
  running: [document.getElementById("runningCount"), document.getElementById("modalRunningCount")],
  done: [document.getElementById("doneCount"), document.getElementById("modalDoneCount")],
  failed: [document.getElementById("failedCount"), document.getElementById("modalFailedCount")],
};

let availableNumbers = [];
let activeJobId = null;
let pollTimer = null;
let manualSelection = new Set();
let autoExcludedRows = new Set();

function updateStickyOffsets() {
  const root = document.documentElement;
  const statusHeight = statusPanel ? Math.ceil(statusPanel.getBoundingClientRect().height) : 96;
  const headHeight = numbersHead ? Math.ceil(numbersHead.getBoundingClientRect().height) : 96;

  root.style.setProperty("--status-offset", `${statusHeight}px`);
  root.style.setProperty("--numbers-head-height", `${headHeight}px`);
}

function clearPollTimer() {
  if (!pollTimer) {
    return;
  }
  window.clearTimeout(pollTimer);
  pollTimer = null;
}

function setMessage(text, kind = "info") {
  if (!text) {
    messageEl.textContent = "";
    messageEl.className = "message hidden";
    return;
  }

  messageEl.textContent = text;
  messageEl.className = `message ${kind}`;
}

function getBatchSize() {
  const value = Number(batchSizeSelect?.value || 0);
  return Number.isFinite(value) && value > 0 ? value : 0;
}

function getRouteMode() {
  return routeModeInputs.find((input) => input.checked)?.value || "default";
}

function getManualRouteTarget() {
  return String(manualRouteTargetInput?.value || "").trim();
}

function getManualRoutePreset() {
  return String(manualRoutePresetSelect?.value || "custom");
}

function validateManualRouteTarget(value) {
  const trimmed = String(value || "").trim();
  const match = /^(\d{1,3}(?:\.\d{1,3}){3}):(\d{1,5})$/.exec(trimmed);
  if (!match) {
    throw new Error("Manual route must look like 52.28.195.200:5060.");
  }

  const octets = match[1].split(".");
  for (const octet of octets) {
    const number = Number(octet);
    if (!Number.isInteger(number) || number < 0 || number > 255) {
      throw new Error("Manual route IP parts must be between 0 and 255.");
    }
  }

  const port = Number(match[2]);
  if (!Number.isInteger(port) || port < 1 || port > 65535) {
    throw new Error("Manual route port must be between 1 and 65535.");
  }

  return `${match[1]}:${port}`;
}

function syncRouteControls() {
  const manualMode = getRouteMode() === "manual";
  const presetValue = getManualRoutePreset();
  const usingCustomRoute = presetValue === "custom";

  if (manualRoutePresetSelect) {
    manualRoutePresetSelect.disabled = !manualMode;
  }

  if (manualRouteTargetInput) {
    manualRouteTargetInput.disabled = !manualMode || !usingCustomRoute;
    if (manualMode && !usingCustomRoute) {
      manualRouteTargetInput.value = presetValue;
    }
  }

  if (routeHint) {
    routeHint.textContent = manualMode
      ? usingCustomRoute
        ? "Manual mode will save the DID with {DID_ALIAS}@IP:PORT for this run."
        : `Manual mode will use ${presetValue} and save it as {DID_ALIAS}@${presetValue} for this run.`
      : "Default mode keeps the existing fixed primary destination.";
  }
}

function syncManualSelection() {
  const validRows = new Set(availableNumbers.map((item) => item.row));
  manualSelection = new Set([...manualSelection].filter((row) => validRows.has(row)));
  autoExcludedRows = new Set([...autoExcludedRows].filter((row) => validRows.has(row)));
}

function getCheckedRows() {
  return availableNumbers
    .filter((item) => manualSelection.has(item.row))
    .map((item) => item.row);
}

function getAutoSelectedRows() {
  return availableNumbers
    .slice(0, getBatchSize())
    .filter((item) => !autoExcludedRows.has(item.row))
    .map((item) => item.row);
}

function getSelectedRows() {
  const includedRows = new Set([...getCheckedRows(), ...getAutoSelectedRows()]);
  return availableNumbers
    .filter((item) => includedRows.has(item.row))
    .map((item) => item.row);
}

function getSelectionBreakdown() {
  const checkedRows = getCheckedRows();
  const autoRows = getAutoSelectedRows();
  const combinedRows = getSelectedRows();
  const checkedSet = new Set(checkedRows);
  const overlap = autoRows.filter((row) => checkedSet.has(row)).length;

  return {
    checked: checkedRows.length,
    auto: autoRows.length,
    overlap,
    total: combinedRows.length,
  };
}

function updateSelectAllState() {
  if (!selectAll) {
    return;
  }
  const checkedCount = getSelectedRows().length;
  const totalCount = availableNumbers.length;

  selectAll.checked = totalCount > 0 && checkedCount === totalCount;
  selectAll.indeterminate = checkedCount > 0 && checkedCount < totalCount;
}

function updateSelectionSummary() {
  const counts = getSelectionBreakdown();
  if (selectionSummary) {
    selectionSummary.textContent = `Checked ${counts.checked} | Auto ${counts.auto} | Total ${counts.total}`;
  }

  if (counts.auto > 0) {
    const requested = getBatchSize();
    const clippedText = counts.auto < requested ? ` (${counts.auto} available right now)` : "";
    const overlapText = counts.overlap > 0 ? ` ${counts.overlap} already overlap with checked rows.` : "";
    if (batchHint) {
      batchHint.textContent = `Auto-including the first ${requested} numbers from the current list${clippedText}.${overlapText}`.trim();
    }
    return;
  }

  if (batchHint) {
    batchHint.textContent = "Choose 5 to 100 to auto-include the first numbers from the list, or keep using manual checkboxes only.";
  }
}

function updateStartButton() {
  const totalSelected = getSelectionBreakdown().total;
  const running = Boolean(activeJobId);

  startBtn.disabled = totalSelected === 0 || running;
  startBtn.textContent = running
    ? "Run In Progress..."
    : totalSelected > 0
      ? `Start Run (${totalSelected})`
      : "Start Selected";
}

function openRunStatusModal() {
  if (!runStatusModal) {
    return;
  }
  runStatusModal.classList.add("open");
  runStatusModal.setAttribute("aria-hidden", "false");
}

function closeRunStatusModal() {
  if (!runStatusModal) {
    return;
  }
  runStatusModal.classList.remove("open");
  runStatusModal.setAttribute("aria-hidden", "true");
}

function renderNumbers() {
  syncManualSelection();

  if (!availableNumbers.length) {
    numbersBody.innerHTML = '<tr><td colspan="3" class="empty">No unchecked numbers found.</td></tr>';
    updateSelectAllState();
    updateSelectionSummary();
    updateStartButton();
    return;
  }

  const autoRows = new Set(getAutoSelectedRows());

  numbersBody.innerHTML = availableNumbers.map((item) => `
    <tr class="${autoRows.has(item.row) ? "is-batch-selected" : ""}">
      <td>
        <label class="check-cell">
          <input class="number-check" type="checkbox" value="${item.row}" ${(manualSelection.has(item.row) || autoRows.has(item.row)) ? "checked" : ""}>
          ${autoRows.has(item.row) ? '<span class="auto-chip">Auto</span>' : ""}
        </label>
      </td>
      <td>${item.number}</td>
      <td>${item.row}</td>
    </tr>
  `).join("");

  document.querySelectorAll(".number-check").forEach((input) => {
    input.addEventListener("change", () => {
      const row = Number(input.value);
      const autoSelected = autoRows.has(row);
      if (input.checked) {
        if (autoSelected) {
          autoExcludedRows.delete(row);
        } else {
          manualSelection.add(row);
        }
      } else {
        manualSelection.delete(row);
        if (autoSelected) {
          autoExcludedRows.add(row);
        }
      }
      renderNumbers();
    });
  });

  updateSelectAllState();
  updateSelectionSummary();
  updateStartButton();
  updateStickyOffsets();
}

function formatTimestamp(value) {
  return value ? String(value).replace("T", " ") : "";
}

function getJobCounts(job) {
  const counts = {
    waiting: 0,
    running: 0,
    done: 0,
    failed: 0,
  };

  (job.items || []).forEach((item) => {
    if (Object.prototype.hasOwnProperty.call(counts, item.status)) {
      counts[item.status] += 1;
    }
  });

  return counts;
}

function jobStatusLabel(status) {
  return {
    queued: "Queued",
    running: "Running",
    completed: "Completed",
    failed: "Failed",
  }[status] || "Idle";
}

function itemStatusLabel(status) {
  return {
    waiting: "Waiting",
    running: "Running",
    done: "Done",
    failed: "Failed",
  }[status] || "Waiting";
}

function buildJobSummary(job, counts) {
  const completed = Number(job.completed || 0);
  const total = Number(job.total || 0);
  const routeText = job.route_mode === "manual" && job.manual_route_target
    ? ` | Manual route ${job.manual_route_target}`
    : " | Default route";
  return `${jobStatusLabel(job.status)} | ${completed}/${total} processed | ${counts.running} running | ${counts.waiting} waiting | ${job.success_count} done | ${job.failure_count} failed${routeText}`;
}

function itemMetaLines(item) {
  const lines = [];

  if (item.result?.message) {
    lines.push(item.result.message);
  } else if (item.status === "running") {
    lines.push("This number is currently being created in CGRT.");
  } else {
    lines.push("Waiting for its turn.");
  }

  if (item.status === "done") {
    lines.push(item.marked_in_sheet ? "Marked in column B." : "Created, but column B was not updated.");
  } else if (item.status === "failed" && item.marked_in_sheet) {
    lines.push("Sheet update was completed before the failure was reported.");
  }

  const startedAt = formatTimestamp(item.started_at);
  const finishedAt = formatTimestamp(item.finished_at);
  if (startedAt && finishedAt) {
    lines.push(`Started ${startedAt} | Finished ${finishedAt}`);
  } else if (startedAt) {
    lines.push(`Started ${startedAt}`);
  }

  return lines;
}

function renderJob(job) {
  const completed = Number(job.completed || 0);
  const total = Number(job.total || 0);
  const percent = total ? Math.round((completed / total) * 100) : 0;
  const counts = getJobCounts(job);
  const summaryText = buildJobSummary(job, counts);

  if (progressBar) {
    progressBar.style.width = `${percent}%`;
  }
  if (modalProgressBar) {
    modalProgressBar.style.width = `${percent}%`;
  }
  if (jobSummary) {
    jobSummary.textContent = summaryText;
  }
  if (modalJobSummary) {
    modalJobSummary.textContent = summaryText;
  }

  counterElements.waiting.forEach((el) => { if (el) el.textContent = counts.waiting; });
  counterElements.running.forEach((el) => { if (el) el.textContent = counts.running; });
  counterElements.done.forEach((el) => { if (el) el.textContent = counts.done; });
  counterElements.failed.forEach((el) => { if (el) el.textContent = counts.failed; });

  if (!runStatusNote) {
    // Old cached HTML can still work without the new status note block.
  } else if (job.status === "completed") {
    runStatusNote.textContent = "Run completed. You can reopen the run window to review the finished list.";
  } else if (job.status === "failed") {
    runStatusNote.textContent = "Run failed. Open the run window to inspect the last processed number and error details.";
  } else {
    runStatusNote.textContent = "Open the run window to follow waiting, running, and completed numbers live.";
  }

  if (openRunStatusBtn) {
    openRunStatusBtn.disabled = !(job.items || []).length;
  }

  if (!(job.items || []).length) {
    resultsList.innerHTML = '<div class="empty-card">No items in this run.</div>';
    return;
  }

  resultsList.innerHTML = job.items.map((item) => {
    const lines = itemMetaLines(item)
      .map((line) => `<div class="result-meta">${line}</div>`)
      .join("");

    return `
      <div class="result-card ${item.status}">
        <div>
          <div class="result-number">${item.number}</div>
          <div class="result-meta">Row ${item.row}</div>
          ${lines}
        </div>
        <div class="badge ${item.status}">${itemStatusLabel(item.status)}</div>
      </div>
    `;
  }).join("");

  updateStickyOffsets();
}

async function loadNumbers() {
  setMessage("");
  sheetSummary.textContent = "Loading numbers from Google Sheet...";
  refreshBtn.disabled = true;

  try {
    const response = await fetch("/api/numbers");
    const data = await response.json();
    if (!response.ok || !data.ok) {
      throw new Error(data.message || "Failed to load numbers.");
    }

    availableNumbers = data.numbers || [];
    sheetSummary.textContent = `${availableNumbers.length} unchecked numbers ready from google sheet.`;
    renderNumbers();
  } catch (error) {
    availableNumbers = [];
    sheetSummary.textContent = "Could not load numbers.";
    numbersBody.innerHTML = `<tr><td colspan="3" class="empty">${error.message}</td></tr>`;
    setMessage(error.message, "error");
    updateSelectionSummary();
    updateStartButton();
  } finally {
    refreshBtn.disabled = false;
    updateStickyOffsets();
  }
}

async function createJob() {
  const rows = getSelectedRows();
  if (!rows.length) {
    setMessage("Select at least one number first.", "error");
    return;
  }

  const routeMode = getRouteMode();
  let manualRouteTarget = "";
  if (routeMode === "manual") {
    try {
      manualRouteTarget = validateManualRouteTarget(getManualRouteTarget());
    } catch (error) {
      setMessage(error.message, "error");
      manualRouteTargetInput?.focus();
      return;
    }
  }

  setMessage(`Starting ${rows.length} numbers...`, "info");
  startBtn.disabled = true;
  refreshBtn.disabled = true;

  try {
    const response = await fetch("/api/jobs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        rows,
        route_mode: routeMode,
        manual_route_target: manualRouteTarget,
      }),
    });
    const data = await response.json();
    if (!response.ok || !data.ok) {
      throw new Error(data.message || "Failed to start the CGRT job.");
    }

    activeJobId = data.job_id;
    renderJob(data.job);
    openRunStatusModal();
    clearPollTimer();
    pollJob();
  } catch (error) {
    activeJobId = null;
    setMessage(error.message, "error");
    refreshBtn.disabled = false;
    updateStartButton();
  }
}

async function pollJob() {
  if (!activeJobId) {
    return;
  }

  try {
    const response = await fetch(`/api/jobs/${activeJobId}`);
    const data = await response.json();
    if (!response.ok || !data.ok) {
      throw new Error(data.message || "Failed to load job status.");
    }

    renderJob(data.job);

    if (data.job.status === "completed" || data.job.status === "failed") {
      clearPollTimer();

      if (data.job.status === "completed") {
        setMessage("CGRT run finished. Successful numbers were marked in column B.", "info");
      } else {
        setMessage(data.job.error || "The CGRT run failed.", "error");
      }

      activeJobId = null;
      refreshBtn.disabled = false;
      updateStartButton();
      await loadNumbers();
      return;
    }

    pollTimer = window.setTimeout(pollJob, 1500);
  } catch (error) {
    setMessage(error.message, "error");
    pollTimer = window.setTimeout(pollJob, 2000);
  }
}

refreshBtn?.addEventListener("click", () => {
  if (!activeJobId) {
    loadNumbers();
  }
});

startBtn?.addEventListener("click", createJob);

selectAll?.addEventListener("change", () => {
  if (selectAll.checked) {
    availableNumbers.forEach((item) => manualSelection.add(item.row));
    autoExcludedRows.clear();
  } else {
    manualSelection.clear();
    autoExcludedRows.clear();
    if (batchSizeSelect) {
      batchSizeSelect.value = "0";
    }
  }
  renderNumbers();
});

batchSizeSelect?.addEventListener("change", () => {
  autoExcludedRows.clear();
  renderNumbers();
});
routeModeInputs.forEach((input) => {
  input.addEventListener("change", syncRouteControls);
});
manualRouteTargetInput?.addEventListener("input", () => {
  if (messageEl.classList.contains("error")) {
    setMessage("");
  }
});
manualRoutePresetSelect?.addEventListener("change", () => {
  syncRouteControls();
  if (messageEl.classList.contains("error")) {
    setMessage("");
  }
});
openRunStatusBtn?.addEventListener("click", openRunStatusModal);
closeRunStatusBtn?.addEventListener("click", closeRunStatusModal);

runStatusModal?.addEventListener("click", (event) => {
  if (event.target === runStatusModal) {
    closeRunStatusModal();
  }
});

window.addEventListener("beforeunload", clearPollTimer);
window.addEventListener("resize", updateStickyOffsets);
window.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && runStatusModal?.classList.contains("open")) {
    closeRunStatusModal();
  }
});

updateStickyOffsets();
updateSelectionSummary();
syncRouteControls();
loadNumbers();
