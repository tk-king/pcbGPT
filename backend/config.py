from __future__ import annotations

import os
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any

from dotenv import load_dotenv
import httpx
from openai import AsyncOpenAI

from backend.core.agents.model_openai import OpenAIChatModel
from backend.provider_settings import (
    ProviderSettings,
    get_default_provider_settings,
    get_provider_settings,
    list_provider_settings,
    provider_settings_public_payload,
    save_provider_model_request_kwargs,
    save_provider_settings,
)

# Load environment variables from .env file
load_dotenv()

KICAD_SYMBOL_PATH = os.getenv("KICAD_SYMBOL_PATH", None)
KICAD_FOOTPRINT_PATH = os.getenv("KICAD_FOOTPRINT_PATH", None)

DEFAULT_DATASHEET_TOOL = (os.getenv("DATASHEET_TOOL") or "vision").strip().lower() or "vision"
if DEFAULT_DATASHEET_TOOL not in {"vision", "text"}:
    raise ValueError(
        f"Invalid DATASHEET_TOOL={DEFAULT_DATASHEET_TOOL!r}. Expected 'vision' or 'text'."
    )
_DATASHEET_TOOL_MODE: ContextVar[str] = ContextVar(
    "pcbgpt_datasheet_tool_mode",
    default=DEFAULT_DATASHEET_TOOL,
)
def normalize_selectable_model_name(model_name: str | None, default: str | None = None) -> str | None:
    raw = model_name if model_name is not None else default
    if raw is None:
        return None
    cleaned = str(raw).strip()
    if not cleaned:
        return normalize_selectable_model_name(default, default=None)
    custom_provider_ref = _custom_provider_model_parts(cleaned)
    if custom_provider_ref is not None:
        provider_name, custom_model = custom_provider_ref
        return f"{provider_name}.{custom_model}"
    raise ValueError(
        f"Unsupported model '{model_name}'. Add the provider through the UI and choose one of its saved models."
    )




def get_datasheet_tool_mode() -> str:
    return _DATASHEET_TOOL_MODE.get()






# Base directory for temporary working data (downloads, caches, etc.).
# Default: system temp dir / "pcbgpt"; override with PCBGPT_TMP_DIR.
TMP_DIR = os.getenv("PCBGPT_TMP_DIR") or os.path.join(
    os.path.abspath(os.getenv("TMPDIR", "/tmp")),
    "pcbgpt",
)


def _normalize_openai_compatible_base_url(url: str | None) -> str | None:
    if not url:
        return None
    cleaned = url.strip().rstrip("/")
    lowered = cleaned.lower()
    if lowered.endswith("/v1") or "/v1/" in lowered:
        return cleaned
    return f"{cleaned}/v1"



def _provider_settings_for_name(provider_name: str) -> ProviderSettings | None:
    return get_provider_settings(provider_name)


def _custom_provider_model_parts(model_name: str) -> tuple[str, str] | None:
    cleaned = (model_name or "").strip()
    if "." not in cleaned:
        return None
    provider_name, custom_model = cleaned.split(".", 1)
    provider_name = provider_name.strip().lower()
    custom_model = custom_model.strip()
    if not provider_name or not custom_model:
        return None
    provider_settings = _provider_settings_for_name(provider_name)
    if provider_settings is None:
        return None
    if not any(model.model_id == custom_model for model in provider_settings.models):
        return None
    return provider_name, custom_model


def custom_provider_model_value(provider_name: str, model_name: str) -> str:
    provider = provider_name.strip().lower()
    model = model_name.strip()
    if not provider:
        raise ValueError("Provider name is required.")
    if not model:
        raise ValueError("Model name is required.")
    return f"{provider}.{model}"


def save_custom_provider_settings(
    *,
    provider_name: str,
    base_url: str,
    api_key: str | None = None,
    default_model: str | None = None,
    models: list[dict[str, Any] | str] | tuple[dict[str, Any] | str, ...] | None = None,
    preserve_existing_api_key: bool = True,
    make_default: bool = True,
) -> ProviderSettings:
    return save_provider_settings(
        provider_name=provider_name,
        base_url=base_url,
        api_key=api_key,
        default_model=default_model,
        models=models,
        preserve_existing_api_key=preserve_existing_api_key,
        make_default=make_default,
    )


def save_custom_provider_model_request_kwargs(
    *,
    provider_name: str,
    model_id: str,
    request_kwargs: dict[str, Any],
) -> ProviderSettings:
    return save_provider_model_request_kwargs(
        provider_name=provider_name,
        model_id=model_id,
        request_kwargs=request_kwargs,
    )


def list_public_custom_provider_settings() -> list[dict]:
    return [
        payload
        for provider in list_provider_settings()
        if (payload := provider_settings_public_payload(provider)) is not None
    ]


def default_public_custom_provider_settings() -> dict | None:
    return provider_settings_public_payload(get_default_provider_settings())


def list_selectable_providers() -> list[dict[str, Any]]:
    providers = list_provider_settings()
    payloads: list[dict[str, Any]] = []
    for provider in providers:
        payload = provider_settings_public_payload(provider)
        if payload is not None:
            payloads.append(payload)
    return payloads


def _active_credentials(provider: str) -> tuple[str | None, str | None]:
    custom_provider = _provider_settings_for_name(provider)
    if custom_provider is not None:
        return custom_provider.api_key, custom_provider.base_url
    raise ValueError(
        f"Provider '{provider}' is not configured. Add it through the UI first."
    )


def _build_openai_client(
    provider: str,
    *,
    api_key: str | None = None,
    base_url: str | None = None,
    default_headers: dict[str, str] | None = None,
) -> AsyncOpenAI:
    if api_key is None and base_url is None:
        api_key, base_url = _active_credentials(provider)
    custom_provider = _provider_settings_for_name(provider)
    if custom_provider is not None:
        headers: dict[str, str] = dict(default_headers or {})
        kwargs: dict[str, object] = {
            "api_key": api_key or "EMPTY",
            "base_url": _normalize_openai_compatible_base_url(base_url),
        }
        if headers:
            kwargs["default_headers"] = headers
        return AsyncOpenAI(**kwargs)
    raise ValueError(
        f"Provider '{provider}' is not configured. Add it through the UI first."
    )


@dataclass(frozen=True)
class ResolvedModelConfig:
    provider: str
    model_name: str
    api_key: str | None
    base_url: str | None
    default_headers: dict[str, str] | None = None
    request_kwargs: dict[str, Any] | None = None


def resolve_model_config(model_name: str) -> ResolvedModelConfig:
    custom_provider_ref = _custom_provider_model_parts(model_name)
    if custom_provider_ref is not None:
        provider_name, resolved_name = custom_provider_ref
        provider_settings = _provider_settings_for_name(provider_name)
        if provider_settings is None:
            raise ValueError(
                f"Custom provider '{provider_name}' is not configured. Save its Base URL and API key first."
            )
        provider_model = next(
            model for model in provider_settings.models if model.model_id == resolved_name
        )
        return ResolvedModelConfig(
            provider=provider_name,
            model_name=resolved_name,
            api_key=provider_settings.api_key,
            base_url=provider_settings.base_url,
            default_headers=None,
            request_kwargs=dict(provider_model.request_kwargs),
        )
    raise ValueError(
        f"Unsupported model '{model_name}'. Add the provider through the UI and choose one of its saved models."
    )


def build_chat_model(model_name: str) -> OpenAIChatModel:
    return build_chat_model_with_temperature(model_name)


def build_chat_model_with_temperature(
    model_name: str,
    *,
    temperature: float | None = None,
) -> OpenAIChatModel:
    resolved = resolve_model_config(model_name)
    client = _build_openai_client(
        resolved.provider,
        api_key=resolved.api_key,
        base_url=resolved.base_url,
        default_headers=resolved.default_headers,
    )
    is_gpt_5_3_codex = resolved.model_name.strip().lower().endswith(
        "gpt-5.3-codex"
    )
    return OpenAIChatModel(
        client,
        resolved.model_name,
        temperature=None if is_gpt_5_3_codex else temperature,
        reasoning_effort="high" if is_gpt_5_3_codex else None,
        request_kwargs=resolved.request_kwargs or {},
    )


def provider_models_url(base_url: str) -> str:
    return f"{_normalize_openai_compatible_base_url(base_url)}/models"


def _provider_model_sort_key(model: dict[str, str | None]) -> tuple[str, str]:
    display_name = str(model.get("name") or "").strip().lower()
    model_id = str(model.get("id") or "").strip().lower()
    return (display_name or model_id, model_id)


def normalize_provider_models_payload(data: Any) -> list[dict[str, str | None]]:
    if not isinstance(data, dict):
        raise ValueError("Provider /models response must be a JSON object.")
    raw_models = data.get("data")
    if not isinstance(raw_models, list):
        raise ValueError("Provider /models response must contain a 'data' list.")
    models: list[dict[str, str | None]] = []
    seen_model_ids: set[str] = set()
    for raw_model in raw_models:
        if not isinstance(raw_model, dict):
            continue
        model_id = str(raw_model.get("id") or "").strip()
        if not model_id or model_id in seen_model_ids:
            continue
        seen_model_ids.add(model_id)
        model_name = raw_model.get("name")
        if model_name is None:
            info = raw_model.get("info")
            if isinstance(info, dict):
                model_name = info.get("name")
        if model_name is None:
            openai_data = raw_model.get("openai")
            if isinstance(openai_data, dict):
                model_name = openai_data.get("name")
        normalized_name = str(model_name).strip() if model_name is not None else None
        models.append({"id": model_id, "name": normalized_name or None})
    if not models:
        raise ValueError("Provider /models response did not return any usable models.")
    models.sort(key=_provider_model_sort_key)
    return models


async def fetch_provider_models(base_url: str, api_key: str | None = None) -> list[dict[str, str | None]]:
    url = provider_models_url(base_url)
    headers = {"Accept": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    try:
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            payload = response.json()
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text.strip() or str(exc)
        raise ValueError(f"Provider models lookup failed ({exc.response.status_code}): {detail}") from exc
    except httpx.HTTPError as exc:
        raise ValueError(f"Provider models lookup failed: {exc}") from exc
    except ValueError as exc:
        raise ValueError(f"Provider models lookup failed: invalid JSON response from {url}.") from exc
    return normalize_provider_models_payload(payload)
