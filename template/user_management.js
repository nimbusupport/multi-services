const PAGE_GROUPS = [
  {
    title: "דשבורדים",
    pages: [
      { key: "home", label: "ראשי" },
      { key: "user_management", label: "משתמשים" },
    ],
  },
  {
    title: "שירותים",
    pages: [
      { key: "sms", label: "SMS" },
      { key: "bot", label: "בוט" },
      { key: "f2m", label: "F2M" },
      { key: "recording_storage", label: "אחסון" },
      { key: "human_service", label: "אנושי" },
      { key: "record", label: "פתיח" },
    ],
  },
  {
    title: "דוחות",
    pages: [
      { key: "tickets_monthly_report", label: "קריאות" },
      { key: "features_report", label: "פיצ׳רים" },
      { key: "features_status", label: "סטטוס" },
    ],
  },
  {
    title: "קריאות",
    pages: [
      { key: "support_tickets", label: "נימבוס" },
      { key: "pais_tickets", label: "הפיס" },
      { key: "hot_tickets", label: "HOT" },
      { key: "nastia_tickets", label: "נסטיה" },
    ],
  },
];

const PAGE_OPTIONS = PAGE_GROUPS.flatMap((group) => group.pages);
const TABLE_LABELS = {
  full_name: "שם",
  email: "אימייל",
  role: "תפקיד",
  pages: "עמודים",
  landing_page: "עמוד נחיתה",
  status: "סטטוס",
  actions: "פעולות",
};

const LANDING_OPTIONS = [
  { value: "/dashboard-services", label: "שירותי פיצ'רים מרכזי" },
  { value: "/dashboard-service-tickets", label: "קריאות שירות" },
  { value: "/dashboard-reports", label: "דוחות" },
];

const form = document.getElementById("user-invite-form");
const inviteMessageEl = document.getElementById("invite-message");
const usersMessageEl = document.getElementById("users-message");
const landingPageSelect = document.getElementById("invite-landing-page");
const pagesHost = document.getElementById("invite-pages");
const usersTableBody = document.getElementById("users-table-body");
const refreshUsersButton = document.getElementById("refresh-users");
const groupSelect = document.getElementById("invite-group-code");
let usersMessageTimer = null;

function setPanelMessage(element, text, kind = "") {
  if (!element) return;
  element.textContent = text;
  element.className = `form-message${element === usersMessageEl ? " panel-message" : ""}${kind ? ` ${kind}` : ""}`;
}

function setInviteMessage(text, kind = "") {
  setPanelMessage(inviteMessageEl, text, kind);
}

function setUsersMessage(text, kind = "") {
  setPanelMessage(usersMessageEl, text, kind);
  if (usersMessageTimer) {
    clearTimeout(usersMessageTimer);
    usersMessageTimer = null;
  }
  if (text && kind === "success") {
    usersMessageTimer = window.setTimeout(() => {
      setPanelMessage(usersMessageEl, "", "");
      usersMessageTimer = null;
    }, 5000);
  }
}

async function readJson(response) {
  const text = await response.text();
  if (!text) return {};
  try {
    return JSON.parse(text);
  } catch {
    throw new Error("Unexpected server response");
  }
}

function renderPageOptions() {
  pagesHost.innerHTML = PAGE_GROUPS.map((group) => `
    <section class="permission-group">
      <p class="permission-group-title">${group.title}</p>
      <div class="permission-group-grid">
        ${group.pages.map((page) => `
          <label class="page-option">
            <input type="checkbox" value="${page.key}" ${page.key === "home" ? "checked" : ""}>
            <span>${page.label}</span>
          </label>
        `).join("")}
      </div>
    </section>
  `).join("");

  landingPageSelect.innerHTML = LANDING_OPTIONS.map((page) => `
    <option value="${page.value}">${page.label}</option>
  `).join("");
}

function checkedPages() {
  return Array.from(pagesHost.querySelectorAll('input[type="checkbox"]:checked')).map((checkbox) => checkbox.value);
}

function renderGroups(groups) {
  const options = ['<option value="">ללא</option>'];
  (groups || []).forEach((group) => {
    options.push(`<option value="${group.code}">${group.name || group.code}</option>`);
  });
  groupSelect.innerHTML = options.join("");
}

function landingLabel(value) {
  const match = LANDING_OPTIONS.find((item) => item.value === value);
  return match ? match.label : (value || "-");
}

function pageLabel(pageKey) {
  const match = PAGE_OPTIONS.find((page) => page.key === pageKey);
  return match ? match.label : pageKey;
}

function roleLabel(role) {
  const roleMap = {
    admin: "Admin",
    user: "User",
    tickets_only: "Tickets only",
    hot_submitter: "HOT submitter",
    assigned_technician: "Assigned technician",
  };
  return roleMap[role] || role || "-";
}

function renderUsers(users) {
  if (!Array.isArray(users) || users.length === 0) {
    usersTableBody.innerHTML = '<tr><td colspan="7">לא נמצאו משתמשים</td></tr>';
    return;
  }

  usersTableBody.innerHTML = users.map((user) => {
    const pages = Array.isArray(user.allowed_pages)
      ? user.allowed_pages.map((page) => `<span class="user-pill">${pageLabel(page)}</span>`).join("")
      : "-";
    const statusClass = user.active ? (user.onboarded_at ? "done" : "pending") : "inactive";
    const statusLabel = user.active ? (user.onboarded_at ? "פעיל" : "ממתין להפעלה") : "לא פעיל";
    return `
      <tr>
        <td data-label="${TABLE_LABELS.full_name}">${user.full_name || "-"}</td>
        <td data-label="${TABLE_LABELS.email}">${user.email || "-"}</td>
        <td data-label="${TABLE_LABELS.role}">${roleLabel(user.role)}</td>
        <td data-label="${TABLE_LABELS.pages}">${pages || "-"}</td>
        <td data-label="${TABLE_LABELS.landing_page}">${landingLabel(user.landing_page)}</td>
        <td data-label="${TABLE_LABELS.status}"><span class="status-pill ${statusClass}">${statusLabel}</span></td>
        <td data-label="${TABLE_LABELS.actions}">
          <button class="action-btn resend-invite-btn" type="button" data-user-id="${user.id}">
            <i class="fa-solid fa-paper-plane"></i>
            <span>שלח שוב</span>
          </button>
        </td>
      </tr>
    `;
  }).join("");
}

async function loadUsers() {
  const response = await fetch("/user-management-data");
  const data = await readJson(response);
  if (!response.ok || !data.ok) {
    throw new Error(data.message || data.error || "Failed to load users");
  }
  renderGroups(data.groups || []);
  renderUsers(data.users || []);
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  setInviteMessage("");

  const payload = {
    email: document.getElementById("invite-email").value.trim(),
    full_name: document.getElementById("invite-full-name").value.trim(),
    role: document.getElementById("invite-role").value,
    group_code: groupSelect.value,
    landing_page: landingPageSelect.value,
    scope_type: document.getElementById("invite-scope-type").value,
    scope_value: document.getElementById("invite-scope-value").value.trim(),
    allowed_pages: checkedPages(),
  };

  try {
    const response = await fetch("/user-management-invite", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await readJson(response);
    if (!response.ok || !data.ok) {
      throw new Error(data.message || data.error || "Failed to create invite");
    }
    setInviteMessage(`Invitation sent to ${data.email}`, "success");
    setUsersMessage("");
    form.reset();
    renderPageOptions();
    await loadUsers();
  } catch (error) {
    setInviteMessage(error.message, "error");
  }
});

usersTableBody.addEventListener("click", async (event) => {
  const button = event.target.closest(".resend-invite-btn");
  if (!button) {
    return;
  }

  button.disabled = true;
  try {
    setUsersMessage("");
    const response = await fetch(`/user-management/${button.dataset.userId}/resend-invite`, { method: "POST" });
    const data = await readJson(response);
    if (!response.ok || !data.ok) {
      throw new Error(data.message || data.error || "Failed to resend invite");
    }
    setUsersMessage(`Invitation resent to ${data.email}`, "success");
    await loadUsers();
  } catch (error) {
    setUsersMessage(error.message, "error");
  } finally {
    button.disabled = false;
  }
});

refreshUsersButton.addEventListener("click", async () => {
  try {
    await loadUsers();
    setUsersMessage("");
  } catch (error) {
    setUsersMessage(error.message, "error");
  }
});

renderPageOptions();
loadUsers().catch((error) => setUsersMessage(error.message, "error"));
