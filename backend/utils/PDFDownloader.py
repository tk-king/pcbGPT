import os
import time
import shutil
from uuid import uuid4

import requests
from ddgs import DDGS

from backend.config import TMP_DIR
from backend.utils.tool_progress import report_tool_progress


_DDGS_TIMEOUT_S = int(os.getenv("DDGS_TIMEOUT", "8"))
_PDF_CONNECT_TIMEOUT_S = float(os.getenv("PDF_CONNECT_TIMEOUT", "5"))
_PDF_READ_TIMEOUT_S = float(os.getenv("PDF_READ_TIMEOUT", "20"))


def progress(msg: str) -> None:
    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)
    # Also forward to any registered UI progress sink (agent tool calls).
    report_tool_progress(msg)


def download_with_requests(pdf_url: str, file_path: str) -> int:
    response = requests.get(
        pdf_url,
        timeout=(_PDF_CONNECT_TIMEOUT_S, _PDF_READ_TIMEOUT_S),
        stream=True,
    )
    response.raise_for_status()
    content_type = response.headers.get("Content-Type", "").lower()
    if "pdf" not in content_type and "octet-stream" not in content_type:
        progress(f"Warning: unexpected Content-Type {content_type!r} for {pdf_url}")

    tmp_path = f"{file_path}.part"
    first_chunk = b""
    total = 0
    with open(tmp_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=1024 * 64):
            if not chunk:
                continue
            if not first_chunk:
                first_chunk = chunk
            f.write(chunk)
            total += len(chunk)
    if not first_chunk.startswith(b"%PDF-"):
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        raise ValueError("Downloaded file does not look like a PDF.")
    os.replace(tmp_path, file_path)
    return total


def download_with_selenium(pdf_url: str, file_path: str) -> int:
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError(
            "Selenium download requested but selenium is not installed. "
            "Install the selenium package and ensure a compatible driver is available."
        ) from exc

    # Use the configured TMP_DIR for selenium download workspace, not the final datasheet folder.
    download_root = os.path.abspath(TMP_DIR)
    temp_download_dir = os.path.join(download_root, f"_selenium_{uuid4().hex}")
    os.makedirs(temp_download_dir, exist_ok=True)

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_experimental_option(
        "prefs",
        {
            "download.default_directory": temp_download_dir,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "plugins.always_open_pdf_externally": True,
        },
    )

    driver = None
    try:
        driver = webdriver.Chrome(options=options)
        timeout_total = max(_PDF_CONNECT_TIMEOUT_S + _PDF_READ_TIMEOUT_S, 1)
        try:
            driver.set_page_load_timeout(timeout_total)
        except Exception:
            pass
        try:
            driver.execute_cdp_cmd(
                "Page.setDownloadBehavior",
                {"behavior": "allow", "downloadPath": temp_download_dir},
            )
        except Exception:
            pass

        existing_files = set(os.listdir(temp_download_dir))
        driver.get(pdf_url)

        deadline = time.time() + timeout_total
        pending_extensions = (".crdownload", ".tmp", ".part")
        downloaded_file = None
        while time.time() < deadline:
            for name in os.listdir(temp_download_dir):
                if name in existing_files:
                    continue
                if name.endswith(pending_extensions):
                    continue
                candidate_path = os.path.join(temp_download_dir, name)
                if os.path.isfile(candidate_path):
                    downloaded_file = candidate_path
                    break
            if downloaded_file:
                break
            time.sleep(0.2)
        if not downloaded_file:
            raise TimeoutError(
                "Timed out waiting for Selenium to finish downloading the PDF."
            )
    finally:
        if driver is not None:
            driver.quit()

    shutil.move(downloaded_file, file_path)
    shutil.rmtree(temp_download_dir, ignore_errors=True)
    return os.path.getsize(file_path)


def clean_part_name_for_search(part_name: str) -> str:
    """Strip library prefixes/underscores: 'Sensor_Pressure:BMP280' -> 'BMP280'.

    Raw KiCad-style names make web searches fail (colons are treated as
    special syntax by some engines); only the bare part name is useful.
    """
    name = str(part_name or "").strip()
    if ":" in name:
        name = name.split(":", 1)[1]
    return name.replace("_", " ").strip()


def select_pdf_url(results: list[dict]) -> str | None:
    return next(
        (
            r.get("href", "")
            for r in results
            if r.get("href", "").lower().endswith(".pdf")
        ),
        None,
    )


def search_pdf_url(query: str) -> str | None:
    # backend="auto" lets ddgs fall back across engines when one fails or
    # returns nothing (a single fixed backend is flaky).
    results = list(
        DDGS(timeout=_DDGS_TIMEOUT_S).text(
            query,
            max_results=5,
            region="de-de",
            backend="auto",
        )
    )
    progress(f"Search returned {len(results)} result(s) for {query!r}")
    url = select_pdf_url(results)
    if not url:
        # Fall back to any result whose page likely links the datasheet.
        for r in results:
            href = str(r.get("href", ""))
            if any(k in href.lower() for k in ("datasheet", "/pdf", "document")):
                return href
    return url
