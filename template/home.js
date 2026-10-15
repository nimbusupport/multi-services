
function setPageLoadingOverlay(isLoading, message = "טוען נתונים...") {
  const overlay = document.getElementById("page-loading-overlay");
  const messageHost = document.getElementById("page-loading-text");
  if (!overlay) return;
  overlay.hidden = !isLoading;
  document.body.classList.toggle("is-page-loading", Boolean(isLoading));
  if (messageHost) {
    messageHost.textContent = message;
  }
}

function navigateWithPageLoader(href, message = "טוען נתונים...") {
  if (!href) return;
  setPageLoadingOverlay(true, message);
  window.setTimeout(() => {
    window.location.href = href;
  }, 24);
}

function bindDashboardTicketCardLoading() {
  document.querySelectorAll("[data-loading-link='true']").forEach((link) => {
    link.addEventListener("click", (event) => {
      if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) {
        return;
      }
      event.preventDefault();
      navigateWithPageLoader(link.href);
    });
  });

  document.querySelectorAll("[data-loading-href]").forEach((card) => {
    const href = card.dataset.loadingHref || "";
    if (!href) return;
    card.addEventListener("click", (event) => {
      if (event.target.closest("a, button, input, select, textarea")) {
        return;
      }
      navigateWithPageLoader(href);
    });
    card.addEventListener("keydown", (event) => {
      if (event.key !== "Enter" && event.key !== " ") {
        return;
      }
      event.preventDefault();
      navigateWithPageLoader(href);
    });
  });

  window.addEventListener("pageshow", () => {
    setPageLoadingOverlay(false);
  });
}

function displayUserName(user) {
  const local = String(user || "").split("@")[0].toLowerCase();
  if (local === "nir") return "ניר";
  if (["eugeni", "yevgeni", "evgeni"].includes(local)) return "יבגני";
  if (local === "golan") return "גולן";
  if (["asaf", "assafh"].includes(local)) return "אסף";
  if (["itsik", "itzik", "isaac"].includes(local)) return "איציק";
  if (local === "zohar" || local === "zora") return "זורה";
  if (["nastia", "nastya", "nastiya"].includes(local)) return "נסטיה";
  if (local === "admin") return "Admin";
  return String(user || "").split("@")[0];
}

function renderUsers(serviceKey, users) {
  const host = document.getElementById(`${serviceKey}-users`);
  if (!host) return;
  if (!Array.isArray(users) || users.length === 0) {
    host.innerHTML = '<span class="active-user-empty">No active users</span>';
    return;
  }
  host.innerHTML = users
    .map((u) => `<span class="active-user-chip">${displayUserName(u)}</span>`)
    .join("");
}

function renderWaiting(serviceKey, waiting) {
  const unavailable = waiting === null || waiting === undefined;
  const value = unavailable ? 0 : (Number(waiting) || 0);
  const countEl = document.getElementById(`${serviceKey}-waiting-count`);
  const barEl = document.getElementById(`${serviceKey}-waiting-bar`);
  if (countEl) countEl.textContent = unavailable ? "!" : String(value);
  if (barEl) {
    const width = Math.min(100, value * 5);
    barEl.style.width = `${width}%`;
    barEl.title = unavailable ? "Service unavailable" : "";
  }
}

function renderSummaryWaiting(serviceKey, total, maxScale = 40) {
  const countEl = document.getElementById(`${serviceKey}-waiting-count`);
  const barEl = document.getElementById(`${serviceKey}-waiting-bar`);
  if (countEl) countEl.textContent = String(total);
  if (barEl) {
    const width = Math.min(100, maxScale <= 0 ? 100 : (total / maxScale) * 100);
    barEl.style.width = `${width}%`;
  }
}

function waitingValue(entry) {
  const value = entry?.waiting;
  return value === null || value === undefined ? 0 : (Number(value) || 0);
}

async function loadDashboardData() {
  try {
    const res = await fetch("/dashboard-data");
    if (!res.ok) return;
    const data = await res.json();
    renderWaiting("sms", data?.sms?.waiting);
    renderUsers("sms", data?.sms?.active_users);
    renderWaiting("bot", data?.bot?.waiting);
    renderUsers("bot", data?.bot?.active_users);
    renderWaiting("f2m", data?.f2m?.waiting);
    renderUsers("f2m", data?.f2m?.active_users);
    renderWaiting("recordings", data?.recordings?.waiting);
    renderUsers("recordings", data?.recordings?.active_users);
    renderWaiting("recording_storage", data?.recording_storage?.waiting);
    renderUsers("recording_storage", data?.recording_storage?.active_users);
    renderWaiting("human_service", data?.human_service?.waiting);
    renderUsers("human_service", data?.human_service?.active_users);
    renderWaiting("support_tickets", data?.support_tickets?.waiting);
    renderUsers("support_tickets", data?.support_tickets?.active_users);
    renderWaiting("pais_tickets", data?.pais_tickets?.waiting);
    renderUsers("pais_tickets", data?.pais_tickets?.active_users);
    renderWaiting("hot_tickets", data?.hot_tickets?.waiting);
    renderUsers("hot_tickets", data?.hot_tickets?.active_users);
    renderWaiting("nastia_tickets", data?.nastia_tickets?.waiting);
    renderUsers("nastia_tickets", data?.nastia_tickets?.active_users);

    const servicesTotal =
      waitingValue(data?.sms) +
      waitingValue(data?.bot) +
      waitingValue(data?.f2m) +
      waitingValue(data?.recordings) +
      waitingValue(data?.recording_storage) +
      waitingValue(data?.human_service);
    renderSummaryWaiting("dashboard-services", servicesTotal);

    const ticketsTotal =
      waitingValue(data?.support_tickets) +
      waitingValue(data?.pais_tickets) +
      waitingValue(data?.hot_tickets);
    renderSummaryWaiting("dashboard-service-tickets", ticketsTotal);
  } catch (err) {
    console.error("dashboard data error", err);
  }
}

document.addEventListener("DOMContentLoaded", () => {
  bindDashboardTicketCardLoading();
  loadDashboardData();
  setInterval(loadDashboardData, 20000);
});
