import os

import fitz

from backend.utils.PDFDownloader import (
    clean_part_name_for_search,
    download_with_requests,
    download_with_selenium,
    progress,
    search_pdf_url,
)


def _has_direct_datasheet_url(datasheet_url: str | None) -> bool:
    if not datasheet_url:
        return False
    candidate = str(datasheet_url).strip()
    if not candidate or candidate == "~":
        return False
    return candidate.startswith(("http://", "https://"))


def _is_valid_pdf_file(path: str) -> bool:
    try:
        with fitz.open(path):
            return True
    except Exception:
        return False

def _short_exc(exc: Exception, limit: int = 240) -> str:
    """First line of an exception message - skips chromedriver stacktraces etc."""
    text = str(exc).strip()
    first = text.splitlines()[0] if text else type(exc).__name__
    return first if len(first) <= limit else first[:limit] + "\u2026"


def _download_datasheet_for_component(
    part_name: str, datasheet_url: str | None, *, use_selenium: bool
) -> str:
    os.makedirs("./datasheets", exist_ok=True)
    safe_name = part_name.replace("/", "_").replace(":", "_")
    local_path = os.path.join("./datasheets", f"{safe_name}.pdf")
    if os.path.exists(local_path):
        if _is_valid_pdf_file(local_path):
            return local_path
        progress(f"Cached datasheet is not a valid PDF, deleting: {local_path}")
        try:
            os.remove(local_path)
        except OSError:
            pass

    last_error: Exception | None = None
    if _has_direct_datasheet_url(datasheet_url):
        progress(f"Downloading datasheet from component URL: {datasheet_url}")
        # Try a plain HTTP GET first: it is faster and produces clearer network
        # errors than a headless browser. Selenium is the fallback for hosts
        # that gate downloads behind cookies/redirects.
        for backend in ("requests", "selenium"):
            progress(f"Direct download attempt via {backend}...")
            try:
                if backend == "requests":
                    download_with_requests(datasheet_url, local_path)
                else:
                    download_with_selenium(datasheet_url, local_path)
                if not _is_valid_pdf_file(local_path):
                    raise ValueError(f"Downloaded file is not a valid PDF: {local_path}")
                progress(f"Saved datasheet to local path: {local_path}")
                return local_path
            except Exception as exc:
                last_error = exc
                progress(f"{backend} download failed: {_short_exc(exc)}")
                if os.path.exists(local_path):
                    try:
                        os.remove(local_path)
                    except OSError:
                        pass
        progress(
            f"Direct datasheet download failed, will try search: {_short_exc(last_error)}"
        )
    elif datasheet_url:
        progress(f"Skipping direct datasheet download for placeholder/invalid URL: {datasheet_url!r}")

    # Try a clean part-name query first; the raw KiCad name (with library
    # prefix and underscores) often returns zero results on search engines.
    base_name = clean_part_name_for_search(part_name)
    queries = []
    if base_name:
        queries.append(f"{base_name} datasheet pdf")
    raw_query = f"{part_name} datasheet pdf"
    if raw_query not in queries:
        queries.append(raw_query)

    pdf_url = None
    search_error: Exception | None = None
    for query in queries:
        progress(f"DDG search: {query!r}")
        try:
            pdf_url = search_pdf_url(query)
        except Exception as exc:
            search_error = exc
            progress(f"Search failed: {type(exc).__name__}: {exc}")
            continue
        if pdf_url:
            break
        progress("No PDF link found in search results")

    if not pdf_url:
        direct_note = f"; direct download also failed ({last_error})" if last_error else ""
        search_note = f" (last error: {search_error})" if search_error else ""
        raise RuntimeError(
            f"No datasheet PDF found for {part_name}{search_note}{direct_note}. "
            "Check your internet connection and try again."
        )

    progress(f"Downloading PDF from search result: {pdf_url}")
    if use_selenium:
        download_with_selenium(pdf_url, local_path)
    else:
        try:
            download_with_requests(pdf_url, local_path)
        except Exception as exc:
            progress(f"Search result download failed, retrying with Selenium: {exc}")
            download_with_selenium(pdf_url, local_path)
    if not _is_valid_pdf_file(local_path):
        try:
            os.remove(local_path)
        except OSError:
            pass
        raise ValueError(f"Downloaded file is not a valid PDF: {local_path}")
    progress(f"Saved datasheet to local path: {local_path}")
    return local_path















