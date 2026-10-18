import argparse
import json
import os
import sys
from getpass import getpass

import requests
from dotenv import load_dotenv


load_dotenv()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Log in as admin and send a test push notification to a support user.",
    )
    parser.add_argument(
        "--base-url",
        default=os.environ.get("SUPPORT_TEST_BASE_URL", "https://multi-services-gilt.vercel.app"),
        help="App base URL, for example http://127.0.0.1:5059 or https://multi-services-gilt.vercel.app",
    )
    parser.add_argument(
        "--username",
        default=os.environ.get("APP_USERNAME") or os.environ.get("SUPPORT_TEST_ADMIN_USERNAME", "admin@nimbusip.com"),
        help="Admin login username. Defaults to APP_USERNAME from .env when available.",
    )
    parser.add_argument(
        "--password",
        default=os.environ.get("APP_PASSWORD") or os.environ.get("SUPPORT_TEST_ADMIN_PASSWORD", ""),
        help="Admin login password. Defaults to APP_PASSWORD from .env when available.",
    )
    parser.add_argument(
        "--support-user",
        default="",
        help="Support user identifier to target, such as a display name, username, or email.",
    )
    parser.add_argument(
        "--title",
        default="בדיקת Push",
        help="Push notification title.",
    )
    parser.add_argument(
        "--body",
        default="בדיקה ידנית",
        help="Push notification body.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=20.0,
        help="HTTP timeout in seconds.",
    )
    parser.add_argument(
        "--insecure",
        action="store_true",
        help="Disable TLS certificate verification.",
    )
    return parser


def normalize_base_url(base_url: str) -> str:
    return str(base_url or "").strip().rstrip("/")


def prompt_value(label: str, initial_value: str = "") -> str:
    provided = str(initial_value or "").strip()
    if provided:
        return provided

    try:
        entered = input(label).strip()
    except EOFError:
        entered = ""
    return entered


def prompt_password(initial_value: str = "") -> str:
    provided = str(initial_value or "")
    if provided:
        return provided

    try:
        entered = getpass("Enter admin password: ")
    except EOFError:
        entered = ""

    if not entered:
        raise RuntimeError("Missing password. Pass --password, set APP_PASSWORD / SUPPORT_TEST_ADMIN_PASSWORD, or enter it when prompted.")
    return entered


def prompt_support_user(initial_value: str = "") -> str:
    entered = prompt_value("Enter support user name / username / email: ", initial_value)
    if not entered:
        raise RuntimeError("Missing support user. Pass --support-user or enter a value when prompted.")
    return entered


def login(session: requests.Session, base_url: str, username: str, password: str, timeout: float, verify: bool) -> None:
    response = session.post(
        f"{base_url}/login",
        data={"username": username, "password": password},
        timeout=timeout,
        verify=verify,
        allow_redirects=False,
    )

    if response.status_code not in {200, 302, 303}:
        raise RuntimeError(f"Login failed with status {response.status_code}: {response.text[:300]}")

    if response.status_code == 200:
        body = response.text or ""
        if "Invalid username or password" in body or "login" in response.url.lower():
            raise RuntimeError(
                "Login did not create a session. Check the admin username/password for this environment. "
                f"base_url={base_url} username={username}"
            )


def send_test_push(
    session: requests.Session,
    base_url: str,
    support_user: str,
    title: str,
    body: str,
    timeout: float,
    verify: bool,
) -> requests.Response:
    payload = {
        "support_user": support_user,
        "title": title,
        "body": body,
    }
    return session.post(
        f"{base_url}/support-users-send-test-push",
        json=payload,
        timeout=timeout,
        verify=verify,
    )


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    base_url = normalize_base_url(args.base_url)
    username = prompt_value("Enter admin username/email: ", args.username)
    password = prompt_password(args.password)
    support_user = prompt_support_user(args.support_user)
    session = requests.Session()
    verify = not args.insecure

    try:
        login(session, base_url, username.strip(), password, args.timeout, verify)
        response = send_test_push(
            session,
            base_url,
            support_user,
            args.title,
            args.body,
            args.timeout,
            verify,
        )
    except requests.RequestException as exc:
        print(f"Request failed: {exc}", file=sys.stderr)
        return 1
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    content_type = response.headers.get("Content-Type", "")
    if "application/json" in content_type:
        try:
            payload = response.json()
        except json.JSONDecodeError:
            payload = {"ok": False, "message": response.text}
    else:
        payload = {"ok": False, "message": response.text}

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if response.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())