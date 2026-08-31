import importlib
import os
import sys
import tempfile
import types
import unittest
from datetime import datetime


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
        colors.white = "#ffffff"
        colors.HexColor = lambda value: value
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
        styles.ParagraphStyle = lambda *args, **kwargs: {"args": args, "kwargs": kwargs}
        styles.getSampleStyleSheet = lambda: {}
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
        pdfmetrics.getRegisteredFontNames = lambda: []
        sys.modules["reportlab.pdfbase.pdfmetrics"] = pdfmetrics

    if "reportlab.pdfbase.ttfonts" not in sys.modules:
        ttfonts = types.ModuleType("reportlab.pdfbase.ttfonts")

        class TTFont:
            def __init__(self, *args, **kwargs):
                self.args = args
                self.kwargs = kwargs

        ttfonts.TTFont = TTFont
        sys.modules["reportlab.pdfbase.ttfonts"] = ttfonts

    if "reportlab.platypus" not in sys.modules:
        platypus = types.ModuleType("reportlab.platypus")
        platypus.Paragraph = lambda *args, **kwargs: {"args": args, "kwargs": kwargs}
        platypus.SimpleDocTemplate = object
        platypus.Spacer = lambda *args, **kwargs: {"args": args, "kwargs": kwargs}
        platypus.Table = lambda *args, **kwargs: {"args": args, "kwargs": kwargs}
        platypus.TableStyle = lambda *args, **kwargs: {"args": args, "kwargs": kwargs}
        sys.modules["reportlab.platypus"] = platypus


class SmsStatusDoneTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        install_import_stubs()
        os.environ["SECRET_KEY"] = "test-secret-key"
        os.environ["APP_PASSWORD"] = "secret123"
        import app as app_module

        cls.app_module = importlib.reload(app_module)

    def setUp(self):
        self.app_module.app.config["TESTING"] = True
        self.client = self.app_module.app.test_client()
        self.original_vercel = os.environ.get("VERCEL")
        self.original_get_gspread_client = self.app_module.get_gspread_client
        self.original_append_log = self.app_module.append_log
        self.original_gspread_utils = getattr(self.app_module.gspread, "utils", None)

    def tearDown(self):
        self.app_module.get_gspread_client = self.original_get_gspread_client
        self.app_module.append_log = self.original_append_log
        if self.original_gspread_utils is None:
            if hasattr(self.app_module.gspread, "utils"):
                delattr(self.app_module.gspread, "utils")
        else:
            self.app_module.gspread.utils = self.original_gspread_utils
        if self.original_vercel is None:
            os.environ.pop("VERCEL", None)
        else:
            os.environ["VERCEL"] = self.original_vercel

    def login(self):
        return self.client.post(
            "/login",
            data={"username": "admin@nimbusip.com", "password": "secret123"},
            follow_redirects=False,
        )

    def test_app_log_path_uses_temp_directory_on_vercel(self):
        os.environ["VERCEL"] = "1"

        path = self.app_module.app_log_path("created.log")

        self.assertIn(tempfile.gettempdir(), path)
        self.assertTrue(path.endswith("created.log"))

    def test_mark_done_updates_sheets_even_when_log_write_fails(self):
        class FakeWorksheet:
            def __init__(self):
                self.updates = []

            def batch_update(self, updates):
                self.updates.extend(updates)

        class FakeSpreadsheet:
            def __init__(self, app_module):
                self.app_module = app_module
                self.sms = FakeWorksheet()
                self.cgr = FakeWorksheet()

            def worksheet(self, name):
                if name == self.app_module.SHEET_NAME:
                    return self.sms
                if name == self.app_module.CGR_SHEET_NAME:
                    return self.cgr
                raise AssertionError(f"Unexpected worksheet request: {name}")

        class FakeClient:
            def __init__(self, spreadsheet):
                self.spreadsheet = spreadsheet

            def open_by_key(self, key):
                self.last_key = key
                return self.spreadsheet

        today = datetime.now().strftime("%Y-%m-%d")
        spreadsheet = FakeSpreadsheet(self.app_module)
        self.app_module.get_gspread_client = lambda: FakeClient(spreadsheet)
        self.app_module.append_log = lambda customers: (_ for _ in ()).throw(OSError("read only file system"))
        self.app_module.gspread.utils = types.SimpleNamespace(
            rowcol_to_a1=lambda row, col: f"{chr(64 + col)}{row}"
        )

        self.login()
        response = self.client.post(
            "/mark-done",
            json={
                "customers": [
                    {
                        "sheet_row": 5,
                        "name": "Client One",
                        "domain": "6404",
                        "did": "046116362",
                        "cgr_row": 7,
                    }
                ]
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["updated"], 1)
        self.assertEqual(
            spreadsheet.sms.updates,
            [{"range": "H5", "values": [[self.app_module.STATUS_DONE]]}],
        )
        self.assertEqual(
            spreadsheet.cgr.updates,
            [{"range": "C7:E7", "values": [["6404", today, True]]}],
        )


if __name__ == "__main__":
    unittest.main()
