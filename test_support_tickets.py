import importlib
import os
import sys
import tempfile
import types
import unittest
from datetime import datetime
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

    def test_extended_assignee_list_is_available(self):
        self.assertIn("איציק", self.app_module.SUPPORT_USERS)
        self.assertIn("זורה", self.app_module.SUPPORT_USERS)
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

    def test_limited_ticket_user_can_only_access_ticket_pages(self):
        response = self.login("nastya@nimbusip.com", "tygeydfuyw5t3g")

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].endswith("/support-tickets"))

        home_response = self.client.get("/home", follow_redirects=False)
        self.assertEqual(home_response.status_code, 302)
        self.assertTrue(home_response.headers["Location"].endswith("/support-tickets"))

        tickets_response = self.client.get("/support-tickets", follow_redirects=False)
        self.assertEqual(tickets_response.status_code, 200)

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

if __name__ == "__main__":
    unittest.main()
