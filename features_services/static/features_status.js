const form = document.getElementById("feature-status-form");
const input = document.getElementById("customer-id-input");
const button = document.getElementById("lookup-submit-btn");
const message = document.getElementById("lookup-message");
const summary = document.getElementById("feature-status-summary");
const results = document.getElementById("feature-status-results");
const featureStatusConfig = window.FEATURE_STATUS_CONFIG || {};

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

function buildApiUrl(customerId) {
  const baseUrl = String(featureStatusConfig.apiBaseUrl || "").trim();
  if (!baseUrl) {
    return "";
  }
  const separator = baseUrl.includes("?") ? "&" : "?";
  return `${baseUrl}${separator}${new URLSearchParams({ customer_id: customerId }).toString()}`;
}

function fetchJsonp(apiUrl) {
  return new Promise((resolve, reject) => {
    const callbackName = `featureStatusCallback_${Date.now()}_${Math.floor(Math.random() * 10000)}`;
    const separator = apiUrl.includes("?") ? "&" : "?";
    const script = document.createElement("script");
    const cleanup = () => {
      if (script.parentNode) {
        script.parentNode.removeChild(script);
      }
      try {
        delete window[callbackName];
      } catch (err) {
        window[callbackName] = undefined;
      }
    };

    const timeoutId = window.setTimeout(() => {
      cleanup();
      reject(new Error("Timeout while loading data"));
    }, 20000);

    window[callbackName] = (payload) => {
      window.clearTimeout(timeoutId);
      cleanup();
      resolve(payload || {});
    };

    script.onerror = () => {
      window.clearTimeout(timeoutId);
      cleanup();
      reject(new Error("Unable to load search service"));
    };
    script.src = `${apiUrl}${separator}callback=${encodeURIComponent(callbackName)}`;
    document.body.appendChild(script);
  });
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
  const apiUrl = buildApiUrl(normalizedCustomerId);
  if (!apiUrl) {
    message.classList.add("error");
    message.textContent = "שירות החיפוש אינו זמין כרגע.";
    return;
  }
  button.disabled = true;
  message.classList.remove("error");
  message.textContent = "אוסף נתונים מכל הגיליונות, נא להמתין...";
  renderLoadingState();

  try {
    let data = {};
    if (String(featureStatusConfig.apiMode || "").trim().toLowerCase() === "jsonp") {
      data = await fetchJsonp(apiUrl);
    } else {
      const res = await fetch(apiUrl);
      data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(data.message || "אירעה שגיאה בזמן שליפת הנתונים");
      }
    }

    if (!data.ok) {
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
  input.value = normalizedCustomerId;
  await loadFeatureStatuses(normalizedCustomerId);
});
