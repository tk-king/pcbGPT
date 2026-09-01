import base64
import os
import re
import shutil
import sqlite3
import zipfile
from dataclasses import asdict
from pathlib import Path

from fastapi import HTTPException

from backend.agent.Core.agent import AgentContext as AgentContext
from backend.agent.tools.app_state import _SESSION_CONTEXTS
from backend.core.agents import Agent
from backend.runtime_paths import settings_db_path, sync_root
import backend.config as config_module


def _init_context(session_id: str) -> dict:
    saved_ctx = _SESSION_CONTEXTS.get(session_id)
    if isinstance(saved_ctx, dict):
        return saved_ctx.copy()
    if saved_ctx:
        return asdict(saved_ctx)
    return asdict(AgentContext())


def _session_workspace(session_id: str) -> Path:
    root = sync_root() / session_id
    root.mkdir(parents=True, exist_ok=True)
    workspace = root / "workspace"
    if workspace.exists():
        shutil.rmtree(workspace)
    workspace.mkdir(parents=True, exist_ok=True)
    return workspace


def _extract_archive_to_workspace(session_id: str, archive_b64: str) -> Path:
    try:
        data = base64.b64decode(archive_b64)
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=f"Invalid archive data: {exc}"
        ) from exc

    workspace = _session_workspace(session_id)
    tmp_zip = workspace.parent / "upload.zip"
    tmp_zip.write_bytes(data)
    workspace_root = workspace.resolve()
    try:
        with zipfile.ZipFile(tmp_zip, "r") as zf:
            for member in zf.infolist():
                dest = workspace / member.filename
                dest_resolved = dest.resolve()
                if not str(dest_resolved).startswith(str(workspace_root)):
                    raise HTTPException(
                        status_code=400, detail="Archive contains unsafe paths."
                    )
                if member.is_dir():
                    dest.mkdir(parents=True, exist_ok=True)
                else:
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(member, "r") as src, dest.open("wb") as dst:
                        shutil.copyfileobj(src, dst)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=f"Failed to extract archive: {exc}"
        ) from exc
    finally:
        tmp_zip.unlink(missing_ok=True)
    return workspace


def _locate_project_folder(base: Path) -> Path:
    direct = list(base.glob("*.kicad_sch"))
    if direct:
        return base
    subdirs = [p for p in base.iterdir() if p.is_dir()]
    if len(subdirs) == 1 and not direct:
        nested = _locate_project_folder(subdirs[0])
        if nested:
            return nested
    rglobs = list(base.rglob("*.kicad_sch"))
    if rglobs:
        return rglobs[0].parent
    return base


def _filter_context_for_dataclass(context: dict | None, context_cls) -> dict:
    if not isinstance(context, dict):
        return {}
    fields = getattr(context_cls, "__dataclass_fields__", None)
    if not fields:
        return context
    return {key: value for key, value in context.items() if key in fields}


def _merge_context(existing: dict | None, updates: dict | None) -> dict:
    merged: dict = {}
    if isinstance(existing, dict):
        merged.update(existing)
    if isinstance(updates, dict):
        merged.update(updates)
    return merged


def _build_sync_prefix(context: dict) -> str | None:
    if not context:
        return None
    snippets: list[str] = []
    project_name = context.get("kicad_project_name")
    if project_name:
        snippets.append(f"Synced project name: {project_name}")
    project_path = context.get("kicad_project_path")
    if project_path:
        snippets.append(f"Synced folder path: {project_path}")
    circuit_code = context.get("circuit")
    if circuit_code:
        snippets.append("Latest circuit code:\n```\n" + circuit_code + "\n```")
    imported_netlist = context.get("imported_netlist")
    if imported_netlist and not circuit_code:
        snippets.append("Latest imported netlist:\n```\n" + imported_netlist + "\n```")
    if not snippets:
        return None
    return (
        "Use the latest synced design context below when answering.\n"
        + "\n".join(snippets)
        + "\n\nUser request:\n"
    )


def _usage_metrics_payload(context_wrapper, agent) -> dict | None:
    if context_wrapper is None or not hasattr(context_wrapper, "usage"):
        return None
    usage = context_wrapper.usage
    model = getattr(agent, "model", None)
    model_name = getattr(model, "model_name", str(model)) if model is not None else "unknown"
    return {
        "model_name": model_name,
        "usage": {
            "requests": int(getattr(usage, "requests", 0) or 0),
            "input_tokens": int(getattr(usage, "input_tokens", 0) or 0),
            "output_tokens": int(getattr(usage, "output_tokens", 0) or 0),
            "total_tokens": int(getattr(usage, "total_tokens", 0) or 0),
            "max_total_tokens": int(getattr(usage, "max_total_tokens", 0) or 0),
            "input_tokens_details": getattr(usage, "input_tokens_details", {}) or {},
            "output_tokens_details": getattr(usage, "output_tokens_details", {}) or {},
        },
    }


def _build_agent_with_generation_model(base_agent: Agent, model_name: str | None) -> Agent:
    if not model_name:
        raise ValueError("No generation LLM configured.")
    model = config_module.build_chat_model(model_name)
    return Agent(
        name=base_agent.name,
        instructions=base_agent.instructions,
        model=model,
        tools=base_agent.tools,
        output_type=base_agent.output_type,
        tool_choice_on_first_turn=base_agent.tool_choice_on_first_turn,
    )


_SCHEMATIC_DIAGNOSIS_RE = re.compile(
    r"\b(error|errors|wrong|issue|issues|problem|problems|inspect|review|troubleshoot|"
    r"diagnose|diagnosis|debug|check|why|fault|faults)\b",
    re.IGNORECASE,
)
_SCHEMATIC_MODIFICATION_RE = re.compile(
    r"\b(fix|modify|update|change|correct|repair|rewrite|generate|build|create)\b",
    re.IGNORECASE,
)


def _configure_agent_for_interactive_request(
    agent: Agent,
    user_input: str,
    context: dict,
) -> Agent:
    has_schematic = bool(context.get("circuit") or context.get("imported_netlist"))
    is_diagnosis = bool(_SCHEMATIC_DIAGNOSIS_RE.search(user_input))
    requests_modification = bool(_SCHEMATIC_MODIFICATION_RE.search(user_input))
    if not (has_schematic and is_diagnosis and not requests_modification):
        return agent

    grounding_tools = {"search_components", "obtain_needed_information"}
    agent.tools = [tool for tool in agent.tools or [] if tool.name in grounding_tools]
    agent.tool_choice_on_first_turn = "required"
    return agent


def _apply_system_settings_to_context(context_obj, settings: dict) -> None:
    if hasattr(context_obj, "generation_model_name"):
        context_obj.generation_model_name = settings["generation_model"]
    if hasattr(context_obj, "validation_model_name"):
        context_obj.validation_model_name = settings["validation_model"]
    if hasattr(context_obj, "validation_enabled"):
        context_obj.validation_enabled = settings["validation_enabled"]


def _coerce_bool(value, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    return bool(value)


def _settings_db_conn():
    db_path = settings_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(db_path)


def _init_system_settings_table() -> None:
    with _settings_db_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS system_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        conn.commit()


def _get_system_setting(key: str) -> str | None:
    _init_system_settings_table()
    with _settings_db_conn() as conn:
        row = conn.execute(
            "SELECT value FROM system_settings WHERE key = ?",
            (key,),
        ).fetchone()
        return row[0] if row else None


def _set_system_setting(key: str, value: str | None) -> None:
    if value is None:
        return
    _init_system_settings_table()
    with _settings_db_conn() as conn:
        conn.execute(
            "INSERT INTO system_settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
        conn.commit()


def clear_system_settings_for_provider(provider_name: str) -> None:
    """Remove generation/validation model settings pointing at a provider."""
    prefix = f"{(provider_name or '').strip().lower()}.%"
    _init_system_settings_table()
    with _settings_db_conn() as conn:
        conn.execute(
            "DELETE FROM system_settings WHERE key IN ('generation_model', 'validation_model') "
            "AND value LIKE ?",
            (prefix,),
        )
        conn.commit()


def save_system_settings(settings: dict) -> None:
    generation_model = settings.get("generation_model")
    validation_model = settings.get("validation_model")
    validation_enabled = settings.get("validation_enabled")
    if generation_model:
        _set_system_setting("generation_model", str(generation_model))
    if validation_model:
        _set_system_setting("validation_model", str(validation_model))
    if isinstance(validation_enabled, bool):
        _set_system_setting("validation_enabled", "1" if validation_enabled else "0")


def _default_system_settings() -> dict:
    generation_model = None
    validation_model = None
    saved_generation_model = _get_system_setting("generation_model")
    saved_validation_model = _get_system_setting("validation_model")
    saved_validation_enabled = _get_system_setting("validation_enabled")
    try:
        if saved_generation_model:
            generation_model = config_module.normalize_selectable_model_name(
                saved_generation_model,
                default=None,
            )
    except ValueError:
        pass
    try:
        if saved_validation_model:
            validation_model = config_module.normalize_selectable_model_name(
                saved_validation_model,
                default=None,
            )
    except ValueError:
        pass

    return {
        "generation_model": generation_model,
        "validation_model": validation_model,
        "validation_enabled": _coerce_bool(
            saved_validation_enabled,
            _coerce_bool(
                os.getenv("AGENT_USE_VALIDATOR_FEEDBACK"),
                False,
            ),
        ),
    }


def _save_custom_provider_from_payload(payload: dict | None):
    if not isinstance(payload, dict):
        return None
    provider_name = payload.get("provider_name")
    base_url = payload.get("base_url")
    model_name = payload.get("model_name")
    api_key = payload.get("api_key")
    if provider_name is None and base_url is None and model_name is None and api_key is None:
        return None
    return config_module.save_custom_provider_settings(
        provider_name=str(provider_name or ""),
        base_url=str(base_url or ""),
        api_key=str(api_key) if api_key is not None else None,
        default_model=str(model_name) if model_name is not None else None,
    )


def _extract_system_settings(message: dict) -> dict:
    defaults = _default_system_settings()
    raw_settings = message.get("system_settings")
    if not isinstance(raw_settings, dict):
        raw_settings = {}

    _save_custom_provider_from_payload(raw_settings.get("custom_provider"))

    generation_model = raw_settings.get("generation_model")
    validation_model = raw_settings.get("validation_model")
    generation_model = (
        config_module.normalize_selectable_model_name(generation_model, default=None)
        if generation_model is not None
        else defaults["generation_model"]
    )
    validation_model = (
        config_module.normalize_selectable_model_name(validation_model, default=None)
        if validation_model is not None
        else defaults["validation_model"]
    )
    validation_enabled = (
        raw_settings.get("validation_enabled", defaults["validation_enabled"])
        if "validation_enabled" in raw_settings
        else defaults["validation_enabled"]
    )
    if not generation_model:
        raise ValueError("No generation model is configured. Add a provider in the UI first.")
    if validation_enabled and not validation_model:
        raise ValueError("No validation model is configured. Add a provider in the UI first.")
    settings = {
        "generation_model": generation_model,
        "validation_model": validation_model,
        "validation_enabled": validation_enabled,
    }
    save_system_settings(settings)
    return settings
