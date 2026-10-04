const PAGE_GROUPS = [
  {
    title: "כללי",
    pages: [
      { key: "home", label: "בית" },
      { key: "user_management", label: "ניהול משתמשים" },
    ],
  },
  {
    title: "שירותים",
    pages: [
      { key: "sms", label: "SMS" },
      { key: "bot", label: "בוט" },
      { key: "f2m", label: "F2M" },
      { key: "recording_storage", label: "הקלטות" },
      { key: "human_service", label: "מוקד אנושי" },
      { key: "record", label: "הקלטה" },
    ],
  },
  {
    title: "דוחות",
    pages: [
      { key: "tickets_monthly_report", label: "דוח חודשי" },
      { key: "features_report", label: "דוח פיצרים" },
      { key: "features_status", label: "סטטוס פיצרים" },
    ],
  },
  {
    title: "תקלות",
    pages: [
      { key: "support_tickets", label: "קריאות שירות" },
      { key: "pais_tickets", label: "פיס" },
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

const BASE_LANDING_OPTIONS = [
  { value: "/dashboard-services", label: "דשבורד שירותים ראשי" },
  { value: "/dashboard-service-tickets", label: "דשבורד שירות" },
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
const roleSelect = document.getElementById("invite-role");
const userLogModal = document.getElementById("user-log-modal");
const userLogContent = document.getElementById("user-log-content");
const userLogClose = document.getElementById("user-log-close");

let usersMessageTimer = null;
let currentUsersById = new Map();
let lastSyncedRole = roleSelect ? roleSelect.value : "";

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
    throw new Error("תגובת שרת לא תקינה");
  }
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function isLimitedAdminRole(role) {
  return role === "admin_no_user_management";
}

function landingOptionsForRole(role) {
  if (isLimitedAdminRole(role)) {
    return [{ value: "/home", label: "בית" }, ...BASE_LANDING_OPTIONS];
  }
  return BASE_LANDING_OPTIONS;
}

function renderLandingOptions(selectedValue = "") {
  const options = landingOptionsForRole(roleSelect ? roleSelect.value : "");
  landingPageSelect.innerHTML = options.map((page) => `
    <option value="${page.value}">${page.label}</option>
  `).join("");

  const nextValue = options.some((item) => item.value === selectedValue)
    ? selectedValue
    : options[0]?.value || "";
  landingPageSelect.value = nextValue;
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

  syncRoleBasedPermissions();
}

function checkedPages() {
  return Array.from(pagesHost.querySelectorAll('input[type="checkbox"]:checked')).map((checkbox) => checkbox.value);
}

function setAllPagesChecked(checked) {
  pagesHost.querySelectorAll('input[type="checkbox"]').forEach((checkbox) => {
    checkbox.checked = checked;
  });
}

function renderGroups(groups) {
  const options = ['<option value="">ללא</option>'];
  (groups || []).forEach((group) => {
    options.push(`<option value="${group.code}">${group.name || group.code}</option>`);
  });
  groupSelect.innerHTML = options.join("");
}

function landingLabel(value) {
  const match = landingOptionsForRole("admin_no_user_management").find((item) => item.value === value);
  return match ? match.label : (value || "-");
}

function pageLabel(pageKey) {
  const match = PAGE_OPTIONS.find((page) => page.key === pageKey);
  return match ? match.label : pageKey;
}

function roleLabel(role) {
  const roleMap = {
    admin: "מנהל",
    admin_no_user_management: "מנהל ללא ניהול משתמשים",
    user: "משתמש",
    tickets_only: "תקלות בלבד",
    hot_submitter: "שולח HOT",
    assigned_technician: "טכנאי שירות שטח",
  };
  return roleMap[role] || role || "-";
}

function syncRoleBasedPermissions() {
  const currentRole = roleSelect ? roleSelect.value : "";
  const isLimitedAdmin = isLimitedAdminRole(currentRole);
  const isSwitchingToLimitedAdmin = isLimitedAdmin && lastSyncedRole !== "admin_no_user_management";

  if (isSwitchingToLimitedAdmin) {
    setAllPagesChecked(true);
  }

  renderLandingOptions(isLimitedAdmin ? "/home" : landingPageSelect.value);

  const userManagementCheckbox = pagesHost.querySelector('input[value="user_management"]');
  if (!userManagementCheckbox) {
    lastSyncedRole = currentRole;
    return;
  }

  if (isLimitedAdmin) {
    userManagementCheckbox.checked = false;
  }
  userManagementCheckbox.disabled = isLimitedAdmin;

  const option = userManagementCheckbox.closest(".page-option");
  if (option) {
    option.style.opacity = isLimitedAdmin ? "0.55" : "1";
  }

  lastSyncedRole = currentRole;
}

function formatLogDate(value) {
  if (!value) {
    return "-";
  }

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }

  return parsed.toLocaleString("he-IL", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function openUserLog(user) {
  if (!userLogModal || !userLogContent) {
    return;
  }

  if (!user) {
    userLogContent.innerHTML = `
      <div class="user-log-row">
        <span class="user-log-label">סטטוס</span>
        <span class="user-log-value">אין נתוני יומן זמינים עבור משתמש זה.</span>
      </div>
    `;
    userLogModal.hidden = false;
    return;
  }

  const rows = [
    ["שם", user.full_name || "-"],
    ["אימייל", user.email || "-"],
    ["תפקיד", roleLabel(user.role)],
    ["עמוד נחיתה", landingLabel(user.landing_page)],
    ["נשלחה הזמנה", formatLogDate(user.invited_at)],
    ["הושלמה הרשמה", formatLogDate(user.onboarded_at)],
    ["התחברות אחרונה", formatLogDate(user.last_login_at)],
    ["נוצר", formatLogDate(user.created_at)],
    ["עודכן", formatLogDate(user.updated_at)],
  ];

  userLogContent.innerHTML = rows.map(([label, value]) => `
    <div class="user-log-row">
      <span class="user-log-label">${escapeHtml(label)}</span>
      <span class="user-log-value">${escapeHtml(value)}</span>
    </div>
  `).join("");

  userLogModal.hidden = false;
}

function closeUserLog() {
  if (!userLogModal || !userLogContent) {
    return;
  }

  userLogModal.hidden = true;
  userLogContent.innerHTML = "";
}

function renderUsers(users) {
  currentUsersById = new Map((users || []).map((user) => [String(user.id), user]));

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
        <td data-label="${TABLE_LABELS.email}">
          <div class="email-cell">
            <span>${user.email || "-"}</span>
            <button class="ghost-btn user-log-trigger" type="button" data-user-id="${user.id}" title="יומן משתמש" aria-label="יומן משתמש">
              <i class="fa-solid fa-clock-rotate-left"></i>
            </button>
          </div>
        </td>
        <td data-label="${TABLE_LABELS.role}">${roleLabel(user.role)}</td>
        <td data-label="${TABLE_LABELS.pages}">${pages || "-"}</td>
        <td data-label="${TABLE_LABELS.landing_page}">${landingLabel(user.landing_page)}</td>
        <td data-label="${TABLE_LABELS.status}"><span class="status-pill ${statusClass}">${statusLabel}</span></td>
        <td data-label="${TABLE_LABELS.actions}">
          <button class="action-btn resend-invite-btn" type="button" data-user-id="${user.id}">
            <i class="fa-solid fa-paper-plane"></i>
            <span>שלח הזמנה שוב</span>
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
    throw new Error(data.message || data.error || "טעינת המשתמשים נכשלה");
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
      throw new Error(data.message || data.error || "יצירת ההזמנה נכשלה");
    }
    const inviteSuccessMessage = data.existing_account
      ? `החשבון כבר קיים. נשלח קישור להגדרת סיסמה אל ${data.email}`
      : `ההזמנה נשלחה אל ${data.email}`;
    setInviteMessage(inviteSuccessMessage, "success");
    setUsersMessage("");
    form.reset();
    renderPageOptions();
    await loadUsers();
  } catch (error) {
    setInviteMessage(error.message, "error");
  }
});

usersTableBody.addEventListener("click", async (event) => {
  const logButton = event.target.closest(".user-log-trigger");
  if (logButton) {
    openUserLog(currentUsersById.get(String(logButton.dataset.userId)));
    return;
  }

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
      throw new Error(data.message || data.error || "שליחה מחדש של ההזמנה נכשלה");
    }
    setUsersMessage(`ההזמנה נשלחה מחדש אל ${data.email}`, "success");
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

if (userLogClose) {
  userLogClose.addEventListener("click", closeUserLog);
}

document.addEventListener("click", (event) => {
  if (event.target.closest("#user-log-close")) {
    closeUserLog();
  }
});

if (userLogModal) {
  userLogModal.addEventListener("click", (event) => {
    if (event.target === userLogModal) {
      closeUserLog();
    }
  });
}

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && userLogModal && !userLogModal.hidden) {
    closeUserLog();
  }
});

renderPageOptions();
if (roleSelect) {
  roleSelect.addEventListener("change", syncRoleBasedPermissions);
}
loadUsers().catch((error) => setUsersMessage(error.message, "error"));
