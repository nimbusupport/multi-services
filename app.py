from flask import Flask, render_template, request, jsonify, send_file
import os
import shutil
import csv
import tempfile
import base64
from werkzeug.utils import secure_filename
from werkzeug.datastructures import FileStorage
from werkzeug.security import check_password_hash
import re
import io
import json
import mimetypes
import smtplib
import pandas as pd
import gspread
import requests
from datetime import datetime, timedelta
from datetime import timezone
from email.message import EmailMessage
from zoneinfo import ZoneInfo
from urllib.parse import quote, urlparse, urlunparse
from xml.sax.saxutils import escape as xml_escape
from bidi.algorithm import get_display
from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from dotenv import load_dotenv
from flask import session, redirect, url_for
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

load_dotenv()

app = Flask(
    __name__,
    template_folder="template",
    static_folder="template",
    static_url_path=""
)
TOKEN_INFORU = (
    os.environ.get("TOKEN_INFORU")
    or os.environ.get("INFORU_MAKE_WEBHOOK_URL")
    or os.environ.get("MAKE_WEBHOOK_URL")
)
app.secret_key = os.environ.get("SECRET_KEY", "super-secret-key")
APP_USERNAME = os.environ.get("APP_USERNAME")
APP_PASSWORD = os.environ.get("APP_PASSWORD")
# Manual login users (same shared password)
DEFAULT_ALLOWED_USERS = {
    "admin@nimbusip.com",
    "eugeni@nimbusip.com",
    "nir@nimbusip.com",
    "nastia@nimbusip.com",
    "nastya@nimbusip.com",
}
ALLOWED_EMAIL_DOMAIN = os.environ.get("ALLOWED_EMAIL_DOMAIN", "nimbusip.com").strip().lower().lstrip("@")
ALLOWED_USERS = {user.strip().lower() for user in DEFAULT_ALLOWED_USERS}
if APP_USERNAME:
    ALLOWED_USERS.add(APP_USERNAME.strip().lower())
for configured_user in os.environ.get("ALLOWED_USERS", "").split(","):
    configured_user = configured_user.strip().lower()
    if configured_user:
        ALLOWED_USERS.add(configured_user)
SHARED_PASSWORD = APP_PASSWORD or "Aa@0778066666"


def env_flag(name, default=False):
    value = (os.environ.get(name) or "").strip().lower()
    if not value:
        return default
    return value in {"1", "true", "yes", "on"}


# ====== .ENV ======
SMS_URL = os.environ.get("SMS_URL")
SMS_TOKEN = os.environ.get("SMS_TOKEN")
SMS_CREATED_MESSAGE = "Created"
# ====== CONFIG ======
SPREADSHEET_ID = "1uwtREvtWENPabibI5FSlhdYokIbBs_kuZmYVeL-BgCQ"
SHEET_NAME = "SMS"
# Bot sheet
BOT_SHEET_NAME = "\u05e9\u05d9\u05e8\u05d5\u05ea \u05de\u05e2\u05e0\u05d4 - \u05d1\u05d5\u05d8"
F2M_SHEET_NAME = "m2f / f2m"
RECORDING_STORAGE_SHEET_NAME = "\u05d0\u05d9\u05d7\u05e1\u05d5\u05df \u05d4\u05e7\u05dc\u05d8\u05d5\u05ea"
HUMAN_SERVICE_SHEET_NAME = "\u05e9\u05d9\u05e8\u05d5\u05ea \u05de\u05e2\u05e0\u05d4 - \u05d0\u05e0\u05d5\u05e9\u05d9"
HUMAN_SERVICE_DONE_COL = 14  # N checkbox
RECORDING_OPENING_SHEET_NAME = "\u05d4\u05e7\u05dc\u05d8\u05ea \u05e4\u05ea\u05d9\u05d7 - \u05d0\u05d5\u05dc\u05e4\u05df"
RECORDING_WITH_MUSIC = "\u05e2\u05dd \u05de\u05d5\u05e1\u05d9\u05e7\u05ea \u05e8\u05e7\u05e2"
RECORDING_WITHOUT_MUSIC = "\u05d1\u05dc\u05d9 \u05de\u05d5\u05e1\u05d9\u05e7\u05ea \u05e8\u05e7\u05e2"

# NumberCGR pool sheet
CGR_SHEET_NAME = "\u05d7\u05d9\u05e4_\u05e1\u05de\u05e1"
CGR_START_ROW = 312
CGR_COL_NUMBER = 1  # A
CGR_COL_DOMAIN = 3  # C
CGR_COL_DATE = 4    # D
CGR_COL_USED = 5    # E (checkbox)

FEATURE_REPORT_SERVICES = {
    "recordings": {
        "label": "\u05d4\u05e7\u05dc\u05d8\u05d5\u05ea",
        "source": "drive_done",
        "category_sheet": RECORDING_OPENING_SHEET_NAME,
        "order_col": 5,    # E
        "category_col": 8, # H
    },
    "bot": {
        "label": "BOT",
        "sheet": BOT_SHEET_NAME,
        "status_col": 8,   # H
        "date_col": 17,    # Q
        "date_order": "mdy",
        "status_value": "\u05d1\u05d5\u05e6\u05e2",
    },
    "human": {
        "label": "\u05de\u05d5\u05e7\u05d3",
        "sheet": HUMAN_SERVICE_SHEET_NAME,
        "status_col": 8,   # H
        "date_col": 15,    # O
        "date_order": "mdy",
        "status_value": "\u05d1\u05d5\u05e6\u05e2",
    },
    "sms": {
        "label": "SMS",
        "sheet": CGR_SHEET_NAME,
        "status_col": 5,   # E
        "date_col": 4,     # D
        "date_order": "mdy",
        "checkbox": True,
    },
}

FEATURE_STATUS_SERVICES = [
    {
        "key": "sms",
        "label": "SMS",
        "sheet": SHEET_NAME,
        "status_col": 8,  # H
    },
    {
        "key": "recording_opening",
        "label": "הקלטת פתיח",
        "sheet": RECORDING_OPENING_SHEET_NAME,
        "status_col": 9,  # I
    },
    {
        "key": "bot",
        "label": "שירות מענה - בוט",
        "sheet": BOT_SHEET_NAME,
        "status_col": 8,  # H
    },
    {
        "key": "human_service",
        "label": "שירות מענה - אנושי",
        "sheet": HUMAN_SERVICE_SHEET_NAME,
        "status_col": 8,  # H
    },
    {
        "key": "f2m",
        "label": "m2f / f2m",
        "sheet": F2M_SHEET_NAME,
        "status_col": 8,  # H
    },
    {
        "key": "recording_storage",
        "label": "איחסון הקלטות",
        "sheet": RECORDING_STORAGE_SHEET_NAME,
        "status_col": 8,  # H
    },
]

PDF_FONT_CANDIDATES = {
    "hebrew": {
        "regular": [
            os.path.join(os.path.dirname(__file__), "template", "fonts", "NotoSansHebrew-Regular.ttf"),
        ],
        "bold": [
            os.path.join(os.path.dirname(__file__), "template", "fonts", "NotoSansHebrew-Bold.ttf"),
            os.path.join(os.path.dirname(__file__), "template", "fonts", "NotoSansHebrew-Regular.ttf"),
        ],
        "extra_bold": [
            os.path.join(os.path.dirname(__file__), "template", "fonts", "NotoSansHebrew-ExtraBold.ttf"),
            os.path.join(os.path.dirname(__file__), "template", "fonts", "NotoSansHebrew-Bold.ttf"),
            os.path.join(os.path.dirname(__file__), "template", "fonts", "NotoSansHebrew-Regular.ttf"),
        ],
    },
    "latin": {
        "regular": [],
        "bold": [],
        "extra_bold": [],
    },
}
PDF_FONT_NAMES = {}
HEBREW_TEXT_RE = re.compile(r"[\u0590-\u05FF]")

# Column mapping (1-based for gspread)
COL_NAME = 1       # A
COL_IDNUMBER = 2   # B (׳—.׳₪) hidden in UI
COL_STATUS = 8     # H
COL_SMS_TEXT = 10  # J
COL_K = 11         # K

STATUS_PENDING = "\u05de\u05de\u05ea\u05d9\u05df"
STATUS_DONE = "\u05d1\u05d5\u05e6\u05e2"
STATUS_NO_SMS_TEXT = "\u05dc\u05d0 \u05d4\u05d5\u05e2\u05d1\u05e8 \u05e0\u05d5\u05e1\u05d7"
STATUS_NOT_INTERESTED = "\u05dc\u05d0 \u05de\u05e2\u05d5\u05e0\u05d9\u05d9\u05df"
K_REQUIRED_VALUE = "\u05dc\u05e7\u05d5\u05d7 \u05d4\u05d5\u05ea\u05e7\u05df"

# ENV
CREDENTIALS_FILE = (os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "credentials.json") or "").strip()
FIREBERRY_TOKENID = (os.environ.get("FIREBERRY_TOKENID") or "").strip()
CRM_URL = (os.environ.get("CRM_URL") or "").strip()
FIREBERRY_URL = CRM_URL
DRIVE_FOLDER_ID = os.environ.get("DRIVE_FOLDER_ID", "1MOdZ1gTYGizpKlc6CtErskM_KMRp-2Db")
DRIVE_DONE_FOLDER_NAME = os.environ.get("DRIVE_DONE_FOLDER_NAME", "Done")
DRIVE_DONE_FOLDER_ID = os.environ.get("DRIVE_DONE_FOLDER_ID", "1LAJ0Ayjpt1HmsRnwmvNJY_RkVcbEffP_")

if not FIREBERRY_TOKENID:
    raise RuntimeError("FIREBERRY_TOKENID not found in .env")
if not FIREBERRY_URL:
    raise RuntimeError("CRM_URL not found in .env")

# Logging
LOG_DIR = "log"
LOG_FILE = os.path.join(LOG_DIR, "created.log")
SUPPORT_LOG_FILE = os.path.join(LOG_DIR, "support.log")
SUPPORT_SCREEN_DIR = "Screens"
INFORU_LOG_FILENAME = "\u05de\u05e1\u05e4\u05e8\u05d9\u05dd \u05dc\u05d0\u05d9\u05de\u05d5\u05ea.txt"
INFORU_LOG_TABLE = (
    os.environ.get("SUPABASE_INFORU_LOG_TABLE")
    or os.environ.get("INFORU_LOG_TABLE")
    or "inforu_logs"
).strip()
INFORU_LOG_DID_COLUMN = (
    os.environ.get("SUPABASE_INFORU_LOG_DID_COLUMN")
    or os.environ.get("INFORU_LOG_DID_COLUMN")
    or "did"
).strip()
INFORU_LOG_SENT_AT_COLUMN = (
    os.environ.get("SUPABASE_INFORU_LOG_SENT_AT_COLUMN")
    or os.environ.get("INFORU_LOG_SENT_AT_COLUMN")
    or "sent_at"
).strip()
ACTIVE_WINDOW_MINUTES = 30
_RAW_SUPABASE_URL = (
    os.environ.get("SUPABASE_URL")
    or os.environ.get("NEXT_PUBLIC_SUPABASE_URL")
    or os.environ.get("SUPABASE_PROJECT_URL")
    or ""
).strip()
SUPABASE_KEY = (
    os.environ.get("SUPABASE_KEY")
    or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    or os.environ.get("SUPABASE_ANON_KEY")
    or ""
).strip()
SUPPORT_USERS = ["ניר", "יבגני", "גולן", "איציק", "זורה", "אסף", "מוסטפה.א", "מוסטפה.ח", "נסטיה"]
COORDINATION_USERS = ["נסטיה"]
TECHNICIAN_SUPPORT_USERS = [user for user in SUPPORT_USERS if user not in COORDINATION_USERS]
COORDINATION_PENDING_STATUS = "ממתין לתיאום"
COORDINATION_PENDING_ALIASES = {COORDINATION_PENDING_STATUS, "ממתין לתאום"}
SUPPORT_STATUSES = ["Waiting", "Done"]
PAIS_STATUSES = ["ממתין", COORDINATION_PENDING_STATUS, "תואם", "אין מענה", "בוצע", "נכשל"]
ALL_TICKET_STATUSES = SUPPORT_STATUSES + [status for status in PAIS_STATUSES if status not in SUPPORT_STATUSES]
SUPPORT_DELIVERY_OPTIONS = ["ביקור טכנאי בתשלום", "ביקור ללא תשלום", "משלוח"]
SUPPORT_CUSTOMER_TYPES = ["לקוח נימבוס", "לקוח הוט"]
VISIT_SLOT_START_HOUR = 9
VISIT_SLOT_END_HOUR = 18
FULL_ACCESS_PAGES = {
    "home",
    "configuration",
    "sms",
    "bot",
    "f2m",
    "recording_storage",
    "human_service",
    "record",
    "features_report",
    "support_tickets",
    "pais_tickets",
    "hot_tickets",
    "nastia_tickets",
}
TICKETS_ONLY_ALLOWED_PAGES = {"support_tickets", "pais_tickets", "hot_tickets", "nastia_tickets"}
LOGIN_USER_OVERRIDES = {
    "nastya@nimbusip.com": {
        "password": "tygeydfuyw5t3g",
        "role": "tickets_only",
        "allowed_pages": sorted(TICKETS_ONLY_ALLOWED_PAGES),
    },
    "nastia@nimbusip.com": {
        "password": "tygeydfuyw5t3g",
        "role": "tickets_only",
        "allowed_pages": sorted(TICKETS_ONLY_ALLOWED_PAGES),
    },
    "golan@nimbusip.com": {
        "password": "0503009456!",
        "role": "assigned_technician",
        "allowed_pages": ["support_tickets", "pais_tickets", "hot_tickets"],
    },
    "assafh@nimbusip.com": {
        "password": "0523111777!",
        "role": "assigned_technician",
        "allowed_pages": ["support_tickets", "pais_tickets", "hot_tickets"],
    },
}
SUPPORT_PRIORITIES = ["High", "Medium", "Low"]
SUPPORT_TICKET_TYPES = ["תקלה", "שאלה", "שירות", "נוסף"]
SUPPORT_SERVICE_TYPES = [
    "מרכזייה",
    "מצלמות",
    "שרתים",
    "מרכזייה אנלוגית",
    "GDMS",
    "Provision ymcs",
    "אפליקציה Cloud Softphone",
]
SUPPORT_ATTACHMENT_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
SUPABASE_STORAGE_BUCKET = (os.environ.get("SUPABASE_STORAGE_BUCKET") or "").strip()
SUPABASE_STORAGE_PREFIX = (
    os.environ.get("SUPABASE_STORAGE_PREFIX") or "ticket-attachments"
).strip().strip("/")
SUPABASE_BUCKET_URL = (os.environ.get("SUPABASE_BUCKET_URL") or "").strip()
SUPABASE_BUCKET_REGION = (os.environ.get("SUPABASE_BUCKET_REGION") or "").strip()
SUPABASE_BUCKET_ACCESS_KEY = (os.environ.get("SUPABASE_BUCKET_ACCESS_KEY") or "").strip()
SUPABASE_BUCKET_SECRET_KEY = (os.environ.get("SUPABASE_BUCKET_SECRET_KEY") or "").strip()
NASTIA_NOTIFICATION_EMAIL = (os.environ.get("NASTIA_NOTIFICATION_EMAIL") or "nastya@nimbusip.com").strip()
RACHELI_NOTIFICATION_EMAIL = (os.environ.get("RACHELI_NOTIFICATION_EMAIL") or "racheli@nimbusip.com").strip()
HOT_FIELD_REPORT_CUSTOMER_EMAIL = (os.environ.get("HOT_FIELD_REPORT_CUSTOMER_EMAIL") or NASTIA_NOTIFICATION_EMAIL).strip()
NIMBUS_LOGO_PATH = next((
    path for path in [
        os.path.join(app.static_folder or "template", "brand", "nimbus-logo-pdf.png"),
        os.path.join(app.static_folder or "template", "brand", "nimbus-logo.png"),
    ]
    if os.path.exists(path)
), os.path.join(app.static_folder or "template", "brand", "nimbus-logo.png"))
PAIS_NOTIFICATION_FROM = (
    os.environ.get("PAIS_NOTIFICATION_FROM")
    or os.environ.get("NASTIA_NOTIFICATION_FROM")
    or ""
).strip()
PAIS_CALENDAR_GUEST_EMAILS = {
    "גולן": "golan@nimbusip.com",
    "אסף": "assafh@nimbusip.com",
    "מוסטפה.ח": "pelecom2016@gmail.com",
    "מוסטפה.א": "mostpc55@gmail.com",
    "איציק": "isaace@nimbusip.com",
    "זורה": "zura@nimbusip.com",
}
SMTP_HOST = (os.environ.get("SMTP_HOST") or "").strip()
SMTP_PORT = int((os.environ.get("SMTP_PORT") or "587").strip())
SMTP_USERNAME = (os.environ.get("SMTP_USERNAME") or "").strip()
SMTP_PASSWORD = (os.environ.get("SMTP_PASSWORD") or "").strip()
SMTP_FROM = (os.environ.get("SMTP_FROM") or SMTP_USERNAME or f"no-reply@{ALLOWED_EMAIL_DOMAIN}").strip()
SMTP_USE_TLS = env_flag("SMTP_USE_TLS", True)
SMTP_USE_SSL = env_flag("SMTP_USE_SSL", False)
TICKET_BOARD_DEFAULTS = {
    "support": {
        "slug": "support",
        "name": "נימבוס",
        "icon_path": "https://tel1.nimbusip.com/themes/default/images/logo.png",
        "route_path": "/support-tickets",
        "workflow": "coordination",
        "paste_template": "",
        "report_enabled": True,
        "sort_order": 1,
    },
    "pais": {
        "slug": "pais",
        "name": "מפעל הפיס",
        "icon_path": "/picture/pais.png",
        "route_path": "/pais-tickets",
        "workflow": "coordination",
        "paste_template": "pais",
        "report_enabled": True,
        "sort_order": 2,
    },
    "hot-kiryot": {
        "slug": "hot-kiryot",
        "name": "הוט קריאות",
        "icon_path": "https://hot.nimbusip.com/themes/default/images/logo.png",
        "route_path": "/hot-kiryot-tickets",
        "workflow": "coordination",
        "paste_template": "hot-kiryot",
        "report_enabled": True,
        "sort_order": 3,
    },
}
SERVICE_ACTIVITY = {
    "configuration": {},
    "sms": {},
    "bot": {},
    "recordings": {},
    "f2m": {},
    "recording_storage": {},
    "human_service": {},
    "support_tickets": {},
    "pais_tickets": {},
    "hot_tickets": {},
    "nastia_tickets": {},
}


def ensure_log_file():
    log_path = app_log_path(os.path.basename(LOG_FILE))
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    if not os.path.exists(log_path):
        with open(log_path, "a", encoding="utf-8") as f:
            f.write("")


def append_log(customers):
    """
    customers: list of dicts with keys: name, domain, did
    """
    ensure_log_file()
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_path = app_log_path(os.path.basename(LOG_FILE))
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"=== {ts} | Status -> {STATUS_DONE} | Count: {len(customers)} ===\n")
        f.write("׳©׳ ׳׳§׳•׳—\tDomain\tDID\n")
        for c in customers:
            name = (c.get("name") or "").strip()
            domain = (c.get("domain") or "").strip()
            did = (c.get("did") or "").strip()
            f.write(f"{name}\t{domain}\t{did}\n")
        f.write("\n")


def ensure_support_log_file():
    log_path = support_log_path()
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    if not os.path.exists(log_path):
        with open(log_path, "a", encoding="utf-8") as f:
            f.write("")


def israel_now():
    return datetime.now(ZoneInfo("Asia/Jerusalem"))


def support_user_name():
    raw = (session.get("username") or session.get("email") or "").strip()
    local = raw.split("@")[0].lower()
    if local in {"admin", "isaac"}:
        return "Admin"
    if local in {"eugeni", "yevgeni", "evgeni"}:
        return "יבגני"
    if local == "nir":
        return "ניר"
    if local == "golan":
        return "גולן"
    if local in {"asaf", "assafh"}:
        return "אסף"
    if local in {"nastia", "nastya", "nastiya"}:
        return "נסטיה"
    return raw.split("@")[0] or "Admin"


def support_user_is_admin():
    role = (session.get("role") or "").strip().lower()
    if role == "admin":
        return True
    raw = (session.get("username") or session.get("email") or "").strip()
    local = raw.split("@")[0].lower()
    return local in {"admin", "isaac"}


def support_user_is_assigned_technician():
    return (session.get("role") or "").strip().lower() == "assigned_technician"


def assigned_technician_allowed_statuses():
    return {"בוצע", "נכשל"}


def normalize_ticket_status(board_slug, status):
    normalized_board = (board_slug or "").strip().lower()
    raw_status = str(status or "").strip()
    if not raw_status:
        return "ממתין" if board_supports_coordination(normalized_board) else "Waiting"
    if raw_status in COORDINATION_PENDING_ALIASES:
        return COORDINATION_PENDING_STATUS
    if normalized_board == "support":
        if raw_status == "Waiting":
            return "ממתין"
        if raw_status == "Done":
            return "בוצע"
    return raw_status


def status_is_coordination_pending(status):
    return normalize_ticket_status("pais", status) == COORDINATION_PENDING_STATUS


def ticket_owner_name(ticket):
    ticket = ticket or {}
    details = ticket.get("details") or {}
    if board_supports_coordination(ticket.get("board_slug")):
        return (details.get("coordinated_worker") or "").strip()
    return (ticket.get("assigned_to") or "").strip()


def assigned_technician_can_access_ticket(ticket, actor_name=None):
    actor_name = (actor_name or support_user_name()).strip()
    return (
        support_user_is_assigned_technician()
        and ticket_owner_name(ticket) == actor_name
    )


def normalize_support_ticket(ticket):
    ticket = dict(ticket or {})
    ticket["id"] = int(ticket.get("id") or 0)
    ticket["ticket_id"] = f"#{ticket['id']:04d}"
    ticket.setdefault("board_slug", "support")
    ticket["status"] = normalize_ticket_status(ticket.get("board_slug"), ticket.get("status"))
    ticket.setdefault("assigned_to", "")
    ticket.setdefault("solution", "")
    ticket.setdefault("priority", "Medium")
    ticket.setdefault("details", {})
    ticket.setdefault("attachments", [])
    ticket.setdefault("updates", [])
    ticket["created_at_display"] = (ticket.get("created_at_display") or "").strip() or format_support_ticket_datetime(ticket.get("created_at"))
    latest_edit_at = latest_ticket_update_at(ticket)
    if latest_edit_at:
        ticket["last_edited_at"] = latest_edit_at.isoformat(timespec="seconds")
        ticket["last_edited_at_display"] = format_support_ticket_datetime(latest_edit_at)
    else:
        ticket.setdefault("last_edited_at", "")
        ticket.setdefault("last_edited_at_display", "")
    ticket["list_timestamp_display"] = ticket.get("last_edited_at_display") or ticket.get("created_at_display") or ""
    return ticket


def support_ticket_is_done(ticket):
    return normalize_ticket_status(ticket.get("board_slug"), ticket.get("status")) in {"Done", "בוצע", "נכשל"}


def support_ticket_is_open(ticket):
    return not support_ticket_is_done(ticket)


def normalize_allowed_pages(values):
    if not values:
        return sorted(FULL_ACCESS_PAGES)
    if isinstance(values, str):
        values = [values]
    normalized = {str(value).strip().lower() for value in values if str(value).strip()}
    if not normalized:
        return sorted(FULL_ACCESS_PAGES)
    if "all" in normalized:
        return sorted(FULL_ACCESS_PAGES)
    # Backfill newly added ticket boards for users whose stored allowed_pages
    # were saved before these board keys existed.
    if normalized.intersection({"support_tickets", "pais_tickets", "nastia_tickets", "hot_tickets"}):
        normalized.add("hot_tickets")
    return sorted(normalized)


def allowed_pages_for_role(role):
    normalized_role = (role or "").strip().lower()
    if normalized_role == "tickets_only":
        return sorted(TICKETS_ONLY_ALLOWED_PAGES)
    if normalized_role == "assigned_technician":
        return ["hot_tickets", "pais_tickets", "support_tickets"]
    return sorted(FULL_ACCESS_PAGES)


def allowed_pages_for_current_user():
    return set(normalize_allowed_pages(session.get("allowed_pages")))


def user_can_access_page(page_key):
    return (page_key or "").strip().lower() in allowed_pages_for_current_user()


def first_allowed_route():
    allowed = allowed_pages_for_current_user()
    if support_user_is_assigned_technician():
        if "pais_tickets" in allowed:
            return url_for("pais_tickets_page")
        if "hot_tickets" in allowed:
            return url_for("hot_kiryot_tickets_page")
        if "support_tickets" in allowed:
            return url_for("support_tickets_page")
    if "home" in allowed:
        return url_for("home")
    if "support_tickets" in allowed:
        return url_for("support_tickets_page")
    if "pais_tickets" in allowed:
        return url_for("pais_tickets_page")
    if "hot_tickets" in allowed:
        return url_for("hot_kiryot_tickets_page")
    if "configuration" in allowed:
        return url_for("configuration_page")
    return url_for("home")


def support_page_key(board_slug=None, queue_slug=None):
    normalized_queue = (queue_slug or "").strip().lower()
    if normalized_queue == "nastia":
        return "nastia_tickets"
    normalized_board = (board_slug or "support").strip().lower()
    if normalized_board == "pais":
        return "pais_tickets"
    if normalized_board == "hot-kiryot":
        return "hot_tickets"
    return "support_tickets"


def route_page_key(path):
    normalized_path = (path or "").strip().lower()
    if normalized_path in {"", "/"}:
        return None
    if normalized_path.startswith("/support-ticket-attachment"):
        return "support_tickets"
    if normalized_path == "/support-tickets-data":
        return support_page_key(request.args.get("board"), request.args.get("queue"))
    if normalized_path == "/support-tickets-create":
        return support_page_key(request.form.get("board_slug"))
    if normalized_path in {
        "/support-tickets-update",
        "/support-tickets-attachments",
        "/support-tickets-attachment-delete",
        "/support-tickets-delete",
    }:
        payload = request.get_json(silent=True) if request.is_json else None
        ticket_id = ""
        board_slug = ""
        queue_slug = ""
        if isinstance(payload, dict):
            ticket_id = payload.get("ticket_id") or ""
            board_slug = payload.get("board_slug") or ""
            queue_slug = payload.get("source_ticket_queue") or ""
        else:
            ticket_id = request.form.get("ticket_id") or ""
            board_slug = request.form.get("board_slug") or ""
            queue_slug = request.form.get("queue") or ""
        ticket = find_support_ticket(load_support_tickets(), ticket_id) if ticket_id else None
        if ticket:
            board_slug = ticket.get("board_slug") or board_slug
        return support_page_key(board_slug, queue_slug)
    if normalized_path.startswith("/support-tickets"):
        return "support_tickets"
    if normalized_path.startswith("/pais-tickets"):
        return "pais_tickets"
    if normalized_path.startswith("/hot-kiryot-tickets"):
        return "hot_tickets"
    if normalized_path.startswith("/nastia-tickets"):
        return "nastia_tickets"
    if normalized_path.startswith("/dashboard-data") or normalized_path == "/home":
        return "home"
    if normalized_path.startswith("/configuration"):
        return "configuration"
    if normalized_path.startswith("/sms"):
        return "sms"
    if normalized_path.startswith("/bot"):
        return "bot"
    if normalized_path.startswith("/f2m"):
        return "f2m"
    if normalized_path.startswith("/recording-storage"):
        return "recording_storage"
    if normalized_path.startswith("/human-service"):
        return "human_service"
    if normalized_path.startswith("/record"):
        return "record"
    if normalized_path.startswith("/features-report"):
        return "features_report"
    return None


@app.before_request
def enforce_page_access():
    if not session.get("logged_in"):
        return None
    page_key = route_page_key(request.path)
    if not page_key or user_can_access_page(page_key):
        return None
    if request.path.endswith("-data") or request.method != "GET" or request.path.startswith("/support-ticket-attachment"):
        return api_error("Access denied", 403, "access_denied")
    return redirect(first_allowed_route())


def pais_ticket_is_coordination(ticket):
    if not board_supports_coordination((ticket.get("board_slug") or "").strip().lower()):
        return False
    details = ticket.get("details") or {}
    return (
        status_is_coordination_pending(ticket.get("status"))
        or bool((details.get("coordinated_worker") or "").strip())
        or bool((details.get("visit_date") or "").strip())
        or bool((details.get("visit_hour_from") or "").strip())
        or bool((details.get("visit_hour_to") or "").strip())
    )


def supabase_ticketing_enabled():
    return bool(SUPABASE_URL and SUPABASE_KEY)


def normalize_supabase_url(url):
    cleaned = (url or "").strip().rstrip("/")
    if cleaned.endswith("/rest/v1"):
        return cleaned[:-8]
    return cleaned


SUPABASE_URL = normalize_supabase_url(_RAW_SUPABASE_URL)


def default_ticket_boards():
    return [
        dict(board)
        for board in sorted(TICKET_BOARD_DEFAULTS.values(), key=lambda item: item["sort_order"])
    ]


def get_ticket_board(board_slug):
    board = TICKET_BOARD_DEFAULTS.get((board_slug or "").strip().lower())
    if board:
        return dict(board)
    return dict(TICKET_BOARD_DEFAULTS["support"])


def board_supports_coordination(board_slug):
    return get_ticket_board(board_slug).get("workflow") == "coordination"


def board_has_coordination_report(board_slug):
    return bool(get_ticket_board(board_slug).get("report_enabled"))


def board_statuses(board_slug):
    normalized_board = (board_slug or "").strip().lower()
    if normalized_board == "support":
        return PAIS_STATUSES
    return PAIS_STATUSES if board_supports_coordination(board_slug) else SUPPORT_STATUSES


def board_page_key(board_slug):
    normalized_board_slug = (board_slug or "").strip().lower()
    if normalized_board_slug == "pais":
        return "pais_tickets"
    if normalized_board_slug == "hot-kiryot":
        return "hot_tickets"
    return "support_tickets"


def support_page_key(board_slug, queue_slug=""):
    normalized_queue = (queue_slug or "").strip().lower()
    if normalized_queue == "nastia":
        return "nastia_tickets"
    return board_page_key(board_slug)


def _supabase_headers(prefer=None):
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
    }
    if prefer:
        headers["Prefer"] = prefer
    return headers


def _supabase_error_message(response):
    try:
        payload = response.json()
    except ValueError:
        return response.text or f"Supabase request failed with status {response.status_code}"
    return (
        payload.get("message")
        or payload.get("details")
        or payload.get("hint")
        or f"Supabase request failed with status {response.status_code}"
    )


def _supabase_request(method, path, *, params=None, json_body=None, prefer=None):
    response = requests.request(
        method,
        f"{SUPABASE_URL}/rest/v1/{path.lstrip('/')}",
        headers=_supabase_headers(prefer=prefer),
        params=params,
        json=json_body,
        timeout=20,
    )
    if response.status_code >= 400:
        raise RuntimeError(_supabase_error_message(response))
    return response


def supabase_storage_enabled():
    return bool(SUPABASE_URL and SUPABASE_KEY and SUPABASE_STORAGE_BUCKET)


def running_on_vercel():
    return bool((os.environ.get("VERCEL") or "").strip())


def app_log_dir():
    if running_on_vercel():
        return os.path.join(tempfile.gettempdir(), "app_logs")
    return LOG_DIR


def app_log_path(filename):
    return os.path.join(app_log_dir(), filename)


def support_log_path():
    if running_on_vercel():
        return app_log_path(os.path.basename(SUPPORT_LOG_FILE))
    return SUPPORT_LOG_FILE


_INFORU_LOG_TABLE_CACHE = None


def normalize_did_value(value):
    return re.sub(r"\D", "", str(value or ""))


def supabase_inforu_log_enabled():
    return bool(SUPABASE_URL and SUPABASE_KEY and INFORU_LOG_TABLE and INFORU_LOG_DID_COLUMN and INFORU_LOG_SENT_AT_COLUMN)


def inforu_log_table_candidates():
    candidates = []
    for table_name in (INFORU_LOG_TABLE, "inforu_logs", "inforu_log"):
        table_name = (table_name or "").strip()
        if table_name and table_name not in candidates:
            candidates.append(table_name)
    return candidates


def resolve_inforu_log_table_name():
    global _INFORU_LOG_TABLE_CACHE
    if _INFORU_LOG_TABLE_CACHE:
        return _INFORU_LOG_TABLE_CACHE

    last_error = None
    for table_name in inforu_log_table_candidates():
        try:
            _supabase_request(
                "GET",
                table_name,
                params={
                    "select": f"{INFORU_LOG_DID_COLUMN},{INFORU_LOG_SENT_AT_COLUMN}",
                    "limit": "1",
                    "order": f"{INFORU_LOG_SENT_AT_COLUMN}.desc",
                },
            )
            _INFORU_LOG_TABLE_CACHE = table_name
            return table_name
        except Exception as exc:
            last_error = exc

    raise RuntimeError(last_error or "Inforu Supabase log table is not available")


def inforu_log_dir():
    if running_on_vercel():
        return os.path.join(tempfile.gettempdir(), "did_inforu")
    return "did_inforu"


def inforu_log_path():
    return os.path.join(inforu_log_dir(), INFORU_LOG_FILENAME)


def read_local_inforu_log_text():
    path = inforu_log_path()

    if not os.path.exists(path):
        fallback_dir = inforu_log_dir()
        if os.path.isdir(fallback_dir):
            txt_files = [f for f in os.listdir(fallback_dir) if f.lower().endswith(".txt")]
            if txt_files:
                path = os.path.join(fallback_dir, txt_files[0])
            else:
                return ""
        else:
            return ""

    with open(path, "rb") as f:
        raw = f.read()

    try:
        content = raw.decode("utf-8")
    except UnicodeDecodeError:
        content = raw.decode("cp1255", errors="replace")

    if "׳" in content:
        try:
            repaired = content.encode("latin1", errors="ignore").decode("utf-8", errors="ignore")
            if repaired.strip():
                content = repaired
        except Exception:
            pass

    return content


def format_sent_date(sent_at):
    raw = str(sent_at or "").strip()
    if not raw:
        return ""
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).strftime("%d.%m.%Y")
    except Exception:
        return raw


def parse_local_inforu_log_entries():
    text = read_local_inforu_log_text()
    if not text.strip():
        return []

    entries = []
    matches = list(re.finditer(r"==(\d{2}\.\d{2}\.\d{4})==", text))
    if not matches:
        for did in re.findall(r"0\d{8,9}", text):
            entries.append({
                "did": did,
                "sent_at": "",
                "sent_date": "",
                "source": "local",
            })
        return entries

    for index, match in enumerate(matches):
        sent_date = match.group(1)
        block_start = match.end()
        block_end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        block = text[block_start:block_end]
        try:
            sent_at = datetime.strptime(sent_date, "%d.%m.%Y").isoformat()
        except Exception:
            sent_at = ""
        for did in re.findall(r"0\d{8,9}", block):
            entries.append({
                "did": did,
                "sent_at": sent_at,
                "sent_date": sent_date,
                "source": "local",
            })

    return entries


def load_supabase_inforu_log_entries():
    if not supabase_inforu_log_enabled():
        return []

    table_name = resolve_inforu_log_table_name()
    rows = _supabase_request(
        "GET",
        table_name,
        params={
            "select": f"{INFORU_LOG_DID_COLUMN},{INFORU_LOG_SENT_AT_COLUMN}",
            "order": f"{INFORU_LOG_SENT_AT_COLUMN}.desc",
            "limit": "5000",
        },
    ).json()

    entries = []
    for row in rows if isinstance(rows, list) else []:
        did = normalize_did_value(row.get(INFORU_LOG_DID_COLUMN))
        if not did:
            continue
        sent_at = str(row.get(INFORU_LOG_SENT_AT_COLUMN) or "").strip()
        entries.append({
            "did": did,
            "sent_at": sent_at,
            "sent_date": format_sent_date(sent_at),
            "source": "supabase",
        })
    return entries


def sort_inforu_log_entries(entries):
    def sort_key(entry):
        raw = str(entry.get("sent_at") or "").strip()
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            return (dt, entry.get("did") or "")
        except Exception:
            return (datetime.min, entry.get("did") or "")

    return sorted(entries, key=sort_key, reverse=True)


def collect_inforu_log_entries():
    entries = []
    supabase_error = None

    if supabase_inforu_log_enabled():
        try:
            entries.extend(load_supabase_inforu_log_entries())
        except Exception as exc:
            supabase_error = exc

    entries.extend(parse_local_inforu_log_entries())

    latest_by_did = {}
    for entry in entries:
        did = normalize_did_value(entry.get("did"))
        if not did:
            continue
        normalized = {
            "did": did,
            "sent_at": str(entry.get("sent_at") or "").strip(),
            "sent_date": str(entry.get("sent_date") or "").strip(),
            "source": entry.get("source") or "local",
        }
        current = latest_by_did.get(did)
        if current is None:
            latest_by_did[did] = normalized
            continue

        current_sent_at = current.get("sent_at") or ""
        next_sent_at = normalized.get("sent_at") or ""
        if next_sent_at >= current_sent_at:
            if current.get("source") == "supabase" and normalized.get("source") != "supabase":
                normalized["source"] = "supabase"
            latest_by_did[did] = normalized

    merged = sort_inforu_log_entries(list(latest_by_did.values()))
    return merged, supabase_error


def inforu_sent_numbers():
    entries, _ = collect_inforu_log_entries()
    return {entry["did"] for entry in entries if entry.get("did")}


def append_local_inforu_log_entries(entries):
    entries = [entry for entry in entries if normalize_did_value(entry.get("did"))]
    if not entries:
        return

    log_dir = inforu_log_dir()
    os.makedirs(log_dir, exist_ok=True)
    path = inforu_log_path()

    grouped = {}
    for entry in sort_inforu_log_entries(entries):
        sent_date = entry.get("sent_date") or format_sent_date(entry.get("sent_at")) or datetime.now().strftime("%d.%m.%Y")
        grouped.setdefault(sent_date, []).append(normalize_did_value(entry.get("did")))

    with open(path, "a", encoding="utf-8") as f:
        for sent_date, dids in grouped.items():
            numbers_str = " , ".join(dict.fromkeys(dids))
            block = f"""
=={sent_date}==
\u05e9\u05dc\u05d5\u05dd \u05e8\u05d1,
\u05d0\u05e0\u05d5 \u05d7\u05d1\u05e8\u05ea \u05e0\u05d9\u05de\u05d1\u05d5\u05e1 \u05d8\u05dc\u05e7\u05d5\u05dd \u05d1\u05e2\"\u05de (\u05d7.\u05e4 514684125), \u05de\u05d0\u05e9\u05e8\u05d9\u05dd \u05d1\u05d6\u05d0\u05ea \u05db\u05d9 \u05de\u05e1\u05e4\u05e8\u05d9 \u05d4\u05e7\u05d5 \u05d4\u05d1\u05d0\u05d9\u05dd:
{numbers_str}
\u05d4\u05dd \u05d1\u05d1\u05e2\u05dc\u05d5\u05ea\u05e0\u05d5/\u05d1\u05d1\u05e2\u05dc\u05d5\u05ea \u05dc\u05e7\u05d5\u05d7 \u05e9\u05dc\u05e0\u05d5 \u05d5\u05d0\u05d9\u05e0\u05dd \u05de\u05ea\u05d7\u05d6\u05d9\u05dd.
\u05e0\u05e9\u05de\u05d7 \u05dc\u05d1\u05d9\u05e6\u05d5\u05e2 \u05d0\u05d9\u05de\u05d5\u05ea \u05de\u05e1\u05e4\u05e8 \u05dc\u05e6\u05d5\u05e8\u05da \u05e7\u05d9\u05d3\u05d5\u05dd \u05d4\u05e7\u05de\u05ea \u05d4\u05e9\u05d9\u05e8\u05d5\u05ea.
\u05ea\u05d5\u05d3\u05d4

"""
            f.write(block)


def save_inforu_log_entries(entries):
    clean_entries = []
    for entry in entries:
        did = normalize_did_value(entry.get("did"))
        if not did:
            continue
        sent_at = str(entry.get("sent_at") or "").strip() or datetime.now(timezone.utc).isoformat()
        clean_entries.append({
            "did": did,
            "sent_at": sent_at,
            "sent_date": format_sent_date(sent_at),
            "source": entry.get("source") or "supabase",
        })

    if not clean_entries:
        return

    supabase_error = None
    if supabase_inforu_log_enabled():
        try:
            table_name = resolve_inforu_log_table_name()
            payload = []
            for entry in clean_entries:
                payload.append({
                    INFORU_LOG_DID_COLUMN: entry["did"],
                    INFORU_LOG_SENT_AT_COLUMN: entry["sent_at"],
                })
            _supabase_request(
                "POST",
                table_name,
                json_body=payload,
                prefer="return=minimal",
            )
        except Exception as exc:
            supabase_error = exc
            print(f"Inforu Supabase log warning: {exc}")

    append_local_inforu_log_entries(clean_entries)

    if supabase_inforu_log_enabled() and supabase_error:
        raise supabase_error


def build_inforu_log_text(entries):
    lines = []
    for entry in sort_inforu_log_entries(entries):
        sent_date = entry.get("sent_date") or format_sent_date(entry.get("sent_at")) or "-"
        source = entry.get("source") or "local"
        lines.append(f"{sent_date}\t{entry.get('did') or ''}\t{source}")
    return "\n".join(lines)


def _supabase_storage_headers(*, content_type=None, extra_headers=None):
    headers = _supabase_headers()
    if content_type:
        headers["Content-Type"] = content_type
    if extra_headers:
        headers.update(extra_headers)
    return headers


def _supabase_storage_url(path):
    return f"{SUPABASE_URL}/storage/v1/{path.lstrip('/')}"


def _supabase_storage_object_path(ticket_folder, saved_name):
    object_parts = [part for part in (SUPABASE_STORAGE_PREFIX, ticket_folder, saved_name) if part]
    return "/".join(object_parts)


def upload_supabase_storage_object(object_path, file_storage, content_type):
    if not supabase_storage_enabled():
        raise RuntimeError("SUPABASE_STORAGE_BUCKET is not configured")
    file_storage.stream.seek(0)
    response = requests.post(
        _supabase_storage_url(f"object/{SUPABASE_STORAGE_BUCKET}/{quote(object_path, safe='/')}"),
        headers=_supabase_storage_headers(
            content_type=content_type,
            extra_headers={"x-upsert": "false", "cache-control": "3600"},
        ),
        data=file_storage.stream.read(),
        timeout=20,
    )
    if response.status_code >= 400:
        raise RuntimeError(_supabase_error_message(response))
    return response


def delete_supabase_storage_object(object_path):
    if not supabase_storage_enabled():
        return
    response = requests.delete(
        _supabase_storage_url(f"object/{SUPABASE_STORAGE_BUCKET}"),
        headers=_supabase_storage_headers(content_type="application/json"),
        json={"prefixes": [object_path]},
        timeout=20,
    )
    if response.status_code >= 400 and response.status_code != 404:
        raise RuntimeError(_supabase_error_message(response))


def download_supabase_storage_object(object_path):
    if not supabase_storage_enabled():
        return None
    response = requests.get(
        _supabase_storage_url(f"object/authenticated/{SUPABASE_STORAGE_BUCKET}/{quote(object_path, safe='/')}"),
        headers=_supabase_storage_headers(),
        timeout=20,
    )
    if response.status_code == 404:
        return None
    if response.status_code >= 400:
        raise RuntimeError(_supabase_error_message(response))
    return response


def load_ticket_boards():
    if not supabase_ticketing_enabled():
        return default_ticket_boards()

    try:
        response = _supabase_request(
            "GET",
            "ticket_boards",
            params={
                "select": "slug,name,icon_path,route_path,sort_order",
                "order": "sort_order.asc",
            },
        )
        rows = response.json()
        if not isinstance(rows, list) or not rows:
            return default_ticket_boards()
        merged_rows = []
        seen_slugs = set()
        for row in rows:
            board_slug = (row.get("slug") or "").strip().lower()
            default_board = TICKET_BOARD_DEFAULTS.get(board_slug, {})
            merged_rows.append({**default_board, **row})
            if board_slug:
                seen_slugs.add(board_slug)
        for board_slug, default_board in TICKET_BOARD_DEFAULTS.items():
            if board_slug not in seen_slugs:
                merged_rows.append(dict(default_board))
        return sorted(merged_rows, key=lambda item: item.get("sort_order", 999))
    except Exception:
        return default_ticket_boards()


def _merge_supabase_ticket_rows(ticket_rows, attachments, updates):
    attachments_by_ticket = {}
    for attachment in attachments:
        ticket_id = int(attachment.get("ticket_id") or 0)
        attachments_by_ticket.setdefault(ticket_id, []).append({
            "original_name": attachment.get("original_name") or "",
            "saved_name": attachment.get("saved_name") or "",
            "folder": attachment.get("folder") or "",
            "url": attachment.get("url") or "",
        })

    updates_by_ticket = {}
    for update in updates:
        ticket_id = int(update.get("ticket_id") or 0)
        updates_by_ticket.setdefault(ticket_id, []).append({
            "at": update.get("changed_at") or "",
            "actor": update.get("actor") or "",
            "field": update.get("field_name") or "",
            "from": update.get("old_value") or "",
            "to": update.get("new_value") or "",
        })

    merged = []
    for row in ticket_rows:
        ticket_id = int(row.get("id") or 0)
        merged.append(normalize_support_ticket({
            **row,
            "attachments": attachments_by_ticket.get(ticket_id, []),
            "updates": updates_by_ticket.get(ticket_id, []),
        }))
    return merged


def _load_supabase_tickets(board_slug=None):
    params = {
        "select": "id,board_slug,created_at,created_at_display,creator,ticket_type,service_type,domain,priority,description,solution,status,assigned_to,details",
        "order": "id.desc",
    }
    if board_slug:
        params["board_slug"] = f"eq.{board_slug}"

    response = _supabase_request("GET", "support_tickets", params=params)
    ticket_rows = response.json()
    if not ticket_rows:
        return []

    ticket_ids = [str(int(ticket.get("id") or 0)) for ticket in ticket_rows if int(ticket.get("id") or 0) > 0]
    id_filter = f"in.({','.join(ticket_ids)})"
    attachments = []
    try:
        attachments = _supabase_request(
            "GET",
            "ticket_attachments",
            params={
                "select": "ticket_id,original_name,saved_name,folder,url",
                "ticket_id": id_filter,
                "order": "id.asc",
            },
        ).json()
    except Exception as exc:
        print(f"Supabase ticket attachments warning for board {board_slug or 'all'}: {exc}")

    updates = []
    try:
        updates = _supabase_request(
            "GET",
            "ticket_updates",
            params={
                "select": "ticket_id,changed_at,actor,field_name,old_value,new_value",
                "ticket_id": id_filter,
                "order": "id.asc",
            },
        ).json()
    except Exception as exc:
        print(f"Supabase ticket updates warning for board {board_slug or 'all'}: {exc}")

    return _merge_supabase_ticket_rows(ticket_rows, attachments, updates)


def load_support_tickets(board_slug=None):
    if supabase_ticketing_enabled():
        try:
            return _load_supabase_tickets(board_slug=board_slug)
        except Exception as exc:
            print(f"Supabase ticket load warning for board {board_slug or 'all'}: {exc}")

    ensure_support_log_file()
    tickets = []
    with open(support_log_path(), "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                tickets.append(normalize_support_ticket(json.loads(line)))
            except json.JSONDecodeError:
                continue
    if board_slug:
        tickets = [ticket for ticket in tickets if ticket.get("board_slug") == board_slug]
    return tickets


def save_support_tickets(tickets):
    ensure_support_log_file()
    with open(support_log_path(), "w", encoding="utf-8") as f:
        for ticket in tickets:
            f.write(json.dumps(ticket, ensure_ascii=False) + "\n")


def next_support_ticket_id():
    if supabase_ticketing_enabled():
        try:
            response = _supabase_request(
                "GET",
                "support_tickets",
                params={"select": "id", "order": "id.desc", "limit": "1"},
            )
            rows = response.json()
            return int(rows[0]["id"]) + 1 if rows else 1
        except Exception:
            pass
    tickets = load_support_tickets()
    return max([int(ticket.get("id") or 0) for ticket in tickets] or [0]) + 1


def support_ticket_stats(tickets):
    return {
        "all": len(tickets),
        "waiting": len([t for t in tickets if support_ticket_is_open(t)]),
        "done": len([t for t in tickets if support_ticket_is_done(t)]),
        "coordination": len([t for t in tickets if status_is_coordination_pending(t.get("status"))]),
        "unassigned": len([t for t in tickets if not t.get("assigned_to")]),
    }


def parse_ticket_created_at(ticket):
    return parse_support_ticket_datetime(ticket.get("created_at"))


def parse_support_ticket_datetime(value):
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=ZoneInfo("Asia/Jerusalem"))
    return parsed


def format_support_ticket_datetime(value):
    parsed = value if isinstance(value, datetime) else parse_support_ticket_datetime(value)
    if not parsed:
        return ""
    return parsed.astimezone(ZoneInfo("Asia/Jerusalem")).strftime("%d/%m/%Y %H:%M")


def latest_ticket_update_at(ticket):
    latest = parse_support_ticket_datetime(ticket.get("last_edited_at"))
    for update in ticket.get("updates") or []:
        parsed = parse_support_ticket_datetime(update.get("at"))
        if parsed and (latest is None or parsed > latest):
            latest = parsed
    return latest


def parse_date_filter(value, *, end_of_day=False):
    raw = (value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.strptime(raw, "%Y-%m-%d")
    except ValueError:
        return None
    zone = ZoneInfo("Asia/Jerusalem")
    if end_of_day:
        return parsed.replace(hour=23, minute=59, second=59, tzinfo=zone)
    return parsed.replace(tzinfo=zone)


def filter_tickets_by_created_range(tickets, date_from=None, date_to=None):
    if not date_from and not date_to:
        return list(tickets)
    filtered = []
    for ticket in tickets:
        created_at = parse_ticket_created_at(ticket)
        if not created_at:
            continue
        if date_from and created_at < date_from:
            continue
        if date_to and created_at > date_to:
            continue
        filtered.append(ticket)
    return filtered


def parse_visit_hour(value):
    raw = (value or "").strip()
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%H:%M")
    except ValueError:
        return None


def visit_slot_is_valid(visit_hour_from, visit_hour_to):
    start = parse_visit_hour(visit_hour_from)
    end = parse_visit_hour(visit_hour_to)
    if not start or not end:
        return False
    if start.minute != 0 or end.minute != 0:
        return False
    if start.hour < VISIT_SLOT_START_HOUR or end.hour > VISIT_SLOT_END_HOUR:
        return False
    return (end - start) == timedelta(hours=1)


def coordination_slot_conflicts(ticket_id, coordinated_worker, visit_date, visit_hour_from, visit_hour_to):
    if not coordinated_worker or not visit_date or not visit_hour_from or not visit_hour_to:
        return None
    for ticket in load_support_tickets():
        if not board_supports_coordination(ticket.get("board_slug")):
            continue
        if int(ticket.get("id") or 0) == int(ticket_id or 0):
            continue
        details = ticket.get("details") or {}
        if (details.get("coordinated_worker") or "").strip() != coordinated_worker:
            continue
        if (details.get("visit_date") or "").strip() != visit_date:
            continue
        if (details.get("visit_hour_from") or "").strip() != visit_hour_from:
            continue
        if (details.get("visit_hour_to") or "").strip() != visit_hour_to:
            continue
        return ticket
    return None


def pais_report_range(period, date_from_raw=None, date_to_raw=None):
    custom_from = parse_date_filter(date_from_raw, end_of_day=False)
    custom_to = parse_date_filter(date_to_raw, end_of_day=True)
    if custom_from or custom_to:
        return custom_from, custom_to

    now = israel_now()
    if period == "weekly":
        start = (now - timedelta(days=6)).replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "monthly":
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = now.replace(hour=23, minute=59, second=59, microsecond=0)
    return start, end


def build_ticket_board_report(tickets, status_filter="", period="daily", date_from_raw="", date_to_raw=""):
    report_from, report_to = pais_report_range(period, date_from_raw, date_to_raw)
    period_filtered = filter_tickets_by_created_range(tickets, report_from, report_to)
    filtered = list(period_filtered)
    if status_filter:
        filtered = [ticket for ticket in filtered if ticket.get("status") == status_filter]

    leaderboard = []
    for user in TECHNICIAN_SUPPORT_USERS:
        user_tickets = [ticket for ticket in filtered if ticket_owner_name(ticket) == user]
        done_count = len([ticket for ticket in user_tickets if support_ticket_is_done(ticket)])
        waiting_count = len([ticket for ticket in user_tickets if support_ticket_is_open(ticket)])
        coordination_count = len([ticket for ticket in user_tickets if status_is_coordination_pending(ticket.get("status"))])
        total_count = len(user_tickets)
        completion_rate = round((done_count / total_count) * 100, 1) if total_count else 0
        leaderboard.append({
            "user": user,
            "total": total_count,
            "done": done_count,
            "waiting": waiting_count,
            "coordination": coordination_count,
            "completion_rate": completion_rate,
        })
    leaderboard.sort(key=lambda item: (-item["done"], -item["total"], item["user"]))

    return {
        "period": period,
        "date_from": report_from.strftime("%Y-%m-%d") if report_from else "",
        "date_to": report_to.strftime("%Y-%m-%d") if report_to else "",
        "status": status_filter,
        "tickets": filtered,
        "period_done_total": len([ticket for ticket in period_filtered if support_ticket_is_done(ticket)]),
        "summary": {
            "total": len(filtered),
            "done": len([ticket for ticket in filtered if support_ticket_is_done(ticket)]),
            "waiting": len([ticket for ticket in filtered if support_ticket_is_open(ticket)]),
            "coordination": len([ticket for ticket in filtered if status_is_coordination_pending(ticket.get("status"))]),
            "failed": len([ticket for ticket in filtered if ticket.get("status") == "נכשל"]),
            "coordinated": len([ticket for ticket in filtered if ticket.get("status") == "תואם"]),
        },
        "leaderboard": leaderboard,
    }


def save_support_attachment(file_storage, ticket_number, allowed_extensions=None):
    if not file_storage or not file_storage.filename:
        return None

    original = secure_filename(file_storage.filename)
    ext = os.path.splitext(original)[1].lower()
    allowed_extensions = allowed_extensions or SUPPORT_ATTACHMENT_EXTENSIONS
    if ext not in allowed_extensions:
        raise ValueError("Only image files (JPG, PNG, WEBP, GIF) are supported")

    ticket_folder = f"TicketID{ticket_number:04d}"
    timestamp = israel_now().strftime("%Y%m%d%H%M%S%f")
    saved_name = secure_filename(f"{timestamp}_{original}")
    content_type = (file_storage.mimetype or mimetypes.guess_type(original)[0] or "application/octet-stream").strip()

    if supabase_storage_enabled():
        upload_supabase_storage_object(
            _supabase_storage_object_path(ticket_folder, saved_name),
            file_storage,
            content_type,
        )
    else:
        if running_on_vercel():
            raise RuntimeError(
                "Ticket image storage is not configured for Vercel. "
                "Set SUPABASE_STORAGE_BUCKET so attachments can be saved in Supabase Storage."
            )
        folder_path = os.path.join(SUPPORT_SCREEN_DIR, ticket_folder)
        os.makedirs(folder_path, exist_ok=True)
        saved_path = os.path.join(folder_path, saved_name)
        file_storage.save(saved_path)

    return {
        "original_name": file_storage.filename,
        "saved_name": saved_name,
        "folder": ticket_folder,
        "url": f"/support-ticket-attachment/{ticket_folder}/{saved_name}",
    }


def save_support_attachments(attachment_files, ticket_number):
    attachments = []
    for file_storage in attachment_files or []:
        if not file_storage or not file_storage.filename:
            continue
        saved_attachment = save_support_attachment(file_storage, ticket_number)
        if saved_attachment:
            attachments.append(saved_attachment)
    return attachments


def save_generated_support_attachment(content, filename, ticket_number, content_type="application/octet-stream"):
    if not filename:
        raise ValueError("Attachment filename is required")
    generated_file = FileStorage(
        stream=io.BytesIO(content if isinstance(content, (bytes, bytearray)) else bytes(content or b"")),
        filename=filename,
        content_type=content_type,
    )
    return save_support_attachment(generated_file, ticket_number, allowed_extensions=SUPPORT_ATTACHMENT_EXTENSIONS | {".pdf"})


def parse_signature_data_url(signature_data_url, label="חתימה"):
    raw_value = str(signature_data_url or "").strip()
    match = re.fullmatch(r"data:image/(?P<subtype>png|jpeg|jpg);base64,(?P<data>[A-Za-z0-9+/=\s]+)", raw_value, re.IGNORECASE)
    if not match:
        raise ValueError(f"{label} אינה תקינה")
    subtype = match.group("subtype").lower().replace("jpg", "jpeg")
    try:
        image_bytes = base64.b64decode(match.group("data"), validate=True)
    except Exception as exc:
        raise ValueError(f"{label} אינה תקינה") from exc
    if not image_bytes:
        raise ValueError(f"{label} אינה תקינה")
    return image_bytes, subtype


def calculate_work_duration(start_time, end_time):
    start_value = str(start_time or "").strip()
    end_value = str(end_time or "").strip()
    if not re.fullmatch(r"\d{2}:\d{2}", start_value) or not re.fullmatch(r"\d{2}:\d{2}", end_value):
        raise ValueError("יש לבחור שעת התחלה ושעת סיום תקינות")
    start_minutes = int(start_value[:2]) * 60 + int(start_value[3:5])
    end_minutes = int(end_value[:2]) * 60 + int(end_value[3:5])
    if end_minutes <= start_minutes:
        raise ValueError("שעת הסיום חייבת להיות אחרי שעת ההתחלה")
    total_minutes = end_minutes - start_minutes
    hours = total_minutes // 60
    minutes = total_minutes % 60
    return {
        "minutes": total_minutes,
        "label": f"{hours}:{minutes:02d}",
        "decimal_hours": round(total_minutes / 60, 2),
    }


def hot_field_report_attachment_label(ticket, report):
    ticket_label = (ticket.get("ticket_id") or f"#{int(ticket.get('id') or 0):04d}").replace("#", "")
    customer_name = secure_filename((ticket.get("details") or {}).get("customer_name") or "customer") or "customer"
    report_stamp = secure_filename(str(report.get("submitted_at_display") or "").replace("/", "-").replace(":", "-").replace(" ", "_")) or israel_now().strftime("%Y%m%d_%H%M")
    return f"hot-field-report-{ticket_label}-{customer_name}-{report_stamp}.pdf"


def normalize_hot_field_report_line_items(items):
    normalized_items = []
    if isinstance(items, str):
        try:
            items = json.loads(items)
        except json.JSONDecodeError:
            items = []
    if not isinstance(items, list):
        items = []
    for row in items:
        if not isinstance(row, dict):
            continue
        item_name = str(row.get("item_name") or "").strip()
        quantity = str(row.get("quantity") or "").strip()
        notes = str(row.get("notes") or "").strip()
        if not any([item_name, quantity, notes]):
            continue
        if quantity:
            if not quantity.isdigit():
                raise ValueError("כמות חייבת להיות מספר בין 1 ל-100")
            quantity_value = int(quantity)
            if quantity_value < 1 or quantity_value > 100:
                raise ValueError("כמות חייבת להיות מספר בין 1 ל-100")
            quantity = str(quantity_value)
        normalized_items.append({
            "item_name": item_name,
            "quantity": quantity,
            "notes": notes,
        })
    return normalized_items


def hot_field_report_photo_rows(photo_attachments):
    rows = []
    for index, attachment in enumerate(photo_attachments or [], start=1):
        label = str(
            attachment.get("original_name")
            or attachment.get("saved_name")
            or f"Photo {index}"
        ).strip() or f"Photo {index}"
        rows.append((f"צילום {index}", label))
    return rows


def build_hot_field_report_pdf(ticket, report, technician_signature_bytes, customer_signature_bytes):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=16 * mm,
        leftMargin=16 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
    )
    latin_regular_font = get_pdf_font_name("regular", "latin")
    latin_bold_font = get_pdf_font_name("bold", "latin")
    hebrew_regular_font = get_pdf_font_name("regular", "hebrew")
    hebrew_bold_font = get_pdf_font_name("bold", "hebrew")
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "HotFieldReportTitle",
        parent=styles["Normal"],
        fontName=hebrew_bold_font,
        fontSize=18,
        leading=22,
        alignment=TA_RIGHT,
        textColor=colors.HexColor("#1f2f46"),
        spaceAfter=10,
    )
    text_style = ParagraphStyle(
        "HotFieldReportText",
        parent=styles["Normal"],
        fontName=hebrew_regular_font,
        fontSize=11,
        leading=16,
        alignment=TA_RIGHT,
        textColor=colors.black,
    )
    label_style = ParagraphStyle(
        "HotFieldReportLabel",
        parent=styles["Normal"],
        fontName=hebrew_bold_font,
        fontSize=10,
        leading=14,
        alignment=TA_RIGHT,
        textColor=colors.HexColor("#385475"),
    )
    latin_style = ParagraphStyle(
        "HotFieldReportLatin",
        parent=styles["Normal"],
        fontName=latin_bold_font or latin_regular_font,
        fontSize=11,
        leading=16,
        alignment=TA_LEFT,
        textColor=colors.black,
    )
    section_title_style = ParagraphStyle(
        "HotFieldReportSectionTitle",
        parent=styles["Normal"],
        fontName=hebrew_bold_font,
        fontSize=12,
        leading=16,
        alignment=TA_RIGHT,
        textColor=colors.HexColor("#233f65"),
        spaceAfter=4,
    )
    intro_style = ParagraphStyle(
        "HotFieldReportIntro",
        parent=styles["Normal"],
        fontName=hebrew_regular_font,
        fontSize=10.5,
        leading=15,
        alignment=TA_RIGHT,
        textColor=colors.black,
    )
    center_cell_style = ParagraphStyle(
        "HotFieldReportCenterCell",
        parent=text_style,
        alignment=TA_CENTER,
    )

    details = ticket.get("details") or {}
    meta_rows = [
        [
            pdf_paragraph("שם הלקוח בנימבוס", label_style, rtl=True, latin_font_name=latin_bold_font, hebrew_font_name=hebrew_bold_font),
            pdf_paragraph(report.get("nimbus_customer_name") or details.get("customer_name") or details.get("call_number") or "-", text_style, rtl=True, latin_font_name=latin_regular_font, hebrew_font_name=hebrew_regular_font),
        ],
        [
            pdf_paragraph("מספר קריאה", label_style, rtl=True, latin_font_name=latin_bold_font, hebrew_font_name=hebrew_bold_font),
            pdf_paragraph(details.get("call_number") or ticket.get("ticket_id") or "-", latin_style, rtl=False, latin_font_name=latin_regular_font, hebrew_font_name=hebrew_regular_font),
        ],
        [
            pdf_paragraph("שם פרטי", label_style, rtl=True, latin_font_name=latin_bold_font, hebrew_font_name=hebrew_bold_font),
            pdf_paragraph(report.get("contact_first_name") or "-", text_style, rtl=True, latin_font_name=latin_regular_font, hebrew_font_name=hebrew_regular_font),
        ],
        [
            pdf_paragraph("שם משפחה", label_style, rtl=True, latin_font_name=latin_bold_font, hebrew_font_name=hebrew_bold_font),
            pdf_paragraph(report.get("contact_last_name") or "-", text_style, rtl=True, latin_font_name=latin_regular_font, hebrew_font_name=hebrew_regular_font),
        ],
        [
            pdf_paragraph("תפקיד", label_style, rtl=True, latin_font_name=latin_bold_font, hebrew_font_name=hebrew_bold_font),
            pdf_paragraph(report.get("role") or "-", text_style, rtl=True, latin_font_name=latin_regular_font, hebrew_font_name=hebrew_regular_font),
        ],
        [
            pdf_paragraph("כתובת ההתקנה", label_style, rtl=True, latin_font_name=latin_bold_font, hebrew_font_name=hebrew_bold_font),
            pdf_paragraph(report.get("installation_address") or details.get("address") or "-", text_style, rtl=True, latin_font_name=latin_regular_font, hebrew_font_name=hebrew_regular_font),
        ],
        [
            pdf_paragraph("טלפון", label_style, rtl=True, latin_font_name=latin_bold_font, hebrew_font_name=hebrew_bold_font),
            pdf_paragraph(report.get("phone") or "-", latin_style, rtl=False, latin_font_name=latin_regular_font, hebrew_font_name=hebrew_regular_font),
        ],
        [
            pdf_paragraph("הערות", label_style, rtl=True, latin_font_name=latin_bold_font, hebrew_font_name=hebrew_bold_font),
            pdf_paragraph(report.get("customer_notes") or "-", text_style, rtl=True, latin_font_name=latin_regular_font, hebrew_font_name=hebrew_regular_font),
        ],
    ]

    story = []
    if os.path.exists(NIMBUS_LOGO_PATH):
        story.append(Image(NIMBUS_LOGO_PATH, width=32 * mm, height=18 * mm, hAlign="LEFT"))
    story.extend([
        pdf_paragraph("Nimbus Telecom", label_style, rtl=False, latin_font_name=latin_bold_font, hebrew_font_name=hebrew_bold_font),
        Spacer(1, 3),
        pdf_paragraph("טופס אישור קבלת ציוד והתקנה", title_style, rtl=True, latin_font_name=latin_bold_font, hebrew_font_name=hebrew_bold_font),
        Spacer(1, 5),
        pdf_paragraph("למילוי ע\"י נציג / הלקוח", section_title_style, rtl=True, latin_font_name=latin_bold_font, hebrew_font_name=hebrew_bold_font),
    ])

    meta_table = Table(meta_rows, colWidths=[40 * mm, 130 * mm], hAlign="RIGHT")
    meta_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.white),
        ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#d8deea")),
        ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#d8deea")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.extend([
        meta_table,
        Spacer(1, 8),
    ])

    line_items = list(report.get("line_items") or [])
    if line_items:
        story.extend([
            pdf_paragraph(
                "הנני מאשר בזאת כי נמסר לידי הציוד המפורט להלן, ובוצעה התקנתו ע\"י טכנאי מטעם נימבוס:",
                intro_style,
                rtl=True,
                latin_font_name=latin_regular_font,
                hebrew_font_name=hebrew_regular_font,
            ),
            Spacer(1, 6),
        ])
        table_rows = [[
            pdf_paragraph("הערות", label_style, rtl=True, latin_font_name=latin_bold_font, hebrew_font_name=hebrew_bold_font),
            pdf_paragraph("כמות", label_style, rtl=True, latin_font_name=latin_bold_font, hebrew_font_name=hebrew_bold_font),
            pdf_paragraph("שם פריט", label_style, rtl=True, latin_font_name=latin_bold_font, hebrew_font_name=hebrew_bold_font),
        ]]
        for row in line_items:
            table_rows.append([
                pdf_paragraph(row.get("notes") or "-", text_style, rtl=True, latin_font_name=latin_regular_font, hebrew_font_name=hebrew_regular_font),
                pdf_paragraph(row.get("quantity") or "-", center_cell_style, rtl=False, latin_font_name=latin_regular_font, hebrew_font_name=hebrew_regular_font),
                pdf_paragraph(row.get("item_name") or "-", text_style, rtl=True, latin_font_name=latin_regular_font, hebrew_font_name=hebrew_regular_font),
            ])
        items_table = Table(table_rows, colWidths=[74 * mm, 24 * mm, 72 * mm], hAlign="RIGHT")
        items_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f3f7fd")),
            ("BOX", (0, 0), (-1, -1), 0.7, colors.HexColor("#bcc8d7")),
            ("INNERGRID", (0, 0), (-1, -1), 0.45, colors.HexColor("#d8deea")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("RIGHTPADDING", (0, 0), (-1, -1), 7),
            ("LEFTPADDING", (0, 0), (-1, -1), 7),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.extend([
            items_table,
            Spacer(1, 8),
        ])

    story.extend([
        pdf_paragraph("הערות נוספות", section_title_style, rtl=True, latin_font_name=latin_bold_font, hebrew_font_name=hebrew_bold_font),
        pdf_paragraph(report.get("additional_notes") or "-", text_style, rtl=True, latin_font_name=latin_regular_font, hebrew_font_name=hebrew_regular_font),
        Spacer(1, 8),
        pdf_paragraph("צילום אזור עבודה", section_title_style, rtl=True, latin_font_name=latin_bold_font, hebrew_font_name=hebrew_bold_font),
    ])

    photo_rows = hot_field_report_photo_rows(report.get("area_photo_attachments") or [])
    if photo_rows:
        photo_table = Table([
            [
                pdf_paragraph(value, text_style, rtl=True, latin_font_name=latin_regular_font, hebrew_font_name=hebrew_regular_font),
                pdf_paragraph(label, label_style, rtl=True, latin_font_name=latin_bold_font, hebrew_font_name=hebrew_bold_font),
            ]
            for label, value in photo_rows
        ], colWidths=[128 * mm, 42 * mm], hAlign="RIGHT")
        photo_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.white),
            ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#d8deea")),
            ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#d8deea")),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(photo_table)
    else:
        story.append(pdf_paragraph("-", text_style, rtl=True, latin_font_name=latin_regular_font, hebrew_font_name=hebrew_regular_font))

    signature_table = Table([
        [
            pdf_paragraph("חתימת הלקוח", section_title_style, rtl=True, latin_font_name=latin_bold_font, hebrew_font_name=hebrew_bold_font),
            pdf_paragraph("חתימת טכנאי", section_title_style, rtl=True, latin_font_name=latin_bold_font, hebrew_font_name=hebrew_bold_font),
        ],
        [
            Image(io.BytesIO(customer_signature_bytes), width=72 * mm, height=28 * mm, hAlign="CENTER"),
            Image(io.BytesIO(technician_signature_bytes), width=72 * mm, height=28 * mm, hAlign="CENTER"),
        ],
    ], colWidths=[85 * mm, 85 * mm], hAlign="RIGHT")
    signature_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#d8deea")),
        ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#d8deea")),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.extend([
        Spacer(1, 10),
        signature_table,
        Spacer(1, 8),
    ])

    technician_meta_table = Table([
        [
            pdf_paragraph("מועד התקנה", label_style, rtl=True, latin_font_name=latin_bold_font, hebrew_font_name=hebrew_bold_font),
            pdf_paragraph(report.get("installation_date") or "-", latin_style, rtl=False, latin_font_name=latin_regular_font, hebrew_font_name=hebrew_regular_font),
            pdf_paragraph("טכנאי מבצע", label_style, rtl=True, latin_font_name=latin_bold_font, hebrew_font_name=hebrew_bold_font),
            pdf_paragraph(report.get("technician_name") or report.get("submitted_by") or "-", text_style, rtl=True, latin_font_name=latin_regular_font, hebrew_font_name=hebrew_regular_font),
        ],
    ], colWidths=[26 * mm, 48 * mm, 30 * mm, 66 * mm], hAlign="RIGHT")
    technician_meta_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.white),
        ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#d8deea")),
        ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#d8deea")),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(technician_meta_table)
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


def send_hot_field_report_email(ticket, report, pdf_filename, pdf_content):
    details = ticket.get("details") or {}
    ticket_label = ticket.get("ticket_id") or f"#{int(ticket.get('id') or 0):04d}"
    item_lines = []
    for row in report.get("line_items") or []:
        item_lines.append(
            " / ".join(part for part in [
                str(row.get("item_name") or "").strip() or "-",
                f"כמות: {str(row.get('quantity') or '').strip() or '-'}",
                f"הערות: {str(row.get('notes') or '').strip() or '-'}",
            ] if part)
        )
    body_lines = [
        f"קריאה: {ticket_label}",
        f"מספר קריאה: {(details.get('call_number') or '').strip() or '-'}",
        f"לקוח: {(details.get('customer_name') or '').strip() or '-'}",
        f"שם הלקוח בנימבוס: {(report.get('nimbus_customer_name') or '').strip() or '-'}",
        f"נציג / לקוח: {' '.join(part for part in [(report.get('contact_first_name') or '').strip(), (report.get('contact_last_name') or '').strip()] if part) or '-'}",
        f"תפקיד: {(report.get('role') or '').strip() or '-'}",
        f"כתובת: {(report.get('installation_address') or details.get('address') or '').strip() or '-'}",
        f"טלפון: {(report.get('phone') or '').strip() or '-'}",
        f"הערות: {(report.get('customer_notes') or '').strip() or '-'}",
        f"הערות נוספות: {(report.get('additional_notes') or '').strip() or '-'}",
        f"פריטים: {' | '.join(item_lines) if item_lines else '-'}",
        f"צילומי אזור עבודה: {len(report.get('area_photo_attachments') or [])}",
        f"טכנאי מבצע: {(report.get('technician_name') or report.get('submitted_by') or '').strip() or '-'}",
        f"מועד התקנה: {(report.get('installation_date') or '').strip() or '-'}",
        f"זמן חתימה: {(report.get('submitted_at_display') or '').strip() or '-'}",
    ]
    html_body = "<html><body dir='rtl'><h2>טופס אישור קבלת ציוד והתקנה</h2><ul>" + "".join(
        f"<li><strong>{xml_escape(line.split(':', 1)[0])}:</strong> {xml_escape(line.split(':', 1)[1].strip() if ':' in line else '')}</li>"
        for line in body_lines
    ) + "</ul></body></html>"
    send_plain_email(
        HOT_FIELD_REPORT_CUSTOMER_EMAIL,
        f"{ticket_label} - טופס אישור קבלת ציוד והתקנה",
        "\n".join(body_lines),
        html_body=html_body,
        attachments=[{
            "filename": pdf_filename,
            "content": pdf_content,
            "maintype": "application",
            "subtype": "pdf",
        }],
    )


def save_hot_field_report(ticket_id, actor, payload, area_photo_files=None):
    tickets = load_support_tickets()
    ticket = find_support_ticket(tickets, ticket_id)
    if not ticket:
        raise LookupError("Ticket not found")
    if (ticket.get("board_slug") or "").strip().lower() != "hot-kiryot":
        raise ValueError("Customer signature is supported only for הוט קריאות")

    details = dict(ticket.get("details") or {})
    previous_report = details.get("field_report") if isinstance(details.get("field_report"), dict) else {}
    contact_first_name = str(payload.get("contact_first_name") or previous_report.get("contact_first_name") or "").strip()
    contact_last_name = str(payload.get("contact_last_name") or previous_report.get("contact_last_name") or "").strip()
    nimbus_customer_name = str(payload.get("nimbus_customer_name") or previous_report.get("nimbus_customer_name") or details.get("customer_name") or details.get("call_number") or "").strip()
    role = str(payload.get("role") or previous_report.get("role") or "").strip()
    installation_address = str(payload.get("installation_address") or previous_report.get("installation_address") or details.get("address") or "").strip()
    phone = re.sub(r"[^\d+]", "", str(payload.get("phone") or previous_report.get("phone") or "").strip())
    customer_notes = str(payload.get("customer_notes") or previous_report.get("customer_notes") or "").strip()
    additional_notes = str(payload.get("additional_notes") or previous_report.get("additional_notes") or "").strip()
    installation_date = str(payload.get("installation_date") or previous_report.get("installation_date") or israel_now().strftime("%d/%m/%Y")).strip()
    technician_name = str(payload.get("technician_name") or previous_report.get("technician_name") or actor).strip()
    technician_signature_data_url = str(payload.get("technician_signature_data_url") or previous_report.get("technician_signature_data_url") or "").strip()
    customer_signature_data_url = str(payload.get("customer_signature_data_url") or previous_report.get("customer_signature_data_url") or "").strip()
    line_items = normalize_hot_field_report_line_items(payload.get("line_items") or previous_report.get("line_items") or [])

    if not nimbus_customer_name:
        raise ValueError("יש למלא שם הלקוח בנימבוס")
    if not contact_first_name:
        raise ValueError("יש למלא שם פרטי")
    if not installation_address:
        raise ValueError("יש למלא כתובת התקנה")
    if not phone:
        raise ValueError("יש למלא טלפון")
    if not technician_name:
        raise ValueError("יש למלא טכנאי מבצע")

    technician_signature_bytes, _ = parse_signature_data_url(technician_signature_data_url, "חתימת הטכנאי")
    customer_signature_bytes, _ = parse_signature_data_url(customer_signature_data_url, "חתימת הלקוח")
    now = israel_now()
    submitted_display = now.strftime("%d/%m/%Y %H:%M")
    merged_photo_attachments = list(previous_report.get("area_photo_attachments") or [])
    if area_photo_files:
        merged_photo_attachments.extend(save_support_attachments(area_photo_files, int(ticket.get("id") or 0)))
    report = {
        "nimbus_customer_name": nimbus_customer_name,
        "contact_first_name": contact_first_name,
        "contact_last_name": contact_last_name,
        "role": role,
        "installation_address": installation_address,
        "phone": phone,
        "customer_notes": customer_notes,
        "line_items": line_items,
        "additional_notes": additional_notes,
        "installation_date": installation_date,
        "technician_name": technician_name,
        "technician_signature_data_url": technician_signature_data_url,
        "customer_signature_data_url": customer_signature_data_url,
        "area_photo_attachments": merged_photo_attachments,
        "submitted_by": actor,
        "submitted_at": now.isoformat(timespec="seconds"),
        "submitted_at_display": submitted_display,
    }
    pdf_content = build_hot_field_report_pdf(ticket, report, technician_signature_bytes, customer_signature_bytes)
    pdf_filename = hot_field_report_attachment_label(ticket, report)
    saved_attachment = save_generated_support_attachment(pdf_content, pdf_filename, int(ticket.get("id") or 0), "application/pdf")
    report["pdf_attachment"] = saved_attachment

    details["field_report"] = report
    now_iso = now.isoformat(timespec="seconds")
    updates = [{
        "changed_at": now_iso,
        "actor": actor,
        "field_name": "details.field_report",
        "old_value": json.dumps(previous_report or {}, ensure_ascii=False),
        "new_value": json.dumps(report, ensure_ascii=False),
    }]
    saved_attachments = list(merged_photo_attachments[len(previous_report.get("area_photo_attachments") or []):]) + [saved_attachment]

    if supabase_ticketing_enabled():
        _supabase_request(
            "PATCH",
            "support_tickets",
            params={"id": f"eq.{ticket['id']}"},
            json_body={"details": details},
            prefer="return=minimal",
        )
        if saved_attachments:
            _supabase_request(
                "POST",
                "ticket_attachments",
                json_body=[{"ticket_id": ticket["id"], **attachment} for attachment in saved_attachments],
                prefer="return=minimal",
            )
        _supabase_request(
            "POST",
            "ticket_updates",
            json_body=[{"ticket_id": ticket["id"], **update} for update in updates],
            prefer="return=minimal",
        )
        normalized_ticket = normalize_support_ticket({
            **ticket,
            "details": details,
            "attachments": (ticket.get("attachments") or []) + saved_attachments,
            "updates": (ticket.get("updates") or []) + [{
                "at": update["changed_at"],
                "actor": update["actor"],
                "field": update["field_name"],
                "from": update["old_value"],
                "to": update["new_value"],
            } for update in updates],
        })
    else:
        persisted = load_support_tickets()
        local_ticket = find_support_ticket(persisted, ticket_id)
        if not local_ticket:
            raise LookupError("Ticket not found")
        local_ticket["details"] = details
        local_ticket["attachments"] = (local_ticket.get("attachments") or []) + saved_attachments
        local_ticket.setdefault("updates", []).extend([{
            "at": update["changed_at"],
            "actor": update["actor"],
            "field": update["field_name"],
            "from": update["old_value"],
            "to": update["new_value"],
        } for update in updates])
        save_support_tickets(persisted)
        normalized_ticket = normalize_support_ticket(local_ticket)

    try:
        send_hot_field_report_email(normalized_ticket, report, pdf_filename, pdf_content)
        normalized_ticket["field_report_sent"] = True
        normalized_ticket["field_report_error"] = ""
    except Exception as exc:
        normalized_ticket["field_report_sent"] = False
        normalized_ticket["field_report_error"] = str(exc)
    return normalized_ticket


def smtp_email_enabled():
    return bool(SMTP_HOST and (SMTP_FROM or SMTP_USERNAME))


def send_plain_email(to_address, subject, body, from_address=None, html_body=None, attachments=None):
    if not smtp_email_enabled():
        raise RuntimeError("SMTP is not configured")

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = (from_address or SMTP_FROM or SMTP_USERNAME).strip()
    message["To"] = to_address
    message.set_content(body)
    if html_body:
        message.add_alternative(html_body, subtype="html")
    for attachment in attachments or []:
        if not isinstance(attachment, dict):
            continue
        filename = str(attachment.get("filename") or "attachment.txt")
        content = attachment.get("content") or ""
        maintype = str(attachment.get("maintype") or "application")
        subtype = str(attachment.get("subtype") or "octet-stream")
        if isinstance(content, str):
            content = content.encode("utf-8")
        message.add_attachment(content, maintype=maintype, subtype=subtype, filename=filename)

    if SMTP_USE_SSL:
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=20) as smtp:
            if SMTP_USERNAME and SMTP_PASSWORD:
                smtp.login(SMTP_USERNAME, SMTP_PASSWORD)
            smtp.send_message(message)
        return

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as smtp:
        if SMTP_USE_TLS:
            smtp.starttls()
        if SMTP_USERNAME and SMTP_PASSWORD:
            smtp.login(SMTP_USERNAME, SMTP_PASSWORD)
        smtp.send_message(message)


def coordination_ticket_has_complete_details(ticket):
    details = ticket.get("details") or {}
    return all([
        (details.get("coordinated_worker") or "").strip(),
        (details.get("visit_date") or "").strip(),
        (details.get("visit_hour_from") or "").strip(),
        (details.get("visit_hour_to") or "").strip(),
    ])


def coordination_ticket_details_changed(previous_ticket, updated_ticket):
    previous_details = (previous_ticket or {}).get("details") or {}
    updated_details = (updated_ticket or {}).get("details") or {}
    fields = ("coordinated_worker", "visit_date", "visit_hour_from", "visit_hour_to")
    return any(
        (previous_details.get(field_name) or "").strip() != (updated_details.get(field_name) or "").strip()
        for field_name in fields
    )


def actor_can_trigger_nastia_notification(actor):
    return (actor or "").strip() in COORDINATION_USERS


def request_targets_nastia_queue(changes):
    payload = changes or {}
    source_page_mode = (payload.get("source_page_mode") or payload.get("page_mode") or "").strip().lower()
    source_ticket_queue = (payload.get("source_ticket_queue") or payload.get("ticket_queue") or "").strip().lower()
    return source_page_mode == "nastia" or source_ticket_queue == "nastia"


def should_notify_nastia(previous_ticket, updated_ticket, enabled=False):
    if not enabled:
        return False
    if not board_supports_coordination((updated_ticket.get("board_slug") or "").strip().lower()):
        return False

    return coordination_ticket_has_complete_details(updated_ticket) and coordination_ticket_details_changed(
        previous_ticket,
        updated_ticket,
    )


def _pais_email_value(value):
    return (str(value or "").strip() or "-")


def _pais_email_multiline_html(value):
    return xml_escape(_pais_email_value(value)).replace("\n", "<br>")


def coordination_ticket_calendar_contact(ticket):
    details = ticket.get("details") or {}
    board_slug = (ticket.get("board_slug") or "").strip().lower()
    if board_slug == "support":
        return (details.get("service_contact") or "").strip()
    if board_slug == "hot-kiryot":
        primary = (details.get("on_site_contact") or "").strip()
        secondary = (details.get("technical_contact") or "").strip()
        if primary and secondary and primary != secondary:
            return f"{primary} | {secondary}"
        return primary or secondary
    name = (details.get("contact_name") or "").strip()
    phone = (details.get("contact_phone") or "").strip()
    if name and phone:
        return f"{name} {phone}"
    return name or phone


def coordination_ticket_calendar_address(ticket):
    details = ticket.get("details") or {}
    board_slug = (ticket.get("board_slug") or "").strip().lower()
    if board_slug == "support":
        return (details.get("service_address") or details.get("address") or "").strip()
    return (details.get("address") or "").strip()


def coordination_ticket_email_context(ticket):
    board_slug = (ticket.get("board_slug") or "").strip().lower()
    board = get_ticket_board(board_slug)
    board_name = (ticket.get("service_type") or board["name"]).strip() or board["name"]
    ticket_label = ticket.get("ticket_id") or f"#{int(ticket.get('id') or 0):04d}"
    details = ticket.get("details") or {}
    calendar_contact = coordination_ticket_calendar_contact(ticket)
    calendar_address = coordination_ticket_calendar_address(ticket)

    top_rows = [
        ("מספר קריאה", ticket_label),
        ("לוח", board_name),
        ("נוצר בתאריך", ticket.get("created_at_display")),
        ("יוצר", ticket.get("creator")),
        ("סטטוס", ticket.get("status")),
        ("משויך ל", ticket.get("assigned_to")),
    ]

    if board_slug == "support":
        detail_rows = [
            ("סוג כרטיס", ticket.get("ticket_type")),
            ("סוג שירות", ticket.get("service_type")),
            ("דומיין", ticket.get("domain")),
            ("עדיפות", ticket.get("priority")),
            ("תיאור", ticket.get("description")),
            ("פתרון", ticket.get("solution")),
            ("סוג לקוח", details.get("customer_type")),
            ("סוג טיפול", details.get("service_mode")),
            ("שם העסק", details.get("business_name")),
            ("איש קשר", details.get("service_contact")),
            ("כתובת", details.get("service_address")),
            ("טכנאי מתואם", details.get("coordinated_worker")),
            ("תאריך ביקור", details.get("visit_date")),
            ("שעת ביקור מ", details.get("visit_hour_from")),
            ("שעת ביקור עד", details.get("visit_hour_to")),
            ("הערות כשל", details.get("failure_notes")),
        ]
        calendar_description_lines = [
            f"מספר קריאה: {ticket_label}",
            f"סוג לקוח: {(details.get('customer_type') or '').strip() or '-'}",
            f"שם העסק: {(details.get('business_name') or '').strip() or '-'}",
            f"תיאור: {(ticket.get('description') or '').strip() or '-'}",
            f"כתובת: {calendar_address or '-'}",
            f"איש קשר: {calendar_contact or '-'}",
            f"טכנאי מתואם: {(details.get('coordinated_worker') or '').strip() or '-'}",
        ]
        calendar_summary = f"קריאת שירות נימבוס {ticket_label}"
        location = calendar_address or "נימבוס"
        subject = f"קריאת שירות נימבוס מס' קריאה : {ticket_label}"
    elif board_slug == "hot-kiryot":
        detail_rows = [
            ("שעה ותאריך פתיחת תקלה", details.get("opened_at")),
            ("מספר קריאה שהוקצה", details.get("call_number")),
            ("תומך במוקד שפתח פניה / טיפל בלקוח", details.get("opened_by")),
            ("ח.פ. / מס לקוח", details.get("customer_id")),
            ("שם לקוח", details.get("customer_name")),
            ("קוד קו / ID-LINK", details.get("line_code")),
            ("כתובת", details.get("address")),
            ("איש קשר במקום", details.get("on_site_contact")),
            ("איש קשר טכני מטעם הלקוח", details.get("technical_contact")),
            ("שעות פעילות / זמינות לקוח", details.get("availability_hours")),
            ("בדיקות שבוצעו מרחוק", details.get("remote_checks")),
            ("מהות התקלה", details.get("issue_summary")),
            ("פעולות / בדיקות שטכנאי צריך לבצע", details.get("technician_actions")),
            ("סוג ציוד קיים אצל הלקוח", details.get("equipment_type")),
            ("הסכם שירות ואיזה ציוד באחריות הוט", details.get("service_agreement")),
            ("פרטים טכניים נוספים", details.get("technical_notes")),
            ("טכנאי מתואם", details.get("coordinated_worker")),
            ("תאריך ביקור", details.get("visit_date")),
            ("שעת ביקור מ", details.get("visit_hour_from")),
            ("שעת ביקור עד", details.get("visit_hour_to")),
            ("הערות כשל", details.get("failure_notes")),
        ]
        calendar_description_lines = [
            f"מספר קריאה: {ticket_label}",
            f"לקוח: {(details.get('customer_name') or '').strip() or '-'}",
            f"מהות התקלה: {(details.get('issue_summary') or '').strip() or '-'}",
            f"כתובת: {calendar_address or '-'}",
            f"איש קשר: {calendar_contact or '-'}",
            f"טכנאי מתואם: {(details.get('coordinated_worker') or '').strip() or '-'}",
        ]
        calendar_summary = f"קריאת שירות הוט קריאות {ticket_label}"
        location = calendar_address or "הוט קריאות"
        subject = f"קריאת שירות הוט קריאות מס' קריאה : {ticket_label}"
    else:
        terminal_number = (details.get("terminal_number") or "").strip()
        detail_rows = [
            ("מספר מסוף", details.get("terminal_number")),
            ("כתובת", details.get("address")),
            ("כתובת IP סטטית", details.get("static_ip")),
            ("אלטורה", details.get("altura")),
            ("Loop Back", details.get("look_back")),
            ("איש קשר", details.get("contact_name")),
            ("טלפון איש קשר", details.get("contact_phone")),
            ("פניית לקוח", details.get("customer_request")),
            ("פעולות", details.get("actions_taken")),
            ("טכנאי מתואם", details.get("coordinated_worker")),
            ("תאריך ביקור", details.get("visit_date")),
            ("שעת ביקור מ", details.get("visit_hour_from")),
            ("שעת ביקור עד", details.get("visit_hour_to")),
            ("הערות כשל", details.get("failure_notes")),
        ]
        calendar_description_lines = [
            f"מספר קריאה: {ticket_label}",
            f"מספר מסוף: {terminal_number or '-'}",
            f"פניית לקוח: {(details.get('customer_request') or '').strip() or '-'}",
            f"כתובת: {calendar_address or '-'}",
            f"איש קשר: {calendar_contact or '-'}",
            f"טכנאי מתואם: {(details.get('coordinated_worker') or '').strip() or '-'}",
        ]
        calendar_summary = f"קריאת שירות מפעל הפיס {ticket_label}"
        location = calendar_address or "מפעל הפיס"
        subject = f"קריאת שירות מפעל הפיס מס' קריאה : {ticket_label}"

    return {
        "board_name": board_name,
        "ticket_label": ticket_label,
        "top_rows": top_rows,
        "detail_rows": detail_rows,
        "calendar_description_lines": calendar_description_lines,
        "calendar_summary": calendar_summary,
        "location": location,
        "subject": subject,
        "body_lines": [f"{label}: {_pais_email_value(value)}" for label, value in top_rows]
        + [""]
        + [f"{label}: {_pais_email_value(value)}" for label, value in detail_rows],
    }


def build_pais_google_calendar_link(ticket):
    details = ticket.get("details") or {}
    visit_date = (details.get("visit_date") or "").strip()
    visit_hour_from = (details.get("visit_hour_from") or "").strip()
    visit_hour_to = (details.get("visit_hour_to") or "").strip()
    if not (visit_date and visit_hour_from and visit_hour_to):
        return None

    try:
        tz = ZoneInfo("Asia/Jerusalem")
        start_at = datetime.strptime(f"{visit_date} {visit_hour_from}", "%Y-%m-%d %H:%M").replace(tzinfo=tz)
        end_at = datetime.strptime(f"{visit_date} {visit_hour_to}", "%Y-%m-%d %H:%M").replace(tzinfo=tz)
    except ValueError:
        return None

    email_context = coordination_ticket_email_context(ticket)
    coordinated_worker = (details.get("coordinated_worker") or "").strip()
    guest_email = PAIS_CALENDAR_GUEST_EMAILS.get(coordinated_worker, "")
    start_utc = start_at.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    end_utc = end_at.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    params = {
        "action": "TEMPLATE",
        "text": email_context["calendar_summary"],
        "dates": f"{start_utc}/{end_utc}",
        "details": "\n".join(email_context["calendar_description_lines"]),
        "location": email_context["location"],
        "ctz": "Asia/Jerusalem",
    }
    if guest_email:
        params["add"] = guest_email
    query = "&".join(f"{key}={quote(str(value), safe='')}" for key, value in params.items())
    return f"https://calendar.google.com/calendar/render?{query}"


def build_pais_email_html(ticket, calendar_link=None):
    email_context = coordination_ticket_email_context(ticket)

    def render_rows(rows):
        return "".join(
            f"""
            <tr>
              <td style="padding:10px 12px;border-bottom:1px solid #e7dfd2;color:#6a6258;font-weight:700;width:34%;">{xml_escape(label)}</td>
              <td style="padding:10px 12px;border-bottom:1px solid #e7dfd2;color:#1f2f46;">{_pais_email_multiline_html(value)}</td>
            </tr>
            """
            for label, value in rows
        )

    calendar_button = ""
    if calendar_link:
        calendar_button = f"""
        <div style="margin:20px 0 0;text-align:center;">
          <a href="{xml_escape(calendar_link)}" style="display:inline-block;background:#28a86f;color:#ffffff;text-decoration:none;padding:12px 22px;border-radius:8px;font-weight:700;">
            הוסף ליומן Google
          </a>
        </div>
        """

    return f"""\
<!DOCTYPE html>
<html lang="he" dir="rtl">
  <body style="margin:0;padding:24px;background:#f5f1ea;font-family:Arial,'Noto Sans Hebrew',sans-serif;color:#1f2f46;">
    <div style="max-width:760px;margin:0 auto;background:#fbfaf7;border:1px solid #ded5c9;border-radius:14px;overflow:hidden;">
      <div style="padding:20px 24px;background:linear-gradient(135deg,#f9f3e8 0%,#eef4ff 100%);border-bottom:1px solid #ded5c9;">
        <div style="font-size:13px;color:#7b7267;font-weight:700;">{xml_escape(email_context['board_name'])}</div>
        <div style="font-size:28px;font-weight:800;margin-top:6px;">{xml_escape(email_context['ticket_label'])}</div>
      </div>
      <div style="padding:24px;">
        <table role="presentation" style="width:100%;border-collapse:collapse;background:#fff;border:1px solid #e7dfd2;border-radius:10px;overflow:hidden;">
          {render_rows(email_context["top_rows"])}
        </table>
        <div style="height:16px;"></div>
        <table role="presentation" style="width:100%;border-collapse:collapse;background:#fff;border:1px solid #e7dfd2;border-radius:10px;overflow:hidden;">
          {render_rows(email_context["detail_rows"])}
        </table>
        {calendar_button}
      </div>
    </div>
  </body>
</html>
"""


def should_notify_racheli(previous_ticket, updated_ticket, actor, changes):
    if (updated_ticket.get("board_slug") or "").strip().lower() != "support":
        return False
    if not actor_can_trigger_nastia_notification(actor) and not request_targets_nastia_queue(changes):
        return False
    previous_mode = ((previous_ticket or {}).get("details") or {}).get("service_mode") or ""
    updated_mode = ((updated_ticket.get("details") or {}).get("service_mode") or "").strip()
    return updated_mode == "משלוח" and previous_mode != updated_mode


def send_racheli_ticket_email(ticket):
    email_context = coordination_ticket_email_context(ticket)
    selected_mode = ((ticket.get("details") or {}).get("service_mode") or "").strip() or "משלוח"
    send_plain_email(
        RACHELI_NOTIFICATION_EMAIL,
        f"{email_context['ticket_label']} - {selected_mode}",
        "\n".join(email_context["body_lines"]),
        from_address=PAIS_NOTIFICATION_FROM or SMTP_FROM or SMTP_USERNAME,
        html_body=build_pais_email_html(ticket),
    )


def send_nastia_ticket_email(ticket):
    email_context = coordination_ticket_email_context(ticket)
    calendar_link = build_pais_google_calendar_link(ticket)
    body_lines = list(email_context["body_lines"])
    if calendar_link:
        body_lines.extend([
            "",
            f"הוספה ליומן Google: {calendar_link}",
        ])
    send_plain_email(
        NASTIA_NOTIFICATION_EMAIL,
        email_context["subject"],
        "\n".join(body_lines),
        from_address=PAIS_NOTIFICATION_FROM or SMTP_FROM or SMTP_USERNAME,
        html_body=build_pais_email_html(ticket, calendar_link=calendar_link),
    )


def process_nastia_ticket_notification(previous_ticket, updated_ticket, enabled=True):
    attempted = should_notify_nastia(previous_ticket, updated_ticket, enabled=enabled)
    result = {
        "notification_attempted": attempted,
        "notification_sent": False,
        "notification_error": "",
    }
    if not attempted:
        return result
    try:
        send_nastia_ticket_email(updated_ticket)
        result["notification_sent"] = True
    except Exception as exc:
        print(f"Nastia notification email warning for ticket {updated_ticket.get('id')}: {exc}")
        result["notification_error"] = str(exc)
    return result


def process_racheli_ticket_notification(previous_ticket, updated_ticket, actor, changes):
    attempted = should_notify_racheli(previous_ticket, updated_ticket, actor, changes)
    result = {
        "racheli_notification_attempted": attempted,
        "racheli_notification_sent": False,
        "racheli_notification_error": "",
    }
    if not attempted:
        return result
    try:
        send_racheli_ticket_email(updated_ticket)
        result["racheli_notification_sent"] = True
    except Exception as exc:
        print(f"Racheli notification email warning for ticket {updated_ticket.get('id')}: {exc}")
        result["racheli_notification_error"] = str(exc)
    return result


def find_support_ticket(tickets, ticket_id):
    try:
        number = int(str(ticket_id).replace("#", ""))
    except ValueError:
        return None
    for ticket in tickets:
        if int(ticket.get("id") or 0) == number:
            return ticket
    return None


def nastia_notification_enabled(previous_ticket, updated_ticket, actor, changes):
    if bool((changes or {}).get("send_nastia_notification", False)):
        return True
    if not (coordination_ticket_has_complete_details(updated_ticket) and coordination_ticket_details_changed(
        previous_ticket,
        updated_ticket,
    )):
        return False
    return actor_can_trigger_nastia_notification(actor) or request_targets_nastia_queue(changes)


def delete_support_attachments(ticket):
    ticket_folders = set()
    for attachment in ticket.get("attachments") or []:
        folder = (attachment.get("folder") or "").strip()
        saved_name = secure_filename(attachment.get("saved_name") or "")
        if not re.fullmatch(r"TicketID\d{4}", folder):
            continue
        if saved_name and supabase_storage_enabled():
            try:
                delete_supabase_storage_object(_supabase_storage_object_path(folder, saved_name))
            except Exception as exc:
                print(f"Supabase attachment delete warning for {folder}/{saved_name}: {exc}")
        ticket_folders.add(folder)
    for folder in ticket_folders:
        folder_path = os.path.abspath(os.path.join(SUPPORT_SCREEN_DIR, folder))
        screen_root = os.path.abspath(SUPPORT_SCREEN_DIR)
        if os.path.commonpath([screen_root, folder_path]) != screen_root:
            continue
        if os.path.isdir(folder_path):
            shutil.rmtree(folder_path, ignore_errors=True)


def ensure_ticket_board_exists(board_slug):
    board = get_ticket_board(board_slug)
    normalized_board_slug = (board.get("slug") or "").strip().lower()
    if not normalized_board_slug or normalized_board_slug == "support":
        return
    _supabase_request(
        "POST",
        "ticket_boards",
        json_body=[{
            "slug": board["slug"],
            "name": board["name"],
            "icon_path": board.get("icon_path") or "",
            "route_path": board["route_path"],
            "sort_order": int(board.get("sort_order") or 1),
        }],
        prefer="resolution=merge-duplicates,return=minimal",
    )


def create_support_ticket_record(ticket_payload, attachment_files=None, attachment_file=None):
    attachment_files = [file_storage for file_storage in (attachment_files or []) if file_storage and file_storage.filename]
    if attachment_file and attachment_file.filename:
        attachment_files.append(attachment_file)

    if not supabase_ticketing_enabled():
        ticket_number = next_support_ticket_id()
        attachments = save_support_attachments(attachment_files, ticket_number)
        ticket = normalize_support_ticket({
            "id": ticket_number,
            **ticket_payload,
            "attachments": attachments,
            "updates": [],
        })
        tickets = load_support_tickets()
        tickets.append(ticket)
        save_support_tickets(tickets)
        return ticket

    ensure_ticket_board_exists(ticket_payload.get("board_slug"))
    response = _supabase_request(
        "POST",
        "support_tickets",
        json_body=[ticket_payload],
        prefer="return=representation",
    )
    rows = response.json()
    if not rows:
        raise RuntimeError("Ticket creation failed")
    ticket = normalize_support_ticket(rows[0])
    attachments = []
    try:
        if attachment_files:
            attachments = save_support_attachments(attachment_files, ticket["id"])
            if attachments:
                _supabase_request(
                    "POST",
                    "ticket_attachments",
                    json_body=[{"ticket_id": ticket["id"], **saved_attachment} for saved_attachment in attachments],
                    prefer="return=minimal",
                )
    except Exception:
        try:
            _supabase_request("DELETE", "support_tickets", params={"id": f"eq.{ticket['id']}"}, prefer="return=minimal")
        except Exception:
            pass
        raise
    ticket["attachments"] = attachments
    ticket["updates"] = []
    return ticket


def append_support_ticket_attachments(ticket_id, attachment_files):
    attachment_files = [file_storage for file_storage in (attachment_files or []) if file_storage and file_storage.filename]
    if not attachment_files:
        raise ValueError("No images were selected")

    tickets = load_support_tickets()
    ticket = find_support_ticket(tickets, ticket_id)
    if not ticket:
        raise LookupError("Ticket not found")

    saved_attachments = save_support_attachments(attachment_files, int(ticket.get("id") or 0))
    if not saved_attachments:
        raise ValueError("No images were selected")

    if supabase_ticketing_enabled():
        _supabase_request(
            "POST",
            "ticket_attachments",
            json_body=[{"ticket_id": ticket["id"], **saved_attachment} for saved_attachment in saved_attachments],
            prefer="return=minimal",
        )
        normalized_ticket = normalize_support_ticket({
            **ticket,
            "attachments": (ticket.get("attachments") or []) + saved_attachments,
        })
        return normalized_ticket

    persisted = load_support_tickets()
    local_ticket = find_support_ticket(persisted, ticket_id)
    if not local_ticket:
        raise LookupError("Ticket not found")
    local_ticket["attachments"] = (local_ticket.get("attachments") or []) + saved_attachments
    save_support_tickets(persisted)
    return normalize_support_ticket(local_ticket)


def delete_support_ticket_attachment(ticket_id, folder, saved_name):
    safe_folder = (folder or "").strip()
    safe_name = secure_filename(saved_name or "")
    if not re.fullmatch(r"TicketID\d{4}", safe_folder) or not safe_name:
        raise ValueError("Invalid attachment")

    tickets = load_support_tickets()
    ticket = find_support_ticket(tickets, ticket_id)
    if not ticket:
        raise LookupError("Ticket not found")

    attachments = list(ticket.get("attachments") or [])
    target_attachment = next(
        (
            attachment for attachment in attachments
            if (attachment.get("folder") or "").strip() == safe_folder
            and secure_filename(attachment.get("saved_name") or "") == safe_name
        ),
        None,
    )
    if not target_attachment:
        raise LookupError("Attachment not found")

    remaining_attachments = [
        attachment for attachment in attachments
        if not (
            (attachment.get("folder") or "").strip() == safe_folder
            and secure_filename(attachment.get("saved_name") or "") == safe_name
        )
    ]

    if supabase_storage_enabled():
        try:
            delete_supabase_storage_object(_supabase_storage_object_path(safe_folder, safe_name))
        except Exception as exc:
            print(f"Supabase attachment delete warning for {safe_folder}/{safe_name}: {exc}")

    file_path = os.path.abspath(os.path.join(SUPPORT_SCREEN_DIR, safe_folder, safe_name))
    screen_root = os.path.abspath(SUPPORT_SCREEN_DIR)
    if os.path.commonpath([screen_root, file_path]) == screen_root and os.path.exists(file_path):
        try:
            os.remove(file_path)
        except OSError:
            pass
        folder_path = os.path.abspath(os.path.join(SUPPORT_SCREEN_DIR, safe_folder))
        if os.path.commonpath([screen_root, folder_path]) == screen_root and os.path.isdir(folder_path):
            if not os.listdir(folder_path):
                shutil.rmtree(folder_path, ignore_errors=True)

    if supabase_ticketing_enabled():
        _supabase_request(
            "DELETE",
            "ticket_attachments",
            params={
                "ticket_id": f"eq.{int(ticket.get('id') or 0)}",
                "folder": f"eq.{safe_folder}",
                "saved_name": f"eq.{safe_name}",
            },
            prefer="return=minimal",
        )
        return normalize_support_ticket({
            **ticket,
            "attachments": remaining_attachments,
        })

    persisted = load_support_tickets()
    local_ticket = find_support_ticket(persisted, ticket_id)
    if not local_ticket:
        raise LookupError("Ticket not found")
    local_ticket["attachments"] = remaining_attachments
    save_support_tickets(persisted)
    return normalize_support_ticket(local_ticket)


def recent_attachment_diagnostics(limit=5):
    attachments = []
    if supabase_ticketing_enabled():
        try:
            rows = _supabase_request(
                "GET",
                "ticket_attachments",
                params={
                    "select": "id,ticket_id,original_name,saved_name,folder,url",
                    "order": "id.desc",
                    "limit": str(limit),
                },
            ).json()
        except Exception as exc:
            return {"items": [], "load_error": str(exc)}

        for row in rows:
            folder = (row.get("folder") or "").strip()
            saved_name = secure_filename(row.get("saved_name") or "")
            object_path = _supabase_storage_object_path(folder, saved_name) if folder and saved_name else ""
            local_path = os.path.abspath(os.path.join(SUPPORT_SCREEN_DIR, folder, saved_name)) if folder and saved_name else ""
            item = {
                "ticket_id": row.get("ticket_id"),
                "original_name": row.get("original_name") or "",
                "saved_name": saved_name,
                "folder": folder,
                "url": row.get("url") or "",
                "object_path": object_path,
                "local_exists": bool(local_path and os.path.exists(local_path)),
                "supabase_exists": None,
                "supabase_error": "",
            }
            if supabase_storage_enabled() and object_path:
                try:
                    response = download_supabase_storage_object(object_path)
                    item["supabase_exists"] = response is not None
                except Exception as exc:
                    item["supabase_exists"] = False
                    item["supabase_error"] = str(exc)
            attachments.append(item)
        return {"items": attachments, "load_error": ""}

    tickets = load_support_tickets()
    for ticket in sorted(tickets, key=lambda item: int(item.get("id") or 0), reverse=True):
        for attachment in reversed(ticket.get("attachments") or []):
            folder = (attachment.get("folder") or "").strip()
            saved_name = secure_filename(attachment.get("saved_name") or "")
            local_path = os.path.abspath(os.path.join(SUPPORT_SCREEN_DIR, folder, saved_name)) if folder and saved_name else ""
            attachments.append({
                "ticket_id": ticket.get("id"),
                "original_name": attachment.get("original_name") or "",
                "saved_name": saved_name,
                "folder": folder,
                "url": attachment.get("url") or "",
                "object_path": "",
                "local_exists": bool(local_path and os.path.exists(local_path)),
                "supabase_exists": None,
                "supabase_error": "",
            })
            if len(attachments) >= limit:
                return {"items": attachments, "load_error": ""}
    return {"items": attachments, "load_error": ""}


def update_support_ticket_record(ticket_id, changes, actor):
    tickets = load_support_tickets()
    ticket = find_support_ticket(tickets, ticket_id)
    if not ticket:
        raise LookupError("Ticket not found")
    previous_ticket = {
        "id": ticket.get("id"),
        "ticket_id": ticket.get("ticket_id"),
        "board_slug": ticket.get("board_slug"),
        "status": ticket.get("status", ""),
        "assigned_to": ticket.get("assigned_to", ""),
        "details": dict(ticket.get("details") or {}),
    }

    updates = []
    now = israel_now().isoformat(timespec="seconds")

    if "assigned_to" in changes:
        assigned_to = (changes.get("assigned_to") or "").strip()
        old_value = ticket.get("assigned_to", "")
        ticket["assigned_to"] = assigned_to
        updates.append({"changed_at": now, "actor": actor, "field_name": "assigned_to", "old_value": old_value, "new_value": assigned_to})

    if "status" in changes:
        status = (changes.get("status") or "").strip()
        old_value = ticket.get("status", "Waiting")
        ticket["status"] = status
        updates.append({"changed_at": now, "actor": actor, "field_name": "status", "old_value": old_value, "new_value": status})

    if "description" in changes:
        description = str(changes.get("description") or "").strip()
        old_value = ticket.get("description", "")
        ticket["description"] = description
        updates.append({"changed_at": now, "actor": actor, "field_name": "description", "old_value": old_value, "new_value": description})

    if "solution" in changes:
        solution = str(changes.get("solution") or "").strip()
        old_value = ticket.get("solution", "")
        ticket["solution"] = solution
        updates.append({"changed_at": now, "actor": actor, "field_name": "solution", "old_value": old_value, "new_value": solution})

    if "details" in changes and isinstance(changes.get("details"), dict):
        detail_fields = {
            "actions_taken",
            "technician_actions",
            "coordinated_worker",
            "visit_date",
            "visit_hour_from",
            "visit_hour_to",
            "failure_notes",
            "customer_type",
            "service_mode",
            "business_name",
            "service_contact",
            "service_address",
        }
        details = dict(ticket.get("details") or {})
        for field_name, new_value in changes.get("details", {}).items():
            if field_name not in detail_fields:
                continue
            old_value = str(details.get(field_name) or "")
            updated_value = str(new_value or "").strip()
            if old_value == updated_value:
                continue
            details[field_name] = updated_value
            updates.append({
                "changed_at": now,
                "actor": actor,
                "field_name": f"details.{field_name}",
                "old_value": old_value,
                "new_value": updated_value,
            })
        ticket["details"] = details

    if supabase_ticketing_enabled():
        ticket_updates = [{"ticket_id": ticket["id"], **update} for update in updates]
        patch_payload = {}
        if "assigned_to" in changes:
            patch_payload["assigned_to"] = ticket["assigned_to"]
        if "status" in changes:
            patch_payload["status"] = ticket["status"]
        if "description" in changes:
            patch_payload["description"] = ticket.get("description") or ""
        if "solution" in changes:
            patch_payload["solution"] = ticket.get("solution") or ""
        if "details" in changes:
            patch_payload["details"] = ticket.get("details") or {}
        if patch_payload:
            _supabase_request(
                "PATCH",
                "support_tickets",
                params={"id": f"eq.{ticket['id']}"},
                json_body=patch_payload,
                prefer="return=minimal",
            )
        if ticket_updates:
            _supabase_request(
                "POST",
                "ticket_updates",
                json_body=ticket_updates,
                prefer="return=minimal",
            )
        normalized_ticket = normalize_support_ticket({**ticket, "updates": (ticket.get("updates") or []) + [
            {
                "at": update["changed_at"],
                "actor": update["actor"],
                "field": update["field_name"],
                "from": update["old_value"],
                "to": update["new_value"],
            }
            for update in updates
        ]})
        notification_enabled = nastia_notification_enabled(previous_ticket, normalized_ticket, actor, changes)
        notification_result = process_nastia_ticket_notification(
            previous_ticket,
            normalized_ticket,
            enabled=notification_enabled,
        )
        normalized_ticket.update(notification_result)
        normalized_ticket.update(process_racheli_ticket_notification(
            previous_ticket,
            normalized_ticket,
            actor,
            changes,
        ))
        return normalized_ticket

    persisted = load_support_tickets()
    local_ticket = find_support_ticket(persisted, ticket_id)
    if not local_ticket:
        raise LookupError("Ticket not found")
    local_updates = local_ticket.setdefault("updates", [])
    for update in updates:
        if "assigned_to" in changes:
            local_ticket["assigned_to"] = ticket["assigned_to"]
        if "status" in changes:
            local_ticket["status"] = ticket["status"]
        if "description" in changes:
            local_ticket["description"] = ticket.get("description") or ""
        if "solution" in changes:
            local_ticket["solution"] = ticket.get("solution") or ""
        if "details" in changes:
            local_ticket["details"] = dict(ticket.get("details") or {})
        local_updates.append({
            "at": update["changed_at"],
            "actor": update["actor"],
            "field": update["field_name"],
            "from": update["old_value"],
            "to": update["new_value"],
        })
    save_support_tickets(persisted)
    normalized_ticket = normalize_support_ticket(local_ticket)
    notification_enabled = nastia_notification_enabled(previous_ticket, normalized_ticket, actor, changes)
    notification_result = process_nastia_ticket_notification(
        previous_ticket,
        normalized_ticket,
        enabled=notification_enabled,
    )
    normalized_ticket.update(notification_result)
    normalized_ticket.update(process_racheli_ticket_notification(
        previous_ticket,
        normalized_ticket,
        actor,
        changes,
    ))
    return normalized_ticket


def delete_support_ticket_record(ticket_id):
    tickets = load_support_tickets()
    ticket = find_support_ticket(tickets, ticket_id)
    if not ticket:
        raise LookupError("Ticket not found")

    delete_support_attachments(ticket)

    if supabase_ticketing_enabled():
        _supabase_request("DELETE", "ticket_attachments", params={"ticket_id": f"eq.{ticket['id']}"}, prefer="return=minimal")
        _supabase_request("DELETE", "ticket_updates", params={"ticket_id": f"eq.{ticket['id']}"}, prefer="return=minimal")
        _supabase_request("DELETE", "support_tickets", params={"id": f"eq.{ticket['id']}"}, prefer="return=minimal")
        return ticket

    remaining_tickets = [item for item in tickets if int(item.get("id") or 0) != int(ticket.get("id") or 0)]
    save_support_tickets(remaining_tickets)
    return ticket


def _service_key(service_name: str) -> str:
    if service_name == "record":
        return "recordings"
    if service_name in ("recording-storage", "recording_storage"):
        return "recording_storage"
    if service_name in ("human-service", "human_service"):
        return "human_service"
    return service_name


def register_service_activity(service_name: str):
    username = (session.get("username") or "").strip().lower()
    if not username:
        return
    key = _service_key(service_name)
    now = datetime.utcnow()
    cutoff = now - timedelta(minutes=ACTIVE_WINDOW_MINUTES)
    users = SERVICE_ACTIVITY.get(key, {})
    users = {u: ts for u, ts in users.items() if ts >= cutoff}
    users[username] = now
    SERVICE_ACTIVITY[key] = users


def get_active_users_for(service_name: str):
    key = _service_key(service_name)
    now = datetime.utcnow()
    cutoff = now - timedelta(minutes=ACTIVE_WINDOW_MINUTES)
    users = SERVICE_ACTIVITY.get(key, {})
    users = {u: ts for u, ts in users.items() if ts >= cutoff}
    SERVICE_ACTIVITY[key] = users
    return sorted(users.keys())


def api_error(message, status=500, code="server_error"):
    return jsonify({"ok": False, "code": code, "message": str(message)}), status


def _supabase_login_user(username):
    if not supabase_ticketing_enabled():
        return None
    try:
        response = _supabase_request(
            "GET",
            "support_app_users",
            params={
                "select": "email,password_hash,role,allowed_pages,active",
                "email": f"eq.{username}",
                "active": "eq.true",
                "limit": "1",
            },
        )
    except Exception:
        return None
    rows = response.json()
    if not rows:
        return None
    row = rows[0]
    return {
        "email": (row.get("email") or "").strip().lower(),
        "password_hash": (row.get("password_hash") or "").strip(),
        "role": (row.get("role") or "user").strip().lower(),
        "allowed_pages": normalize_allowed_pages(row.get("allowed_pages")),
    }


def authenticate_login(username, password):
    username = (username or "").strip().lower()
    if not username.endswith(f"@{ALLOWED_EMAIL_DOMAIN}"):
        return None

    supabase_user = _supabase_login_user(username)
    if supabase_user:
        if supabase_user["password_hash"] and check_password_hash(supabase_user["password_hash"], password or ""):
            return {
                "username": supabase_user["email"],
                "role": supabase_user["role"],
                "allowed_pages": supabase_user["allowed_pages"] or allowed_pages_for_role(supabase_user["role"]),
            }
        return None

    override = LOGIN_USER_OVERRIDES.get(username)
    if override:
        if password == override["password"]:
            return {
                "username": username,
                "role": override["role"],
                "allowed_pages": normalize_allowed_pages(override.get("allowed_pages")),
            }
        return None

    if username in ALLOWED_USERS and password == SHARED_PASSWORD:
        role = "admin" if username.split("@")[0] in {"admin", "isaac"} else "user"
        return {
            "username": username,
            "role": role,
            "allowed_pages": allowed_pages_for_role(role),
        }
    return None


def service_dashboard_entry(service_name, waiting_loader):
    try:
        waiting = waiting_loader()
        return {
            "waiting": waiting,
            "active_users": get_active_users_for(service_name),
            "ok": True,
        }
    except Exception as exc:
        return {
            "waiting": None,
            "active_users": get_active_users_for(service_name),
            "ok": False,
            "error": str(exc),
        }


def load_service_account_info():
    creds_source = CREDENTIALS_FILE.strip()
    if not creds_source:
        raise RuntimeError("GOOGLE_APPLICATION_CREDENTIALS is empty.")

    if creds_source.startswith("{"):
        info = json.loads(creds_source)
        source_label = "GOOGLE_APPLICATION_CREDENTIALS (inline JSON)"
    else:
        abs_path = os.path.abspath(creds_source)
        if not os.path.exists(abs_path):
            raise RuntimeError(f"Credentials file not found: {abs_path}")
        with open(abs_path, "r", encoding="utf-8") as f:
            info = json.load(f)
        source_label = abs_path

    if info.get("type") != "service_account":
        raise RuntimeError(
            f"Credentials must be a service account JSON. "
            f"Found type={info.get('type')!r} in {source_label}"
        )

    private_key = info.get("private_key")
    if not private_key:
        raise RuntimeError(f"Missing private_key in {source_label}")

    if "\\n" in private_key and "\n" not in private_key:
        info["private_key"] = private_key.replace("\\n", "\n")

    return info, source_label


def get_gspread_client():
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds_info, creds_source = load_service_account_info()
    service_account = creds_info.get("client_email") or "unknown"
    key_id = creds_info.get("private_key_id") or "unknown"
    account_hint = f"Service account: {service_account}; key id: {key_id}; loaded from: {creds_source}"
    try:
        creds = Credentials.from_service_account_info(creds_info, scopes=scope)
        creds.refresh(Request())
    except RefreshError as e:
        message = str(e)
        if "invalid_grant" in message or "Invalid JWT Signature" in message:
            raise RuntimeError(
                "Google auth failed: invalid_grant / Invalid JWT Signature. "
                "Use a valid active service-account JSON key for this service account. "
                f"{account_hint}"
            ) from e
        raise RuntimeError(f"Google auth refresh failed ({account_hint}): {message}") from e
    except Exception as e:
        raise RuntimeError(f"Failed to initialize Google credentials ({account_hint}): {e}") from e
    return gspread.authorize(creds)


def digits_only(s: str) -> str:
    return re.sub(r"\D+", "", (s or "").strip())


def normalize_idnumber_for_fireberry(idnumber: str) -> str:
    id_digits = digits_only(idnumber)
    if 0 < len(id_digits) < 9:
        return id_digits.zfill(9)
    return id_digits


def first_number_clean(value: str) -> str:
    """
    Take the first number chunk from a string, keep only digits.
    If length >= 10 -> return first 10
    If length == 9 -> return 9
    Else -> return whatever digits exist
    """
    raw = (value or "").strip()
    if not raw:
        return ""

    parts = re.split(r"[\s,;]+", raw)
    for p in parts:
        d = digits_only(p)
        if d:
            if len(d) >= 10:
                return d[:10]
            if len(d) == 9:
                return d
            return d

    d = digits_only(raw)
    if not d:
        return ""
    if len(d) >= 10:
        return d[:10]
    if len(d) == 9:
        return d
    return d


def normalize_phone_with_zero(value: str) -> str:
    digits = digits_only(value)
    if not digits:
        return ""
    return digits if digits.startswith("0") else f"0{digits}"


def reserve_cgr_numbers(customers):
    normalized_customers = []
    for customer in customers:
        if not isinstance(customer, dict):
            continue
        domain = (customer.get("domain") or "").strip()
        numbercgr = normalize_phone_with_zero(customer.get("numbercgr") or "")
        if not domain or not numbercgr:
            continue
        normalized_customers.append({
            "domain": domain,
            "numbercgr": numbercgr,
        })

    if not normalized_customers:
        return {"updated": 0, "missing_numbers": []}

    customer_by_number = {}
    for customer in normalized_customers:
        customer_by_number[customer["numbercgr"]] = customer["domain"]

    client = get_gspread_client()
    cgr_ws = client.open_by_key(SPREADSHEET_ID).worksheet(CGR_SHEET_NAME)
    cgr_data = cgr_ws.get(f"A{CGR_START_ROW}:E")

    updates = []
    matched_numbers = set()
    current_date = datetime.now(ZoneInfo("Asia/Jerusalem")).strftime("%Y-%m-%d")

    for idx, row in enumerate(cgr_data):
        sheet_number = normalize_phone_with_zero(row[0] if len(row) >= 1 else "")
        if not sheet_number or sheet_number not in customer_by_number or sheet_number in matched_numbers:
            continue

        updates.append({
            "range": (
                f"{gspread.utils.rowcol_to_a1(CGR_START_ROW + idx, CGR_COL_DOMAIN)}:"
                f"{gspread.utils.rowcol_to_a1(CGR_START_ROW + idx, CGR_COL_USED)}"
            ),
            "values": [[customer_by_number[sheet_number], current_date, True]],
        })
        matched_numbers.add(sheet_number)

    if updates:
        cgr_ws.batch_update(updates)

    missing_numbers = sorted(number for number in customer_by_number if number not in matched_numbers)
    return {
        "updated": len(updates),
        "missing_numbers": missing_numbers,
    }


def is_checked(value) -> bool:
    text = str(value or "").strip().lower()
    return text in ("true", "yes", "1", "v", "\u2713", "\u2714")


def is_done_status(value) -> bool:
    return str(value or "").strip() == STATUS_DONE


def fireberry_lookup_by_idnumber(idnumber: str) -> dict:
    id_digits = normalize_idnumber_for_fireberry(idnumber)
    if not id_digits:
        return {"found": False, "domain": "", "did": ""}

    headers = {"tokenid": FIREBERRY_TOKENID}
    body = {
        "objecttype": 1,
        "page_size": 50,
        "page_number": 1,
        "fields": "pcfsystemfield179,accountname,pcfsystemfield256,pcfsystemfield164,pcfsystemfield166",
        "query": f"(idnumber = {id_digits})",
        "sort_type": "desc"
    }

    r = requests.post(FIREBERRY_URL, headers=headers, json=body, timeout=30)
    r.raise_for_status()
    resp = r.json()

    rows = []
    if isinstance(resp, dict):
        inner = resp.get("data")
        if isinstance(inner, dict) and isinstance(inner.get("Data"), list):
            rows = inner.get("Data", [])

    if not rows or not isinstance(rows[0], dict):
        return {"found": False, "domain": "", "did": ""}

    row = rows[0]
    domain = (row.get("pcfsystemfield179") or "").strip()

    main_raw = (row.get("pcfsystemfield166") or "").strip()
    range_raw = (row.get("pcfsystemfield164") or "").strip()
    did_raw = main_raw if main_raw else range_raw
    did = first_number_clean(did_raw)

    return {"found": True, "domain": domain, "did": did}

#//fireberry_lookup_by_idnumber
def fireberry_lookup_domain_by_record_id(record_id):

    headers = {"tokenid": FIREBERRY_TOKENID}

    body = {
        "objecttype": 1,
        "page_size": 1,
        "page_number": 1,
        "fields": "pcfsystemfield179",
        "query": f"(id = {record_id})"
    }

    try:

        r = requests.post(FIREBERRY_URL, headers=headers, json=body, timeout=30)
        r.raise_for_status()

        resp = r.json()

        rows = resp.get("data", {}).get("Data", [])

        if rows:
            return (rows[0].get("pcfsystemfield179") or "").strip()

    except Exception as e:
        print("Fireberry BOT lookup error:", e)

    return ""


def get_drive_service(readonly=True):
    scope = ["https://www.googleapis.com/auth/drive.readonly"] if readonly else ["https://www.googleapis.com/auth/drive"]
    creds_info, creds_source = load_service_account_info()
    try:
        creds = Credentials.from_service_account_info(creds_info, scopes=scope)
        creds.refresh(Request())
    except RefreshError as e:
        message = str(e)
        if "invalid_grant" in message or "Invalid JWT Signature" in message:
            raise RuntimeError(
                "Google auth failed: invalid_grant / Invalid JWT Signature. "
                "Use a valid active service-account JSON key for this service account. "
                f"Loaded from: {creds_source}"
            ) from e
        raise RuntimeError(f"Google auth refresh failed ({creds_source}): {message}") from e
    except Exception as e:
        raise RuntimeError(f"Failed to initialize Google Drive credentials ({creds_source}): {e}") from e
    return build("drive", "v3", credentials=creds)


def extract_order_id_from_record(filename: str) -> str:
    base_name = os.path.splitext(os.path.basename(filename or ""))[0]
    if not base_name:
        return ""
    # Primary rule: first 5 digits from the left side (allows leading spaces).
    match = re.match(r"\s*(\d{5})", base_name)
    if match:
        return match.group(1)
    # Fallback for names like "... - 12249.wav".
    tail_match = re.search(r"(\d{5})\s*$", base_name)
    return tail_match.group(1) if tail_match else ""


def normalize_domain_value(value: str) -> str:
    domain = (value or "").strip()
    if not domain:
        return ""
    if domain.lower() == "accepted":
        return ""
    return domain


def get_domain_from_crm(crmordernumber):
    try:
        if not crmordernumber:
            return ""
        if not FIREBERRY_TOKENID:
            return ""

        headers = {"tokenid": FIREBERRY_TOKENID}

        order_body = {
            "objecttype": 13,
            "page_size": 1,
            "page_number": 1,
            "fields": "accountid,CrmOrderNumber",
            "query": f"(CrmOrderNumber = '{crmordernumber}')",
            "sort_type": "desc"
        }
        order_resp = requests.post(FIREBERRY_URL, headers=headers, json=order_body, timeout=20)
        order_resp.raise_for_status()
        order_rows = order_resp.json().get("data", {}).get("Data", [])
        if not order_rows or not isinstance(order_rows[0], dict):
            return ""

        accountid = str(order_rows[0].get("accountid") or "").strip()
        if not accountid:
            return ""

        account_body = {
            "objecttype": 1,
            "page_size": 1,
            "page_number": 1,
            "fields": "accountid,pcfsystemfield179,accountname",
            "query": f"(accountid = '{accountid}')"
        }
        account_resp = requests.post(FIREBERRY_URL, headers=headers, json=account_body, timeout=20)
        account_resp.raise_for_status()
        account_rows = account_resp.json().get("data", {}).get("Data", [])
        if not account_rows or not isinstance(account_rows[0], dict):
            return ""

        value = account_rows[0].get("pcfsystemfield179")
        return normalize_domain_value(str(value).strip() if value is not None else "")

    except Exception as e:
        print("CRM error:", e)
        return ""


def get_pending_customers():
    """
    Returns customers where:
      H == ׳׳׳×׳™׳ AND K == ׳׳§׳•׳— ׳”׳•׳×׳§׳
    Also includes:
      - idnumber (hidden)
      - numbercgr from sheet ׳—׳™׳₪_׳¡׳׳¡ (only rows where column C empty)
      - cgr_row (for updates on export)
      - cgr_marked (green/yellow indicator from column B)
    """
    client = get_gspread_client()
    ws = client.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)

    data = ws.get_all_values()
    if not data or len(data) < 2:
        return []

    rows = data[1:]
    pending = []
    missing_text_rows = []

    for i, row in enumerate(rows, start=2):
        status = row[COL_STATUS - 1].strip() if len(row) >= COL_STATUS else ""
        k_value = row[COL_K - 1].strip() if len(row) >= COL_K else ""

        if status != STATUS_PENDING or k_value != K_REQUIRED_VALUE:
            continue

        name = row[COL_NAME - 1].strip() if len(row) >= COL_NAME else ""
        idnumber = row[COL_IDNUMBER - 1].strip() if len(row) >= COL_IDNUMBER else ""
        sms_text = row[COL_SMS_TEXT - 1].strip() if len(row) >= COL_SMS_TEXT else ""

        if not sms_text:
            missing_text_rows.append(i)
            continue

        pending.append({
            "sheet_row": i,
            "name": name,
            "idnumber": idnumber,
            "text": sms_text,
            "status": status
        })

    if missing_text_rows:
        try:
            ws.batch_update([
                {
                    "range": gspread.utils.rowcol_to_a1(row_number, COL_STATUS),
                    "values": [[STATUS_NO_SMS_TEXT]],
                }
                for row_number in missing_text_rows
            ])
        except Exception as exc:
            print(f"SMS missing-text status update warning: {exc}")

    # Attach NumberCGR from ׳—׳™׳₪_׳¡׳׳¡ (ONLY rows where column C empty)
    try:
        if pending:
            free_numbers = get_available_cgr_numbers()

            # attach numbers to customers
            for idx, cust in enumerate(pending):
                if idx < len(free_numbers):
                    cust["numbercgr"] = free_numbers[idx]["number"]
                    cust["cgr_row"] = free_numbers[idx]["row"]
                    cust["cgr_marked"] = free_numbers[idx]["marked"]
                else:
                    cust["numbercgr"] = ""
                    cust["cgr_row"] = None
                    cust["cgr_marked"] = False

    except Exception:
        for cust in pending:
            cust["numbercgr"] = ""
            cust["cgr_row"] = None
            cust["cgr_marked"] = False

    return pending


def get_available_cgr_numbers(limit=None):
    client = get_gspread_client()
    cgr_ws = client.open_by_key(SPREADSHEET_ID).worksheet(CGR_SHEET_NAME)
    cgr_data = cgr_ws.get(f"A{CGR_START_ROW}:C")

    free_numbers = []

    for idx, row in enumerate(cgr_data):
        a_val = row[0] if len(row) >= 1 else ""
        b_val = row[1] if len(row) >= 2 else ""
        c_val = row[2] if len(row) >= 3 else ""

        if (c_val or "").strip():
            continue

        numbercgr = normalize_phone_with_zero(a_val)
        if not numbercgr:
            continue

        b_norm = (b_val or "").strip().upper()
        marked = bool(b_norm) and b_norm not in ("FALSE", "0", "NO")

        free_numbers.append({
            "number": numbercgr,
            "row": CGR_START_ROW + idx,
            "marked": marked,
        })

        if isinstance(limit, int) and limit > 0 and len(free_numbers) >= limit:
            break

    return free_numbers


def get_recordings_waiting_count():
    service = get_drive_service(readonly=True)
    results = service.files().list(
        q=f"'{DRIVE_FOLDER_ID}' in parents and mimeType='audio/wav' and trashed=false",
        fields="files(id)"
    ).execute()
    return len(results.get("files", []))


def parse_report_date(value, preferred_order="mdy"):
    raw = str(value or "").strip()
    if not raw:
        return None

    raw = raw.split()[0]
    parts = re.split(r"[./-]", raw)
    if len(parts) != 3:
        return None

    try:
        first, second, year = [int(part) for part in parts]
        if year < 100:
            year += 2000

        if first > 12 and second <= 12:
            day, month = first, second
        elif second > 12 and first <= 12:
            month, day = first, second
        elif preferred_order == "dmy":
            day, month = first, second
        else:
            month, day = first, second

        return datetime(year, month, day).date()
    except ValueError:
        return None


def report_checkbox_marked(value):
    text = str(value or "").strip().lower()
    return text in ("true", "yes", "1", "v", "\u2713", "\u2714")


def parse_drive_modified_time(value):
    raw = str(value or "").strip()
    if not raw:
        return None

    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return parsed.astimezone(ZoneInfo("Asia/Jerusalem")).date()
    except ValueError:
        return None


def normalize_recording_order_id(value):
    digits = digits_only(str(value or ""))
    return digits[:5] if len(digits) >= 5 else ""


def normalize_recording_music_type(value):
    text = re.sub(r"\s+", " ", str(value or "").strip())
    if not text:
        return "without_music"
    if RECORDING_WITHOUT_MUSIC in text:
        return "without_music"
    if RECORDING_WITH_MUSIC in text:
        return "with_music"
    return "unknown"


def extract_recording_business_name(filename):
    base_name = os.path.splitext(os.path.basename(filename or ""))[0].strip()
    order_id = extract_order_id_from_record(base_name)
    if not order_id:
        return base_name

    name = re.sub(rf"^\s*{re.escape(order_id)}\s*[-–—]?\s*", "", base_name)
    name = re.sub(rf"\s*[-–—]\s*{re.escape(order_id)}\s*$", "", name)
    name = re.sub(r"\b\d{7,10}\b", "", name)
    name = re.sub(r"\s*[-–—]\s*$", "", name)
    return re.sub(r"\s+", " ", name).strip()


def get_recording_music_type_by_order(client, config):
    ws = client.open_by_key(SPREADSHEET_ID).worksheet(config["category_sheet"])
    rows = ws.get_all_values()[1:]
    order_col = config["order_col"]
    category_col = config["category_col"]
    music_by_order = {}

    for row in rows:
        order_id = normalize_recording_order_id(row[order_col - 1] if len(row) >= order_col else "")
        if not order_id:
            continue
        music_by_order[order_id] = normalize_recording_music_type(
            row[category_col - 1] if len(row) >= category_col else ""
        )

    return music_by_order


def get_done_recordings_for_month(selected_month, client, config):
    music_by_order = get_recording_music_type_by_order(client, config)
    service = get_drive_service(readonly=True)
    query = (
        f"'{DRIVE_DONE_FOLDER_ID}' in parents and "
        "mimeType = 'audio/wav' and trashed=false"
    )
    recordings = []
    page_token = None

    while True:
        response = service.files().list(
            q=query,
            fields="nextPageToken, files(id, name, modifiedTime)",
            pageSize=1000,
            pageToken=page_token,
        ).execute()

        for file_item in response.get("files", []):
            modified_date = parse_drive_modified_time(file_item.get("modifiedTime"))
            if not modified_date:
                continue
            if modified_date.year == selected_month.year and modified_date.month == selected_month.month:
                order_id = extract_order_id_from_record(file_item.get("name", ""))
                if not order_id:
                    order_id = normalize_recording_order_id(file_item.get("name", ""))
                music_type = music_by_order.get(order_id, "unknown")
                recordings.append({
                    "order_id": order_id,
                    "business_name": extract_recording_business_name(file_item.get("name", "")),
                    "file_name": file_item.get("name", ""),
                    "modified_date": modified_date,
                    "music_type": music_type if music_type == "with_music" else "without_music",
                })

        page_token = response.get("nextPageToken")
        if not page_token:
            break

    return recordings


def count_done_recordings_from_drive(selected_month, client, config):
    recordings = get_done_recordings_for_month(selected_month, client, config)
    result = {
        "count": len(recordings),
        "children": [
            {"key": "recordings_with_music", "label": RECORDING_WITH_MUSIC, "count": 0},
            {"key": "recordings_without_music", "label": RECORDING_WITHOUT_MUSIC, "count": 0},
        ],
    }

    for recording in recordings:
        if recording["music_type"] == "with_music":
            result["children"][0]["count"] += 1
        else:
            result["children"][1]["count"] += 1

    return result


def iter_month_values(start_month, end_month):
    current = datetime(start_month.year, start_month.month, 1)
    finish = datetime(end_month.year, end_month.month, 1)

    while current <= finish:
        yield current.strftime("%Y-%m")
        if current.month == 12:
            current = datetime(current.year + 1, 1, 1)
        else:
            current = datetime(current.year, current.month + 1, 1)


def count_done_recordings_by_month(start_month, end_month):
    service = get_drive_service(readonly=True)
    query = (
        f"'{DRIVE_DONE_FOLDER_ID}' in parents and "
        "mimeType = 'audio/wav' and trashed=false"
    )
    totals = {month_value: 0 for month_value in iter_month_values(start_month, end_month)}
    page_token = None

    while True:
        response = service.files().list(
            q=query,
            fields="nextPageToken, files(modifiedTime)",
            pageSize=1000,
            pageToken=page_token,
        ).execute()

        for file_item in response.get("files", []):
            modified_date = parse_drive_modified_time(file_item.get("modifiedTime"))
            if not modified_date:
                continue

            month_value = modified_date.strftime("%Y-%m")
            if month_value in totals:
                totals[month_value] += 1

        page_token = response.get("nextPageToken")
        if not page_token:
            break

    return totals


def count_sheet_feature_by_month(config, start_month, end_month, client):
    ws = client.open_by_key(SPREADSHEET_ID).worksheet(config["sheet"])
    rows = ws.get_all_values()[1:]
    totals = {month_value: 0 for month_value in iter_month_values(start_month, end_month)}

    for row in rows:
        status_col = config["status_col"]
        date_col = config["date_col"]
        status = row[status_col - 1].strip() if len(row) >= status_col else ""
        date_value = row[date_col - 1].strip() if len(row) >= date_col else ""

        if config.get("checkbox"):
            is_done = report_checkbox_marked(status)
        else:
            is_done = status == config["status_value"]

        if not is_done:
            continue

        done_date = parse_report_date(date_value, config.get("date_order", "mdy"))
        if not done_date:
            continue

        month_value = done_date.strftime("%Y-%m")
        if month_value in totals:
            totals[month_value] += 1

    return totals


def get_feature_report_counts(month_value):
    selected_month = datetime.strptime(month_value, "%Y-%m")
    client = get_gspread_client()
    reports = []

    for service_key, config in FEATURE_REPORT_SERVICES.items():
        if config.get("source") == "drive_done":
            recording_counts = count_done_recordings_from_drive(selected_month, client, config)
            reports.append({
                "key": service_key,
                "label": config["label"],
                "count": recording_counts["count"],
                "children": recording_counts["children"],
            })
            continue

        ws = client.open_by_key(SPREADSHEET_ID).worksheet(config["sheet"])
        rows = ws.get_all_values()[1:]
        count = 0

        for row in rows:
            status_col = config["status_col"]
            date_col = config["date_col"]
            status = row[status_col - 1].strip() if len(row) >= status_col else ""
            date_value = row[date_col - 1].strip() if len(row) >= date_col else ""

            if config.get("checkbox"):
                is_done = report_checkbox_marked(status)
            else:
                is_done = status == config["status_value"]

            if not is_done:
                continue

            done_date = parse_report_date(date_value, config.get("date_order", "mdy"))
            if not done_date:
                continue

            if done_date.year == selected_month.year and done_date.month == selected_month.month:
                count += 1

        reports.append({
            "key": service_key,
            "label": config["label"],
            "count": count,
        })

    return {
        "month": month_value,
        "month_display": selected_month.strftime("%m/%Y"),
        "services": reports,
        "total": sum(item["count"] for item in reports),
    }


def get_feature_report_monthly_totals(start_month_value, end_month_value):
    start_month = datetime.strptime(start_month_value, "%Y-%m")
    end_month = datetime.strptime(end_month_value, "%Y-%m")
    if start_month > end_month:
        raise ValueError("Start month must be before end month")

    monthly_totals = {month_value: 0 for month_value in iter_month_values(start_month, end_month)}
    client = get_gspread_client()

    for config in FEATURE_REPORT_SERVICES.values():
        if config.get("source") == "drive_done":
            service_totals = count_done_recordings_by_month(start_month, end_month)
        else:
            service_totals = count_sheet_feature_by_month(config, start_month, end_month, client)

        for month_value, count in service_totals.items():
            monthly_totals[month_value] += count

    months = []
    for month_value in iter_month_values(start_month, end_month):
        month_label = datetime.strptime(month_value, "%Y-%m").strftime("%m/%Y")
        months.append({
            "month": month_value,
            "month_display": month_label,
            "total": monthly_totals[month_value],
        })

    return {
        "start_month": start_month_value,
        "end_month": end_month_value,
        "months": months,
    }


def get_feature_report_graph_range():
    now = datetime.now(ZoneInfo("Asia/Jerusalem"))
    start_year = now.year if now.month >= 4 else now.year - 1
    start_month = f"{start_year}-04"
    end_month = now.strftime("%Y-%m")
    return start_month, end_month


def normalize_feature_status_customer_id(value):
    digits_only = re.sub(r"\D", "", str(value or ""))
    if not digits_only:
        return ""
    return digits_only.lstrip("0") or digits_only


def collapse_feature_status_entries(entries):
    if not entries:
        return []

    filtered = []
    for entry in entries:
        status_value = (entry.get("status") or "").strip()
        if status_value == "כפילות":
            continue
        filtered.append({
            "business_name": (entry.get("business_name") or "").strip(),
            "customer_id": (entry.get("customer_id") or "").strip(),
            "status": status_value or "לא הוגדר",
        })

    source_entries = filtered or [{
        "business_name": (entries[0].get("business_name") or "").strip() if entries else "",
        "customer_id": (entries[0].get("customer_id") or "").strip() if entries else "",
        "status": "לא הוגדר",
    }]
    statuses = [entry["status"] for entry in source_entries]

    if "בוצע" in statuses:
        final_status = "בוצע"
    else:
        final_status = next((status for status in statuses if status != "לא הוגדר"), "לא הוגדר")

    primary_entry = next(
        (entry for entry in source_entries if entry["status"] == final_status),
        source_entries[0],
    )
    return [{
        "business_name": primary_entry["business_name"],
        "customer_id": primary_entry["customer_id"],
        "status": final_status,
    }]


def lookup_feature_status_by_customer_id(customer_id):
    normalized_customer_id = normalize_feature_status_customer_id(customer_id)
    if not normalized_customer_id:
        raise ValueError("יש להזין מספר ח.פ של העסק")

    client = get_gspread_client()
    spreadsheet = client.open_by_key(SPREADSHEET_ID)
    services = []
    business_names = []

    for config in FEATURE_STATUS_SERVICES:
        ws = spreadsheet.worksheet(config["sheet"])
        rows = ws.get_all_values()
        entries = []

        for row_index, row in enumerate(rows[1:], start=2):
            row_customer_id = normalize_feature_status_customer_id(row[1] if len(row) >= 2 else "")
            if row_customer_id != normalized_customer_id:
                continue

            business_name = (row[0] if len(row) >= 1 else "").strip()
            status_value = (row[config["status_col"] - 1] if len(row) >= config["status_col"] else "").strip()
            row_customer_display = (row[1] if len(row) >= 2 else "").strip()

            if business_name and business_name not in business_names:
                business_names.append(business_name)

            entries.append({
                "row": row_index,
                "business_name": business_name,
                "customer_id": row_customer_display,
                "status": status_value or "לא הוגדר",
            })

        entries = collapse_feature_status_entries(entries)

        services.append({
            "key": config["key"],
            "label": config["label"],
            "sheet": config["sheet"],
            "found": bool(entries),
            "entry_count": len(entries),
            "entries": entries,
        })

    found_count = len([service for service in services if service["found"]])
    return {
        "customer_id": normalized_customer_id,
        "business_names": business_names,
        "services": services,
        "found_count": found_count,
        "missing_count": len(services) - found_count,
    }


def get_pdf_font_name(weight="regular", script="hebrew"):
    cache_key = f"{script}:{weight}"
    cached_name = PDF_FONT_NAMES.get(cache_key)
    if cached_name:
        return cached_name

    font_alias = f"AppPdfFont{script.title().replace('_', '')}{weight.title().replace('_', '')}"
    font_paths = PDF_FONT_CANDIDATES.get(script, {}).get(weight, [])

    for font_path in font_paths:
        if not font_path or not os.path.exists(font_path):
            continue
        try:
            pdfmetrics.registerFont(TTFont(font_alias, font_path))
            PDF_FONT_NAMES[cache_key] = font_alias
            return font_alias
        except Exception:
            continue

    fallback = {
        "regular": "Helvetica",
        "bold": "Helvetica-Bold",
        "extra_bold": "Helvetica-Bold",
    }.get(weight, "Helvetica")
    PDF_FONT_NAMES[cache_key] = fallback
    return fallback


def format_rtl_pdf_text(value):
    text = str(value or "").replace("\r\n", "\n").strip()
    if not text:
        return "-"
    if not HEBREW_TEXT_RE.search(text):
        return text

    return "\n".join(get_display(line) for line in text.split("\n"))


def pdf_paragraph(value, style, rtl=False, latin_font_name=None, hebrew_font_name=None):
    text = format_rtl_pdf_text(value) if rtl else str(value or "-").replace("\r\n", "\n").strip() or "-"
    paragraph_style = style
    if latin_font_name and hebrew_font_name:
        font_name = hebrew_font_name if HEBREW_TEXT_RE.search(str(value or "")) else latin_font_name
        paragraph_style = ParagraphStyle(
            f"{style.name}{font_name}",
            parent=style,
            fontName=font_name,
        )
    return Paragraph(xml_escape(text).replace("\n", "<br/>"), paragraph_style)


def build_pdf_buffer(title, metadata_rows, headers, rows, rtl_columns=None, emphasis_columns=None, emphasis_meta_labels=None):
    rtl_columns = set(rtl_columns or [])
    emphasis_columns = set(emphasis_columns or [])
    emphasis_meta_labels = {str(label) for label in (emphasis_meta_labels or [])}
    buffer = io.BytesIO()
    latin_bold_font = get_pdf_font_name("bold", "latin")
    latin_extra_bold_font = get_pdf_font_name("extra_bold", "latin")
    hebrew_bold_font = get_pdf_font_name("bold", "hebrew")
    hebrew_extra_bold_font = get_pdf_font_name("extra_bold", "hebrew")
    styles = getSampleStyleSheet()
    normal_style = styles.get("Normal") if hasattr(styles, "get") else None
    heading_style = styles.get("Heading1", normal_style) if hasattr(styles, "get") else normal_style
    body_style = styles.get("BodyText", normal_style) if hasattr(styles, "get") else normal_style
    title_style = ParagraphStyle(
        "PdfTitle",
        parent=heading_style,
        fontName=hebrew_extra_bold_font,
        fontSize=19,
        leading=23,
        alignment=TA_RIGHT,
        textColor=colors.HexColor("#0f2f57"),
        spaceAfter=10,
    )
    meta_label_style = ParagraphStyle(
        "PdfMetaLabel",
        parent=body_style,
        fontName=latin_bold_font,
        fontSize=11,
        leading=14,
        alignment=TA_LEFT,
        textColor=colors.HexColor("#233f65"),
    )
    meta_value_style = ParagraphStyle(
        "PdfMetaValue",
        parent=body_style,
        fontName=latin_bold_font,
        fontSize=11,
        leading=14,
        alignment=TA_RIGHT,
        textColor=colors.HexColor("#0f172a"),
    )
    meta_value_emphasis_style = ParagraphStyle(
        "PdfMetaValueEmphasis",
        parent=meta_value_style,
        fontName=latin_extra_bold_font,
        fontSize=12,
        leading=15,
        textColor=colors.HexColor("#0b1f3a"),
    )
    header_style = ParagraphStyle(
        "PdfHeader",
        parent=body_style,
        fontName=latin_extra_bold_font,
        fontSize=11,
        leading=13,
        alignment=TA_CENTER,
        textColor=colors.white,
    )
    cell_style = ParagraphStyle(
        "PdfCell",
        parent=body_style,
        fontName=latin_bold_font,
        fontSize=10,
        leading=12,
        alignment=TA_RIGHT,
        textColor=colors.HexColor("#111827"),
    )
    emphasis_cell_style = ParagraphStyle(
        "PdfCellEmphasis",
        parent=cell_style,
        fontName=latin_extra_bold_font,
        fontSize=11,
        leading=13,
        textColor=colors.HexColor("#0b1f3a"),
    )

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=14 * mm,
        leftMargin=14 * mm,
        topMargin=14 * mm,
        bottomMargin=14 * mm,
    )

    story = [pdf_paragraph(title, title_style, rtl=True, latin_font_name=latin_extra_bold_font, hebrew_font_name=hebrew_extra_bold_font)]
    for label, value in metadata_rows:
        value_style = meta_value_emphasis_style if str(label) in emphasis_meta_labels else meta_value_style
        story.append(
            Table(
                [[
                    pdf_paragraph(label, meta_label_style, latin_font_name=latin_bold_font, hebrew_font_name=hebrew_bold_font),
                    pdf_paragraph(value, value_style, rtl=True, latin_font_name=latin_extra_bold_font if str(label) in emphasis_meta_labels else latin_bold_font, hebrew_font_name=hebrew_extra_bold_font if str(label) in emphasis_meta_labels else hebrew_bold_font),
                ]],
                colWidths=[40 * mm, 130 * mm],
                hAlign="RIGHT",
                style=TableStyle([
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]),
            )
        )
    story.append(Spacer(1, 10))

    table_data = [[
        pdf_paragraph(header, header_style, latin_font_name=latin_extra_bold_font, hebrew_font_name=hebrew_extra_bold_font)
        for header in headers
    ]]
    for row in rows:
        table_data.append([
            pdf_paragraph(
                value,
                emphasis_cell_style if index in emphasis_columns else cell_style,
                rtl=index in rtl_columns,
                latin_font_name=latin_extra_bold_font if index in emphasis_columns else latin_bold_font,
                hebrew_font_name=hebrew_extra_bold_font if index in emphasis_columns else hebrew_bold_font,
            )
            for index, value in enumerate(row)
        ])

    table = Table(table_data, repeatRows=1, hAlign="RIGHT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1d4f91")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.65, colors.HexColor("#c7d4e6")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fbff")]),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(table)
    doc.build(story)
    buffer.seek(0)
    return buffer


def build_ticket_board_export_rows(report):
    rows = []
    for index, ticket in enumerate(report["tickets"], start=1):
        details = ticket.get("details") or {}
        if (ticket.get("board_slug") or "").strip().lower() == "support":
            reference_value = details.get("business_name") or ticket.get("service_type") or ""
            secondary_value = details.get("service_address") or ""
        elif (ticket.get("board_slug") or "").strip().lower() == "hot-kiryot":
            reference_value = details.get("call_number") or ""
            secondary_value = details.get("customer_name") or ""
        else:
            reference_value = details.get("terminal_number") or ""
            secondary_value = details.get("address") or ""
        rows.append({
            "counter": index,
            "reference": reference_value,
            "secondary": secondary_value,
        })
    return rows


def ticket_board_export_config(board_slug):
    normalized_board = (board_slug or "").strip().lower()
    if normalized_board == "hot-kiryot":
        return {
            "headers": ["#", "מספר קריאה", "שם לקוח"],
            "csv_fields": ["counter", "call_number", "customer_name"],
            "row_mapper": lambda row: {
                "counter": row["counter"],
                "call_number": row["reference"],
                "customer_name": row["secondary"],
            },
            "pdf_row_mapper": lambda row: [row["counter"], row["reference"], row["secondary"]],
            "rtl_columns": {1, 2},
        }
    if normalized_board == "support":
        return {
            "headers": ["#", "Business", "Address"],
            "csv_fields": ["counter", "business_name", "address"],
            "row_mapper": lambda row: {
                "counter": row["counter"],
                "business_name": row["reference"],
                "address": row["secondary"],
            },
            "pdf_row_mapper": lambda row: [row["counter"], row["reference"], row["secondary"]],
            "rtl_columns": {2},
        }
    return {
        "headers": ["#", "Terminal Number", "Address"],
        "csv_fields": ["counter", "terminal_number", "address"],
        "row_mapper": lambda row: {
            "counter": row["counter"],
            "terminal_number": row["reference"],
            "address": row["secondary"],
        },
        "pdf_row_mapper": lambda row: [row["counter"], row["reference"], row["secondary"]],
        "rtl_columns": {2},
    }


def build_features_export_rows(report):
    rows = []
    for service in report.get("services", []):
        rows.append([service.get("label") or "", report.get("month_display") or "", service.get("count") or 0])
        for child in service.get("children") or []:
            rows.append([f"{service.get('label') or ''} - {child.get('label') or ''}", report.get("month_display") or "", child.get("count") or 0])
    rows.append(["Total", report.get("month_display") or "", report.get("total") or 0])
    return rows


# ================= ROOT =================
@app.route("/")
def root():
    return redirect(url_for("login"))


# ================= LOGIN =================
@app.route("/login", methods=["GET", "POST"])
def login():

    # If already logged in ג†’ go to home
    if session.get("logged_in"):
        return redirect(url_for("home"))

    if request.method == "POST":
        username = (request.form.get("username") or "").strip().lower()
        password = request.form.get("password")

        auth = authenticate_login(username, password)
        if auth:
            session["logged_in"] = True
            session["username"] = auth["username"]
            session["role"] = auth["role"]
            session["allowed_pages"] = auth["allowed_pages"]
            return redirect(first_allowed_route())

        return render_template("login.html", error="Invalid username or password")

    return render_template("login.html")


# ================= HOME =================
@app.route("/home")
def home():

    if not session.get("logged_in"):
        return redirect(url_for("login"))
    if not user_can_access_page("home"):
        return redirect(first_allowed_route())

    register_service_activity("dashboard")
    return render_template("home.html", current_user=session.get("username", ""))


@app.route("/portals")
def portals_page():

    if not session.get("logged_in"):
        return redirect(url_for("login"))
    if not user_can_access_page("home"):
        return redirect(first_allowed_route())

    register_service_activity("dashboard")
    return render_template("portals.html", current_user=session.get("username", ""))


@app.route("/configuration")
def configuration_page():

    if not session.get("logged_in"):
        return redirect(url_for("login"))
    if not user_can_access_page("configuration"):
        return redirect(first_allowed_route())

    register_service_activity("configuration")
    return render_template("configuration.html", current_user=session.get("username", ""))


# ================= SMS PAGE =================
@app.route("/sms")
def sms_page():

    if not session.get("logged_in"):
        return redirect(url_for("login"))

    register_service_activity("sms")
    return render_template("index.html", current_user=session.get("username", ""))


# ================= BOT PAGE =================
@app.route("/bot")
def bot_page():

    if not session.get("logged_in"):
        return redirect(url_for("login"))

    register_service_activity("bot")
    return render_template("bot.html", current_user=session.get("username", ""))


# ================= F2M PAGE =================
@app.route("/f2m")
def f2m_page():

    if not session.get("logged_in"):
        return redirect(url_for("login"))

    register_service_activity("f2m")
    return render_template("f2m.html", current_user=session.get("username", ""))


# ================= RECORDING STORAGE PAGE =================
@app.route("/recording-storage")
def recording_storage_page():

    if not session.get("logged_in"):
        return redirect(url_for("login"))

    register_service_activity("recording_storage")
    return render_template("recording_storage.html", current_user=session.get("username", ""))


# ================= HUMAN SERVICE PAGE =================
@app.route("/human-service")
def human_service_page():

    if not session.get("logged_in"):
        return redirect(url_for("login"))

    register_service_activity("human_service")
    return render_template("human_service.html", current_user=session.get("username", ""))


# ================= RECORD PAGE =================
@app.route("/record")
def record_page():

    if not session.get("logged_in"):
        return redirect(url_for("login"))

    register_service_activity("recordings")
    return render_template("record.html", current_user=session.get("username", ""))


@app.route("/features-report")
def features_report_page():

    if not session.get("logged_in"):
        return redirect(url_for("login"))

    return render_template("features_report.html", current_user=session.get("username", ""))


@app.route("/features-status")
def features_status_page():
    return render_template(
        "features_status.html",
        current_user=session.get("username", ""),
    )


@app.route("/features-status-data")
def features_status_data():
    customer_id = request.args.get("customer_id", "")
    try:
        payload = lookup_feature_status_by_customer_id(customer_id)
    except ValueError as exc:
        return api_error(exc, 400, "missing_customer_id")
    except Exception as exc:
        return api_error(exc, 500, "google_auth_or_sheet_error")
    return jsonify({"ok": True, **payload})


@app.route("/features-report-data")
def features_report_data():

    if not session.get("logged_in"):
        return redirect(url_for("login"))

    month_value = request.args.get("month", datetime.now().strftime("%Y-%m"))

    try:
        report = get_feature_report_counts(month_value)
    except ValueError:
        return jsonify({"ok": False, "error": "Invalid month"}), 400
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

    return jsonify({"ok": True, "report": report})


@app.route("/features-report-export")
def features_report_export():

    if not session.get("logged_in"):
        return redirect(url_for("login"))

    month_value = request.args.get("month", datetime.now().strftime("%Y-%m"))
    export_format = (request.args.get("format") or "pdf").strip().lower()

    try:
        report = get_feature_report_counts(month_value)
    except ValueError:
        return jsonify({"ok": False, "error": "Invalid month"}), 400
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

    if export_format == "csv":
        rows = [["Service", "Month", "Completed Count"], *build_features_export_rows(report)]
        output = io.StringIO()
        for row in rows:
            output.write(",".join(f'"{str(value).replace(chr(34), chr(34) + chr(34))}"' for value in row))
            output.write("\r\n")
        csv_buffer = io.BytesIO(("\ufeff" + output.getvalue()).encode("utf-8"))
        csv_buffer.seek(0)
        return send_file(
            csv_buffer,
            mimetype="text/csv",
            as_attachment=True,
            download_name=f"features-report-{report['month']}.csv",
        )

    rows = build_features_export_rows(report)
    pdf_buffer = build_pdf_buffer(
        title="דו\"ח פיצ'רים",
        metadata_rows=[
            ("Month", report.get("month_display") or ""),
            ("Total", report.get("total") or 0),
        ],
        headers=["Service", "Month", "Completed Count"],
        rows=rows,
        rtl_columns={0},
        emphasis_columns={1, 2},
        emphasis_meta_labels={"Month", "Total"},
    )
    return send_file(
        pdf_buffer,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"features-report-{report['month']}.pdf",
    )


@app.route("/features-report-monthly-totals")
def features_report_monthly_totals():

    if not session.get("logged_in"):
        return redirect(url_for("login"))

    default_start_month, default_end_month = get_feature_report_graph_range()
    start_month = request.args.get("start_month", default_start_month)
    end_month = request.args.get("end_month", default_end_month)

    try:
        totals = get_feature_report_monthly_totals(start_month, end_month)
    except ValueError:
        return jsonify({"ok": False, "error": "Invalid month range"}), 400
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

    return jsonify({"ok": True, **totals})


@app.route("/features-report-recordings-detail")
def features_report_recordings_detail():

    if not session.get("logged_in"):
        return redirect(url_for("login"))

    month_value = request.args.get("month", datetime.now().strftime("%Y-%m"))

    try:
        selected_month = datetime.strptime(month_value, "%Y-%m")
    except ValueError:
        return jsonify({"ok": False, "error": "Invalid month"}), 400

    client = get_gspread_client()
    config = FEATURE_REPORT_SERVICES["recordings"]
    recordings = get_done_recordings_for_month(selected_month, client, config)
    recordings.sort(key=lambda item: (item["modified_date"], item["order_id"], item["business_name"]))

    rows = [["שם העסק", "מס' הזמנה"]]
    for recording in recordings:
        rows.append([recording["business_name"], recording["order_id"]])

    output = io.StringIO()
    for row in rows:
        output.write(",".join(f'"{str(value).replace(chr(34), chr(34) + chr(34))}"' for value in row))
        output.write("\n")

    data = io.BytesIO(("\ufeff" + output.getvalue()).encode("utf-8"))
    return send_file(
        data,
        mimetype="text/csv",
        as_attachment=True,
        download_name=f"recordings_detail_{month_value}.csv",
    )


@app.route("/dashboard-data")
def dashboard_data():
    if not session.get("logged_in"):
        return api_error("Login required", 401, "login_required")

    register_service_activity("dashboard")

    return jsonify({
        "ok": True,
        "sms": service_dashboard_entry("sms", lambda: len(get_pending_customers())),
        "bot": service_dashboard_entry("bot", lambda: len(get_bot_customers())),
        "recordings": service_dashboard_entry("recordings", get_recordings_waiting_count),
        "f2m": service_dashboard_entry("f2m", lambda: len(get_f2m_customers())),
        "recording_storage": service_dashboard_entry("recording_storage", lambda: len(get_recording_storage_customers())),
        "human_service": service_dashboard_entry("human_service", lambda: len(get_human_service_customers())),
        "support_tickets": service_dashboard_entry(
            "support_tickets",
            lambda: len([t for t in load_support_tickets("support") if support_ticket_is_open(t)]),
        ),
        "pais_tickets": service_dashboard_entry(
            "pais_tickets",
            lambda: len([t for t in load_support_tickets("pais") if support_ticket_is_open(t)]),
        ),
        "hot_tickets": service_dashboard_entry(
            "hot_tickets",
            lambda: len([t for t in load_support_tickets("hot-kiryot") if support_ticket_is_open(t)]),
        ),
        "nastia_tickets": service_dashboard_entry(
            "nastia_tickets",
            lambda: len([
                t for t in load_support_tickets()
                if board_supports_coordination(t.get("board_slug")) and status_is_coordination_pending(t.get("status"))
            ]),
        ),
    })


def render_ticket_board_page(board_slug):
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    board = get_ticket_board(board_slug)
    register_service_activity(support_page_key(board_slug))
    allowed_pages = allowed_pages_for_current_user()
    assigned_technician_mode = support_user_is_assigned_technician()
    return render_template(
        "support_tickets.html",
        current_user=session.get("username", ""),
        is_admin=support_user_is_admin(),
        support_user=support_user_name(),
        support_users=TECHNICIAN_SUPPORT_USERS,
        technician_users=TECHNICIAN_SUPPORT_USERS,
        ticket_boards=load_ticket_boards(),
        ticket_board=board,
        page_mode="board",
        page_title=board["name"],
        page_subtitle=board["name"],
        page_icon_path=board.get("icon_path") or "",
        ticket_queue="",
        show_create_button=not assigned_technician_mode,
        show_pais_report=board_has_coordination_report(board["slug"]) and not assigned_technician_mode,
        service_types=SUPPORT_SERVICE_TYPES,
        ticket_types=SUPPORT_TICKET_TYPES,
        priorities=SUPPORT_PRIORITIES,
        support_delivery_options=SUPPORT_DELIVERY_OPTIONS,
        support_customer_types=SUPPORT_CUSTOMER_TYPES,
        support_statuses=SUPPORT_STATUSES,
        pais_statuses=PAIS_STATUSES,
        nastia_notification_email=NASTIA_NOTIFICATION_EMAIL,
        ticket_operator_mode="assigned_technician" if assigned_technician_mode else "default",
        can_upload_ticket_attachments=True,
        can_delete_ticket_attachments=not assigned_technician_mode,
        default_ticket_scope="my" if assigned_technician_mode else "all",
        can_access_home="home" in allowed_pages,
        can_access_support="support_tickets" in allowed_pages,
        can_access_pais="pais_tickets" in allowed_pages,
        can_access_hot="hot_tickets" in allowed_pages,
        can_access_nastia="nastia_tickets" in allowed_pages,
    )


@app.route("/support-tickets")
def support_tickets_page():
    return render_ticket_board_page("support")


@app.route("/support-tickets-storage-health")
def support_tickets_storage_health():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    if not support_user_is_admin():
        return jsonify({"ok": False, "message": "Admin access required"}), 403

    diagnostics = recent_attachment_diagnostics(limit=5)
    attachment_mode = "supabase" if supabase_storage_enabled() else "local"
    warning = ""
    if running_on_vercel() and attachment_mode == "local":
        warning = (
            "Attachments are currently using local storage on Vercel. "
            "Set SUPABASE_STORAGE_BUCKET to keep uploaded images available."
        )

    return jsonify({
        "ok": True,
        "runtime": {
            "on_vercel": running_on_vercel(),
            "ticketing_uses_supabase": supabase_ticketing_enabled(),
            "storage_uses_supabase": supabase_storage_enabled(),
            "supabase_url_configured": bool(SUPABASE_URL),
            "supabase_key_configured": bool(SUPABASE_KEY),
            "supabase_storage_bucket_configured": bool(SUPABASE_STORAGE_BUCKET),
            "supabase_storage_bucket": SUPABASE_STORAGE_BUCKET,
            "supabase_bucket_url_configured": bool(SUPABASE_BUCKET_URL),
            "supabase_bucket_region_configured": bool(SUPABASE_BUCKET_REGION),
            "supabase_bucket_access_key_configured": bool(SUPABASE_BUCKET_ACCESS_KEY),
            "supabase_bucket_secret_key_configured": bool(SUPABASE_BUCKET_SECRET_KEY),
            "attachment_mode": attachment_mode,
            "warning": warning,
        },
        "recent_attachments": diagnostics["items"],
        "load_error": diagnostics["load_error"],
    })


@app.route("/pais-tickets")
def pais_tickets_page():
    return render_ticket_board_page("pais")


@app.route("/hot-kiryot-tickets")
def hot_kiryot_tickets_page():
    return render_ticket_board_page("hot-kiryot")


@app.route("/nastia-tickets")
def nastia_tickets_page():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    if support_user_is_assigned_technician():
        return redirect(first_allowed_route())
    board = get_ticket_board("pais")
    register_service_activity("nastia_tickets")
    allowed_pages = allowed_pages_for_current_user()
    return render_template(
        "support_tickets.html",
        current_user=session.get("username", ""),
        is_admin=support_user_is_admin(),
        support_user=support_user_name(),
        support_users=TECHNICIAN_SUPPORT_USERS,
        technician_users=TECHNICIAN_SUPPORT_USERS,
        ticket_boards=load_ticket_boards(),
        ticket_board=board,
        page_mode="nastia",
        page_title="נסטיה",
        page_subtitle="תאום ביקורי טכנאי",
        page_icon_path=board.get("icon_path") or "",
        ticket_queue="nastia",
        show_create_button=False,
        show_pais_report=False,
        service_types=SUPPORT_SERVICE_TYPES,
        ticket_types=SUPPORT_TICKET_TYPES,
        priorities=SUPPORT_PRIORITIES,
        support_delivery_options=SUPPORT_DELIVERY_OPTIONS,
        support_customer_types=SUPPORT_CUSTOMER_TYPES,
        support_statuses=SUPPORT_STATUSES,
        pais_statuses=PAIS_STATUSES,
        nastia_notification_email=NASTIA_NOTIFICATION_EMAIL,
        ticket_operator_mode="default",
        can_upload_ticket_attachments=True,
        can_delete_ticket_attachments=True,
        default_ticket_scope="all",
        can_access_home="home" in allowed_pages,
        can_access_support="support_tickets" in allowed_pages,
        can_access_pais="pais_tickets" in allowed_pages,
        can_access_hot="hot_tickets" in allowed_pages,
        can_access_nastia="nastia_tickets" in allowed_pages,
    )


@app.route("/support-tickets-data")
def support_tickets_data():
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    board_slug = (request.args.get("board") or "support").strip().lower()
    queue_slug = (request.args.get("queue") or "").strip().lower()
    register_service_activity(support_page_key(board_slug, queue_slug))
    tickets = load_support_tickets(board_slug)
    scope = (request.args.get("scope") or "all").strip().lower()
    status_filter = (request.args.get("status") or "").strip()
    assignee_filter = (request.args.get("assignee") or "").strip()
    priority_filter = (request.args.get("priority") or "").strip()
    date_from = (request.args.get("date_from") or "").strip()
    date_to = (request.args.get("date_to") or "").strip()
    search = (request.args.get("search") or "").strip().lower()
    current_support_user = support_user_name()
    assigned_technician_mode = support_user_is_assigned_technician()

    base_tickets = list(tickets)
    if queue_slug == "nastia":
        base_tickets = [ticket for ticket in base_tickets if pais_ticket_is_coordination(ticket)]
    if assigned_technician_mode:
        base_tickets = [
            ticket for ticket in base_tickets
            if assigned_technician_can_access_ticket(ticket, current_support_user)
        ]
        scope = "my"
        assignee_filter = ""

    filtered = list(base_tickets)
    if scope == "my":
        if assigned_technician_mode:
            filtered = [t for t in filtered if assigned_technician_can_access_ticket(t, current_support_user)]
        else:
            filtered = [t for t in filtered if t.get("assigned_to") == current_support_user]
    elif scope == "unassigned":
        filtered = [t for t in filtered if not t.get("assigned_to")]

    if status_filter:
        filtered = [t for t in filtered if t.get("status") == status_filter]
    if assignee_filter:
        filtered = [t for t in filtered if t.get("assigned_to") == assignee_filter]
    if priority_filter:
        filtered = [t for t in filtered if t.get("priority") == priority_filter]
    filtered = filter_tickets_by_created_range(
        filtered,
        parse_date_filter(date_from, end_of_day=False),
        parse_date_filter(date_to, end_of_day=True),
    )
    if search:
        if board_slug == "pais":
            filtered = [
                t for t in filtered
                if (
                    search in str((t.get("details") or {}).get("terminal_number") or "").lower()
                    or search in str((t.get("details") or {}).get("address") or "").lower()
                )
            ]
        elif board_slug == "hot-kiryot":
            filtered = [
                t for t in filtered
                if any(
                    search in str((t.get("details") or {}).get(field_name) or "").lower()
                    for field_name in ("call_number", "customer_name", "address", "line_code", "issue_summary")
                )
                or search in str(t.get("ticket_id") or "").lower()
                or search in str(t.get("id") or "").lower()
            ]
        else:
            filtered = [
                t for t in filtered
                if search in json.dumps(t, ensure_ascii=False).lower()
            ]

    filtered.sort(key=lambda item: int(item.get("id") or 0), reverse=True)
    return jsonify({
        "tickets": filtered,
        "stats": support_ticket_stats(base_tickets),
        "next_id": f"#{next_support_ticket_id():04d}",
        "current_user": current_support_user,
        "board": get_ticket_board(board_slug),
        "users": TECHNICIAN_SUPPORT_USERS,
        "statuses": board_statuses(board_slug),
    })


@app.route("/pais-tickets-report-data")
def pais_tickets_report_data():
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    board_slug = (request.args.get("board") or "pais").strip().lower()
    if not board_has_coordination_report(board_slug):
        return jsonify({"ok": False, "message": "Report not enabled"}), 400
    register_service_activity(board_page_key(board_slug))
    status_filter = (request.args.get("status") or "").strip()
    period = (request.args.get("period") or "monthly").strip().lower()
    date_from = (request.args.get("date_from") or "").strip()
    date_to = (request.args.get("date_to") or "").strip()
    if period not in {"daily", "weekly", "monthly"}:
        period = "monthly"

    report = build_ticket_board_report(
        load_support_tickets(board_slug),
        status_filter=status_filter,
        period=period,
        date_from_raw=date_from,
        date_to_raw=date_to,
    )
    return jsonify({"ok": True, "board": get_ticket_board(board_slug), **report})


@app.route("/pais-tickets-report-export")
def pais_tickets_report_export():
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    board_slug = (request.args.get("board") or "pais").strip().lower()
    if not board_has_coordination_report(board_slug):
        return jsonify({"ok": False, "message": "Report not enabled"}), 400
    register_service_activity(board_page_key(board_slug))
    status_filter = (request.args.get("status") or "").strip()
    period = (request.args.get("period") or "monthly").strip().lower()
    export_format = (request.args.get("format") or "csv").strip().lower()
    date_from = (request.args.get("date_from") or "").strip()
    date_to = (request.args.get("date_to") or "").strip()
    if period not in {"daily", "weekly", "monthly"}:
        period = "monthly"
    if export_format not in {"csv", "pdf"}:
        export_format = "csv"

    report = build_ticket_board_report(
        load_support_tickets(board_slug),
        status_filter=status_filter,
        period=period,
        date_from_raw=date_from,
        date_to_raw=date_to,
    )

    board = get_ticket_board(board_slug)
    rows = build_ticket_board_export_rows(report)
    export_config = ticket_board_export_config(board_slug)
    csv_rows = [export_config["row_mapper"](row) for row in rows]

    if export_format == "pdf":
        pdf_buffer = build_pdf_buffer(
            title=board.get("name") or "דו\"ח קריאות",
            metadata_rows=[
                ("Period", report.get("period") or ""),
                ("Dates", f"{report.get('date_from') or ''} - {report.get('date_to') or ''}"),
                ("Status", report.get("status") or "All"),
                ("Rows", len(rows)),
            ],
            headers=export_config["headers"],
            rows=[export_config["pdf_row_mapper"](row) for row in rows] or [["-", "-", "No rows found for this report."]],
            rtl_columns=export_config["rtl_columns"],
            emphasis_columns={0},
            emphasis_meta_labels={"Dates", "Rows"},
        )
        return send_file(
            pdf_buffer,
            mimetype="application/pdf",
            as_attachment=True,
            download_name=f"{board_slug}_tickets_{period}_{report['date_from']}_to_{report['date_to']}.pdf",
        )

    csv_text = io.StringIO()
    writer = csv.DictWriter(csv_text, fieldnames=export_config["csv_fields"])
    writer.writeheader()
    for row in csv_rows:
        writer.writerow(row)
    total_row = {field_name: "" for field_name in export_config["csv_fields"]}
    total_row[export_config["csv_fields"][0]] = "TOTAL"
    if len(export_config["csv_fields"]) > 1:
        total_row[export_config["csv_fields"][1]] = len(rows)
    writer.writerow(total_row)

    output = io.BytesIO(("\ufeff" + csv_text.getvalue()).encode("utf-8"))
    output.seek(0)
    return send_file(
        output,
        mimetype="text/csv",
        as_attachment=True,
        download_name=f"{board_slug}_tickets_{period}_{report['date_from']}_to_{report['date_to']}.csv",
    )


@app.route("/support-tickets-create", methods=["POST"])
def support_tickets_create():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    if support_user_is_assigned_technician():
        return jsonify({"ok": False, "message": "Technician accounts cannot create tickets"}), 403

    board_slug = (request.form.get("board_slug") or "support").strip().lower()
    board = get_ticket_board(board_slug)
    service_type = (request.form.get("service_type") or "").strip()
    domain = (request.form.get("domain") or "").strip()
    ticket_type = (request.form.get("ticket_type") or "").strip()
    priority = (request.form.get("priority") or "Medium").strip()
    description = (request.form.get("description") or "").strip()
    solution = (request.form.get("solution") or "").strip()
    assigned_to = (request.form.get("assigned_to") or "").strip()
    details = {}

    if assigned_to and assigned_to not in TECHNICIAN_SUPPORT_USERS:
        return jsonify({"ok": False, "message": "Invalid assignee"}), 400

    now = israel_now()

    if board["slug"] == "pais":
        terminal_number = (request.form.get("terminal_number") or "").strip()
        address = (request.form.get("address") or "").strip()
        customer_request = (request.form.get("customer_request") or "").strip()
        actions_taken = (request.form.get("actions_taken") or "").strip()
        if not terminal_number:
            return jsonify({"ok": False, "message": "מספר מסוף הוא שדה חובה"}), 400
        if not address:
            return jsonify({"ok": False, "message": "כתובת היא שדה חובה"}), 400
        if not customer_request:
            return jsonify({"ok": False, "message": "פניית לקוח היא שדה חובה"}), 400
        details = {
            "terminal_number": terminal_number,
            "address": address,
            "static_ip": (request.form.get("static_ip") or "").strip(),
            "altura": (request.form.get("altura") or "").strip(),
            "look_back": (request.form.get("look_back") or "").strip(),
            "contact_name": (request.form.get("contact_name") or "").strip(),
            "contact_phone": (request.form.get("contact_phone") or "").strip(),
            "customer_request": customer_request,
            "actions_taken": actions_taken,
            "coordinated_worker": "",
            "visit_date": "",
            "visit_hour_from": "",
            "visit_hour_to": "",
            "failure_notes": "",
        }
        service_type = board["name"]
        domain = ""
        priority = "Medium"
        ticket_type = "שירות"
        description = ""
        solution = ""
    elif board["slug"] == "support":
        if ticket_type not in SUPPORT_TICKET_TYPES:
            return jsonify({"ok": False, "message": "Invalid ticket type"}), 400
        if priority not in SUPPORT_PRIORITIES:
            return jsonify({"ok": False, "message": "Invalid priority"}), 400
        if service_type == "מרכזייה" and not domain:
            return jsonify({"ok": False, "message": "Domain is required for מרכזייה"}), 400
        if not description:
            return jsonify({"ok": False, "message": "Description is required"}), 400
        service_mode = (request.form.get("service_mode") or "").strip()
        if service_mode and service_mode not in SUPPORT_DELIVERY_OPTIONS:
            return jsonify({"ok": False, "message": "Invalid service mode"}), 400
        customer_type = (request.form.get("customer_type") or "").strip()
        if customer_type and customer_type not in SUPPORT_CUSTOMER_TYPES:
            return jsonify({"ok": False, "message": "Invalid customer type"}), 400
        business_name = (request.form.get("business_name") or "").strip()
        service_contact = (request.form.get("service_contact") or "").strip()
        service_address = (request.form.get("service_address") or "").strip()
        if service_mode and not all([business_name, service_contact, service_address]):
            return jsonify({"ok": False, "message": "יש למלא שם העסק, איש קשר וכתובת עבור סוג הטיפול שנבחר"}), 400
        details = {
            "customer_type": customer_type,
            "service_mode": service_mode,
            "business_name": business_name,
            "service_contact": service_contact,
            "service_address": service_address,
            "coordinated_worker": "",
            "visit_date": "",
            "visit_hour_from": "",
            "visit_hour_to": "",
            "failure_notes": "",
        }
    elif board["slug"] == "hot-kiryot":
        call_number = (request.form.get("call_number") or "").strip()
        address = (request.form.get("address") or "").strip()
        customer_name = (request.form.get("customer_name") or "").strip()
        issue_summary = (request.form.get("issue_summary") or "").strip()
        if not call_number:
            return jsonify({"ok": False, "message": "מספר קריאה הוא שדה חובה"}), 400
        if not address:
            return jsonify({"ok": False, "message": "כתובת היא שדה חובה"}), 400
        if not customer_name:
            return jsonify({"ok": False, "message": "שם לקוח הוא שדה חובה"}), 400
        if not issue_summary:
            return jsonify({"ok": False, "message": "מהות התקלה היא שדה חובה"}), 400
        details = {
            "opened_at": (request.form.get("opened_at") or "").strip(),
            "call_number": call_number,
            "opened_by": (request.form.get("opened_by") or "").strip(),
            "customer_id": (request.form.get("customer_id") or "").strip(),
            "customer_name": customer_name,
            "line_code": (request.form.get("line_code") or "").strip(),
            "address": address,
            "on_site_contact": (request.form.get("on_site_contact") or "").strip(),
            "technical_contact": (request.form.get("technical_contact") or "").strip(),
            "availability_hours": (request.form.get("availability_hours") or "").strip(),
            "remote_checks": (request.form.get("remote_checks") or "").strip(),
            "issue_summary": issue_summary,
            "technician_actions": (request.form.get("technician_actions") or "").strip(),
            "equipment_type": (request.form.get("equipment_type") or "").strip(),
            "service_agreement": (request.form.get("service_agreement") or "").strip(),
            "technical_notes": (request.form.get("technical_notes") or "").strip(),
            "coordinated_worker": "",
            "visit_date": "",
            "visit_hour_from": "",
            "visit_hour_to": "",
            "failure_notes": "",
        }
        service_type = board["name"]
        domain = ""
        priority = "Medium"
        ticket_type = "שירות"
        description = ""
        solution = ""
    else:
        if ticket_type not in SUPPORT_TICKET_TYPES:
            return jsonify({"ok": False, "message": "Invalid ticket type"}), 400
        if priority not in SUPPORT_PRIORITIES:
            return jsonify({"ok": False, "message": "Invalid priority"}), 400
        if service_type == "מרכזייה" and not domain:
            return jsonify({"ok": False, "message": "Domain is required for מרכזייה"}), 400
        if not description:
            return jsonify({"ok": False, "message": "Description is required"}), 400

    ticket_payload = {
        "created_at": now.isoformat(timespec="seconds"),
        "created_at_display": now.strftime("%d/%m/%Y %H:%M"),
        "creator": support_user_name(),
        "board_slug": board["slug"],
        "ticket_type": ticket_type,
        "service_type": service_type,
        "domain": domain,
        "priority": priority,
        "description": description,
        "solution": solution,
        "status": normalize_ticket_status(board["slug"], "ממתין" if board_supports_coordination(board["slug"]) else "Waiting"),
        "assigned_to": assigned_to,
        "details": details,
    }

    attachment_files = [file_storage for file_storage in request.files.getlist("attachments") if file_storage and file_storage.filename]
    if not attachment_files:
        legacy_attachment = request.files.get("attachment")
        if legacy_attachment and legacy_attachment.filename:
            attachment_files.append(legacy_attachment)

    try:
        ticket = create_support_ticket_record(ticket_payload, attachment_files=attachment_files)
    except ValueError as exc:
        return jsonify({"ok": False, "message": str(exc)}), 400
    except RuntimeError as exc:
        return jsonify({"ok": False, "message": str(exc)}), 502

    return jsonify({"ok": True, "ticket": ticket})


@app.route("/support-tickets-update", methods=["POST"])
def support_tickets_update():
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    payload = request.get_json(silent=True) or {}
    actor = support_user_name()
    target_ticket = None

    if support_user_is_assigned_technician():
        target_ticket = find_support_ticket(load_support_tickets(), payload.get("ticket_id"))
        if not target_ticket:
            return jsonify({"ok": False, "message": "Ticket not found"}), 404
        if not assigned_technician_can_access_ticket(target_ticket, actor):
            return jsonify({"ok": False, "message": "Access denied"}), 403
        if "assigned_to" in payload:
            return jsonify({"ok": False, "message": "Technician accounts cannot reassign tickets"}), 403
        status = normalize_ticket_status(target_ticket.get("board_slug"), payload.get("status"))
        payload["status"] = status
        if status not in assigned_technician_allowed_statuses():
            return jsonify({"ok": False, "message": "Technician accounts can only set status to בוצע או נכשל"}), 403
        if status == "נכשל" and not isinstance(payload.get("details"), dict):
            return jsonify({"ok": False, "message": "יש למלא סיבת כשל"}), 400
        if "details" in payload:
            details = payload.get("details")
            if not isinstance(details, dict):
                return jsonify({"ok": False, "message": "Invalid details payload"}), 400
            disallowed_fields = {
                field_name for field_name, value in details.items()
                if field_name != "failure_notes" and str(value or "").strip()
            }
            if disallowed_fields:
                return jsonify({"ok": False, "message": "Technician accounts can only update failure notes"}), 403
            if status == "נכשל" and not str(details.get("failure_notes") or "").strip():
                return jsonify({"ok": False, "message": "יש למלא סיבת כשל"}), 400

    if "details" in payload and isinstance(payload.get("details"), dict):
        details = payload["details"]
        if all([
            (details.get("coordinated_worker") or "").strip(),
            (details.get("visit_date") or "").strip(),
            (details.get("visit_hour_from") or "").strip(),
            (details.get("visit_hour_to") or "").strip(),
        ]) and not (payload.get("status") or "").strip():
            payload["status"] = "תואם"

    if "assigned_to" in payload:
        assigned_to = (payload.get("assigned_to") or "").strip()
        if assigned_to and assigned_to not in TECHNICIAN_SUPPORT_USERS:
            return jsonify({"ok": False, "message": "Invalid assignee"}), 400

    if "status" in payload:
        target_ticket = target_ticket or find_support_ticket(load_support_tickets(), payload.get("ticket_id"))
        status = normalize_ticket_status((target_ticket or {}).get("board_slug"), payload.get("status"))
        payload["status"] = status
        if status not in ALL_TICKET_STATUSES:
            return jsonify({"ok": False, "message": "Invalid status"}), 400
    if "details" in payload and isinstance(payload.get("details"), dict):
        details = payload["details"]
        customer_type = (details.get("customer_type") or "").strip()
        if customer_type and customer_type not in SUPPORT_CUSTOMER_TYPES:
            return jsonify({"ok": False, "message": "Invalid customer type"}), 400
        service_mode = (details.get("service_mode") or "").strip()
        if service_mode and service_mode not in SUPPORT_DELIVERY_OPTIONS:
            return jsonify({"ok": False, "message": "Invalid service mode"}), 400
        if service_mode and not all([
            (details.get("business_name") or "").strip(),
            (details.get("service_contact") or "").strip(),
            (details.get("service_address") or "").strip(),
        ]):
            return jsonify({"ok": False, "message": "יש למלא שם העסק, איש קשר וכתובת עבור סוג הטיפול שנבחר"}), 400
        coordinated_worker = (details.get("coordinated_worker") or "").strip()
        visit_date = (details.get("visit_date") or "").strip()
        visit_hour_from = (details.get("visit_hour_from") or "").strip()
        visit_hour_to = (details.get("visit_hour_to") or "").strip()
        if coordinated_worker and coordinated_worker not in TECHNICIAN_SUPPORT_USERS:
            return jsonify({"ok": False, "message": "Invalid coordinated worker"}), 400
        if any([coordinated_worker, visit_date, visit_hour_from, visit_hour_to]) and not all([coordinated_worker, visit_date, visit_hour_from, visit_hour_to]):
            return jsonify({"ok": False, "message": "יש למלא עובד, תאריך ושעת ביקור מלאה"}), 400
        if visit_hour_from or visit_hour_to:
            if not visit_slot_is_valid(visit_hour_from, visit_hour_to):
                return jsonify({"ok": False, "message": "יש לבחור חלון תיאום של שעה אחת בין 09:00 ל-18:00"}), 400
        conflicting_ticket = coordination_slot_conflicts(
            payload.get("ticket_id"),
            coordinated_worker,
            visit_date,
            visit_hour_from,
            visit_hour_to,
        )
        if conflicting_ticket:
            return jsonify({
                "ok": False,
                "message": f"העובד {coordinated_worker} כבר תפוס בתאריך {visit_date} בין {visit_hour_from} ל-{visit_hour_to}",
            }), 400
        if (payload.get("status") or "").strip() == "נכשל" and not (details.get("failure_notes") or "").strip():
            return jsonify({"ok": False, "message": "יש למלא סיבת כשל"}), 400
    try:
        ticket = update_support_ticket_record(payload.get("ticket_id"), payload, actor)
    except LookupError:
        return jsonify({"ok": False, "message": "Ticket not found"}), 404
    except RuntimeError as exc:
        return jsonify({"ok": False, "message": str(exc)}), 502
    return jsonify({"ok": True, "ticket": ticket})


@app.route("/support-tickets-attachments", methods=["POST"])
def support_tickets_attachments():
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    ticket_id = (request.form.get("ticket_id") or "").strip()
    if support_user_is_assigned_technician():
        target_ticket = find_support_ticket(load_support_tickets(), ticket_id)
        if not target_ticket:
            return jsonify({"ok": False, "message": "Ticket not found"}), 404
        if not assigned_technician_can_access_ticket(target_ticket):
            return jsonify({"ok": False, "message": "Access denied"}), 403

    attachment_files = [file_storage for file_storage in request.files.getlist("attachments") if file_storage and file_storage.filename]
    if not attachment_files:
        legacy_attachment = request.files.get("attachment")
        if legacy_attachment and legacy_attachment.filename:
            attachment_files.append(legacy_attachment)

    try:
        ticket = append_support_ticket_attachments(ticket_id, attachment_files)
    except ValueError as exc:
        return jsonify({"ok": False, "message": str(exc)}), 400
    except LookupError:
        return jsonify({"ok": False, "message": "Ticket not found"}), 404
    except RuntimeError as exc:
        return jsonify({"ok": False, "message": str(exc)}), 502
    return jsonify({"ok": True, "ticket": ticket})


@app.route("/support-tickets-field-report", methods=["POST"])
def support_tickets_field_report():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    if not support_user_is_assigned_technician():
        return jsonify({"ok": False, "message": "Technician access required"}), 403

    payload = request.get_json(silent=True) or {}
    area_photo_files = []
    if not payload and request.form:
        raw_payload = (request.form.get("payload") or "").strip()
        if raw_payload:
            try:
                payload = json.loads(raw_payload)
            except json.JSONDecodeError as exc:
                return jsonify({"ok": False, "message": f"Invalid payload: {exc}"}), 400
        else:
            payload = request.form.to_dict(flat=True)
    if request.files:
        area_photo_files = [
            file_storage
            for file_storage in request.files.getlist("area_photos")
            if file_storage and file_storage.filename
        ]
    ticket_id = payload.get("ticket_id")
    target_ticket = find_support_ticket(load_support_tickets(), ticket_id)
    if not target_ticket:
        return jsonify({"ok": False, "message": "Ticket not found"}), 404
    if not assigned_technician_can_access_ticket(target_ticket):
        return jsonify({"ok": False, "message": "Access denied"}), 403
    if (target_ticket.get("board_slug") or "").strip().lower() != "hot-kiryot":
        return jsonify({"ok": False, "message": "Customer signature is supported only for הוט קריאות"}), 400

    try:
        ticket = save_hot_field_report(ticket_id, support_user_name(), payload, area_photo_files=area_photo_files)
    except ValueError as exc:
        return jsonify({"ok": False, "message": str(exc)}), 400
    except LookupError:
        return jsonify({"ok": False, "message": "Ticket not found"}), 404
    except RuntimeError as exc:
        return jsonify({"ok": False, "message": str(exc)}), 502
    return jsonify({"ok": True, "ticket": ticket})


@app.route("/support-tickets-attachment-delete", methods=["POST"])
def support_tickets_attachment_delete():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    if support_user_is_assigned_technician():
        return jsonify({"ok": False, "message": "Technician accounts cannot delete attachments"}), 403

    payload = request.get_json(silent=True) or {}
    try:
        ticket = delete_support_ticket_attachment(
            payload.get("ticket_id"),
            payload.get("folder"),
            payload.get("saved_name"),
        )
    except ValueError as exc:
        return jsonify({"ok": False, "message": str(exc)}), 400
    except LookupError as exc:
        message = str(exc) or "Attachment not found"
        status = 404
        if "ticket" in message.lower():
            message = "Ticket not found"
        else:
            message = "Attachment not found"
        return jsonify({"ok": False, "message": message}), status
    except RuntimeError as exc:
        return jsonify({"ok": False, "message": str(exc)}), 502
    return jsonify({"ok": True, "ticket": ticket})


@app.route("/support-tickets-delete", methods=["POST"])
def support_tickets_delete():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    if not support_user_is_admin():
        return jsonify({"ok": False, "message": "Admin access required"}), 403

    payload = request.get_json(silent=True) or {}
    try:
        ticket = delete_support_ticket_record(payload.get("ticket_id"))
    except LookupError:
        return jsonify({"ok": False, "message": "Ticket not found"}), 404
    except RuntimeError as exc:
        return jsonify({"ok": False, "message": str(exc)}), 502
    return jsonify({"ok": True, "deleted_ticket_id": ticket.get("ticket_id")})


@app.route("/support-ticket-attachment/<ticket_folder>/<filename>")
def support_ticket_attachment(ticket_folder, filename):
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    if not re.fullmatch(r"TicketID\d{4}", ticket_folder):
        return jsonify({"ok": False, "message": "Invalid ticket folder"}), 400

    safe_name = secure_filename(filename)
    file_path = os.path.abspath(os.path.join(SUPPORT_SCREEN_DIR, ticket_folder, safe_name))
    screen_root = os.path.abspath(SUPPORT_SCREEN_DIR)
    if os.path.commonpath([screen_root, file_path]) == screen_root and os.path.exists(file_path):
        return send_file(file_path)

    if supabase_storage_enabled():
        object_path = _supabase_storage_object_path(ticket_folder, safe_name)
        try:
            response = download_supabase_storage_object(object_path)
        except RuntimeError as exc:
            return jsonify({"ok": False, "message": str(exc)}), 502
        if response is not None:
            return send_file(
                io.BytesIO(response.content),
                mimetype=response.headers.get("Content-Type") or mimetypes.guess_type(safe_name)[0] or "application/octet-stream",
                download_name=safe_name,
            )

    return jsonify({"ok": False, "message": "Attachment not found"}), 404


@app.route("/favicon.ico")
def favicon():
    return redirect("/favicon/favicon.jpg", code=307)


@app.route("/recordings-data")
def recordings_data():

    if not session.get("logged_in"):
        return redirect(url_for("login"))
    register_service_activity("recordings")

    service = get_drive_service(readonly=True)
    results = service.files().list(
        q=f"'{DRIVE_FOLDER_ID}' in parents and mimeType='audio/wav' and trashed=false",
        fields="files(id,name)"
    ).execute()

    files = results.get("files", [])
    output = []
    domain_by_order = {}

    for f in files:
        order_id = extract_order_id_from_record(f.get("name", ""))
        if order_id and order_id not in domain_by_order:
            domain_by_order[order_id] = get_domain_from_crm(order_id)

    for f in files:
        name = f.get("name", "")
        file_id = f.get("id", "")
        order_id = extract_order_id_from_record(name)
        domain = domain_by_order.get(order_id, "") if order_id else ""

        output.append({
            "name": name,
            "file_id": file_id,
            "order_id": order_id,
            "domain": domain
        })

    return jsonify(output)


@app.route("/download-record/<file_id>/<domain>")
def download_record(file_id, domain):

    if not session.get("logged_in"):
        return redirect(url_for("login"))

    service = get_drive_service(readonly=True)
    request_drive = service.files().get_media(fileId=file_id)

    file_data = io.BytesIO()
    downloader = MediaIoBaseDownload(file_data, request_drive)

    done = False
    while not done:
        _, done = downloader.next_chunk()

    file_data.seek(0)

    if domain == "nodomain":
        domain = ""

    filename = f"{domain}_IVR.wav" if domain else "record_IVR.wav"
    return send_file(
        file_data,
        mimetype="audio/wav",
        as_attachment=True,
        download_name=filename
    )


@app.route("/mark-done/<file_id>", methods=["POST"])
def mark_record_done(file_id):

    if not session.get("logged_in"):
        return redirect(url_for("login"))

    service = get_drive_service(readonly=False)

    file_meta = service.files().get(fileId=file_id, fields="id,parents").execute()
    current_parents = file_meta.get("parents", [])

    done_query = (
        f"'{DRIVE_FOLDER_ID}' in parents and "
        f"name = '{DRIVE_DONE_FOLDER_NAME}' and "
        "mimeType = 'application/vnd.google-apps.folder' and trashed=false"
    )
    done_search = service.files().list(q=done_query, fields="files(id,name)").execute().get("files", [])

    if done_search:
        done_folder_id = done_search[0]["id"]
    else:
        done_folder = service.files().create(
            body={
                "name": DRIVE_DONE_FOLDER_NAME,
                "mimeType": "application/vnd.google-apps.folder",
                "parents": [DRIVE_FOLDER_ID]
            },
            fields="id"
        ).execute()
        done_folder_id = done_folder["id"]

    remove_parents = ",".join(current_parents) if current_parents else ""
    service.files().update(
        fileId=file_id,
        addParents=done_folder_id,
        removeParents=remove_parents,
        fields="id,parents"
    ).execute()

    return jsonify({"ok": True})


# ================= LOGOUT =================
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))
##Load data
@app.route("/load-data")
def load_data():
    if not session.get("logged_in"):
        return api_error("Login required", 401, "login_required")
    register_service_activity("sms")
    try:
        return jsonify({
            "ok": True,
            "customers": get_pending_customers(),
            "inforu_sent_numbers": sorted(inforu_sent_numbers()),
        })
    except Exception as exc:
        return api_error(exc, 500, "google_auth_or_sheet_error")

#Firebarry Sync by ID number
@app.route("/fireberry-by-id", methods=["POST"])
def fireberry_by_id():
    payload = request.get_json(silent=True) or {}
    idnumber = (payload.get("idnumber") or "").strip()

    if not idnumber:
        return jsonify({"ok": False, "message": "Missing idnumber"}), 400

    try:
        result = fireberry_lookup_by_idnumber(idnumber)
        return jsonify({"ok": True, **result})
    except requests.HTTPError as e:
        return jsonify({"ok": False, "message": f"Fireberry HTTP error: {str(e)}"}), 502
    except Exception as e:
        return jsonify({"ok": False, "message": f"Error: {str(e)}"}), 500


@app.route("/sms-domain-lookup", methods=["POST"])
def sms_domain_lookup():
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    payload = request.get_json(silent=True) or {}
    domain = (payload.get("domain") or "").strip()

    if not domain:
        return jsonify({"ok": False, "message": "Missing domain"}), 400

    client = get_gspread_client()
    sheet_names = ["\u05d7\u05d9\u05e4", CGR_SHEET_NAME]
    last_error = None

    for sheet_name in sheet_names:
        try:
            ws = client.open_by_key(SPREADSHEET_ID).worksheet(sheet_name)
            data = ws.get_all_values()
            for row in data:
                row_domain = row[2].strip() if len(row) >= 3 else ""
                if row_domain == domain:
                    return jsonify({
                        "ok": True,
                        "found": True,
                        "domain": row_domain,
                        "date": row[3].strip() if len(row) >= 4 else "",
                        "did": row[5].strip() if len(row) >= 6 else "",
                        "sheet": sheet_name,
                    })
        except Exception as e:
            last_error = e

    if last_error:
        print("SMS domain lookup warning:", last_error)

    return jsonify({"ok": True, "found": False})


@app.route("/domain-by-order", methods=["POST"])
def domain_by_order():
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    payload = request.get_json(silent=True) or {}
    order_id = (payload.get("order_id") or "").strip()

    if not order_id:
        return jsonify({"ok": False, "message": "Missing order_id"}), 400

    domain = get_domain_from_crm(order_id)
    return jsonify({
        "ok": True,
        "found": bool(domain),
        "domain": domain,
    })


@app.route("/mark-done", methods=["POST"])
def mark_done():
    if not session.get("logged_in"):
        return api_error("Unauthorized", 401, "unauthorized")

    try:
        payload = request.get_json(silent=True) or {}
        customers = payload.get("customers", [])

        if not isinstance(customers, list) or not customers:
            return api_error("No customers provided.", 400, "missing_customers")

        rows = []
        cgr_updates = []
        clean_customers = []

        for c in customers:
            if not isinstance(c, dict):
                continue

            r = c.get("sheet_row")
            cgr_row = c.get("cgr_row")

            if not isinstance(r, int) or r < 2:
                continue

            name = (c.get("name") or "").strip()
            domain = (c.get("domain") or "").strip()
            did = (c.get("did") or "").strip()

            rows.append(r)
            clean_customers.append({
                "name": name,
                "domain": domain,
                "did": did,
            })

            if isinstance(cgr_row, int) and domain:
                cgr_updates.append({
                    "range": (
                        f"{gspread.utils.rowcol_to_a1(cgr_row, CGR_COL_DOMAIN)}:"
                        f"{gspread.utils.rowcol_to_a1(cgr_row, CGR_COL_USED)}"
                    ),
                    "values": [[domain, datetime.now().strftime("%Y-%m-%d"), True]],
                })

        if not rows:
            return api_error("No valid rows to update.", 400, "missing_rows")

        client = get_gspread_client()
        spreadsheet = client.open_by_key(SPREADSHEET_ID)

        ws = spreadsheet.worksheet(SHEET_NAME)
        updates = []
        for r in rows:
            updates.append({
                "range": gspread.utils.rowcol_to_a1(r, COL_STATUS),
                "values": [[STATUS_DONE]],
            })

        ws.batch_update(updates)

        if cgr_updates:
            cgr_ws = spreadsheet.worksheet(CGR_SHEET_NAME)
            cgr_ws.batch_update(cgr_updates)

        try:
            append_log(clean_customers)
        except Exception as log_exc:
            print(f"Mark-done log warning: {log_exc}")

        return jsonify({
            "ok": True,
            "updated": len(rows),
        })
    except Exception as exc:
        return api_error(exc, 500, "mark_done_failed")

@app.route("/send-inforu-mail", methods=["POST"])
def send_inforu_mail():
    if not session.get("logged_in"):
        return api_error("Unauthorized", 401, "unauthorized")

    payload = request.get_json(silent=True) or {}
    dids = payload.get("dids", [])
    # normalize numbers
    dids = [normalize_did_value(d) for d in dids]

    if not dids:
        return jsonify({"ok": False, "message": "No DID provided"}), 400

    # remove duplicates
    dids = list(dict.fromkeys(dids))

    existing_numbers = inforu_sent_numbers()

    # filter only new numbers
    new_dids = [d for d in dids if d not in existing_numbers]

    if not new_dids:
        return jsonify({"ok": False, "message": "All numbers already logged"}), 400

    numbers_str = " , ".join(new_dids)

    if not TOKEN_INFORU:
        return jsonify({
            "ok": False,
            "message": "Inforu Make webhook is not configured. Set TOKEN_INFORU or INFORU_MAKE_WEBHOOK_URL.",
        }), 500

    def build_inforu_webhook_error_message(exc, response=None):
        details = ""
        webhook_response = response or getattr(exc, "response", None)
        if webhook_response is not None:
            try:
                payload = webhook_response.json()
            except ValueError:
                payload = None

            if isinstance(payload, dict):
                for key in ("message", "error", "detail"):
                    value = payload.get(key)
                    if isinstance(value, str) and value.strip():
                        details = value.strip()
                        break
                if not details and payload:
                    details = json.dumps(payload, ensure_ascii=False)
            elif payload not in (None, ""):
                details = json.dumps(payload, ensure_ascii=False)

            if not details:
                response_text = (getattr(webhook_response, "text", "") or "").strip()
                if response_text:
                    details = response_text

            if not details:
                status_code = getattr(webhook_response, "status_code", None)
                if status_code:
                    details = f"Webhook request failed with status {status_code}."

        if not details:
            details = str(exc).strip()

        return details or "Failed to send Inforu email via Make webhook."

    try:
        response = requests.post(
            TOKEN_INFORU,
            json={
                "body": numbers_str,
                "numbers": ", ".join(new_dids),
                "count": len(new_dids),
            },
            timeout=20,
        )
        response.raise_for_status()
    except Exception as e:
        error_message = build_inforu_webhook_error_message(e, response if "response" in locals() else None)
        print("Make webhook error:", error_message)
        return jsonify({
            "ok": False,
            "message": error_message,
        }), 502

    sent_at = datetime.now(ZoneInfo("Asia/Jerusalem")).isoformat()
    log_entries = [{"did": did, "sent_at": sent_at, "source": "supabase"} for did in new_dids]
    log_warning = ""
    try:
        save_inforu_log_entries(log_entries)
    except Exception as exc:
        log_warning = str(exc)

    return jsonify({
        "ok": True,
        "added": len(new_dids),
        "numbers": new_dids,
        "entries": sort_inforu_log_entries(log_entries),
        "warning": log_warning,
    })


@app.route("/reserve-numbercgr", methods=["POST"])
def reserve_numbercgr():
    if not session.get("logged_in"):
        return api_error("Unauthorized", 401, "unauthorized")

    try:
        payload = request.get_json(silent=True) or {}
        customers = payload.get("customers", [])

        if not isinstance(customers, list) or not customers:
            return api_error("No customers provided.", 400, "missing_customers")

        result = reserve_cgr_numbers(customers)
        return jsonify({
            "ok": True,
            **result,
        })
    except Exception as exc:
        return api_error(exc, 500, "reserve_numbercgr_failed")


@app.route("/available-numbercgr", methods=["GET"])
def available_numbercgr():
    if not session.get("logged_in"):
        return api_error("Unauthorized", 401, "unauthorized")

    try:
        numbers = get_available_cgr_numbers(limit=1)
        if not numbers:
            return jsonify({"ok": True, "found": False})

        return jsonify({
            "ok": True,
            "found": True,
            "number": numbers[0]["number"],
            "row": numbers[0]["row"],
            "marked": bool(numbers[0]["marked"]),
        })
    except Exception as exc:
        return api_error(exc, 500, "available_numbercgr_failed")


# ================================
# RETURN INFORU LOG TO FRONTEND
# ================================

@app.route("/inforu-log-data", methods=["GET"])
def get_inforu_log_data():
    if not session.get("logged_in"):
        return api_error("Unauthorized", 401, "unauthorized")

    entries, supabase_error = collect_inforu_log_entries()
    return jsonify({
        "ok": True,
        "entries": entries,
        "sent_numbers": [entry["did"] for entry in entries if entry.get("did")],
        "warning": str(supabase_error) if supabase_error else "",
    })

@app.route("/inforu-log", methods=["GET"])
def get_inforu_log():
    if not session.get("logged_in"):
        return api_error("Unauthorized", 401, "unauthorized")

    entries, _ = collect_inforu_log_entries()
    return build_inforu_log_text(entries)


@app.route("/export", methods=["POST"])
def export_csv():

    data = request.get_json(silent=True)
    if not isinstance(data, list) or not data:
        return jsonify({"ok": False, "message": "No data to export."}), 400
    
    

    rows_out = []
    cgr_updates = []
    status_updates = []

    for r in data:
        if not isinstance(r, dict):
            continue

        domain = (r.get("Domain") or "").strip()
        caller_id = (r.get("DID") or "").strip()
        numbercgr = (r.get("NumberCGR") or "").strip()
        template_txt = (r.get("Text") or "").strip()
        cgr_row = int(r.get("cgr_row") or 0)
        sheet_row = int(r.get("sheet_row") or 0)

        num_digits = digits_only(numbercgr)
        if num_digits:
            numbercgr = num_digits if num_digits.startswith("0") else ("0" + num_digits)

        rows_out.append({
            "name": domain,
            "caller_id_number": caller_id,
            "did": numbercgr,
            "template": template_txt
        }
        )
        # Update ׳—׳™׳₪_׳¡׳׳¡ columns C:E with Domain, date, and used checkbox.
        if isinstance(cgr_row, int) and cgr_row >= 1 and domain:
            cgr_updates.append({
                "range": (
                    f"{gspread.utils.rowcol_to_a1(cgr_row, CGR_COL_DOMAIN)}:"
                    f"{gspread.utils.rowcol_to_a1(cgr_row, CGR_COL_USED)}"
                ),
                "values": [[domain, datetime.now().strftime("%Y-%m-%d"), True]]
            })

        if isinstance(sheet_row, int) and sheet_row >= 2 and not template_txt:
            status_updates.append({
                "range": gspread.utils.rowcol_to_a1(sheet_row, COL_STATUS),
                "values": [[STATUS_NO_SMS_TEXT]],
            })

    spreadsheet = None
    try:
        if cgr_updates or status_updates:
            client = get_gspread_client()
            spreadsheet = client.open_by_key(SPREADSHEET_ID)
    except Exception as e:
        print("SHEET OPEN ERROR:", e)

    if spreadsheet and status_updates:
        try:
            ws = spreadsheet.worksheet(SHEET_NAME)
            ws.batch_update(status_updates)
        except Exception as e:
            print("SMS STATUS UPDATE ERROR:", e)

    if spreadsheet and cgr_updates:
        try:
            cgr_ws = spreadsheet.worksheet(CGR_SHEET_NAME)
            cgr_ws.batch_update(cgr_updates)
        except Exception as e:
            print("CGR UPDATE ERROR:", e)

    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=["name", "caller_id_number", "number", "template"])
    writer.writeheader()
    for row in rows_out:
        writer.writerow({
            "name": row["name"],
            "caller_id_number": row["caller_id_number"],
            "number": row["did"],
            "template": row["template"],
        })

    csv_bytes = io.BytesIO()
    csv_bytes.write("\ufeff".encode("utf-8"))
    csv_bytes.write(output.getvalue().encode("utf-8"))
    csv_bytes.seek(0)

    response = send_file(csv_bytes, mimetype="text/csv", as_attachment=True, download_name="sms_export.csv")
    response.headers["X-SMS-Empty-Text-Status-Count"] = str(len(status_updates))
    return response

def normalize_voipappz_sms_url(url):
    if not url:
        return url

    parsed = urlparse(url)
    if parsed.hostname != "cloud.voipappz.io" or parsed.port not in (443, 9443):
        return url

    netloc = parsed.hostname
    return urlunparse(parsed._replace(netloc=netloc))


def summarize_sms_response_message(response, fallback="API Error"):
    if response is None:
        return fallback

    if isinstance(response, str):
        text = response.strip()
        return text or fallback

    if isinstance(response, (int, float, bool)):
        return str(response)

    if isinstance(response, list):
        messages = []
        for item in response:
            message = summarize_sms_response_message(item, fallback="")
            if message and message not in messages:
                messages.append(message)
        return "; ".join(messages) or fallback

    if isinstance(response, dict):
        prioritized_keys = ("message", "error", "detail", "title", "description", "status")
        for key in prioritized_keys:
            if key in response:
                message = summarize_sms_response_message(response.get(key), fallback="")
                if message:
                    return message

        errors = response.get("errors")
        if errors is not None:
            message = summarize_sms_response_message(errors, fallback="")
            if message:
                return message

        field_messages = []
        for key, value in response.items():
            if key in prioritized_keys or key == "errors":
                continue
            message = summarize_sms_response_message(value, fallback="")
            if message:
                field_messages.append(f"{key}: {message}")

        if field_messages:
            return "; ".join(field_messages)

    return fallback


@app.route("/create-sms", methods=["POST"])
def create_sms():

    payload = request.get_json(silent=True) or {}
    customers = payload.get("customers", [])

    if not customers:
        return jsonify({"ok": False, "message": "No customers selected"}), 400

    results = []

    headers = {
        "Authorization": SMS_TOKEN,
        "Content-Type": "application/x-www-form-urlencoded"
    }

    for c in customers:

        domain = (c.get("domain") or "").strip()
        did = (c.get("did") or "").strip()
        number = (c.get("numbercgr") or "").strip()
        template = (c.get("text") or "").strip()

        if not domain:
            results.append({
                "domain": "UNKNOWN",
                "success": False,
                "response": "Missing Domain",
                "message": "Missing Domain"
            })
            continue

        api_payload = {
            "type": "sms",
            "environment_name": domain,
            "vml[0][caller_id_number]": did,
            "vml[0][number]": number,
            "vml[0][template]": template
        }

        print("Sending To Voipappz API:", api_payload)
        print("Token configured:", bool(SMS_TOKEN))

        try:

            r = requests.post(
                normalize_voipappz_sms_url(SMS_URL),
                headers=headers,
                data=api_payload,
                timeout=30
            )

            try:
                resp = r.json()
            except:
                resp = r.text

            if r.status_code in (200, 201):

                results.append({
                    "domain": domain,
                    "success": True,
                    "response": SMS_CREATED_MESSAGE,
                    "message": SMS_CREATED_MESSAGE
                })

            else:

                results.append({
                    "domain": domain,
                    "success": False,
                    "response": resp,
                    "message": summarize_sms_response_message(resp)
                })

        except requests.exceptions.RequestException as e:

            print("Voipappz request completed without response:", e)

            results.append({
                "domain": domain,
                "success": True,
                "response": SMS_CREATED_MESSAGE,
                "message": SMS_CREATED_MESSAGE
            })

    return jsonify({
        "ok": True,
        "results": results
    })



def get_bot_customers():

    client = get_gspread_client()
    ws = client.open_by_key(SPREADSHEET_ID).worksheet(BOT_SHEET_NAME)

    data = ws.get_all_values()

    customers = []

    if not data or len(data) < 2:
        return customers

    rows = data[1:]

    for i, row in enumerate(rows, start=2):

        name = row[0].strip() if len(row) >= 1 else ""
        client_id = row[1].strip() if len(row) >= 2 else ""
        did = row[14].strip() if len(row) >= 15 else ""
        done = row[15].strip().lower() if len(row) >= 16 else ""

        if did and done != "true":

            if not did.startswith("0"):
                did = "0" + did

            customers.append({
                "row": i,
                "name": name,
                "client_id": client_id,
                "did": did,
                "domain": "",
                "status": "׳׳׳×׳™׳"
            })

    return customers


def get_f2m_customers(include_domains=False):

    client = get_gspread_client()
    ws = client.open_by_key(SPREADSHEET_ID).worksheet(F2M_SHEET_NAME)

    data = ws.get_all_values()

    customers = []

    if not data or len(data) < 2:
        return customers

    rows = data[1:]

    domain_by_order_id = {}

    for i, row in enumerate(rows, start=2):

        name = row[0].strip() if len(row) >= 1 else ""
        order_id = row[4].strip() if len(row) >= 5 else ""
        status = row[7].strip() if len(row) >= 8 else ""
        email = row[9].strip() if len(row) >= 10 else ""

        if not email or status == STATUS_DONE:
            continue

        domain = ""
        if include_domains and order_id:
            if order_id not in domain_by_order_id:
                domain_by_order_id[order_id] = get_domain_from_crm(order_id)
            domain = domain_by_order_id[order_id]

        customers.append({
            "row": i,
            "name": name,
            "order_id": order_id,
            "domain": domain,
            "email": email,
            "status": status or STATUS_PENDING
        })

    return customers


def get_recording_storage_customers(include_domains=False):

    client = get_gspread_client()
    ws = client.open_by_key(SPREADSHEET_ID).worksheet(RECORDING_STORAGE_SHEET_NAME)

    data = ws.get_all_values()
    customers = []

    if not data or len(data) < 2:
        return customers

    domain_by_order_id = {}

    for i, row in enumerate(data[1:], start=2):
        name = row[0].strip() if len(row) >= 1 else ""
        order_id = row[4].strip() if len(row) >= 5 else ""
        status = row[7].strip() if len(row) >= 8 else ""
        storage_size = row[9].strip() if len(row) >= 10 else ""

        if is_done_status(status) or status == STATUS_NOT_INTERESTED:
            continue

        domain = ""
        if include_domains and order_id:
            if order_id not in domain_by_order_id:
                domain_by_order_id[order_id] = get_domain_from_crm(order_id)
            domain = domain_by_order_id[order_id]

        customers.append({
            "row": i,
            "name": name,
            "order_id": order_id,
            "domain": domain,
            "storage_size": storage_size or "\u05d1\u05dc\u05d9 \u05e0\u05e4\u05d7",
            "status": status or STATUS_PENDING
        })

    return customers


def get_human_service_customers(include_domains=False):

    client = get_gspread_client()
    ws = client.open_by_key(SPREADSHEET_ID).worksheet(HUMAN_SERVICE_SHEET_NAME)

    data = ws.get_all_values()
    customers = []

    if not data or len(data) < 2:
        return customers

    domain_by_order_id = {}

    for i, row in enumerate(data[1:], start=2):
        name = row[0].strip() if len(row) >= 1 else ""
        order_id = row[4].strip() if len(row) >= 5 else ""
        hip_number = normalize_phone_with_zero(row[9] if len(row) >= 10 else "")
        done = is_checked(row[13] if len(row) >= 14 else "")

        if done or not hip_number:
            continue

        domain = ""
        if include_domains and order_id:
            if order_id not in domain_by_order_id:
                domain_by_order_id[order_id] = get_domain_from_crm(order_id)
            domain = domain_by_order_id[order_id]

        customers.append({
            "row": i,
            "name": name,
            "order_id": order_id,
            "domain": domain,
            "hip": hip_number
        })

    return customers


@app.route("/bot-data")
def bot_data():
    register_service_activity("bot")

    customers = get_bot_customers()

    return jsonify({
        "count": len(customers),
        "customers": customers
    })


@app.route("/f2m-data")
def f2m_data():
    register_service_activity("f2m")

    customers = get_f2m_customers(include_domains=True)

    return jsonify({
        "count": len(customers),
        "customers": customers
    })


@app.route("/recording-storage-data")
def recording_storage_data():
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    register_service_activity("recording_storage")
    customers = get_recording_storage_customers(include_domains=False)

    return jsonify({
        "count": len(customers),
        "customers": customers
    })


@app.route("/human-service-data")
def human_service_data():
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    register_service_activity("human_service")
    customers = get_human_service_customers(include_domains=False)

    return jsonify({
        "count": len(customers),
        "customers": customers
    })


@app.route("/bot-done", methods=["POST"])
def bot_done():

    payload = request.get_json(silent=True) or {}

    row = payload.get("row")

    if not row:
        return jsonify({"ok": False})

    client = get_gspread_client()
    ws = client.open_by_key(SPREADSHEET_ID).worksheet(BOT_SHEET_NAME)

    ws.update_cell(row, 16, True)  # column P checkbox

    return jsonify({"ok": True})


@app.route("/f2m-done", methods=["POST"])
def f2m_done():

    payload = request.get_json(silent=True) or {}

    row = payload.get("row")

    if not isinstance(row, int) or row < 2:
        return jsonify({"ok": False, "message": "Invalid row"}), 400

    client = get_gspread_client()
    ws = client.open_by_key(SPREADSHEET_ID).worksheet(F2M_SHEET_NAME)

    ws.update_cell(row, COL_STATUS, STATUS_DONE)

    return jsonify({"ok": True})


@app.route("/recording-storage-done", methods=["POST"])
def recording_storage_done():

    payload = request.get_json(silent=True) or {}
    row = payload.get("row")

    if not isinstance(row, int) or row < 2:
        return jsonify({"ok": False, "message": "Invalid row"}), 400

    client = get_gspread_client()
    ws = client.open_by_key(SPREADSHEET_ID).worksheet(RECORDING_STORAGE_SHEET_NAME)
    ws.update_cell(row, COL_STATUS, STATUS_DONE)

    return jsonify({"ok": True})


@app.route("/human-service-done", methods=["POST"])
def human_service_done():

    payload = request.get_json(silent=True) or {}
    row = payload.get("row")

    if not isinstance(row, int) or row < 2:
        return jsonify({"ok": False, "message": "Invalid row"}), 400

    client = get_gspread_client()
    ws = client.open_by_key(SPREADSHEET_ID).worksheet(HUMAN_SERVICE_SHEET_NAME)
    ws.update_cell(row, HUMAN_SERVICE_DONE_COL, True)

    return jsonify({"ok": True})

#//Dashboard Page
@app.route("/dashboard")
def dashboard():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    return render_template("home.html", current_user=session.get("username", ""))

    

if __name__ == "__main__":
    app.run(port=5059, debug=True)
