from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import time
from typing import Callable, Iterable

from dotenv import load_dotenv
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager


BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent

load_dotenv(ROOT_DIR / ".env")
load_dotenv(BASE_DIR / ".env", override=True)

LOGIN_URL = "https://billing.nimbusip.com/admin/login/?next=/admin/login/"
DID_LIST_URL = "https://billing.nimbusip.com/admin/management/did/"
CUSTOMER_VALUE = "15555304679453049"
PRIMARY_DESTINATION = "{DID_ALIAS}@52.28.195.112:5080"


@dataclass
class DidCreationResult:
    input_number: str
    normalized_number: str
    alias: str
    full_number: str
    ok: bool
    message: str


def increment_number_str(number_str: str) -> str:
    try:
        return str(int(number_str) + 1)
    except ValueError as exc:
        raise ValueError("Input must be a numeric string.") from exc


def normalize_did_input(raw_value: str) -> str:
    did_input = (raw_value or "").strip().lstrip("0")
    if not did_input.isdigit() or len(did_input) < 8:
        raise ValueError("Invalid number. Must be digits and at least 8 characters after stripping 0s.")
    return did_input


def get_cgrt_login_credentials() -> tuple[str, str]:
    username = (os.environ.get("cgrtusername") or os.environ.get("CGRTUSERNAME") or "").strip()
    password = (os.environ.get("cgrtpassword") or os.environ.get("CGRTPASSWORD") or "").strip()

    if not username:
        raise RuntimeError("Missing cgrtusername in .env.")
    if not password:
        raise RuntimeError("Missing cgrtpassword in .env.")

    return username, password


class CGRTAutomationSession:
    def __init__(self, *, headless: bool = True):
        self.headless = headless
        self.driver = None
        self.wait = None

    def __enter__(self) -> "CGRTAutomationSession":
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def start(self) -> None:
        if self.driver is not None:
            return

        chrome_options = Options()
        if self.headless:
            chrome_options.add_argument("--headless")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")

        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        self.wait = WebDriverWait(self.driver, 20)
        self._login()

    def close(self) -> None:
        if self.driver is not None:
            self.driver.quit()
            self.driver = None
            self.wait = None

    def _login(self) -> None:
        driver = self._require_driver()
        wait = self._require_wait()
        username, password = get_cgrt_login_credentials()

        driver.get(LOGIN_URL)
        wait.until(EC.presence_of_element_located((By.ID, "id_username"))).send_keys(username)
        driver.find_element(By.NAME, "password").send_keys(password)
        driver.find_element(By.XPATH, "//input[@value='Sign in']").click()
        wait.until(EC.presence_of_element_located((By.XPATH, "//body")))

    def create_did(self, did_input: str) -> DidCreationResult:
        normalized = normalize_did_input(did_input)
        full_number = f"972{normalized}"
        alias = f"0{normalized}"

        driver = self._require_driver()
        wait = self._require_wait()

        driver.get(DID_LIST_URL)
        wait.until(EC.element_to_be_clickable((By.XPATH, "//a[@class='btn btn-primary']"))).click()

        wait.until(EC.presence_of_element_located((By.NAME, "country")))
        Select(driver.find_element(By.NAME, "country")).select_by_value("IL")
        driver.find_element(By.ID, "id_did_number").send_keys(full_number)
        driver.find_element(By.ID, "id_did_alias").send_keys(alias)
        time.sleep(1)

        Select(driver.find_element(By.ID, "id_status")).select_by_index(2)
        time.sleep(1)
        Select(driver.find_element(By.ID, "id_tenant")).select_by_index(1)
        time.sleep(1)
        Select(driver.find_element(By.ID, "id_customer")).select_by_value(CUSTOMER_VALUE)
        time.sleep(1)
        Select(driver.find_element(By.ID, "id_provider")).select_by_index(1)
        time.sleep(1)
        Select(driver.find_element(By.ID, "id_primary_route")).select_by_index(4)
        time.sleep(1)

        driver.find_element(By.ID, "id_primary_destination").send_keys(PRIMARY_DESTINATION)
        time.sleep(1)

        driver.find_element(
            By.XPATH,
            "//fieldset[@id='fieldset-3']//span[contains(@class, 'glyphicon-resize-full')]",
        ).click()
        time.sleep(1)
        Select(driver.find_element(By.ID, "id_customer_plan")).select_by_index(1)
        time.sleep(1)

        driver.find_element(By.NAME, "_save").click()

        duplicate_xpath = "//li[normalize-space()='DID number already exists.']"
        try:
            WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.XPATH, duplicate_xpath))
            )
            return DidCreationResult(
                input_number=did_input,
                normalized_number=normalized,
                alias=alias,
                full_number=full_number,
                ok=False,
                message=f"{alias} already exists.",
            )
        except TimeoutException:
            return DidCreationResult(
                input_number=did_input,
                normalized_number=normalized,
                alias=alias,
                full_number=full_number,
                ok=True,
                message=f"{alias} DID created successfully.",
            )

    def _require_driver(self):
        if self.driver is None:
            raise RuntimeError("Browser session is not started.")
        return self.driver

    def _require_wait(self):
        if self.wait is None:
            raise RuntimeError("Browser wait helper is not started.")
        return self.wait


def run_script(did_input: str, *, headless: bool = True) -> DidCreationResult:
    with CGRTAutomationSession(headless=headless) as session:
        return session.create_did(did_input)


def run_batch(
    did_inputs: Iterable[str],
    *,
    headless: bool = True,
    progress_callback: Callable[[DidCreationResult, int, int], None] | None = None,
) -> list[DidCreationResult]:
    results: list[DidCreationResult] = []
    normalized_inputs = list(did_inputs)
    total = len(normalized_inputs)

    with CGRTAutomationSession(headless=headless) as session:
        for index, did_input in enumerate(normalized_inputs, start=1):
            result = session.create_did(did_input)
            results.append(result)
            if progress_callback:
                progress_callback(result, index, total)

    return results


def main() -> None:
    try:
        did_input = normalize_did_input(input("Enter Number: ").strip())
    except ValueError as exc:
        print(f"Error: {exc}")
        return

    with CGRTAutomationSession(headless=True) as session:
        while True:
            result = session.create_did(did_input)
            print(result.message)

            choice = input("Press 1 to end script, Press 2 to continue, Press 3 to add range: ").strip()

            if choice == "1":
                print("Exiting script.")
                break

            if choice == "2":
                try:
                    did_input = increment_number_str(did_input)
                except ValueError as exc:
                    print(f"Error: {exc}")
                    break
                continue

            if choice == "3":
                range_input = input("Enter range (max 10): ").strip()
                if not range_input.isdigit():
                    print("Range must be digits only.")
                    continue

                range_count = int(range_input)
                if not (1 <= range_count <= 10):
                    print("Range must be between 1 and 10.")
                    continue

                try:
                    start_number = int(did_input) + 1
                    end_number = start_number + range_count
                    created_numbers = []

                    for num in range(start_number, end_number):
                        batch_result = session.create_did(str(num))
                        print(batch_result.message)
                        if batch_result.ok:
                            created_numbers.append(batch_result.alias)

                    if created_numbers:
                        print(f"Created: {created_numbers[0]} - {created_numbers[-1]}")
                    did_input = str(end_number - 1)
                except ValueError as exc:
                    print(f"Error: {exc}")
                    break
                continue

            print("Invalid choice. Please enter 1, 2, or 3.")


if __name__ == "__main__":
    main()
