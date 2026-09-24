let currentScope = "all";
let debounceTimer = null;
let lastTickets = [];
let reportQuickFilter = "all";
let ticketsLoading = false;
let paisReportLoading = false;
let autoRefreshTimer = null;
let leaderboardWorkersVisible = false;
let imagePreviewScale = 1;
let sendSuccessToastTimer = null;
let signaturePadDirty = false;
let activeFieldReportSignatureTarget = "customer";
let nastyaBoardFilter = "all";

const AUTO_REFRESH_INTERVAL_MS = 10000;
const NASTYA_EDITABLE_STATUSES = ["ממתין לתיאום", "תואם", "בוצע", "נכשל"];
const NASTYA_FINAL_STATUSES = ["בוצע", "נכשל"];

const supportTicketsContext = window.supportTicketsContext || {};
const boardSlug = String(supportTicketsContext.boardSlug || "support");
const boardName = String(supportTicketsContext.boardName || "נימבוס");
const isAdmin = supportTicketsContext.isAdmin === true || supportTicketsContext.isAdmin === "true";
const supportUsers = Array.isArray(supportTicketsContext.supportUsers) ? supportTicketsContext.supportUsers : [];
const technicianUsers = Array.isArray(supportTicketsContext.technicianUsers) ? supportTicketsContext.technicianUsers : [];
const currentSupportUser = String(supportTicketsContext.currentSupportUser || "");
const supportStatuses = Array.isArray(supportTicketsContext.supportStatuses) ? supportTicketsContext.supportStatuses : ["Waiting", "Done"];
const paisStatuses = Array.isArray(supportTicketsContext.paisStatuses) ? supportTicketsContext.paisStatuses : ["ממתין", "ממתין לתיאום", "תואם", "אין מענה", "בוצע", "נכשל"];
const pageMode = String(supportTicketsContext.pageMode || "board");
const ticketQueue = String(supportTicketsContext.ticketQueue || "");
const ticketOperatorMode = String(supportTicketsContext.ticketOperatorMode || "default");
const canUploadTicketAttachments = supportTicketsContext.canUploadTicketAttachments === true || supportTicketsContext.canUploadTicketAttachments === "true";
const canDeleteTicketAttachments = supportTicketsContext.canDeleteTicketAttachments === true || supportTicketsContext.canDeleteTicketAttachments === "true";
const defaultTicketScope = String(supportTicketsContext.defaultTicketScope || "all");
const isNastyaQueuePage = pageMode === "nastia" || ticketQueue === "nastia";
const isAssignedTechnicianMode = ticketOperatorMode === "assigned_technician";
const ticketBoards = Array.isArray(supportTicketsContext.ticketBoards) ? supportTicketsContext.ticketBoards : [];
const ticketBoardsBySlug = new Map(ticketBoards.map((board) => [String(board?.slug || ""), board || {}]));
currentScope = defaultTicketScope;

function boardConfig(boardSlugValue) {
  return ticketBoardsBySlug.get(String(boardSlugValue || "")) || {};
}

function boardDisplayName(boardSlugValue) {
  return String(boardConfig(boardSlugValue).name || (boardSlugValue === "support" ? "נימבוס" : ""));
}

function boardSupportsCoordination(boardSlugValue) {
  return String(boardConfig(boardSlugValue).workflow || "") === "coordination";
}

function boardSupportsReport(boardSlugValue) {
  return boardConfig(boardSlugValue).report_enabled === true;
}

function isCoordinationTicket(ticket) {
  return boardSupportsCoordination(ticket?.board_slug);
}

function isPaisTicket(ticket) {
  return ticket?.board_slug === "pais";
}

function isHotTicket(ticket) {
  return ticket?.board_slug === "hot-kiryot";
}

function normalizePendingStatus(status) {
  return String(status || "") === "ממתין לתאום" ? "ממתין לתיאום" : String(status || "");
}

function canAssignedTechnicianEditTicket(ticket) {
  const details = ticketDetails(ticket);
  const ownerName = isCoordinationTicket(ticket)
    ? String(details.coordinated_worker || "")
    : String(ticket?.assigned_to || "");
  return isAssignedTechnicianMode
    && isCoordinationTicket(ticket)
    && ownerName === currentSupportUser;
}

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

function leaderboardRankMarkup(index, doneCount) {
  if (Number(doneCount) <= 0) {
    return `<span class="leaderboard-rank">#${index + 1}</span>`;
  }
  if (index === 0) {
    return '<span class="leaderboard-rank top-1"><i class="fa-solid fa-trophy" aria-hidden="true"></i></span>';
  }
  if (index === 1) {
    return '<span class="leaderboard-rank top-2"><i class="fa-solid fa-trophy" aria-hidden="true"></i></span>';
  }
  if (index === 2) {
    return '<span class="leaderboard-rank top-3"><i class="fa-solid fa-trophy" aria-hidden="true"></i></span>';
  }
  return `<span class="leaderboard-rank">#${index + 1}</span>`;
}

function statusClassName(status) {
  const normalizedStatus = normalizePendingStatus(status);
  if (normalizedStatus === "Done" || normalizedStatus === "בוצע" || normalizedStatus === "נכשל") return "done";
  if (normalizedStatus === "ממתין לתיאום" || normalizedStatus === "תואם") return "coordination";
  return "waiting";
}

function attachmentExtension(file) {
  const name = String(file?.original_name || file?.saved_name || "").toLowerCase();
  const dotIndex = name.lastIndexOf(".");
  return dotIndex >= 0 ? name.slice(dotIndex) : "";
}

function isPdfAttachment(file) {
  return attachmentExtension(file) === ".pdf";
}

function isImageAttachment(file) {
  return [".jpg", ".jpeg", ".png", ".webp", ".gif"].includes(attachmentExtension(file));
}

function displayTicketStatus(ticket) {
  if (pageMode === "nastia" && ticket?.board_slug === "pais" && normalizePendingStatus(ticket?.status) === "ממתין לתיאום") {
    return "ממתין";
  }
  return ticket?.status || "";
}

function statusOptionsForTicket(ticket) {
  if (canAssignedTechnicianEditTicket(ticket)) {
    const statuses = [ticket.status, ...NASTYA_FINAL_STATUSES.filter((status) => status !== ticket.status)];
    return statuses.map((status) => `
      <option value="${escapeHtml(status)}" ${ticket.status === status ? "selected" : ""}>${escapeHtml(displayTicketStatus({ ...ticket, status }))}</option>
    `).join("");
  }
  if (ticket.board_slug === "pais" && isNastyaQueuePage && NASTYA_EDITABLE_STATUSES.includes(ticket.status)) {
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
  return ticket.board_slug === "pais" && isNastyaQueuePage && NASTYA_EDITABLE_STATUSES.includes(ticket.status);
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
  if (ticket.board_slug === "support") {
    const business = details.business_name || ticket.service_type || boardDisplayName(ticket.board_slug);
    const address = details.service_address ? ` / ${details.service_address}` : "";
    return `${business}${address}`;
  }
  if (ticket.board_slug === "hot-kiryot") {
    const callNumber = details.call_number ? `פניה ${details.call_number}` : boardDisplayName(ticket.board_slug);
    const customer = details.customer_name ? ` / ${details.customer_name}` : "";
    const address = details.address ? ` / ${details.address}` : "";
    return `${callNumber}${customer}${address}`;
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

function ticketListTimestamp(ticket) {
  return ticket?.list_timestamp_display || ticket?.last_edited_at_display || ticket?.created_at_display || "";
}

function detailDisplayValue(value, fallback = "—") {
  const text = String(value ?? "").trim();
  return text || fallback;
}

function pushCopyLine(lines, label, value, fallback = "—") {
  lines.push(`${label}: ${detailDisplayValue(value, fallback)}`);
}

function ticketCopyText(ticket) {
  const details = ticketDetails(ticket);
  const lines = [];

  pushCopyLine(lines, "Ticket", ticket.ticket_id || `#${String(ticket.id || "").padStart(4, "0")}`);
  pushCopyLine(lines, "Board", ticket.board_slug === "pais" ? "מפעל הפיס" : "נימבוס");
  if (ticket.board_slug !== "pais") {
    pushCopyLine(lines, "Ticket Type", ticket.ticket_type);
    pushCopyLine(lines, "Service Type", ticket.service_type);
    pushCopyLine(lines, "Domain", ticket.domain);
  }
  pushCopyLine(lines, "Status", displayTicketStatus(ticket));
  pushCopyLine(lines, "Priority", ticket.priority || "Medium");
  pushCopyLine(lines, "Assigned To", ticket.assigned_to || "Unassigned");
  pushCopyLine(lines, "Creator", ticket.creator);
  pushCopyLine(lines, "Created", ticket.created_at_display);
  pushCopyLine(lines, "Last Edited", ticket.last_edited_at_display);
  pushCopyLine(lines, "Internal ID", ticket.id);

  if (ticket.board_slug === "pais") {
    lines.push("");
    lines.push("Details");
    pushCopyLine(lines, "Terminal Number", details.terminal_number);
    pushCopyLine(lines, "Address", details.address);
    pushCopyLine(lines, "Static IP", details.static_ip);
    pushCopyLine(lines, "Altura", details.altura);
    pushCopyLine(lines, "Loop Back", details.look_back);
    pushCopyLine(lines, "Contact Name", details.contact_name);
    pushCopyLine(lines, "Contact Phone", details.contact_phone);
    pushCopyLine(lines, "Customer Request", details.customer_request);
    pushCopyLine(lines, "Actions Taken", details.actions_taken);
    pushCopyLine(lines, "Coordinated Worker", details.coordinated_worker);
    pushCopyLine(lines, "Visit Date", details.visit_date);
    pushCopyLine(lines, "Visit Hours", [details.visit_hour_from, details.visit_hour_to].filter(Boolean).join(" - "));
    pushCopyLine(lines, "Failure Notes", details.failure_notes);
  } else {
    lines.push("");
    lines.push("Details");
    pushCopyLine(lines, "Description", ticket.description);
    pushCopyLine(lines, "Solution", ticket.solution);
  }

  const attachments = Array.isArray(ticket.attachments) ? ticket.attachments : [];
  lines.push("");
  lines.push("Attachments");
  if (attachments.length === 0) {
    lines.push("None");
  } else {
    attachments.forEach((file, index) => {
      const label = file?.original_name || file?.saved_name || `Image ${index + 1}`;
      const url = String(file?.url || "").trim();
      lines.push(`${index + 1}. ${label}${url ? ` - ${url}` : ""}`);
    });
  }

  return lines.join("\n");
}

async function writeTextToClipboard(text) {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text);
    return;
  }

  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.setAttribute("readonly", "");
  textarea.style.position = "fixed";
  textarea.style.opacity = "0";
  document.body.appendChild(textarea);
  textarea.focus();
  textarea.select();
  document.execCommand("copy");
  textarea.remove();
}

function flashCopyButton(button, success) {
  if (!button) return;
  const originalTitle = button.dataset.originalTitle || button.getAttribute("title") || "";
  if (!button.dataset.originalTitle) {
    button.dataset.originalTitle = originalTitle;
  }
  button.setAttribute("title", success ? "Copied" : "Copy failed");
  button.setAttribute("aria-label", success ? "Copied" : "Copy failed");
  window.setTimeout(() => {
    button.setAttribute("title", originalTitle || "Copy ticket details");
    button.setAttribute("aria-label", originalTitle || "Copy ticket details");
  }, 1400);
}

async function copyTicketDetails(ticketId, triggerButton = null) {
  const ticket = getTicket(ticketId);
  if (!ticket) return;

  try {
    await writeTextToClipboard(ticketCopyText(ticket));
    flashCopyButton(triggerButton, true);
  } catch (err) {
    flashCopyButton(triggerButton, false);
    alert("Copy failed");
  }
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

function todayIsraelDateValue() {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Jerusalem",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(new Date());
  const getPart = (type) => parts.find((part) => part.type === type)?.value || "";
  return `${getPart("year")}-${getPart("month")}-${getPart("day")}`;
}

function formatCoordinationVisitDate(dateValue) {
  const value = String(dateValue || "").trim();
  const match = value.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (!match) return value;
  const [, year, month, day] = match;
  return `${day}/${month}/${year.slice(-2)}`;
}

function coordinationMetaMarkup(ticket) {
  const details = ticketDetails(ticket);
  const worker = String(details.coordinated_worker || "").trim();
  const visitDate = String(details.visit_date || "").trim();
  const hourRange = [details.visit_hour_from, details.visit_hour_to].filter(Boolean).join(" - ");
  if (!worker && !visitDate && !hourRange) return "";

  const isTodayVisit = Boolean(visitDate) && visitDate === todayIsraelDateValue();
  const dateLabel = visitDate ? `${isTodayVisit ? "היום" : "ביקור"} | ${formatCoordinationVisitDate(visitDate)}` : "";

  return `
    <div class="ticket-meta-note ${isTodayVisit ? "is-today" : ""}">
      ${worker ? `<span class="ticket-meta-note-line ticket-meta-note-worker">תואם: ${escapeHtml(worker)}</span>` : ""}
      ${dateLabel ? `<span class="ticket-meta-note-line ticket-meta-note-date ${isTodayVisit ? "today" : ""}">${escapeHtml(dateLabel)}</span>` : ""}
      ${hourRange ? `<span class="ticket-meta-note-line ticket-meta-note-hours">${escapeHtml(hourRange)}</span>` : ""}
    </div>
  `;
}

function applyReportQuickFilter(tickets) {
  if (!Array.isArray(tickets)) return [];
  if (reportQuickFilter === "done") {
    return tickets.filter((ticket) => ["בוצע", "נכשל"].includes(normalizePendingStatus(ticket.status)));
  }
  if (reportQuickFilter === "open") {
    return tickets.filter((ticket) => !["בוצע", "נכשל"].includes(normalizePendingStatus(ticket.status)));
  }
  if (reportQuickFilter === "coordination") {
    return tickets.filter((ticket) => normalizePendingStatus(ticket.status) === "ממתין לתיאום");
  }
  if (reportQuickFilter === "failed") {
    return tickets.filter((ticket) => ticket.status === "נכשל");
  }
  if (reportQuickFilter === "coordinated") {
    return tickets.filter((ticket) => ticket.status === "תואם");
  }
  return tickets;
}

function applyNastyaBoardFilter(tickets) {
  if (!Array.isArray(tickets)) return [];
  if (!isNastyaQueuePage || nastyaBoardFilter === "all") {
    return tickets;
  }
  return tickets.filter((ticket) => String(ticket?.board_slug || "") === nastyaBoardFilter);
}

function syncNastyaBoardFilterButtons() {
  document.querySelectorAll("[data-board-filter]").forEach((button) => {
    const isActive = String(button.dataset.boardFilter || "") === nastyaBoardFilter;
    button.classList.toggle("is-active", isActive);
    button.setAttribute("aria-pressed", isActive ? "true" : "false");
  });
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

function setTicketsLoading(isLoading) {
  const stage = document.getElementById("ticket-list-stage");
  const loading = document.getElementById("tickets-loading");
  const empty = document.getElementById("tickets-empty");
  const refreshIndicator = document.getElementById("tickets-refresh-indicator");
  const showBlockingLoader = Boolean(isLoading) && lastTickets.length === 0;
  if (stage) {
    stage.classList.toggle("is-loading", showBlockingLoader);
  }
  if (loading) {
    loading.hidden = !showBlockingLoader;
  }
  if (refreshIndicator) {
    refreshIndicator.hidden = !isLoading;
  }
  if (showBlockingLoader && empty) {
    empty.style.display = "none";
  }
}

function renderStats(stats) {
  const statAll = document.getElementById("stat-all");
  const statUnassigned = document.getElementById("stat-unassigned");
  const statWaiting = document.getElementById("stat-waiting");
  if (statAll) statAll.textContent = stats?.all ?? 0;
  if (statUnassigned) statUnassigned.textContent = stats?.unassigned ?? 0;
  if (statWaiting) statWaiting.textContent = `${stats?.waiting ?? 0} Open`;
  document.querySelectorAll("[data-board-counter]").forEach((chip) => {
    const boardCounter = String(chip.dataset.boardCounter || "");
    const value = stats?.board_waiting?.[boardCounter] ?? 0;
    const counter = chip.querySelector("strong");
    if (counter) counter.textContent = String(value);
  });
  syncNastyaBoardFilterButtons();
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
    const attachmentCount = Array.isArray(ticket.attachments) ? ticket.attachments.length : 0;
    const statusClass = statusClassName(ticket.status);
    const coordinationMarkup = coordinationMetaMarkup(ticket);

    row.innerHTML = `
      <div class="ticket-id">${escapeHtml(ticket.ticket_id)}</div>
      <div class="ticket-main">
        <h3>${escapeHtml(ticketHeadline(ticket))}</h3>
        <p>${escapeHtml(ticketSnippet(ticket))}</p>
      </div>
      <div class="ticket-extra">
        ${firstAttachment ? `
          <button
            class="ticket-attachment-indicator"
            type="button"
            data-image-url="${escapeHtml(firstAttachment.url)}"
            title="${attachmentCount > 1 ? `${attachmentCount} files attached` : "1 file attached"}"
            aria-label="${attachmentCount > 1 ? `${attachmentCount} files attached` : "1 file attached"}"
          >
            <i class="fa-solid fa-paperclip"></i>
            <span>${escapeHtml(attachmentCount)}</span>
          </button>
        ` : ""}
      </div>
      <div class="ticket-meta">
        <strong>${escapeHtml(ticketTypeLabel(ticket))}</strong><br>
        ${escapeHtml(ticket.creator)}<br>${escapeHtml(ticketListTimestamp(ticket))}
        ${coordinationMarkup || ""}
      </div>
      <select class="assignee-select" data-ticket-id="${ticket.id}" ${isNastyaQueuePage && ticket.board_slug === "pais" ? "disabled" : ""}>${assigneeOptions}</select>
      <select class="status-select" data-ticket-id="${ticket.id}" ${(isNastyaQueuePage && ticket.board_slug === "pais" && !canNastyaEditPaisInlineStatus(ticket)) ? "disabled" : ""}>${statusOptionsForTicket(ticket)}</select>
      <div class="ticket-actions">
        <span class="pill ${statusClass}">${escapeHtml(displayTicketStatus(ticket))}</span>
        <span class="pill ${priorityClass(ticket.priority || "Medium")}">${escapeHtml(ticket.priority || "Medium")}</span>
        <button class="copy-ticket-btn" type="button" data-ticket-id="${ticket.id}" title="Copy ticket details" aria-label="Copy ticket details"><i class="fa-regular fa-copy"></i></button>
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
  document.querySelectorAll(".ticket-attachment-indicator").forEach((button) => {
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
  document.querySelectorAll(".copy-ticket-btn").forEach((button) => {
    button.addEventListener("click", async (event) => {
      event.stopPropagation();
      await copyTicketDetails(button.dataset.ticketId, button);
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

function extractPhoneNumber(text) {
  const match = String(text || "").match(/(\+?\d[\d -]{7,}\d)/);
  return match ? match[1].trim() : "";
}

function renderContactWithPhone(text) {
  const safeText = String(text || "").trim();
  if (!safeText) return "-";
  const phone = extractPhoneNumber(safeText);
  if (!phone) return escapeHtml(safeText);
  const href = phoneHref(phone);
  if (!href) return escapeHtml(safeText);
  const safePhone = escapeHtml(phone);
  const safeFullText = escapeHtml(safeText);
  return safeFullText.replace(safePhone, `<a class="detail-link" href="${escapeHtml(href)}">${safePhone}</a>`);
}

function selectedSupportServiceMode(root = document) {
  const field = root.querySelector('input[name="service_mode"][type="hidden"], input[name="service_mode"]:checked, select[name="service_mode"]');
  return String(field?.value || "");
}

function selectedSupportCustomerType(root = document) {
  const field = root.querySelector('input[name="customer_type"]:checked, select[name="customer_type"]');
  return String(field?.value || "");
}

function closeServiceModeMenus(exceptSelector = null) {
  document.querySelectorAll(".service-mode-selector").forEach((selector) => {
    if (exceptSelector && selector === exceptSelector) return;
    selector.querySelector('[data-role="menu"]')?.classList.remove("open");
    selector.querySelector('[data-role="toggle"]')?.setAttribute("aria-expanded", "false");
  });
}

function syncServiceModeSelector(selector, root = document) {
  if (!selector) return;
  const hiddenInput = selector.querySelector('input[name="service_mode"]');
  const label = selector.querySelector('[data-role="label"]');
  const toggle = selector.querySelector('[data-role="toggle"]');
  const selectedMode = String(hiddenInput?.value || "");
  const placeholder = selector.dataset.placeholder || "בחר סוג טיפול";
  if (label) {
    label.textContent = selectedMode || placeholder;
  }
  if (toggle) {
    toggle.classList.toggle("selected", Boolean(selectedMode));
  }
  selector.querySelectorAll("[data-service-mode]").forEach((button) => {
    button.classList.toggle("active", button.dataset.serviceMode === selectedMode);
  });
  toggleSupportServiceDetails(root);
}

function setupServiceModeSelectors(root = document) {
  root.querySelectorAll(".service-mode-selector").forEach((selector) => {
    const toggle = selector.querySelector('[data-role="toggle"]');
    const menu = selector.querySelector('[data-role="menu"]');
    const hiddenInput = selector.querySelector('input[name="service_mode"]');
    if (!toggle || !menu || !hiddenInput) return;
    if (!selector.dataset.bound) {
      toggle.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopPropagation();
        const willOpen = !menu.classList.contains("open");
        closeServiceModeMenus(willOpen ? selector : null);
        menu.classList.toggle("open", willOpen);
        toggle.setAttribute("aria-expanded", willOpen ? "true" : "false");
      });
      menu.querySelectorAll("[data-service-mode]").forEach((button) => {
        button.addEventListener("click", () => {
          hiddenInput.value = String(button.dataset.serviceMode || "");
          syncServiceModeSelector(selector, root);
          closeServiceModeMenus();
        });
      });
      selector.dataset.bound = "true";
    }
    syncServiceModeSelector(selector, root);
  });
}

function toggleSupportServiceDetails(root = document) {
  const detailsWrap = root.querySelector("#support-create-service-details, #support-service-details");
  if (!detailsWrap) return;
  const hasSelection = Boolean(selectedSupportServiceMode(root));
  detailsWrap.hidden = !hasSelection;
  detailsWrap.querySelectorAll("input").forEach((input) => {
    input.required = hasSelection;
  });
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

function detailSectionHtml(title, html) {
  return `
    <section class="detail-description">
      <h3>${escapeHtml(title)}</h3>
      <div class="detail-rich-content">${html || "-"}</div>
    </section>
  `;
}

function todayIsraelDate() {
  return new Intl.DateTimeFormat("en-GB", {
    timeZone: "Asia/Jerusalem",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date());
}

function splitContactName(rawValue) {
  const cleanValue = String(rawValue || "").replace(/\s+/g, " ").trim();
  if (!cleanValue) {
    return { firstName: "", lastName: "" };
  }
  const withoutPhone = extractPhoneNumber(cleanValue)
    ? cleanValue.replace(extractPhoneNumber(cleanValue), "").replace(/\s+/g, " ").trim()
    : cleanValue;
  const [firstName = "", ...rest] = withoutPhone.split(" ").filter(Boolean);
  return {
    firstName,
    lastName: rest.join(" "),
  };
}

function normalizeFieldReportLineItems(items) {
  return (Array.isArray(items) ? items : [])
    .filter((row) => row && typeof row === "object")
    .map((row) => ({
      item_name: String(row.item_name || ""),
      quantity: String(row.quantity || ""),
      notes: String(row.notes || ""),
    }));
}

function lineItemsHasData(items) {
  return (Array.isArray(items) ? items : []).some((row) => (
    row && typeof row === "object" && Object.values(row).some((value) => String(value || "").trim())
  ));
}

function fieldReportLineItemHasData(row) {
  return row && typeof row === "object" && Object.values(row).some((value) => String(value || "").trim());
}

function fieldReportLineItemRowHtml(index, row = {}) {
  return `
    <tr data-line-item-row="${index}">
      <td><input id="field-report-item-name-${index}" type="text" data-line-item="item_name" data-index="${index}" value="${escapeHtml(row.item_name || "")}"></td>
      <td><input id="field-report-item-quantity-${index}" type="number" min="1" max="100" step="1" inputmode="numeric" data-line-item="quantity" data-index="${index}" value="${escapeHtml(row.quantity || "")}"></td>
      <td><input id="field-report-item-notes-${index}" type="text" data-line-item="notes" data-index="${index}" value="${escapeHtml(row.notes || "")}"></td>
    </tr>
  `;
}

function collectFieldReportLineItems() {
  return Array.from(document.querySelectorAll("#field-report-line-items tr")).map((row) => ({
    item_name: row.querySelector('[data-line-item="item_name"]')?.value || "",
    quantity: row.querySelector('[data-line-item="quantity"]')?.value || "",
    notes: row.querySelector('[data-line-item="notes"]')?.value || "",
  }));
}

function appendFieldReportLineItemRow(row = {}) {
  const host = document.getElementById("field-report-line-items");
  if (!host) return;
  const index = host.querySelectorAll("tr").length;
  host.insertAdjacentHTML("beforeend", fieldReportLineItemRowHtml(index, row));
  bindFieldReportLineItemInputs();
}

function ensureSingleTrailingEmptyLineItemRow() {
  const host = document.getElementById("field-report-line-items");
  if (!host) return;
  let items = collectFieldReportLineItems();
  if (items.length === 0) {
    appendFieldReportLineItemRow();
    return;
  }
  while (items.length > 1 && !fieldReportLineItemHasData(items[items.length - 1]) && !fieldReportLineItemHasData(items[items.length - 2])) {
    host.lastElementChild?.remove();
    items = collectFieldReportLineItems();
  }
  const lastRow = items[items.length - 1];
  if (fieldReportLineItemHasData(lastRow)) {
    appendFieldReportLineItemRow();
  }
}

function bindFieldReportLineItemInputs() {
  document.querySelectorAll('#field-report-line-items input').forEach((input) => {
    if (input.dataset.bound === "true") return;
    input.addEventListener("input", (event) => {
      if (event.currentTarget.dataset.lineItem === "quantity") {
        const digitsOnly = String(event.currentTarget.value || "").replace(/\D+/g, "");
        if (!digitsOnly) {
          event.currentTarget.value = "";
        } else {
          event.currentTarget.value = String(Math.min(100, Math.max(1, Number(digitsOnly))));
        }
      }
      ensureSingleTrailingEmptyLineItemRow();
    });
    input.dataset.bound = "true";
  });
}

function renderFieldReportLineItemRows(items) {
  const host = document.getElementById("field-report-line-items");
  if (!host) return;
  const normalizedItems = normalizeFieldReportLineItems(items)
    .filter((row) => Object.values(row).some((value) => String(value || "").trim()));
  const visibleRows = normalizedItems.length ? [...normalizedItems, { item_name: "", quantity: "", notes: "" }] : [{ item_name: "", quantity: "", notes: "" }];
  host.innerHTML = visibleRows.map((row, index) => fieldReportLineItemRowHtml(index, row)).join("");
  bindFieldReportLineItemInputs();
}

function renderFieldReportPhotoList(attachments, hostId, emptyLabel) {
  const host = document.getElementById(hostId);
  if (!host) return;
  const files = Array.isArray(attachments) ? attachments : [];
  host.innerHTML = files.length
    ? files.map((file, index) => {
      const label = file?.original_name || file?.saved_name || `Photo ${index + 1}`;
      const href = String(file?.url || "").trim();
      return href
        ? `<a class="detail-file-btn field-report-photo-chip" href="${escapeHtml(href)}" download><i class="fa-regular fa-image"></i><span>${escapeHtml(label)}</span></a>`
        : `<span class="field-report-photo-chip"><i class="fa-regular fa-image"></i><span>${escapeHtml(label)}</span></span>`;
    }).join("")
    : `<span class="field-report-empty">${escapeHtml(emptyLabel)}</span>`;
}

function technicianDisplayName() {
  return String(currentSupportUser || "").trim() || "טכנאי";
}

function setFieldReportItemsExpanded(expanded) {
  const body = document.getElementById("field-report-items-body");
  const button = document.getElementById("field-report-items-toggle");
  const icon = button?.querySelector(".field-report-collapse-icon");
  if (body) {
    body.hidden = !expanded;
  }
  if (button) {
    button.setAttribute("aria-expanded", expanded ? "true" : "false");
    button.classList.toggle("expanded", Boolean(expanded));
  }
  if (icon) {
    icon.textContent = expanded ? "−" : "+";
  }
}

function fieldReportSummaryCard(ticket, allowEdit = false) {
  const report = ticketDetails(ticket).field_report;
  if (!report || typeof report !== "object") return "";
  const pdfUrl = String(report?.pdf_attachment?.url || "").trim();
  const photoCount = Array.isArray(report.area_photo_attachments) ? report.area_photo_attachments.length : 0;
  const contactName = [report.contact_first_name, report.contact_last_name].filter(Boolean).join(" ");
  return `
    <section class="detail-description detail-edit-card">
      <h3>טופס אישור קבלת ציוד והתקנה</h3>
      <div class="field-report-summary">
        <div><strong>שם הלקוח:</strong> ${escapeHtml(report.nimbus_customer_name || "-")}</div>
        <div><strong>נציג / לקוח:</strong> ${escapeHtml(contactName || "-")}</div>
        <div><strong>טלפון:</strong> ${escapeHtml(report.phone || "-")}</div>
        <div><strong>טכנאי מבצע:</strong> ${escapeHtml(report.technician_name || report.submitted_by || "-")}</div>
        <div><strong>מועד התקנה:</strong> ${escapeHtml(report.installation_date || "-")}</div>
        <div><strong>צילומים:</strong> ${escapeHtml(photoCount ? String(photoCount) : "0")}</div>
        ${report.additional_notes ? `<div><strong>הערות נוספות:</strong> ${escapeHtml(report.additional_notes)}</div>` : ""}
        ${report.submitted_at_display ? `<div><strong>נשמר:</strong> ${escapeHtml(report.submitted_at_display)}</div>` : ""}
      </div>
      <div class="field-report-actions">
        ${allowEdit ? `<button class="create-ticket-btn open-field-report-btn" type="button" data-ticket-id="${escapeHtml(ticket.id)}">
          <i class="fa-solid fa-file-signature"></i><span>${pdfUrl ? "עדכן טופס" : "החתמת לקוח"}</span>
        </button>` : ""}
        ${pdfUrl ? `<a class="secondary-btn field-report-download-btn" href="${escapeHtml(pdfUrl)}" download>הורד PDF</a>` : ""}
      </div>
    </section>
  `;
}

function renderPaisDetailSections(ticket) {
  const details = ticketDetails(ticket);
  const technicianMode = canAssignedTechnicianEditTicket(ticket);
  const isCoordinatorView = isNastyaQueuePage;
  const technicianOptions = ['<option value="">בחר עובד</option>']
    .concat(technicianUsers.map((user) => `<option value="${escapeHtml(user)}" ${details.coordinated_worker === user ? "selected" : ""}>${escapeHtml(user)}</option>`))
    .join("");
  const showCoordination = isCoordinatorView || pageMode === "nastia" || normalizePendingStatus(ticket.status) === "ממתין לתיאום" || Boolean(details.coordinated_worker || details.visit_date || details.visit_hour_from || details.visit_hour_to);
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

  if (technicianMode) {
    return `
      ${detailSection("פניית לקוח", details.customer_request)}
      ${detailSection("פעולות", details.actions_taken)}
      <section class="detail-description detail-edit-card">
        <h3>סטטוס</h3>
        <select id="detail-status-select">
          ${statusOptionsForTicket(ticket)}
        </select>
      </section>
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
  const currentTicket = getTicket(ticketId);
  const currentDetails = ticketDetails(currentTicket);
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
  if (shouldMarkCoordinated && (!selectedStatus || selectedStatus === "ממתין לתיאום" || selectedStatus === "תואם")) {
    nextStatus = "תואם";
  }
  const isFinalStatus = NASTYA_FINAL_STATUSES.includes(selectedStatus);

  const payload = {
    ticket_id: ticketId,
    source_page_mode: pageMode,
    source_ticket_queue: ticketQueue,
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

  if (isNastyaQueuePage && !isFinalStatus) {
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

  const coordinationChanged = ["coordinated_worker", "visit_date", "visit_hour_from", "visit_hour_to"]
    .some((fieldName) => String(currentDetails?.[fieldName] || "") !== String(coordinationPayload[fieldName] || ""));
  if (isNastyaQueuePage && shouldMarkCoordinated && coordinationChanged) {
    payload.send_nastia_notification = true;
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
    if (data?.ticket?.notification_error) {
      openNotificationErrorModal(`הסטטוס עודכן אבל שליחת המייל נכשלה: ${data.ticket.notification_error}`);
    } else if (data?.ticket?.notification_sent === true) {
      showSendSuccessToast();
    } else if (payload.send_nastia_notification === true) {
      openNotificationErrorModal("הסטטוס עודכן אבל טריגר המייל לא הופעל.");
    }
    closeTicketDetail();
    await loadTickets();
    await loadPaisReport();
  } catch (err) {
    openNotificationErrorModal(err.message || "Save failed");
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
    detailItem("Board", ticket.board_slug === "pais" ? "מפעל הפיס" : "נימבוס"),
    detailItem("Status", displayTicketStatus(ticket)),
    detailItem("Assigned To", ticket.assigned_to || "Unassigned"),
    detailItem("Creator", ticket.creator),
    detailItem("Created", ticket.created_at_display),
    detailItem("Last Edited", ticket.last_edited_at_display || "—"),
    detailItem("Internal ID", ticket.id),
  ];

  if (ticket.board_slug === "pais") {
    gridItems.splice(1, 0,
      detailItem("מספר מסוף", details.terminal_number),
      detailItemHtml("כתובת", renderAddressValue(details.address)),
      detailItem("כתובת IP סטטית", details.static_ip),
      detailItem("אלטורה", details.altura),
      detailItem("loop back", details.look_back),
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
  const detailCopyButton = document.getElementById("detail-copy-btn");
  if (detailCopyButton) {
    detailCopyButton.dataset.ticketId = ticket.id;
  }
  document.getElementById("detail-upload-ticket-id").value = ticket.id;
  document.getElementById("detail-upload-form")?.reset();
  document.getElementById("detail-upload-message").textContent = "";
  syncDetailAttachmentInputState();
  if (ticket.board_slug === "pais") {
    clearCoordinationValidation();
    document.getElementById("detail-status-select")?.addEventListener("change", syncPaisDetailStatusFields);
    document.getElementById("detail-visit-hour-from")?.addEventListener("change", syncPaisDetailVisitRange);
    document.getElementById("detail-coordinated-worker")?.addEventListener("change", () => setFieldInvalid(document.getElementById("detail-coordinated-worker"), false));
    document.getElementById("detail-visit-date")?.addEventListener("input", () => setFieldInvalid(document.getElementById("detail-visit-date"), false));
    document.getElementById("detail-visit-hour-from")?.addEventListener("change", () => setFieldInvalid(document.getElementById("detail-visit-hour-from"), false));
    document.getElementById("detail-visit-hour-to")?.addEventListener("change", () => setFieldInvalid(document.getElementById("detail-visit-hour-to"), false));
    document.getElementById("detail-save-btn")?.addEventListener("click", () => saveTicketDetailWithFeedback(ticket.id));
    syncPaisDetailStatusFields();
    syncPaisDetailVisitRange();
  }

  const attachments = Array.isArray(ticket.attachments) ? ticket.attachments : [];
  const attachmentHost = document.getElementById("detail-attachments");
  attachmentHost.innerHTML = attachments.length
    ? attachments.map((file, index) => `
        <div class="detail-attachment-item">
          <button class="detail-image-btn" type="button" data-image-url="${escapeHtml(file.url)}">
            <i class="fa-solid fa-paperclip"></i>
            <span>File ${index + 1}</span>
          </button>
          <button
            class="detail-attachment-delete"
            type="button"
            data-ticket-id="${escapeHtml(ticket.id)}"
            data-folder="${escapeHtml(file.folder || "")}"
            data-saved-name="${escapeHtml(file.saved_name || "")}"
            title="Delete file"
          >
            <i class="fa-solid fa-trash"></i>
          </button>
        </div>
      `).join("")
    : "";
  attachmentHost.querySelectorAll(".detail-image-btn").forEach((button) => {
    button.addEventListener("click", () => openImagePreview(button.dataset.imageUrl || ""));
  });
  attachmentHost.querySelectorAll(".detail-attachment-delete").forEach((button) => {
    button.addEventListener("click", () => deleteDetailAttachment(
      button.dataset.ticketId || "",
      button.dataset.folder || "",
      button.dataset.savedName || "",
    ));
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

function openNotificationErrorModal(message) {
  const modal = document.getElementById("notification-error-modal");
  const messageHost = document.getElementById("notification-error-message");
  if (messageHost) {
    messageHost.textContent = message || "אירעה שגיאה בשליחת המייל.";
  }
  if (!modal) return;
  modal.classList.add("open");
  modal.setAttribute("aria-hidden", "false");
}

function closeNotificationErrorModal() {
  const modal = document.getElementById("notification-error-modal");
  if (!modal) return;
  modal.classList.remove("open");
  modal.setAttribute("aria-hidden", "true");
}

function showSendSuccessToast() {
  const toast = document.getElementById("send-success-toast");
  if (!toast) return;
  toast.classList.add("visible");
  toast.setAttribute("aria-hidden", "false");
  if (sendSuccessToastTimer) {
    window.clearTimeout(sendSuccessToastTimer);
  }
  sendSuccessToastTimer = window.setTimeout(() => {
    toast.classList.remove("visible");
    toast.setAttribute("aria-hidden", "true");
  }, 5000);
}

function clampImageScale(scale) {
  return Math.min(Math.max(scale, 1), 4);
}

function applyImagePreviewScale(scale) {
  const preview = document.getElementById("image-preview");
  if (!preview) return;
  imagePreviewScale = clampImageScale(scale);
  preview.style.transform = `scale(${imagePreviewScale})`;
  preview.style.cursor = imagePreviewScale > 1 ? "grab" : "zoom-in";
}

function adjustImagePreviewScale(delta) {
  applyImagePreviewScale(imagePreviewScale + delta);
}

function resetImagePreviewScale() {
  applyImagePreviewScale(1);
  const stage = document.getElementById("image-stage");
  if (stage) {
    stage.scrollTop = 0;
    stage.scrollLeft = 0;
    stage.classList.remove("is-panning");
  }
  document.getElementById("image-preview")?.classList.remove("is-panning");
}

function openImagePreview(url) {
  if (!url) return;
  const modal = document.getElementById("image-modal");
  const preview = document.getElementById("image-preview");
  const downloadLink = document.getElementById("download-image-preview");
  preview.src = url;
  downloadLink.href = url;
  downloadLink.setAttribute("download", decodeURIComponent(url.split("/").pop() || "attachment"));
  resetImagePreviewScale();
  modal.classList.add("open");
  modal.setAttribute("aria-hidden", "false");
}

function closeImagePreview() {
  const modal = document.getElementById("image-modal");
  modal.classList.remove("open");
  modal.setAttribute("aria-hidden", "true");
  const preview = document.getElementById("image-preview");
  preview.src = "";
  preview.style.transform = "";
  preview.classList.remove("is-panning");
  document.getElementById("download-image-preview")?.setAttribute("href", "#");
  document.getElementById("download-image-preview")?.removeAttribute("download");
  document.getElementById("image-stage")?.classList.remove("is-panning");
  imagePreviewScale = 1;
}

async function loadTickets() {
  if (ticketsLoading) return;
  ticketsLoading = true;
  setTicketsLoading(true);
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
    renderTickets(applyNastyaBoardFilter(applyReportQuickFilter(data.tickets)), data.users);
    document.getElementById("next-ticket-id").textContent = data.next_id || "#0001";
  } finally {
    ticketsLoading = false;
    setTicketsLoading(false);
  }
}

function submitTicketSearch() {
  clearTimeout(debounceTimer);
  loadTickets();
}

function hasOpenModal() {
  return ["ticket-modal", "ticket-detail-modal", "notification-error-modal", "image-modal"].some((id) => document.getElementById(id)?.classList.contains("open"));
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
    board: boardSlug,
    period: document.getElementById("pais-report-period")?.value || "monthly",
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
      <span>ממתין לתיאום</span>
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
  const leaderboardCards = leaderboard.map((item, index) => `
    <article class="leaderboard-card">
      ${leaderboardRankMarkup(index, item.done)}
      <div class="leaderboard-main">
        <h3>${escapeHtml(item.user)}</h3>
        <p>${escapeHtml(item.done)} בוצע מתוך ${escapeHtml(item.total)} בתקופה שנבחרה</p>
      </div>
      <div class="leaderboard-metrics">
        <span class="pill done">בוצע ${escapeHtml(item.done)}</span>
        <span class="pill waiting">פתוח ${escapeHtml(item.waiting)}</span>
        <span class="pill coordination">תאום ${escapeHtml(item.coordination ?? 0)}</span>
        <span class="pill priority-low">${escapeHtml(item.done)} / ${escapeHtml(item.total)}</span>
      </div>
    </article>
  `).join("");
  leaderboardHost.innerHTML = `
    <div class="leaderboard-toolbar">
      <div class="leaderboard-toolbar-copy">
      <p>רשימת העובדים מוסתרת כברירת מחדל.</p>
      <p class="leaderboard-period-total">בוצע בתקופה: ${escapeHtml(data?.period_done_total ?? summary.done ?? 0)}</p>
      </div>
      <button class="icon-btn leaderboard-toggle-btn" id="leaderboard-toggle-btn" type="button" aria-expanded="${leaderboardWorkersVisible ? "true" : "false"}" aria-label="${leaderboardWorkersVisible ? "הסתר עובדים" : "הצג עובדים"}">
        <i class="fa-solid ${leaderboardWorkersVisible ? "fa-eye-slash" : "fa-eye"}"></i>
        <span>${leaderboardWorkersVisible ? "הסתר עובדים" : "הצג עובדים"}</span>
      </button>
    </div>
    <div class="leaderboard-list" ${leaderboardWorkersVisible ? "" : "hidden"}>
      ${leaderboardCards || '<div class="tickets-empty report-empty" style="display:block">No report data found</div>'}
    </div>
  `;
  document.getElementById("leaderboard-toggle-btn")?.addEventListener("click", () => {
    leaderboardWorkersVisible = !leaderboardWorkersVisible;
    renderPaisReport(data);
  });
}

async function loadPaisReport() {
  if (!boardSupportsReport(boardSlug)) return;
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
  if (!boardSupportsReport(boardSlug)) return;
  const params = paisReportParams();
  const url = `/pais-tickets-report-export?${params.toString()}`;
  window.location.href = url;
}

async function updateTicket(ticketId, changes) {
  if (Object.prototype.hasOwnProperty.call(changes || {}, "status") && !changes?.status) {
    return;
  }
  if (isAssignedTechnicianMode && changes.status === "נכשל" && (!changes.details || !String(changes.details.failure_notes || "").trim())) {
    const reason = window.prompt("למה קריאה נכשלה?");
    if (reason === null) {
      await loadTickets();
      return;
    }
    if (!String(reason).trim()) {
      openNotificationErrorModal("יש למלא סיבת כשל");
      await loadTickets();
      return;
    }
    changes = {
      ...changes,
      details: {
        ...(changes.details || {}),
        failure_notes: String(reason).trim(),
      },
    };
  }
  const payload = {
    ticket_id: ticketId,
    source_page_mode: pageMode,
    source_ticket_queue: ticketQueue,
    ...changes,
  };
  const res = await fetch("/support-tickets-update", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok || !data.ok) {
    openNotificationErrorModal(data.message || "Update failed");
    return;
  }
  if (data?.ticket?.notification_error) {
    openNotificationErrorModal(`הסטטוס עודכן אבל שליחת המייל נכשלה: ${data.ticket.notification_error}`);
  } else if (data?.ticket?.notification_sent === true) {
    showSendSuccessToast();
  } else if (payload.send_nastia_notification === true) {
    openNotificationErrorModal("הסטטוס עודכן אבל טריגר המייל לא הופעל.");
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
  setupServiceModeSelectors(document.getElementById("ticket-form"));
  toggleSupportServiceDetails(document.getElementById("ticket-form"));
  document.getElementById("ticket-modal").classList.add("open");
  document.getElementById("ticket-modal").setAttribute("aria-hidden", "false");
  closeCreateMenu();
}

function closeModal() {
  closeServiceModeMenus();
  toggleSupportServiceDetails(document.getElementById("ticket-form"));
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
  toggleSupportServiceDetails(document.getElementById("ticket-form"));
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

  const complaintPattern = [
    "\u05E4\u05E0\u05D9\u05D9\u05EA\\s*\u05DC\u05E7\u05D5\u05D7",
    "\u05EA\u05DC\u05D5\u05E0\u05D4?",
    "\u05D4\u05DC\u05E7\u05D5\u05D7\\s*\u05D8\u05D5\u05E2\u05DF",
  ].join("|");

  const labelPatterns = [
    { key: "terminal_number", pattern: "(?:מספר\\s*מסוף|מסוף)" },
    { key: "address", pattern: "כתובת(?!\\s*(?:IP|סטטית))" },
    { key: "static_ip", pattern: "(?:כתובת\\s*(?:IP\\s*)?סטטית|כתובת\\s*IP\\s*סטטית)" },
    { key: "altura", pattern: "אלטורה" },
    { key: "look_back", pattern: "(?:loop\\s*back|look\\s*back|loopback)" },
    { key: "contact", pattern: "איש\\s*קשר" },
    { key: "customer_request", pattern: "(?:פניית\\s*לקוח|תלונת?|תלונה)" },
  ];
  labelPatterns[labelPatterns.length - 1].pattern = `(?:${complaintPattern})`;

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
  const contactLine = contactRaw.split(/\n/)[0].replace(/^[\s:־-]+/, "").trim();
  const phoneMatch = contactRaw.match(/(0\d[\d-]{7,})/);
  if (phoneMatch) {
    result.contact_phone = phoneMatch[1].trim();
    result.contact_name = contactLine.replace(phoneMatch[1], "").trim();
  } else {
    result.contact_name = contactLine;
  }

  if (sections.customer_request) {
    result.customer_request = sections.customer_request.trim();
  } else {
    const lines = text.split("\n").map((line) => line.trim()).filter(Boolean);
    const requestStart = lines.findIndex((line) => /(?:פניית\s*לקוח|תלונת?|תלונה)/i.test(line));
    if (requestStart >= 0) {
      result.customer_request = lines.slice(requestStart + 1).join("\n").trim();
    }
  }

  if (!result.customer_request) {
    result.customer_request = contactRaw
      .split(/\n/)
      .slice(1)
      .join("\n")
      .trim();
  }

  if (!result.customer_request) {
    const complaintHeaderMatch = text.match(new RegExp(`(?:${complaintPattern})[\\s:ײ¾-]*([\\s\\S]+)$`, "i"));
    if (complaintHeaderMatch?.[1]) {
      result.customer_request = complaintHeaderMatch[1].trim();
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

function syncAttachmentInputState() {
  const input = document.getElementById("attachment-input");
  const hint = document.getElementById("attachment-file-count");
  if (!hint) return;
  const files = Array.from(input?.files || []);
  if (files.length === 0) {
    hint.textContent = "Drag images here or click to choose JPG, PNG, WEBP, GIF";
    return;
  }
  hint.textContent = files.length === 1
    ? files[0].name
    : `${files.length} images selected`;
}

function syncDetailAttachmentInputState() {
  const input = document.getElementById("detail-attachment-input");
  const hint = document.getElementById("detail-attachment-file-count");
  if (!hint) return;
  const files = Array.from(input?.files || []);
  if (files.length === 0) {
    hint.textContent = "Choose JPG, PNG, WEBP, GIF";
    return;
  }
  hint.textContent = files.length === 1
    ? files[0].name
    : `${files.length} images selected`;
}

async function uploadDetailAttachments(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const message = document.getElementById("detail-upload-message");
  const button = document.getElementById("detail-upload-btn");
  const input = document.getElementById("detail-attachment-input");
  const ticketId = document.getElementById("detail-upload-ticket-id")?.value || "";
  if (message) message.textContent = "";
  if (!input?.files?.length) {
    if (message) message.textContent = "Please choose at least one image";
    return;
  }
  if (button) button.disabled = true;

  try {
    const formData = new FormData(form);
    formData.set("ticket_id", ticketId);
    const res = await fetch("/support-tickets-attachments", {
      method: "POST",
      body: formData,
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok || !data.ok) {
      throw new Error(data.message || "Upload failed");
    }
    form.reset();
    syncDetailAttachmentInputState();
    await loadTickets();
    openTicketDetail(ticketId);
  } catch (err) {
    if (message) message.textContent = err.message;
  } finally {
    if (button) button.disabled = false;
  }
}

async function deleteDetailAttachment(ticketId, folder, savedName) {
  const message = document.getElementById("detail-upload-message");
  if (message) message.textContent = "";

  try {
    const res = await fetch("/support-tickets-attachment-delete", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        ticket_id: ticketId,
        folder,
        saved_name: savedName,
      }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok || !data.ok) {
      throw new Error(data.message || "Delete failed");
    }
    await loadTickets();
    openTicketDetail(ticketId);
  } catch (err) {
    if (message) message.textContent = err.message;
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
    syncAttachmentInputState();
    syncDomainRequirement();
    setupServiceModeSelectors(form);
    toggleSupportServiceDetails(form);
    closeModal();
    await loadTickets();
    await loadPaisReport();
  } catch (err) {
    message.textContent = err.message;
  } finally {
    submit.disabled = false;
  }
}

function fieldReportSignatureFieldId(target) {
  return target === "technician"
    ? "field-report-technician-signature-data"
    : "field-report-customer-signature-data";
}

function fieldReportSignatureStatusId(target) {
  return target === "technician"
    ? "field-report-technician-signature-status"
    : "field-report-customer-signature-status";
}

function fieldReportSignatureStatusText(target) {
  const dataValue = document.getElementById(fieldReportSignatureFieldId(target))?.value || "";
  const label = target === "technician" ? "חתימת טכנאי" : "חתימת לקוח";
  return dataValue ? `${label} נוספה` : `לא נוספה ${label}`;
}

function syncFieldReportSignatureStatuses() {
  ["customer", "technician"].forEach((target) => {
    const status = document.getElementById(fieldReportSignatureStatusId(target));
    const hasValue = Boolean(document.getElementById(fieldReportSignatureFieldId(target))?.value);
    if (!status) return;
    status.textContent = fieldReportSignatureStatusText(target);
    status.classList.toggle("ready", hasValue);
  });
}

function setFieldReportMessage(text, kind = "") {
  const message = document.getElementById("field-report-message");
  if (!message) return;
  message.textContent = text || "";
  message.classList.remove("success", "error");
  if (kind) {
    message.classList.add(kind);
  }
}

function setFieldReportLoading(isLoading) {
  const form = document.getElementById("field-report-form");
  const overlay = document.getElementById("field-report-loading");
  const button = document.getElementById("field-report-save-btn");
  if (form) {
    form.classList.toggle("is-loading", Boolean(isLoading));
  }
  if (overlay) {
    overlay.hidden = !isLoading;
  }
  if (button) {
    button.disabled = Boolean(isLoading);
    if (!button.dataset.defaultHtml) {
      button.dataset.defaultHtml = button.innerHTML;
    }
    button.innerHTML = isLoading
      ? '<i class="fa-solid fa-spinner fa-spin"></i><span>שומר ושולח...</span>'
      : button.dataset.defaultHtml;
  }
}

function signatureCanvasContext() {
  const canvas = document.getElementById("signature-canvas");
  if (!canvas) return { canvas: null, ctx: null };
  return { canvas, ctx: canvas.getContext("2d") };
}

function resizeSignatureCanvas() {
  const { canvas, ctx } = signatureCanvasContext();
  if (!canvas || !ctx) return;
  const ratio = window.devicePixelRatio || 1;
  const rect = canvas.getBoundingClientRect();
  const cssWidth = Math.max(Math.round(rect.width), 320);
  const cssHeight = Math.max(Math.round(rect.height), 220);
  canvas.width = Math.round(cssWidth * ratio);
  canvas.height = Math.round(cssHeight * ratio);
  ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
  ctx.lineCap = "round";
  ctx.lineJoin = "round";
  ctx.lineWidth = 2.2;
  ctx.strokeStyle = "#1f2f46";
  ctx.fillStyle = "#ffffff";
  ctx.fillRect(0, 0, cssWidth, cssHeight);
  signaturePadDirty = false;
}

function clearSignatureCanvas() {
  resizeSignatureCanvas();
}

function openSignatureModal() {
  const modal = document.getElementById("signature-modal");
  const title = document.getElementById("signature-modal-title");
  const kicker = document.getElementById("signature-modal-kicker");
  if (title) {
    title.textContent = activeFieldReportSignatureTarget === "technician" ? "חתימת טכנאי" : "חתימת לקוח";
  }
  if (kicker) {
    kicker.textContent = activeFieldReportSignatureTarget === "technician" ? "Technician Signature" : "Customer Signature";
  }
  modal?.classList.add("open");
  modal?.setAttribute("aria-hidden", "false");
  window.setTimeout(clearSignatureCanvas, 0);
}

function closeSignatureModal() {
  const modal = document.getElementById("signature-modal");
  modal?.classList.remove("open");
  modal?.setAttribute("aria-hidden", "true");
}

function saveSignatureToFieldReport() {
  const { canvas } = signatureCanvasContext();
  if (!canvas || !signaturePadDirty) {
    openNotificationErrorModal("יש להוסיף חתימה לפני שמירה");
    return;
  }
  const dataField = document.getElementById(fieldReportSignatureFieldId(activeFieldReportSignatureTarget));
  if (dataField) {
    dataField.value = canvas.toDataURL("image/png");
  }
  syncFieldReportSignatureStatuses();
  closeSignatureModal();
}

function bindSignaturePad() {
  const { canvas, ctx } = signatureCanvasContext();
  if (!canvas || !ctx || canvas.dataset.bound === "true") return;
  let drawing = false;
  const pointForEvent = (event) => {
    const rect = canvas.getBoundingClientRect();
    const source = event.touches?.[0] || event.changedTouches?.[0] || event;
    return {
      x: source.clientX - rect.left,
      y: source.clientY - rect.top,
    };
  };
  const startStroke = (event) => {
    event.preventDefault();
    const point = pointForEvent(event);
    drawing = true;
    ctx.beginPath();
    ctx.moveTo(point.x, point.y);
  };
  const moveStroke = (event) => {
    if (!drawing) return;
    event.preventDefault();
    const point = pointForEvent(event);
    ctx.lineTo(point.x, point.y);
    ctx.stroke();
    signaturePadDirty = true;
  };
  const endStroke = (event) => {
    if (!drawing) return;
    event.preventDefault();
    drawing = false;
  };
  canvas.addEventListener("pointerdown", startStroke);
  canvas.addEventListener("pointermove", moveStroke);
  canvas.addEventListener("pointerup", endStroke);
  canvas.addEventListener("pointerleave", endStroke);
  canvas.dataset.bound = "true";
}

function openFieldReportModal(ticketId) {
  const ticket = getTicket(ticketId);
  if (!ticket) return;
  const report = ticketDetails(ticket).field_report || {};
  const details = ticketDetails(ticket);
  const contactPhone = extractPhoneNumber(details.on_site_contact || details.technical_contact || "");
  const nameParts = splitContactName(report.contact_first_name || report.contact_last_name
    ? `${report.contact_first_name || ""} ${report.contact_last_name || ""}`.trim()
    : (details.on_site_contact || ""));
  const itemRows = normalizeFieldReportLineItems(report.line_items);
  document.getElementById("field-report-ticket-id").value = ticket.id;
  document.getElementById("field-report-ticket-label").textContent = ticket.ticket_id || `#${String(ticket.id).padStart(4, "0")}`;
  document.getElementById("field-report-call-number-label").textContent = `מספר קריאה: ${details.call_number || "-"}`;
  document.getElementById("field-report-nimbus-customer-name").value = report.nimbus_customer_name || details.customer_name || details.call_number || "";
  document.getElementById("field-report-contact-first-name").value = report.contact_first_name || nameParts.firstName || "";
  document.getElementById("field-report-contact-last-name").value = report.contact_last_name || nameParts.lastName || "";
  document.getElementById("field-report-role").value = report.role || "";
  document.getElementById("field-report-installation-address").value = report.installation_address || details.address || "";
  document.getElementById("field-report-phone").value = report.phone || contactPhone || "";
  document.getElementById("field-report-customer-notes").value = report.customer_notes || "";
  document.getElementById("field-report-additional-notes").value = report.additional_notes || "";
  document.getElementById("field-report-installation-date").value = report.installation_date || todayIsraelDate();
  document.getElementById("field-report-technician-name").value = report.technician_name || technicianDisplayName();
  document.getElementById("field-report-technician-signature-data").value = report.technician_signature_data_url || "";
  document.getElementById("field-report-customer-signature-data").value = report.customer_signature_data_url || "";
  document.getElementById("field-report-area-photos").value = "";
  renderFieldReportLineItemRows(itemRows);
  renderFieldReportPhotoList(report.area_photo_attachments || [], "field-report-existing-photos", "עדיין לא נוספו צילומים");
  renderFieldReportPhotoList([], "field-report-pending-photos", "לא נבחרו קבצים חדשים");
  setFieldReportMessage("", "");
  setFieldReportLoading(false);
  setFieldReportItemsExpanded(lineItemsHasData(itemRows));
  syncFieldReportSignatureStatuses();
  document.getElementById("field-report-modal")?.classList.add("open");
  document.getElementById("field-report-modal")?.setAttribute("aria-hidden", "false");
}

function closeFieldReportModal() {
  setFieldReportLoading(false);
  document.getElementById("field-report-modal")?.classList.remove("open");
  document.getElementById("field-report-modal")?.setAttribute("aria-hidden", "true");
}

async function submitFieldReport(event) {
  event.preventDefault();
  setFieldReportMessage("", "");
  setFieldReportLoading(true);

  const lineItems = collectFieldReportLineItems()
    .filter((row) => Object.values(row).some((value) => String(value || "").trim()));

  const payload = {
    ticket_id: document.getElementById("field-report-ticket-id")?.value || "",
    nimbus_customer_name: document.getElementById("field-report-nimbus-customer-name")?.value || "",
    contact_first_name: document.getElementById("field-report-contact-first-name")?.value || "",
    contact_last_name: document.getElementById("field-report-contact-last-name")?.value || "",
    role: document.getElementById("field-report-role")?.value || "",
    installation_address: document.getElementById("field-report-installation-address")?.value || "",
    phone: document.getElementById("field-report-phone")?.value || "",
    customer_notes: document.getElementById("field-report-customer-notes")?.value || "",
    additional_notes: document.getElementById("field-report-additional-notes")?.value || "",
    line_items: lineItems,
    installation_date: document.getElementById("field-report-installation-date")?.value || "",
    technician_name: document.getElementById("field-report-technician-name")?.value || "",
    technician_signature_data_url: document.getElementById("field-report-technician-signature-data")?.value || "",
    customer_signature_data_url: document.getElementById("field-report-customer-signature-data")?.value || "",
  };
  const areaPhotoInput = document.getElementById("field-report-area-photos");
  const selectedPhotos = Array.from(areaPhotoInput?.files || []);

  if (!payload.technician_signature_data_url) {
    setFieldReportMessage("יש להוסיף חתימת טכנאי", "error");
    setFieldReportLoading(false);
    return;
  }
  if (!payload.customer_signature_data_url) {
    setFieldReportMessage("יש להוסיף חתימת לקוח", "error");
    setFieldReportLoading(false);
    return;
  }

  try {
    const formData = new FormData();
    formData.append("payload", JSON.stringify(payload));
    selectedPhotos.forEach((file) => {
      formData.append("area_photos", file);
    });
    const res = await fetch("/support-tickets-field-report", {
      method: "POST",
      body: formData,
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok || !data.ok) {
      throw new Error(data.message || "Save failed");
    }
    if (data?.ticket?.field_report_error) {
      setFieldReportMessage(`הטופס נשמר, אך שליחת המייל נכשלה: ${data.ticket.field_report_error}`, "error");
      closeSignatureModal();
      closeFieldReportModal();
      closeTicketDetail();
      await loadTickets();
      openNotificationErrorModal(`הטופס נשמר, אך שליחת המייל נכשלה: ${data.ticket.field_report_error}`);
    } else {
      showSendSuccessToast();
      closeSignatureModal();
      closeFieldReportModal();
      closeTicketDetail();
      await loadTickets();
    }
  } catch (err) {
    setFieldReportMessage(err.message || "Save failed", "error");
  } finally {
    setFieldReportLoading(false);
  }
}

function displayTicketStatus(ticket) {
  const normalizedStatus = normalizePendingStatus(ticket?.status);
  if (pageMode === "nastia" && isCoordinationTicket(ticket) && normalizedStatus === "ממתין לתיאום") {
    return "ממתין";
  }
  return normalizedStatus || "";
}

function statusOptionsForTicket(ticket) {
  const normalizedStatus = normalizePendingStatus(ticket.status);
  if (canAssignedTechnicianEditTicket(ticket)) {
    const normalizedStatus = normalizePendingStatus(ticket.status);
    const placeholder = NASTYA_FINAL_STATUSES.includes(normalizedStatus)
      ? ""
      : '<option value="" selected disabled>בחר סטטוס</option>';
    return `${placeholder}${NASTYA_FINAL_STATUSES.map((status) => `
      <option value="${escapeHtml(status)}" ${normalizedStatus === status ? "selected" : ""}>${escapeHtml(status)}</option>
    `).join("")}`;
  }
  if (isCoordinationTicket(ticket) && isNastyaQueuePage && NASTYA_EDITABLE_STATUSES.includes(normalizedStatus)) {
    const options = [
      { value: normalizedStatus, label: displayTicketStatus(ticket) },
      ...NASTYA_FINAL_STATUSES
        .filter((status) => status !== normalizedStatus)
        .map((status) => ({ value: status, label: status })),
    ];
    return options.map(({ value, label }) => `
      <option value="${escapeHtml(value)}" ${normalizedStatus === value ? "selected" : ""}>${escapeHtml(label)}</option>
    `).join("");
  }
  const options = isCoordinationTicket(ticket) ? paisStatuses : supportStatuses;
  return options.map((status) => `
    <option value="${escapeHtml(status)}" ${normalizedStatus === status ? "selected" : ""}>${escapeHtml(status)}</option>
  `).join("");
}

function canNastyaEditPaisInlineStatus(ticket) {
  return isCoordinationTicket(ticket) && isNastyaQueuePage && NASTYA_EDITABLE_STATUSES.includes(normalizePendingStatus(ticket.status));
}

function ticketHeadline(ticket) {
  const details = ticketDetails(ticket);
  if (isPaisTicket(ticket)) {
    const terminal = details.terminal_number ? `מסוף ${details.terminal_number}` : (boardDisplayName(ticket.board_slug) || boardName);
    const address = details.address ? ` / ${details.address}` : "";
    return `${terminal}${address}`;
  }
  if (isHotTicket(ticket)) {
    const callNumber = details.call_number ? `פניה ${details.call_number}` : (boardDisplayName(ticket.board_slug) || boardName);
    const customerName = details.customer_name ? ` / ${details.customer_name}` : "";
    const address = details.address ? ` / ${details.address}` : "";
    return `${callNumber}${customerName}${address}`;
  }
  return `${ticket.service_type || "General"}${ticket.domain ? ` / ${ticket.domain}` : ""}`;
}

function ticketSnippet(ticket) {
  const details = ticketDetails(ticket);
  if (isPaisTicket(ticket)) {
    const parts = [details.customer_request || details.actions_taken || ""];
    if (ticket.assigned_to) parts.push(`נציג: ${ticket.assigned_to}`);
    if (details.coordinated_worker) parts.push(`תואם: ${details.coordinated_worker}`);
    if (details.visit_date) {
      const hourRange = [details.visit_hour_from, details.visit_hour_to].filter(Boolean).join(" - ");
      parts.push(`ביקור: ${details.visit_date}${hourRange ? ` ${hourRange}` : ""}`);
    }
    return parts.filter(Boolean).join(" | ");
  }
  if (isHotTicket(ticket)) {
    const parts = [details.issue_summary || details.technician_actions || ""];
    if (ticket.assigned_to) parts.push(`נציג: ${ticket.assigned_to}`);
    if (details.coordinated_worker) parts.push(`תואם: ${details.coordinated_worker}`);
    if (details.visit_date) {
      const hourRange = [details.visit_hour_from, details.visit_hour_to].filter(Boolean).join(" - ");
      parts.push(`ביקור: ${details.visit_date}${hourRange ? ` ${hourRange}` : ""}`);
    }
    return parts.filter(Boolean).join(" | ");
  }
  if (ticket.board_slug === "support") {
    const parts = [ticket.description || ""];
    if (details.customer_type) parts.push(`סוג לקוח: ${details.customer_type}`);
    if (details.service_mode) parts.push(`סוג טיפול: ${details.service_mode}`);
    if (details.service_contact) parts.push(`איש קשר: ${details.service_contact}`);
    if (details.coordinated_worker) parts.push(`תואם: ${details.coordinated_worker}`);
    if (details.visit_date) {
      const hourRange = [details.visit_hour_from, details.visit_hour_to].filter(Boolean).join(" - ");
      parts.push(`ביקור: ${details.visit_date}${hourRange ? ` ${hourRange}` : ""}`);
    }
    return parts.filter(Boolean).join(" | ");
  }
  return ticket.description || "";
}

function ticketTypeLabel(ticket) {
  if (isCoordinationTicket(ticket)) {
    return boardDisplayName(ticket.board_slug) || ticket.service_type || "";
  }
  return ticket.ticket_type || "";
}

function ticketCopyText(ticket) {
  const details = ticketDetails(ticket);
  const lines = [];

  pushCopyLine(lines, "Ticket", ticket.ticket_id || `#${String(ticket.id || "").padStart(4, "0")}`);
  pushCopyLine(lines, "Board", isCoordinationTicket(ticket) ? (boardDisplayName(ticket.board_slug) || ticket.service_type || "") : "נימבוס");
  if (!isCoordinationTicket(ticket)) {
    pushCopyLine(lines, "Ticket Type", ticket.ticket_type);
    pushCopyLine(lines, "Service Type", ticket.service_type);
    pushCopyLine(lines, "Domain", ticket.domain);
  }
  pushCopyLine(lines, "Status", displayTicketStatus(ticket));
  pushCopyLine(lines, "Priority", ticket.priority || "Medium");
  pushCopyLine(lines, "Assigned To", ticket.assigned_to || "Unassigned");
  pushCopyLine(lines, "Creator", ticket.creator);
  pushCopyLine(lines, "Created", ticket.created_at_display);
  pushCopyLine(lines, "Last Edited", ticket.last_edited_at_display);
  pushCopyLine(lines, "Internal ID", ticket.id);
  lines.push("");
  lines.push("Details");

  if (isPaisTicket(ticket)) {
    pushCopyLine(lines, "Terminal Number", details.terminal_number);
    pushCopyLine(lines, "Address", details.address);
    pushCopyLine(lines, "Static IP", details.static_ip);
    pushCopyLine(lines, "Altura", details.altura);
    pushCopyLine(lines, "Loop Back", details.look_back);
    pushCopyLine(lines, "Contact Name", details.contact_name);
    pushCopyLine(lines, "Contact Phone", details.contact_phone);
    pushCopyLine(lines, "Customer Request", details.customer_request);
    pushCopyLine(lines, "Actions Taken", details.actions_taken);
    pushCopyLine(lines, "Coordinated Worker", details.coordinated_worker);
    pushCopyLine(lines, "Visit Date", details.visit_date);
    pushCopyLine(lines, "Visit Hours", [details.visit_hour_from, details.visit_hour_to].filter(Boolean).join(" - "));
    pushCopyLine(lines, "Failure Notes", details.failure_notes);
  } else if (isHotTicket(ticket)) {
    pushCopyLine(lines, "Opened At", details.opened_at);
    pushCopyLine(lines, "Call Number", details.call_number);
    pushCopyLine(lines, "Opened By", details.opened_by);
    pushCopyLine(lines, "Customer ID", details.customer_id);
    pushCopyLine(lines, "Customer Name", details.customer_name);
    pushCopyLine(lines, "Line Code", details.line_code);
    pushCopyLine(lines, "Address", details.address);
    pushCopyLine(lines, "On-site Contact", details.on_site_contact);
    pushCopyLine(lines, "Technical Contact", details.technical_contact);
    pushCopyLine(lines, "Availability", details.availability_hours);
    pushCopyLine(lines, "Remote Checks", details.remote_checks);
    pushCopyLine(lines, "Issue Summary", details.issue_summary);
    pushCopyLine(lines, "Technician Actions", details.technician_actions);
    pushCopyLine(lines, "Equipment Type", details.equipment_type);
    pushCopyLine(lines, "Service Agreement", details.service_agreement);
    pushCopyLine(lines, "Technical Notes", details.technical_notes);
    pushCopyLine(lines, "Coordinated Worker", details.coordinated_worker);
    pushCopyLine(lines, "Visit Date", details.visit_date);
    pushCopyLine(lines, "Visit Hours", [details.visit_hour_from, details.visit_hour_to].filter(Boolean).join(" - "));
    pushCopyLine(lines, "Failure Notes", details.failure_notes);
  } else if (ticket.board_slug === "support") {
    pushCopyLine(lines, "Description", ticket.description);
    pushCopyLine(lines, "Solution", ticket.solution);
    pushCopyLine(lines, "Customer Type", details.customer_type);
    pushCopyLine(lines, "Service Mode", details.service_mode);
    pushCopyLine(lines, "Business Name", details.business_name);
    pushCopyLine(lines, "Service Contact", details.service_contact);
    pushCopyLine(lines, "Service Address", details.service_address);
    pushCopyLine(lines, "Coordinated Worker", details.coordinated_worker);
    pushCopyLine(lines, "Visit Date", details.visit_date);
    pushCopyLine(lines, "Visit Hours", [details.visit_hour_from, details.visit_hour_to].filter(Boolean).join(" - "));
    pushCopyLine(lines, "Failure Notes", details.failure_notes);
  } else {
    pushCopyLine(lines, "Description", ticket.description);
    pushCopyLine(lines, "Solution", ticket.solution);
  }

  const attachments = Array.isArray(ticket.attachments) ? ticket.attachments : [];
  lines.push("");
  lines.push("Attachments");
  if (attachments.length === 0) {
    lines.push("None");
  } else {
    attachments.forEach((file, index) => {
      const label = file?.original_name || file?.saved_name || `Image ${index + 1}`;
      const url = String(file?.url || "").trim();
      lines.push(`${index + 1}. ${label}${url ? ` - ${url}` : ""}`);
    });
  }

  return lines.join("\n");
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
    row.className = `ticket-row ${isCoordinationTicket(ticket) ? "pais-row" : ""}`;
    row.dataset.ticketId = ticket.id;
    const technicianCanUpdate = canAssignedTechnicianEditTicket(ticket);
    const assigneeOptions = ['<option value="">Unassigned</option>']
      .concat((users || []).map((user) => `<option value="${escapeHtml(user)}" ${ticket.assigned_to === user ? "selected" : ""}>${escapeHtml(user)}</option>`))
      .join("");
    const firstAttachment = Array.isArray(ticket.attachments) ? ticket.attachments[0] : null;
    const attachmentCount = Array.isArray(ticket.attachments) ? ticket.attachments.length : 0;
    const statusClass = statusClassName(ticket.status);
    const coordinationMarkup = coordinationMetaMarkup(ticket);

    row.innerHTML = `
      <div class="ticket-id">${escapeHtml(ticket.ticket_id)}</div>
      <div class="ticket-main">
        <h3>${escapeHtml(ticketHeadline(ticket))}</h3>
        <p>${escapeHtml(ticketSnippet(ticket))}</p>
      </div>
      <div class="ticket-extra">
        ${firstAttachment ? `
          <button
            class="ticket-attachment-indicator"
            type="button"
            data-image-url="${escapeHtml(firstAttachment.url)}"
            title="${attachmentCount > 1 ? `${attachmentCount} files attached` : "1 file attached"}"
            aria-label="${attachmentCount > 1 ? `${attachmentCount} files attached` : "1 file attached"}"
          >
            <i class="fa-solid fa-paperclip"></i>
            <span>${escapeHtml(attachmentCount)}</span>
          </button>
        ` : ""}
      </div>
      <div class="ticket-meta">
        <strong>${escapeHtml(ticketTypeLabel(ticket))}</strong><br>
        ${escapeHtml(ticket.creator)}<br>${escapeHtml(ticketListTimestamp(ticket))}
        ${coordinationMarkup || ""}
      </div>
      <select class="assignee-select" data-ticket-id="${ticket.id}" ${(isAssignedTechnicianMode || (isNastyaQueuePage && isCoordinationTicket(ticket))) ? "disabled" : ""}>${assigneeOptions}</select>
      <select class="status-select" data-ticket-id="${ticket.id}" ${((isAssignedTechnicianMode && !technicianCanUpdate) || (isNastyaQueuePage && isCoordinationTicket(ticket) && !canNastyaEditPaisInlineStatus(ticket))) ? "disabled" : ""}>${statusOptionsForTicket(ticket)}</select>
      <div class="ticket-actions">
        <span class="pill ${statusClass}">${escapeHtml(displayTicketStatus(ticket))}</span>
        <span class="pill ${priorityClass(ticket.priority || "Medium")}">${escapeHtml(ticket.priority || "Medium")}</span>
        <button class="copy-ticket-btn" type="button" data-ticket-id="${ticket.id}" title="Copy ticket details" aria-label="Copy ticket details"><i class="fa-regular fa-copy"></i></button>
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
  document.querySelectorAll(".ticket-attachment-indicator").forEach((button) => {
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
  document.querySelectorAll(".copy-ticket-btn").forEach((button) => {
    button.addEventListener("click", async (event) => {
      event.stopPropagation();
      await copyTicketDetails(button.dataset.ticketId, button);
    });
  });
}

function coordinationStatusEditor(ticket) {
  if (canAssignedTechnicianEditTicket(ticket)) {
    return `
    <section class="detail-description detail-edit-card">
      <h3>סטטוס</h3>
      <select id="detail-status-select">
        ${statusOptionsForTicket(ticket)}
      </select>
    </section>`;
  }
  const isCoordinatorView = isNastyaQueuePage;
  const showCoordinatorStatus = isCoordinatorView && NASTYA_EDITABLE_STATUSES.includes(ticket.status);
  const coordinatorStatusOptions = [
    { value: ticket.status, label: displayTicketStatus(ticket) },
    ...NASTYA_FINAL_STATUSES
      .filter((status) => status !== ticket.status)
      .map((status) => ({ value: status, label: status })),
  ]
    .map(({ value, label }) => `<option value="${escapeHtml(value)}" ${ticket.status === value ? "selected" : ""}>${escapeHtml(label)}</option>`)
    .join("");

  if (showCoordinatorStatus) {
    return `
    <section class="detail-description detail-edit-card">
      <h3>סטטוס</h3>
      <select id="detail-status-select">
        ${coordinatorStatusOptions}
      </select>
    </section>`;
  }
  if (!isCoordinatorView) {
    return `
    <section class="detail-description detail-edit-card">
      <h3>סטטוס</h3>
      <select id="detail-status-select">
        ${paisStatuses.map((status) => `<option value="${escapeHtml(status)}" ${ticket.status === status ? "selected" : ""}>${escapeHtml(status)}</option>`).join("")}
      </select>
    </section>`;
  }
  return "";
}

function coordinationSchedulingEditor(ticket, details) {
  if (isAssignedTechnicianMode) return "";
  const isCoordinatorView = isNastyaQueuePage;
  const technicianOptions = ['<option value="">בחר עובד</option>']
    .concat(technicianUsers.map((user) => `<option value="${escapeHtml(user)}" ${details.coordinated_worker === user ? "selected" : ""}>${escapeHtml(user)}</option>`))
    .join("");
  const showCoordination = isCoordinatorView || normalizePendingStatus(ticket.status) === "ממתין לתיאום" || Boolean(details.coordinated_worker || details.visit_date || details.visit_hour_from || details.visit_hour_to);
  if (!showCoordination) return "";
  return `
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
      <p class="detail-hint">חלונות התיאום הם של שעה אחת, החל מ-09:00.</p>
      ${coordinationCancelButton(ticket, details)}
    </section>`;
}

function renderHotDetailSections(ticket) {
  const details = ticketDetails(ticket);
  const technicianMode = canAssignedTechnicianEditTicket(ticket);
  const showFailureNotes = ticket.status === "נכשל";
  if (technicianMode) {
    return `
      ${detailSection("מהות התקלה", details.issue_summary)}
      ${detailSection("בדיקות שבוצעו מרחוק", details.remote_checks)}
      ${detailSection("פעולות / בדיקות שטכנאי צריך לבצע", details.technician_actions)}
      ${details.equipment_type ? detailSection("סוג ציוד קיים אצל הלקוח", details.equipment_type) : ""}
      ${details.service_agreement ? detailSection("הסכם שירות ואיזה ציוד באחריות הוט", details.service_agreement) : ""}
      ${details.technical_notes ? detailSection("פרטים טכניים נוספים", details.technical_notes) : ""}
      ${fieldReportSummaryCard(ticket, true) || `
      <section class="detail-description detail-edit-card">
        <h3>דוח החתמת לקוח</h3>
        <div class="field-report-actions">
          <button class="create-ticket-btn open-field-report-btn" type="button" data-ticket-id="${escapeHtml(ticket.id)}">
            <i class="fa-solid fa-file-signature"></i><span>החתמת לקוח</span>
          </button>
        </div>
      </section>`}
      ${coordinationStatusEditor(ticket)}
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
  return `
    ${detailSection("מהות התקלה", details.issue_summary)}
    ${detailSection("בדיקות שבוצעו מרחוק", details.remote_checks)}
    <section class="detail-description detail-edit-card">
      <h3>פעולות / בדיקות שטכנאי צריך לבצע</h3>
      <textarea id="detail-technician-actions" rows="4">${escapeHtml(details.technician_actions || "")}</textarea>
    </section>
    ${details.equipment_type ? detailSection("סוג ציוד קיים אצל הלקוח", details.equipment_type) : ""}
    ${details.service_agreement ? detailSection("הסכם שירות ואיזה ציוד באחריות הוט", details.service_agreement) : ""}
    ${details.technical_notes ? detailSection("פרטים טכניים נוספים", details.technical_notes) : ""}
    ${details.field_report ? fieldReportSummaryCard(ticket, false) : ""}
    ${coordinationStatusEditor(ticket)}
    ${coordinationSchedulingEditor(ticket, details)}
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

function supportServiceModeEditor(details) {
  const currentCustomerType = String(details.customer_type || "");
  const currentMode = String(details.service_mode || "");
  const customerTypes = ["לקוח נימבוס", "לקוח הוט"];
  const options = ["ביקור טכנאי בתשלום", "ביקור ללא תשלום", "משלוח"];
  return `
    <section class="detail-description detail-edit-card service-mode-card">
      <h3>סוג לקוח</h3>
      <div class="choice-pill-selector customer-type-selector">
        ${customerTypes.map((option) => `
          <label class="choice-pill">
            <input type="radio" name="customer_type" value="${escapeHtml(option)}" ${currentCustomerType === option ? "checked" : ""}>
            <span>${escapeHtml(option)}</span>
          </label>
        `).join("")}
      </div>
      <h3>סוג טיפול</h3>
      <div class="service-mode-selector" data-placeholder="בחר סוג טיפול">
        <input type="hidden" name="service_mode" value="${escapeHtml(currentMode)}">
        <button class="service-mode-toggle-btn servoption-ticket-menu-toggle" type="button" data-role="toggle" aria-expanded="false">
          <span data-role="label">${escapeHtml(currentMode || "בחר סוג טיפול")}</span>
          <i class="fa-solid fa-chevron-down"></i>
        </button>
        <div class="add-ticket-menu service-option-menu" data-role="menu">
        ${options.map((option) => `
          <button class="menu-item ${currentMode === option ? "active" : ""}" type="button" data-service-mode="${escapeHtml(option)}">${escapeHtml(option)}</button>
        `).join("")}
        </div>
      </div>
    </section>
    <div class="detail-form-grid support-service-details" id="support-service-details" ${currentMode ? "" : "hidden"}>
      <label>
        <span>שם העסק</span>
        <input id="detail-business-name" type="text" value="${escapeHtml(details.business_name || "")}">
      </label>
      <label>
        <span>איש קשר</span>
        <input id="detail-service-contact" type="text" value="${escapeHtml(details.service_contact || "")}">
      </label>
      <label>
        <span>כתובת</span>
        <input id="detail-service-address" type="text" value="${escapeHtml(details.service_address || "")}">
      </label>
    </div>
  `;
}

function renderSupportDetailSections(ticket) {
  const details = ticketDetails(ticket);
  const technicianMode = canAssignedTechnicianEditTicket(ticket);
  const showFailureNotes = normalizePendingStatus(ticket.status) === "נכשל";
  if (technicianMode) {
    return `
      ${detailSection("תיאור", ticket.description)}
      ${detailSection("פתרון", ticket.solution)}
      ${details.customer_type ? detailSection("סוג לקוח", details.customer_type) : ""}
      ${details.service_mode ? detailSection("סוג טיפול", details.service_mode) : ""}
      ${details.business_name ? detailSection("שם העסק", details.business_name) : ""}
      ${details.service_contact ? detailSectionHtml("איש קשר", renderContactWithPhone(details.service_contact)) : ""}
      ${details.service_address ? detailSectionHtml("כתובת", renderAddressValue(details.service_address)) : ""}
      ${coordinationStatusEditor(ticket)}
      <section class="detail-description detail-edit-card ${showFailureNotes ? "" : "hidden"}" id="detail-failure-notes-wrap">
        <h3>למה קריאה נכשלה</h3>
        <textarea id="detail-failure-notes" rows="4">${escapeHtml(details.failure_notes || "")}</textarea>
      </section>
      <div class="detail-save-row">
        <span id="detail-save-message"></span>
        <button class="create-ticket-btn" id="detail-save-btn" type="button">שמור</button>
      </div>
    `;
  }
  return `
    <section class="detail-description detail-edit-card">
      <h3>תיאור</h3>
      <textarea id="detail-support-description" rows="4">${escapeHtml(ticket.description || "")}</textarea>
    </section>
    <section class="detail-description detail-edit-card">
      <h3>פתרון</h3>
      <textarea id="detail-support-solution" rows="4">${escapeHtml(ticket.solution || "")}</textarea>
    </section>
    ${supportServiceModeEditor(details)}
    ${coordinationStatusEditor(ticket)}
    ${coordinationSchedulingEditor(ticket, details)}
    <section class="detail-description detail-edit-card ${showFailureNotes ? "" : "hidden"}" id="detail-failure-notes-wrap">
      <h3>למה קריאה נכשלה</h3>
      <textarea id="detail-failure-notes" rows="4">${escapeHtml(details.failure_notes || "")}</textarea>
    </section>
    <div class="detail-save-row">
      <span id="detail-save-message"></span>
      <button class="create-ticket-btn" id="detail-save-btn" type="button">שמור</button>
    </div>
  `;
}

function renderDetailSections(ticket) {
  if (ticket.board_slug === "support") {
    return renderSupportDetailSections(ticket);
  }
  if (isPaisTicket(ticket)) {
    return renderPaisDetailSections(ticket);
  }
  if (isHotTicket(ticket)) {
    return renderHotDetailSections(ticket);
  }
  return [
    detailSection("Description", ticket.description),
    detailSection("Solution", ticket.solution),
  ].join("");
}

function setDetailSaveMessageState(message, text = "", kind = "") {
  if (!message) return;
  message.textContent = text || "";
  message.classList.remove("saving", "success", "error");
  if (kind) {
    message.classList.add(kind);
  }
}

function waitForUi(ms) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

async function savePaisDetail(ticketId) {
  const currentTicket = getTicket(ticketId);
  const currentDetails = ticketDetails(currentTicket);
  const technicianMode = canAssignedTechnicianEditTicket(currentTicket);
  const coordinatedWorkerField = document.getElementById("detail-coordinated-worker");
  const visitDateField = document.getElementById("detail-visit-date");
  const visitHourFromField = document.getElementById("detail-visit-hour-from");
  const visitHourToField = document.getElementById("detail-visit-hour-to");
  const statusSelect = document.getElementById("detail-status-select");
  const detailFieldName = isHotTicket(currentTicket) ? "technician_actions" : "actions_taken";
  const detailFieldElement = document.getElementById(isHotTicket(currentTicket) ? "detail-technician-actions" : "detail-actions-taken");
  const coordinationPayload = {
    coordinated_worker: coordinatedWorkerField?.value || "",
    visit_date: visitDateField?.value || "",
    visit_hour_from: visitHourFromField?.value || "",
    visit_hour_to: visitHourToField?.value || "",
  };
  const selectedStatus = statusSelect?.value || "";
  const detailSections = document.getElementById("detail-sections");
  const shouldMarkCoordinated = Object.values(coordinationPayload).every(Boolean);
  let nextStatus = selectedStatus;
  if (shouldMarkCoordinated && (!selectedStatus || selectedStatus === "ממתין לתיאום" || selectedStatus === "תואם")) {
    nextStatus = "תואם";
  }
  const isFinalStatus = NASTYA_FINAL_STATUSES.includes(selectedStatus);
  const payload = {
    ticket_id: ticketId,
    source_page_mode: pageMode,
    source_ticket_queue: ticketQueue,
    status: nextStatus,
  };
  if (technicianMode) {
    payload.details = {
      ...(detailFieldName === "actions_taken" ? { actions_taken: detailFieldElement?.value || "" } : {}),
      failure_notes: document.getElementById("detail-failure-notes")?.value || "",
    };
  } else {
    if (currentTicket.board_slug === "support") {
      payload.description = document.getElementById("detail-support-description")?.value || "";
      payload.solution = document.getElementById("detail-support-solution")?.value || "";
    }
    payload.details = {
      ...(currentTicket.board_slug === "support"
        ? {
            service_mode: selectedSupportServiceMode(detailSections || document),
            customer_type: selectedSupportCustomerType(detailSections || document),
            business_name: document.getElementById("detail-business-name")?.value || "",
            service_contact: document.getElementById("detail-service-contact")?.value || "",
            service_address: document.getElementById("detail-service-address")?.value || "",
          }
        : {
            [detailFieldName]: detailFieldElement?.value || "",
          }),
      coordinated_worker: coordinationPayload.coordinated_worker,
      visit_date: coordinationPayload.visit_date,
      visit_hour_from: coordinationPayload.visit_hour_from,
      visit_hour_to: coordinationPayload.visit_hour_to,
      failure_notes: document.getElementById("detail-failure-notes")?.value || "",
    };
  }
  const message = document.getElementById("detail-save-message");
  const button = document.getElementById("detail-save-btn");
  const originalButtonContent = button?.innerHTML || "";
  setDetailSaveMessageState(message, "שומר נתונים...", "saving");
  clearCoordinationValidation();
  if (button) {
    button.disabled = true;
    button.classList.add("is-saving");
    button.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i><span>שומר נתונים...</span>';
  }
  if (technicianMode && selectedStatus === "נכשל" && !String(payload.details.failure_notes || "").trim()) {
    if (message) message.textContent = "יש למלא סיבת כשל";
    if (button) button.disabled = false;
    return;
  }
  if (technicianMode && !selectedStatus) {
    if (message) message.textContent = "יש לבחור סטטוס";
    if (button) button.disabled = false;
    return;
  }

  if (currentTicket.board_slug === "support" && payload.details.service_mode && !technicianMode) {
    if (!payload.details.business_name || !payload.details.service_contact || !payload.details.service_address) {
      if (message) message.textContent = "יש למלא שם העסק, איש קשר וכתובת";
      if (button) button.disabled = false;
      return;
    }
  }

  if (isNastyaQueuePage && !technicianMode && !isFinalStatus) {
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

  const coordinationChanged = ["coordinated_worker", "visit_date", "visit_hour_from", "visit_hour_to"]
    .some((fieldName) => String(currentDetails?.[fieldName] || "") !== String(coordinationPayload[fieldName] || ""));
  if (isNastyaQueuePage && !technicianMode && shouldMarkCoordinated && coordinationChanged) {
    payload.send_nastia_notification = true;
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
    if (data?.ticket?.notification_error) {
      openNotificationErrorModal(`הסטטוס עודכן אבל שליחת המייל נכשלה: ${data.ticket.notification_error}`);
    } else if (data?.ticket?.notification_sent === true) {
      showSendSuccessToast();
    } else if (payload.send_nastia_notification === true) {
      openNotificationErrorModal("הסטטוס עודכן אבל טריגר המייל לא הופעל.");
    }
    closeTicketDetail();
    await loadTickets();
    await loadPaisReport();
  } catch (err) {
    openNotificationErrorModal(err.message || "Save failed");
    if (message) message.textContent = err.message;
  } finally {
    if (button) button.disabled = false;
  }
}

function hasCoordinationDetails(details) {
  return ["coordinated_worker", "visit_date", "visit_hour_from", "visit_hour_to"]
    .some((fieldName) => Boolean(String(details?.[fieldName] || "").trim()));
}

function coordinationCancelButton(ticket, details) {
  if (isAssignedTechnicianMode || !isNastyaQueuePage || !hasCoordinationDetails(details)) {
    return "";
  }
  return `
    <div class="detail-save-row coordination-card-actions">
      <span></span>
      <button class="secondary-btn coordination-cancel-btn" id="detail-cancel-coordination-btn" type="button" data-ticket-id="${escapeHtml(ticket.id)}">בטל ביקור</button>
    </div>
  `;
}

async function cancelTicketCoordination(ticketId) {
  const currentTicket = getTicket(ticketId);
  if (!currentTicket) return;
  const currentDetails = ticketDetails(currentTicket);
  const message = document.getElementById("detail-save-message");
  if (!hasCoordinationDetails(currentDetails)) {
    setDetailSaveMessageState(message, "אין ביקור מתואם לבטל", "error");
    return;
  }

  const coordinatedWorkerField = document.getElementById("detail-coordinated-worker");
  const visitDateField = document.getElementById("detail-visit-date");
  const visitHourFromField = document.getElementById("detail-visit-hour-from");
  const visitHourToField = document.getElementById("detail-visit-hour-to");
  if (coordinatedWorkerField) coordinatedWorkerField.value = "";
  if (visitDateField) visitDateField.value = "";
  if (visitHourFromField) visitHourFromField.value = "";
  if (visitHourToField) visitHourToField.value = "";
  clearCoordinationValidation();

  await saveTicketDetailWithFeedback(ticketId, { cancelCoordination: true });
}

async function saveTicketDetailWithFeedback(ticketId, options = {}) {
  const currentTicket = getTicket(ticketId);
  if (!currentTicket) return;

  const cancelCoordination = Boolean(options.cancelCoordination);
  const currentDetails = ticketDetails(currentTicket);
  const technicianMode = canAssignedTechnicianEditTicket(currentTicket);
  const coordinatedWorkerField = document.getElementById("detail-coordinated-worker");
  const visitDateField = document.getElementById("detail-visit-date");
  const visitHourFromField = document.getElementById("detail-visit-hour-from");
  const visitHourToField = document.getElementById("detail-visit-hour-to");
  const statusSelect = document.getElementById("detail-status-select");
  const detailFieldName = isHotTicket(currentTicket) ? "technician_actions" : "actions_taken";
  const detailFieldElement = document.getElementById(isHotTicket(currentTicket) ? "detail-technician-actions" : "detail-actions-taken");
  const detailSections = document.getElementById("detail-sections");
  const message = document.getElementById("detail-save-message");
  const button = document.getElementById("detail-save-btn");
  const cancelButton = document.getElementById("detail-cancel-coordination-btn");
  const originalButtonContent = button?.innerHTML || "";
  const coordinationPayload = {
    coordinated_worker: coordinatedWorkerField?.value || "",
    visit_date: visitDateField?.value || "",
    visit_hour_from: visitHourFromField?.value || "",
    visit_hour_to: visitHourToField?.value || "",
  };
  const selectedStatus = statusSelect?.value || "";
  const shouldMarkCoordinated = Object.values(coordinationPayload).every(Boolean);
  let nextStatus = cancelCoordination ? "ממתין לתיאום" : selectedStatus;
  if (!cancelCoordination && shouldMarkCoordinated && (!selectedStatus || selectedStatus === "ממתין לתיאום" || selectedStatus === "תואם")) {
    nextStatus = "תואם";
  }
  const isFinalStatus = NASTYA_FINAL_STATUSES.includes(selectedStatus);
  const payload = {
    ticket_id: ticketId,
    source_page_mode: pageMode,
    source_ticket_queue: ticketQueue,
    status: nextStatus,
  };
  const resetSaveButton = () => {
    if (!button) return;
    button.disabled = false;
    button.classList.remove("is-saving");
    button.innerHTML = originalButtonContent;
    if (cancelButton) {
      cancelButton.disabled = false;
    }
  };

  if (technicianMode) {
    payload.details = {
      ...(detailFieldName === "actions_taken" ? { actions_taken: detailFieldElement?.value || "" } : {}),
      failure_notes: document.getElementById("detail-failure-notes")?.value || "",
    };
  } else {
    if (currentTicket.board_slug === "support") {
      payload.description = document.getElementById("detail-support-description")?.value || "";
      payload.solution = document.getElementById("detail-support-solution")?.value || "";
    }
    payload.details = {
      ...(currentTicket.board_slug === "support"
        ? {
            service_mode: selectedSupportServiceMode(detailSections || document),
            customer_type: selectedSupportCustomerType(detailSections || document),
            business_name: document.getElementById("detail-business-name")?.value || "",
            service_contact: document.getElementById("detail-service-contact")?.value || "",
            service_address: document.getElementById("detail-service-address")?.value || "",
          }
        : {
            [detailFieldName]: detailFieldElement?.value || "",
          }),
      coordinated_worker: coordinationPayload.coordinated_worker,
      visit_date: coordinationPayload.visit_date,
      visit_hour_from: coordinationPayload.visit_hour_from,
      visit_hour_to: coordinationPayload.visit_hour_to,
      failure_notes: document.getElementById("detail-failure-notes")?.value || "",
    };
  }

  clearCoordinationValidation();
  setDetailSaveMessageState(message, "שומר נתונים...", "saving");
  if (button) {
    button.disabled = true;
    button.classList.add("is-saving");
    button.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i><span>שומר נתונים...</span>';
  }
  if (cancelButton) {
    cancelButton.disabled = true;
  }

  if (technicianMode && selectedStatus === "נכשל" && !String(payload.details.failure_notes || "").trim()) {
    setDetailSaveMessageState(message, "יש למלא סיבת כשל", "error");
    resetSaveButton();
    return;
  }
  if (technicianMode && !selectedStatus) {
    setDetailSaveMessageState(message, "יש לבחור סטטוס", "error");
    resetSaveButton();
    return;
  }
  if (currentTicket.board_slug === "support" && payload.details.service_mode && !technicianMode) {
    if (!payload.details.business_name || !payload.details.service_contact || !payload.details.service_address) {
      setDetailSaveMessageState(message, "יש למלא שם העסק, איש קשר וכתובת", "error");
      resetSaveButton();
      return;
    }
  }
  if (isNastyaQueuePage && !technicianMode && !isFinalStatus && !cancelCoordination) {
    if (!coordinationPayload.coordinated_worker) {
      setFieldInvalid(coordinatedWorkerField, true);
      setDetailSaveMessageState(message, "לא נבחר טכנאי מטפל", "error");
      resetSaveButton();
      return;
    }
    if (!coordinationPayload.visit_date) {
      setFieldInvalid(visitDateField, true);
      setDetailSaveMessageState(message, "לא נבחר תאריך ביקור", "error");
      resetSaveButton();
      return;
    }
    if (!coordinationPayload.visit_hour_from) {
      setFieldInvalid(visitHourFromField, true);
      setDetailSaveMessageState(message, "לא נבחרה שעת התחלה", "error");
      resetSaveButton();
      return;
    }
    if (!coordinationPayload.visit_hour_to) {
      setFieldInvalid(visitHourToField, true);
      setDetailSaveMessageState(message, "לא נבחרה שעת סיום", "error");
      resetSaveButton();
      return;
    }
  }

  const coordinationChanged = ["coordinated_worker", "visit_date", "visit_hour_from", "visit_hour_to"]
    .some((fieldName) => String(currentDetails?.[fieldName] || "") !== String(coordinationPayload[fieldName] || ""));
  if (isNastyaQueuePage && !technicianMode && cancelCoordination && coordinationChanged) {
    payload.send_nastia_cancellation_notification = true;
  } else if (isNastyaQueuePage && !technicianMode && shouldMarkCoordinated && coordinationChanged) {
    payload.send_nastia_notification = true;
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
    if (data?.ticket?.notification_error) {
      openNotificationErrorModal(`הסטטוס עודכן אבל שליחת המייל נכשלה: ${data.ticket.notification_error}`);
    } else if (data?.ticket?.notification_sent === true) {
      showSendSuccessToast();
    } else if (payload.send_nastia_notification === true || payload.send_nastia_cancellation_notification === true) {
      openNotificationErrorModal("הסטטוס עודכן אבל טריגר המייל לא הופעל.");
    }
    setDetailSaveMessageState(message, "נשמר בהצלחה", "success");
    if (button) {
      button.innerHTML = '<i class="fa-solid fa-check"></i><span>נשמר</span>';
    }
    await waitForUi(650);
    closeTicketDetail();
    await loadTickets();
    await loadPaisReport();
  } catch (err) {
    openNotificationErrorModal(err.message || "Save failed");
    setDetailSaveMessageState(message, err.message || "שמירה נכשלה", "error");
  } finally {
    resetSaveButton();
  }
}

function openTicketDetail(ticketId) {
  const ticket = getTicket(ticketId);
  if (!ticket) return;

  const details = ticketDetails(ticket);
  document.getElementById("detail-kicker").textContent = isCoordinationTicket(ticket) ? (boardDisplayName(ticket.board_slug) || ticket.service_type || "Ticket") : (ticket.service_type || "Ticket");
  document.getElementById("detail-title").textContent = ticket.ticket_id || `#${String(ticket.id).padStart(4, "0")}`;

  const gridItems = [
    detailItem("Board", isCoordinationTicket(ticket) ? (boardDisplayName(ticket.board_slug) || ticket.service_type || "") : "נימבוס"),
    detailItem("Status", displayTicketStatus(ticket)),
    detailItem("Assigned To", ticket.assigned_to || "Unassigned"),
    detailItem("Creator", ticket.creator),
    detailItem("Created", ticket.created_at_display),
    detailItem("Last Edited", ticket.last_edited_at_display || "—"),
    detailItem("Internal ID", ticket.id),
  ];

  if (isPaisTicket(ticket)) {
    gridItems.splice(1, 0,
      detailItem("מספר מסוף", details.terminal_number),
      detailItemHtml("כתובת", renderAddressValue(details.address)),
      detailItem("כתובת IP סטטית", details.static_ip),
      detailItem("אלטורה", details.altura),
      detailItem("loop back", details.look_back),
      detailItem("נציג מטפל", ticket.assigned_to || "—"),
      detailItem("טכנאי מתואם", details.coordinated_worker || "—"),
      detailItem("תאריך ביקור", details.visit_date || "—"),
      detailItem("שעות ביקור", [details.visit_hour_from, details.visit_hour_to].filter(Boolean).join(" - ") || "—"),
      detailItem("איש קשר - שם", details.contact_name),
      detailItemHtml("איש קשר - מספר", renderPhoneValue(details.contact_phone)),
    );
  } else if (isHotTicket(ticket)) {
    gridItems.splice(1, 0,
      detailItem("מספר קריאה", details.call_number),
      detailItem("שם לקוח", details.customer_name),
      detailItem("ח.פ. / מס לקוח", details.customer_id),
      detailItem("קוד קו / ID-LINK", details.line_code),
      detailItemHtml("כתובת", renderAddressValue(details.address)),
      detailItem("שעת פתיחת תקלה", details.opened_at),
      detailItem("נציג מטפל", ticket.assigned_to || "—"),
      detailItem("תומך במוקד", details.opened_by),
      detailItemHtml("איש קשר במקום", renderContactWithPhone(details.on_site_contact)),
      detailItem("איש קשר טכני", details.technical_contact),
      detailItem("זמינות לקוח", details.availability_hours),
      detailItem("טכנאי מתואם", details.coordinated_worker || "—"),
      detailItem("תאריך ביקור", details.visit_date || "—"),
      detailItem("שעות ביקור", [details.visit_hour_from, details.visit_hour_to].filter(Boolean).join(" - ") || "—"),
    );
  } else {
    gridItems.splice(1, 0,
      detailItem("Ticket Type", ticket.ticket_type),
      detailItem("Service Type", ticket.service_type),
      detailItem("Domain", ticket.domain),
      detailItem("Priority", ticket.priority),
      details.customer_type ? detailItem("סוג לקוח", details.customer_type) : "",
      details.service_mode ? detailItem("סוג טיפול", details.service_mode) : "",
      details.business_name ? detailItem("שם העסק", details.business_name) : "",
      details.service_contact ? detailItemHtml("איש קשר", renderContactWithPhone(details.service_contact)) : "",
      details.service_address ? detailItemHtml("כתובת", renderAddressValue(details.service_address)) : "",
      detailItem("טכנאי מתואם", details.coordinated_worker || "—"),
      detailItem("תאריך ביקור", details.visit_date || "—"),
      detailItem("שעות ביקור", [details.visit_hour_from, details.visit_hour_to].filter(Boolean).join(" - ") || "—"),
    );
  }

  document.getElementById("detail-grid").innerHTML = gridItems.filter(Boolean).join("");
  document.getElementById("detail-sections").innerHTML = renderDetailSections(ticket);
  const detailCopyButton = document.getElementById("detail-copy-btn");
  if (detailCopyButton) {
    detailCopyButton.dataset.ticketId = ticket.id;
  }
  const detailUploadTicketId = document.getElementById("detail-upload-ticket-id");
  if (detailUploadTicketId) {
    detailUploadTicketId.value = ticket.id;
  }
  document.getElementById("detail-upload-form")?.reset();
  const detailUploadMessage = document.getElementById("detail-upload-message");
  if (detailUploadMessage) {
    detailUploadMessage.textContent = "";
  }
  syncDetailAttachmentInputState();
  const detailUploadPanel = document.getElementById("detail-upload-panel");
  if (detailUploadPanel) {
    detailUploadPanel.hidden = !canUploadTicketAttachments;
  }
  if (isCoordinationTicket(ticket)) {
    clearCoordinationValidation();
    document.getElementById("detail-status-select")?.addEventListener("change", syncPaisDetailStatusFields);
    const detailSections = document.getElementById("detail-sections");
    setupServiceModeSelectors(detailSections || document);
    document.getElementById("detail-visit-hour-from")?.addEventListener("change", syncPaisDetailVisitRange);
    document.getElementById("detail-coordinated-worker")?.addEventListener("change", () => setFieldInvalid(document.getElementById("detail-coordinated-worker"), false));
    document.getElementById("detail-visit-date")?.addEventListener("input", () => setFieldInvalid(document.getElementById("detail-visit-date"), false));
    document.getElementById("detail-visit-hour-from")?.addEventListener("change", () => setFieldInvalid(document.getElementById("detail-visit-hour-from"), false));
    document.getElementById("detail-visit-hour-to")?.addEventListener("change", () => setFieldInvalid(document.getElementById("detail-visit-hour-to"), false));
    document.getElementById("detail-save-btn")?.addEventListener("click", () => saveTicketDetailWithFeedback(ticket.id));
    document.getElementById("detail-cancel-coordination-btn")?.addEventListener("click", () => cancelTicketCoordination(ticket.id));
    syncPaisDetailStatusFields();
    syncPaisDetailVisitRange();
    toggleSupportServiceDetails(detailSections);
  }

  const attachments = Array.isArray(ticket.attachments) ? ticket.attachments : [];
  const attachmentHost = document.getElementById("detail-attachments");
  attachmentHost.innerHTML = attachments.length
    ? attachments.map((file, index) => `
        <div class="detail-attachment-item">
          ${isImageAttachment(file)
            ? `<button class="detail-image-btn" type="button" data-image-url="${escapeHtml(file.url)}">
                <i class="fa-solid fa-paperclip"></i>
                <span>${escapeHtml(file.original_name || `File ${index + 1}`)}</span>
              </button>`
            : `<a class="detail-file-btn" href="${escapeHtml(file.url)}" download>
                <i class="fa-regular fa-file-pdf"></i>
                <span>${escapeHtml(file.original_name || `File ${index + 1}`)}</span>
              </a>`}
          <button
            class="detail-attachment-delete"
            type="button"
            data-ticket-id="${escapeHtml(ticket.id)}"
            data-folder="${escapeHtml(file.folder || "")}"
            data-saved-name="${escapeHtml(file.saved_name || "")}"
            title="Delete file"
            ${canDeleteTicketAttachments ? "" : "hidden"}
          >
            <i class="fa-solid fa-trash"></i>
          </button>
        </div>
      `).join("")
    : "";
  attachmentHost.querySelectorAll(".detail-image-btn").forEach((button) => {
    button.addEventListener("click", () => openImagePreview(button.dataset.imageUrl || ""));
  });
  attachmentHost.querySelectorAll(".open-field-report-btn").forEach((button) => {
    button.addEventListener("click", () => openFieldReportModal(button.dataset.ticketId || ""));
  });
  if (canDeleteTicketAttachments) {
    attachmentHost.querySelectorAll(".detail-attachment-delete").forEach((button) => {
      button.addEventListener("click", () => deleteDetailAttachment(
        button.dataset.ticketId || "",
        button.dataset.folder || "",
        button.dataset.savedName || "",
      ));
    });
  }

  const modal = document.getElementById("ticket-detail-modal");
  modal.classList.add("open");
  modal.setAttribute("aria-hidden", "false");
  document.querySelectorAll(".open-field-report-btn").forEach((button) => {
    button.addEventListener("click", () => openFieldReportModal(button.dataset.ticketId || ""));
  });
}

function normalizeHotPasteLine(line) {
  return String(line || "")
    .replace(/\*\*/g, "")
    .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
    .replace(/\u00a0/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function hotPasteLabelKey(line) {
  const normalized = normalizeHotPasteLine(line).replace(/[\\/]/g, "/");
  const labels = [
    ["שעה ותאריך פתיחת תקלה", "opened_at"],
    ["מספר קריאה שהוקצה", "call_number"],
    ["תומך במוקד שפתח פניה / טיפל בלקוח", "opened_by"],
    ["ח.פ. / מס לקוח", "customer_id"],
    ["שם לקוח", "customer_name"],
    ["קוד קו / ID-LINK", "line_code"],
    ["כתובת לקוח", "address"],
    ["איש קשר במקום", "on_site_contact"],
    ["איש קשר טכני מטעם הלקוח", "technical_contact"],
    ["שעות פעילות / זמינות לקוח", "availability_hours"],
    ["בדיקות שבוצעו מרחוק", "remote_checks"],
    ["מהות התקלה", "issue_summary"],
    ["פעולות / בדיקות שטכנאי צריך לבצע", "technician_actions"],
    ["סוג ציוד קיים אצל הלקוח", "equipment_type"],
    ["הסכם שירות ואיזה ציוד באחריות הוט", "service_agreement"],
    ["פרטים טכניים נוספים שהטכנאי צריך להכיר ( יוזר / סיסמא / קונפיגורציה / גיבויים )", "technical_notes"],
    ["פרטים טכניים נוספים שהטכנאי צריך להכיר", "technical_notes"],
  ];
  const match = labels.find(([label]) => normalized === label);
  return match?.[1] || "";
}

function parseHotPasteText(rawText) {
  const lines = String(rawText || "")
    .replace(/\r/g, "")
    .split("\n")
    .map(normalizeHotPasteLine)
    .filter((line) => line && !/^\|(?:\s*-\s*\|?)*$/.test(line));
  const result = {
    opened_at: "",
    call_number: "",
    opened_by: "",
    customer_id: "",
    customer_name: "",
    line_code: "",
    address: "",
    on_site_contact: "",
    technical_contact: "",
    availability_hours: "",
    remote_checks: "",
    issue_summary: "",
    technician_actions: "",
    equipment_type: "",
    service_agreement: "",
    technical_notes: "",
  };

  for (let index = 0; index < lines.length; index += 1) {
    const key = hotPasteLabelKey(lines[index]);
    if (!key) continue;
    const values = [];
    for (let cursor = index + 1; cursor < lines.length; cursor += 1) {
      if (hotPasteLabelKey(lines[cursor])) {
        index = cursor - 1;
        break;
      }
      values.push(lines[cursor]);
      if (cursor === lines.length - 1) {
        index = cursor;
      }
    }
    result[key] = values.join("\n").trim();
  }

  result.call_number = result.call_number.replace(/^פניה\s*[-:]\s*/i, "").trim();
  return result;
}

function fillBoardFieldsFromPaste() {
  const source = document.getElementById("board-paste-source");
  const message = document.getElementById("board-paste-message");
  if (!source) return;

  const parsed = boardSlug === "hot-kiryot" ? parseHotPasteText(source.value) : parsePaisPasteText(source.value);
  const mapping = boardSlug === "hot-kiryot"
    ? {
        opened_at: 'input[name="opened_at"]',
        call_number: 'input[name="call_number"]',
        opened_by: 'input[name="opened_by"]',
        customer_id: 'input[name="customer_id"]',
        customer_name: 'input[name="customer_name"]',
        line_code: 'input[name="line_code"]',
        address: 'input[name="address"]',
        on_site_contact: 'input[name="on_site_contact"]',
        technical_contact: 'input[name="technical_contact"]',
        availability_hours: 'input[name="availability_hours"]',
        remote_checks: 'textarea[name="remote_checks"]',
        issue_summary: 'textarea[name="issue_summary"]',
        technician_actions: 'textarea[name="technician_actions"]',
        equipment_type: 'textarea[name="equipment_type"]',
        service_agreement: 'textarea[name="service_agreement"]',
        technical_notes: 'textarea[name="technical_notes"]',
      }
    : {
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

function fieldReportSignatureStatusText(target) {
  const dataValue = document.getElementById(fieldReportSignatureFieldId(target))?.value || "";
  const label = target === "technician" ? "חתימת טכנאי" : "חתימת לקוח";
  const optionalSuffix = target === "customer" ? " (לא חובה)" : "";
  return dataValue ? `${label} נוספה` : `לא נוספה ${label}${optionalSuffix}`;
}

function renderPaisDetailSections(ticket) {
  const details = ticketDetails(ticket);
  const technicianMode = canAssignedTechnicianEditTicket(ticket);
  const isCoordinatorView = isNastyaQueuePage;
  const technicianOptions = ['<option value="">בחר עובד</option>']
    .concat(technicianUsers.map((user) => `<option value="${escapeHtml(user)}" ${details.coordinated_worker === user ? "selected" : ""}>${escapeHtml(user)}</option>`))
    .join("");
  const showCoordination = isCoordinatorView || pageMode === "nastia" || normalizePendingStatus(ticket.status) === "ממתין לתיאום" || Boolean(details.coordinated_worker || details.visit_date || details.visit_hour_from || details.visit_hour_to);
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

  if (technicianMode) {
    return `
      ${detailSection("פניית לקוח", details.customer_request)}
      <section class="detail-description detail-edit-card">
        <h3>פעולות / טקסט חופשי</h3>
        <textarea id="detail-actions-taken" rows="4" placeholder="לא חובה למלא">${escapeHtml(details.actions_taken || "")}</textarea>
      </section>
      ${fieldReportSummaryCard(ticket, true) || `
      <section class="detail-description detail-edit-card">
        <h3>החתמת לקוח</h3>
        <div class="field-report-actions">
          <button class="create-ticket-btn open-field-report-btn" type="button" data-ticket-id="${escapeHtml(ticket.id)}">
            <i class="fa-solid fa-file-signature"></i><span>החתמת לקוח (לא חובה)</span>
          </button>
        </div>
      </section>`}
      <section class="detail-description detail-edit-card">
        <h3>סטטוס</h3>
        <select id="detail-status-select">
          ${statusOptionsForTicket(ticket)}
        </select>
      </section>
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

  return `
    ${detailSection("פניית לקוח", details.customer_request)}
    <section class="detail-description detail-edit-card">
      <h3>פעולות</h3>
      <textarea id="detail-actions-taken" rows="4">${escapeHtml(details.actions_taken || "")}</textarea>
    </section>
    ${details.field_report ? fieldReportSummaryCard(ticket, false) : ""}
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
      <p class="detail-hint">חלונות התיאום הם של שעה אחת, החל מ-09:00.</p>
      ${coordinationCancelButton(ticket, details)}
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

async function submitFieldReport(event) {
  event.preventDefault();
  setFieldReportMessage("", "");
  setFieldReportLoading(true);

  const lineItems = collectFieldReportLineItems()
    .filter((row) => Object.values(row).some((value) => String(value || "").trim()));

  const payload = {
    ticket_id: document.getElementById("field-report-ticket-id")?.value || "",
    nimbus_customer_name: document.getElementById("field-report-nimbus-customer-name")?.value || "",
    contact_first_name: document.getElementById("field-report-contact-first-name")?.value || "",
    contact_last_name: document.getElementById("field-report-contact-last-name")?.value || "",
    role: document.getElementById("field-report-role")?.value || "",
    installation_address: document.getElementById("field-report-installation-address")?.value || "",
    phone: document.getElementById("field-report-phone")?.value || "",
    customer_notes: document.getElementById("field-report-customer-notes")?.value || "",
    additional_notes: document.getElementById("field-report-additional-notes")?.value || "",
    line_items: lineItems,
    installation_date: document.getElementById("field-report-installation-date")?.value || "",
    technician_name: document.getElementById("field-report-technician-name")?.value || "",
    technician_signature_data_url: document.getElementById("field-report-technician-signature-data")?.value || "",
    customer_signature_data_url: document.getElementById("field-report-customer-signature-data")?.value || "",
  };
  const areaPhotoInput = document.getElementById("field-report-area-photos");
  const selectedPhotos = Array.from(areaPhotoInput?.files || []);

  if (!payload.technician_signature_data_url) {
    setFieldReportMessage("יש להוסיף חתימת טכנאי", "error");
    setFieldReportLoading(false);
    return;
  }

  try {
    const formData = new FormData();
    formData.append("payload", JSON.stringify(payload));
    selectedPhotos.forEach((file) => {
      formData.append("area_photos", file);
    });
    const res = await fetch("/support-tickets-field-report", {
      method: "POST",
      body: formData,
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok || !data.ok) {
      throw new Error(data.message || "Save failed");
    }
    if (data?.ticket?.field_report_error) {
      setFieldReportMessage(`הטופס נשמר, אך שליחת המייל נכשלה: ${data.ticket.field_report_error}`, "error");
      closeSignatureModal();
      closeFieldReportModal();
      closeTicketDetail();
      await loadTickets();
      openNotificationErrorModal(`הטופס נשמר, אך שליחת המייל נכשלה: ${data.ticket.field_report_error}`);
      return;
    }
    closeSignatureModal();
    closeFieldReportModal();
    closeTicketDetail();
    showSendSuccessToast();
    await loadTickets();
  } catch (error) {
    setFieldReportMessage(error.message || "שמירת הטופס נכשלה", "error");
    setFieldReportLoading(false);
    return;
  }

  setFieldReportLoading(false);
}

document.addEventListener("DOMContentLoaded", () => {
  const portalToggle = document.querySelector(".portal-toggle");
  if (portalToggle) {
    const portalMenu = portalToggle.closest(".portal-menu");
    portalToggle.setAttribute("aria-expanded", portalMenu?.classList.contains("collapsed") ? "false" : "true");
    portalToggle.addEventListener("click", () => {
      portalMenu?.classList.toggle("collapsed");
      portalToggle.setAttribute("aria-expanded", portalMenu?.classList.contains("collapsed") ? "false" : "true");
    });
  }

  document.querySelectorAll(".ticket-tab").forEach((button) => {
    button.classList.toggle("active", (button.dataset.scope || "all") === currentScope);
    button.addEventListener("click", () => {
      document.querySelectorAll(".ticket-tab").forEach((tab) => tab.classList.remove("active"));
      button.classList.add("active");
      currentScope = button.dataset.scope || "all";
      loadTickets();
    });
  });

  syncNastyaBoardFilterButtons();
  document.querySelectorAll("[data-board-filter]").forEach((button) => {
    button.addEventListener("click", () => {
      const selectedBoard = String(button.dataset.boardFilter || "all");
      nastyaBoardFilter = nastyaBoardFilter === selectedBoard ? "all" : selectedBoard;
      syncNastyaBoardFilterButtons();
      loadTickets();
    });
  });

  ["status-filter", "assignee-filter", "priority-filter", "date-from-filter", "date-to-filter"].forEach((id) => {
    document.getElementById(id).addEventListener("change", loadTickets);
  });
  document.getElementById("ticket-filters-form")?.addEventListener("submit", (event) => {
    event.preventDefault();
    submitTicketSearch();
  });
  const ticketSearch = document.getElementById("ticket-search");
  const ticketSearchButton = document.getElementById("ticket-search-btn");
  ticketSearch?.addEventListener("keydown", (event) => {
    if (event.key !== "Enter") return;
    event.preventDefault();
    submitTicketSearch();
  });
  ticketSearch?.addEventListener("search", submitTicketSearch);
  ticketSearchButton?.addEventListener("click", (event) => {
    event.preventDefault();
    submitTicketSearch();
  });

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
    if (!event.target.closest(".service-mode-selector")) {
      closeServiceModeMenus();
    }
  });

  document.getElementById("close-ticket-modal").addEventListener("click", closeModal);
  document.getElementById("ticket-modal").addEventListener("click", (event) => {
    if (event.target.id === "ticket-modal") closeModal();
  });
  document.getElementById("close-detail-modal").addEventListener("click", closeTicketDetail);
  document.getElementById("close-field-report-modal")?.addEventListener("click", closeFieldReportModal);
  document.getElementById("field-report-modal")?.addEventListener("click", (event) => {
    if (event.target.id === "field-report-modal") closeFieldReportModal();
  });
  document.getElementById("close-signature-modal")?.addEventListener("click", closeSignatureModal);
  document.getElementById("cancel-signature-btn")?.addEventListener("click", closeSignatureModal);
  document.getElementById("clear-signature-btn")?.addEventListener("click", clearSignatureCanvas);
  document.getElementById("save-signature-btn")?.addEventListener("click", saveSignatureToFieldReport);
  document.querySelectorAll(".field-report-signature-btn").forEach((button) => {
    button.addEventListener("click", () => {
      activeFieldReportSignatureTarget = button.dataset.signatureTarget === "technician" ? "technician" : "customer";
      openSignatureModal();
    });
  });
  document.getElementById("signature-modal")?.addEventListener("click", (event) => {
    if (event.target.id === "signature-modal") closeSignatureModal();
  });
  document.getElementById("detail-copy-btn")?.addEventListener("click", async (event) => {
    const button = event.currentTarget;
    await copyTicketDetails(button.dataset.ticketId || "", button);
  });
  document.getElementById("ticket-detail-modal").addEventListener("click", (event) => {
    if (event.target.id === "ticket-detail-modal") closeTicketDetail();
  });
  document.getElementById("close-notification-error-modal")?.addEventListener("click", closeNotificationErrorModal);
  document.getElementById("notification-error-close-btn")?.addEventListener("click", closeNotificationErrorModal);
  document.getElementById("notification-error-modal")?.addEventListener("click", (event) => {
    if (event.target.id === "notification-error-modal") closeNotificationErrorModal();
  });
  document.getElementById("close-image-modal").addEventListener("click", closeImagePreview);
  document.getElementById("image-modal").addEventListener("click", (event) => {
    if (event.target.id === "image-modal") closeImagePreview();
  });
  document.getElementById("zoom-in-image")?.addEventListener("click", () => adjustImagePreviewScale(0.25));
  document.getElementById("zoom-out-image")?.addEventListener("click", () => adjustImagePreviewScale(-0.25));
  document.getElementById("zoom-reset-image")?.addEventListener("click", resetImagePreviewScale);
  document.getElementById("image-preview")?.addEventListener("dblclick", () => {
    if (imagePreviewScale > 1) {
      resetImagePreviewScale();
      return;
    }
    applyImagePreviewScale(2);
  });
  document.getElementById("image-stage")?.addEventListener("wheel", (event) => {
    if (!document.getElementById("image-modal")?.classList.contains("open")) return;
    event.preventDefault();
    adjustImagePreviewScale(event.deltaY < 0 ? 0.2 : -0.2);
  }, { passive: false });

  const serviceTypeInput = document.getElementById("service-type");
  if (serviceTypeInput) {
    serviceTypeInput.addEventListener("input", syncDomainRequirement);
    syncDomainRequirement();
  }
  setupServiceModeSelectors(document.getElementById("ticket-form"));

  document.getElementById("attachment-input")?.addEventListener("change", syncAttachmentInputState);
  document.getElementById("detail-attachment-input")?.addEventListener("change", syncDetailAttachmentInputState);
  document.getElementById("field-report-phone")?.addEventListener("input", (event) => {
    event.currentTarget.value = String(event.currentTarget.value || "").replace(/[^\d+]/g, "");
  });
  document.getElementById("field-report-area-photos")?.addEventListener("change", (event) => {
    const files = Array.from(event.currentTarget?.files || []).map((file) => ({ original_name: file.name }));
    renderFieldReportPhotoList(files, "field-report-pending-photos", "לא נבחרו קבצים חדשים");
  });
  document.getElementById("field-report-items-toggle")?.addEventListener("click", () => {
    const isExpanded = document.getElementById("field-report-items-toggle")?.getAttribute("aria-expanded") === "true";
    setFieldReportItemsExpanded(!isExpanded);
  });
  syncAttachmentInputState();
  syncDetailAttachmentInputState();
  syncFieldReportSignatureStatuses();
  setFieldReportItemsExpanded(false);
  renderFieldReportPhotoList([], "field-report-existing-photos", "עדיין לא נוספו צילומים");
  renderFieldReportPhotoList([], "field-report-pending-photos", "לא נבחרו קבצים חדשים");
  bindSignaturePad();

  document.getElementById("ticket-form").addEventListener("submit", submitTicket);
  document.getElementById("detail-upload-form")?.addEventListener("submit", uploadDetailAttachments);
  document.getElementById("field-report-form")?.addEventListener("submit", submitFieldReport);
  document.getElementById("parse-board-paste")?.addEventListener("click", fillBoardFieldsFromPaste);
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) {
      runAutoRefresh();
    }
  });
  document.addEventListener("keydown", (event) => {
    if (document.getElementById("notification-error-modal")?.classList.contains("open") && event.key === "Escape") {
      closeNotificationErrorModal();
      return;
    }
    if (document.getElementById("signature-modal")?.classList.contains("open") && event.key === "Escape") {
      closeSignatureModal();
      return;
    }
    if (document.getElementById("field-report-modal")?.classList.contains("open") && event.key === "Escape") {
      closeFieldReportModal();
      return;
    }
    if (!document.getElementById("image-modal")?.classList.contains("open")) return;
    if (event.key === "Escape") {
      closeImagePreview();
      return;
    }
    if (event.key === "+" || event.key === "=") {
      event.preventDefault();
      adjustImagePreviewScale(0.25);
      return;
    }
    if (event.key === "-" || event.key === "_") {
      event.preventDefault();
      adjustImagePreviewScale(-0.25);
      return;
    }
    if (event.key === "0") {
      event.preventDefault();
      resetImagePreviewScale();
    }
  });

  loadTickets();
  if (boardSupportsReport(boardSlug)) {
    ["pais-report-period", "pais-report-status", "pais-report-from", "pais-report-to"].forEach((id) => {
      document.getElementById(id)?.addEventListener("change", loadPaisReport);
    });
    document.getElementById("export-pais-report")?.addEventListener("click", exportPaisReport);
    loadPaisReport();
  }
  startAutoRefresh();
});
