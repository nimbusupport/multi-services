const form = document.getElementById("feature-status-form");
const monthInput = document.getElementById("status-month-input");
const queryTypeSelect = document.getElementById("query-type-select");
const queryInput = document.getElementById("query-input");
const queryTextField = document.getElementById("query-text-field");
const statusFilterSelect = document.getElementById("status-filter-select");
const projectManagerQueryField = document.getElementById("project-manager-query-field");
const projectManagerFilterSelect = document.getElementById("project-manager-filter-select");
const button = document.getElementById("lookup-submit-btn");
const resetButton = document.getElementById("lookup-reset-btn");
const message = document.getElementById("lookup-message");
const statusCounterGrid = document.getElementById("status-counter-grid");
const summaryGrid = document.getElementById("feature-status-summary");
const results = document.getElementById("feature-status-results");
const toolbarSurface = document.querySelector(".toolbar-surface");
const summarySurface = document.querySelector(".summary-surface");
const resultsSurface = document.querySelector(".results-surface");
const summaryTotalCount = document.getElementById("summary-total-count");
const summaryMonthLabel = document.getElementById("summary-month-label");
const summaryDoneCount = document.getElementById("summary-done-count");
const summaryWaitingCount = document.getElementById("summary-waiting-count");
const summaryServicesCount = document.getElementById("summary-services-count");
const activeFilterLabel = document.getElementById("active-filter-label");
const resultsCountLabel = document.getElementById("results-count-label");
const resultsExportActions = document.getElementById("results-export-actions");
const resultsExportHint = document.getElementById("results-export-hint");
const exportButtons = Array.from(document.querySelectorAll("[data-export-format]"));

let currentPayload = null;

function looksLikeBrokenHebrew(value) {
  const text = String(value || "");
  return /[-]/.test(text) || (text.match(/׳/g) || []).length >= 2;
}

function repairBrokenHebrew(value) {
  const text = String(value || "");
  if (!looksLikeBrokenHebrew(text)) {
    return text;
  }
  const chars = [];
  for (const ch of text) {
    const code = ch.charCodeAt(0);
    chars.push(code <= 0xFF ? String.fromCharCode(code) : ch);
  }
  try {
    return decodeURIComponent(escape(chars.join("")));
  } catch {
    return text;
  }
}

function normalizeLegacyHebrewData(value) {
  if (Array.isArray(value)) {
    return value.map(normalizeLegacyHebrewData);
  }
  if (value && typeof value === "object") {
    return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, normalizeLegacyHebrewData(item)]));
  }
  if (typeof value === "string") {
    return repairBrokenHebrew(value);
  }
  return value;
}

function currentMonthValue() {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function normalizeStatusClass(status) {
  const value = String(status || "").trim();
  if (value === "בוצע") return "done";
  if (value === "ממתין") return "waiting";
  return "other";
}

function statusCounterTone(label) {
  const value = String(label || "").trim();
  if (value === "בוצע") return "tone-done";
  if (value === "ממתין") return "tone-waiting";
  if (value === "נשלחה הודעה") return "tone-sent";
  if (value === "לא הוגדר") return "tone-undefined";
  if (value === "טעות במספר") return "tone-error";
  if (value === "סטטוס אחר") return "tone-other";
  return "tone-neutral";
}

function setMessage(text, isError = false) {
  message.textContent = text;
  message.classList.toggle("error", isError);
}

function syncQueryMode() {
  const isProjectManagerMode = queryTypeSelect.value === "project_manager";
  queryTextField?.classList.toggle("hidden", isProjectManagerMode);
  projectManagerQueryField?.classList.toggle("hidden", !isProjectManagerMode);
  if (isProjectManagerMode) {
    queryInput.value = "";
    return;
  }
  projectManagerFilterSelect.value = "";
}

function buildRequestParams() {
  const queryType = queryTypeSelect.value;
  const projectManagerValue = projectManagerFilterSelect.value;
  const queryValue = queryType === "project_manager" ? projectManagerValue : queryInput.value.trim();
  return new URLSearchParams({
    month: monthInput.value || currentMonthValue(),
    query: queryValue,
    query_type: queryType,
    status: statusFilterSelect.value,
    project_manager: queryType === "project_manager" ? "" : projectManagerValue,
  });
}

function activeProjectManagerValue(payload) {
  if (!payload) {
    return "";
  }
  if (payload.query_type === "project_manager") {
    return String(payload.query || "").trim();
  }
  return String(payload.project_manager_filter || "").trim();
}

function syncExportState(payload) {
  currentPayload = payload;
  const canExport = Boolean(activeProjectManagerValue(payload)) && Number(payload?.summary?.total_entries || 0) > 0;
  resultsExportActions?.classList.toggle("hidden", !canExport);
  resultsExportHint?.classList.toggle("hidden", canExport);
  exportButtons.forEach((buttonElement) => {
    buttonElement.disabled = !canExport;
  });
}

function setLoadingState(isLoading) {
  button.disabled = isLoading;
  if (resetButton) {
    resetButton.disabled = isLoading;
  }
  toolbarSurface?.classList.toggle("is-loading", isLoading);
  summarySurface?.classList.toggle("is-loading", isLoading);
  resultsSurface?.classList.toggle("is-loading", isLoading);
}

function renderLoadingState() {
  results.innerHTML = Array.from({ length: 6 }).map(() => `
    <article class="service-status-skeleton">
      <div class="skeleton-line title"></div>
      <div class="skeleton-line short"></div>
      <div class="skeleton-line medium"></div>
      <div class="skeleton-line long"></div>
      <div class="skeleton-line medium"></div>
    </article>
  `).join("");
}

function syncStatusFilterOptions(statuses, selectedValue) {
  const normalizedStatuses = Array.isArray(statuses) ? [...statuses] : [];
  if (selectedValue === "סטטוס אחר" && !normalizedStatuses.includes("סטטוס אחר")) {
    normalizedStatuses.push("סטטוס אחר");
  }
  const options = ['<option value="">הכל</option>']
    .concat(normalizedStatuses.map((status) => `
      <option value="${escapeHtml(status)}" ${selectedValue === status ? "selected" : ""}>${escapeHtml(status)}</option>
    `));
  statusFilterSelect.innerHTML = options.join("");
}

function syncProjectManagerFilterOptions(managers, selectedValue) {
  const options = ['<option value="">הכל</option>']
    .concat((managers || []).map((manager) => `
      <option value="${escapeHtml(manager)}" ${selectedValue === manager ? "selected" : ""}>${escapeHtml(manager)}</option>
    `));
  projectManagerFilterSelect.innerHTML = options.join("");
}

function renderStatusCounters(payload) {
  const activeStatus = String(payload.status_filter || "");
  const counters = Array.isArray(payload.status_counts) ? payload.status_counts : [];
  statusCounterGrid.innerHTML = counters.map((item) => `
    <button
      type="button"
      class="status-counter-btn ${statusCounterTone(item.label)}${activeStatus === item.label ? " is-active" : ""}"
      data-status-counter="${escapeHtml(item.label)}"
      aria-pressed="${activeStatus === item.label ? "true" : "false"}"
    >
      <strong>${escapeHtml(item.count ?? 0)}</strong>
      <span>${escapeHtml(item.label || "")}</span>
    </button>
  `).join("");
}

function renderTopSummary(payload) {
  const summary = payload.summary || {};
  summaryTotalCount.textContent = summary.total_entries || 0;
  summaryMonthLabel.textContent = `חודש ${payload.month_display || "--/----"}`;
  summaryDoneCount.textContent = summary.done_count || 0;
  summaryWaitingCount.textContent = summary.waiting_count || 0;
  summaryServicesCount.textContent = summary.services_count || 0;
  resultsCountLabel.textContent = summary.total_entries || 0;

  const filterParts = [payload.status_filter || "כל הסטטוסים"];
  if (payload.query_type === "project_manager" && payload.query) {
    filterParts.push(payload.query);
  } else if (payload.project_manager_filter) {
    filterParts.push(payload.project_manager_filter);
  }
  activeFilterLabel.textContent = filterParts.join(" • ");
}

function renderSummary(payload) {
  const searchValue = payload.query || "ללא";

  summaryGrid.innerHTML = `
    <article class="summary-tile">
      <span>חיפוש פעיל</span>
      <strong>${escapeHtml(searchValue)}</strong>
    </article>
    <article class="summary-tile">
      <span>סוג חיפוש</span>
      <strong>${escapeHtml(queryTypeSelect.options[queryTypeSelect.selectedIndex]?.text || "כללי")}</strong>
    </article>
    <article class="summary-tile">
      <span>חודש מוצג</span>
      <strong>${escapeHtml(payload.month_display || "--/----")}</strong>
    </article>
    <article class="summary-tile">
      <span>מנהל פרויקט</span>
      <strong>${escapeHtml(payload.project_manager_filter || (payload.query_type === "project_manager" ? payload.query || "הכל" : "הכל"))}</strong>
    </article>
  `;
}

function renderServiceEntry(entry) {
  return `
    <div class="service-entry">
      <div class="entry-name">${escapeHtml(entry.business_name || "לא צוין")}</div>
      <div class="entry-meta">
        <span>שירות: ${escapeHtml(entry.service_label || "-")}</span>
        <span>סטטוס: <strong>${escapeHtml(entry.status || "לא הוגדר")}</strong></span>
        <span>מס' הזמנה: ${escapeHtml(entry.order_id || "-")}</span>
        <span>ח.פ: ${escapeHtml(entry.customer_id || "-")}</span>
        <span>מנהל פרויקט: ${escapeHtml(entry.project_manager || entry.project_manager_raw || "-")}</span>
        <span>תאריך: ${escapeHtml(entry.date_display || "-")}</span>
      </div>
    </div>
  `;
}

function renderResults(services) {
  if (!Array.isArray(services) || services.length === 0) {
    results.innerHTML = `
      <article class="service-status-card missing empty-state-card">
        <h3>לא נמצאו פיצ'רים</h3>
        <p class="service-empty">לא נמצאו פיצ'רים התואמים לחיפוש שנבחר.</p>
      </article>
    `;
    return;
  }

  const visibleServices = services.filter((service) => Array.isArray(service.entries) && service.entries.length > 0);
  const servicesToRender = visibleServices.length > 0 ? visibleServices : services;

  results.innerHTML = servicesToRender.map((service) => {
    const entries = Array.isArray(service.entries) ? service.entries : [];
    const statusValue = entries[0]?.status_category || entries[0]?.status || "";
    return `
      <article class="service-status-card ${service.found ? "found" : "missing"}">
        <h3>${escapeHtml(service.label || "")}</h3>
        <p class="service-status-sheet">${escapeHtml(service.sheet || "")}</p>
        ${service.found ? `
          <div class="status-chip-row">
            <span class="status-chip ${normalizeStatusClass(statusValue)}">${escapeHtml(statusValue)}</span>
            <span class="status-chip other">סה"כ ${escapeHtml(service.entry_count ?? 0)}</span>
            <span class="status-chip done">בוצע ${escapeHtml(service.done_count ?? 0)}</span>
            <span class="status-chip waiting">ממתין ${escapeHtml(service.waiting_count ?? 0)}</span>
          </div>
          <div class="service-entry-list">
            ${entries.map(renderServiceEntry).join("")}
          </div>
        ` : `
          <p class="service-empty">לא נמצאו פיצ'רים תחת שירות זה בחודש הנבחר.</p>
        `}
      </article>
    `;
  }).join("");
}

async function loadFeatureStatuses() {
  const month = monthInput.value || currentMonthValue();
  monthInput.value = month;
  setLoadingState(true);
  const originalButtonText = button.innerHTML;
  button.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i><span>טוען...</span>';
  setMessage("טוען את נתוני סטטוס הפיצ'רים...");
  renderLoadingState();

  try {
    const params = buildRequestParams();
    const res = await fetch(`/features-status-data?${params.toString()}`);
    const data = normalizeLegacyHebrewData(await res.json().catch(() => ({})));

    if (!res.ok || !data.ok) {
      throw new Error(data.message || "אירעה שגיאה בטעינת נתוני הפיצ'רים");
    }

    syncStatusFilterOptions(data.available_statuses || [], data.status_filter || "");
    const selectedProjectManager = data.query_type === "project_manager"
      ? (data.query || "")
      : (data.project_manager_filter || "");
    syncProjectManagerFilterOptions(data.available_project_managers || [], selectedProjectManager);
    renderTopSummary(data);
    renderStatusCounters(data);
    renderSummary(data);
    renderResults(Array.isArray(data.services) ? data.services : []);
    syncExportState(data);
    setMessage("הנתונים נטענו בהצלחה.");
  } catch (err) {
    statusCounterGrid.innerHTML = "";
    summaryGrid.innerHTML = "";
    results.innerHTML = "";
    syncExportState(null);
    setMessage(err.message || "אירעה שגיאה בטעינת נתוני הפיצ'רים", true);
  } finally {
    setLoadingState(false);
    button.innerHTML = originalButtonText;
  }
}

function resetFeatureStatusFilters() {
  monthInput.value = currentMonthValue();
  queryTypeSelect.value = "all";
  queryInput.value = "";
  statusFilterSelect.value = "";
  projectManagerFilterSelect.value = "";
  syncQueryMode();
  setMessage("המסננים אופסו ונטענו מחדש.");
  loadFeatureStatuses();
}


monthInput.value = currentMonthValue();
syncQueryMode();

form?.addEventListener("submit", async (event) => {
  event.preventDefault();
  await loadFeatureStatuses();
});

monthInput?.addEventListener("change", loadFeatureStatuses);
statusFilterSelect?.addEventListener("change", loadFeatureStatuses);
projectManagerFilterSelect?.addEventListener("change", () => {
  if (queryTypeSelect.value === "project_manager" && !projectManagerFilterSelect.value) {
    syncExportState(null);
    setMessage("בחר/י מנהל פרויקט כדי לטעון את הנתונים.");
    return;
  }
  loadFeatureStatuses();
});
queryTypeSelect?.addEventListener("change", () => {
  syncQueryMode();
  if (queryTypeSelect.value === "project_manager") {
    if (!projectManagerFilterSelect.value) {
      syncExportState(null);
      setMessage("בחר/י מנהל פרויקט כדי לטעון את הנתונים.");
      return;
    }
    loadFeatureStatuses();
    return;
  }
  loadFeatureStatuses();
});
resetButton?.addEventListener("click", resetFeatureStatusFilters);

exportButtons.forEach((buttonElement) => {
  buttonElement.addEventListener("click", () => {
    if (!currentPayload) {
      return;
    }
    const format = String(buttonElement.dataset.exportFormat || "pdf").toLowerCase();
    const params = buildRequestParams();
    params.set("format", format);
    window.location.href = `/features-status-export?${params.toString()}`;
  });
});

statusCounterGrid?.addEventListener("click", (event) => {
  const trigger = event.target.closest("[data-status-counter]");
  if (!trigger) {
    return;
  }
  const nextValue = String(trigger.dataset.statusCounter || "");
  statusFilterSelect.value = statusFilterSelect.value === nextValue ? "" : nextValue;
  loadFeatureStatuses().then(() => {
    resultsSurface?.scrollIntoView({ behavior: "smooth", block: "start" });
  });
});

syncExportState(null);
loadFeatureStatuses();
