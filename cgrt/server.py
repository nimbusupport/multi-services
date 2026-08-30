from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import datetime
from importlib import import_module
from pathlib import Path

import gspread
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.service_account import Credentials


BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent

load_dotenv(ROOT_DIR / ".env")
load_dotenv(BASE_DIR / ".env")

PORT = 1002
SPREADSHEET_ID = "1uwtREvtWENPabibI5FSlhdYokIbBs_kuZmYVeL-BgCQ"
SHEET_NAME = "חיפ_סמס"
START_ROW = 312
COL_NUMBER = 1  # A
COL_MARKED = 2  # B
CREDENTIALS_FILE = (os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "credentials.json") or "").strip()

app = Flask(__name__, template_folder="templates", static_folder="static")

job_lock = threading.Lock()
jobs_lock = threading.Lock()
jobs: dict[str, dict] = {}
active_job_id: str | None = None


def digits_only(value: str) -> str:
    return "".join(ch for ch in (value or "").strip() if ch.isdigit())


def report_checkbox_marked(value) -> bool:
    text = str(value or "").strip().lower()
    return text in ("true", "yes", "1", "v", "✓", "✔")


def resolve_credentials_path(raw_path: str) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        return path

    candidates = [
        ROOT_DIR / path,
        BASE_DIR / path,
        Path.cwd() / path,
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return ROOT_DIR / path


def load_service_account_info():
    creds_source = CREDENTIALS_FILE.strip()
    if not creds_source:
        raise RuntimeError("GOOGLE_APPLICATION_CREDENTIALS is empty.")

    if creds_source.startswith("{"):
        info = json.loads(creds_source)
        source_label = "GOOGLE_APPLICATION_CREDENTIALS (inline JSON)"
    else:
        abs_path = resolve_credentials_path(creds_source)
        if not abs_path.exists():
            raise RuntimeError(f"Credentials file not found: {abs_path}")
        with abs_path.open("r", encoding="utf-8") as handle:
            info = json.load(handle)
        source_label = str(abs_path)

    if info.get("type") != "service_account":
        raise RuntimeError(
            f"Credentials must be a service account JSON. Found type={info.get('type')!r} in {source_label}"
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
        "https://www.googleapis.com/auth/drive",
    ]
    creds_info, creds_source = load_service_account_info()
    service_account = creds_info.get("client_email") or "unknown"
    key_id = creds_info.get("private_key_id") or "unknown"
    account_hint = f"Service account: {service_account}; key id: {key_id}; loaded from: {creds_source}"

    try:
        creds = Credentials.from_service_account_info(creds_info, scopes=scope)
        creds.refresh(Request())
    except RefreshError as exc:
        raise RuntimeError(f"Google auth refresh failed ({account_hint}): {exc}") from exc
    except Exception as exc:
        raise RuntimeError(f"Failed to initialize Google credentials ({account_hint}): {exc}") from exc

    return gspread.authorize(creds)


def get_sheet():
    client = get_gspread_client()
    return client.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)


def load_cgrt_runner():
    try:
        return import_module("cgrtmultinew")
    except ModuleNotFoundError as exc:
        missing_name = getattr(exc, "name", "") or "a required package"
        raise RuntimeError(
            f"CGRT runner could not start because {missing_name} is missing. "
            "Install the packages from cgrt/requirements.txt first."
        ) from exc


def fetch_available_numbers() -> list[dict]:
    ws = get_sheet()
    rows = ws.get(f"A{START_ROW}:B")
    numbers: list[dict] = []

    for offset, row in enumerate(rows):
        row_number = START_ROW + offset
        raw_number = row[COL_NUMBER - 1] if len(row) >= COL_NUMBER else ""
        raw_marked = row[COL_MARKED - 1] if len(row) >= COL_MARKED else ""

        if report_checkbox_marked(raw_marked):
            continue

        digits = digits_only(raw_number)
        if not digits:
            continue

        display_number = digits if digits.startswith("0") else f"0{digits}"
        numbers.append(
            {
                "row": row_number,
                "number": display_number,
                "normalized_number": digits.lstrip("0") or digits,
                "marked": False,
            }
        )

    return numbers


def serialize_result(result) -> dict:
    return {
        "input_number": result.input_number,
        "normalized_number": result.normalized_number,
        "alias": result.alias,
        "full_number": result.full_number,
        "ok": result.ok,
        "message": result.message,
    }


def get_job_snapshot(job_id: str) -> dict:
    with jobs_lock:
        job = jobs.get(job_id)
        if job is None:
            raise KeyError(job_id)
        return {
            "id": job["id"],
            "status": job["status"],
            "created_at": job["created_at"],
            "started_at": job["started_at"],
            "finished_at": job["finished_at"],
            "total": job["total"],
            "completed": job["completed"],
            "success_count": job["success_count"],
            "failure_count": job["failure_count"],
            "error": job["error"],
            "items": [dict(item) for item in job["items"]],
        }


def set_job_state(job_id: str, **updates) -> None:
    with jobs_lock:
        job = jobs[job_id]
        job.update(updates)


def update_job_item(job_id: str, row_number: int, **updates) -> None:
    with jobs_lock:
        job = jobs[job_id]
        for item in job["items"]:
            if item["row"] == row_number:
                item.update(updates)
                return
        raise KeyError(f"Row {row_number} not found in job {job_id}.")


def run_selected_numbers(job_id: str, selected_items: list[dict]) -> None:
    global active_job_id

    try:
        runner = load_cgrt_runner()
        set_job_state(job_id, status="running", started_at=datetime.now().isoformat(timespec="seconds"))
        ws = get_sheet()

        def progress_callback(result, index: int, total: int) -> None:
            row_number = selected_items[index - 1]["row"]
            serialized_result = serialize_result(result)
            item_status = "done" if result.ok else "failed"
            marked_in_sheet = False

            if result.ok:
                try:
                    ws.update_cell(row_number, COL_MARKED, True)
                    marked_in_sheet = True
                except Exception as exc:
                    item_status = "failed"
                    serialized_result["ok"] = False
                    serialized_result["message"] = (
                        f"{result.message} CGRT was created, but column B could not be updated: {exc}"
                    )

            item_updates = {
                "status": item_status,
                "result": serialized_result,
                "finished_at": datetime.now().isoformat(timespec="seconds"),
                "marked_in_sheet": marked_in_sheet,
            }

            update_job_item(job_id, row_number, **item_updates)

            with jobs_lock:
                job = jobs[job_id]
                job["completed"] = index
                job["success_count"] = sum(1 for item in job["items"] if item["status"] == "done")
                job["failure_count"] = sum(1 for item in job["items"] if item["status"] == "failed")

        runner.run_batch(
            [item["number"] for item in selected_items],
            headless=True,
            progress_callback=progress_callback,
        )

        set_job_state(job_id, status="completed", finished_at=datetime.now().isoformat(timespec="seconds"))
    except Exception as exc:
        set_job_state(
            job_id,
            status="failed",
            error=str(exc),
            finished_at=datetime.now().isoformat(timespec="seconds"),
        )
    finally:
        with job_lock:
            active_job_id = None


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/numbers")
def api_numbers():
    try:
        return jsonify({"ok": True, "numbers": fetch_available_numbers()})
    except Exception as exc:
        return jsonify({"ok": False, "message": str(exc)}), 500


@app.post("/api/jobs")
def api_create_job():
    global active_job_id

    payload = request.get_json(silent=True) or {}
    selected_rows = payload.get("rows") or []
    if not isinstance(selected_rows, list) or not selected_rows:
        return jsonify({"ok": False, "message": "Select at least one number."}), 400

    try:
        selected_rows = [int(row) for row in selected_rows]
    except (TypeError, ValueError):
        return jsonify({"ok": False, "message": "Rows must be integers."}), 400

    try:
        runner = load_cgrt_runner()
    except RuntimeError as exc:
        return jsonify({"ok": False, "message": str(exc)}), 500

    available_numbers = fetch_available_numbers()
    number_map = {item["row"]: item for item in available_numbers}
    selected_items = [number_map[row] for row in selected_rows if row in number_map]

    if not selected_items:
        return jsonify({"ok": False, "message": "Selected numbers are no longer available."}), 400

    for item in selected_items:
        try:
            runner.normalize_did_input(item["number"])
        except ValueError as exc:
            return jsonify({"ok": False, "message": f"{item['number']}: {exc}"}), 400

    with job_lock:
        if active_job_id is not None:
            return jsonify({"ok": False, "message": "Another CGRT job is already running."}), 409

        job_id = uuid.uuid4().hex
        active_job_id = job_id

    job = {
        "id": job_id,
        "status": "queued",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "started_at": None,
        "finished_at": None,
        "total": len(selected_items),
        "completed": 0,
        "success_count": 0,
        "failure_count": 0,
        "error": None,
        "items": [
            {
                "row": item["row"],
                "number": item["number"],
                "status": "queued",
                "marked_in_sheet": False,
                "result": None,
                "finished_at": None,
            }
            for item in selected_items
        ],
    }

    with jobs_lock:
        jobs[job_id] = job

    worker = threading.Thread(target=run_selected_numbers, args=(job_id, selected_items), daemon=True)
    worker.start()

    return jsonify({"ok": True, "job_id": job_id, "job": get_job_snapshot(job_id)})


@app.get("/api/jobs/<job_id>")
def api_job(job_id: str):
    try:
        return jsonify({"ok": True, "job": get_job_snapshot(job_id)})
    except KeyError:
        return jsonify({"ok": False, "message": "Job not found."}), 404


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=PORT, debug=False)
