const monthInput = document.getElementById("monthly-report-month");
const refreshButton = document.getElementById("monthly-report-refresh");
const rangeLabel = document.getElementById("monthly-report-range");
const messageEl = document.getElementById("monthly-report-message");
const kpiTotal = document.getElementById("kpi-total");
const kpiCoordinated = document.getElementById("kpi-coordinated");
const kpiRate = document.getElementById("kpi-rate");
const kpiOpen = document.getElementById("kpi-open");
const trendChart = document.getElementById("monthly-trend-chart");
const trendEmptyState = document.getElementById("trend-empty-state");
const busiestMonthEl = document.getElementById("trend-busiest-month");
const bestCoordinationMonthEl = document.getElementById("best-coordination-month");
const boardsBreakdown = document.getElementById("boards-breakdown");
const coordinatedCountChip = document.getElementById("coordinated-count-chip");
const coordinatedTableBody = document.getElementById("coordinated-table-body");
const coordinatedEmptyState = document.getElementById("coordinated-empty-state");
const detailsTitle = document.getElementById("details-title");
const detailsChipLabel = document.getElementById("details-chip-label");
const activeFilterSummary = document.getElementById("active-filter-summary");

const BOARD_LABELS = {
  all: "כללי",
  support: "נימבוס",
  pais: "מפעל הפיס",
  "hot-kiryot": "הוט",
};

const METRIC_CONFIG = {
  all: {
    title: "כל הקריאות בחודש",
    chip: "קריאות מוצגות",
    summary: "כל הקריאות",
    match: () => true,
  },
  coordinated: {
    title: "קריאות מתואמות",
    chip: "קריאות מתואמות",
    summary: "קריאות מתואמות",
    match: (row) => row.status === "תואם",
  },
  coordination: {
    title: "קריאות שתואמו החודש",
    chip: "בסיס אחוז תיאום",
    summary: "אחוז תיאום",
    match: (row) => row.status === "תואם",
  },
  open: {
    title: "קריאות פתוחות",
    chip: "קריאות פתוחות",
    summary: "קריאות פתוחות",
    match: (row) => row.status !== "תואם" && row.status !== "בוצע" && row.status !== "נכשל" && row.status !== "Done",
  },
};

let activeReport = null;
let activeBoardFilter = "all";
let activeMetricFilter = "all";

function currentMonthValue() {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
}

function setMessage(text, isError = false) {
  messageEl.textContent = text;
  messageEl.style.color = isError ? "#ffbcb7" : "";
}

function summarizeRows(rows) {
  const total = rows.length;
  const coordinated = rows.filter((row) => row.status === "תואם").length;
  const open = rows.filter((row) => !["תואם", "בוצע", "נכשל", "Done"].includes(row.status)).length;
  const coordinationRate = total ? (coordinated / total) * 100 : 0;
  return { total, coordinated, open, coordinationRate };
}

function boardLabel(boardSlug) {
  return BOARD_LABELS[boardSlug] || boardSlug;
}

function rowsForBoard(boardSlug) {
  if (!activeReport) {
    return [];
  }
  const rows = Array.isArray(activeReport.all_tickets) ? activeReport.all_tickets : [];
  if (boardSlug === "all") {
    return rows;
  }
  return rows.filter((row) => row.board_slug === boardSlug);
}

function filteredRows() {
  const rows = rowsForBoard(activeBoardFilter);
  const metric = METRIC_CONFIG[activeMetricFilter] || METRIC_CONFIG.all;
  return rows.filter((row) => metric.match(row));
}

function syncBoardButtons() {
  document.querySelectorAll("[data-board-filter]").forEach((button) => {
    const isActive = button.dataset.boardFilter === activeBoardFilter;
    button.classList.toggle("is-active", isActive);
    button.setAttribute("aria-pressed", isActive ? "true" : "false");
  });
}

function syncMetricCards() {
  document.querySelectorAll("[data-metric-filter]").forEach((card) => {
    const isActive = card.dataset.metricFilter === activeMetricFilter;
    card.classList.toggle("is-active", isActive);
    card.setAttribute("aria-pressed", isActive ? "true" : "false");
  });
}

function renderSummary() {
  const summary = summarizeRows(rowsForBoard(activeBoardFilter));
  kpiTotal.textContent = summary.total;
  kpiCoordinated.textContent = summary.coordinated;
  kpiRate.textContent = `${summary.coordinationRate.toFixed(1).replace(".0", "")}%`;
  kpiOpen.textContent = summary.open;
}

function renderBoards(boards) {
  boardsBreakdown.innerHTML = boards.map((board) => {
    const isActive = board.slug === activeBoardFilter;
    return `
      <article class="board-card${isActive ? " is-active" : ""}" data-board-filter="${board.slug}" role="button" tabindex="0" aria-pressed="${isActive ? "true" : "false"}">
        <div class="board-card-head">
          <strong>${board.name}</strong>
          <span>${board.total} קריאות</span>
        </div>
        <div class="board-stats">
          <div>
            <strong>${board.coordinated}</strong>
            <span>תואם</span>
          </div>
          <div>
            <strong>${board.open}</strong>
            <span>פתוחות</span>
          </div>
        </div>
        <div class="board-progress" aria-hidden="true" style="--board-progress:${Math.max(Number(board.coordination_rate || 0), 3)}%">
          <span></span>
        </div>
        <div class="board-progress-meta">
          <span>אחוז תיאום</span>
          <strong>${Number(board.coordination_rate || 0).toFixed(1).replace(".0", "")}%</strong>
        </div>
      </article>
    `;
  }).join("");
}

function trendItemForBoard(item) {
  if (activeBoardFilter === "all") {
    return item;
  }
  const boardSummary = item?.boards?.[activeBoardFilter] || {};
  return {
    ...item,
    total: Number(boardSummary.total || 0),
    coordinated: Number(boardSummary.coordinated || 0),
    coordination_rate: Number(boardSummary.coordination_rate || 0),
  };
}

function renderTrend(months, selectedMonth) {
  const scopedMonths = (Array.isArray(months) ? months : []).map(trendItemForBoard);
  if (scopedMonths.length === 0) {
    trendChart.innerHTML = "";
    trendEmptyState.hidden = false;
    busiestMonthEl.textContent = "-";
    bestCoordinationMonthEl.textContent = "-";
    return;
  }

  trendEmptyState.hidden = false;
  const dataMonths = scopedMonths.filter((item) => Number(item.total || 0) > 0);
  const referenceMonths = dataMonths.length ? dataMonths : scopedMonths;
  const maxTotal = Math.max(...referenceMonths.map((item) => Number(item.total || 0)), 1);
  const maxCoordinated = Math.max(...referenceMonths.map((item) => Number(item.coordinated || 0)), 1);
  const busiest = referenceMonths.reduce((best, item) => (Number(item.total || 0) > Number(best.total || 0) ? item : best), referenceMonths[0]);
  const bestCoord = referenceMonths.reduce((best, item) => (
    Number(item.coordination_rate || 0) > Number(best.coordination_rate || 0) ? item : best
  ), referenceMonths[0]);

  busiestMonthEl.textContent = `${busiest.month_display} • ${busiest.total || 0}`;
  bestCoordinationMonthEl.textContent = `${bestCoord.month_display} • ${Number(bestCoord.coordination_rate || 0).toFixed(1).replace(".0", "")}%`;

  trendChart.innerHTML = scopedMonths.map((item) => {
    const totalHeight = Math.max((Number(item.total || 0) / maxTotal) * 100, item.total ? 12 : 0);
    const coordinatedHeight = Math.max((Number(item.coordinated || 0) / maxCoordinated) * 100, item.coordinated ? 12 : 0);
    const activeClass = item.month === selectedMonth ? " is-active" : "";
    const rateText = `${Number(item.coordination_rate || 0).toFixed(1).replace(".0", "")}%`;
    return `
      <button type="button" class="trend-bar-card${activeClass}" data-month="${item.month}" aria-label="טען חודש ${item.month_display}">
        <div class="trend-card-top">
          <strong class="trend-total">${item.total || 0}</strong>
          <span class="trend-rate">${rateText}</span>
        </div>
        <div class="trend-bars">
          <span
            class="trend-bar total"
            style="--total-height:${totalHeight}%"
            title="כחול = סה&quot;כ קריאות בחודש הזה: ${item.total || 0}"
            aria-label="סהכ קריאות: ${item.total || 0}"
          ></span>
          <span
            class="trend-bar coordinated"
            style="--coordinated-height:${coordinatedHeight}%"
            title="ירוק = קריאות מתואמות בחודש הזה: ${item.coordinated || 0}"
            aria-label="קריאות מתואמות: ${item.coordinated || 0}"
          ></span>
        </div>
        <span class="trend-month">${item.month_display}</span>
      </button>
    `;
  }).join("");

  trendEmptyState.hidden = scopedMonths.length !== 0;
}

function renderDetails() {
  const rows = filteredRows();
  const metric = METRIC_CONFIG[activeMetricFilter] || METRIC_CONFIG.all;
  const boardText = boardLabel(activeBoardFilter);

  detailsTitle.textContent = metric.title;
  detailsChipLabel.textContent = metric.chip;
  activeFilterSummary.textContent = `${boardText} • ${metric.summary}`;
  coordinatedCountChip.textContent = rows.length;
  coordinatedEmptyState.hidden = rows.length > 0;
  coordinatedEmptyState.textContent = `אין תוצאות עבור ${boardText} • ${metric.summary}.`;

  coordinatedTableBody.innerHTML = rows.map((row) => {
    const visitLabel = [row.visit_date || "", row.visit_hours || ""].filter(Boolean).join(" | ") || "-";
    const secondary = row.secondary_value || "-";
    const worker = row.coordinated_worker || row.assigned_to || "-";
    return `
      <tr>
        <td><span class="board-badge">${row.board_name}</span></td>
        <td class="coordinated-primary">${row.reference_number || row.ticket_id || "-"}</td>
        <td><div class="coordinated-primary">${row.business_name || "-"}</div></td>
        <td class="coordinated-secondary">${secondary}</td>
        <td>${worker}</td>
        <td>${visitLabel}</td>
        <td>${row.created_at_display || "-"}</td>
      </tr>
    `;
  }).join("");
}

function renderReport(report) {
  activeReport = report;
  rangeLabel.textContent = `${report.date_from} - ${report.date_to}`;
  renderSummary();
  renderBoards(Array.isArray(report.boards) ? report.boards : []);
  renderTrend(Array.isArray(report.trend_months) ? report.trend_months : [], report.month);
  renderDetails();
  syncBoardButtons();
  syncMetricCards();
}

function setBoardFilter(filterValue) {
  activeBoardFilter = BOARD_LABELS[filterValue] ? filterValue : "all";
  if (!activeReport) {
    syncBoardButtons();
    return;
  }
  renderSummary();
  renderBoards(Array.isArray(activeReport.boards) ? activeReport.boards : []);
  renderTrend(Array.isArray(activeReport.trend_months) ? activeReport.trend_months : [], activeReport.month);
  renderDetails();
  syncBoardButtons();
}

function setMetricFilter(filterValue) {
  activeMetricFilter = METRIC_CONFIG[filterValue] ? filterValue : "all";
  if (!activeReport) {
    syncMetricCards();
    return;
  }
  renderDetails();
  syncMetricCards();
}

async function loadReport() {
  const month = monthInput.value || currentMonthValue();
  monthInput.value = month;
  refreshButton.disabled = true;
  setMessage("טוען דו\"ח חודשי...");

  try {
    const response = await fetch(`/tickets-monthly-report-data?${new URLSearchParams({ month }).toString()}`);
    const data = await response.json();
    if (!response.ok || !data.ok) {
      throw new Error(data.message || "טעינת הדוח נכשלה");
    }
    renderReport(data.report || {});
    setMessage("");
  } catch (error) {
    setMessage(`שגיאה בטעינת הדוח: ${error.message}`, true);
  } finally {
    refreshButton.disabled = false;
  }
}

monthInput.value = currentMonthValue();
refreshButton.addEventListener("click", loadReport);
monthInput.addEventListener("change", loadReport);

document.addEventListener("click", (event) => {
  const boardTrigger = event.target.closest("[data-board-filter]");
  if (boardTrigger) {
    setBoardFilter(boardTrigger.dataset.boardFilter);
    return;
  }

  const metricTrigger = event.target.closest("[data-metric-filter]");
  if (metricTrigger) {
    setMetricFilter(metricTrigger.dataset.metricFilter);
  }
});

document.addEventListener("keydown", (event) => {
  const trigger = event.target.closest("[data-board-filter], [data-metric-filter]");
  if (!trigger) {
    return;
  }
  if (event.key !== "Enter" && event.key !== " ") {
    return;
  }
  event.preventDefault();
  if (trigger.dataset.boardFilter) {
    setBoardFilter(trigger.dataset.boardFilter);
    return;
  }
  if (trigger.dataset.metricFilter) {
    setMetricFilter(trigger.dataset.metricFilter);
  }
});

trendChart.addEventListener("click", (event) => {
  const trigger = event.target.closest("[data-month]");
  if (!trigger) {
    return;
  }
  monthInput.value = trigger.dataset.month;
  loadReport();
});

loadReport();
