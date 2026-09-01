from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from backend.runtime_paths import custom_sessions_db_path


def _now_ms() -> int:
    return int(time.time() * 1000)


@dataclass(frozen=True)
class SQLiteSession:
    session_id: str
    db_path: str | None = None
    table_prefix: str = "core_agents"

    @property
    def _sessions_table(self) -> str:
        return f"{self.table_prefix}_sessions"

    @property
    def _messages_table(self) -> str:
        return f"{self.table_prefix}_messages"

    @property
    def _events_table(self) -> str:
        return f"{self.table_prefix}_events"

    def _connect(self) -> sqlite3.Connection:
        db_path = Path(self.db_path) if self.db_path else custom_sessions_db_path()
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS {sessions_table} (
                  session_id TEXT PRIMARY KEY,
                  created_at_ms INTEGER NOT NULL
                )
                """.format(sessions_table=self._sessions_table)
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS {messages_table} (
                  session_id TEXT NOT NULL,
                  idx INTEGER NOT NULL,
                  role TEXT NOT NULL,
                  content TEXT,
                  tool_calls_json TEXT,
                  tool_call_id TEXT,
                  created_at_ms INTEGER NOT NULL,
                  PRIMARY KEY (session_id, idx)
                )
                """.format(messages_table=self._messages_table)
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS {events_table} (
                  session_id TEXT NOT NULL,
                  idx INTEGER NOT NULL,
                  type TEXT NOT NULL,
                  payload_json TEXT NOT NULL,
                  created_at_ms INTEGER NOT NULL,
                  PRIMARY KEY (session_id, idx)
                )
                """.format(events_table=self._events_table)
            )
            conn.execute(
                f"INSERT OR IGNORE INTO {self._sessions_table}(session_id, created_at_ms) VALUES (?, ?)",
                (self.session_id, _now_ms()),
            )

    def append_message(self, message: dict[str, Any]) -> None:
        self._ensure_schema()
        with self._connect() as conn:
            cur = conn.execute(
                f"SELECT COALESCE(MAX(idx), -1) + 1 FROM {self._messages_table} WHERE session_id=?",
                (self.session_id,),
            )
            idx = int(cur.fetchone()[0])
            conn.execute(
                """
                INSERT INTO {messages_table}(session_id, idx, role, content, tool_calls_json, tool_call_id, created_at_ms)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """.format(messages_table=self._messages_table),
                (
                    self.session_id,
                    idx,
                    message.get("role"),
                    message.get("content"),
                    json.dumps(message.get("tool_calls")) if message.get("tool_calls") is not None else None,
                    message.get("tool_call_id"),
                    _now_ms(),
                ),
            )

    def append_event(self, event_type: str, payload: dict[str, Any]) -> None:
        self._ensure_schema()
        with self._connect() as conn:
            cur = conn.execute(
                f"SELECT COALESCE(MAX(idx), -1) + 1 FROM {self._events_table} WHERE session_id=?",
                (self.session_id,),
            )
            idx = int(cur.fetchone()[0])
            conn.execute(
                """
                INSERT INTO {events_table}(session_id, idx, type, payload_json, created_at_ms)
                VALUES (?, ?, ?, ?, ?)
                """.format(events_table=self._events_table),
                (self.session_id, idx, event_type, json.dumps(payload), _now_ms()),
            )

    def load_messages(self) -> list[dict[str, Any]]:
        self._ensure_schema()
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT role, content, tool_calls_json, tool_call_id
                FROM {messages_table}
                WHERE session_id=?
                ORDER BY idx ASC
                """.format(messages_table=self._messages_table),
                (self.session_id,),
            ).fetchall()
        out: list[dict[str, Any]] = []
        for role, content, tool_calls_json, tool_call_id in rows:
            msg: dict[str, Any] = {"role": role, "content": content}
            if tool_calls_json:
                try:
                    msg["tool_calls"] = json.loads(tool_calls_json)
                except Exception:
                    msg["tool_calls"] = None
            if tool_call_id:
                msg["tool_call_id"] = tool_call_id
            out.append(msg)
        return out

