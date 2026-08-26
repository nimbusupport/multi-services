const monthFilter = document.getElementById("month-filter");
const loadButton = document.getElementById("load-report");
const detailExportButton = document.getElementById("recordings-detail-export");
const exportButton = document.getElementById("export-btn");
const exportFormat = document.getElementById("export-format");
const reportBody = document.getElementById("report-body");
const reportTotal = document.getElementById("report-total");
const reportMonthLabel = document.getElementById("report-month-label");
const reportMessage = document.getElementById("report-message");
const printArea = document.getElementById("print-area");
const reportLoading = document.getElementById("report-loading");
const reportLoadingText = document.getElementById("report-loading-text");
const trendChart = document.getElementById("trend-chart");
const trendRange = document.getElementById("trend-range");
const trendMessage = document.getElementById("trend-message");

let currentReport = null;

function currentMonthValue() {
  const now = new Date();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  return `${now.getFullYear()}-${month}`;
}

function setMessage(text, isError = false) {
  reportMessage.textContent = text;
  reportMessage.classList.toggle("error", isError);
}

function setTrendMessage(text, isError = false) {
  trendMessage.textContent = text;
  trendMessage.classList.toggle("error", isError);
}

function setReportLoading(isLoading, text = "Loading report...") {
  reportLoading.hidden = !isLoading;
  reportLoadingText.textContent = text;
  printArea.classList.toggle("is-loading", isLoading);
  loadButton.disabled = isLoading;
  monthFilter.disabled = isLoading;
  trendChart.querySelectorAll(".trend-bar-card").forEach((card) => {
    card.disabled = isLoading;
  });
}

function renderReport(report) {
  currentReport = report;
  reportMonthLabel.textContent = `\u05d7\u05d5\u05d3\u05e9 ${report.month_display}`;
  reportTotal.textContent = report.total;
  reportBody.innerHTML = report.services
    .map((service) => {
      const children = (service.children || [])
        .map((child) => `
          <tr class="sub-row">
            <td>
              <span class="report-service sub-service">
                <span class="service-dot sub-dot"></span>
                <span>${child.label}</span>
              </span>
            </td>
            <td class="counter-cell sub-counter">${child.count}</td>
          </tr>
        `)
        .join("");

      return `
        <tr>
          <td>
            <span class="report-service">
              <span class="service-dot"></span>
              <span>${service.label}</span>
            </span>
          </td>
          <td class="counter-cell">${service.count}</td>
        </tr>
        ${children}
      `;
    })
    .join("");
}

function renderTrendChart(months, startMonth, endMonth) {
  if (!months.length) {
    trendChart.innerHTML = "";
    trendRange.textContent = "--/---- - --/----";
    setTrendMessage("No monthly data available.", true);
    return;
  }

  const maxTotal = Math.max(...months.map((item) => item.total), 1);
  trendRange.textContent = `${startMonth} - ${endMonth}`;
  trendChart.innerHTML = months
    .map((item) => {
      const height = Math.max((item.total / maxTotal) * 100, item.total > 0 ? 8 : 0);
      const isActive = monthFilter.value === item.month;
      return `
        <button
          type="button"
          class="trend-bar-card${isActive ? " active" : ""}"
          data-month="${item.month}"
          aria-label="Load report for ${item.month_display}"
        >
          <strong class="trend-value">${item.total}</strong>
          <div class="trend-bar-track">
            <div class="trend-bar-fill" style="height: ${height}%"></div>
          </div>
          <span class="trend-label">${item.month_display}</span>
        </button>
      `;
    })
    .join("");
  setTrendMessage("");
}

async function loadReport(loadingText = "Loading report...") {
  const month = monthFilter.value || currentMonthValue();
  monthFilter.value = month;
  setMessage("\u05d8\u05d5\u05e2\u05df \u05e0\u05ea\u05d5\u05e0\u05d9\u05dd...");
  setReportLoading(true, loadingText);

  try {
    const params = new URLSearchParams({ month });
    const res = await fetch(`/features-report-data?${params.toString()}`);
    const data = await res.json();
    if (!res.ok || !data.ok) {
      throw new Error(data.error || "Failed to load report");
    }
    renderReport(data.report);
    renderTrendChartFromDomSelection(month);
    setMessage("");
  } catch (error) {
    currentReport = null;
    reportBody.innerHTML = "";
    reportTotal.textContent = "0";
    setMessage(`\u05e9\u05d2\u05d9\u05d0\u05d4 \u05d1\u05d8\u05e2\u05d9\u05e0\u05ea \u05d4\u05d3\u05d5\"\u05d7: ${error.message}`, true);
  } finally {
    setReportLoading(false);
  }
}

async function loadMonthlyTotals() {
  setTrendMessage("Loading monthly totals...");

  try {
    const res = await fetch("/features-report-monthly-totals");
    const data = await res.json();
    if (!res.ok || !data.ok) {
      throw new Error(data.error || "Failed to load monthly totals");
    }
    renderTrendChart(data.months || [], data.start_month, data.end_month);
  } catch (error) {
    trendChart.innerHTML = "";
    trendRange.textContent = "--/---- - --/----";
    setTrendMessage(`Failed to load monthly totals: ${error.message}`, true);
  }
}

async function loadReportForMonth(month) {
  monthFilter.value = month;
  await loadReport(`Loading ${month}...`);
  renderTrendChartFromDomSelection(month);
  printArea.scrollIntoView({ behavior: "smooth", block: "start" });
}

function renderTrendChartFromDomSelection(selectedMonth) {
  trendChart.querySelectorAll(".trend-bar-card").forEach((card) => {
    card.classList.toggle("active", card.dataset.month === selectedMonth);
  });
}

function downloadCsv() {
  if (!currentReport) {
    setMessage("\u05d0\u05d9\u05df \u05e0\u05ea\u05d5\u05e0\u05d9\u05dd \u05dc\u05d9\u05d9\u05e6\u05d5\u05d0. \u05dc\u05d7\u05e5 \u05d4\u05e6\u05d2 \u05e7\u05d5\u05d3\u05dd.", true);
    return;
  }

  const rows = [["Service", "Month", "Completed Count"]];
  currentReport.services.forEach((service) => {
    rows.push([service.label, currentReport.month_display, service.count]);
    (service.children || []).forEach((child) => {
      rows.push([`${service.label} - ${child.label}`, currentReport.month_display, child.count]);
    });
  });
  rows.push(["Total", currentReport.month_display, currentReport.total]);

  const csv = rows
    .map((row) => row.map((value) => `"${String(value).replace(/"/g, "\"\"")}"`).join(","))
    .join("\r\n");
  const blob = new Blob([`\uFEFF${csv}`], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `features-report-${currentReport.month}.csv`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function exportReport() {
  if (exportFormat.value === "csv") {
    downloadCsv();
    return;
  }

  if (exportFormat.value === "pdf") {
    if (!currentReport) {
      setMessage("\u05d0\u05d9\u05df \u05e0\u05ea\u05d5\u05e0\u05d9\u05dd \u05dc\u05d9\u05d9\u05e6\u05d5\u05d0. \u05dc\u05d7\u05e5 \u05d4\u05e6\u05d2 \u05e7\u05d5\u05d3\u05dd.", true);
      return;
    }
    window.print();
    return;
  }

  setMessage("\u05d1\u05d7\u05e8 \u05e4\u05d5\u05e8\u05de\u05d8 CSV \u05d0\u05d5 PDF.", true);
}

function exportRecordingsDetail() {
  const month = monthFilter.value || currentMonthValue();
  monthFilter.value = month;
  window.location.href = `/features-report-recordings-detail?${new URLSearchParams({ month }).toString()}`;
}

monthFilter.value = currentMonthValue();
loadButton.addEventListener("click", loadReport);
monthFilter.addEventListener("change", loadReport);
exportButton.addEventListener("click", exportReport);
detailExportButton.addEventListener("click", exportRecordingsDetail);
trendChart.addEventListener("click", async (event) => {
  const card = event.target.closest(".trend-bar-card");
  if (!card) {
    return;
  }
  await loadReportForMonth(card.dataset.month);
});
loadReport();
loadMonthlyTotals();
