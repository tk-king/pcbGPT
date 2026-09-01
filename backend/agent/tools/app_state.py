import os
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_FRONTEND_DIST = Path(
    os.getenv("PCBGPT_FRONTEND_DIST", str(_REPO_ROOT / "frontend" / "dist"))
).resolve()
_SPA_ROUTE_PREFIXES = {"generate"}
_API_ROUTE_PREFIXES = {"settings", "parts", "sessions", "download", "sync", "chat", "system"}

_SESSION_CONTEXTS: dict[str, dict] = {}
_SESSION_HISTORIES: dict[str, list[dict]] = {}
