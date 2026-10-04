const form = document.getElementById("user-invite-form");
const usersTableBody = document.getElementById("users-table-body");
const inviteMessage = document.getElementById("invite-message");
const usersMessage = document.getElementById("users-message");
const refreshUsersButton = document.getElementById("refresh-users");
const pagesHost = document.getElementById("invite-pages");
const roleSelect = document.getElementById("invite-role");
const landingPageSelect = document.getElementById("invite-landing-page");
const groupSelect = document.getElementById("invite-group-code");
const accessLevelSelect = document.getElementById("invite-access-level");
const scopeTypeSelect = document.getElementById("invite-scope-type");
const scopeValueInput = document.getElementById("invite-scope-value");
const editUserIdInput = document.getElementById("edit-user-id");
const emailInput = document.getElementById("invite-email");
const fullNameInput = document.getElementById("invite-full-name");
const formKicker = document.getElementById("user-form-kicker");
const formTitle = document.getElementById("user-form-title");
const formModeBadge = document.getElementById("form-mode-badge");
const submitLabel = document.getElementById("user-form-submit-label");
const resetPasswordButton = document.getElementById("reset-password-btn");
const cancelEditButton = document.getElementById("cancel-edit-btn");
const blockUserButton = document.getElementById("block-user-btn");
const blockUserButtonLabel = document.getElementById("block-user-btn-label");
const editOnlyActions = document.getElementById("edit-only-actions");
const userLogModal = document.getElementById("user-log-modal");
const userLogClose = document.getElementById("user-log-close");
const userLogContent = document.getElementById("user-log-content");
const summaryTotalUsers = document.getElementById("summary-total-users");
const summaryActiveUsers = document.getElementById("summary-active-users");
const summaryPendingUsers = document.getElementById("summary-pending-users");
const summaryBlockedUsers = document.getElementById("summary-blocked-users");
const groupsOverview = document.getElementById("groups-overview");
const usersSearchInput = document.getElementById("users-search");
const usersStatusFilter = document.getElementById("users-status-filter");
const usersRoleFilter = document.getElementById("users-role-filter");
const usersGroupFilter = document.getElementById("users-group-filter");
const usersResultsCount = document.getElementById("users-results-count");
const userFormModal = document.getElementById("user-form-modal");
const openCreateUserModalButton = document.getElementById("open-create-user-modal");
const closeUserFormModalButton = document.getElementById("close-user-form-modal");
const pagesFieldset = document.getElementById("pages-fieldset");
const pagesToggleButton = document.getElementById("pages-toggle-btn");
const pagesPanel = document.getElementById("pages-panel");
const pagesToggleSummary = document.getElementById("pages-toggle-summary");

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
      { key: "bot", label: "בוט" },
      { key: "sms", label: "SMS" },
      { key: "storage", label: "הקלטות" },
      { key: "f2m", label: "F2M" },
      { key: "hot", label: "HOT" },
      { key: "cloud", label: "מוקד אנושי" },
    ],
  },
  {
    title: "דוחות",
    pages: [
      { key: "tickets_monthly_report", label: "דוח חודשי" },
      { key: "features_report", label: "דוח פיצ'רים" },
      { key: "features_status", label: "סטטוס פיצ'רים" },
    ],
  },
  {
    title: "תקלות",
    pages: [
      { key: "support_tickets", label: "קריאות שירות" },
      { key: "pais", label: "פיס" },
      { key: "reports", label: "נסטיה" },
    ],
  },
];

const PAGE_OPTIONS = PAGE_GROUPS.flatMap((group) => group.pages);
const BASE_LANDING_OPTIONS = [
  { value: "/home", label: "בית" },
  { value: "/dashboard-services", label: "שירותים" },
  { value: "/dashboard-service-tickets", label: "קריאות שירות" },
  { value: "/dashboard-reports", label: "דוחות" },
  { value: "/user-management", label: "ניהול משתמשים" },
];

const TABLE_LABELS = {
  full_name: "שם",
  email: "אימייל",
  role: "תפקיד",
  group: "קבוצה",
  pages: "עמודים",
  landing_page: "עמוד נחיתה",
  status: "סטטוס",
  actions: "פעולות",
};

let currentEditUserId = "";
let currentEditUserActive = true;
let lastSyncedRole = "";
let currentUsers = [];
let currentUsersById = new Map();
let currentGroups = [];
let viewerCanWrite = true;

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

async function readJson(response) {
  const text = await response.text();
  try {
    return text ? JSON.parse(text) : {};
  } catch {
    return { ok: false, message: text || "התקבלה תשובה לא תקינה מהשרת" };
  }
}

function setMessage(node, message, tone = "") {
  if (!node) {
    return;
  }
  node.textContent = message || "";
  node.classList.remove("success", "error");
  if (tone) {
    node.classList.add(tone);
  }
}

function setInviteMessage(message, tone = "") {
  setMessage(inviteMessage, message, tone);
}

function setUsersMessage(message, tone = "") {
  setMessage(usersMessage, message, tone);
}

function setPagesExpanded(expanded) {
  if (!pagesToggleButton || !pagesPanel) {
    return;
  }
  pagesToggleButton.setAttribute("aria-expanded", expanded ? "true" : "false");
  pagesPanel.hidden = !expanded;
  if (pagesFieldset) {
    pagesFieldset.classList.toggle("is-open", expanded);
  }
}

function updatePagesSummary() {
  if (!pagesToggleSummary) {
    return;
  }
  const count = checkedPages().length;
  pagesToggleSummary.textContent = count ? `${count} עמודים נבחרו` : "לחצו להצגת ההרשאות";
}

function openUserFormModal() {
  if (userFormModal) {
    userFormModal.hidden = false;
  }
}

function closeUserFormModal() {
  if (userFormModal) {
    userFormModal.hidden = true;
  }
}

function roleLabel(role) {
  const roleMap = {
    admin: "מנהל",
    admin_no_user_management: "מנהל ללא ניהול משתמשים",
    user: "משתמש",
    tickets_only: "תקלות בלבד",
    hot_submitter: "שולח HOT",
    assigned_technician: "טכנאי שירות שטח",
    external_technician: "טכנאי חיצוני",
  };
  return roleMap[role] || role || "-";
}

function accessLevelLabel(value) {
  return value === "read_only" ? "קריאה בלבד" : "קריאה ועריכה";
}

function landingOptionsForRole(role) {
  if (role === "assigned_technician" || role === "external_technician") {
    return [
      { value: "/dashboard-service-tickets", label: "קריאות שירות" },
      { value: "/home", label: "בית" },
    ];
  }
  return BASE_LANDING_OPTIONS;
}

function landingLabel(value) {
  const option = BASE_LANDING_OPTIONS.find((item) => item.value === value);
  return option ? option.label : (value || "-");
}

function pageLabel(pageKey) {
  const match = PAGE_OPTIONS.find((page) => page.key === pageKey);
  return match ? match.label : pageKey;
}

function isLimitedAdminRole(role) {
  return role === "admin_no_user_management";
}

function renderLandingOptions(selectedValue = "") {
  const options = landingOptionsForRole(roleSelect ? roleSelect.value : "");
  landingPageSelect.innerHTML = options
    .map((option) => `<option value="${option.value}">${option.label}</option>`)
    .join("");
  const hasMatch = options.some((item) => item.value === selectedValue);
  landingPageSelect.value = hasMatch ? selectedValue : options[0]?.value || "/home";
}

function renderPageOptions() {
  pagesHost.innerHTML = PAGE_GROUPS.map((group) => `
    <section class="permission-group">
      <h3 class="permission-group-title">${group.title}</h3>
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
  updatePagesSummary();
}

function checkedPages() {
  return Array.from(pagesHost.querySelectorAll('input[type="checkbox"]:checked')).map((checkbox) => checkbox.value);
}

function setCheckedPages(pageKeys) {
  const selected = new Set(Array.isArray(pageKeys) ? pageKeys : []);
  pagesHost.querySelectorAll('input[type="checkbox"]').forEach((checkbox) => {
    checkbox.checked = selected.has(checkbox.value);
  });
  updatePagesSummary();
}

function setAllPagesChecked(checked) {
  pagesHost.querySelectorAll('input[type="checkbox"]').forEach((checkbox) => {
    checkbox.checked = checked;
  });
  updatePagesSummary();
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
  if (userManagementCheckbox) {
    if (isLimitedAdmin) {
      userManagementCheckbox.checked = false;
    }
    userManagementCheckbox.disabled = isLimitedAdmin;
    const option = userManagementCheckbox.closest(".page-option");
    if (option) {
      option.style.opacity = isLimitedAdmin ? "0.58" : "1";
    }
  }

  lastSyncedRole = currentRole;
}

function renderGroups(groups) {
  currentGroups = Array.isArray(groups) ? groups : [];

  const formOptions = ['<option value="">ללא</option>'];
  const filterOptions = ['<option value="all">כל הקבוצות</option>'];

  currentGroups.forEach((group) => {
    const label = escapeHtml(group.name || group.code || "-");
    const code = escapeHtml(group.code || "");
    formOptions.push(`<option value="${code}">${label}</option>`);
    filterOptions.push(`<option value="${code}">${label}</option>`);
  });

  groupSelect.innerHTML = formOptions.join("");
  usersGroupFilter.innerHTML = filterOptions.join("");

  if (!currentGroups.length) {
    groupsOverview.innerHTML = '<div class="group-card"><span class="group-card-name">לא הוגדרו קבוצות</span></div>';
    return;
  }

  groupsOverview.innerHTML = currentGroups.map((group) => `
    <article class="group-card">
      <span class="group-card-code">#${escapeHtml(group.id || "-")}</span>
      <strong class="group-card-name">${escapeHtml(group.name || group.code || "-")}</strong>
      <div class="summary-note">קוד: ${escapeHtml(group.code || "-")}</div>
    </article>
  `).join("");
}

function statusMeta(user) {
  if (user.active === false) {
    return { key: "inactive", label: "חסום", className: "inactive" };
  }
  if (user.onboarded_at) {
    return { key: "active", label: "פעיל", className: "done" };
  }
  return { key: "pending", label: "ממתין", className: "pending" };
}

function renderSummary(users) {
  const list = Array.isArray(users) ? users : [];
  const activeCount = list.filter((user) => statusMeta(user).key === "active").length;
  const pendingCount = list.filter((user) => statusMeta(user).key === "pending").length;
  const blockedCount = list.filter((user) => statusMeta(user).key === "inactive").length;

  summaryTotalUsers.textContent = String(list.length);
  summaryActiveUsers.textContent = String(activeCount);
  summaryPendingUsers.textContent = String(pendingCount);
  summaryBlockedUsers.textContent = String(blockedCount);
}

function formatLogDate(value) {
  if (!value) {
    return "-";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat("he-IL", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function applyUserFilters(users) {
  const searchTerm = (usersSearchInput?.value || "").trim().toLowerCase();
  const statusFilter = usersStatusFilter?.value || "all";
  const roleFilter = usersRoleFilter?.value || "all";
  const groupFilter = usersGroupFilter?.value || "all";

  return (Array.isArray(users) ? users : []).filter((user) => {
    const meta = statusMeta(user);
    const matchesSearch = !searchTerm || [user.full_name, user.email]
      .filter(Boolean)
      .some((value) => String(value).toLowerCase().includes(searchTerm));
    const matchesStatus = statusFilter === "all" || meta.key === statusFilter;
    const matchesRole = roleFilter === "all" || (user.role || "") === roleFilter;
    const matchesGroup = groupFilter === "all" || (user.group_code || "") === groupFilter;
    return matchesSearch && matchesStatus && matchesRole && matchesGroup;
  });
}

function renderUsers(users) {
  const filteredUsers = applyUserFilters(users);
  currentUsersById = new Map((currentUsers || []).map((user) => [String(user.id), user]));

  usersResultsCount.textContent = `${filteredUsers.length} משתמשים`;

  if (!filteredUsers.length) {
    usersTableBody.innerHTML = '<tr><td colspan="9">לא נמצאו משתמשים לפי הסינון שנבחר</td></tr>';
    return;
  }

  usersTableBody.innerHTML = filteredUsers.map((user) => {
    const pages = Array.isArray(user.allowed_pages) && user.allowed_pages.length
      ? user.allowed_pages.map((page) => `<span class="user-pill">${escapeHtml(pageLabel(page))}</span>`).join("")
      : "-";
    const meta = statusMeta(user);
    const group = currentGroups.find((item) => (item.code || "") === (user.group_code || ""));
    const groupLabel = group ? (group.name || group.code) : (user.group_code || "-");

    return `
      <tr>
        <td data-label="${TABLE_LABELS.full_name}">${escapeHtml(user.full_name || "-")}</td>
        <td data-label="${TABLE_LABELS.email}">
          <div class="email-cell">
            <span>${escapeHtml(user.email || "-")}</span>
            <button class="ghost-btn user-log-trigger" type="button" data-user-id="${escapeHtml(user.id)}" title="יומן משתמש" aria-label="יומן משתמש">
              <i class="fa-solid fa-clock-rotate-left"></i>
            </button>
          </div>
        </td>
        <td data-label="${TABLE_LABELS.role}">${escapeHtml(roleLabel(user.role))}</td>
        <td data-label="${TABLE_LABELS.group}">${escapeHtml(groupLabel)}</td>
        <td data-label="רמת הרשאה">${escapeHtml(accessLevelLabel(user.access_level))}</td>
        <td data-label="${TABLE_LABELS.pages}">${pages}</td>
        <td data-label="${TABLE_LABELS.landing_page}">${escapeHtml(landingLabel(user.landing_page))}</td>
        <td data-label="${TABLE_LABELS.status}"><span class="status-pill ${meta.className}">${meta.label}</span></td>
        <td data-label="${TABLE_LABELS.actions}">
          <div class="table-actions">
            <button class="ghost-btn edit-user-btn" type="button" data-user-id="${escapeHtml(user.id)}">
              <i class="fa-solid fa-pen"></i>
              <span>ערוך</span>
            </button>
            <button class="action-btn resend-invite-btn" type="button" data-user-id="${escapeHtml(user.id)}" ${viewerCanWrite ? "" : "disabled"}>
              <i class="fa-solid fa-paper-plane"></i>
              <span>שלח שוב</span>
            </button>
          </div>
        </td>
      </tr>
    `;
  }).join("");
}

function updateFormMode() {
  const isEditing = Boolean(currentEditUserId);
  if (formKicker) {
    formKicker.textContent = isEditing ? "עריכת משתמש" : "משתמש חדש";
  }
  if (formTitle) {
    formTitle.textContent = isEditing ? "עריכת משתמש והרשאות" : "הוספת משתמש ושליחת הזמנה";
  }
  if (formModeBadge) {
    formModeBadge.textContent = isEditing ? "עריכה" : "יצירה";
  }
  if (submitLabel) {
    submitLabel.textContent = isEditing ? "שמור שינויים" : "הוספת משתמש ושליחת הזמנה";
  }
  if (form) {
    Array.from(form.elements).forEach((element) => {
      if (!(element instanceof HTMLElement)) {
        return;
      }
      if (element.id === "cancel-edit-btn") {
        element.disabled = false;
        return;
      }
      if (!viewerCanWrite) {
        element.disabled = element.type !== "hidden";
      }
    });
  }
  if (editOnlyActions) {
    editOnlyActions.hidden = !isEditing;
  }
  if (blockUserButtonLabel) {
    blockUserButtonLabel.textContent = currentEditUserActive ? "חסום משתמש" : "בטל חסימה";
  }
}

function openCreateUserMode() {
  currentEditUserId = "";
  currentEditUserActive = true;
  if (editUserIdInput) {
    editUserIdInput.value = "";
  }
  form.reset();
  if (roleSelect) {
    roleSelect.value = "user";
  }
  if (accessLevelSelect) {
    accessLevelSelect.value = "read_write";
  }
  renderPageOptions();
  setCheckedPages(["home"]);
  renderLandingOptions(landingOptionsForRole(roleSelect ? roleSelect.value : "")[0]?.value || "/home");
  if (groupSelect) {
    groupSelect.value = "";
  }
  if (scopeTypeSelect) {
    scopeTypeSelect.value = "";
  }
  if (scopeValueInput) {
    scopeValueInput.value = "";
  }
  setInviteMessage("");
  syncRoleBasedPermissions();
  updateFormMode();
  setPagesExpanded(false);
  openUserFormModal();
}

function resetUserForm(scrollToTop = false) {
  currentEditUserId = "";
  currentEditUserActive = true;
  if (editUserIdInput) {
    editUserIdInput.value = "";
  }
  form.reset();
  if (roleSelect) {
    roleSelect.value = "user";
  }
  if (accessLevelSelect) {
    accessLevelSelect.value = "read_write";
  }
  renderPageOptions();
  setCheckedPages(["home"]);
  renderLandingOptions(landingOptionsForRole(roleSelect ? roleSelect.value : "")[0]?.value || "/home");
  if (groupSelect) {
    groupSelect.value = "";
  }
  if (scopeTypeSelect) {
    scopeTypeSelect.value = "";
  }
  if (scopeValueInput) {
    scopeValueInput.value = "";
  }
  syncRoleBasedPermissions();
  updateFormMode();
  setPagesExpanded(false);
  closeUserFormModal();
  if (scrollToTop) {
    window.scrollTo({ top: 0, behavior: "smooth" });
  }
}

function startEditUser(user) {
  if (!user) {
    return;
  }
  currentEditUserId = String(user.id || "");
  currentEditUserActive = user.active !== false;
  if (editUserIdInput) {
    editUserIdInput.value = currentEditUserId;
  }
  if (emailInput) {
    emailInput.value = user.email || "";
  }
  if (fullNameInput) {
    fullNameInput.value = user.full_name || "";
  }
  if (roleSelect) {
    roleSelect.value = user.role || "user";
  }
  renderPageOptions();
  setCheckedPages(Array.isArray(user.allowed_pages) && user.allowed_pages.length ? user.allowed_pages : ["home"]);
  renderLandingOptions(user.landing_page || "");
  if (groupSelect) {
    groupSelect.value = user.group_code || "";
  }
  if (accessLevelSelect) {
    accessLevelSelect.value = user.access_level || "read_write";
  }
  if (scopeTypeSelect) {
    scopeTypeSelect.value = user.scope_type || "";
  }
  if (scopeValueInput) {
    scopeValueInput.value = user.scope_value || "";
  }
  syncRoleBasedPermissions();
  updateFormMode();
  setPagesExpanded(false);
  openUserFormModal();
  setInviteMessage(`כעת עורכים את המשתמש ${user.email || ""}`, "success");
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function collectFormPayload() {
  return {
    email: (emailInput?.value || "").trim(),
    full_name: (fullNameInput?.value || "").trim(),
    role: roleSelect?.value || "user",
    group_code: groupSelect?.value || "",
    access_level: accessLevelSelect?.value || "read_write",
    landing_page: landingPageSelect?.value || "/home",
    scope_type: scopeTypeSelect?.value || "",
    scope_value: (scopeValueInput?.value || "").trim(),
    allowed_pages: checkedPages(),
  };
}

function openUserLog(user) {
  if (!userLogModal || !userLogContent) {
    return;
  }
  if (!user) {
    userLogContent.innerHTML = `
      <div class="user-log-row">
        <span class="user-log-label">מידע</span>
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
    ["רמת הרשאה", accessLevelLabel(user.access_level)],
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

async function loadUsers() {
  const response = await fetch("/user-management-data");
  const data = await readJson(response);
  if (!response.ok || !data.ok) {
    throw new Error(data.message || data.error || "טעינת המשתמשים נכשלה");
  }
  viewerCanWrite = data.can_write !== false;
  currentUsers = Array.isArray(data.users) ? data.users : [];
  renderGroups(data.groups || []);
  renderSummary(currentUsers);
  renderUsers(currentUsers);
  if (!viewerCanWrite) {
    setInviteMessage("החשבון שלך מוגדר כקריאה בלבד. ניתן לצפות, אך לא לבצע שינויים.", "error");
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  setInviteMessage("");

  const payload = collectFormPayload();
  const isEditing = Boolean(currentEditUserId);
  const endpoint = isEditing ? `/user-management/${currentEditUserId}/update` : "/user-management-invite";

  try {
    const response = await fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await readJson(response);
    if (!response.ok || !data.ok) {
      throw new Error(data.message || data.error || (isEditing ? "שמירת המשתמש נכשלה" : "יצירת ההזמנה נכשלה"));
    }

    if (isEditing) {
      setInviteMessage(`פרטי המשתמש ${data.user?.email || payload.email} נשמרו בהצלחה`, "success");
      setUsersMessage(data.message || "פרטי המשתמש נשמרו", "success");
      resetUserForm(true);
    } else {
      const inviteSuccessMessage = data.existing_account
        ? `החשבון כבר קיים. נשלח קישור להגדרת סיסמה אל ${data.email}`
        : `ההזמנה נשלחה אל ${data.email}`;
      setInviteMessage(inviteSuccessMessage, "success");
      setUsersMessage("");
      resetUserForm(true);
    }

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

  const editButton = event.target.closest(".edit-user-btn");
  if (editButton) {
    startEditUser(currentUsersById.get(String(editButton.dataset.userId)));
    return;
  }

  const resendButton = event.target.closest(".resend-invite-btn");
  if (!resendButton) {
    return;
  }

  resendButton.disabled = true;
  try {
    setUsersMessage("");
    const response = await fetch(`/user-management/${resendButton.dataset.userId}/resend-invite`, { method: "POST" });
    const data = await readJson(response);
    if (!response.ok || !data.ok) {
      throw new Error(data.message || data.error || "שליחה מחדש של ההזמנה נכשלה");
    }
    setUsersMessage(`ההזמנה נשלחה מחדש אל ${data.email}`, "success");
    await loadUsers();
  } catch (error) {
    setUsersMessage(error.message, "error");
  } finally {
    resendButton.disabled = false;
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

if (pagesToggleButton) {
  pagesToggleButton.addEventListener("click", () => {
    const expanded = pagesToggleButton.getAttribute("aria-expanded") === "true";
    setPagesExpanded(!expanded);
  });
}

if (pagesHost) {
  pagesHost.addEventListener("change", (event) => {
    const target = event.target;
    if (target instanceof HTMLInputElement && target.type === "checkbox") {
      updatePagesSummary();
    }
  });
}

if (openCreateUserModalButton) {
  openCreateUserModalButton.addEventListener("click", () => {
    openCreateUserMode();
  });
}

if (closeUserFormModalButton) {
  closeUserFormModalButton.addEventListener("click", () => {
    if (currentEditUserId) {
      resetUserForm(true);
      return;
    }
    closeUserFormModal();
  });
}

[usersSearchInput, usersStatusFilter, usersRoleFilter, usersGroupFilter].forEach((node) => {
  if (node) {
    node.addEventListener("input", () => renderUsers(currentUsers));
    node.addEventListener("change", () => renderUsers(currentUsers));
  }
});

if (userLogClose) {
  userLogClose.addEventListener("click", closeUserLog);
}

if (userLogModal) {
  userLogModal.addEventListener("click", (event) => {
    if (event.target === userLogModal) {
      closeUserLog();
    }
  });
}

if (userFormModal) {
  userFormModal.addEventListener("click", (event) => {
    if (event.target === userFormModal) {
      if (currentEditUserId) {
        resetUserForm(true);
        return;
      }
      closeUserFormModal();
    }
  });
}

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    if (userLogModal && !userLogModal.hidden) {
      closeUserLog();
      return;
    }
    if (userFormModal && !userFormModal.hidden && !currentEditUserId) {
      closeUserFormModal();
      return;
    }
    if (currentEditUserId) {
      resetUserForm(true);
    }
  }
});

if (blockUserButton) {
  blockUserButton.addEventListener("click", async () => {
    if (!currentEditUserId) {
      return;
    }
    blockUserButton.disabled = true;
    try {
      const response = await fetch(`/user-management/${currentEditUserId}/set-active`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ active: !currentEditUserActive }),
      });
      const data = await readJson(response);
      if (!response.ok || !data.ok) {
        throw new Error(data.message || data.error || "עדכון מצב המשתמש נכשל");
      }
      setInviteMessage(data.message || "מצב המשתמש עודכן", "success");
      setUsersMessage(data.message || "מצב המשתמש עודכן", "success");
      resetUserForm(true);
      await loadUsers();
    } catch (error) {
      setInviteMessage(error.message, "error");
    } finally {
      blockUserButton.disabled = false;
    }
  });
}

if (cancelEditButton) {
  cancelEditButton.addEventListener("click", () => resetUserForm(true));
}

if (resetPasswordButton) {
  resetPasswordButton.addEventListener("click", async () => {
    if (!currentEditUserId) {
      return;
    }
    resetPasswordButton.disabled = true;
    try {
      const response = await fetch(`/user-management/${currentEditUserId}/reset-password`, { method: "POST" });
      const data = await readJson(response);
      if (!response.ok || !data.ok) {
        throw new Error(data.message || data.error || "איפוס הסיסמה נכשל");
      }
      setInviteMessage(data.message || `קישור לאיפוס סיסמה נשלח אל ${data.email}`, "success");
      setUsersMessage(data.message || `קישור לאיפוס סיסמה נשלח אל ${data.email}`, "success");
      await loadUsers();
    } catch (error) {
      setInviteMessage(error.message, "error");
    } finally {
      resetPasswordButton.disabled = false;
    }
  });
}

if (roleSelect) {
  roleSelect.addEventListener("change", syncRoleBasedPermissions);
}

resetUserForm();
setPagesExpanded(false);
loadUsers().catch((error) => setUsersMessage(error.message, "error"));
