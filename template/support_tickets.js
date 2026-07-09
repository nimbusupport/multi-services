let currentScope = "all";
let debounceTimer = null;
let lastTickets = [];
let reportQuickFilter = "all";
let ticketsLoading = false;
let paisReportLoading = false;
let autoRefreshTimer = null;

const AUTO_REFRESH_INTERVAL_MS = 10000;
const NASTYA_EDITABLE_STATUSES = ["ממתין לתאום", "תואם", "בוצע", "נכשל"];
const NASTYA_FINAL_STATUSES = ["בוצע", "נכשל"];

const supportTicketsContext = window.supportTicketsContext || {};
const boardSlug = String(supportTicketsContext.boardSlug || "support");
const boardName = String(supportTicketsContext.boardName || "Support Tickets");
const isAdmin = supportTicketsContext.isAdmin === true || supportTicketsContext.isAdmin === "true";
const supportUsers = Array.isArray(supportTicketsContext.supportUsers) ? supportTicketsContext.supportUsers : [];
const technicianUsers = Array.isArray(supportTicketsContext.technicianUsers) ? supportTicketsContext.technicianUsers : [];
const currentSupportUser = String(supportTicketsContext.currentSupportUser || "");
const supportStatuses = Array.isArray(supportTicketsContext.supportStatuses) ? supportTicketsContext.supportStatuses : ["Waiting", "Done"];
const paisStatuses = Array.isArray(supportTicketsContext.paisStatuses) ? supportTicketsContext.paisStatuses : ["ממתין", "ממתין לתאום", "תואם", "אין מענה", "בוצע", "נכשל"];
const pageMode = String(supportTicketsContext.pageMode || "board");
const ticketQueue = String(supportTicketsContext.ticketQueue || "");
const isNastyaUser = currentSupportUser === "נסטיה";

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function israelDatePreview() {
  return new Intl.DateTimeFormat("he-IL", {
    timeZone: "Asia/Jerusalem",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date());
}

function timeLabel(hour) {
  return `${String(hour).padStart(2, "0")}:00`;
}

function hourOptions(startHour, endHour, selectedValue) {
  const options = ['<option value=""></option>'];
  for (let hour = startHour; hour <= endHour; hour += 1) {
    const value = timeLabel(hour);
    options.push(`<option value="${value}" ${selectedValue === value ? "selected" : ""}>${value}</option>`);
  }
  return options.join("");
}

function nextHourValue(value) {
  const hour = Number(String(value || "").split(":")[0]);
  if (!Number.isInteger(hour)) return "";
  return timeLabel(hour + 1);
}

function priorityClass(priority) {
  return `priority-${String(priority || "medium").toLowerCase()}`;
}

function statusClassName(status) {
  if (status === "Done" || status === "בוצע") return "done";
  if (status === "ממתין לתאום" || status === "תואם") return "coordination";
  return "waiting";
}

function displayTicketStatus(ticket) {
  if (pageMode === "nastia" && ticket?.board_slug === "pais" && ticket?.status === "ממתין לתאום") {
    return "ממתין";
  }
  return ticket?.status || "";
}

function statusOptionsForTicket(ticket) {
  if (ticket.board_slug === "pais" && isNastyaUser && NASTYA_EDITABLE_STATUSES.includes(ticket.status)) {
    const options = [
      { value: ticket.status, label: displayTicketStatus(ticket) },
      ...NASTYA_FINAL_STATUSES
        .filter((status) => status !== ticket.status)
        .map((status) => ({ value: status, label: status })),
    ];
    return options.map(({ value, label }) => `
      <option value="${escapeHtml(value)}" ${ticket.status === value ? "selected" : ""}>${escapeHtml(label)}</option>
    `).join("");
  }
  const options = ticket.board_slug === "pais" ? paisStatuses : supportStatuses;
  return options.map((status) => `
    <option value="${escapeHtml(status)}" ${ticket.status === status ? "selected" : ""}>${escapeHtml(status)}</option>
  `).join("");
}

function canNastyaEditPaisInlineStatus(ticket) {
  return ticket.board_slug === "pais" && isNastyaUser && NASTYA_EDITABLE_STATUSES.includes(ticket.status);
}

function ticketDetails(ticket) {
  return ticket?.details && typeof ticket.details === "object" ? ticket.details : {};
}

function ticketHeadline(ticket) {
  const details = ticketDetails(ticket);
  if (ticket.board_slug === "pais") {
    const terminal = details.terminal_number ? `מסוף ${details.terminal_number}` : boardName;
    const address = details.address ? ` / ${details.address}` : "";
    return `${terminal}${address}`;
  }
  return `${ticket.service_type || "General"}${ticket.domain ? ` / ${ticket.domain}` : ""}`;
}

function ticketSnippet(ticket) {
  const details = ticketDetails(ticket);
  if (ticket.board_slug === "pais") {
    const parts = [details.customer_request || details.actions_taken || ""];
    if (ticket.assigned_to) {
      parts.push(`נציג: ${ticket.assigned_to}`);
    }
    if (details.coordinated_worker) {
      parts.push(`תואם: ${details.coordinated_worker}`);
    }
    if (details.visit_date) {
      const hourRange = [details.visit_hour_from, details.visit_hour_to].filter(Boolean).join(" - ");
      parts.push(`ביקור: ${details.visit_date}${hourRange ? ` ${hourRange}` : ""}`);
    }
    return parts.filter(Boolean).join(" | ");
  }
  return ticket.description || "";
}

function ticketTypeLabel(ticket) {
  if (ticket.board_slug === "pais") return "מפעל הפיס";
  return ticket.ticket_type || "";
}

function coordinationSummary(ticket) {
  const details = ticketDetails(ticket);
  if (!details.coordinated_worker && !details.visit_date) return "";
  const parts = ["תואם"];
  if (details.coordinated_worker) {
    parts.push(details.coordinated_worker);
  }
  if (details.visit_date) {
    const hourRange = [details.visit_hour_from, details.visit_hour_to].filter(Boolean).join(" - ");
    parts.push(hourRange ? `${details.visit_date} ${hourRange}` : details.visit_date);
  }
  return parts.join(" | ");
}

function applyReportQuickFilter(tickets) {
  if (!Array.isArray(tickets)) return [];
  if (reportQuickFilter === "done") {
    return tickets.filter((ticket) => ticket.status === "בוצע");
  }
  if (reportQuickFilter === "open") {
    return tickets.filter((ticket) => ticket.status !== "בוצע");
  }
  if (reportQuickFilter === "coordination") {
    return tickets.filter((ticket) => ticket.status === "ממתין לתאום");
  }
  if (reportQuickFilter === "failed") {
    return tickets.filter((ticket) => ticket.status === "נכשל");
  }
  if (reportQuickFilter === "coordinated") {
    return tickets.filter((ticket) => ticket.status === "תואם");
  }
  return tickets;
}

function setFieldInvalid(element, isInvalid) {
  if (!element) return;
  element.classList.toggle("field-invalid", Boolean(isInvalid));
}

function clearCoordinationValidation() {
  setFieldInvalid(document.getElementById("detail-coordinated-worker"), false);
  setFieldInvalid(document.getElementById("detail-visit-date"), false);
  setFieldInvalid(document.getElementById("detail-visit-hour-from"), false);
  setFieldInvalid(document.getElementById("detail-visit-hour-to"), false);
}

function renderStats(stats) {
  const statAll = document.getElementById("stat-all");
  const statUnassigned = document.getElementById("stat-unassigned");
  const statWaiting = document.getElementById("stat-waiting");
  if (statAll) statAll.textContent = stats?.all ?? 0;
  if (statUnassigned) statUnassigned.textContent = stats?.unassigned ?? 0;
  if (statWaiting) statWaiting.textContent = `${stats?.waiting ?? 0} Open`;
}

function renderTickets(tickets, users) {
  const list = document.getElementById("ticket-list");
  const empty = document.getElementById("tickets-empty");
  lastTickets = Array.isArray(tickets) ? tickets : [];
  list.innerHTML = "";

  if (!Array.isArray(tickets) || tickets.length === 0) {
    empty.style.display = "block";
    return;
  }

  empty.style.display = "none";
  tickets.forEach((ticket) => {
    const row = document.createElement("article");
    row.className = `ticket-row ${ticket.board_slug === "pais" ? "pais-row" : ""}`;
    row.dataset.ticketId = ticket.id;
    const assigneeOptions = ['<option value="">Unassigned</option>']
      .concat((users || []).map((user) => `<option value="${escapeHtml(user)}" ${ticket.assigned_to === user ? "selected" : ""}>${escapeHtml(user)}</option>`))
      .join("");
    const firstAttachment = Array.isArray(ticket.attachments) ? ticket.attachments[0] : null;
    const statusClass = statusClassName(ticket.status);
    const coordinationText = coordinationSummary(ticket);

    row.innerHTML = `
      <div class="ticket-id">${escapeHtml(ticket.ticket_id)}</div>
      <div class="ticket-main">
        <h3>${escapeHtml(ticketHeadline(ticket))}</h3>
        <p>${escapeHtml(ticketSnippet(ticket))}</p>
      </div>
      <div class="ticket-meta">
        <strong>${escapeHtml(ticketTypeLabel(ticket))}</strong><br>
        ${escapeHtml(ticket.creator)}<br>${escapeHtml(ticket.created_at_display)}
        ${coordinationText ? `<div class="ticket-meta-note">${escapeHtml(coordinationText)}</div>` : ""}
      </div>
      <select class="assignee-select" data-ticket-id="${ticket.id}" ${isNastyaUser && ticket.board_slug === "pais" ? "disabled" : ""}>${assigneeOptions}</select>
      <select class="status-select" data-ticket-id="${ticket.id}" ${(isNastyaUser && ticket.board_slug === "pais" && !canNastyaEditPaisInlineStatus(ticket)) ? "disabled" : ""}>${statusOptionsForTicket(ticket)}</select>
      <div class="ticket-actions">
        <span class="pill ${statusClass}">${escapeHtml(displayTicketStatus(ticket))}</span>
        <span class="pill ${priorityClass(ticket.priority || "Medium")}">${escapeHtml(ticket.priority || "Medium")}</span>
        ${firstAttachment ? `<button class="attachment-link" type="button" data-image-url="${escapeHtml(firstAttachment.url)}" title="Open JPG"><i class="fa-regular fa-image"></i></button>` : ""}
        ${isAdmin ? `<button class="delete-ticket-btn" type="button" data-ticket-id="${ticket.id}" title="Delete ticket"><i class="fa-solid fa-trash"></i></button>` : ""}
      </div>
    `;
    row.addEventListener("click", (event) => {
      if (event.target.closest("select, button, a, input, textarea")) return;
      openTicketDetail(ticket.id);
    });
    list.appendChild(row);
  });

  document.querySelectorAll(".assignee-select").forEach((select) => {
    if (select.disabled) return;
    select.addEventListener("change", () => updateTicket(select.dataset.ticketId, { assigned_to: select.value }));
  });
  document.querySelectorAll(".status-select").forEach((select) => {
    if (select.disabled) return;
    select.addEventListener("change", () => updateTicket(select.dataset.ticketId, { status: select.value }));
  });
  document.querySelectorAll(".attachment-link").forEach((button) => {
    button.addEventListener("click", (event) => {
      event.stopPropagation();
      openImagePreview(button.dataset.imageUrl || "");
    });
  });
  document.querySelectorAll(".delete-ticket-btn").forEach((button) => {
    button.addEventListener("click", (event) => {
      event.stopPropagation();
      deleteTicket(button.dataset.ticketId);
    });
  });
}

function getTicket(ticketId) {
  const numericId = Number(String(ticketId).replace("#", ""));
  return lastTickets.find((ticket) => Number(ticket.id) === numericId);
}

function detailItem(label, value) {
  return `
    <div class="detail-item">
      <span>${escapeHtml(label)}</span>
      <strong>${escapeHtml(value || "-")}</strong>
    </div>
  `;
}

function detailItemHtml(label, html) {
  return `
    <div class="detail-item">
      <span>${escapeHtml(label)}</span>
      <strong>${html || "-"}</strong>
    </div>
  `;
}

function phoneHref(phone) {
  const normalized = String(phone || "").replace(/[^\d+]/g, "");
  if (!normalized) return "";
  return `tel:${normalized}`;
}

function renderPhoneValue(phone) {
  const safePhone = escapeHtml(phone || "-");
  const href = phoneHref(phone);
  if (!href) return safePhone;
  return `<a class="detail-link" href="${escapeHtml(href)}">${safePhone}</a>`;
}

function renderAddressValue(address) {
  const safeAddress = String(address || "").trim();
  if (!safeAddress) return "-";
  const encodedAddress = encodeURIComponent(safeAddress);
  const wazeHref = `https://waze.com/ul?q=${encodedAddress}`;
  const googleHref = `https://www.google.com/maps/search/?api=1&query=${encodedAddress}`;
  return `
    <div class="detail-address-links">
      <div>${escapeHtml(safeAddress)}</div>
      <div class="detail-inline-links">
        <a class="detail-link" href="${escapeHtml(wazeHref)}" target="_blank" rel="noopener noreferrer">Waze</a>
        <a class="detail-link" href="${escapeHtml(googleHref)}" target="_blank" rel="noopener noreferrer">Google Maps</a>
      </div>
    </div>
  `;
}

function detailSection(title, value) {
  return `
    <section class="detail-description">
      <h3>${escapeHtml(title)}</h3>
      <p>${escapeHtml(value || "-")}</p>
    </section>
  `;
}

function renderPaisDetailSections(ticket) {
  const details = ticketDetails(ticket);
  const isCoordinatorView = isNastyaUser;
  const technicianOptions = ['<option value="">בחר עובד</option>']
    .concat(technicianUsers.map((user) => `<option value="${escapeHtml(user)}" ${details.coordinated_worker === user ? "selected" : ""}>${escapeHtml(user)}</option>`))
    .join("");
  const showCoordination = isCoordinatorView || pageMode === "nastia" || ticket.status === "ממתין לתאום" || Boolean(details.coordinated_worker || details.visit_date || details.visit_hour_from || details.visit_hour_to);
  const showFailureNotes = ticket.status === "נכשל";
  const showCoordinatorStatus = isCoordinatorView && NASTYA_EDITABLE_STATUSES.includes(ticket.status);
  const coordinatorStatusOptions = [
    { value: ticket.status, label: displayTicketStatus(ticket) },
    ...NASTYA_FINAL_STATUSES
      .filter((status) => status !== ticket.status)
      .map((status) => ({ value: status, label: status })),
  ]
    .map(({ value, label }) => `<option value="${escapeHtml(value)}" ${ticket.status === value ? "selected" : ""}>${escapeHtml(label)}</option>`)
    .join("");

  return `
    ${detailSection("פניית לקוח", details.customer_request)}
    <section class="detail-description detail-edit-card">
      <h3>פעולות</h3>
      <textarea id="detail-actions-taken" rows="4">${escapeHtml(details.actions_taken || "")}</textarea>
    </section>
    ${showCoordinatorStatus ? `
    <section class="detail-description detail-edit-card">
      <h3>סטטוס</h3>
      <select id="detail-status-select">
        ${coordinatorStatusOptions}
      </select>
    </section>` : ""}
    ${!isCoordinatorView ? `
    <section class="detail-description detail-edit-card">
      <h3>סטטוס</h3>
      <select id="detail-status-select">
        ${paisStatuses.map((status) => `<option value="${escapeHtml(status)}" ${ticket.status === status ? "selected" : ""}>${escapeHtml(status)}</option>`).join("")}
      </select>
    </section>` : ""}
    ${showCoordination ? `
    <section class="detail-description detail-edit-card">
      <h3>לאחר טיפול נציג</h3>
      <div class="detail-form-grid">
        <label>
          <span>טכנאי מתואם</span>
          <select id="detail-coordinated-worker">${technicianOptions}</select>
        </label>
        <label>
          <span>תאריך ביקור טכנאי</span>
          <input id="detail-visit-date" type="date" value="${escapeHtml(details.visit_date || "")}">
        </label>
        <label>
          <span>משעה</span>
          <select id="detail-visit-hour-from">${hourOptions(9, 17, details.visit_hour_from || "")}</select>
        </label>
        <label>
          <span>עד שעה</span>
          <select id="detail-visit-hour-to">${hourOptions(10, 18, details.visit_hour_to || "")}</select>
        </label>
      </div>
      <p class="detail-hint">חלונות התאום הם של שעה אחת, החל מ-09:00.</p>
    </section>` : ""}
    <section class="detail-description detail-edit-card ${showFailureNotes ? "" : "hidden"}" id="detail-failure-notes-wrap">
      <h3>הערות</h3>
      <textarea id="detail-failure-notes" rows="4">${escapeHtml(details.failure_notes || "")}</textarea>
    </section>
    <div class="detail-save-row">
      <span id="detail-save-message"></span>
      <button class="create-ticket-btn" id="detail-save-btn" type="button">שמור</button>
    </div>
  `;
}

function renderDetailSections(ticket) {
  if (ticket.board_slug === "pais") {
    return renderPaisDetailSections(ticket);
  }
  return [
    detailSection("Description", ticket.description),
    detailSection("Solution", ticket.solution),
  ].join("");
}

function syncPaisDetailStatusFields() {
  const statusSelect = document.getElementById("detail-status-select");
  const notesWrap = document.getElementById("detail-failure-notes-wrap");
  if (!notesWrap) return;
  if (!statusSelect) {
    notesWrap.classList.add("hidden");
    return;
  }
  notesWrap.classList.toggle("hidden", statusSelect.value !== "נכשל");
}

function syncPaisDetailVisitRange() {
  const startSelect = document.getElementById("detail-visit-hour-from");
  const endSelect = document.getElementById("detail-visit-hour-to");
  if (!startSelect || !endSelect) return;
  const nextValue = nextHourValue(startSelect.value);
  if (nextValue) {
    endSelect.value = nextValue;
  }
}

async function savePaisDetail(ticketId) {
  const coordinatedWorkerField = document.getElementById("detail-coordinated-worker");
  const visitDateField = document.getElementById("detail-visit-date");
  const visitHourFromField = document.getElementById("detail-visit-hour-from");
  const visitHourToField = document.getElementById("detail-visit-hour-to");
  const statusSelect = document.getElementById("detail-status-select");
  const coordinationPayload = {
    coordinated_worker: coordinatedWorkerField?.value || "",
    visit_date: visitDateField?.value || "",
    visit_hour_from: visitHourFromField?.value || "",
    visit_hour_to: visitHourToField?.value || "",
  };
  const selectedStatus = statusSelect?.value || "";
  const shouldMarkCoordinated = Object.values(coordinationPayload).every(Boolean);
  let nextStatus = selectedStatus;
  if (shouldMarkCoordinated && (!selectedStatus || selectedStatus === "ממתין לתאום" || selectedStatus === "תואם")) {
    nextStatus = "תואם";
  }
  const isFinalStatus = NASTYA_FINAL_STATUSES.includes(selectedStatus);

  const payload = {
    ticket_id: ticketId,
    status: nextStatus,
    details: {
      actions_taken: document.getElementById("detail-actions-taken")?.value || "",
      coordinated_worker: coordinationPayload.coordinated_worker,
      visit_date: coordinationPayload.visit_date,
      visit_hour_from: coordinationPayload.visit_hour_from,
      visit_hour_to: coordinationPayload.visit_hour_to,
      failure_notes: document.getElementById("detail-failure-notes")?.value || "",
    },
  };
  const message = document.getElementById("detail-save-message");
  const button = document.getElementById("detail-save-btn");
  if (message) message.textContent = "";
  clearCoordinationValidation();
  if (button) button.disabled = true;

  if (isNastyaUser && !isFinalStatus) {
    if (!coordinationPayload.coordinated_worker) {
      setFieldInvalid(coordinatedWorkerField, true);
      if (message) message.textContent = "לא נבחר טכנאי מטפל";
      if (button) button.disabled = false;
      return;
    }
    if (!coordinationPayload.visit_date) {
      setFieldInvalid(visitDateField, true);
      if (message) message.textContent = "לא נבחר תאריך ביקור";
      if (button) button.disabled = false;
      return;
    }
    if (!coordinationPayload.visit_hour_from) {
      setFieldInvalid(visitHourFromField, true);
      if (message) message.textContent = "לא נבחרה שעת התחלה";
      if (button) button.disabled = false;
      return;
    }
    if (!coordinationPayload.visit_hour_to) {
      setFieldInvalid(visitHourToField, true);
      if (message) message.textContent = "לא נבחרה שעת סיום";
      if (button) button.disabled = false;
      return;
    }
  }

  try {
    const res = await fetch("/support-tickets-update", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok || !data.ok) {
      throw new Error(data.message || "Save failed");
    }
    closeTicketDetail();
    await loadTickets();
    await loadPaisReport();
  } catch (err) {
    if (message) message.textContent = err.message;
  } finally {
    if (button) button.disabled = false;
  }
}

function openTicketDetail(ticketId) {
  const ticket = getTicket(ticketId);
  if (!ticket) return;

  const details = ticketDetails(ticket);
  document.getElementById("detail-kicker").textContent = ticket.board_slug === "pais" ? "מפעל הפיס" : (ticket.service_type || "Ticket");
  document.getElementById("detail-title").textContent = ticket.ticket_id || `#${String(ticket.id).padStart(4, "0")}`;

  const gridItems = [
    detailItem("Board", ticket.board_slug === "pais" ? "מפעל הפיס" : "Support Tickets"),
    detailItem("Status", displayTicketStatus(ticket)),
    detailItem("Assigned To", ticket.assigned_to || "Unassigned"),
    detailItem("Creator", ticket.creator),
    detailItem("Created", ticket.created_at_display),
    detailItem("Internal ID", ticket.id),
  ];

  if (ticket.board_slug === "pais") {
    gridItems.splice(1, 0,
      detailItem("מספר מסוף", details.terminal_number),
      detailItemHtml("כתובת", renderAddressValue(details.address)),
      detailItem("כתובת IP סטטית", details.static_ip),
      detailItem("אלטורה", details.altura),
      detailItem("look back", details.look_back),
      detailItem("נציג מטפל", ticket.assigned_to || "—"),
      detailItem("טכנאי מתואם", details.coordinated_worker || "—"),
      detailItem("תאריך ביקור", details.visit_date || "—"),
      detailItem("שעות ביקור", [details.visit_hour_from, details.visit_hour_to].filter(Boolean).join(" - ") || "—"),
      detailItem("איש קשר - שם", details.contact_name),
      detailItemHtml("איש קשר - מספר", renderPhoneValue(details.contact_phone)),
    );
  } else {
    gridItems.splice(1, 0,
      detailItem("Ticket Type", ticket.ticket_type),
      detailItem("Service Type", ticket.service_type),
      detailItem("Domain", ticket.domain),
      detailItem("Priority", ticket.priority),
    );
  }

  document.getElementById("detail-grid").innerHTML = gridItems.join("");
  document.getElementById("detail-sections").innerHTML = renderDetailSections(ticket);
  if (ticket.board_slug === "pais") {
    clearCoordinationValidation();
    document.getElementById("detail-status-select")?.addEventListener("change", syncPaisDetailStatusFields);
    document.getElementById("detail-visit-hour-from")?.addEventListener("change", syncPaisDetailVisitRange);
    document.getElementById("detail-coordinated-worker")?.addEventListener("change", () => setFieldInvalid(document.getElementById("detail-coordinated-worker"), false));
    document.getElementById("detail-visit-date")?.addEventListener("input", () => setFieldInvalid(document.getElementById("detail-visit-date"), false));
    document.getElementById("detail-visit-hour-from")?.addEventListener("change", () => setFieldInvalid(document.getElementById("detail-visit-hour-from"), false));
    document.getElementById("detail-visit-hour-to")?.addEventListener("change", () => setFieldInvalid(document.getElementById("detail-visit-hour-to"), false));
    document.getElementById("detail-save-btn")?.addEventListener("click", () => savePaisDetail(ticket.id));
    syncPaisDetailStatusFields();
    syncPaisDetailVisitRange();
  }

  const attachments = Array.isArray(ticket.attachments) ? ticket.attachments : [];
  const attachmentHost = document.getElementById("detail-attachments");
  attachmentHost.innerHTML = attachments.length
    ? attachments.map((file, index) => `
        <button class="detail-image-btn" type="button" data-image-url="${escapeHtml(file.url)}">
          <i class="fa-regular fa-image"></i>
          <span>JPG ${index + 1}</span>
        </button>
      `).join("")
    : "";
  attachmentHost.querySelectorAll(".detail-image-btn").forEach((button) => {
    button.addEventListener("click", () => openImagePreview(button.dataset.imageUrl || ""));
  });

  const modal = document.getElementById("ticket-detail-modal");
  modal.classList.add("open");
  modal.setAttribute("aria-hidden", "false");
}

function closeTicketDetail() {
  const modal = document.getElementById("ticket-detail-modal");
  modal.classList.remove("open");
  modal.setAttribute("aria-hidden", "true");
}

function openImagePreview(url) {
  if (!url) return;
  const modal = document.getElementById("image-modal");
  document.getElementById("image-preview").src = url;
  modal.classList.add("open");
  modal.setAttribute("aria-hidden", "false");
}

function closeImagePreview() {
  const modal = document.getElementById("image-modal");
  modal.classList.remove("open");
  modal.setAttribute("aria-hidden", "true");
  document.getElementById("image-preview").src = "";
}

async function loadTickets() {
  if (ticketsLoading) return;
  ticketsLoading = true;
  const params = new URLSearchParams({
    board: boardSlug,
    scope: currentScope,
    queue: ticketQueue,
    status: document.getElementById("status-filter").value,
    assignee: document.getElementById("assignee-filter").value,
    priority: document.getElementById("priority-filter").value,
    date_from: document.getElementById("date-from-filter").value,
    date_to: document.getElementById("date-to-filter").value,
    search: document.getElementById("ticket-search").value,
  });
  try {
    const res = await fetch(`/support-tickets-data?${params.toString()}`);
    if (!res.ok) return;
    const data = await res.json();
    renderStats(data.stats);
    renderTickets(applyReportQuickFilter(data.tickets), data.users);
    document.getElementById("next-ticket-id").textContent = data.next_id || "#0001";
  } finally {
    ticketsLoading = false;
  }
}

function submitTicketSearch() {
  clearTimeout(debounceTimer);
  loadTickets();
}

function hasOpenModal() {
  return ["ticket-modal", "ticket-detail-modal", "image-modal"].some((id) => document.getElementById(id)?.classList.contains("open"));
}

async function runAutoRefresh() {
  if (document.hidden || hasOpenModal()) return;
  await loadTickets();
  await loadPaisReport();
}

function startAutoRefresh() {
  if (autoRefreshTimer) {
    window.clearInterval(autoRefreshTimer);
  }
  autoRefreshTimer = window.setInterval(runAutoRefresh, AUTO_REFRESH_INTERVAL_MS);
}

function paisReportParams() {
  return new URLSearchParams({
    period: document.getElementById("pais-report-period")?.value || "daily",
    status: document.getElementById("pais-report-status")?.value || "",
    format: document.getElementById("pais-report-format")?.value || "csv",
    date_from: document.getElementById("pais-report-from")?.value || "",
    date_to: document.getElementById("pais-report-to")?.value || "",
  });
}

function renderPaisReport(data) {
  const summaryHost = document.getElementById("pais-report-summary");
  const leaderboardHost = document.getElementById("pais-report-leaderboard");
  if (!summaryHost || !leaderboardHost) return;

  const summary = data?.summary || {};
  summaryHost.innerHTML = `
    <article class="report-stat-card ${reportQuickFilter === "all" ? "active" : ""}" data-quick-filter="all">
      <strong>${escapeHtml(summary.total ?? 0)}</strong>
      <span>Total</span>
    </article>
    <article class="report-stat-card done ${reportQuickFilter === "done" ? "active" : ""}" data-quick-filter="done">
      <strong>${escapeHtml(summary.done ?? 0)}</strong>
      <span>בוצע</span>
    </article>
    <article class="report-stat-card waiting ${reportQuickFilter === "open" ? "active" : ""}" data-quick-filter="open">
      <strong>${escapeHtml(summary.waiting ?? 0)}</strong>
      <span>פתוח</span>
    </article>
    <article class="report-stat-card coordination ${reportQuickFilter === "coordination" ? "active" : ""}" data-quick-filter="coordination">
      <strong>${escapeHtml(summary.coordination ?? 0)}</strong>
      <span>ממתין לתאום</span>
    </article>
    <article class="report-stat-card failed ${reportQuickFilter === "failed" ? "active" : ""}" data-quick-filter="failed">
      <strong>${escapeHtml(summary.failed ?? 0)}</strong>
      <span>נכשל</span>
    </article>
    <article class="report-stat-card coordinated ${reportQuickFilter === "coordinated" ? "active" : ""}" data-quick-filter="coordinated">
      <strong>${escapeHtml(summary.coordinated ?? 0)}</strong>
      <span>תואם</span>
    </article>
  `;
  summaryHost.querySelectorAll("[data-quick-filter]").forEach((card) => {
    card.addEventListener("click", async () => {
      reportQuickFilter = card.dataset.quickFilter || "all";
      renderPaisReport(data);
      await loadTickets();
    });
  });

  const leaderboard = Array.isArray(data?.leaderboard) ? data.leaderboard : [];
  leaderboardHost.innerHTML = leaderboard.map((item, index) => `
    <article class="leaderboard-card">
      <div class="leaderboard-rank">#${index + 1}</div>
      <div class="leaderboard-main">
        <h3>${escapeHtml(item.user)}</h3>
        <p>${escapeHtml(item.done)} solved / ${escapeHtml(item.total)} total</p>
      </div>
      <div class="leaderboard-metrics">
        <span class="pill done">בוצע ${escapeHtml(item.done)}</span>
        <span class="pill waiting">פתוח ${escapeHtml(item.waiting)}</span>
        <span class="pill coordination">תאום ${escapeHtml(item.coordination ?? 0)}</span>
        <span class="pill ${Number(item.completion_rate) >= 60 ? "priority-low" : "priority-medium"}">${escapeHtml(item.completion_rate)}%</span>
      </div>
    </article>
  `).join("") || '<div class="tickets-empty report-empty" style="display:block">No report data found</div>';
}

async function loadPaisReport() {
  if (boardSlug !== "pais") return;
  if (paisReportLoading) return;
  paisReportLoading = true;
  try {
    const res = await fetch(`/pais-tickets-report-data?${paisReportParams().toString()}`);
    if (!res.ok) return;
    const data = await res.json();
    if (!data.ok) return;
    renderPaisReport(data);
  } finally {
    paisReportLoading = false;
  }
}

function exportPaisReport() {
  if (boardSlug !== "pais") return;
  const params = paisReportParams();
  const format = params.get("format") || "csv";
  const url = `/pais-tickets-report-export?${params.toString()}`;
  if (format === "pdf") {
    window.open(url, "_blank", "noopener");
    return;
  }
  window.location.href = url;
}

async function updateTicket(ticketId, changes) {
  const payload = { ticket_id: ticketId, ...changes };
  const res = await fetch("/support-tickets-update", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok || !data.ok) {
    alert(data.message || "Update failed");
  }
  await loadTickets();
  await loadPaisReport();
}

async function deleteTicket(ticketId) {
  const ticket = getTicket(ticketId);
  const ticketLabel = ticket?.ticket_id || `#${String(ticketId).replace("#", "").padStart(4, "0")}`;
  if (!window.confirm(`Delete ticket ${ticketLabel}?`)) {
    return;
  }

  const res = await fetch("/support-tickets-delete", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ticket_id: ticketId }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok || !data.ok) {
    alert(data.message || "Delete failed");
    return;
  }

  closeTicketDetail();
  await loadTickets();
  await loadPaisReport();
}

function openModal() {
  document.getElementById("created-preview").value = israelDatePreview();
  document.getElementById("ticket-form-message").textContent = "";
  document.getElementById("ticket-modal").classList.add("open");
  document.getElementById("ticket-modal").setAttribute("aria-hidden", "false");
  closeCreateMenu();
}

function closeModal() {
  document.getElementById("ticket-modal").classList.remove("open");
  document.getElementById("ticket-modal").setAttribute("aria-hidden", "true");
}

function closeCreateMenu() {
  const menu = document.getElementById("ticket-create-menu");
  if (menu) {
    menu.classList.remove("open");
  }
}

function syncDomainRequirement() {
  const serviceTypeInput = document.getElementById("service-type");
  const domainField = document.getElementById("domain-field");
  const domainInput = document.getElementById("domain-input");
  if (!serviceTypeInput || !domainField || !domainInput) return;
  const required = serviceTypeInput.value.trim() === "מרכזייה";
  domainField.classList.toggle("visible", required);
  domainInput.required = required;
  if (!required) domainInput.value = "";
}

function parsePaisPasteText(rawText) {
  const text = String(rawText || "").replace(/\r/g, "").trim();
  const result = {
    terminal_number: "",
    address: "",
    static_ip: "",
    altura: "",
    look_back: "",
    contact_name: "",
    contact_phone: "",
    customer_request: "",
  };
  if (!text) return result;

  const labelPatterns = [
    { key: "terminal_number", pattern: "(?:מספר\\s*מסוף|מסוף)" },
    { key: "address", pattern: "כתובת(?!\\s*(?:IP|סטטית))" },
    { key: "static_ip", pattern: "(?:כתובת\\s*(?:IP\\s*)?סטטית|כתובת\\s*IP\\s*סטטית)" },
    { key: "altura", pattern: "אלטורה" },
    { key: "look_back", pattern: "(?:loop\\s*back|look\\s*back|loopback)" },
    { key: "contact", pattern: "איש\\s*קשר" },
    { key: "customer_request", pattern: "פניית\\s*לקוח" },
  ];

  const positions = [];
  labelPatterns.forEach(({ key, pattern }) => {
    const regex = new RegExp(pattern, "ig");
    let match;
    while ((match = regex.exec(text)) !== null) {
      positions.push({ key, index: match.index, matchText: match[0] });
    }
  });
  positions.sort((a, b) => a.index - b.index);

  const sections = {};
  positions.forEach((item, index) => {
    const start = item.index + item.matchText.length;
    const end = index + 1 < positions.length ? positions[index + 1].index : text.length;
    const rawValue = text.slice(start, end).replace(/^[\s:־-]+/, "").trim();
    sections[item.key] = rawValue;
  });

  result.terminal_number = (sections.terminal_number || "").split(/\n/)[0].trim();
  result.address = (sections.address || "").split(/\n/)[0].trim();
  result.static_ip = (sections.static_ip || "").split(/\n/)[0].trim();
  result.altura = (sections.altura || "").split(/\n/)[0].trim();
  result.look_back = (sections.look_back || "").split(/\n/)[0].trim();

  const contactRaw = sections.contact || "";
  const phoneMatch = contactRaw.match(/(0\d[\d-]{7,})/);
  if (phoneMatch) {
    result.contact_phone = phoneMatch[1].trim();
    result.contact_name = contactRaw.replace(phoneMatch[1], "").replace(/^[\s:־-]+/, "").trim();
  } else {
    result.contact_name = contactRaw.split(/\n/)[0].trim();
  }

  if (sections.customer_request) {
    result.customer_request = sections.customer_request.trim();
  } else {
    const lines = text.split("\n").map((line) => line.trim()).filter(Boolean);
    const requestStart = lines.findIndex((line) => /פניית\s*לקוח/i.test(line));
    if (requestStart >= 0) {
      result.customer_request = lines.slice(requestStart + 1).join("\n").trim();
    }
  }

  return result;
}

function fillPaisFieldsFromPaste() {
  const source = document.getElementById("pais-paste-source");
  const message = document.getElementById("pais-paste-message");
  if (!source) return;
  const parsed = parsePaisPasteText(source.value);
  const mapping = {
    terminal_number: 'input[name="terminal_number"]',
    address: 'input[name="address"]',
    static_ip: 'input[name="static_ip"]',
    altura: 'input[name="altura"]',
    look_back: 'input[name="look_back"]',
    contact_name: 'input[name="contact_name"]',
    contact_phone: 'input[name="contact_phone"]',
    customer_request: 'textarea[name="customer_request"]',
  };

  let filledCount = 0;
  Object.entries(mapping).forEach(([key, selector]) => {
    const element = document.querySelector(selector);
    if (!element || !parsed[key]) return;
    element.value = parsed[key];
    filledCount += 1;
  });

  if (message) {
    message.textContent = filledCount > 0 ? `מולאו ${filledCount} שדות` : "לא זוהו שדות למילוי";
  }
}

async function submitTicket(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const message = document.getElementById("ticket-form-message");
  const submit = form.querySelector(".create-ticket-btn");
  message.textContent = "";
  submit.disabled = true;

  try {
    const res = await fetch("/support-tickets-create", {
      method: "POST",
      body: new FormData(form),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok || !data.ok) {
      throw new Error(data.message || "Create failed");
    }
    form.reset();
    const hiddenBoard = form.querySelector('input[name="board_slug"]');
    if (hiddenBoard) hiddenBoard.value = boardSlug;
    syncDomainRequirement();
    closeModal();
    await loadTickets();
    await loadPaisReport();
  } catch (err) {
    message.textContent = err.message;
  } finally {
    submit.disabled = false;
  }
}

document.addEventListener("DOMContentLoaded", () => {
  const portalToggle = document.querySelector(".portal-toggle");
  if (portalToggle) {
    portalToggle.addEventListener("click", () => {
      portalToggle.closest(".portal-menu")?.classList.toggle("collapsed");
    });
  }

  document.querySelectorAll(".ticket-tab").forEach((button) => {
    button.addEventListener("click", () => {
      document.querySelectorAll(".ticket-tab").forEach((tab) => tab.classList.remove("active"));
      button.classList.add("active");
      currentScope = button.dataset.scope || "all";
      loadTickets();
    });
  });

  ["status-filter", "assignee-filter", "priority-filter", "date-from-filter", "date-to-filter"].forEach((id) => {
    document.getElementById(id).addEventListener("change", loadTickets);
  });
  const ticketSearch = document.getElementById("ticket-search");
  const ticketSearchButton = document.getElementById("ticket-search-btn");
  ticketSearch?.addEventListener("keydown", (event) => {
    if (event.key !== "Enter") return;
    event.preventDefault();
    submitTicketSearch();
  });
  ticketSearch?.addEventListener("search", submitTicketSearch);
  ticketSearchButton?.addEventListener("click", submitTicketSearch);

  const openModalButton = document.getElementById("open-ticket-modal");
  if (openModalButton) {
    openModalButton.addEventListener("click", openModal);
  }

  const menuToggle = document.getElementById("open-create-menu");
  if (menuToggle) {
    menuToggle.addEventListener("click", (event) => {
      event.stopPropagation();
      document.getElementById("ticket-create-menu")?.classList.toggle("open");
    });
  }

  const createRegularButton = document.getElementById("create-regular-ticket");
  if (createRegularButton) {
    createRegularButton.addEventListener("click", openModal);
  }

  document.addEventListener("click", (event) => {
    if (!event.target.closest(".ticket-create-controls")) {
      closeCreateMenu();
    }
  });

  document.getElementById("close-ticket-modal").addEventListener("click", closeModal);
  document.getElementById("ticket-modal").addEventListener("click", (event) => {
    if (event.target.id === "ticket-modal") closeModal();
  });
  document.getElementById("close-detail-modal").addEventListener("click", closeTicketDetail);
  document.getElementById("ticket-detail-modal").addEventListener("click", (event) => {
    if (event.target.id === "ticket-detail-modal") closeTicketDetail();
  });
  document.getElementById("close-image-modal").addEventListener("click", closeImagePreview);
  document.getElementById("image-modal").addEventListener("click", (event) => {
    if (event.target.id === "image-modal") closeImagePreview();
  });

  const serviceTypeInput = document.getElementById("service-type");
  if (serviceTypeInput) {
    serviceTypeInput.addEventListener("input", syncDomainRequirement);
    syncDomainRequirement();
  }

  document.getElementById("ticket-form").addEventListener("submit", submitTicket);
  document.getElementById("parse-pais-paste")?.addEventListener("click", fillPaisFieldsFromPaste);
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) {
      runAutoRefresh();
    }
  });

  loadTickets();
  if (boardSlug === "pais") {
    ["pais-report-period", "pais-report-status", "pais-report-from", "pais-report-to"].forEach((id) => {
      document.getElementById(id)?.addEventListener("change", loadPaisReport);
    });
    document.getElementById("export-pais-report")?.addEventListener("click", exportPaisReport);
    loadPaisReport();
  }
  startAutoRefresh();
});
