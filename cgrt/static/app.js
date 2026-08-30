const numbersBody = document.getElementById("numbersBody");
const sheetSummary = document.getElementById("sheetSummary");
const jobSummary = document.getElementById("jobSummary");
const messageEl = document.getElementById("message");
const startBtn = document.getElementById("startBtn");
const refreshBtn = document.getElementById("refreshBtn");
const selectAll = document.getElementById("selectAll");
const progressBar = document.getElementById("progressBar");
const resultsList = document.getElementById("resultsList");
const statusPanel = document.querySelector(".panel-status");
const numbersHead = document.querySelector(".numbers-head");

let availableNumbers = [];
let activeJobId = null;
let pollTimer = null;

function updateStickyOffsets() {
  const root = document.documentElement;
  const statusHeight = statusPanel ? Math.ceil(statusPanel.getBoundingClientRect().height) : 96;
  const headHeight = numbersHead ? Math.ceil(numbersHead.getBoundingClientRect().height) : 96;

  root.style.setProperty("--status-offset", `${statusHeight}px`);
  root.style.setProperty("--numbers-head-height", `${headHeight}px`);
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

function getSelectedRows() {
  return Array.from(document.querySelectorAll(".number-check:checked"))
    .map((input) => Number(input.value))
    .filter((value) => Number.isInteger(value));
}

function updateStartButton() {
  const hasSelection = getSelectedRows().length > 0;
  const running = Boolean(activeJobId);
  startBtn.disabled = !hasSelection || running;
}

function renderNumbers() {
  if (!availableNumbers.length) {
    numbersBody.innerHTML = '<tr><td colspan="3" class="empty">No unchecked numbers found.</td></tr>';
    updateStartButton();
    return;
  }

  numbersBody.innerHTML = availableNumbers.map((item) => `
    <tr>
      <td><input class="number-check" type="checkbox" value="${item.row}"></td>
      <td>${item.number}</td>
      <td>${item.row}</td>
    </tr>
  `).join("");

  document.querySelectorAll(".number-check").forEach((input) => {
    input.addEventListener("change", updateStartButton);
  });

  updateStartButton();
}

function renderJob(job) {
  const completed = Number(job.completed || 0);
  const total = Number(job.total || 0);
  const percent = total ? Math.round((completed / total) * 100) : 0;

  progressBar.style.width = `${percent}%`;
  jobSummary.textContent = `${job.status.toUpperCase()} | ${completed}/${total} completed | ${job.success_count} success | ${job.failure_count} failed`;

  if (!job.items.length) {
    resultsList.innerHTML = '<div class="empty-card">No items in this run.</div>';
    return;
  }

  resultsList.innerHTML = job.items.map((item) => {
    const resultMessage = item.result?.message || "Waiting to run.";
    const markedText = item.marked_in_sheet ? "Marked in column B" : "Not marked in sheet";

    return `
      <div class="result-card">
        <div>
          <div class="result-number">${item.number}</div>
          <div class="result-meta">Row ${item.row} | ${resultMessage}</div>
          <div class="result-meta">${markedText}</div>
        </div>
        <div class="badge ${item.status}">${item.status}</div>
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
    sheetSummary.textContent = `${availableNumbers.length} unchecked numbers ready from חיפ_סמס.`;
    selectAll.checked = false;
    renderNumbers();
    updateStickyOffsets();
  } catch (error) {
    availableNumbers = [];
    sheetSummary.textContent = "Could not load numbers.";
    numbersBody.innerHTML = `<tr><td colspan="3" class="empty">${error.message}</td></tr>`;
    setMessage(error.message, "error");
  } finally {
    refreshBtn.disabled = false;
    updateStartButton();
  }
}

async function createJob() {
  const rows = getSelectedRows();
  if (!rows.length) {
    setMessage("Select at least one number first.", "error");
    return;
  }

  setMessage(`Starting ${rows.length} selected numbers...`, "info");
  startBtn.disabled = true;
  refreshBtn.disabled = true;

  try {
    const response = await fetch("/api/jobs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ rows }),
    });
    const data = await response.json();
    if (!response.ok || !data.ok) {
      throw new Error(data.message || "Failed to start the CGRT job.");
    }

    activeJobId = data.job_id;
    renderJob(data.job);
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
      if (data.job.status === "completed") {
        setMessage("CGRT run finished. Successful numbers were marked in column B.", "info");
      } else {
        setMessage(data.job.error || "The CGRT run failed.", "error");
      }

      activeJobId = null;
      refreshBtn.disabled = false;
      await loadNumbers();
      return;
    }

    pollTimer = window.setTimeout(pollJob, 1500);
  } catch (error) {
    setMessage(error.message, "error");
    pollTimer = window.setTimeout(pollJob, 2000);
  }
}

refreshBtn.addEventListener("click", () => {
  if (!activeJobId) {
    loadNumbers();
  }
});

startBtn.addEventListener("click", createJob);

selectAll.addEventListener("change", () => {
  document.querySelectorAll(".number-check").forEach((input) => {
    input.checked = selectAll.checked;
  });
  updateStartButton();
});

window.addEventListener("beforeunload", () => {
  if (pollTimer) {
    window.clearTimeout(pollTimer);
  }
});

window.addEventListener("resize", updateStickyOffsets);

updateStickyOffsets();
loadNumbers();
