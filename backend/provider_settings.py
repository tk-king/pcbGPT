from __future__ import annotations

import re
import sqlite3
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from backend.runtime_paths import settings_db_path

_PROVIDER_NAME_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


@dataclass(frozen=True)
class ProviderModel:
    provider_name: str
    model_id: str
    model_name: str | None
    request_kwargs: dict[str, Any]
    created_at: str
    updated_at: str
    source: str = "database"


@dataclass(frozen=True)
class ProviderSettings:
    provider_name: str
    base_url: str
    api_key: str | None
    default_model: str | None
    models: tuple[ProviderModel, ...]
    is_default: bool
    created_at: str
    updated_at: str
    source: str = "database"


def normalize_provider_name(provider_name: str | None) -> str:
    cleaned = (provider_name or "").strip().lower()
    if not cleaned:
        raise ValueError("Provider name is required.")
    if not _PROVIDER_NAME_RE.fullmatch(cleaned):
        raise ValueError(
            "Provider name must use only letters, numbers, underscores, or hyphens."
        )
    return cleaned


def normalize_base_url(base_url: str | None) -> str:
    cleaned = (base_url or "").strip()
    if not cleaned:
        raise ValueError("Base URL is required.")
    if not (cleaned.startswith("http://") or cleaned.startswith("https://")):
        raise ValueError("Base URL must start with http:// or https://.")
    return cleaned.rstrip("/")


def normalize_model_name(model_name: str | None) -> str | None:
    cleaned = (model_name or "").strip()
    return cleaned or None


def normalize_provider_model(
    provider_name: str,
    model: dict[str, Any] | str,
) -> tuple[str, str | None, dict[str, Any] | None]:
    if isinstance(model, str):
        model_id = model.strip()
        model_name = None
        request_kwargs = None
    elif isinstance(model, dict):
        model_id = str(model.get("id") or "").strip()
        raw_name = model.get("name")
        model_name = str(raw_name).strip() if raw_name is not None else None
        if not model_name:
            openai_data = model.get("openai")
            if isinstance(openai_data, dict):
                raw_openai_name = openai_data.get("name")
                model_name = (
                    str(raw_openai_name).strip() if raw_openai_name is not None else None
                )
        info_data = model.get("info")
        if not model_name and isinstance(info_data, dict):
            raw_info_name = info_data.get("name")
            model_name = str(raw_info_name).strip() if raw_info_name is not None else None
        raw_request_kwargs = model.get("request_kwargs", model.get("requestKwargs"))
        if raw_request_kwargs is None:
            request_kwargs = None
        elif not isinstance(raw_request_kwargs, dict):
            raise ValueError(f"Model '{model_id}' request kwargs must be a JSON object.")
        else:
            try:
                request_kwargs = json.loads(json.dumps(raw_request_kwargs))
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"Model '{model_id}' request kwargs must contain JSON-compatible values."
                ) from exc
    else:
        raise ValueError("Unsupported provider model payload.")

    if not model_id:
        raise ValueError(f"Provider '{provider_name}' returned a model without an id.")

    if model_name and not model_name.strip():
        model_name = None
    return model_id, model_name, request_kwargs


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _settings_db_conn():
    db_path = settings_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(db_path)


def init_settings_db() -> None:
    with _settings_db_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS provider_settings (
                provider_name TEXT PRIMARY KEY,
                base_url TEXT NOT NULL,
                api_key TEXT,
                default_model TEXT,
                is_default INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        columns = {
            row[1] for row in conn.execute("PRAGMA table_info(provider_settings)").fetchall()
        }
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS provider_models (
                provider_name TEXT NOT NULL,
                model_id TEXT NOT NULL,
                model_name TEXT,
                request_kwargs_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (provider_name, model_id),
                FOREIGN KEY (provider_name) REFERENCES provider_settings(provider_name) ON DELETE CASCADE
            )
            """
        )
        model_columns = {
            row[1] for row in conn.execute("PRAGMA table_info(provider_models)").fetchall()
        }
        if "request_kwargs_json" not in model_columns:
            conn.execute(
                "ALTER TABLE provider_models ADD COLUMN request_kwargs_json TEXT NOT NULL DEFAULT '{}'"
            )
        if "model_ids" in columns:
            rows = conn.execute(
                """
                SELECT provider_name, model_ids, created_at, updated_at
                FROM provider_settings
                """
            ).fetchall()
            for provider_name, model_ids_raw, created_at, updated_at in rows:
                if not model_ids_raw:
                    continue
                try:
                    model_ids = json.loads(model_ids_raw)
                except Exception:
                    model_ids = []
                if not isinstance(model_ids, list):
                    continue
                for raw_model_id in model_ids:
                    model_id = str(raw_model_id or "").strip()
                    if not model_id:
                        continue
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO provider_models (
                            provider_name, model_id, model_name, created_at, updated_at
                        )
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (provider_name, model_id, None, created_at, updated_at),
                    )
        conn.commit()


def _list_provider_models(conn: sqlite3.Connection, provider_name: str) -> tuple[ProviderModel, ...]:
    rows = conn.execute(
        """
        SELECT provider_name, model_id, model_name, request_kwargs_json, created_at, updated_at
        FROM provider_models
        WHERE provider_name = ?
        ORDER BY COALESCE(NULLIF(model_name, ''), model_id) COLLATE NOCASE ASC, model_id COLLATE NOCASE ASC
        """,
        (provider_name,),
    ).fetchall()
    return tuple(
        ProviderModel(
            provider_name=row[0],
            model_id=row[1],
            model_name=row[2],
            request_kwargs=json.loads(row[3] or "{}"),
            created_at=row[4],
            updated_at=row[5],
        )
        for row in rows
    )


def _row_to_provider(conn: sqlite3.Connection, row) -> ProviderSettings | None:
    if not row:
        return None
    if len(row) >= 8:
        provider_name = row[0]
        base_url = row[1]
        api_key = row[2]
        default_model = row[3]
        is_default = row[-3]
        created_at = row[-2]
        updated_at = row[-1]
    else:
        (
            provider_name,
            base_url,
            api_key,
            default_model,
            is_default,
            created_at,
            updated_at,
        ) = row
    return ProviderSettings(
        provider_name=provider_name,
        base_url=base_url,
        api_key=api_key,
        default_model=default_model,
        models=_list_provider_models(conn, provider_name),
        is_default=bool(is_default),
        created_at=created_at,
        updated_at=updated_at,
    )


def get_provider_settings(provider_name: str | None) -> ProviderSettings | None:
    try:
        normalized = normalize_provider_name(provider_name)
    except ValueError:
        return None
    init_settings_db()
    with _settings_db_conn() as conn:
        row = conn.execute(
            """
            SELECT provider_name, base_url, api_key, default_model, is_default, created_at, updated_at
            FROM provider_settings
            WHERE provider_name = ?
            """,
            (normalized,),
        ).fetchone()
        return _row_to_provider(conn, row)


def list_provider_settings() -> list[ProviderSettings]:
    init_settings_db()
    with _settings_db_conn() as conn:
        rows = conn.execute(
            """
            SELECT provider_name, base_url, api_key, default_model, is_default, created_at, updated_at
            FROM provider_settings
            ORDER BY is_default DESC, updated_at DESC, provider_name ASC
            """
        ).fetchall()
        return [
            provider
            for row in rows
            if (provider := _row_to_provider(conn, row)) is not None
        ]


def get_default_provider_settings() -> ProviderSettings | None:
    init_settings_db()
    with _settings_db_conn() as conn:
        row = conn.execute(
            """
            SELECT provider_name, base_url, api_key, default_model, is_default, created_at, updated_at
            FROM provider_settings
            ORDER BY is_default DESC, updated_at DESC
            LIMIT 1
            """
        ).fetchone()
        return _row_to_provider(conn, row)


def save_provider_settings(
    *,
    provider_name: str,
    base_url: str,
    api_key: str | None = None,
    default_model: str | None = None,
    models: list[dict[str, Any] | str] | tuple[dict[str, Any] | str, ...] | None = None,
    preserve_existing_api_key: bool = True,
    make_default: bool = True,
) -> ProviderSettings:
    normalized_provider = normalize_provider_name(provider_name)
    normalized_base_url = normalize_base_url(base_url)
    normalized_model = normalize_model_name(default_model)
    normalized_api_key = (api_key or "").strip() or None
    existing = get_provider_settings(normalized_provider)
    if preserve_existing_api_key and normalized_api_key is None and existing is not None:
        normalized_api_key = existing.api_key

    now = _utc_now()
    created_at = existing.created_at if existing else now
    existing_models_by_id = {model.model_id: model for model in (existing.models if existing else ())}
    normalized_models: list[tuple[str, str | None, dict[str, Any], str, str]] = []
    seen_model_ids: set[str] = set()
    for raw_model in models or []:
        model_id, model_name, request_kwargs = normalize_provider_model(
            normalized_provider,
            raw_model,
        )
        if model_id in seen_model_ids:
            continue
        seen_model_ids.add(model_id)
        existing_model = existing_models_by_id.get(model_id)
        normalized_models.append(
            (
                model_id,
                model_name,
                request_kwargs
                if request_kwargs is not None
                else dict(existing_model.request_kwargs) if existing_model else {},
                existing_model.created_at if existing_model else now,
                now,
            )
        )
    if normalized_models:
        model_ids = {model_id for model_id, _, _, _, _ in normalized_models}
        if normalized_model and normalized_model not in model_ids:
            raise ValueError(
                f"Default model '{normalized_model}' was not returned by provider '{normalized_provider}'."
            )
        if normalized_model is None:
            normalized_model = normalized_models[0][0]

    init_settings_db()
    with _settings_db_conn() as conn:
        if make_default:
            conn.execute("UPDATE provider_settings SET is_default = 0")
        conn.execute(
            """
            INSERT INTO provider_settings (
                provider_name, base_url, api_key, default_model, is_default, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(provider_name) DO UPDATE SET
                base_url = excluded.base_url,
                api_key = excluded.api_key,
                default_model = excluded.default_model,
                is_default = excluded.is_default,
                updated_at = excluded.updated_at
            """,
            (
                normalized_provider,
                normalized_base_url,
                normalized_api_key,
                normalized_model,
                1 if make_default else 0,
                created_at,
                now,
            ),
        )
        conn.execute(
            "DELETE FROM provider_models WHERE provider_name = ?",
            (normalized_provider,),
        )
        if normalized_models:
            conn.executemany(
                """
                INSERT INTO provider_models (
                    provider_name, model_id, model_name, request_kwargs_json, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        normalized_provider,
                        model_id,
                        model_name,
                        json.dumps(request_kwargs, separators=(",", ":"), sort_keys=True),
                        model_created_at,
                        model_updated_at,
                    )
                    for model_id, model_name, request_kwargs, model_created_at, model_updated_at in normalized_models
                ],
            )
        conn.commit()
    saved = get_provider_settings(normalized_provider)
    if saved is None:
        raise RuntimeError("Provider settings were not saved.")
    return saved


def save_provider_model_request_kwargs(
    *,
    provider_name: str,
    model_id: str,
    request_kwargs: dict[str, Any],
) -> ProviderSettings:
    normalized_provider = normalize_provider_name(provider_name)
    normalized_model_id = str(model_id or "").strip()
    if not normalized_model_id:
        raise ValueError("Model id is required.")
    if not isinstance(request_kwargs, dict):
        raise ValueError("Model request kwargs must be a JSON object.")
    reserved = {
        "model",
        "messages",
        "input",
        "tools",
        "tool_choice",
        "stream",
        "stream_options",
    }
    conflicts = sorted(reserved.intersection(request_kwargs))
    if conflicts:
        raise ValueError(
            "Model request kwargs cannot override managed fields: "
            + ", ".join(conflicts)
        )
    try:
        serialized = json.dumps(request_kwargs, separators=(",", ":"), sort_keys=True)
    except (TypeError, ValueError) as exc:
        raise ValueError("Model request kwargs must contain JSON-compatible values.") from exc

    init_settings_db()
    now = _utc_now()
    with _settings_db_conn() as conn:
        cursor = conn.execute(
            """
            UPDATE provider_models
            SET request_kwargs_json = ?, updated_at = ?
            WHERE provider_name = ? AND model_id = ?
            """,
            (serialized, now, normalized_provider, normalized_model_id),
        )
        if cursor.rowcount != 1:
            raise ValueError(
                f"Model '{normalized_model_id}' is not saved for provider '{normalized_provider}'."
            )
        conn.execute(
            "UPDATE provider_settings SET updated_at = ? WHERE provider_name = ?",
            (now, normalized_provider),
        )
        conn.commit()
    saved = get_provider_settings(normalized_provider)
    if saved is None:
        raise RuntimeError("Provider model settings were not saved.")
    return saved


def delete_provider_settings(provider_name: str | None) -> bool:
    """Delete a provider and its saved models. Returns True if it existed."""
    try:
        normalized = normalize_provider_name(provider_name)
    except ValueError:
        return False
    init_settings_db()
    with _settings_db_conn() as conn:
        conn.execute(
            "DELETE FROM provider_models WHERE provider_name = ?",
            (normalized,),
        )
        cursor = conn.execute(
            "DELETE FROM provider_settings WHERE provider_name = ?",
            (normalized,),
        )
        conn.commit()
    return cursor.rowcount > 0


def api_key_preview(api_key: str | None) -> str | None:
    if not api_key:
        return None
    if len(api_key) <= 4:
        return "*" * len(api_key)
    return f"...{api_key[-4:]}"


def provider_settings_public_payload(provider: ProviderSettings | None) -> dict | None:
    if provider is None:
        return None
    return {
        "provider_name": provider.provider_name,
        "base_url": provider.base_url,
        "default_model": provider.default_model,
        "models": [
            {
                "id": model.model_id,
                "name": model.model_name,
                "request_kwargs": model.request_kwargs,
            }
            for model in provider.models
        ],
        "has_api_key": bool(provider.api_key),
        "api_key_preview": api_key_preview(provider.api_key),
        "is_default": provider.is_default,
        "source": provider.source,
        "updated_at": provider.updated_at,
    }
