import unittest
from unittest.mock import patch

import requests

import app as sms_app


class FakeResponse:
    def __init__(self, status_code, body):
        self.status_code = status_code
        self._body = body
        self.text = body if isinstance(body, str) else ""

    def json(self):
        if isinstance(self._body, Exception):
            raise self._body
        return self._body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} error")


class CreateSmsTests(unittest.TestCase):
    def setUp(self):
        sms_app.app.config["TESTING"] = True
        self.client = sms_app.app.test_client()
        self.original_sms_url = sms_app.SMS_URL
        self.original_sms_token = sms_app.SMS_TOKEN
        sms_app.SMS_URL = "https://cloud.voipappz.io:9443/api/schemas"
        sms_app.SMS_TOKEN = "Basic test-token"

    def tearDown(self):
        sms_app.SMS_URL = self.original_sms_url
        sms_app.SMS_TOKEN = self.original_sms_token

    def test_normalizes_old_voipappz_ports(self):
        self.assertEqual(
            sms_app.normalize_voipappz_sms_url("https://cloud.voipappz.io:9443/api/schemas"),
            "https://cloud.voipappz.io/api/schemas",
        )
        self.assertEqual(
            sms_app.normalize_voipappz_sms_url("https://cloud.voipappz.io:443/api/schemas"),
            "https://cloud.voipappz.io/api/schemas",
        )

    @patch("app.requests.post")
    def test_timeout_without_response_is_reported_as_created(self, post):
        post.side_effect = requests.exceptions.ReadTimeout("read timed out")

        response = self.client.post(
            "/create-sms",
            json={
                "customers": [
                    {
                        "domain": "6101",
                        "did": "0747041404",
                        "numbercgr": "0777315857",
                        "text": "hello",
                    }
                ]
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["results"][0]["success"])
        self.assertEqual(payload["results"][0]["response"], "Created")
        self.assertEqual(post.call_args.args[0], "https://cloud.voipappz.io/api/schemas")

    @patch("app.requests.post")
    def test_api_error_response_is_preserved(self, post):
        post.return_value = FakeResponse(409, {"message": "environment name exists"})

        response = self.client.post(
            "/create-sms",
            json={
                "customers": [
                    {
                        "domain": "6101",
                        "did": "0747041404",
                        "numbercgr": "0777315857",
                        "text": "hello",
                    }
                ]
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertFalse(payload["results"][0]["success"])
        self.assertEqual(payload["results"][0]["response"], {"message": "environment name exists"})


class FireberryIdNumberTests(unittest.TestCase):
    def test_eight_digit_idnumber_gets_leading_zero(self):
        self.assertEqual(sms_app.normalize_idnumber_for_fireberry("29702305"), "029702305")
        self.assertEqual(sms_app.normalize_idnumber_for_fireberry("029702305"), "029702305")

    @patch("app.requests.post")
    def test_fireberry_lookup_queries_padded_idnumber(self, post):
        post.return_value = FakeResponse(
            200,
            {
                "data": {
                    "Data": [
                        {
                            "pcfsystemfield179": "6101",
                            "pcfsystemfield166": "0747041404",
                            "pcfsystemfield164": "",
                        }
                    ]
                }
            },
        )

        result = sms_app.fireberry_lookup_by_idnumber("29702305")

        self.assertTrue(result["found"])
        self.assertEqual(result["domain"], "6101")
        self.assertEqual(post.call_args.kwargs["json"]["query"], "(idnumber = 029702305)")


if __name__ == "__main__":
    unittest.main()
