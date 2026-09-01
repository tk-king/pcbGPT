import json
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from backend.runtime_paths import custom_sessions_db_path, sessions_db_path, sync_root
from backend.agent.tools.app_state import _SESSION_CONTEXTS, _SESSION_HISTORIES


def _db_conn():
    db_path = sessions_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(db_path)


def init_db():
    with _db_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                context_json TEXT NOT NULL,
                history_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        columns = {
            row[1] for row in conn.execute("PRAGMA table_info(sessions)").fetchall()
        }
        if "custom_title" not in columns:
            conn.execute("ALTER TABLE sessions ADD COLUMN custom_title TEXT")
        _migrate_legacy_v2_table(conn)
        conn.commit()


def _migrate_legacy_v2_table(conn) -> None:
    """Copy data from the legacy ``v2_sessions`` table, then drop it."""
    legacy_tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    if "v2_sessions" not in legacy_tables:
        return
    legacy_columns = {
        row[1]
        for row in conn.execute("PRAGMA table_info(v2_sessions)").fetchall()
    }
    custom_title = "custom_title" if "custom_title" in legacy_columns else "NULL"
    conn.execute(
        f"""
        INSERT OR IGNORE INTO sessions (session_id, context_json, history_json, updated_at, custom_title)
        SELECT session_id, context_json, history_json, updated_at, {custom_title}
        FROM v2_sessions
        """
    )
    conn.execute("DROP TABLE v2_sessions")


def load_session(session_id: str):
    with _db_conn() as conn:
        cur = conn.execute(
            "SELECT context_json, history_json FROM sessions WHERE session_id = ?",
            (session_id,),
        )
        row = cur.fetchone()
    if not row:
        return None, None
    context_json, history_json = row
    try:
        context = json.loads(context_json)
    except Exception:
        context = None
    try:
        history = json.loads(history_json)
    except Exception:
        history = None
    if history is not None:
        normalized = normalize_history(history)
        if normalized != history and context is not None:
            save_session(session_id, context, normalized)
        history = normalized
    return context, history


def save_session(session_id: str, context: dict, history: list[dict]):
    payload_context = json.dumps(context, ensure_ascii=False)
    payload_history = json.dumps(history, ensure_ascii=False)
    updated_at = datetime.now(timezone.utc).isoformat()
    with _db_conn() as conn:
        conn.execute(
            """
            INSERT INTO sessions (session_id, context_json, history_json, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(session_id) DO UPDATE SET
                context_json = excluded.context_json,
                history_json = excluded.history_json,
                updated_at = excluded.updated_at
            """,
            (session_id, payload_context, payload_history, updated_at),
        )
        conn.commit()


def extract_history_title(history: list[dict]) -> str | None:
    for item in history:
        if item.get("role") == "user" and item.get("content"):
            title = str(item["content"]).strip()
            if title:
                return title.split("\n", 1)[0][:80]
    return None


def normalize_custom_title(title: str | None) -> str | None:
    if title is None:
        return None
    cleaned = title.strip()
    if not cleaned:
        return None
    return cleaned[:120]


def set_session_custom_title(session_id: str, title: str | None) -> bool:
    normalized = normalize_custom_title(title)
    with _db_conn() as conn:
        cur = conn.execute(
            "UPDATE sessions SET custom_title = ? WHERE session_id = ?",
            (normalized, session_id),
        )
        conn.commit()
    return cur.rowcount > 0


def list_sessions(limit: int = 50):
    with _db_conn() as conn:
        cur = conn.execute(
            """
            SELECT session_id, context_json, history_json, updated_at, custom_title
            FROM sessions
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            (limit,),
        )
        rows = cur.fetchall()
    sessions = []
    for session_id, context_json, history_json, updated_at, custom_title in rows:
        try:
            context = json.loads(context_json)
        except Exception:
            context = {}
        try:
            history = json.loads(history_json)
        except Exception:
            history = []
        auto_title = extract_history_title(history)
        display_title = normalize_custom_title(custom_title) or auto_title
        sessions.append(
            {
                "session_id": session_id,
                "title": display_title or "Untitled chat",
                "updated_at": updated_at,
                "has_pdf": bool(context.get("schematic_pdf_base64")),
            }
        )
    return sessions


def session_exists(session_id: str) -> bool:
    with _db_conn() as conn:
        cur = conn.execute(
            "SELECT 1 FROM sessions WHERE session_id = ? LIMIT 1",
            (session_id,),
        )
        return cur.fetchone() is not None


def delete_session_row(session_id: str) -> bool:
    with _db_conn() as conn:
        cur = conn.execute(
            "DELETE FROM sessions WHERE session_id = ?", (session_id,)
        )
        conn.commit()
        return cur.rowcount > 0


def delete_core_agents_session(
    session_id: str,
    *,
    db_path: str | None = None,
) -> None:
    tables = {
        "sessions": "core_agents_sessions",
        "messages": "core_agents_messages",
        "events": "core_agents_events",
    }
    try:
        resolved_path = Path(db_path) if db_path else custom_sessions_db_path()
        resolved_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(resolved_path) as conn:
            existing = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            for table in (tables["messages"], tables["events"], tables["sessions"]):
                if table not in existing:
                    continue
                conn.execute(f"DELETE FROM {table} WHERE session_id = ?", (session_id,))
            conn.commit()
    except Exception:
        return


def delete_sync_workspace(session_id: str) -> None:
    root = sync_root() / session_id
    try:
        if root.exists():
            shutil.rmtree(root)
    except Exception:
        return


def normalize_history(history: list[dict]) -> list[dict]:
    result: list[dict] = []
    pending_content: str | None = None
    pending_tool_ids: set[str] | None = None

    def flush_pending():
        nonlocal pending_content, pending_tool_ids
        if pending_content:
            result.append(
                {"role": "assistant", "content": pending_content, "tool_calls": None}
            )
        pending_content = None
        pending_tool_ids = None

    for item in history:
        role = item.get("role")
        if role == "user":
            flush_pending()
            result.append(item)
            continue

        if role == "assistant":
            tool_calls = item.get("tool_calls")
            content = item.get("content")
            if tool_calls:
                flush_pending()
                result.append(
                    {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": tool_calls,
                    }
                )
                if content:
                    pending_content = content
                    ids = {
                        call.get("id")
                        for call in tool_calls
                        if isinstance(call, dict) and call.get("id")
                    }
                    pending_tool_ids = ids if ids else None
            else:
                flush_pending()
                result.append(item)
            continue

        if role == "tool":
            result.append(item)
            if pending_tool_ids is not None:
                tool_call_id = item.get("tool_call_id")
                if tool_call_id in pending_tool_ids:
                    pending_tool_ids.discard(tool_call_id)
                    if not pending_tool_ids:
                        flush_pending()
            continue

        flush_pending()
        result.append(item)

    flush_pending()
    return result


def persist_context(session_id: str, context: dict) -> None:
    history = _SESSION_HISTORIES.get(session_id)
    if history is None:
        _, history = load_session(session_id)
        if history is None:
            history = []
    _SESSION_HISTORIES[session_id] = history
    save_session(session_id, context, history)


def append_assistant_message(session_id: str, content: str | None) -> None:
    if not content:
        return
    text = str(content).strip()
    if not text:
        return
    history = _SESSION_HISTORIES.get(session_id)
    if history is None:
        _, history = load_session(session_id)
        if history is None:
            history = []
    history = list(history)
    history.append({"role": "assistant", "content": text, "tool_calls": None})
    history = normalize_history(history)
    _SESSION_HISTORIES[session_id] = history
    context = _SESSION_CONTEXTS.get(session_id)
    if context is None:
        context, _ = load_session(session_id)
    save_session(session_id, context or {}, history)


def sync_import_message(context: dict) -> str:
    project_name = context.get("kicad_project_name") or context.get("client_folder_name") or "project"
    if context.get("circuit"):
        return (
            f"Imported KiCad project '{project_name}'. The circuit is now in context and the "
            "Python circuit code has been reconstructed from the schematic."
        )
    return (
        f"Imported KiCad project '{project_name}'. The project is now in context, but Python "
        "circuit code could not be reconstructed from the schematic."
    )


