import sqlite3

from backend.runtime_paths import settings_db_path


def _settings_db_conn():
    db_path = settings_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(db_path)


def _init_table() -> None:
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


def get_component_embedding_model() -> str | None:
    _init_table()
    with _settings_db_conn() as conn:
        row = conn.execute(
            "SELECT value FROM system_settings WHERE key = ?",
            ("component_embedding_model",),
        ).fetchone()
    model_name = row[0].strip() if row and row[0] else ""
    return model_name or None


def save_component_embedding_model(model_name: str) -> str:
    normalized = str(model_name or "").strip()
    if not normalized:
        raise ValueError("Embedding model cannot be empty.")
    _init_table()
    with _settings_db_conn() as conn:
        conn.execute(
            "INSERT INTO system_settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            ("component_embedding_model", normalized),
        )
        conn.commit()
    return normalized
