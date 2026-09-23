import importlib
import io
import json
import os
import sys
import tempfile
import types
import unittest
from datetime import datetime
from urllib.parse import parse_qs, unquote, urlparse
from zoneinfo import ZoneInfo


class SupportTicketsTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.install_import_stubs()
        os.environ["SECRET_KEY"] = "test-secret-key"
        os.environ["APP_ENV"] = "testing"
        os.environ["FIREBERRY_TOKENID"] = "token"
        os.environ["CRM_URL"] = "https://crm.example"
        os.environ["SMS_URL"] = "https://sms.example"
        os.environ["SMS_TOKEN"] = "sms-token"
        os.environ["APP_PASSWORD"] = "secret123"
        import app as app_module

        cls.app_module = importlib.reload(app_module)

    @staticmethod
    def install_import_stubs():
        if "gspread" not in sys.modules:
            gspread = types.ModuleType("gspread")
            gspread.authorize = lambda creds: object()
            sys.modules["gspread"] = gspread

        if "pandas" not in sys.modules:
            pandas = types.ModuleType("pandas")
            pandas.DataFrame = object
            sys.modules["pandas"] = pandas

        if "google" not in sys.modules:
            sys.modules["google"] = types.ModuleType("google")

        if "google.auth" not in sys.modules:
            sys.modules["google.auth"] = types.ModuleType("google.auth")

        if "google.auth.exceptions" not in sys.modules:
            exceptions = types.ModuleType("google.auth.exceptions")
            exceptions.RefreshError = RuntimeError
            sys.modules["google.auth.exceptions"] = exceptions

        if "google.auth.transport" not in sys.modules:
            sys.modules["google.auth.transport"] = types.ModuleType("google.auth.transport")

        if "google.auth.transport.requests" not in sys.modules:
            requests_module = types.ModuleType("google.auth.transport.requests")
            requests_module.Request = object
            sys.modules["google.auth.transport.requests"] = requests_module

        if "google.oauth2" not in sys.modules:
            sys.modules["google.oauth2"] = types.ModuleType("google.oauth2")

        if "google.oauth2.service_account" not in sys.modules:
            service_account = types.ModuleType("google.oauth2.service_account")

            class FakeCredentials:
                @classmethod
                def from_service_account_info(cls, info, scopes=None):
                    return cls()

                def refresh(self, request):
                    return None

            service_account.Credentials = FakeCredentials
            sys.modules["google.oauth2.service_account"] = service_account

        if "googleapiclient" not in sys.modules:
            sys.modules["googleapiclient"] = types.ModuleType("googleapiclient")

        if "googleapiclient.discovery" not in sys.modules:
            discovery = types.ModuleType("googleapiclient.discovery")
            discovery.build = lambda *args, **kwargs: object()
            sys.modules["googleapiclient.discovery"] = discovery

        if "googleapiclient.http" not in sys.modules:
            http = types.ModuleType("googleapiclient.http")
            http.MediaIoBaseDownload = object
            sys.modules["googleapiclient.http"] = http

        if "bidi" not in sys.modules:
            sys.modules["bidi"] = types.ModuleType("bidi")

        if "bidi.algorithm" not in sys.modules:
            bidi_algorithm = types.ModuleType("bidi.algorithm")
            bidi_algorithm.get_display = lambda value: value
            sys.modules["bidi.algorithm"] = bidi_algorithm

        if "reportlab" not in sys.modules:
            sys.modules["reportlab"] = types.ModuleType("reportlab")

        if "reportlab.lib" not in sys.modules:
            sys.modules["reportlab.lib"] = types.ModuleType("reportlab.lib")

        if "reportlab.lib.colors" not in sys.modules:
            colors = types.ModuleType("reportlab.lib.colors")
            colors.HexColor = lambda value: value
            colors.whitesmoke = "whitesmoke"
            colors.black = "black"
            colors.white = "white"
            sys.modules["reportlab.lib.colors"] = colors

        if "reportlab.lib.enums" not in sys.modules:
            enums = types.ModuleType("reportlab.lib.enums")
            enums.TA_CENTER = 1
            enums.TA_LEFT = 0
            enums.TA_RIGHT = 2
            sys.modules["reportlab.lib.enums"] = enums

        if "reportlab.lib.pagesizes" not in sys.modules:
            pagesizes = types.ModuleType("reportlab.lib.pagesizes")
            pagesizes.A4 = (595, 842)
            sys.modules["reportlab.lib.pagesizes"] = pagesizes

        if "reportlab.lib.styles" not in sys.modules:
            styles = types.ModuleType("reportlab.lib.styles")

            class FakeParagraphStyle:
                def __init__(self, name, parent=None, **kwargs):
                    self.name = name
                    self.parent = parent
                    for key, value in kwargs.items():
                        setattr(self, key, value)

            styles.ParagraphStyle = FakeParagraphStyle
            styles.getSampleStyleSheet = lambda: {
                "Normal": FakeParagraphStyle("Normal"),
                "Heading1": FakeParagraphStyle("Heading1"),
                "BodyText": FakeParagraphStyle("BodyText"),
            }
            sys.modules["reportlab.lib.styles"] = styles

        if "reportlab.lib.units" not in sys.modules:
            units = types.ModuleType("reportlab.lib.units")
            units.mm = 1
            sys.modules["reportlab.lib.units"] = units

        if "reportlab.pdfbase" not in sys.modules:
            sys.modules["reportlab.pdfbase"] = types.ModuleType("reportlab.pdfbase")

        if "reportlab.pdfbase.pdfmetrics" not in sys.modules:
            pdfmetrics = types.ModuleType("reportlab.pdfbase.pdfmetrics")
            pdfmetrics.registerFont = lambda *args, **kwargs: None
            sys.modules["reportlab.pdfbase.pdfmetrics"] = pdfmetrics

        if "reportlab.pdfbase.ttfonts" not in sys.modules:
            ttfonts = types.ModuleType("reportlab.pdfbase.ttfonts")

            class FakeTTFont:
                def __init__(self, *args, **kwargs):
                    self.args = args
                    self.kwargs = kwargs

            ttfonts.TTFont = FakeTTFont
            sys.modules["reportlab.pdfbase.ttfonts"] = ttfonts

        if "reportlab.platypus" not in sys.modules:
            platypus = types.ModuleType("reportlab.platypus")
            platypus.Paragraph = lambda *args, **kwargs: ("Paragraph", args, kwargs)

            class FakeSimpleDocTemplate:
                def __init__(self, buffer, *args, **kwargs):
                    self.buffer = buffer
                    self.args = args
                    self.kwargs = kwargs

                def build(self, story, *args, **kwargs):
                    self.buffer.write(b"%PDF-FAKE")

            class FakeTable:
                def __init__(self, *args, **kwargs):
                    self.args = args
                    self.kwargs = kwargs
                    self.styles = []

                def setStyle(self, style):
                    self.styles.append(style)

            platypus.SimpleDocTemplate = FakeSimpleDocTemplate
            platypus.Spacer = lambda *args, **kwargs: ("Spacer", args, kwargs)
            platypus.Table = FakeTable
            platypus.TableStyle = lambda *args, **kwargs: ("TableStyle", args, kwargs)
            platypus.Image = lambda *args, **kwargs: ("Image", args, kwargs)
            sys.modules["reportlab.platypus"] = platypus

    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.app = self.app_module.app
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()
        self.support_log_file = os.path.join(self.tempdir.name, "support.log")
        self.screens_dir = os.path.join(self.tempdir.name, "Screens")
        self.original_log = self.app_module.SUPPORT_LOG_FILE
        self.original_screens = self.app_module.SUPPORT_SCREEN_DIR
        self.original_supabase_url = self.app_module.SUPABASE_URL
        self.original_supabase_key = self.app_module.SUPABASE_KEY
        self.original_israel_now = self.app_module.israel_now
        self.original_get_gspread_client = self.app_module.get_gspread_client
        self.original_get_feature_report_counts = self.app_module.get_feature_report_counts
        self.original_send_nastia_ticket_email = self.app_module.send_nastia_ticket_email
        self.original_send_nastia_waiting_alert_email = self.app_module.send_nastia_waiting_alert_email
        self.original_send_plain_email = self.app_module.send_plain_email
        self.original_build_hot_field_report_pdf = self.app_module.build_hot_field_report_pdf
        self.original_smtp_from = self.app_module.SMTP_FROM
        self.original_smtp_username = self.app_module.SMTP_USERNAME
        self.original_token_inforu = self.app_module.TOKEN_INFORU
        self.original_requests_post = self.app_module.requests.post
        self.original_inforu_log_dir = self.app_module.inforu_log_dir
        self.original_inforu_log_path = self.app_module.inforu_log_path
        self.original_pais_notification_from = self.app_module.PAIS_NOTIFICATION_FROM
        self.original_vercel = os.environ.get("VERCEL")
        self.app_module.SUPPORT_LOG_FILE = self.support_log_file
        self.app_module.SUPPORT_SCREEN_DIR = self.screens_dir
        self.app_module.SUPABASE_URL = ""
        self.app_module.SUPABASE_KEY = ""
        self.seed_tickets()

    def tearDown(self):
        self.app_module.SUPPORT_LOG_FILE = self.original_log
        self.app_module.SUPPORT_SCREEN_DIR = self.original_screens
        self.app_module.SUPABASE_URL = self.original_supabase_url
        self.app_module.SUPABASE_KEY = self.original_supabase_key
        self.app_module.israel_now = self.original_israel_now
        self.app_module.get_gspread_client = self.original_get_gspread_client
        self.app_module.get_feature_report_counts = self.original_get_feature_report_counts
        self.app_module.send_nastia_ticket_email = self.original_send_nastia_ticket_email
        self.app_module.send_nastia_waiting_alert_email = self.original_send_nastia_waiting_alert_email
        self.app_module.send_plain_email = self.original_send_plain_email
        self.app_module.build_hot_field_report_pdf = self.original_build_hot_field_report_pdf
        self.app_module.SMTP_FROM = self.original_smtp_from
        self.app_module.SMTP_USERNAME = self.original_smtp_username
        self.app_module.TOKEN_INFORU = self.original_token_inforu
        self.app_module.requests.post = self.original_requests_post
        self.app_module.inforu_log_dir = self.original_inforu_log_dir
        self.app_module.inforu_log_path = self.original_inforu_log_path
        self.app_module.PAIS_NOTIFICATION_FROM = self.original_pais_notification_from
        if self.original_vercel is None:
            os.environ.pop("VERCEL", None)
        else:
            os.environ["VERCEL"] = self.original_vercel
        self.tempdir.cleanup()

    def seed_tickets(self):
        os.makedirs(self.screens_dir, exist_ok=True)
        ticket_folder = os.path.join(self.screens_dir, "TicketID0001")
        os.makedirs(ticket_folder, exist_ok=True)
        attachment_path = os.path.join(ticket_folder, "example.jpg")
        with open(attachment_path, "wb") as handle:
            handle.write(b"jpg")

        tickets = [{
            "id": 1,
            "created_at": "2026-06-29T10:00:00+03:00",
            "created_at_display": "29/06/2026 10:00",
            "creator": "Admin",
            "ticket_type": "שאלה",
            "service_type": "מרכזייה",
            "domain": "example.com",
            "priority": "Medium",
            "description": "Test ticket",
            "solution": "",
            "status": "Waiting",
            "assigned_to": "",
            "attachments": [{
                "original_name": "example.jpg",
                "saved_name": "example.jpg",
                "folder": "TicketID0001",
                "url": "/support-ticket-attachment/TicketID0001/example.jpg",
            }],
            "updates": [],
        }]
        self.app_module.save_support_tickets(tickets)

    def login(self, username, password="secret123"):
        return self.client.post(
            "/login",
            data={"username": username, "password": password},
            follow_redirects=False,
        )

    def test_admin_can_delete_ticket(self):
        self.login("admin@nimbusip.com")
        response = self.client.post("/support-tickets-delete", json={"ticket_id": 1})

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["ok"])
        self.assertEqual(self.app_module.load_support_tickets(), [])
        self.assertFalse(os.path.exists(os.path.join(self.screens_dir, "TicketID0001")))

    def test_non_admin_cannot_delete_ticket(self):
        self.login("eugeni@nimbusip.com")
        response = self.client.post("/support-tickets-delete", json={"ticket_id": 1})

        self.assertEqual(response.status_code, 403)
        self.assertFalse(response.get_json()["ok"])
        self.assertEqual(len(self.app_module.load_support_tickets()), 1)

    def test_support_data_returns_only_requested_board(self):
        tickets = self.app_module.load_support_tickets()
        tickets.append({
            "id": 2,
            "board_slug": "pais",
            "created_at": "2026-06-29T11:00:00+03:00",
            "created_at_display": "29/06/2026 11:00",
            "creator": "Admin",
            "ticket_type": "שירות",
            "service_type": "מפעל הפיס",
            "domain": "",
            "priority": "Medium",
            "description": "",
            "solution": "",
            "status": "Waiting",
            "assigned_to": "",
            "details": {
                "terminal_number": "1234",
                "address": "Test address",
                "customer_request": "Needs check",
                "actions_taken": "",
            },
            "attachments": [],
            "updates": [],
        })
        self.app_module.save_support_tickets(tickets)

        self.login("admin@nimbusip.com")
        response = self.client.get("/support-tickets-data?board=support")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(len(payload["tickets"]), 1)
        self.assertEqual(payload["tickets"][0]["board_slug"], "support")

    def test_ticket_list_uses_last_edit_timestamp_after_update(self):
        self.app_module.israel_now = lambda: datetime(2026, 7, 10, 14, 35, tzinfo=ZoneInfo("Asia/Jerusalem"))

        self.login("admin@nimbusip.com")
        update_response = self.client.post(
            "/support-tickets-update",
            json={
                "ticket_id": 1,
                "assigned_to": "ניר",
            },
        )

        self.assertEqual(update_response.status_code, 200)
        update_payload = update_response.get_json()
        self.assertEqual(update_payload["ticket"]["created_at_display"], "29/06/2026 10:00")
        self.assertEqual(update_payload["ticket"]["last_edited_at_display"], "10/07/2026 14:35")
        self.assertEqual(update_payload["ticket"]["list_timestamp_display"], "10/07/2026 14:35")

        data_response = self.client.get("/support-tickets-data?board=support")

        self.assertEqual(data_response.status_code, 200)
        ticket = data_response.get_json()["tickets"][0]
        self.assertEqual(ticket["created_at_display"], "29/06/2026 10:00")
        self.assertEqual(ticket["last_edited_at_display"], "10/07/2026 14:35")
        self.assertEqual(ticket["list_timestamp_display"], "10/07/2026 14:35")

    def test_ticket_list_uses_last_edit_timestamp_for_pais_detail_changes(self):
        tickets = self.app_module.load_support_tickets()
        tickets.append({
            "id": 2,
            "board_slug": "pais",
            "created_at": "2026-07-08T09:00:00+03:00",
            "created_at_display": "08/07/2026 09:00",
            "creator": "Admin",
            "ticket_type": "שירות",
            "service_type": "מפעל הפיס",
            "domain": "",
            "priority": "Medium",
            "description": "",
            "solution": "",
            "status": "ממתין",
            "assigned_to": "ניר",
            "details": {
                "terminal_number": "5555",
                "address": "Test address",
                "customer_request": "Original request",
                "actions_taken": "",
            },
            "attachments": [],
            "updates": [],
        })
        self.app_module.save_support_tickets(tickets)
        self.app_module.israel_now = lambda: datetime(2026, 7, 11, 9, 20, tzinfo=ZoneInfo("Asia/Jerusalem"))

        self.login("admin@nimbusip.com")
        update_response = self.client.post(
            "/support-tickets-update",
            json={
                "ticket_id": 2,
                "details": {
                    "actions_taken": "Updated note",
                },
            },
        )

        self.assertEqual(update_response.status_code, 200)
        update_payload = update_response.get_json()
        self.assertEqual(update_payload["ticket"]["details"]["actions_taken"], "Updated note")
        self.assertEqual(update_payload["ticket"]["last_edited_at_display"], "11/07/2026 09:20")

        data_response = self.client.get("/support-tickets-data?board=pais")

        self.assertEqual(data_response.status_code, 200)
        ticket = next(item for item in data_response.get_json()["tickets"] if item["id"] == 2)
        self.assertEqual(ticket["created_at_display"], "08/07/2026 09:00")
        self.assertEqual(ticket["last_edited_at_display"], "11/07/2026 09:20")
        self.assertEqual(ticket["list_timestamp_display"], "11/07/2026 09:20")

    def test_features_status_lookup_aggregates_services_without_login(self):
        class FakeWorksheet:
            def __init__(self, rows):
                self.rows = rows

            def get_all_values(self):
                return self.rows

        class FakeSpreadsheet:
            def __init__(self, worksheets):
                self.worksheets = worksheets

            def worksheet(self, name):
                return FakeWorksheet(self.worksheets[name])

        class FakeGspreadClient:
            def __init__(self, worksheets):
                self.worksheets = worksheets

            def open_by_key(self, key):
                return FakeSpreadsheet(self.worksheets)

        worksheets = {
            self.app_module.SHEET_NAME: [
                ["name", "id", "", "", "", "", "", "status"],
                ["Business One", "514684125", "", "", "", "", "", "כפילות"],
                ["Business One", "514684125", "", "", "", "", "", "בוצע"],
                ["Business One", "514684125", "", "", "", "", "", "בוצע"],
            ],
            self.app_module.RECORDING_OPENING_SHEET_NAME: [
                ["name", "id", "", "", "", "", "", "", "status"],
                ["Business One", "514684125", "", "", "", "", "", "", "ממתין"],
            ],
            self.app_module.BOT_SHEET_NAME: [
                ["name", "id", "", "", "", "", "", "status"],
                ["Business One", "514684125", "", "", "", "", "", "בוצע"],
            ],
            self.app_module.HUMAN_SERVICE_SHEET_NAME: [
                ["name", "id", "", "", "", "", "", "status"],
                ["Business One", "514684125", "", "", "", "", "", "ממתין"],
            ],
            self.app_module.F2M_SHEET_NAME: [
                ["name", "id", "", "", "", "", "", "status"],
                ["Business One", "514684125", "", "", "", "", "", ""],
                ["Business One", "514684125", "", "", "", "", "", "בוצע"],
            ],
            self.app_module.RECORDING_STORAGE_SHEET_NAME: [
                ["name", "id", "", "", "", "", "", "status"],
                ["Business One", "514684125", "", "", "", "", "", ""],
            ],
        }
        self.app_module.get_gspread_client = lambda: FakeGspreadClient(worksheets)

        response = self.client.get("/features-status-data?customer_id=051-4684125")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["customer_id"], "514684125")
        self.assertEqual(payload["found_count"], 6)
        self.assertEqual(payload["missing_count"], 0)
        self.assertEqual(payload["business_names"], ["Business One"])
        self.assertEqual(len(payload["services"]), 6)
        self.assertEqual(len(payload["services"][0]["entries"]), 1)
        self.assertEqual(payload["services"][0]["entries"][0]["status"], "בוצע")
        self.assertEqual(payload["services"][1]["entries"][0]["status"], "ממתין")
        self.assertEqual(len(payload["services"][4]["entries"]), 1)
        self.assertEqual(payload["services"][4]["entries"][0]["status"], "בוצע")
        self.assertEqual(payload["services"][5]["entries"][0]["status"], "לא הוגדר")

    def test_recording_storage_data_excludes_not_interested_customers(self):
        class FakeWorksheet:
            def __init__(self, rows):
                self.rows = rows

            def get_all_values(self):
                return self.rows

        class FakeSpreadsheet:
            def __init__(self, worksheets):
                self.worksheets = worksheets

            def worksheet(self, name):
                return FakeWorksheet(self.worksheets[name])

        class FakeGspreadClient:
            def __init__(self, worksheets):
                self.worksheets = worksheets

            def open_by_key(self, key):
                return FakeSpreadsheet(self.worksheets)

        worksheets = {
            self.app_module.RECORDING_STORAGE_SHEET_NAME: [
                ["name", "id", "", "", "order_id", "", "", "status", "", "storage_size"],
                ["Active Customer", "123", "", "", "1001", "", "", "ממתין", "", "50GB"],
                ["Ignore Customer", "456", "", "", "1002", "", "", "לא מעוניין", "", "100GB"],
                ["Done Customer", "789", "", "", "1003", "", "", "בוצע", "", "200GB"],
            ],
        }
        self.app_module.get_gspread_client = lambda: FakeGspreadClient(worksheets)

        self.login("admin@nimbusip.com")
        response = self.client.get("/recording-storage-data")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["count"], 1)
        self.assertEqual(len(payload["customers"]), 1)
        self.assertEqual(payload["customers"][0]["name"], "Active Customer")
        self.assertEqual(payload["customers"][0]["status"], "ממתין")

    def test_can_create_pais_ticket_without_description_solution(self):
        self.login("admin@nimbusip.com")
        response = self.client.post(
            "/support-tickets-create",
            data={
                "board_slug": "pais",
                "terminal_number": "7788",
                "address": "רחוב הבדיקה 5",
                "static_ip": "10.0.0.8",
                "altura": "כן",
                "look_back": "24h",
                "contact_name": "דני",
                "contact_phone": "0501234567",
                "customer_request": "מסוף לא מגיב",
                "actions_taken": "בוצע איפוס",
                "assigned_to": "זורה",
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["ticket"]["board_slug"], "pais")
        self.assertEqual(payload["ticket"]["assigned_to"], "זורה")
        self.assertEqual(payload["ticket"]["details"]["terminal_number"], "7788")
        self.assertEqual(payload["ticket"]["status"], "ממתין")
        self.assertEqual(payload["ticket"]["description"], "")
        self.assertEqual(payload["ticket"]["solution"], "")

    def test_can_create_hot_kiryot_ticket_from_mail_fields(self):
        self.login("admin@nimbusip.com")
        response = self.client.post(
            "/support-tickets-create",
            data={
                "board_slug": "hot-kiryot",
                "opened_at": "14:12 08.09",
                "call_number": "275749117",
                "opened_by": "רוני",
                "customer_id": "510571870",
                "customer_name": "חיים",
                "line_code": "887585-25018021",
                "address": "האופה 1, נתניה",
                "on_site_contact": "חיים 0524443593",
                "technical_contact": "",
                "availability_hours": "8:00-17:00",
                "remote_checks": "בדיקות של מוקד נימבוס מול הלקוח",
                "issue_summary": "PANCODE לא עובד",
                "technician_actions": "בדיקות של מוקד נימבוס מול הלקוח",
                "equipment_type": "-אינטרקום?",
                "service_agreement": "",
                "technical_notes": "",
                "assigned_to": "גולן",
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["ticket"]["board_slug"], "hot-kiryot")
        self.assertEqual(payload["ticket"]["service_type"], "הוט קריאות")
        self.assertEqual(payload["ticket"]["status"], "ממתין")
        self.assertEqual(payload["ticket"]["assigned_to"], "גולן")
        self.assertEqual(payload["ticket"]["details"]["call_number"], "275749117")
        self.assertEqual(payload["ticket"]["details"]["customer_name"], "חיים")
        self.assertEqual(payload["ticket"]["details"]["issue_summary"], "PANCODE לא עובד")

    def test_supabase_hot_ticket_creation_upserts_board_before_ticket_insert(self):
        calls = []
        original_request = self.app_module._supabase_request
        self.app_module.SUPABASE_URL = "https://supabase.example"
        self.app_module.SUPABASE_KEY = "service-key"

        def fake_supabase_request(method, path, *, params=None, json_body=None, prefer=None):
            calls.append({
                "method": method,
                "path": path,
                "params": params,
                "json_body": json_body,
                "prefer": prefer,
            })

            class FakeResponse:
                def __init__(self, payload):
                    self._payload = payload

                def json(self):
                    return self._payload

            if path == "ticket_boards":
                return FakeResponse([])
            if path == "support_tickets":
                return FakeResponse([{
                    "id": 22,
                    "board_slug": "hot-kiryot",
                    "created_at": "2026-07-08T09:00:00+03:00",
                    "created_at_display": "08/07/2026 09:00",
                    "creator": "Admin",
                    "ticket_type": "שירות",
                    "service_type": "הוט קריאות",
                    "domain": "",
                    "priority": "Medium",
                    "description": "",
                    "solution": "",
                    "status": "ממתין",
                    "assigned_to": "גולן",
                    "details": {
                        "call_number": "275749117",
                        "customer_name": "חיים",
                        "address": "האופה 1, נתניה",
                        "issue_summary": "PANCODE לא עובד",
                    },
                }])
            raise AssertionError(f"Unexpected Supabase path: {path}")

        self.app_module._supabase_request = fake_supabase_request
        try:
            ticket = self.app_module.create_support_ticket_record({
                "created_at": "2026-07-08T09:00:00+03:00",
                "created_at_display": "08/07/2026 09:00",
                "creator": "Admin",
                "board_slug": "hot-kiryot",
                "ticket_type": "שירות",
                "service_type": "הוט קריאות",
                "domain": "",
                "priority": "Medium",
                "description": "",
                "solution": "",
                "status": "ממתין",
                "assigned_to": "גולן",
                "details": {
                    "call_number": "275749117",
                    "customer_name": "חיים",
                    "address": "האופה 1, נתניה",
                    "issue_summary": "PANCODE לא עובד",
                },
            })
        finally:
            self.app_module._supabase_request = original_request

        self.assertEqual(ticket["board_slug"], "hot-kiryot")
        self.assertGreaterEqual(len(calls), 2)
        self.assertEqual(calls[0]["path"], "ticket_boards")
        self.assertEqual(calls[0]["json_body"][0]["slug"], "hot-kiryot")
        self.assertEqual(calls[1]["path"], "support_tickets")

    def test_support_tickets_data_still_loads_when_supabase_attachment_queries_fail(self):
        original_request = self.app_module._supabase_request
        self.app_module.SUPABASE_URL = "https://supabase.example"
        self.app_module.SUPABASE_KEY = "service-key"

        class FakeResponse:
            def __init__(self, payload):
                self._payload = payload

            def json(self):
                return self._payload

        def fake_supabase_request(method, path, *, params=None, json_body=None, prefer=None):
            if path == "support_tickets":
                return FakeResponse([{
                    "id": 22,
                    "board_slug": "pais",
                    "created_at": "2026-07-08T09:00:00+03:00",
                    "created_at_display": "08/07/2026 09:00",
                    "creator": "Admin",
                    "ticket_type": "שירות",
                    "service_type": "מפעל הפיס",
                    "domain": "",
                    "priority": "Medium",
                    "description": "",
                    "solution": "",
                    "status": "ממתין",
                    "assigned_to": "",
                    "details": {
                        "terminal_number": "603884",
                        "address": "בדיקה 6",
                    },
                }])
            if path in {"ticket_attachments", "ticket_updates"}:
                raise RuntimeError(f"{path} unavailable")
            raise AssertionError(f"Unexpected Supabase path: {path}")

        self.app_module._supabase_request = fake_supabase_request
        self.login("admin@nimbusip.com")
        try:
            response = self.client.get("/support-tickets-data?board=pais")
        finally:
            self.app_module._supabase_request = original_request

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(len(payload["tickets"]), 1)
        self.assertEqual(payload["tickets"][0]["id"], 22)
        self.assertEqual(payload["tickets"][0]["attachments"], [])
        self.assertEqual(payload["tickets"][0]["updates"], [])

    def test_can_create_ticket_with_multiple_image_attachments(self):
        self.login("admin@nimbusip.com")
        response = self.client.post(
            "/support-tickets-create",
            data={
                "board_slug": "support",
                "ticket_type": "תקלה",
                "service_type": "מצלמות",
                "priority": "Medium",
                "assigned_to": "ניר",
                "description": "Need image evidence",
                "solution": "",
                "attachments": [
                    (io.BytesIO(b"image-one"), "first.jpg"),
                    (io.BytesIO(b"image-two"), "second.png"),
                ],
            },
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["ok"])
        self.assertEqual(len(payload["ticket"]["attachments"]), 2)

        ticket_folder = os.path.join(self.screens_dir, "TicketID0002")
        self.assertTrue(os.path.isdir(ticket_folder))
        self.assertEqual(len(os.listdir(ticket_folder)), 2)

    def test_can_add_image_attachments_to_existing_ticket(self):
        self.login("admin@nimbusip.com")
        response = self.client.post(
            "/support-tickets-attachments",
            data={
                "ticket_id": "1",
                "attachments": [
                    (io.BytesIO(b"image-three"), "third.jpg"),
                    (io.BytesIO(b"image-four"), "fourth.png"),
                ],
            },
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["ok"])
        self.assertEqual(len(payload["ticket"]["attachments"]), 3)

        ticket_folder = os.path.join(self.screens_dir, "TicketID0001")
        self.assertTrue(os.path.isdir(ticket_folder))
        self.assertEqual(len(os.listdir(ticket_folder)), 3)

    def test_can_delete_image_attachment_from_existing_ticket(self):
        self.login("admin@nimbusip.com")
        response = self.client.post(
            "/support-tickets-attachment-delete",
            json={
                "ticket_id": "1",
                "folder": "TicketID0001",
                "saved_name": "example.jpg",
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["ok"])
        self.assertEqual(len(payload["ticket"]["attachments"]), 0)

        ticket_folder = os.path.join(self.screens_dir, "TicketID0001")
        self.assertFalse(os.path.exists(os.path.join(ticket_folder, "example.jpg")))

    def test_pais_coordination_status_change_sends_waiting_alert_to_nastya(self):
        tickets = self.app_module.load_support_tickets()
        tickets.append({
            "id": 2,
            "board_slug": "pais",
            "created_at": "2026-07-08T09:00:00+03:00",
            "created_at_display": "08/07/2026 09:00",
            "creator": "Admin",
            "ticket_type": "שירות",
            "service_type": "מפעל הפיס",
            "domain": "",
            "priority": "Medium",
            "description": "",
            "solution": "",
            "status": "ממתין",
            "assigned_to": "ניר",
            "details": {
                "terminal_number": "9988",
                "address": "Email street 4",
                "customer_request": "לקוח מבקש תיאום",
                "actions_taken": "",
            },
            "attachments": [],
            "updates": [],
        })
        self.app_module.save_support_tickets(tickets)
        sent_tickets = []
        self.app_module.send_nastia_waiting_alert_email = lambda ticket: sent_tickets.append(ticket)

        self.login("admin@nimbusip.com")
        response = self.client.post(
            "/support-tickets-update",
            json={
                "ticket_id": 2,
                "status": "ממתין לתאום",
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["ticket"]["status"], "ממתין לתאום")
        self.assertTrue(payload["ticket"]["notification_attempted"])
        self.assertTrue(payload["ticket"]["notification_sent"])
        self.assertEqual(len(sent_tickets), 1)

    def test_extended_assignee_list_is_available(self):
        self.assertIn("איציק", self.app_module.SUPPORT_USERS)
        self.assertIn("זורה", self.app_module.SUPPORT_USERS)
        self.assertIn("מוסטפה.א", self.app_module.SUPPORT_USERS)
        self.assertIn("מוסטפה.ח", self.app_module.SUPPORT_USERS)
        self.assertIn("נסטיה", self.app_module.SUPPORT_USERS)
        self.assertIn("ממתין לתאום", self.app_module.PAIS_STATUSES)
        self.assertIn("אין מענה", self.app_module.PAIS_STATUSES)

    def test_assignment_lists_exclude_nastia(self):
        self.login("admin@nimbusip.com")
        response = self.client.get("/support-tickets-data?board=pais")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertNotIn("נסטיה", payload["users"])

    def test_nastia_queue_returns_coordination_tickets(self):
        tickets = self.app_module.load_support_tickets()
        tickets.extend([
            {
                "id": 2,
                "board_slug": "pais",
                "created_at": "2026-07-08T09:00:00+03:00",
                "created_at_display": "08/07/2026 09:00",
                "creator": "Admin",
                "ticket_type": "שירות",
                "service_type": "מפעל הפיס",
                "domain": "",
                "priority": "Medium",
                "description": "",
                "solution": "",
                "status": "ממתין לתאום",
                "assigned_to": "ניר",
                "details": {
                    "terminal_number": "6001",
                    "address": "Coordination address",
                    "customer_request": "R4",
                    "actions_taken": "",
                    "coordinated_worker": "",
                    "visit_date": "",
                    "visit_hour_from": "",
                    "visit_hour_to": "",
                },
                "attachments": [],
                "updates": [],
            },
            {
                "id": 3,
                "board_slug": "pais",
                "created_at": "2026-07-08T10:00:00+03:00",
                "created_at_display": "08/07/2026 10:00",
                "creator": "Admin",
                "ticket_type": "שירות",
                "service_type": "מפעל הפיס",
                "domain": "",
                "priority": "Medium",
                "description": "",
                "solution": "",
                "status": "בוצע",
                "assigned_to": "גולן",
                "details": {
                    "terminal_number": "6002",
                    "address": "Regular address",
                    "customer_request": "R5",
                    "actions_taken": "",
                },
                "attachments": [],
                "updates": [],
            },
        ])
        self.app_module.save_support_tickets(tickets)

        self.login("admin@nimbusip.com")
        response = self.client.get("/support-tickets-data?board=pais&queue=nastia")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(len(payload["tickets"]), 1)
        self.assertEqual(payload["tickets"][0]["details"]["terminal_number"], "6001")

    def test_nastia_queue_includes_hot_coordination_tickets(self):
        tickets = self.app_module.load_support_tickets()
        tickets.extend([
            {
                "id": 2,
                "board_slug": "hot-kiryot",
                "created_at": "2026-07-08T09:00:00+03:00",
                "created_at_display": "08/07/2026 09:00",
                "creator": "Admin",
                "ticket_type": "שירות",
                "service_type": "הוט קריות",
                "domain": "",
                "priority": "Medium",
                "description": "",
                "solution": "",
                "status": "ממתין לתיאום",
                "assigned_to": "ניר",
                "details": {
                    "call_number": "275749117",
                    "customer_name": "חיים",
                    "address": "Hot coordination address",
                    "issue_summary": "PANCODE לא עובד",
                    "coordinated_worker": "",
                    "visit_date": "",
                    "visit_hour_from": "",
                    "visit_hour_to": "",
                },
                "attachments": [],
                "updates": [],
            },
        ])
        self.app_module.save_support_tickets(tickets)

        self.login("admin@nimbusip.com")
        response = self.client.get("/support-tickets-data?board=pais&queue=nastia")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(len(payload["tickets"]), 1)
        self.assertEqual(payload["tickets"][0]["board_slug"], "hot-kiryot")
        self.assertEqual(payload["tickets"][0]["details"]["call_number"], "275749117")

    def test_nastia_queue_prioritizes_waiting_tickets_at_top(self):
        tickets = self.app_module.load_support_tickets()
        tickets.extend([
            {
                "id": 2,
                "board_slug": "pais",
                "created_at": "2026-07-08T09:00:00+03:00",
                "created_at_display": "08/07/2026 09:00",
                "creator": "Admin",
                "ticket_type": "שירות",
                "service_type": "מפעל הפיס",
                "domain": "",
                "priority": "Medium",
                "description": "",
                "solution": "",
                "status": "ממתין לתיאום",
                "assigned_to": "ניר",
                "details": {
                    "terminal_number": "6001",
                    "address": "Waiting address",
                    "customer_request": "R4",
                    "actions_taken": "",
                },
                "attachments": [],
                "updates": [],
            },
            {
                "id": 3,
                "board_slug": "pais",
                "created_at": "2026-07-08T10:00:00+03:00",
                "created_at_display": "08/07/2026 10:00",
                "creator": "Admin",
                "ticket_type": "שירות",
                "service_type": "מפעל הפיס",
                "domain": "",
                "priority": "Medium",
                "description": "",
                "solution": "",
                "status": "תואם",
                "assigned_to": "גולן",
                "details": {
                    "terminal_number": "6002",
                    "address": "Scheduled address",
                    "customer_request": "R5",
                    "actions_taken": "",
                    "coordinated_worker": "גולן",
                    "visit_date": "2026-07-09",
                    "visit_hour_from": "09:00",
                    "visit_hour_to": "10:00",
                },
                "attachments": [],
                "updates": [],
            },
        ])
        self.app_module.save_support_tickets(tickets)

        self.login("admin@nimbusip.com")
        response = self.client.get("/support-tickets-data?board=pais&queue=nastia")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual([ticket["id"] for ticket in payload["tickets"]], [2, 3])

    def test_pais_report_filters_by_status_and_date(self):
        tickets = self.app_module.load_support_tickets()
        tickets.extend([
            {
                "id": 2,
                "board_slug": "pais",
                "created_at": "2026-07-08T09:00:00+03:00",
                "created_at_display": "08/07/2026 09:00",
                "creator": "Admin",
                "ticket_type": "שירות",
                "service_type": "מפעל הפיס",
                "domain": "",
                "priority": "Medium",
                "description": "",
                "solution": "",
                "status": "בוצע",
                "assigned_to": "ניר",
                "details": {
                    "terminal_number": "2001",
                    "address": "A",
                    "customer_request": "R1",
                    "actions_taken": "A1",
                },
                "attachments": [],
                "updates": [],
            },
            {
                "id": 3,
                "board_slug": "pais",
                "created_at": "2026-07-01T09:00:00+03:00",
                "created_at_display": "01/07/2026 09:00",
                "creator": "Admin",
                "ticket_type": "שירות",
                "service_type": "מפעל הפיס",
                "domain": "",
                "priority": "Medium",
                "description": "",
                "solution": "",
                "status": "ממתין",
                "assigned_to": "גולן",
                "details": {
                    "terminal_number": "2002",
                    "address": "B",
                    "customer_request": "R2",
                    "actions_taken": "A2",
                },
                "attachments": [],
                "updates": [],
            },
        ])
        self.app_module.save_support_tickets(tickets)

        self.login("admin@nimbusip.com")
        response = self.client.get(
            "/pais-tickets-report-data?period=daily&status=בוצע&date_from=2026-07-08&date_to=2026-07-08"
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["summary"]["done"], 1)
        self.assertEqual(payload["summary"]["total"], 1)
        self.assertEqual(payload["leaderboard"][0]["user"], "ניר")
        self.assertEqual(payload["leaderboard"][0]["done"], 1)

    def test_pais_csv_export_contains_counter_and_total(self):
        self.app_module.israel_now = lambda: datetime(2026, 7, 15, 10, 0, tzinfo=ZoneInfo("Asia/Jerusalem"))
        tickets = self.app_module.load_support_tickets()
        tickets.append({
            "id": 2,
            "board_slug": "pais",
            "created_at": "2026-07-08T09:00:00+03:00",
            "created_at_display": "08/07/2026 09:00",
            "creator": "Admin",
            "ticket_type": "שירות",
            "service_type": "מפעל הפיס",
            "domain": "",
            "priority": "Medium",
            "description": "",
            "solution": "",
            "status": "ממתין לתאום",
            "assigned_to": "נסטיה",
            "details": {
                "terminal_number": "3001",
                "address": "C",
                "customer_request": "R3",
                "actions_taken": "A3",
            },
            "attachments": [],
            "updates": [],
        })
        self.app_module.save_support_tickets(tickets)

        self.login("admin@nimbusip.com")
        response = self.client.get("/pais-tickets-report-export?period=monthly&format=csv")

        self.assertEqual(response.status_code, 200)
        body = response.data.decode("utf-8-sig")
        self.assertIn("counter,terminal_number,address", body)
        self.assertIn("1,3001,C", body)
        self.assertIn("TOTAL,1,", body)

    def test_pais_pdf_export_downloads_attachment(self):
        self.app_module.israel_now = lambda: datetime(2026, 7, 15, 10, 0, tzinfo=ZoneInfo("Asia/Jerusalem"))
        tickets = self.app_module.load_support_tickets()
        tickets.append({
            "id": 2,
            "board_slug": "pais",
            "created_at": "2026-07-08T09:00:00+03:00",
            "created_at_display": "08/07/2026 09:00",
            "creator": "Admin",
            "ticket_type": "׳©׳™׳¨׳•׳×",
            "service_type": self.app_module.TICKET_BOARD_DEFAULTS["pais"]["name"],
            "domain": "",
            "priority": "Medium",
            "description": "",
            "solution": "",
            "status": "׳׳׳×׳™׳ ׳׳×׳׳•׳",
            "assigned_to": "׳ ׳¡׳˜׳™׳”",
            "details": {
                "terminal_number": "3001",
                "address": "C",
                "customer_request": "R3",
                "actions_taken": "A3",
            },
            "attachments": [],
            "updates": [],
        })
        self.app_module.save_support_tickets(tickets)

        self.login("admin@nimbusip.com")
        response = self.client.get("/pais-tickets-report-export?period=monthly&format=pdf")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "application/pdf")
        self.assertTrue(response.headers["Content-Disposition"].startswith("attachment;"))
        self.assertIn(".pdf", response.headers["Content-Disposition"])
        self.assertTrue(response.data.startswith(b"%PDF"))

    def test_pais_report_export_defaults_to_monthly_period(self):
        self.app_module.israel_now = lambda: datetime(2026, 7, 15, 10, 0, tzinfo=ZoneInfo("Asia/Jerusalem"))
        tickets = self.app_module.load_support_tickets()
        tickets.append({
            "id": 2,
            "board_slug": "pais",
            "created_at": "2026-07-08T09:00:00+03:00",
            "created_at_display": "08/07/2026 09:00",
            "creator": "Admin",
            "ticket_type": "׳©׳™׳¨׳•׳×",
            "service_type": "׳׳₪׳¢׳ ׳”׳₪׳™׳¡",
            "domain": "",
            "priority": "Medium",
            "description": "",
            "solution": "",
            "status": "׳׳׳×׳™׳ ׳׳×׳׳•׳",
            "assigned_to": "׳ ׳¡׳˜׳™׳”",
            "details": {
                "terminal_number": "3001",
                "address": "C",
                "customer_request": "R3",
                "actions_taken": "A3",
            },
            "attachments": [],
            "updates": [],
        })
        self.app_module.save_support_tickets(tickets)

        self.login("admin@nimbusip.com")
        response = self.client.get("/pais-tickets-report-export?format=csv")

        self.assertEqual(response.status_code, 200)
        self.assertIn("pais_tickets_monthly_", response.headers["Content-Disposition"])
        body = response.data.decode("utf-8-sig")
        self.assertIn("1,3001,C", body)

    def test_hot_csv_export_contains_call_number_and_customer_name(self):
        self.app_module.israel_now = lambda: datetime(2026, 7, 15, 10, 0, tzinfo=ZoneInfo("Asia/Jerusalem"))
        tickets = self.app_module.load_support_tickets()
        tickets.append({
            "id": 2,
            "board_slug": "hot-kiryot",
            "created_at": "2026-07-08T09:00:00+03:00",
            "created_at_display": "08/07/2026 09:00",
            "creator": "Admin",
            "ticket_type": "שירות",
            "service_type": self.app_module.TICKET_BOARD_DEFAULTS["hot-kiryot"]["name"],
            "domain": "",
            "priority": "Medium",
            "description": "",
            "solution": "",
            "status": "ממתין לתיאום",
            "assigned_to": "נסטיה",
            "details": {
                "call_number": "275749117",
                "customer_name": "חיים",
                "address": "נתניה",
            },
            "attachments": [],
            "updates": [],
        })
        self.app_module.save_support_tickets(tickets)

        self.login("admin@nimbusip.com")
        response = self.client.get("/pais-tickets-report-export?board=hot-kiryot&period=monthly&format=csv")

        self.assertEqual(response.status_code, 200)
        body = response.data.decode("utf-8-sig")
        self.assertIn("counter,call_number,customer_name", body)
        self.assertIn("1,275749117,חיים", body)
        self.assertIn("TOTAL,1,", body)

    def test_hot_pdf_export_downloads_attachment(self):
        self.app_module.israel_now = lambda: datetime(2026, 7, 15, 10, 0, tzinfo=ZoneInfo("Asia/Jerusalem"))
        tickets = self.app_module.load_support_tickets()
        tickets.append({
            "id": 2,
            "board_slug": "hot-kiryot",
            "created_at": "2026-07-08T09:00:00+03:00",
            "created_at_display": "08/07/2026 09:00",
            "creator": "Admin",
            "ticket_type": "שירות",
            "service_type": self.app_module.TICKET_BOARD_DEFAULTS["hot-kiryot"]["name"],
            "domain": "",
            "priority": "Medium",
            "description": "",
            "solution": "",
            "status": "ממתין לתיאום",
            "assigned_to": "נסטיה",
            "details": {
                "call_number": "275749117",
                "customer_name": "חיים",
                "address": "נתניה",
            },
            "attachments": [],
            "updates": [],
        })
        self.app_module.save_support_tickets(tickets)

        self.login("admin@nimbusip.com")
        response = self.client.get("/pais-tickets-report-export?board=hot-kiryot&period=monthly&format=pdf")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "application/pdf")
        self.assertTrue(response.headers["Content-Disposition"].startswith("attachment;"))
        self.assertIn(".pdf", response.headers["Content-Disposition"])
        self.assertTrue(response.data.startswith(b"%PDF"))

    def test_features_pdf_export_downloads_attachment(self):
        self.app_module.get_feature_report_counts = lambda month: {
            "month": month,
            "month_display": "07/2026",
            "services": [
                {"label": "SMS", "count": 3, "children": []},
                {"label": "מוקד", "count": 2, "children": [{"label": "משנה", "count": 1}]},
            ],
            "total": 5,
        }

        self.login("admin@nimbusip.com")
        response = self.client.get("/features-report-export?month=2026-07&format=pdf")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "application/pdf")
        self.assertTrue(response.headers["Content-Disposition"].startswith("attachment;"))
        self.assertIn("features-report-2026-07.pdf", response.headers["Content-Disposition"])
        self.assertTrue(response.data.startswith(b"%PDF"))

    def test_pdf_rtl_format_keeps_non_hebrew_text_order(self):
        formatted = self.app_module.format_rtl_pdf_text("2026-08-01 - 2026-08-31")
        self.assertEqual(formatted, "2026-08-01 - 2026-08-31")

    def test_pdf_font_prefers_bundled_hebrew_font(self):
        regular_font = self.app_module.get_pdf_font_name("regular", "hebrew")
        bold_font = self.app_module.get_pdf_font_name("bold", "hebrew")
        extra_bold_font = self.app_module.get_pdf_font_name("extra_bold", "hebrew")
        latin_bold_font = self.app_module.get_pdf_font_name("bold", "latin")
        self.assertEqual(regular_font, "AppPdfFontHebrewRegular")
        self.assertEqual(bold_font, "AppPdfFontHebrewBold")
        self.assertEqual(extra_bold_font, "AppPdfFontHebrewExtraBold")
        self.assertEqual(latin_bold_font, "Helvetica-Bold")

    def test_send_inforu_mail_returns_error_when_webhook_missing(self):
        self.app_module.TOKEN_INFORU = ""
        self.app_module.inforu_log_dir = lambda: self.tempdir.name
        self.app_module.inforu_log_path = lambda: os.path.join(self.tempdir.name, self.app_module.INFORU_LOG_FILENAME)
        self.login("admin@nimbusip.com")

        response = self.client.post("/send-inforu-mail", json={"dids": ["031234568"]})

        self.assertEqual(response.status_code, 500)
        payload = response.get_json()
        self.assertFalse(payload["ok"])
        self.assertIn("TOKEN_INFORU", payload["message"])

    def test_send_inforu_mail_returns_error_when_webhook_fails(self):
        self.app_module.TOKEN_INFORU = "https://hook.example"
        self.app_module.inforu_log_dir = lambda: self.tempdir.name
        self.app_module.inforu_log_path = lambda: os.path.join(self.tempdir.name, self.app_module.INFORU_LOG_FILENAME)
        self.login("admin@nimbusip.com")

        def failing_post(*args, **kwargs):
            raise RuntimeError("boom")

        self.app_module.requests.post = failing_post
        response = self.client.post("/send-inforu-mail", json={"dids": ["031234569"]})

        self.assertEqual(response.status_code, 502)
        payload = response.get_json()
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["message"], "boom")

    def test_inforu_log_path_uses_temp_directory_on_vercel(self):
        os.environ["VERCEL"] = "1"

        path = self.app_module.inforu_log_path()

        self.assertIn(tempfile.gettempdir(), path)
        self.assertTrue(path.endswith(self.app_module.INFORU_LOG_FILENAME))

    def test_pais_search_uses_terminal_number(self):
        tickets = self.app_module.load_support_tickets()
        tickets.append({
            "id": 2,
            "board_slug": "pais",
            "created_at": "2026-07-08T09:00:00+03:00",
            "created_at_display": "08/07/2026 09:00",
            "creator": "Admin",
            "ticket_type": "שירות",
            "service_type": "מפעל הפיס",
            "domain": "",
            "priority": "Medium",
            "description": "",
            "solution": "",
            "status": "ממתין",
            "assigned_to": "נסטיה",
            "details": {
                "terminal_number": "5555",
                "address": "Search address",
                "customer_request": "R3",
                "actions_taken": "",
            },
            "attachments": [],
            "updates": [],
        })
        self.app_module.save_support_tickets(tickets)

        self.login("admin@nimbusip.com")
        response = self.client.get("/support-tickets-data?board=pais&search=5555")
        payload = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(payload["tickets"]), 1)
        self.assertEqual(payload["tickets"][0]["details"]["terminal_number"], "5555")

    def test_pais_search_uses_address(self):
        tickets = self.app_module.load_support_tickets()
        tickets.append({
            "id": 2,
            "board_slug": "pais",
            "created_at": "2026-07-08T09:00:00+03:00",
            "created_at_display": "08/07/2026 09:00",
            "creator": "Admin",
            "ticket_type": "שירות",
            "service_type": "מפעל הפיס",
            "domain": "",
            "priority": "Medium",
            "description": "",
            "solution": "",
            "status": "ממתין",
            "assigned_to": "נסטיה",
            "details": {
                "terminal_number": "9999",
                "address": "נתניה שדרות אגם כנרת 6",
                "customer_request": "R10",
                "actions_taken": "",
            },
            "attachments": [],
            "updates": [],
        })
        self.app_module.save_support_tickets(tickets)

        self.login("admin@nimbusip.com")
        response = self.client.get("/support-tickets-data?board=pais&search=אגם כנרת")
        payload = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(payload["tickets"]), 1)
        self.assertEqual(payload["tickets"][0]["details"]["address"], "נתניה שדרות אגם כנרת 6")


    def test_asaf_is_in_worker_lists(self):
        self.assertIn("אסף", self.app_module.SUPPORT_USERS)
        self.assertIn("אסף", self.app_module.TECHNICIAN_SUPPORT_USERS)
        self.assertIn("מוסטפה.א", self.app_module.TECHNICIAN_SUPPORT_USERS)
        self.assertIn("מוסטפה.ח", self.app_module.TECHNICIAN_SUPPORT_USERS)

    def test_hot_search_uses_call_number_and_customer_name(self):
        tickets = self.app_module.load_support_tickets()
        tickets.append({
            "id": 2,
            "board_slug": "hot-kiryot",
            "created_at": "2026-07-08T09:00:00+03:00",
            "created_at_display": "08/07/2026 09:00",
            "creator": "Admin",
            "ticket_type": "שירות",
            "service_type": "הוט קריאות",
            "domain": "",
            "priority": "Medium",
            "description": "",
            "solution": "",
            "status": "ממתין",
            "assigned_to": "",
            "details": {
                "call_number": "275749117",
                "customer_name": "חיים",
                "address": "האופה 1, נתניה",
                "issue_summary": "PANCODE לא עובד",
            },
            "attachments": [],
            "updates": [],
        })
        self.app_module.save_support_tickets(tickets)

        self.login("admin@nimbusip.com")
        response = self.client.get("/support-tickets-data?board=hot-kiryot&search=275749117")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(len(payload["tickets"]), 1)
        self.assertEqual(payload["tickets"][0]["details"]["customer_name"], "חיים")

        response = self.client.get("/support-tickets-data?board=hot-kiryot&search=חיים")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(len(payload["tickets"]), 1)

    def test_normalize_allowed_pages_backfills_hot_ticket_access_for_existing_ticket_users(self):
        normalized = self.app_module.normalize_allowed_pages(["support_tickets", "pais_tickets", "nastia_tickets"])
        self.assertIn("hot_tickets", normalized)

    def test_limited_ticket_user_can_only_access_ticket_pages(self):
        response = self.login("nastya@nimbusip.com", "tygeydfuyw5t3g")

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].endswith("/support-tickets"))

        home_response = self.client.get("/home", follow_redirects=False)
        self.assertEqual(home_response.status_code, 302)
        self.assertTrue(home_response.headers["Location"].endswith("/support-tickets"))

        tickets_response = self.client.get("/support-tickets", follow_redirects=False)
        self.assertEqual(tickets_response.status_code, 200)

    def test_assigned_technician_login_redirects_to_tickets_menu_page(self):
        response = self.login("golan@nimbusip.com", "0503009456!")

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].endswith("/pais-tickets"))

        page_response = self.client.get("/pais-tickets", follow_redirects=False)
        self.assertEqual(page_response.status_code, 200)
        self.assertIn(b"tickets-menu", page_response.data)

    def test_assigned_technician_support_user_name_matches_worker(self):
        with self.app.test_request_context("/pais-tickets"):
            from flask import session

            session["logged_in"] = True
            session["username"] = "assafh@nimbusip.com"
            session["role"] = "assigned_technician"

            self.assertEqual(self.app_module.support_user_name(), "אסף")

    def test_assigned_technician_only_sees_own_coordination_tickets(self):
        tickets = self.app_module.load_support_tickets()
        tickets.extend([
            {
                "id": 2,
                "board_slug": "support",
                "created_at": "2026-07-08T08:50:00+03:00",
                "created_at_display": "08/07/2026 08:50",
                "creator": "Admin",
                "ticket_type": "שאלה",
                "service_type": "מרכזייה",
                "domain": "golan.example",
                "priority": "Medium",
                "description": "Assigned support ticket",
                "solution": "",
                "status": "Waiting",
                "assigned_to": "ניר",
                "details": {
                    "service_mode": "ביקור טכנאי בתשלום",
                    "business_name": "Nimbus Biz",
                    "service_contact": "גולן 0503009456",
                    "service_address": "Support road 1",
                    "coordinated_worker": "גולן",
                    "visit_date": "2026-07-10",
                    "visit_hour_from": "10:00",
                    "visit_hour_to": "11:00",
                    "failure_notes": "",
                },
                "attachments": [],
                "updates": [],
            },
            {
                "id": 3,
                "board_slug": "pais",
                "created_at": "2026-07-08T09:00:00+03:00",
                "created_at_display": "08/07/2026 09:00",
                "creator": "Admin",
                "ticket_type": "שירות",
                "service_type": "מפעל הפיס",
                "domain": "",
                "priority": "Medium",
                "description": "",
                "solution": "",
                "status": "ממתין לתאום",
                "assigned_to": "זוהרה",
                "details": {
                    "terminal_number": "9001",
                    "address": "Golan street 1",
                    "customer_request": "Need visit",
                    "actions_taken": "",
                    "coordinated_worker": "גולן",
                    "visit_date": "",
                    "visit_hour_from": "",
                    "visit_hour_to": "",
                    "failure_notes": "",
                },
                "attachments": [],
                "updates": [],
            },
            {
                "id": 4,
                "board_slug": "hot-kiryot",
                "created_at": "2026-07-08T09:10:00+03:00",
                "created_at_display": "08/07/2026 09:10",
                "creator": "Admin",
                "ticket_type": "שירות",
                "service_type": "הוט קריאות",
                "domain": "",
                "priority": "Medium",
                "description": "",
                "solution": "",
                "status": "תואם",
                "assigned_to": "זוהרה",
                "details": {
                    "call_number": "275749117",
                    "customer_name": "חיים",
                    "address": "האופה 1, נתניה",
                    "issue_summary": "PANCODE לא עובד",
                    "technician_actions": "בדיקות",
                    "coordinated_worker": "גולן",
                    "visit_date": "2026-07-09",
                    "visit_hour_from": "09:00",
                    "visit_hour_to": "10:00",
                    "failure_notes": "",
                },
                "attachments": [],
                "updates": [],
            },
            {
                "id": 5,
                "board_slug": "pais",
                "created_at": "2026-07-08T09:15:00+03:00",
                "created_at_display": "08/07/2026 09:15",
                "creator": "Admin",
                "ticket_type": "שירות",
                "service_type": "מפעל הפיס",
                "domain": "",
                "priority": "Medium",
                "description": "",
                "solution": "",
                "status": "ממתין לתאום",
                "assigned_to": "ניר",
                "details": {
                    "terminal_number": "9002",
                    "address": "Assaf street 2",
                    "customer_request": "Other visit",
                    "actions_taken": "",
                    "coordinated_worker": "אסף",
                    "visit_date": "",
                    "visit_hour_from": "",
                    "visit_hour_to": "",
                    "failure_notes": "",
                },
                "attachments": [],
                "updates": [],
            },
        ])
        self.app_module.save_support_tickets(tickets)

        self.login("golan@nimbusip.com", "0503009456!")

        support_response = self.client.get("/support-tickets-data?board=support")
        self.assertEqual(support_response.status_code, 200)
        support_payload = support_response.get_json()
        self.assertEqual(len(support_payload["tickets"]), 1)
        self.assertEqual(support_payload["tickets"][0]["details"]["coordinated_worker"], "גולן")

        pais_response = self.client.get("/support-tickets-data?board=pais")
        self.assertEqual(pais_response.status_code, 200)
        pais_payload = pais_response.get_json()
        self.assertEqual(len(pais_payload["tickets"]), 1)
        self.assertEqual(pais_payload["tickets"][0]["details"]["coordinated_worker"], "גולן")
        self.assertEqual(pais_payload["stats"]["all"], 1)

        hot_response = self.client.get("/support-tickets-data?board=hot-kiryot")
        self.assertEqual(hot_response.status_code, 200)
        hot_payload = hot_response.get_json()
        self.assertEqual(len(hot_payload["tickets"]), 1)
        self.assertEqual(hot_payload["tickets"][0]["details"]["coordinated_worker"], "גולן")
        self.assertEqual(hot_payload["stats"]["all"], 1)

    def test_assigned_technician_can_only_set_final_status_on_own_ticket(self):
        tickets = self.app_module.load_support_tickets()
        tickets.extend([
            {
                "id": 2,
                "board_slug": "hot-kiryot",
                "created_at": "2026-07-08T09:10:00+03:00",
                "created_at_display": "08/07/2026 09:10",
                "creator": "Admin",
                "ticket_type": "שירות",
                "service_type": "הוט קריאות",
                "domain": "",
                "priority": "Medium",
                "description": "",
                "solution": "",
                "status": "תואם",
                "assigned_to": "זוהרה",
                "details": {
                    "call_number": "275749117",
                    "customer_name": "חיים",
                    "address": "האופה 1, נתניה",
                    "issue_summary": "PANCODE לא עובד",
                    "technician_actions": "בדיקות",
                    "coordinated_worker": "גולן",
                    "visit_date": "2026-07-09",
                    "visit_hour_from": "09:00",
                    "visit_hour_to": "10:00",
                    "failure_notes": "",
                },
                "attachments": [],
                "updates": [],
            },
            {
                "id": 3,
                "board_slug": "pais",
                "created_at": "2026-07-08T09:15:00+03:00",
                "created_at_display": "08/07/2026 09:15",
                "creator": "Admin",
                "ticket_type": "שירות",
                "service_type": "מפעל הפיס",
                "domain": "",
                "priority": "Medium",
                "description": "",
                "solution": "",
                "status": "ממתין לתאום",
                "assigned_to": "ניר",
                "details": {
                    "terminal_number": "9002",
                    "address": "Assaf street 2",
                    "customer_request": "Other visit",
                    "actions_taken": "",
                    "coordinated_worker": "אסף",
                    "visit_date": "",
                    "visit_hour_from": "",
                    "visit_hour_to": "",
                    "failure_notes": "",
                },
                "attachments": [],
                "updates": [],
            },
        ])
        self.app_module.save_support_tickets(tickets)

        self.login("golan@nimbusip.com", "0503009456!")

        success_response = self.client.post(
            "/support-tickets-update",
            json={
                "ticket_id": 2,
                "status": "בוצע",
                "details": {
                    "failure_notes": "",
                },
            },
        )
        self.assertEqual(success_response.status_code, 200)
        self.assertEqual(success_response.get_json()["ticket"]["status"], "בוצע")

        invalid_status_response = self.client.post(
            "/support-tickets-update",
            json={
                "ticket_id": 2,
                "status": "תואם",
                "details": {
                    "failure_notes": "",
                },
            },
        )
        self.assertEqual(invalid_status_response.status_code, 403)

        foreign_ticket_response = self.client.post(
            "/support-tickets-update",
            json={
                "ticket_id": 3,
                "status": "נכשל",
                "details": {
                    "failure_notes": "No access",
                },
            },
        )
        self.assertEqual(foreign_ticket_response.status_code, 403)

    def test_assigned_technician_can_update_pais_actions_taken(self):
        tickets = self.app_module.load_support_tickets()
        tickets.append({
            "id": 2,
            "board_slug": "pais",
            "created_at": "2026-07-08T09:15:00+03:00",
            "created_at_display": "08/07/2026 09:15",
            "creator": "Admin",
            "ticket_type": "שירות",
            "service_type": "מפעל הפיס",
            "domain": "",
            "priority": "Medium",
            "description": "",
            "solution": "",
            "status": "ממתין לתיאום",
            "assigned_to": "גולן",
            "details": {
                "terminal_number": "9002",
                "address": "Assaf street 2",
                "customer_request": "Other visit",
                "actions_taken": "",
                "coordinated_worker": "גולן",
                "failure_notes": "",
            },
            "attachments": [],
            "updates": [],
        })
        self.app_module.save_support_tickets(tickets)

        self.login("golan@nimbusip.com", "0503009456!")
        response = self.client.post(
            "/support-tickets-update",
            json={
                "ticket_id": 2,
                "status": "בוצע",
                "details": {
                    "actions_taken": "בוצע ביקור, הוסבר ללקוח",
                    "failure_notes": "",
                },
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["ticket"]["details"]["actions_taken"], "בוצע ביקור, הוסבר ללקוח")

    def test_assigned_technician_status_change_on_pais_sends_nastia_email_with_status(self):
        tickets = self.app_module.load_support_tickets()
        tickets.append({
            "id": 2,
            "board_slug": "pais",
            "created_at": "2026-07-08T09:15:00+03:00",
            "created_at_display": "08/07/2026 09:15",
            "creator": "Admin",
            "ticket_type": "שירות",
            "service_type": "מפעל הפיס",
            "domain": "",
            "priority": "Medium",
            "description": "",
            "solution": "",
            "status": "תואם",
            "assigned_to": "גולן",
            "details": {
                "terminal_number": "9002",
                "address": "Assaf street 2",
                "customer_request": "Other visit",
                "actions_taken": "",
                "coordinated_worker": "גולן",
                "visit_date": "2026-07-09",
                "visit_hour_from": "09:00",
                "visit_hour_to": "10:00",
                "failure_notes": "",
            },
            "attachments": [],
            "updates": [],
        })
        self.app_module.save_support_tickets(tickets)
        captured = {}

        def fake_send_plain_email(to_address, subject, body, from_address=None, html_body=None, attachments=None):
            captured["to_address"] = to_address
            captured["subject"] = subject
            captured["body"] = body
            captured["html_body"] = html_body or ""

        self.app_module.send_plain_email = fake_send_plain_email
        self.login("golan@nimbusip.com", "0503009456!")
        response = self.client.post(
            "/support-tickets-update",
            json={
                "ticket_id": 2,
                "status": "בוצע",
                "details": {
                    "failure_notes": "",
                },
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["ticket"]["status"], "בוצע")
        self.assertTrue(payload["ticket"]["notification_attempted"])
        self.assertTrue(payload["ticket"]["notification_sent"])
        self.assertEqual(captured["to_address"], self.app_module.NASTIA_NOTIFICATION_EMAIL)
        self.assertIn("סטטוס: בוצע", captured["body"])
        self.assertIn("בוצע", captured["html_body"])

    def test_assigned_technician_cannot_create_but_can_upload_attachments(self):
        tickets = self.app_module.load_support_tickets()
        tickets.append({
            "id": 2,
            "board_slug": "hot-kiryot",
            "created_at": "2026-07-08T09:10:00+03:00",
            "created_at_display": "08/07/2026 09:10",
            "creator": "Admin",
            "ticket_type": "שירות",
            "service_type": "הוט קריאות",
            "domain": "",
            "priority": "Medium",
            "description": "",
            "solution": "",
            "status": "תואם",
            "assigned_to": "גולן",
            "details": {
                "call_number": "275749117",
                "customer_name": "חיים",
                "address": "האופה 1, נתניה",
                "issue_summary": "PANCODE לא עובד",
                "technician_actions": "בדיקות",
                "coordinated_worker": "גולן",
                "visit_date": "2026-07-09",
                "visit_hour_from": "09:00",
                "visit_hour_to": "10:00",
                "failure_notes": "",
            },
            "attachments": [],
            "updates": [],
        })
        self.app_module.save_support_tickets(tickets)

        self.login("golan@nimbusip.com", "0503009456!")

        create_response = self.client.post(
            "/support-tickets-create",
            data={
                "board_slug": "hot-kiryot",
                "call_number": "999999",
                "address": "Blocked 1",
                "customer_name": "Blocked",
                "issue_summary": "Blocked",
            },
        )
        self.assertEqual(create_response.status_code, 403)

        upload_response = self.client.post(
            "/support-tickets-attachments",
            data={
                "ticket_id": "2",
                "attachments": [(io.BytesIO(b"jpg"), "field.jpg")],
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(upload_response.status_code, 200)
        upload_payload = upload_response.get_json()
        self.assertTrue(upload_payload["ok"])
        self.assertEqual(len(upload_payload["ticket"]["attachments"]), 1)

    def test_assigned_technician_can_save_hot_field_report_pdf(self):
        tickets = self.app_module.load_support_tickets()
        tickets.append({
            "id": 2,
            "board_slug": "hot-kiryot",
            "created_at": "2026-07-08T09:10:00+03:00",
            "created_at_display": "08/07/2026 09:10",
            "creator": "Admin",
            "ticket_type": "שירות",
            "service_type": "הוט קריאות",
            "domain": "",
            "priority": "Medium",
            "description": "",
            "solution": "",
            "status": "תואם",
            "assigned_to": "גולן",
            "details": {
                "call_number": "275749117",
                "customer_name": "חיים",
                "address": "האופה 1, נתניה",
                "on_site_contact": "חיים 0524443593",
                "issue_summary": "PANCODE לא עובד",
                "technician_actions": "בדיקות",
                "coordinated_worker": "גולן",
                "visit_date": "2026-07-09",
                "visit_hour_from": "09:00",
                "visit_hour_to": "10:00",
                "failure_notes": "",
            },
            "attachments": [],
            "updates": [],
        })
        self.app_module.save_support_tickets(tickets)
        self.app_module.build_hot_field_report_pdf = lambda ticket, report, technician_signature, customer_signature: b"%PDF-1.4 fake"
        captured = {}

        def fake_send_plain_email(to_address, subject, body, from_address=None, html_body=None, attachments=None):
            captured["to_address"] = to_address
            captured["subject"] = subject
            captured["attachments"] = attachments or []

        self.app_module.send_plain_email = fake_send_plain_email
        self.login("golan@nimbusip.com", "0503009456!")

        response = self.client.post(
            "/support-tickets-field-report",
            data={
                "payload": json.dumps({
                    "ticket_id": 2,
                    "nimbus_customer_name": "חיים",
                    "contact_first_name": "חיים",
                    "contact_last_name": "כהן",
                    "role": "מנהל",
                    "installation_address": "האופה 1, נתניה",
                    "phone": "0524443593",
                    "customer_notes": "בדיקה מול לקוח",
                    "additional_notes": "הותקן בהצלחה",
                    "installation_date": "10/09/2026",
                    "technician_name": "גולן",
                    "line_items": [
                        {"item_name": "פאנל אינטרקום", "quantity": "1", "notes": "הותקן"},
                    ],
                    "technician_signature_data_url": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4////fwAJ+wP9KobjigAAAABJRU5ErkJggg==",
                    "customer_signature_data_url": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4////fwAJ+wP9KobjigAAAABJRU5ErkJggg==",
                }, ensure_ascii=False),
                "area_photos": [(io.BytesIO(b"jpg"), "field.jpg")],
            },
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["ok"])
        self.assertTrue(payload["ticket"]["field_report_sent"])
        self.assertEqual(payload["ticket"]["details"]["field_report"]["contact_first_name"], "חיים")
        self.assertEqual(payload["ticket"]["details"]["field_report"]["technician_name"], "גולן")
        self.assertEqual(len(payload["ticket"]["details"]["field_report"]["area_photo_attachments"]), 1)
        self.assertEqual(len(payload["ticket"]["attachments"]), 2)
        self.assertTrue(any(str(item["original_name"]).endswith(".pdf") for item in payload["ticket"]["attachments"]))
        self.assertEqual(captured["to_address"], self.app_module.HOT_FIELD_REPORT_CUSTOMER_EMAIL)
        self.assertEqual(captured["attachments"][0]["subtype"], "pdf")

    def test_assigned_technician_can_save_hot_field_report_without_customer_signature(self):
        tickets = self.app_module.load_support_tickets()
        tickets.append({
            "id": 2,
            "board_slug": "hot-kiryot",
            "created_at": "2026-07-08T09:10:00+03:00",
            "created_at_display": "08/07/2026 09:10",
            "creator": "Admin",
            "ticket_type": "שירות",
            "service_type": "הוט קריות",
            "domain": "",
            "priority": "Medium",
            "description": "",
            "solution": "",
            "status": "תואם",
            "assigned_to": "גולן",
            "details": {
                "call_number": "275749117",
                "customer_name": "חיים",
                "address": "האופה 1, נתניה",
                "on_site_contact": "חיים 0524443593",
                "issue_summary": "PANCODE לא עובד",
                "technician_actions": "בדיקות",
                "coordinated_worker": "גולן",
                "visit_date": "2026-07-09",
                "visit_hour_from": "09:00",
                "visit_hour_to": "10:00",
                "failure_notes": "",
            },
            "attachments": [],
            "updates": [],
        })
        self.app_module.save_support_tickets(tickets)
        self.app_module.build_hot_field_report_pdf = lambda ticket, report, technician_signature, customer_signature: b"%PDF-1.4 fake"
        sent_messages = []
        self.app_module.send_plain_email = lambda *args, **kwargs: sent_messages.append((args, kwargs))
        self.login("golan@nimbusip.com", "0503009456!")

        response = self.client.post(
            "/support-tickets-field-report",
            json={
                "ticket_id": 2,
                "nimbus_customer_name": "חיים",
                "contact_first_name": "חיים",
                "installation_address": "האופה 1, נתניה",
                "phone": "0524443593",
                "technician_name": "גולן",
                "technician_signature_data_url": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4////fwAJ+wP9KobjigAAAABJRU5ErkJggg==",
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["ticket"]["details"]["field_report"]["customer_signature_data_url"], "")
        self.assertEqual(len(sent_messages), 1)

    def test_assigned_technician_can_save_pais_field_report_without_customer_signature(self):
        tickets = self.app_module.load_support_tickets()
        tickets.append({
            "id": 2,
            "board_slug": "pais",
            "created_at": "2026-07-08T09:10:00+03:00",
            "created_at_display": "08/07/2026 09:10",
            "creator": "Admin",
            "ticket_type": "שירות",
            "service_type": "מפעל הפיס",
            "domain": "",
            "priority": "Medium",
            "description": "",
            "solution": "",
            "status": "תואם",
            "assigned_to": "גולן",
            "details": {
                "call_number": "PAIS-22",
                "customer_name": "לקוח פיס",
                "address": "רחוב 1",
                "on_site_contact": "לקוח פיס 0501234567",
                "customer_request": "נדרש ביקור",
                "actions_taken": "",
                "coordinated_worker": "גולן",
                "visit_date": "2026-07-09",
                "visit_hour_from": "09:00",
                "visit_hour_to": "10:00",
                "failure_notes": "",
            },
            "attachments": [],
            "updates": [],
        })
        self.app_module.save_support_tickets(tickets)
        self.app_module.build_hot_field_report_pdf = lambda ticket, report, technician_signature, customer_signature: b"%PDF-1.4 fake"
        self.login("golan@nimbusip.com", "0503009456!")

        response = self.client.post(
            "/support-tickets-field-report",
            json={
                "ticket_id": 2,
                "nimbus_customer_name": "לקוח פיס",
                "contact_first_name": "לקוח",
                "installation_address": "רחוב 1",
                "phone": "0501234567",
                "technician_name": "גולן",
                "technician_signature_data_url": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4////fwAJ+wP9KobjigAAAABJRU5ErkJggg==",
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["ticket"]["details"]["field_report"]["contact_first_name"], "לקוח")
        self.assertEqual(payload["ticket"]["details"]["field_report"]["customer_signature_data_url"], "")
        self.assertTrue(any(str(item["original_name"]).endswith(".pdf") for item in payload["ticket"]["attachments"]))

    def test_assigned_technician_field_report_requires_hot_ticket(self):
        tickets = self.app_module.load_support_tickets()
        tickets.append({
            "id": 2,
            "board_slug": "support",
            "created_at": "2026-07-08T09:10:00+03:00",
            "created_at_display": "08/07/2026 09:10",
            "creator": "Admin",
            "ticket_type": "תקלה",
            "service_type": "מצלמות",
            "domain": "",
            "priority": "Medium",
            "description": "Need visit",
            "solution": "",
            "status": "תואם",
            "assigned_to": "ניר",
            "details": {
                "coordinated_worker": "גולן",
                "visit_date": "2026-07-09",
                "visit_hour_from": "09:00",
                "visit_hour_to": "10:00",
                "failure_notes": "",
            },
            "attachments": [],
            "updates": [],
        })
        self.app_module.save_support_tickets(tickets)
        self.login("golan@nimbusip.com", "0503009456!")

        response = self.client.post(
            "/support-tickets-field-report",
            json={
                "ticket_id": 2,
                "nimbus_customer_name": "לקוח",
                "contact_first_name": "לקוח",
                "installation_address": "רחוב 1",
                "phone": "0501234567",
                "technician_name": "גולן",
                "technician_signature_data_url": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4////fwAJ+wP9KobjigAAAABJRU5ErkJggg==",
                "customer_signature_data_url": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4////fwAJ+wP9KobjigAAAABJRU5ErkJggg==",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("הוט קריאות", response.get_json()["message"])

    def test_assigned_technician_failed_status_requires_reason(self):
        tickets = self.app_module.load_support_tickets()
        tickets.append({
            "id": 2,
            "board_slug": "hot-kiryot",
            "created_at": "2026-07-08T09:10:00+03:00",
            "created_at_display": "08/07/2026 09:10",
            "creator": "Admin",
            "ticket_type": "שירות",
            "service_type": "הוט קריאות",
            "domain": "",
            "priority": "Medium",
            "description": "",
            "solution": "",
            "status": "תואם",
            "assigned_to": "זוהרה",
            "details": {
                "call_number": "275749117",
                "customer_name": "חיים",
                "address": "האופה 1, נתניה",
                "issue_summary": "PANCODE לא עובד",
                "technician_actions": "בדיקות",
                "coordinated_worker": "גולן",
                "visit_date": "2026-07-09",
                "visit_hour_from": "09:00",
                "visit_hour_to": "10:00",
                "failure_notes": "",
            },
            "attachments": [],
            "updates": [],
        })
        self.app_module.save_support_tickets(tickets)

        self.login("golan@nimbusip.com", "0503009456!")
        response = self.client.post(
            "/support-tickets-update",
            json={
                "ticket_id": 2,
                "status": "נכשל",
                "details": {
                    "failure_notes": "",
                },
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("סיבת כשל", response.get_json()["message"])

    def test_can_create_support_ticket_with_service_mode_details(self):
        self.login("admin@nimbusip.com")
        response = self.client.post(
            "/support-tickets-create",
            data={
                "board_slug": "support",
                "ticket_type": "תקלה",
                "service_type": "מרכזייה",
                "domain": "biz.example",
                "priority": "Medium",
                "assigned_to": "ניר",
                "description": "Need Nimbus technician",
                "solution": "",
                "service_mode": "ביקור טכנאי בתשלום",
                "business_name": "עסק בדיקה",
                "service_contact": "דני 0501234567",
                "service_address": "רחוב השלום 7",
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["ticket"]["board_slug"], "support")
        self.assertEqual(payload["ticket"]["status"], "ממתין")
        self.assertEqual(payload["ticket"]["details"]["service_mode"], "ביקור טכנאי בתשלום")
        self.assertEqual(payload["ticket"]["details"]["business_name"], "עסק בדיקה")

    def test_support_ticket_pending_coordination_appears_in_nastya_queue(self):
        tickets = self.app_module.load_support_tickets()
        tickets.append({
            "id": 2,
            "board_slug": "support",
            "created_at": "2026-07-08T09:00:00+03:00",
            "created_at_display": "08/07/2026 09:00",
            "creator": "Admin",
            "ticket_type": "שירות",
            "service_type": "מרכזייה",
            "domain": "support.example",
            "priority": "Medium",
            "description": "Nimbus coordination",
            "solution": "",
            "status": "ממתין לתיאום",
            "assigned_to": "ניר",
            "details": {
                "service_mode": "ביקור ללא תשלום",
                "business_name": "Nimbus Queue",
                "service_contact": "Dana",
                "service_address": "Queue road 3",
                "coordinated_worker": "",
                "visit_date": "",
                "visit_hour_from": "",
                "visit_hour_to": "",
                "failure_notes": "",
            },
            "attachments": [],
            "updates": [],
        })
        self.app_module.save_support_tickets(tickets)

        self.login("nastya@nimbusip.com", "tygeydfuyw5t3g")
        response = self.client.get("/support-tickets-data?board=support&queue=nastia")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(len(payload["tickets"]), 1)
        self.assertEqual(payload["tickets"][0]["board_slug"], "support")

    def test_nastya_marking_support_ticket_as_shipping_sends_racheli_email(self):
        tickets = self.app_module.load_support_tickets()
        tickets.append({
            "id": 2,
            "board_slug": "support",
            "created_at": "2026-07-08T09:00:00+03:00",
            "created_at_display": "08/07/2026 09:00",
            "creator": "Admin",
            "ticket_type": "שירות",
            "service_type": "מרכזייה",
            "domain": "support.example",
            "priority": "Medium",
            "description": "Nimbus shipping",
            "solution": "",
            "status": "ממתין לתיאום",
            "assigned_to": "ניר",
            "details": {
                "service_mode": "ביקור ללא תשלום",
                "business_name": "Ship Biz",
                "service_contact": "Dana 0501111111",
                "service_address": "Ship road 4",
                "coordinated_worker": "",
                "visit_date": "",
                "visit_hour_from": "",
                "visit_hour_to": "",
                "failure_notes": "",
            },
            "attachments": [],
            "updates": [],
        })
        self.app_module.save_support_tickets(tickets)

        captured = {}

        def fake_send_plain_email(to_address, subject, body, from_address=None, html_body=None, attachments=None):
            captured["to_address"] = to_address
            captured["subject"] = subject
            captured["body"] = body
            captured["html_body"] = html_body or ""

        self.app_module.send_plain_email = fake_send_plain_email
        self.login("nastya@nimbusip.com", "tygeydfuyw5t3g")
        response = self.client.post(
            "/support-tickets-update",
            json={
                "ticket_id": 2,
                "source_page_mode": "nastia",
                "source_ticket_queue": "nastia",
                "details": {
                    "service_mode": "משלוח",
                    "business_name": "Ship Biz",
                    "service_contact": "Dana 0501111111",
                    "service_address": "Ship road 4",
                    "failure_notes": "",
                },
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["ticket"]["racheli_notification_attempted"])
        self.assertTrue(payload["ticket"]["racheli_notification_sent"])
        self.assertEqual(captured["to_address"], self.app_module.RACHELI_NOTIFICATION_EMAIL)
        self.assertIn("#0002", captured["subject"])
        self.assertIn("משלוח", captured["subject"])
        self.assertIn("Ship Biz", captured["html_body"])

    def test_support_board_report_data_uses_board_parameter(self):
        tickets = self.app_module.load_support_tickets()
        tickets.append({
            "id": 2,
            "board_slug": "support",
            "created_at": "2026-07-08T09:00:00+03:00",
            "created_at_display": "08/07/2026 09:00",
            "creator": "Admin",
            "ticket_type": "שירות",
            "service_type": "מרכזייה",
            "domain": "support.example",
            "priority": "Medium",
            "description": "Nimbus report",
            "solution": "",
            "status": "בוצע",
            "assigned_to": "ניר",
            "details": {
                "service_mode": "ביקור טכנאי בתשלום",
                "business_name": "Report Biz",
                "service_contact": "Dana",
                "service_address": "Report road 6",
                "coordinated_worker": "אסף",
                "visit_date": "2026-07-08",
                "visit_hour_from": "09:00",
                "visit_hour_to": "10:00",
                "failure_notes": "",
            },
            "attachments": [],
            "updates": [],
        })
        self.app_module.save_support_tickets(tickets)

        self.login("admin@nimbusip.com")
        response = self.client.get("/pais-tickets-report-data?board=support&period=monthly&date_from=2026-07-01&date_to=2026-07-31")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["board"]["slug"], "support")
        self.assertEqual(payload["summary"]["total"], 1)

    def test_slot_conflict_is_rejected(self):
        tickets = self.app_module.load_support_tickets()
        tickets.extend([
            {
                "id": 2,
                "board_slug": "pais",
                "created_at": "2026-07-08T09:00:00+03:00",
                "created_at_display": "08/07/2026 09:00",
                "creator": "Admin",
                "ticket_type": "שירות",
                "service_type": "מפעל הפיס",
                "domain": "",
                "priority": "Medium",
                "description": "",
                "solution": "",
                "status": "ממתין לתאום",
                "assigned_to": "ניר",
                "details": {
                    "terminal_number": "7001",
                    "address": "Coord 1",
                    "customer_request": "R6",
                    "actions_taken": "",
                    "coordinated_worker": "אסף",
                    "visit_date": "2026-07-08",
                    "visit_hour_from": "09:00",
                    "visit_hour_to": "10:00",
                },
                "attachments": [],
                "updates": [],
            },
            {
                "id": 3,
                "board_slug": "pais",
                "created_at": "2026-07-08T09:30:00+03:00",
                "created_at_display": "08/07/2026 09:30",
                "creator": "Admin",
                "ticket_type": "שירות",
                "service_type": "מפעל הפיס",
                "domain": "",
                "priority": "Medium",
                "description": "",
                "solution": "",
                "status": "ממתין לתאום",
                "assigned_to": "גולן",
                "details": {
                    "terminal_number": "7002",
                    "address": "Coord 2",
                    "customer_request": "R7",
                    "actions_taken": "",
                    "coordinated_worker": "",
                    "visit_date": "",
                    "visit_hour_from": "",
                    "visit_hour_to": "",
                },
                "attachments": [],
                "updates": [],
            },
        ])
        self.app_module.save_support_tickets(tickets)

        self.login("admin@nimbusip.com")
        response = self.client.post(
            "/support-tickets-update",
            json={
                "ticket_id": 3,
                "status": "ממתין לתאום",
                "details": {
                    "coordinated_worker": "אסף",
                    "visit_date": "2026-07-08",
                    "visit_hour_from": "09:00",
                    "visit_hour_to": "10:00",
                },
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("אסף", response.get_json()["message"])

    def test_nastya_can_coordinate_and_ticket_becomes_coordinated(self):
        tickets = self.app_module.load_support_tickets()
        tickets.append({
            "id": 2,
            "board_slug": "pais",
            "created_at": "2026-07-08T09:00:00+03:00",
            "created_at_display": "08/07/2026 09:00",
            "creator": "Admin",
            "ticket_type": "שירות",
            "service_type": "מפעל הפיס",
            "domain": "",
            "priority": "Medium",
            "description": "",
            "solution": "",
            "status": "ממתין לתאום",
            "assigned_to": "ניר",
            "details": {
                "terminal_number": "8001",
                "address": "Coordinate me",
                "customer_request": "R8",
                "actions_taken": "",
                "coordinated_worker": "",
                "visit_date": "",
                "visit_hour_from": "",
                "visit_hour_to": "",
            },
            "attachments": [],
            "updates": [],
        })
        self.app_module.save_support_tickets(tickets)

        self.login("nastya@nimbusip.com", "tygeydfuyw5t3g")
        response = self.client.post(
            "/support-tickets-update",
            json={
                "ticket_id": 2,
                "details": {
                    "coordinated_worker": "אסף",
                    "visit_date": "2026-07-09",
                    "visit_hour_from": "09:00",
                    "visit_hour_to": "10:00",
                },
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["ticket"]["status"], "תואם")
        self.assertEqual(payload["ticket"]["details"]["coordinated_worker"], "אסף")
        self.assertEqual(payload["ticket"]["details"]["visit_date"], "2026-07-09")
        self.assertEqual(payload["ticket"]["details"]["visit_hour_from"], "09:00")
        self.assertEqual(payload["ticket"]["details"]["visit_hour_to"], "10:00")

    def test_nastya_can_complete_a_coordinated_ticket(self):
        tickets = self.app_module.load_support_tickets()
        tickets.append({
            "id": 2,
            "board_slug": "pais",
            "created_at": "2026-07-08T09:00:00+03:00",
            "created_at_display": "08/07/2026 09:00",
            "creator": "Admin",
            "ticket_type": "שירות",
            "service_type": "מפעל הפיס",
            "domain": "",
            "priority": "Medium",
            "description": "",
            "solution": "",
            "status": "תואם",
            "assigned_to": "ניר",
            "details": {
                "terminal_number": "8002",
                "address": "Complete me",
                "customer_request": "R9",
                "actions_taken": "",
                "coordinated_worker": "אסף",
                "visit_date": "2026-07-09",
                "visit_hour_from": "09:00",
                "visit_hour_to": "10:00",
            },
            "attachments": [],
            "updates": [],
        })
        self.app_module.save_support_tickets(tickets)

        self.login("nastya@nimbusip.com", "tygeydfuyw5t3g")
        response = self.client.post(
            "/support-tickets-update",
            json={
                "ticket_id": 2,
                "status": "בוצע",
                "details": {
                    "coordinated_worker": "אסף",
                    "visit_date": "2026-07-09",
                    "visit_hour_from": "09:00",
                    "visit_hour_to": "10:00",
                },
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["ticket"]["status"], "בוצע")
        self.assertEqual(payload["ticket"]["details"]["coordinated_worker"], "אסף")

    def test_nastya_can_fail_a_waiting_coordination_ticket(self):
        tickets = self.app_module.load_support_tickets()
        tickets.append({
            "id": 2,
            "board_slug": "pais",
            "created_at": "2026-07-08T09:00:00+03:00",
            "created_at_display": "08/07/2026 09:00",
            "creator": "Admin",
            "ticket_type": "שירות",
            "service_type": "מפעל הפיס",
            "domain": "",
            "priority": "Medium",
            "description": "",
            "solution": "",
            "status": "ממתין לתאום",
            "assigned_to": "ניר",
            "details": {
                "terminal_number": "8003",
                "address": "Fail me",
                "customer_request": "R11",
                "actions_taken": "",
            },
            "attachments": [],
            "updates": [],
        })
        self.app_module.save_support_tickets(tickets)

        self.login("nastya@nimbusip.com", "tygeydfuyw5t3g")
        response = self.client.post(
            "/support-tickets-update",
            json={
                "ticket_id": 2,
                "status": "נכשל",
                "details": {
                    "failure_notes": "לא הצליח",
                },
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["ticket"]["status"], "נכשל")
        self.assertEqual(payload["ticket"]["details"]["failure_notes"], "לא הצליח")

    def test_nastya_coordination_save_sends_waiting_alert_then_full_email_after_worker_and_visit_are_set(self):
        tickets = self.app_module.load_support_tickets()
        tickets.append({
            "id": 2,
            "board_slug": "pais",
            "created_at": "2026-07-08T09:00:00+03:00",
            "created_at_display": "08/07/2026 09:00",
            "creator": "Admin",
            "ticket_type": "׳©׳™׳¨׳•׳×",
            "service_type": "׳׳₪׳¢׳ ׳”׳₪׳™׳¡",
            "domain": "",
            "priority": "Medium",
            "description": "",
            "solution": "",
            "status": self.app_module.PAIS_STATUSES[0],
            "assigned_to": "׳ ׳™׳¨",
            "details": {
                "terminal_number": "9988",
                "address": "Email street 4",
                "customer_request": "׳׳§׳•׳— ׳׳‘׳§׳© ׳×׳™׳׳•׳",
                "actions_taken": "",
            },
            "attachments": [],
            "updates": [],
        })
        self.app_module.save_support_tickets(tickets)
        sent_tickets = []
        waiting_alerts = []
        self.app_module.send_nastia_ticket_email = lambda ticket: sent_tickets.append(ticket)
        self.app_module.send_nastia_waiting_alert_email = lambda ticket: waiting_alerts.append(ticket)

        self.login("admin@nimbusip.com")
        response = self.client.post(
            "/support-tickets-update",
            json={
                "ticket_id": 2,
                "status": self.app_module.PAIS_STATUSES[1],
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(waiting_alerts), 1)
        self.assertEqual(len(sent_tickets), 0)

        self.client.get("/logout")
        self.login("nastya@nimbusip.com", "tygeydfuyw5t3g")
        response = self.client.post(
            "/support-tickets-update",
            json={
                "ticket_id": 2,
                "details": {
                    "actions_taken": "",
                    "coordinated_worker": "אסף",
                    "visit_date": "2026-07-09",
                    "visit_hour_from": "09:00",
                    "visit_hour_to": "10:00",
                    "failure_notes": "",
                },
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["ticket"]["status"], "תואם")
        self.assertEqual(len(sent_tickets), 1)
        self.assertEqual(sent_tickets[0]["details"]["coordinated_worker"], "אסף")
        self.assertEqual(sent_tickets[0]["details"]["visit_date"], "2026-07-09")

    def test_admin_coordination_save_without_flag_does_not_send_email(self):
        tickets = self.app_module.load_support_tickets()
        tickets.append({
            "id": 2,
            "board_slug": "pais",
            "created_at": "2026-07-08T09:00:00+03:00",
            "created_at_display": "08/07/2026 09:00",
            "creator": "Admin",
            "ticket_type": "שירות",
            "service_type": "מפעל הפיס",
            "domain": "",
            "priority": "Medium",
            "description": "",
            "solution": "",
            "status": self.app_module.PAIS_STATUSES[1],
            "assigned_to": "ניר",
            "details": {
                "terminal_number": "9988",
                "address": "Email street 4",
                "customer_request": "לקוח מבקש תיאום",
                "actions_taken": "",
                "coordinated_worker": "",
                "visit_date": "",
                "visit_hour_from": "",
                "visit_hour_to": "",
                "failure_notes": "",
            },
            "attachments": [],
            "updates": [],
        })
        self.app_module.save_support_tickets(tickets)
        sent_tickets = []
        self.app_module.send_nastia_ticket_email = lambda ticket: sent_tickets.append(ticket)

        self.login("admin@nimbusip.com")
        response = self.client.post(
            "/support-tickets-update",
            json={
                "ticket_id": 2,
                "details": {
                    "actions_taken": "",
                    "coordinated_worker": "אסף",
                    "visit_date": "2026-07-09",
                    "visit_hour_from": "09:00",
                    "visit_hour_to": "10:00",
                    "failure_notes": "",
                },
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["ticket"]["status"], "תואם")
        self.assertEqual(len(sent_tickets), 0)

    def test_admin_coordination_save_from_nastya_queue_sends_email_without_flag(self):
        tickets = self.app_module.load_support_tickets()
        tickets.append({
            "id": 2,
            "board_slug": "pais",
            "created_at": "2026-07-08T09:00:00+03:00",
            "created_at_display": "08/07/2026 09:00",
            "creator": "Admin",
            "ticket_type": "שירות",
            "service_type": "מפעל הפיס",
            "domain": "",
            "priority": "Medium",
            "description": "",
            "solution": "",
            "status": self.app_module.PAIS_STATUSES[1],
            "assigned_to": "ניר",
            "details": {
                "terminal_number": "9988",
                "address": "Email street 4",
                "customer_request": "לקוח מבקש תיאום",
                "actions_taken": "",
                "coordinated_worker": "",
                "visit_date": "",
                "visit_hour_from": "",
                "visit_hour_to": "",
                "failure_notes": "",
            },
            "attachments": [],
            "updates": [],
        })
        self.app_module.save_support_tickets(tickets)
        sent_tickets = []
        self.app_module.send_nastia_ticket_email = lambda ticket: sent_tickets.append(ticket)

        self.login("admin@nimbusip.com")
        response = self.client.post(
            "/support-tickets-update",
            json={
                "ticket_id": 2,
                "source_page_mode": "nastia",
                "source_ticket_queue": "nastia",
                "details": {
                    "actions_taken": "",
                    "coordinated_worker": "אסף",
                    "visit_date": "2026-07-09",
                    "visit_hour_from": "09:00",
                    "visit_hour_to": "10:00",
                    "failure_notes": "",
                },
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["ticket"]["status"], "תואם")
        self.assertTrue(payload["ticket"]["notification_attempted"])
        self.assertTrue(payload["ticket"]["notification_sent"])
        self.assertEqual(len(sent_tickets), 1)

    def test_send_nastia_ticket_email_uses_configured_sender_full_details_and_subject_for_ticket_0043(self):
        captured = {}
        self.app_module.PAIS_NOTIFICATION_FROM = ""
        self.app_module.SMTP_FROM = "nimbuskonan@gmail.com"
        self.app_module.SMTP_USERNAME = "nimbuskonan@gmail.com"

        def fake_send_plain_email(to_address, subject, body, from_address=None, html_body=None, attachments=None):
            captured["to_address"] = to_address
            captured["subject"] = subject
            captured["body"] = body
            captured["from_address"] = from_address
            captured["html_body"] = html_body or ""
            captured["attachments"] = attachments or []

        self.app_module.send_plain_email = fake_send_plain_email

        self.app_module.send_nastia_ticket_email({
            "id": 43,
            "service_type": "מפעל הפיס",
            "created_at_display": "08/07/2026 09:00",
            "creator": "Admin",
            "status": "ממתין לתאום",
            "assigned_to": "נסטיה",
            "details": {
                "terminal_number": "9988",
                "address": "Email street 4",
                "static_ip": "1.2.3.4",
                "altura": "ALT-9",
                "look_back": "Enabled",
                "contact_name": "Dana",
                "contact_phone": "0501234567",
                "customer_request": "לקוח מבקש תיאום",
                "actions_taken": "בוצע איפוס",
                "coordinated_worker": "אסף",
                "visit_date": "2026-07-09",
                "visit_hour_from": "09:00",
                "visit_hour_to": "10:00",
                "failure_notes": "",
            },
        })

        self.assertEqual(captured["to_address"], self.app_module.NASTIA_NOTIFICATION_EMAIL)
        self.assertEqual(captured["from_address"], "nimbuskonan@gmail.com")
        self.assertEqual(captured["subject"], "קריאת שירות מפעל הפיס מס' קריאה : #0043")
        self.assertIn("מספר קריאה: #0043", captured["body"])
        self.assertIn("סטטוס: ממתין לתאום", captured["body"])
        self.assertIn("מספר מסוף: 9988", captured["body"])
        self.assertIn("כתובת: Email street 4", captured["body"])
        self.assertIn("כתובת IP סטטית: 1.2.3.4", captured["body"])
        self.assertIn("פניית לקוח: לקוח מבקש תיאום", captured["body"])
        self.assertIn("טכנאי מתואם: אסף", captured["body"])
        self.assertIn("שעת ביקור עד: 10:00", captured["body"])
        self.assertIn("הוספה ליומן Google: https://calendar.google.com/calendar/render?", captured["body"])
        self.assertIn("<html", captured["html_body"])
        self.assertIn("הוסף ליומן Google", captured["html_body"])
        self.assertIn("https://calendar.google.com/calendar/render?", captured["html_body"])
        self.assertIn("Email street 4", captured["html_body"])
        self.assertIn("add=assafh%40nimbusip.com", captured["body"])
        self.assertIn("add=assafh%40nimbusip.com", captured["html_body"])
        self.assertEqual(captured["attachments"], [])

    def test_send_nastia_waiting_alert_email_includes_terminal_and_address(self):
        captured = {}
        self.app_module.PAIS_NOTIFICATION_FROM = ""
        self.app_module.SMTP_FROM = "nimbuskonan@gmail.com"
        self.app_module.SMTP_USERNAME = "nimbuskonan@gmail.com"

        def fake_send_plain_email(to_address, subject, body, from_address=None, html_body=None, attachments=None):
            captured["to_address"] = to_address
            captured["subject"] = subject
            captured["body"] = body
            captured["from_address"] = from_address
            captured["html_body"] = html_body or ""
            captured["attachments"] = attachments or []

        self.app_module.send_plain_email = fake_send_plain_email

        self.app_module.send_nastia_waiting_alert_email({
            "id": 44,
            "board_slug": "pais",
            "service_type": "מפעל הפיס",
            "status": "ממתין לתיאום",
            "details": {
                "terminal_number": "7788",
                "address": "Alert street 7",
            },
        })

        self.assertEqual(captured["to_address"], self.app_module.NASTIA_NOTIFICATION_EMAIL)
        self.assertEqual(captured["from_address"], "nimbuskonan@gmail.com")
        self.assertIn("#0044", captured["subject"])
        self.assertIn("ממתין לתיאום", captured["subject"])
        self.assertIn("סטטוס: ממתין לתיאום", captured["body"])
        self.assertIn("מספר מסוף: 7788", captured["body"])
        self.assertIn("כתובת: Alert street 7", captured["body"])
        self.assertIn("Alert street 7", captured["html_body"])
        self.assertIn("7788", captured["html_body"])
        self.assertEqual(captured["attachments"], [])

    def test_send_nastia_waiting_alert_email_for_hot_includes_call_number_customer_and_address(self):
        captured = {}
        self.app_module.PAIS_NOTIFICATION_FROM = ""
        self.app_module.SMTP_FROM = "nimbuskonan@gmail.com"
        self.app_module.SMTP_USERNAME = "nimbuskonan@gmail.com"

        def fake_send_plain_email(to_address, subject, body, from_address=None, html_body=None, attachments=None):
            captured["to_address"] = to_address
            captured["subject"] = subject
            captured["body"] = body
            captured["from_address"] = from_address
            captured["html_body"] = html_body or ""
            captured["attachments"] = attachments or []

        self.app_module.send_plain_email = fake_send_plain_email

        self.app_module.send_nastia_waiting_alert_email({
            "id": 45,
            "board_slug": "hot-kiryot",
            "service_type": "הוט קריות",
            "status": "ממתין לתיאום",
            "details": {
                "call_number": "275749117",
                "customer_name": "חיים",
                "address": "Hot street 9",
            },
        })

        self.assertEqual(captured["to_address"], self.app_module.NASTIA_NOTIFICATION_EMAIL)
        self.assertEqual(captured["from_address"], "nimbuskonan@gmail.com")
        self.assertIn("#0045", captured["subject"])
        self.assertIn("ממתין לתיאום", captured["subject"])
        self.assertIn("סטטוס: ממתין לתיאום", captured["body"])
        self.assertIn("מספר קריאה: 275749117", captured["body"])
        self.assertIn("שם לקוח: חיים", captured["body"])
        self.assertIn("כתובת: Hot street 9", captured["body"])
        self.assertIn("275749117", captured["html_body"])
        self.assertIn("חיים", captured["html_body"])
        self.assertIn("Hot street 9", captured["html_body"])
        self.assertEqual(captured["attachments"], [])

    def test_golan_coordination_calendar_link_includes_worker_guest_email(self):
        calendar_link = self.app_module.build_pais_google_calendar_link({
            "id": 44,
            "details": {
                "terminal_number": "1234",
                "address": "Calendar road 8",
                "customer_request": "Need visit",
                "coordinated_worker": "גולן",
                "visit_date": "2026-07-10",
                "visit_hour_from": "11:00",
                "visit_hour_to": "12:00",
            },
        })

        self.assertIsNotNone(calendar_link)
        self.assertIn("add=golan%40nimbusip.com", calendar_link)

    def test_new_worker_coordination_calendar_link_includes_worker_guest_email(self):
        calendar_link = self.app_module.build_pais_google_calendar_link({
            "id": 45,
            "details": {
                "terminal_number": "5678",
                "address": "Worker road 5",
                "customer_request": "Need installer",
                "coordinated_worker": "איציק",
                "visit_date": "2026-07-10",
                "visit_hour_from": "11:00",
                "visit_hour_to": "12:00",
            },
        })

        self.assertIsNotNone(calendar_link)
        self.assertIn("add=isaace%40nimbusip.com", calendar_link)

    def test_calendar_link_includes_address_and_contact_details(self):
        calendar_link = self.app_module.build_pais_google_calendar_link({
            "id": 46,
            "board_slug": "pais",
            "details": {
                "terminal_number": "9988",
                "address": "Email street 4",
                "contact_name": "Dana",
                "contact_phone": "0501234567",
                "customer_request": "Need visit",
                "coordinated_worker": "אסף",
                "visit_date": "2026-07-09",
                "visit_hour_from": "09:00",
                "visit_hour_to": "10:00",
            },
        })

        self.assertIsNotNone(calendar_link)
        query = parse_qs(urlparse(calendar_link).query)
        details_value = unquote(query["details"][0])
        self.assertIn("כתובת: Email street 4", details_value)
        self.assertIn("איש קשר: Dana 0501234567", details_value)
        self.assertEqual(query["location"][0], "Email street 4")

    def test_hot_coordination_changes_trigger_notification_email(self):
        tickets = self.app_module.load_support_tickets()
        tickets.append({
            "id": 2,
            "board_slug": "hot-kiryot",
            "created_at": "2026-07-08T09:00:00+03:00",
            "created_at_display": "08/07/2026 09:00",
            "creator": "Admin",
            "ticket_type": "שירות",
            "service_type": "הוט קריאות",
            "domain": "",
            "priority": "Medium",
            "description": "",
            "solution": "",
            "status": "ממתין לתאום",
            "assigned_to": "נסטיה",
            "details": {
                "call_number": "275749117",
                "customer_name": "חיים",
                "address": "האופה 1, נתניה",
                "issue_summary": "PANCODE לא עובד",
                "technician_actions": "בדיקות",
                "coordinated_worker": "",
                "visit_date": "",
                "visit_hour_from": "",
                "visit_hour_to": "",
                "failure_notes": "",
            },
            "attachments": [],
            "updates": [],
        })
        self.app_module.save_support_tickets(tickets)
        sent_tickets = []
        self.app_module.send_nastia_ticket_email = lambda ticket: sent_tickets.append(ticket)

        self.login("nastia@nimbusip.com", password="tygeydfuyw5t3g")
        response = self.client.post(
            "/support-tickets-update",
            json={
                "ticket_id": 2,
                "source_page_mode": "nastia",
                "source_ticket_queue": "nastia",
                "status": "תואם",
                "details": {
                    "technician_actions": "בדיקות",
                    "coordinated_worker": "אסף",
                    "visit_date": "2026-07-09",
                    "visit_hour_from": "09:00",
                    "visit_hour_to": "10:00",
                    "failure_notes": "",
                },
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["ticket"]["status"], "תואם")
        self.assertTrue(payload["ticket"]["notification_attempted"])
        self.assertTrue(payload["ticket"]["notification_sent"])
        self.assertEqual(len(sent_tickets), 1)
        self.assertEqual(sent_tickets[0]["details"]["call_number"], "275749117")

    def test_assigned_technician_field_report_requires_hot_ticket(self):
        tickets = self.app_module.load_support_tickets()
        tickets.append({
            "id": 2,
            "board_slug": "support",
            "created_at": "2026-07-08T09:10:00+03:00",
            "created_at_display": "08/07/2026 09:10",
            "creator": "Admin",
            "ticket_type": "תקלה",
            "service_type": "מצלמות",
            "domain": "",
            "priority": "Medium",
            "description": "Need visit",
            "solution": "",
            "status": "תואם",
            "assigned_to": "ניר",
            "details": {
                "coordinated_worker": "גולן",
                "visit_date": "2026-07-09",
                "visit_hour_from": "09:00",
                "visit_hour_to": "10:00",
                "failure_notes": "",
            },
            "attachments": [],
            "updates": [],
        })
        self.app_module.save_support_tickets(tickets)
        self.login("golan@nimbusip.com", "0503009456!")

        response = self.client.post(
            "/support-tickets-field-report",
            json={
                "ticket_id": 2,
                "nimbus_customer_name": "לקוח",
                "contact_first_name": "לקוח",
                "installation_address": "רחוב 1",
                "phone": "0501234567",
                "technician_name": "גולן",
                "technician_signature_data_url": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4////fwAJ+wP9KobjigAAAABJRU5ErkJggg==",
                "customer_signature_data_url": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4////fwAJ+wP9KobjigAAAABJRU5ErkJggg==",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("הוט ופיס", response.get_json()["message"])

    def test_pais_coordination_status_change_sends_waiting_alert_to_nastya(self):
        tickets = self.app_module.load_support_tickets()
        tickets.append({
            "id": 2,
            "board_slug": "pais",
            "created_at": "2026-07-08T09:00:00+03:00",
            "created_at_display": "08/07/2026 09:00",
            "creator": "Admin",
            "ticket_type": "שירות",
            "service_type": "מפעל הפיס",
            "domain": "",
            "priority": "Medium",
            "description": "",
            "solution": "",
            "status": "ממתין",
            "assigned_to": "ניר",
            "details": {
                "terminal_number": "9988",
                "address": "Email street 4",
                "customer_request": "לקוח מבקש תיאום",
                "actions_taken": "",
            },
            "attachments": [],
            "updates": [],
        })
        self.app_module.save_support_tickets(tickets)
        sent_tickets = []
        self.app_module.send_nastia_waiting_alert_email = lambda ticket: sent_tickets.append(ticket)

        self.login("admin@nimbusip.com")
        response = self.client.post(
            "/support-tickets-update",
            json={
                "ticket_id": 2,
                "status": self.app_module.COORDINATION_PENDING_STATUS,
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["ticket"]["status"], self.app_module.COORDINATION_PENDING_STATUS)
        self.assertTrue(payload["ticket"]["notification_attempted"])
        self.assertTrue(payload["ticket"]["notification_sent"])
        self.assertEqual(len(sent_tickets), 1)

    def test_hot_coordination_status_change_sends_waiting_alert_to_nastya(self):
        tickets = self.app_module.load_support_tickets()
        tickets.append({
            "id": 2,
            "board_slug": "hot-kiryot",
            "created_at": "2026-07-08T09:00:00+03:00",
            "created_at_display": "08/07/2026 09:00",
            "creator": "Admin",
            "ticket_type": "שירות",
            "service_type": "הוט קריות",
            "domain": "",
            "priority": "Medium",
            "description": "",
            "solution": "",
            "status": "ממתין",
            "assigned_to": "ניר",
            "details": {
                "call_number": "275749117",
                "customer_name": "חיים",
                "address": "Hot street 9",
                "issue_summary": "PANCODE לא עובד",
            },
            "attachments": [],
            "updates": [],
        })
        self.app_module.save_support_tickets(tickets)
        sent_tickets = []
        self.app_module.send_nastia_waiting_alert_email = lambda ticket: sent_tickets.append(ticket)

        self.login("admin@nimbusip.com")
        response = self.client.post(
            "/support-tickets-update",
            json={
                "ticket_id": 2,
                "status": self.app_module.COORDINATION_PENDING_STATUS,
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["ticket"]["status"], self.app_module.COORDINATION_PENDING_STATUS)
        self.assertTrue(payload["ticket"]["notification_attempted"])
        self.assertTrue(payload["ticket"]["notification_sent"])
        self.assertEqual(len(sent_tickets), 1)
        self.assertEqual(sent_tickets[0]["details"]["call_number"], "275749117")

    def test_extended_assignee_list_is_available(self):
        self.assertIn("איציק", self.app_module.SUPPORT_USERS)
        self.assertIn("זורה", self.app_module.SUPPORT_USERS)
        self.assertIn("מוסטפה.א", self.app_module.SUPPORT_USERS)
        self.assertIn("מוסטפה.ח", self.app_module.SUPPORT_USERS)
        self.assertIn("נסטיה", self.app_module.SUPPORT_USERS)
        self.assertIn(self.app_module.COORDINATION_PENDING_STATUS, self.app_module.PAIS_STATUSES)
        self.assertIn("אין מענה", self.app_module.PAIS_STATUSES)

    def test_pais_report_filters_by_status_and_date(self):
        tickets = self.app_module.load_support_tickets()
        tickets.extend([
            {
                "id": 2,
                "board_slug": "pais",
                "created_at": "2026-07-08T09:00:00+03:00",
                "created_at_display": "08/07/2026 09:00",
                "creator": "Admin",
                "ticket_type": "שירות",
                "service_type": "מפעל הפיס",
                "domain": "",
                "priority": "Medium",
                "description": "",
                "solution": "",
                "status": "בוצע",
                "assigned_to": "ניר",
                "details": {
                    "terminal_number": "2001",
                    "address": "A",
                    "customer_request": "R1",
                    "actions_taken": "A1",
                },
                "attachments": [],
                "updates": [],
            },
            {
                "id": 3,
                "board_slug": "pais",
                "created_at": "2026-07-08T10:00:00+03:00",
                "created_at_display": "08/07/2026 10:00",
                "creator": "Admin",
                "ticket_type": "שירות",
                "service_type": "מפעל הפיס",
                "domain": "",
                "priority": "Medium",
                "description": "",
                "solution": "",
                "status": "ממתין",
                "assigned_to": "זורה",
                "details": {
                    "terminal_number": "2002",
                    "address": "B",
                    "customer_request": "R2",
                    "actions_taken": "A2",
                },
                "attachments": [],
                "updates": [],
            },
        ])
        self.app_module.save_support_tickets(tickets)

        self.login("admin@nimbusip.com")
        response = self.client.get(
            "/pais-tickets-report-data?period=daily&status=בוצע&date_from=2026-07-08&date_to=2026-07-08"
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["summary"]["done"], 1)
        self.assertEqual(payload["summary"]["total"], 1)
        self.assertEqual(len(payload["tickets"]), 1)
        self.assertEqual(payload["tickets"][0]["details"]["terminal_number"], "2001")

if __name__ == "__main__":
    unittest.main()
