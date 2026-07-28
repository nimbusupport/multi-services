const form = document.getElementById("feature-status-form");
const input = document.getElementById("customer-id-input");
const button = document.getElementById("lookup-submit-btn");
const message = document.getElementById("lookup-message");
const summary = document.getElementById("feature-status-summary");
const results = document.getElementById("feature-status-results");

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

function normalizeCustomerId(value) {
  const digitsOnly = String(value || "").replace(/\D/g, "");
  if (!digitsOnly) return "";
  return digitsOnly.replace(/^0+/, "") || digitsOnly;
}

function renderLoadingState() {
  summary.classList.add("hidden");
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

function renderSummary(payload) {
  const names = Array.isArray(payload.business_names) ? payload.business_names : [];
  summary.innerHTML = `
    <div class="summary-head">
      <div>
        <h2>תוצאות עבור לקוח</h2>
        <div class="summary-id">ח.פ: ${escapeHtml(payload.customer_id || "")}</div>
      </div>
    </div>
    <div class="summary-names">
      ${names.length
        ? names.map((name) => `<span class="summary-chip">${escapeHtml(name)}</span>`).join("")
        : '<span class="summary-chip">לא נמצא שם עסק תואם</span>'}
    </div>
    <div class="summary-stats">
      <span class="summary-stat">נמצאו ${escapeHtml(payload.found_count ?? 0)} שירותים</span>
      <span class="summary-stat">לא נמצאו ${escapeHtml(payload.missing_count ?? 0)} שירותים</span>
    </div>
  `;
  summary.classList.remove("hidden");
}

function renderServiceEntry(entry) {
  return `
    <div class="service-entry">
      <div class="entry-name">${escapeHtml(entry.business_name || "ללא שם עסק")}</div>
      <div class="entry-meta">
        <span>סטטוס: <strong>${escapeHtml(entry.status || "לא הוגדר")}</strong></span>
        <span>שורה: ${escapeHtml(entry.row || "")}</span>
        <span>ח.פ: ${escapeHtml(entry.customer_id || "")}</span>
      </div>
    </div>
  `;
}

function renderServiceEntry(entry) {
  return `
    <div class="service-entry">
      <div class="entry-name">סטטוס: <strong>${escapeHtml(entry.status || "לא הוגדר")}</strong></div>
    </div>
  `;
}

function renderResults(services) {
  results.innerHTML = services.map((service) => {
    const entries = Array.isArray(service.entries) ? service.entries : [];
    const statusValue = entries[0]?.status || "";
    return `
      <article class="service-status-card ${service.found ? "found" : "missing"}">
        <h3>${escapeHtml(service.label || "")}</h3>
        ${service.found ? `
          <div class="status-chip-row">
            <span class="status-chip ${normalizeStatusClass(statusValue)}">${escapeHtml(statusValue)}</span>
          </div>
          <div class="service-entry-list">
            ${entries.map(renderServiceEntry).join("")}
          </div>
        ` : `
          <p class="service-empty">לא נמצא פיצ'ר תואם בגיליון הזה.</p>
        `}
      </article>
    `;
  }).join("");
}

async function loadFeatureStatuses(customerId) {
  const normalizedCustomerId = normalizeCustomerId(customerId);
  button.disabled = true;
  message.classList.remove("error");
  message.textContent = "אוסף נתונים מכל הגיליונות, נא להמתין...";
  renderLoadingState();

  try {
    const params = new URLSearchParams({ customer_id: normalizedCustomerId });
    const res = await fetch(`/features-status-data?${params.toString()}`);
    const data = await res.json().catch(() => ({}));

    if (!res.ok || !data.ok) {
      throw new Error(data.message || "אירעה שגיאה בזמן שליפת הנתונים");
    }

    renderSummary(data);
    renderResults(Array.isArray(data.services) ? data.services : []);
    message.textContent = "הנתונים עודכנו בהצלחה.";
  } catch (err) {
    summary.classList.add("hidden");
    results.innerHTML = "";
    message.classList.add("error");
    message.textContent = err.message || "אירעה שגיאה בזמן שליפת הנתונים";
  } finally {
    button.disabled = false;
  }
}

form?.addEventListener("submit", async (event) => {
  event.preventDefault();
  const customerId = input?.value.trim() || "";
  const normalizedCustomerId = normalizeCustomerId(customerId);
  if (!normalizedCustomerId) {
    message.classList.add("error");
    message.textContent = "יש להזין מספר ח.פ של העסק";
    input?.focus();
    return;
  }
  if (input) {
    input.value = normalizedCustomerId;
  }
  await loadFeatureStatuses(normalizedCustomerId);
});
