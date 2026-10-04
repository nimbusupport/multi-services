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
const reportServicesCount = document.getElementById("report-services-count");
const reportChildrenCount = document.getElementById("report-children-count");
const reportTopServiceCount = document.getElementById("report-top-service-count");
const reportTopServiceLabel = document.getElementById("report-top-service-label");
const reportSummaryTotalChip = document.getElementById("report-summary-total-chip");
const insightMonth = document.getElementById("insight-month");
const insightTopService = document.getElementById("insight-top-service");
const insightAverage = document.getElementById("insight-average");
const trendPeak = document.getElementById("trend-peak");

let currentReport = null;

function isQuotaExceededMessage(message) {
  const text = String(message || "").toLowerCase();
  return text.includes("quota exceeded") || (text.includes("429") && text.includes("sheets.googleapis.com"));
}

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

function setReportLoading(isLoading, text = "טוען דוח...") {
  reportLoading.hidden = !isLoading;
  reportLoadingText.textContent = text;
  printArea.classList.toggle("is-loading", isLoading);
  loadButton.disabled = isLoading;
  monthFilter.disabled = isLoading;
  trendChart.querySelectorAll(".trend-bar-card").forEach((card) => {
    card.disabled = isLoading;
  });
}

function reportInsights(report) {
  const services = Array.isArray(report.services) ? report.services : [];
  const servicesCount = services.filter((service) => Number(service.count || 0) > 0).length;
  const topService = services.reduce((best, service) => {
    if (!best || Number(service.count || 0) > Number(best.count || 0)) {
      return service;
    }
    return best;
  }, null);
  const average = services.length ? (Number(report.total || 0) / services.length) : 0;
  return {
    servicesCount,
    topService,
    average,
  };
}

function renderReport(report) {
  currentReport = report;
  reportMonthLabel.textContent = `\u05d7\u05d5\u05d3\u05e9 ${report.month_display}`;
  reportTotal.textContent = report.total;
  reportSummaryTotalChip.textContent = report.total;
  insightMonth.textContent = report.month_display || "--/----";
  const insights = reportInsights(report);
  reportServicesCount.textContent = insights.servicesCount;
  reportChildrenCount.textContent = Number(report.waiting_total || 0);
  reportTopServiceCount.textContent = insights.topService ? insights.topService.count : 0;
  reportTopServiceLabel.textContent = insights.topService ? insights.topService.label : "-";
  insightTopService.textContent = insights.topService ? insights.topService.label : "-";
  insightAverage.textContent = insights.average.toFixed(1).replace(".0", "");
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
    trendPeak.textContent = "-";
    setTrendMessage("אין נתונים חודשיים להצגה.", true);
    return;
  }

  const maxTotal = Math.max(...months.map((item) => item.total), 1);
  const peakMonth = months.reduce((best, item) => (item.total > best.total ? item : best), months[0]);
  trendRange.textContent = `${startMonth} - ${endMonth}`;
  trendPeak.textContent = `${peakMonth.month_display} • ${peakMonth.total}`;
  trendChart.innerHTML = months
    .map((item) => {
      const height = Math.max((item.total / maxTotal) * 100, item.total > 0 ? 8 : 0);
      const isActive = monthFilter.value === item.month;
      return `
        <button
          type="button"
          class="trend-bar-card${isActive ? " active" : ""}"
          data-month="${item.month}"
          aria-label="טען דוח עבור ${item.month_display}"
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

async function loadReport(loadingText = "טוען דוח...") {
  const month = monthFilter.value || currentMonthValue();
  monthFilter.value = month;
  setMessage("\u05d8\u05d5\u05e2\u05df \u05e0\u05ea\u05d5\u05e0\u05d9\u05dd...");
  setReportLoading(true, loadingText);

  try {
    for (let attempt = 0; attempt < 2; attempt += 1) {
      try {
        const params = new URLSearchParams({ month });
        const res = await fetch(`/features-report-data?${params.toString()}`);
        const data = normalizeLegacyHebrewData(await res.json());
        if (!res.ok || !data.ok) {
          throw new Error(data.error || "שגיאה בטעינת הדוח");
        }
        renderReport(data.report);
        renderTrendChartFromDomSelection(month);
        setMessage("");
        return;
      } catch (error) {
        if (attempt === 0 && isQuotaExceededMessage(error.message)) {
          await new Promise((resolve) => window.setTimeout(resolve, 1500));
          continue;
        }
        throw error;
      }
    }
  } catch (error) {
    currentReport = null;
    reportBody.innerHTML = "";
    reportTotal.textContent = "0";
    reportSummaryTotalChip.textContent = "0";
    reportServicesCount.textContent = "0";
    reportChildrenCount.textContent = "0";
    reportTopServiceCount.textContent = "0";
    reportTopServiceLabel.textContent = "-";
    insightMonth.textContent = "--/----";
    insightTopService.textContent = "-";
    insightAverage.textContent = "0";
    setMessage(`\u05e9\u05d2\u05d9\u05d0\u05d4 \u05d1\u05d8\u05e2\u05d9\u05e0\u05ea \u05d4\u05d3\u05d5\"\u05d7: ${error.message}`, true);
  } finally {
    setReportLoading(false);
  }
}

async function loadMonthlyTotals() {
  setTrendMessage("טוען סיכום חודשי...");

  try {
    for (let attempt = 0; attempt < 2; attempt += 1) {
      try {
        const res = await fetch("/features-report-monthly-totals");
        const data = normalizeLegacyHebrewData(await res.json());
        if (!res.ok || !data.ok) {
          throw new Error(data.error || "שגיאה בטעינת הסיכום החודשי");
        }
        renderTrendChart(data.months || [], data.start_month, data.end_month);
        return;
      } catch (error) {
        if (attempt === 0 && isQuotaExceededMessage(error.message)) {
          await new Promise((resolve) => window.setTimeout(resolve, 1500));
          continue;
        }
        throw error;
      }
    }
  } catch (error) {
    trendChart.innerHTML = "";
    trendRange.textContent = "--/---- - --/----";
    trendPeak.textContent = "-";
    setTrendMessage(`שגיאה בטעינת הסיכום החודשי: ${error.message}`, true);
  }
}

async function loadReportForMonth(month) {
  monthFilter.value = month;
  await loadReport(`טוען את ${month}...`);
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

  const rows = [["שירות", "חודש", "כמות שבוצעה"]];
  currentReport.services.forEach((service) => {
    rows.push([service.label, currentReport.month_display, service.count]);
    (service.children || []).forEach((child) => {
      rows.push([`${service.label} - ${child.label}`, currentReport.month_display, child.count]);
    });
  });
  rows.push(["סה\"כ", currentReport.month_display, currentReport.total]);

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

function downloadPdf() {
  if (!currentReport) {
    setMessage("\u05d0\u05d9\u05df \u05e0\u05ea\u05d5\u05e0\u05d9\u05dd \u05dc\u05d9\u05d9\u05e6\u05d5\u05d0. \u05dc\u05d7\u05e5 \u05d4\u05e6\u05d2 \u05e7\u05d5\u05d3\u05dd.", true);
    return;
  }

  const params = new URLSearchParams({
    month: currentReport.month,
    format: "pdf",
  });
  window.location.href = `/features-report-export?${params.toString()}`;
}

async function downloadFileFromEndpoint(url, fallbackErrorMessage) {
  try {
    const res = await fetch(url, { credentials: "same-origin" });
    if (!res.ok) {
      let errorMessage = fallbackErrorMessage;
      const contentType = res.headers.get("content-type") || "";
      if (contentType.includes("application/json")) {
        const data = normalizeLegacyHebrewData(await res.json());
        errorMessage = data.error || data.message || fallbackErrorMessage;
      } else {
        const text = await res.text();
        errorMessage = text || fallbackErrorMessage;
      }
      throw new Error(errorMessage);
    }

    const blob = await res.blob();
    const downloadUrl = URL.createObjectURL(blob);
    const link = document.createElement("a");
    const disposition = res.headers.get("content-disposition") || "";
    const fileNameMatch = disposition.match(/filename\*?=(?:UTF-8''|"?)([^";]+)/i);

    link.href = downloadUrl;
    link.download = fileNameMatch ? decodeURIComponent(fileNameMatch[1].replace(/"/g, "")) : "download.csv";
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(downloadUrl);
    setMessage("");
  } catch (error) {
    setMessage(`\u05e9\u05d2\u05d9\u05d0\u05d4 \u05d1\u05d4\u05d5\u05e8\u05d3\u05ea \u05d4\u05d3\u05d5\"\u05d7: ${error.message}`, true);
  }
}

function exportReport() {
  if (exportFormat.value === "csv") {
    downloadCsv();
    return;
  }

  if (exportFormat.value === "pdf") {
    downloadPdf();
    return;
  }

  setMessage("\u05d1\u05d7\u05e8 \u05e4\u05d5\u05e8\u05de\u05d8 CSV \u05d0\u05d5 PDF.", true);
}

function exportRecordingsDetail() {
  const month = monthFilter.value || currentMonthValue();
  monthFilter.value = month;
  const params = new URLSearchParams({ month });
  downloadFileFromEndpoint(
    `/features-report-recordings-detail?${params.toString()}`,
    "שגיאה בהורדת דוח פירוט ההקלטות"
  );
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

