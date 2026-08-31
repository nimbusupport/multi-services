from flask import Flask, render_template, request, jsonify, send_file
import os
import shutil
import csv
import tempfile
from werkzeug.utils import secure_filename
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
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

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
SUPPORT_STATUSES = ["Waiting", "Done"]
PAIS_STATUSES = ["ממתין", "ממתין לתאום", "תואם", "אין מענה", "בוצע", "נכשל"]
ALL_TICKET_STATUSES = SUPPORT_STATUSES + [status for status in PAIS_STATUSES if status not in SUPPORT_STATUSES]
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
    "nastia_tickets",
}
TICKETS_ONLY_ALLOWED_PAGES = {"support_tickets", "pais_tickets"}
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
NASTIA_NOTIFICATION_EMAIL = (os.environ.get("NASTIA_NOTIFICATION_EMAIL") or "orders@nimbusip.com").strip()
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
        "name": "Support Tickets",
        "icon_path": "",
        "route_path": "/support-tickets",
        "sort_order": 1,
    },
    "pais": {
        "slug": "pais",
        "name": "מפעל הפיס",
        "icon_path": "/picture/pais.png",
        "route_path": "/pais-tickets",
        "sort_order": 2,
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
    if local == "asaf":
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


def normalize_support_ticket(ticket):
    ticket = dict(ticket or {})
    ticket["id"] = int(ticket.get("id") or 0)
    ticket["ticket_id"] = f"#{ticket['id']:04d}"
    ticket.setdefault("board_slug", "support")
    ticket.setdefault("status", "Waiting")
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
    return (ticket.get("status") or "").strip() in {"Done", "בוצע"}


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
    return sorted(normalized)


def allowed_pages_for_role(role):
    normalized_role = (role or "").strip().lower()
    if normalized_role == "tickets_only":
        return sorted(TICKETS_ONLY_ALLOWED_PAGES)
    return sorted(FULL_ACCESS_PAGES)


def allowed_pages_for_current_user():
    return set(normalize_allowed_pages(session.get("allowed_pages")))


def user_can_access_page(page_key):
    return (page_key or "").strip().lower() in allowed_pages_for_current_user()


def first_allowed_route():
    allowed = allowed_pages_for_current_user()
    if "home" in allowed:
        return url_for("home")
    if "support_tickets" in allowed:
        return url_for("support_tickets_page")
    if "pais_tickets" in allowed:
        return url_for("pais_tickets_page")
    if "configuration" in allowed:
        return url_for("configuration_page")
    return url_for("home")


def route_page_key(path):
    normalized_path = (path or "").strip().lower()
    if normalized_path in {"", "/"}:
        return None
    if normalized_path.startswith("/support-ticket-attachment"):
        return "support_tickets"
    if normalized_path.startswith("/support-tickets"):
        return "support_tickets"
    if normalized_path.startswith("/pais-tickets"):
        return "pais_tickets"
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
    if (ticket.get("board_slug") or "").strip().lower() != "pais":
        return False
    details = ticket.get("details") or {}
    return (
        (ticket.get("status") or "").strip() == "ממתין לתאום"
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


def support_page_key(board_slug, queue_slug=""):
    normalized_queue = (queue_slug or "").strip().lower()
    if normalized_queue == "nastia":
        return "nastia_tickets"
    return "pais_tickets" if (board_slug or "").strip().lower() == "pais" else "support_tickets"


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


def inforu_log_dir():
    if running_on_vercel():
        return os.path.join(tempfile.gettempdir(), "did_inforu")
    return "did_inforu"


def inforu_log_path():
    return os.path.join(inforu_log_dir(), INFORU_LOG_FILENAME)


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
        return rows
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
    attachments = _supabase_request(
        "GET",
        "ticket_attachments",
        params={
            "select": "ticket_id,original_name,saved_name,folder,url",
            "ticket_id": id_filter,
            "order": "id.asc",
        },
    ).json()
    updates = _supabase_request(
        "GET",
        "ticket_updates",
        params={
            "select": "ticket_id,changed_at,actor,field_name,old_value,new_value",
            "ticket_id": id_filter,
            "order": "id.asc",
        },
    ).json()
    return _merge_supabase_ticket_rows(ticket_rows, attachments, updates)


def load_support_tickets(board_slug=None):
    if supabase_ticketing_enabled():
        try:
            return _load_supabase_tickets(board_slug=board_slug)
        except Exception:
            pass

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
        "coordination": len([t for t in tickets if t.get("status") == "ממתין לתאום"]),
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
    for ticket in load_support_tickets("pais"):
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


def build_pais_report(tickets, status_filter="", period="daily", date_from_raw="", date_to_raw=""):
    report_from, report_to = pais_report_range(period, date_from_raw, date_to_raw)
    period_filtered = filter_tickets_by_created_range(tickets, report_from, report_to)
    filtered = list(period_filtered)
    if status_filter:
        filtered = [ticket for ticket in filtered if ticket.get("status") == status_filter]

    leaderboard = []
    for user in TECHNICIAN_SUPPORT_USERS:
        user_tickets = [ticket for ticket in filtered if ticket.get("assigned_to") == user]
        done_count = len([ticket for ticket in user_tickets if support_ticket_is_done(ticket)])
        waiting_count = len([ticket for ticket in user_tickets if support_ticket_is_open(ticket)])
        coordination_count = len([ticket for ticket in user_tickets if ticket.get("status") == "ממתין לתאום"])
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
            "coordination": len([ticket for ticket in filtered if ticket.get("status") == "ממתין לתאום"]),
            "failed": len([ticket for ticket in filtered if ticket.get("status") == "נכשל"]),
            "coordinated": len([ticket for ticket in filtered if ticket.get("status") == "תואם"]),
        },
        "leaderboard": leaderboard,
    }


def save_support_attachment(file_storage, ticket_number):
    if not file_storage or not file_storage.filename:
        return None

    original = secure_filename(file_storage.filename)
    ext = os.path.splitext(original)[1].lower()
    if ext not in SUPPORT_ATTACHMENT_EXTENSIONS:
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


def smtp_email_enabled():
    return bool(SMTP_HOST and SMTP_FROM)


def send_plain_email(to_address, subject, body):
    if not smtp_email_enabled():
        raise RuntimeError("SMTP is not configured")

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = SMTP_FROM
    message["To"] = to_address
    message.set_content(body)

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


def should_notify_nastia(previous_ticket, updated_ticket):
    if (updated_ticket.get("board_slug") or "").strip().lower() != "pais":
        return False

    previous_ticket = previous_ticket or {}
    previous_status = (previous_ticket.get("status") or "").strip()
    updated_status = (updated_ticket.get("status") or "").strip()
    previous_assignee = (previous_ticket.get("assigned_to") or "").strip()
    updated_assignee = (updated_ticket.get("assigned_to") or "").strip()

    moved_to_coordination = updated_status == "ממתין לתאום" and previous_status != "ממתין לתאום"
    assigned_to_nastia = updated_assignee == "נסטיה" and previous_assignee != "נסטיה"
    return moved_to_coordination or assigned_to_nastia


def send_nastia_ticket_email(ticket):
    details = ticket.get("details") or {}
    terminal_number = (details.get("terminal_number") or "").strip()
    customer_request = (details.get("customer_request") or "").strip()
    address = (details.get("address") or "").strip()
    ticket_label = ticket.get("ticket_id") or f"#{int(ticket.get('id') or 0):04d}"
    subject = f"קריאת שירות פייס מספר מסוף {terminal_number or ticket_label}"
    body_lines = [f"פניית לקוח: {customer_request or '-'}"]
    if address:
        body_lines.append(f"כתובת: {address}")
    body_lines.append(f"מספר קריאה: {ticket_label}")
    send_plain_email(NASTIA_NOTIFICATION_EMAIL, subject, "\n".join(body_lines))


def maybe_send_nastia_ticket_notification(previous_ticket, updated_ticket):
    if not should_notify_nastia(previous_ticket, updated_ticket):
        return
    try:
        send_nastia_ticket_email(updated_ticket)
    except Exception as exc:
        print(f"Nastia notification email warning for ticket {updated_ticket.get('id')}: {exc}")


def find_support_ticket(tickets, ticket_id):
    try:
        number = int(str(ticket_id).replace("#", ""))
    except ValueError:
        return None
    for ticket in tickets:
        if int(ticket.get("id") or 0) == number:
            return ticket
    return None


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
        maybe_send_nastia_ticket_notification({}, ticket)
        return ticket

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
    maybe_send_nastia_ticket_notification({}, ticket)
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

    if "details" in changes and isinstance(changes.get("details"), dict):
        detail_fields = {
            "actions_taken",
            "coordinated_worker",
            "visit_date",
            "visit_hour_from",
            "visit_hour_to",
            "failure_notes",
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
        maybe_send_nastia_ticket_notification(previous_ticket, normalized_ticket)
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
    maybe_send_nastia_ticket_notification(previous_ticket, normalized_ticket)
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

    for i, row in enumerate(rows, start=2):
        status = row[COL_STATUS - 1].strip() if len(row) >= COL_STATUS else ""
        k_value = row[COL_K - 1].strip() if len(row) >= COL_K else ""

        if status != STATUS_PENDING or k_value != K_REQUIRED_VALUE:
            continue

        name = row[COL_NAME - 1].strip() if len(row) >= COL_NAME else ""
        idnumber = row[COL_IDNUMBER - 1].strip() if len(row) >= COL_IDNUMBER else ""
        sms_text = row[COL_SMS_TEXT - 1].strip() if len(row) >= COL_SMS_TEXT else ""

        pending.append({
            "sheet_row": i,
            "name": name,
            "idnumber": idnumber,
            "text": sms_text,
            "status": status
        })

    # Attach NumberCGR from ׳—׳™׳₪_׳¡׳׳¡ (ONLY rows where column C empty)
    try:
        if pending:
            cgr_ws = client.open_by_key(SPREADSHEET_ID).worksheet(CGR_SHEET_NAME)

            # read more rows so we can filter
            cgr_data = cgr_ws.get(f"A{CGR_START_ROW}:C")

            free_numbers = []

            for idx, row in enumerate(cgr_data):
                a_val = row[0] if len(row) >= 1 else ""
                b_val = row[1] if len(row) >= 2 else ""
                c_val = row[2] if len(row) >= 3 else ""

                # IMPORTANT: skip rows where column C is not empty
                if (c_val or "").strip():
                    continue

                num_digits = digits_only(a_val)
                if not num_digits:
                    continue

                numbercgr = num_digits if num_digits.startswith("0") else ("0" + num_digits)

                b_norm = (b_val or "").strip().upper()
                marked = bool(b_norm) and b_norm not in ("FALSE", "0", "NO")

                free_numbers.append({
                    "number": numbercgr,
                    "row": CGR_START_ROW + idx,
                    "marked": marked
                })

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
    title_style = ParagraphStyle(
        "PdfTitle",
        parent=styles["Heading1"],
        fontName=hebrew_extra_bold_font,
        fontSize=19,
        leading=23,
        alignment=TA_RIGHT,
        textColor=colors.HexColor("#0f2f57"),
        spaceAfter=10,
    )
    meta_label_style = ParagraphStyle(
        "PdfMetaLabel",
        parent=styles["BodyText"],
        fontName=latin_bold_font,
        fontSize=11,
        leading=14,
        alignment=TA_LEFT,
        textColor=colors.HexColor("#233f65"),
    )
    meta_value_style = ParagraphStyle(
        "PdfMetaValue",
        parent=styles["BodyText"],
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
        parent=styles["BodyText"],
        fontName=latin_extra_bold_font,
        fontSize=11,
        leading=13,
        alignment=TA_CENTER,
        textColor=colors.white,
    )
    cell_style = ParagraphStyle(
        "PdfCell",
        parent=styles["BodyText"],
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


def build_pais_export_rows(report):
    rows = []
    for index, ticket in enumerate(report["tickets"], start=1):
        details = ticket.get("details") or {}
        rows.append({
            "counter": index,
            "terminal_number": details.get("terminal_number") or "",
            "address": details.get("address") or "",
        })
    return rows


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
        "nastia_tickets": service_dashboard_entry(
            "nastia_tickets",
            lambda: len([t for t in load_support_tickets("pais") if (t.get("status") or "").strip() == "ממתין לתאום"]),
        ),
    })


def render_ticket_board_page(board_slug):
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    board = get_ticket_board(board_slug)
    register_service_activity(support_page_key(board_slug))
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
        page_mode="board",
        page_title=board["name"],
        page_subtitle=board["name"],
        page_icon_path=board.get("icon_path") or "",
        ticket_queue="",
        show_create_button=True,
        show_pais_report=board["slug"] == "pais",
        service_types=SUPPORT_SERVICE_TYPES,
        ticket_types=SUPPORT_TICKET_TYPES,
        priorities=SUPPORT_PRIORITIES,
        support_statuses=SUPPORT_STATUSES,
        pais_statuses=PAIS_STATUSES,
        can_access_home="home" in allowed_pages,
        can_access_support="support_tickets" in allowed_pages,
        can_access_pais="pais_tickets" in allowed_pages,
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


@app.route("/nastia-tickets")
def nastia_tickets_page():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
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
        support_statuses=SUPPORT_STATUSES,
        pais_statuses=PAIS_STATUSES,
        can_access_home="home" in allowed_pages,
        can_access_support="support_tickets" in allowed_pages,
        can_access_pais="pais_tickets" in allowed_pages,
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

    base_tickets = list(tickets)
    if queue_slug == "nastia":
        base_tickets = [ticket for ticket in base_tickets if pais_ticket_is_coordination(ticket)]

    filtered = list(base_tickets)
    if scope == "my":
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
        "statuses": PAIS_STATUSES if board_slug == "pais" else SUPPORT_STATUSES,
    })


@app.route("/pais-tickets-report-data")
def pais_tickets_report_data():
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    register_service_activity("pais_tickets")
    status_filter = (request.args.get("status") or "").strip()
    period = (request.args.get("period") or "monthly").strip().lower()
    date_from = (request.args.get("date_from") or "").strip()
    date_to = (request.args.get("date_to") or "").strip()
    if period not in {"daily", "weekly", "monthly"}:
        period = "monthly"

    report = build_pais_report(
        load_support_tickets("pais"),
        status_filter=status_filter,
        period=period,
        date_from_raw=date_from,
        date_to_raw=date_to,
    )
    return jsonify({"ok": True, **report})


@app.route("/pais-tickets-report-export")
def pais_tickets_report_export():
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    register_service_activity("pais_tickets")
    status_filter = (request.args.get("status") or "").strip()
    period = (request.args.get("period") or "monthly").strip().lower()
    export_format = (request.args.get("format") or "csv").strip().lower()
    date_from = (request.args.get("date_from") or "").strip()
    date_to = (request.args.get("date_to") or "").strip()
    if period not in {"daily", "weekly", "monthly"}:
        period = "monthly"
    if export_format not in {"csv", "pdf"}:
        export_format = "csv"

    report = build_pais_report(
        load_support_tickets("pais"),
        status_filter=status_filter,
        period=period,
        date_from_raw=date_from,
        date_to_raw=date_to,
    )

    rows = build_pais_export_rows(report)

    if export_format == "pdf":
        pdf_buffer = build_pdf_buffer(
            title="מפעל הפיס",
            metadata_rows=[
                ("Period", report.get("period") or ""),
                ("Dates", f"{report.get('date_from') or ''} - {report.get('date_to') or ''}"),
                ("Status", report.get("status") or "All"),
                ("Rows", len(rows)),
            ],
            headers=["#", "Terminal Number", "Address"],
            rows=[[row["counter"], row["terminal_number"], row["address"]] for row in rows] or [["-", "-", "No rows found for this report."]],
            rtl_columns={2},
            emphasis_columns={0},
            emphasis_meta_labels={"Dates", "Rows"},
        )
        return send_file(
            pdf_buffer,
            mimetype="application/pdf",
            as_attachment=True,
            download_name=f"pais_tickets_{period}_{report['date_from']}_to_{report['date_to']}.pdf",
        )

    csv_text = io.StringIO()
    writer = csv.DictWriter(csv_text, fieldnames=["counter", "terminal_number", "address"])
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    writer.writerow({"counter": "TOTAL", "terminal_number": len(rows), "address": ""})

    output = io.BytesIO(("\ufeff" + csv_text.getvalue()).encode("utf-8"))
    output.seek(0)
    return send_file(
        output,
        mimetype="text/csv",
        as_attachment=True,
        download_name=f"pais_tickets_{period}_{report['date_from']}_to_{report['date_to']}.csv",
    )


@app.route("/support-tickets-create", methods=["POST"])
def support_tickets_create():
    if not session.get("logged_in"):
        return redirect(url_for("login"))

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
        "status": "ממתין" if board["slug"] == "pais" else "Waiting",
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
        status = (payload.get("status") or "").strip()
        if status not in ALL_TICKET_STATUSES:
            return jsonify({"ok": False, "message": "Invalid status"}), 400
    if "details" in payload and isinstance(payload.get("details"), dict):
        details = payload["details"]
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


@app.route("/support-tickets-attachment-delete", methods=["POST"])
def support_tickets_attachment_delete():
    if not session.get("logged_in"):
        return redirect(url_for("login"))

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
        return jsonify({"ok": True, "customers": get_pending_customers()})
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

    payload = request.get_json(silent=True) or {}
    dids = payload.get("dids", [])
    # normalize numbers
    dids = [re.sub(r"\D", "", d) for d in dids]

    if not dids:
        return jsonify({"ok": False, "message": "No DID provided"}), 400

    # remove duplicates
    dids = list(dict.fromkeys(dids))

    log_dir = inforu_log_dir()
    os.makedirs(log_dir, exist_ok=True)
    path = inforu_log_path()

    # read existing numbers
    existing_numbers = set()
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
            existing_numbers = set(re.findall(r"0\d{8,9}", text))

    # filter only new numbers
    new_dids = [d for d in dids if d not in existing_numbers]

    if not new_dids:
        return jsonify({"ok": False, "message": "All numbers already logged"}), 400

    numbers_str = " , ".join(new_dids)
    date_str = datetime.now().strftime("%d.%m.%Y")

    block = f"""
=={date_str}==
\u05e9\u05dc\u05d5\u05dd \u05e8\u05d1,
\u05d0\u05e0\u05d5 \u05d7\u05d1\u05e8\u05ea \u05e0\u05d9\u05de\u05d1\u05d5\u05e1 \u05d8\u05dc\u05e7\u05d5\u05dd \u05d1\u05e2\"\u05de (\u05d7.\u05e4 514684125), \u05de\u05d0\u05e9\u05e8\u05d9\u05dd \u05d1\u05d6\u05d0\u05ea \u05db\u05d9 \u05de\u05e1\u05e4\u05e8\u05d9 \u05d4\u05e7\u05d5 \u05d4\u05d1\u05d0\u05d9\u05dd:
{numbers_str}
\u05d4\u05dd \u05d1\u05d1\u05e2\u05dc\u05d5\u05ea\u05e0\u05d5/\u05d1\u05d1\u05e2\u05dc\u05d5\u05ea \u05dc\u05e7\u05d5\u05d7 \u05e9\u05dc\u05e0\u05d5 \u05d5\u05d0\u05d9\u05e0\u05dd \u05de\u05ea\u05d7\u05d6\u05d9\u05dd.
\u05e0\u05e9\u05de\u05d7 \u05dc\u05d1\u05d9\u05e6\u05d5\u05e2 \u05d0\u05d9\u05de\u05d5\u05ea \u05de\u05e1\u05e4\u05e8 \u05dc\u05e6\u05d5\u05e8\u05da \u05e7\u05d9\u05d3\u05d5\u05dd \u05d4\u05e7\u05de\u05ea \u05d4\u05e9\u05d9\u05e8\u05d5\u05ea.
\u05ea\u05d5\u05d3\u05d4

"""

    with open(path, "a", encoding="utf-8") as f:
        f.write(block)

    if not TOKEN_INFORU:
        return jsonify({
            "ok": False,
            "message": "Inforu Make webhook is not configured. Set TOKEN_INFORU or INFORU_MAKE_WEBHOOK_URL.",
        }), 500

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
        print("Make webhook error:", e)
        return jsonify({
            "ok": False,
            "message": "Failed to send Inforu email via Make webhook.",
        }), 502

    return jsonify({
        "ok": True,
        "added": len(new_dids),
        "numbers": new_dids
    })


# ================================
# RETURN INFORU LOG TO FRONTEND
# ================================

@app.route("/inforu-log", methods=["GET"])
def get_inforu_log():

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

    # Repair common mojibake pattern seen in old log entries.
    if "׳" in content:
        try:
            repaired = content.encode("latin1", errors="ignore").decode("utf-8", errors="ignore")
            if repaired.strip():
                content = repaired
        except Exception:
            pass

    return content


@app.route("/export", methods=["POST"])
def export_csv():

    data = request.get_json(silent=True)
    if not isinstance(data, list) or not data:
        return jsonify({"ok": False, "message": "No data to export."}), 400
    
    

    rows_out = []
    updates = []

    for r in data:
        if not isinstance(r, dict):
            continue

        domain = (r.get("Domain") or "").strip()
        caller_id = (r.get("DID") or "").strip()
        numbercgr = (r.get("NumberCGR") or "").strip()
        template_txt = (r.get("Text") or "").strip()
        cgr_row = int(r.get("cgr_row") or 0)

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
            updates.append({
                "range": (
                    f"{gspread.utils.rowcol_to_a1(cgr_row, CGR_COL_DOMAIN)}:"
                    f"{gspread.utils.rowcol_to_a1(cgr_row, CGR_COL_USED)}"
                ),
                "values": [[domain, datetime.now().strftime("%Y-%m-%d"), True]]
            })

    # Update Google Sheet ׳—׳™׳₪_׳¡׳׳¡
    try:
        if updates:
            client = get_gspread_client()
            cgr_ws = client.open_by_key(SPREADSHEET_ID).worksheet(CGR_SHEET_NAME)
            cgr_ws.batch_update(updates)
    except Exception as e:
        print ("CGR UPDATE ERROR:", e)
        print("CGR sheet updated successfully")

    df = pd.DataFrame(rows_out, columns=["name", "caller_id_number", "did", "template"])
    df.rename(columns={"did": "number"}, inplace=True)

    output = io.BytesIO()
    df.to_csv(output, index=False, encoding="utf-8-sig")
    output.seek(0)

    return send_file(output, mimetype="text/csv", as_attachment=True, download_name="sms_export.csv")

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

        if is_done_status(status):
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
