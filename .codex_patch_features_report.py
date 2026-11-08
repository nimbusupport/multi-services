from pathlib import Path

root = Path(r"C:\sms_imported")

# app.py
app_path = root / "app.py"
app_text = app_path.read_text(encoding="utf-8")
helpers_anchor = "    return totals\n\n\ndef get_feature_report_counts(month_value, use_cache=True, allow_stale_on_error=True):"
helpers_insert = '''    return totals\n\n\ndef get_feature_report_detail_headers():\n    return ["לקוח", "מס פרויקט הוט", "מס הזמנה נימבוס"]\n\n\ndef build_feature_report_detail_entry(customer_name="", hot_project_id="", nimbus_order_id=""):\n    return {\n        "customer_name": str(customer_name or "").strip(),\n        "hot_project_id": str(hot_project_id or "").strip(),\n        "nimbus_order_id": str(nimbus_order_id or "").strip(),\n    }\n\n\ndef build_feature_report_detail_entry_from_row(row):\n    return build_feature_report_detail_entry(\n        customer_name=row[0].strip() if len(row) >= 1 else "",\n        hot_project_id=row[3].strip() if len(row) >= 4 else "",\n        nimbus_order_id=row[4].strip() if len(row) >= 5 else "",\n    )\n\n\ndef sort_feature_report_detail_entries(entries):\n    return sorted(\n        entries,\n        key=lambda item: (\n            str(item.get("customer_name") or "").strip(),\n            str(item.get("hot_project_id") or "").strip(),\n            str(item.get("nimbus_order_id") or "").strip(),\n        ),\n    )\n\n\ndef get_matching_feature_report_sheet_rows(selected_month, config, spreadsheet):\n    ws = spreadsheet.worksheet(config["sheet"])\n    rows = ws.get_all_values()[1:]\n    matched_rows = []\n\n    for row in rows:\n        status_col = config["status_col"]\n        date_col = config["date_col"]\n        status = row[status_col - 1].strip() if len(row) >= status_col else ""\n        date_value = row[date_col - 1].strip() if len(row) >= date_col else ""\n\n        if config.get("checkbox"):\n            is_done = report_checkbox_marked(status)\n        else:\n            is_done = status == config["status_value"]\n\n        if not is_done:\n            continue\n\n        done_date = parse_report_date(date_value, config.get("date_order", "mdy"))\n        if not done_date:\n            continue\n\n        if done_date.year == selected_month.year and done_date.month == selected_month.month:\n            matched_rows.append(row)\n\n    return matched_rows\n\n\ndef build_sms_feature_report_detail_entries(selected_month, spreadsheet):\n    ws = spreadsheet.worksheet(SHEET_NAME)\n    rows = ws.get_all_values()[1:]\n    entries = []\n\n    for row in rows:\n        status = row[COL_STATUS - 1].strip() if len(row) >= COL_STATUS else ""\n        date_value = row[6].strip() if len(row) >= 7 else ""\n\n        if status != STATUS_DONE:\n            continue\n\n        done_date = parse_report_date(date_value, "dmy")\n        if not done_date:\n            continue\n\n        if done_date.year == selected_month.year and done_date.month == selected_month.month:\n            entry = build_feature_report_detail_entry_from_row(row)\n            if any(entry.values()):\n                entries.append(entry)\n\n    return entries\n'''
if helpers_anchor not in app_text:
    raise SystemExit("helpers anchor not found")
app_text = app_text.replace(helpers_anchor, helpers_insert + "\n\n\ndef build_recordings_feature_report_detail_entries(selected_month, spreadsheet, config, child_key=\"\"):\n    recordings = get_done_recordings_for_month(selected_month, spreadsheet, config)\n    if child_key == \"recordings_with_music\":\n        recordings = [item for item in recordings if item.get(\"music_type\") == \"with_music\"]\n    elif child_key == \"recordings_without_music\":\n        recordings = [item for item in recordings if item.get(\"music_type\") == \"without_music\"]\n    elif child_key:\n        raise ValueError(\"Invalid child feature\")\n\n    order_details = {}\n    ws = spreadsheet.worksheet(config[\"category_sheet\"])\n    rows = ws.get_all_values()[1:]\n    order_col = config[\"order_col\"]\n\n    for row in rows:\n        order_id = normalize_recording_order_id(row[order_col - 1] if len(row) >= order_col else \"\")\n        if not order_id or order_id in order_details:\n            continue\n        order_details[order_id] = build_feature_report_detail_entry_from_row(row)\n\n    entries = []\n    for recording in recordings:\n        order_id = normalize_recording_order_id(recording.get(\"order_id\") or \"\")\n        detail = order_details.get(order_id, {})\n        entry = build_feature_report_detail_entry(\n            customer_name=detail.get(\"customer_name\") or recording.get(\"business_name\") or \"\",\n            hot_project_id=detail.get(\"hot_project_id\") or \"\",\n            nimbus_order_id=detail.get(\"nimbus_order_id\") or order_id,\n        )\n        if any(entry.values()):\n            entries.append(entry)\n\n    return entries\n\n\ndef get_feature_report_detail(month_value, service_key, child_key=\"\"):\n    selected_month = datetime.strptime(month_value, \"%Y-%m\")\n    normalized_service_key = str(service_key or \"\").strip().lower()\n    normalized_child_key = str(child_key or \"\").strip().lower()\n    config = FEATURE_REPORT_SERVICES.get(normalized_service_key)\n    if not config:\n        raise ValueError(\"Invalid service\")\n\n    client = get_gspread_client()\n    spreadsheet = client.open_by_key(SPREADSHEET_ID)\n\n    detail_label = config[\"label\"]\n    if normalized_service_key == \"recordings\":\n        entries = build_recordings_feature_report_detail_entries(selected_month, spreadsheet, config, normalized_child_key)\n        if normalized_child_key == \"recordings_with_music\":\n            detail_label = f\"{config['label']} - {RECORDING_WITH_MUSIC}\"\n        elif normalized_child_key == \"recordings_without_music\":\n            detail_label = f\"{config['label']} - {RECORDING_WITHOUT_MUSIC}\"\n    elif normalized_service_key == \"sms\":\n        entries = build_sms_feature_report_detail_entries(selected_month, spreadsheet)\n    else:\n        matched_rows = get_matching_feature_report_sheet_rows(selected_month, config, spreadsheet)\n        entries = []\n        for row in matched_rows:\n            entry = build_feature_report_detail_entry_from_row(row)\n            if any(entry.values()):\n                entries.append(entry)\n\n    entries = sort_feature_report_detail_entries(entries)\n    payload = normalize_legacy_hebrew_data({\n        \"month\": month_value,\n        \"month_display\": selected_month.strftime(\"%m/%Y\"),\n        \"service_key\": normalized_service_key,\n        \"child_key\": normalized_child_key,\n        \"label\": detail_label,\n        \"headers\": get_feature_report_detail_headers(),\n        \"entries\": entries,\n        \"total\": len(entries),\n    })\n    return payload\n\n\ndef build_feature_report_detail_export_rows(detail_payload):\n    rows = []\n    for entry in detail_payload.get(\"entries\", []):\n        rows.append([\n            entry.get(\"customer_name\") or \"\",\n            entry.get(\"hot_project_id\") or \"\",\n            entry.get(\"nimbus_order_id\") or \"\",\n        ])\n    return rows\n\n\ndef get_feature_report_counts(month_value, use_cache=True, allow_stale_on_error=True):", 1)

route_anchor = '    return jsonify({"ok": True, **totals})\n\n\n@app.route("/features-report-recordings-detail")'
route_insert = '''    return jsonify({"ok": True, **totals})\n\n\n@app.route("/features-report-service-detail")\ndef features_report_service_detail():\n\n    if not session.get("logged_in"):\n        return redirect(url_for("login"))\n\n    month_value = request.args.get("month", datetime.now().strftime("%Y-%m"))\n    service_key = request.args.get("service", "")\n    child_key = request.args.get("child", "")\n\n    try:\n        detail = get_feature_report_detail(month_value, service_key, child_key)\n    except ValueError as exc:\n        return jsonify({"ok": False, "error": str(exc)}), 400\n    except Exception as exc:\n        return jsonify({"ok": False, "error": str(exc)}), 500\n\n    return jsonify({"ok": True, "detail": detail})\n\n\n@app.route("/features-report-service-detail-export")\ndef features_report_service_detail_export():\n\n    if not session.get("logged_in"):\n        return redirect(url_for("login"))\n\n    month_value = request.args.get("month", datetime.now().strftime("%Y-%m"))\n    service_key = request.args.get("service", "")\n    child_key = request.args.get("child", "")\n    export_format = (request.args.get("format") or "csv").strip().lower()\n\n    try:\n        detail = get_feature_report_detail(month_value, service_key, child_key)\n    except ValueError as exc:\n        return jsonify({"ok": False, "error": str(exc)}), 400\n    except Exception as exc:\n        return jsonify({"ok": False, "error": str(exc)}), 500\n\n    rows = build_feature_report_detail_export_rows(detail)\n    headers = detail.get("headers") or get_feature_report_detail_headers()\n    file_suffix = f"-{detail['child_key']}" if detail.get("child_key") else ""\n\n    if export_format == "pdf":\n        pdf_rows = rows or [["-", "-", "-"]]\n        pdf_buffer = build_pdf_buffer(\n            title=f"דו\\"ח לקוחות לפיצ'ר {detail.get('label') or ''}",\n            metadata_rows=[\n                ("חודש", detail.get("month_display") or ""),\n                ("שירות", detail.get("label") or ""),\n                ("לקוחות", detail.get("total") or 0),\n            ],\n            headers=headers,\n            rows=pdf_rows,\n            rtl_columns={0, 1, 2},\n            emphasis_columns={2},\n            emphasis_meta_labels={"חודש", "שירות", "לקוחות"},\n        )\n        return send_file(\n            pdf_buffer,\n            mimetype="application/pdf",\n            as_attachment=True,\n            download_name=f"features-report-detail-{detail['service_key']}{file_suffix}-{detail['month']}.pdf",\n        )\n\n    output = io.StringIO()\n    writer = csv.writer(output)\n    writer.writerow(headers)\n    writer.writerows(rows)\n    csv_buffer = io.BytesIO(("\\ufeff" + output.getvalue()).encode("utf-8"))\n    csv_buffer.seek(0)\n    return send_file(\n        csv_buffer,\n        mimetype="text/csv",\n        as_attachment=True,\n        download_name=f"features-report-detail-{detail['service_key']}{file_suffix}-{detail['month']}.csv",\n    )\n\n\n@app.route("/features-report-recordings-detail")'''
if route_anchor not in app_text:
    raise SystemExit("route anchor not found")
app_text = app_text.replace(route_anchor, route_insert, 1)
app_path.write_text(app_text, encoding="utf-8")
# HTML
html_path = root / "template" / "features_report.html"
html_text = html_path.read_text(encoding="utf-8")
html_anchor = '''    <section class="surface trend-surface" aria-labelledby="trend-title">\n      <div class="section-head">\n        <div>\n          <p class="section-kicker">השוואת חודשים</p>\n          <h2 id="trend-title">מגמת פיצ'רים שבוצעו</h2>\n        </div>\n        <div class="section-chip soft">\n          <span id="trend-peak">-</span>\n          <small>חודש שיא</small>\n        </div>\n      </div>\n      <div id="trend-chart" class="trend-chart" aria-live="polite"></div>\n      <p id="trend-message" class="inline-message trend-message"></p>\n    </section>\n  </main>'''
html_replace = '''    <section class="surface trend-surface" aria-labelledby="trend-title">\n      <div class="section-head">\n        <div>\n          <p class="section-kicker">השוואת חודשים</p>\n          <h2 id="trend-title">מגמת פיצ'רים שבוצעו</h2>\n        </div>\n        <div class="section-chip soft">\n          <span id="trend-peak">-</span>\n          <small>חודש שיא</small>\n        </div>\n      </div>\n      <div id="trend-chart" class="trend-chart" aria-live="polite"></div>\n      <p id="trend-message" class="inline-message trend-message"></p>\n    </section>\n\n    <section id="feature-detail-surface" class="surface feature-detail-surface" aria-labelledby="feature-detail-title" hidden>\n      <div id="feature-detail-loading" class="report-loading" aria-live="polite" hidden>\n        <div class="report-loading-spinner" aria-hidden="true"></div>\n        <span id="feature-detail-loading-text">טוען לקוחות...</span>\n      </div>\n\n      <div class="section-head feature-detail-head">\n        <div>\n          <p class="section-kicker">לקוחות לפי שירות</p>\n          <h2 id="feature-detail-title">בחרו שירות מהטבלה</h2>\n        </div>\n        <div class="detail-toolbar">\n          <div class="section-chip accent">\n            <span id="feature-detail-total-chip">0</span>\n            <small>לקוחות בדוח</small>\n          </div>\n          <div class="toolbar-actions feature-detail-actions">\n            <button id="feature-detail-export-csv" class="toolbar-btn secondary" type="button" disabled>\n              <i class="fa-solid fa-file-csv"></i>\n              <span>CSV</span>\n            </button>\n            <button id="feature-detail-export-pdf" class="toolbar-btn export" type="button" disabled>\n              <i class="fa-solid fa-file-pdf"></i>\n              <span>PDF</span>\n            </button>\n          </div>\n        </div>\n      </div>\n\n      <p id="feature-detail-subtitle" class="feature-detail-subtitle">לחצו על אחד השירותים בדוח כדי לראות את הלקוחות שבוצעו באותו חודש.</p>\n      <div class="feature-detail-table-wrap">\n        <table class="report-table feature-detail-table">\n          <thead>\n            <tr>\n              <th>לקוח</th>\n              <th>מס פרויקט הוט</th>\n              <th>מס הזמנה נימבוס</th>\n            </tr>\n          </thead>\n          <tbody id="feature-detail-body"></tbody>\n        </table>\n      </div>\n      <p id="feature-detail-message" class="inline-message"></p>\n    </section>\n  </main>'''
if html_anchor not in html_text:
    raise SystemExit("html anchor not found")
html_text = html_text.replace(html_anchor, html_replace, 1)
html_path.write_text(html_text, encoding="utf-8")
# JS
js_path = root / "template" / "features_report.js"
js_text = """const monthFilter = document.getElementById(\"month-filter\");
const loadButton = document.getElementById(\"load-report\");
const detailExportButton = document.getElementById(\"recordings-detail-export\");
const exportButton = document.getElementById(\"export-btn\");
const exportFormat = document.getElementById(\"export-format\");
const reportBody = document.getElementById(\"report-body\");
const reportTotal = document.getElementById(\"report-total\");
const reportMonthLabel = document.getElementById(\"report-month-label\");
const reportMessage = document.getElementById(\"report-message\");
const printArea = document.getElementById(\"print-area\");
const reportLoading = document.getElementById(\"report-loading\");
const reportLoadingText = document.getElementById(\"report-loading-text\");
const trendChart = document.getElementById(\"trend-chart\");
const trendRange = document.getElementById(\"trend-range\");
const trendMessage = document.getElementById(\"trend-message\");
const reportServicesCount = document.getElementById(\"report-services-count\");
const reportChildrenCount = document.getElementById(\"report-children-count\");
const reportTopServiceCount = document.getElementById(\"report-top-service-count\");
const reportTopServiceLabel = document.getElementById(\"report-top-service-label\");
const reportSummaryTotalChip = document.getElementById(\"report-summary-total-chip\");
const insightMonth = document.getElementById(\"insight-month\");
const insightTopService = document.getElementById(\"insight-top-service\");
const insightAverage = document.getElementById(\"insight-average\");
const trendPeak = document.getElementById(\"trend-peak\");
const featureDetailSurface = document.getElementById(\"feature-detail-surface\");
const featureDetailTitle = document.getElementById(\"feature-detail-title\");
const featureDetailSubtitle = document.getElementById(\"feature-detail-subtitle\");
const featureDetailBody = document.getElementById(\"feature-detail-body\");
const featureDetailMessage = document.getElementById(\"feature-detail-message\");
const featureDetailLoading = document.getElementById(\"feature-detail-loading\");
const featureDetailLoadingText = document.getElementById(\"feature-detail-loading-text\");
const featureDetailTotalChip = document.getElementById(\"feature-detail-total-chip\");
const featureDetailExportCsvButton = document.getElementById(\"feature-detail-export-csv\");
const featureDetailExportPdfButton = document.getElementById(\"feature-detail-export-pdf\");

let currentReport = null;
let currentDetail = null;

function isQuotaExceededMessage(message) {
  const text = String(message || \"\").toLowerCase();
  return text.includes(\"quota exceeded\") || (text.includes(\"429\") && text.includes(\"sheets.googleapis.com\"));
}

function looksLikeBrokenHebrew(value) {
  const text = String(value || \"\");
  return /[\x80-\x9f]/.test(text) || (text.match(//g) || []).length >= 2;
}

function repairBrokenHebrew(value) {
  const text = String(value || \"\");
  if (!looksLikeBrokenHebrew(text)) {
    return text;
  }
  const chars = [];
  for (const ch of text) {
    const code = ch.charCodeAt(0);
    chars.push(code <= 0xFF ? String.fromCharCode(code) : ch);
  }
  try {
    return decodeURIComponent(escape(chars.join(\"\")));
  } catch {
    return text;
  }
}

function normalizeLegacyHebrewData(value) {
  if (Array.isArray(value)) {
    return value.map(normalizeLegacyHebrewData);
  }
  if (value && typeof value === \"object\") {
    return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, normalizeLegacyHebrewData(item)]));
  }
  if (typeof value === \"string\") {
    return repairBrokenHebrew(value);
  }
  return value;
}

function currentMonthValue() {
  const now = new Date();
  const month = String(now.getMonth() + 1).padStart(2, \"0\");
  return `${now.getFullYear()}-${month}`;
}

function setMessage(text, isError = false) {
  reportMessage.textContent = text;
  reportMessage.classList.toggle(\"error\", isError);
}

function setTrendMessage(text, isError = false) {
  trendMessage.textContent = text;
  trendMessage.classList.toggle(\"error\", isError);
}

function setFeatureDetailMessage(text, isError = false) {
  featureDetailMessage.textContent = text;
  featureDetailMessage.classList.toggle(\"error\", isError);
}

function setReportLoading(isLoading, text = \"טוען דוח...\") {
  reportLoading.hidden = !isLoading;
  reportLoadingText.textContent = text;
  printArea.classList.toggle(\"is-loading\", isLoading);
  loadButton.disabled = isLoading;
  monthFilter.disabled = isLoading;
  trendChart.querySelectorAll(\".trend-bar-card\").forEach((card) => {
    card.disabled = isLoading;
  });
}

function setFeatureDetailLoading(isLoading, text = \"טוען לקוחות...\") {
  featureDetailLoading.hidden = !isLoading;
  featureDetailLoadingText.textContent = text;
  featureDetailSurface.classList.toggle(\"is-loading\", isLoading);
  featureDetailExportCsvButton.disabled = isLoading || !currentDetail;
  featureDetailExportPdfButton.disabled = isLoading || !currentDetail;
}

function resetFeatureDetail(hideSurface = true) {
  currentDetail = null;
  featureDetailTitle.textContent = \"בחרו שירות מהטבלה\";
  featureDetailSubtitle.textContent = \"לחצו על אחד השירותים בדוח כדי לראות את הלקוחות שבוצעו באותו חודש.\";
  featureDetailBody.innerHTML = \"\";
  featureDetailTotalChip.textContent = \"0\";
  setFeatureDetailMessage(\"\");
  setFeatureDetailLoading(false);
  featureDetailExportCsvButton.disabled = true;
  featureDetailExportPdfButton.disabled = true;
  if (hideSurface) {
    featureDetailSurface.hidden = true;
  }
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
  resetFeatureDetail();
  reportMonthLabel.textContent = `חודש ${report.month_display}`;
  reportTotal.textContent = report.total;
  reportSummaryTotalChip.textContent = report.total;
  insightMonth.textContent = report.month_display || \"--/----\";
  const insights = reportInsights(report);
  reportServicesCount.textContent = insights.servicesCount;
  reportChildrenCount.textContent = Number(report.waiting_total || 0);
  reportTopServiceCount.textContent = insights.topService ? insights.topService.count : 0;
  reportTopServiceLabel.textContent = insights.topService ? insights.topService.label : \"-\";
  insightTopService.textContent = insights.topService ? insights.topService.label : \"-\";
  insightAverage.textContent = insights.average.toFixed(1).replace(\".0\", \"\");
  reportBody.innerHTML = report.services
    .map((service) => {
      const children = (service.children || [])
        .map((child) => `
          <tr class=\"sub-row\">
            <td>
              <button type=\"button\" class=\"feature-detail-trigger sub-service\" data-service-key=\"${service.key}\" data-child-key=\"${child.key || \"\"}\">
                <span class=\"service-dot sub-dot\"></span>
                <span>${child.label}</span>
              </button>
            </td>
            <td class=\"counter-cell sub-counter\">${child.count}</td>
          </tr>
        `)
        .join(\"\");

      return `
        <tr>
          <td>
            <button type=\"button\" class=\"feature-detail-trigger\" data-service-key=\"${service.key}\">
              <span class=\"service-dot\"></span>
              <span>${service.label}</span>
            </button>
          </td>
          <td class=\"counter-cell\">${service.count}</td>
        </tr>
        ${children}
      `;
    })
    .join(\"\");
}

function renderTrendChart(months, startMonth, endMonth) {
  if (!months.length) {
    trendChart.innerHTML = \"\";
    trendRange.textContent = \"--/---- - --/----\";
    trendPeak.textContent = \"-\";
    setTrendMessage(\"אין נתונים חודשיים להצגה.\", true);
    return;
  }

  const maxTotal = Math.max(...months.map((item) => item.total), 1);
  const peakMonth = months.reduce((best, item) => (item.total > best.total ? item : best), months[0]);
  trendRange.textContent = `${startMonth} - ${endMonth}`;
  trendPeak.textContent = `${peakMonth.month_display}  ${peakMonth.total}`;
  trendChart.innerHTML = months
    .map((item) => {
      const height = Math.max((item.total / maxTotal) * 100, item.total > 0 ? 8 : 0);
      const isActive = monthFilter.value === item.month;
      return `
        <button
          type=\"button\"
          class=\"trend-bar-card${isActive ? \" active\" : \"\"}\"
          data-month=\"${item.month}\"
          aria-label=\"טען דוח עבור ${item.month_display}\"
        >
          <strong class=\"trend-value\">${item.total}</strong>
          <div class=\"trend-bar-track\">
            <div class=\"trend-bar-fill\" style=\"height: ${height}%\"></div>
          </div>
          <span class=\"trend-label\">${item.month_display}</span>
        </button>
      `;
    })
    .join(\"\");
  setTrendMessage(\"\");
}
function renderFeatureDetail(detail) {
  currentDetail = detail;
  featureDetailSurface.hidden = false;
  featureDetailTitle.textContent = `לקוחות עבור ${detail.label}`;
  featureDetailSubtitle.textContent = `חודש ${detail.month_display}  ${detail.total} לקוחות`;
  featureDetailTotalChip.textContent = detail.total;
  featureDetailBody.innerHTML = (detail.entries || []).length
    ? detail.entries
        .map((entry) => `
          <tr>
            <td>${entry.customer_name || "-"}</td>
            <td>${entry.hot_project_id || "-"}</td>
            <td>${entry.nimbus_order_id || "-"}</td>
          </tr>
        `)
        .join("")
    : `
      <tr class="feature-empty-row">
        <td colspan="3">לא נמצאו לקוחות להצגה עבור השירות בחודש שנבחר.</td>
      </tr>
    `;
  featureDetailExportCsvButton.disabled = false;
  featureDetailExportPdfButton.disabled = false;
  setFeatureDetailMessage("");
  featureDetailSurface.scrollIntoView({ behavior: "smooth", block: "start" });
}

async function loadReport(loadingText = "טוען דוח...") {
  const month = monthFilter.value || currentMonthValue();
  monthFilter.value = month;
  setMessage("טוען נתונים...");
  resetFeatureDetail();
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
    setMessage(`שגיאה בטעינת הדוח: ${error.message}`, true);
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

async function loadFeatureDetail(serviceKey, childKey = "") {
  if (!currentReport) {
    setFeatureDetailMessage("אין נתוני דוח זמינים. טענו דוח תחילה.", true);
    return;
  }

  const month = currentReport.month || monthFilter.value || currentMonthValue();
  featureDetailSurface.hidden = false;
  setFeatureDetailMessage("");
  setFeatureDetailLoading(true, "טוען לקוחות...");

  try {
    const params = new URLSearchParams({
      month,
      service: serviceKey,
    });
    if (childKey) {
      params.set("child", childKey);
    }

    const res = await fetch(`/features-report-service-detail?${params.toString()}`);
    const data = normalizeLegacyHebrewData(await res.json());
    if (!res.ok || !data.ok) {
      throw new Error(data.error || "שגיאה בטעינת פירוט השירות");
    }

    renderFeatureDetail(data.detail);
  } catch (error) {
    currentDetail = null;
    featureDetailBody.innerHTML = "";
    featureDetailTotalChip.textContent = "0";
    featureDetailExportCsvButton.disabled = true;
    featureDetailExportPdfButton.disabled = true;
    setFeatureDetailMessage(`שגיאה בטעינת פירוט השירות: ${error.message}`, true);
  } finally {
    setFeatureDetailLoading(false);
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
    setMessage("אין נתונים לייצוא. לחץ הצג קודם.", true);
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
    .map((row) => row.map((value) => `"${String(value).replace(/"/g, "\\"\\"")}"`).join(","))
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
    setMessage("אין נתונים לייצוא. לחץ הצג קודם.", true);
    return;
  }

  const params = new URLSearchParams({
    month: currentReport.month,
    format: "pdf",
  });
  window.location.href = `/features-report-export?${params.toString()}`;
}

async function downloadFileFromEndpoint(url, fallbackErrorMessage, messageSetter = setMessage) {
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
    messageSetter("");
  } catch (error) {
    messageSetter(`שגיאה בהורדת הדוח: ${error.message}`, true);
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

  setMessage("בחר פורמט CSV או PDF.", true);
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

function exportFeatureDetail(format) {
  if (!currentDetail) {
    setFeatureDetailMessage("אין פירוט פתוח לייצוא.", true);
    return;
  }

  const params = new URLSearchParams({
    month: currentDetail.month,
    service: currentDetail.service_key,
    format,
  });
  if (currentDetail.child_key) {
    params.set("child", currentDetail.child_key);
  }

  downloadFileFromEndpoint(
    `/features-report-service-detail-export?${params.toString()}`,
    "שגיאה בהורדת פירוט השירות",
    setFeatureDetailMessage,
  );
}

monthFilter.value = currentMonthValue();
loadButton.addEventListener("click", loadReport);
monthFilter.addEventListener("change", loadReport);
exportButton.addEventListener("click", exportReport);
detailExportButton.addEventListener("click", exportRecordingsDetail);
featureDetailExportCsvButton.addEventListener("click", () => exportFeatureDetail("csv"));
featureDetailExportPdfButton.addEventListener("click", () => exportFeatureDetail("pdf"));
trendChart.addEventListener("click", async (event) => {
  const card = event.target.closest(".trend-bar-card");
  if (!card) {
    return;
  }
  await loadReportForMonth(card.dataset.month);
});
reportBody.addEventListener("click", async (event) => {
  const trigger = event.target.closest(".feature-detail-trigger");
  if (!trigger) {
    return;
  }
  await loadFeatureDetail(trigger.dataset.serviceKey || "", trigger.dataset.childKey || "");
});
loadReport();
loadMonthlyTotals();
"""
js_path.write_text(js_text, encoding="utf-8")

# CSS
css_path = root / "template" / "features_report.css"
css_text = css_path.read_text(encoding="utf-8")
css_anchor = ".trend-message {\n  margin-top: 10px;\n}\n\n.inline-message.error {\n  color: #ffd0cb;\n}\n"
css_replace = ".trend-message {\n  margin-top: 10px;\n}\n\n.feature-detail-surface {\n  position: relative;\n  margin-top: 20px;\n  padding: 22px;\n  overflow: hidden;\n}\n\n.feature-detail-surface.is-loading .feature-detail-table-wrap,\n.feature-detail-surface.is-loading .feature-detail-subtitle {\n  opacity: 0.3;\n}\n\n.feature-detail-head,\n.detail-toolbar,\n.feature-detail-actions {\n  display: flex;\n  align-items: center;\n  gap: 12px;\n}\n\n.detail-toolbar {\n  flex-wrap: wrap;\n  justify-content: flex-end;\n}\n\n.feature-detail-subtitle {\n  margin: 0 0 18px;\n  color: #bdd2eb;\n}\n\n.feature-detail-table-wrap {\n  overflow-x: auto;\n}\n\n.feature-detail-trigger {\n  display: inline-flex;\n  align-items: center;\n  gap: 10px;\n  width: 100%;\n  padding: 0;\n  border: 0;\n  background: transparent;\n  color: #143965;\n  font: inherit;\n  font-weight: 800;\n  text-align: right;\n  cursor: pointer;\n}\n\n.feature-detail-trigger:hover {\n  color: #0f5c66;\n}\n\n.feature-detail-trigger:focus-visible {\n  outline: 2px solid var(--features-cyan);\n  outline-offset: 4px;\n  border-radius: 8px;\n}\n\n.feature-empty-row td {\n  color: #46678f;\n  font-weight: 700;\n}\n\n.inline-message.error {\n  color: #ffd0cb;\n}\n"
if css_anchor not in css_text:
    raise SystemExit("css anchor not found")
css_text = css_text.replace(css_anchor, css_replace, 1)
css_path.write_text(css_text, encoding="utf-8")

# tests
test_path = root / "test_support_tickets.py"
test_text = test_path.read_text(encoding="utf-8")
test_anchor = '''    def test_features_report_data_uses_stale_cache_when_google_sheets_quota_is_exceeded(self):\n'''
test_insert = '''    def test_features_report_service_detail_returns_bot_customers(self):\n        class FakeWorksheet:\n            def __init__(self, rows):\n                self.rows = rows\n\n            def get_all_values(self):\n                return self.rows\n\n        class FakeSpreadsheet:\n            def worksheet(self, name):\n                if name != self.expected_name:\n                    raise AssertionError(f"unexpected worksheet {name}")\n                return FakeWorksheet([\n                    ["לקוח", "B", "C", "מס פרויקט הוט", "מס הזמנה נימבוס", "F", "G", "H", "I", "J", "K", "L", "M", "N", "O", "P", "Q"],\n                    ["אלפא", "", "", "HOT-100", "NIM-500", "", "", "בוצע", "", "", "", "", "", "", "", "", "07/15/2026"],\n                    ["בטא", "", "", "HOT-101", "NIM-501", "", "", "ממתין", "", "", "", "", "", "", "", "", "07/20/2026"],\n                ])\n\n            expected_name = "שירות מענה - בוט"\n\n        class WorkingClient:\n            def open_by_key(self, key):\n                return FakeSpreadsheet()\n\n        self.app_module.get_gspread_client = lambda: WorkingClient()\n\n        self.login("admin@nimbusip.com")\n        response = self.client.get("/features-report-service-detail?month=2026-07&service=bot")\n\n        self.assertEqual(response.status_code, 200)\n        payload = response.get_json()\n        self.assertTrue(payload["ok"])\n        self.assertEqual(payload["detail"]["label"], "BOT")\n        self.assertEqual(payload["detail"]["total"], 1)\n        self.assertEqual(payload["detail"]["entries"][0]["customer_name"], "אלפא")\n        self.assertEqual(payload["detail"]["entries"][0]["hot_project_id"], "HOT-100")\n        self.assertEqual(payload["detail"]["entries"][0]["nimbus_order_id"], "NIM-500")\n\n    def test_features_report_service_detail_csv_export_downloads_attachment(self):\n        self.app_module.get_feature_report_detail = lambda month, service_key, child_key=\"\": {\n            \"month\": month,\n            \"month_display\": \"07/2026\",\n            \"service_key\": service_key,\n            \"child_key\": child_key,\n            \"label\": \"BOT\",\n            \"headers\": [\"לקוח\", \"מס פרויקט הוט\", \"מס הזמנה נימבוס\"],\n            \"entries\": [\n                {\n                    \"customer_name\": \"אלפא\",\n                    \"hot_project_id\": \"HOT-100\",\n                    \"nimbus_order_id\": \"NIM-500\",\n                }\n            ],\n            \"total\": 1,\n        }\n\n        self.login(\"admin@nimbusip.com\")\n        response = self.client.get(\"/features-report-service-detail-export?month=2026-07&service=bot&format=csv\")\n\n        self.assertEqual(response.status_code, 200)\n        self.assertEqual(response.mimetype, \"text/csv\")\n        self.assertIn(\"features-report-detail-bot-2026-07.csv\", response.headers[\"Content-Disposition\"])\n        self.assertIn(\"לקוח\".encode(\"utf-8\"), response.data)\n        self.assertIn(\"אלפא\".encode(\"utf-8\"), response.data)\n\n    def test_features_report_data_uses_stale_cache_when_google_sheets_quota_is_exceeded(self):\n'''
if test_anchor not in test_text:
    raise SystemExit("test anchor not found")
test_text = test_text.replace(test_anchor, test_insert, 1)
test_path.write_text(test_text, encoding="utf-8")

print("ok")

