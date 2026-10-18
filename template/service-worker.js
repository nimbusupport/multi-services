const DEFAULT_ICON = "/brand/nimbus-logo.png";
const SUPPORT_NOTIFICATION_TAG_PREFIX = "support-ticket-";
const SUPPORT_SUMMARY_NOTIFICATION_TAG_PREFIX = "support-ticket-summary-";

self.addEventListener("install", (event) => {
  event.waitUntil(self.skipWaiting());
});

self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});

function parsePushPayload(event) {
  if (!event.data) return {};
  try {
    return event.data.json() || {};
  } catch (error) {
    try {
      return { body: event.data.text() };
    } catch (textError) {
      return {};
    }
  }
}

self.addEventListener("push", (event) => {
  const payload = parsePushPayload(event);
  const title = String(payload.title || "קריאה חדשה הוקצתה אליך");
  const options = {
    body: String(payload.body || "יש קריאה חדשה שממתינה לך."),
    icon: String(payload.icon || DEFAULT_ICON),
    badge: String(payload.badge || DEFAULT_ICON),
    tag: String(payload.tag || `${SUPPORT_NOTIFICATION_TAG_PREFIX}${Date.now()}`),
    data: {
      url: String(payload.url || "/support-tickets"),
      ticketId: String(payload.ticketId || ""),
      boardSlug: String(payload.boardSlug || "support"),
      supportUser: String(payload.supportUser || ""),
    },
    renotify: true,
    requireInteraction: false,
    dir: "rtl",
    lang: "he",
  };
  event.waitUntil(self.registration.showNotification(title, options));
});

async function clearTicketNotifications(ticketIds = []) {
  const normalizedIds = Array.isArray(ticketIds)
    ? ticketIds.map((ticketId) => String(ticketId || "").trim()).filter(Boolean)
    : [];
  const notifications = await self.registration.getNotifications();
  notifications.forEach((notification) => {
    const notificationTicketId = String(notification?.data?.ticketId || "").trim();
    const isSupportNotification = String(notification.tag || "").startsWith(SUPPORT_NOTIFICATION_TAG_PREFIX);
    if (!isSupportNotification) return;
    if (normalizedIds.length > 0 && !normalizedIds.includes(notificationTicketId)) return;
    notification.close();
  });
}

async function syncTicketAlertSummary(payload = {}) {
  const unreadCount = Number.parseInt(payload.unreadCount, 10) || 0;
  const tag = String(payload.tag || `${SUPPORT_SUMMARY_NOTIFICATION_TAG_PREFIX}global`);
  const url = String(payload.url || "/support-tickets?scope=my");
  const title = String(payload.title || "קריאות שלא נקראו");
  const body = unreadCount > 0
    ? String(payload.body || `יש לך ${unreadCount} קריאות שלא נקראו.`)
    : "";

  const notifications = await self.registration.getNotifications({ tag });
  notifications.forEach((notification) => notification.close());

  if (unreadCount <= 0) {
    return;
  }

  await self.registration.showNotification(title, {
    body,
    icon: String(payload.icon || DEFAULT_ICON),
    badge: String(payload.badge || DEFAULT_ICON),
    tag,
    data: {
      url,
      supportUser: String(payload.supportUser || ""),
      boardSlug: String(payload.boardSlug || "support"),
      summary: true,
    },
    renotify: false,
    requireInteraction: false,
    silent: true,
    dir: "rtl",
    lang: "he",
  });
}

self.addEventListener("message", (event) => {
  const payload = event.data || {};
  if (payload.type === "clear-ticket-notifications") {
    event.waitUntil(clearTicketNotifications(payload.ticketIds));
    return;
  }
  if (payload.type === "sync-ticket-alert-summary") {
    event.waitUntil(syncTicketAlertSummary(payload));
  }
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const targetUrl = String(event.notification?.data?.url || "/support-tickets");
  event.waitUntil((async () => {
    const windowClients = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
    for (const client of windowClients) {
      try {
        if ("navigate" in client) {
          await client.navigate(targetUrl);
        }
        if ("focus" in client) {
          await client.focus();
        }
        return;
      } catch (error) {
      }
    }
    if (self.clients.openWindow) {
      await self.clients.openWindow(targetUrl);
    }
  })());
});
