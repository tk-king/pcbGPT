from __future__ import annotations

import base64
import re
import time
from typing import Any

from langchain_openai import ChatOpenAI

import backend.config as config_module
from backend.config import (
    _normalize_openai_compatible_base_url,
)
from backend.utils.PDFDownloader import progress as pdf_progress
from backend.utils.tool_progress import report_tool_progress

from .read_datasheet_settings import (
    DEBUG_PROGRESS,
    OPENAI_REQUEST_TIMEOUT_S,
)


def progress(msg: str, *, step: str | None = None, t0: float | None = None) -> None:
    # Always forward to any registered UI progress sink (agent tool calls);
    # verbose console printing stays gated behind DEBUG_PROGRESS.
    report_tool_progress(msg)
    if not DEBUG_PROGRESS:
        return
    ts = time.strftime("%H:%M:%S")
    elapsed = ""
    if t0 is not None:
        elapsed = f" (+{time.time() - t0:.2f}s)"
    prefix = f"[{ts}]{elapsed}"
    if step is not None:
        prefix += f" [{step}]"
    pdf_progress(f"{prefix} {msg}")


def build_langchain_chat_model(model: str) -> ChatOpenAI:
    resolved = config_module.resolve_model_config(model)

    kwargs: dict[str, Any] = {
        "model": resolved.model_name,
        "request_timeout": OPENAI_REQUEST_TIMEOUT_S,
    }
    if resolved.api_key:
        kwargs["api_key"] = resolved.api_key
    if resolved.base_url:
        kwargs["base_url"] = _normalize_openai_compatible_base_url(resolved.base_url)
    if resolved.default_headers:
        kwargs["default_headers"] = resolved.default_headers
    return ChatOpenAI(**kwargs)




def llm_debug_identity(llm: ChatOpenAI) -> tuple[str, str]:
    model_name = (
        getattr(llm, "model_name", None)
        or getattr(llm, "model", None)
        or "<unknown-model>"
    )
    base_url = (
        getattr(llm, "openai_api_base", None)
        or getattr(llm, "base_url", None)
        or "<default-base-url>"
    )
    return str(model_name), str(base_url)


def image_path_to_data_url(image_path: str) -> str:
    with open(image_path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("utf-8")
    return f"data:image/png;base64,{encoded}"


def safe_filename(text: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", text.strip())
    cleaned = cleaned.strip("._")
    return cleaned or "unknown"


def response_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"])
            elif hasattr(item, "text") and isinstance(item.text, str):
                parts.append(item.text)
        return "\n".join(parts)
    return str(content)
