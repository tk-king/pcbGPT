import mimetypes
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from backend.agent.tools.app_state import _API_ROUTE_PREFIXES, _FRONTEND_DIST, _SPA_ROUTE_PREFIXES
from backend.agent.tools.routers import chat, downloads, parts, sessions, settings, sync, system
from backend.agent.tools.session_store import init_db

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

init_db()

app.include_router(settings.router)
app.include_router(parts.router)
app.include_router(sessions.router)
app.include_router(downloads.router)
app.include_router(sync.router)
app.include_router(chat.router)
app.include_router(system.router)


def _frontend_index_path() -> Path | None:
    index_path = _FRONTEND_DIST / "index.html"
    if index_path.is_file():
        return index_path
    return None


def _resolve_frontend_asset(path: str) -> Path | None:
    index_path = _frontend_index_path()
    if index_path is None:
        return None

    normalized = path.strip("/")
    if not normalized:
        return index_path

    candidate = (_FRONTEND_DIST / normalized).resolve()
    try:
        candidate.relative_to(_FRONTEND_DIST)
    except ValueError:
        return None

    if candidate.is_file():
        return candidate

    first_segment = normalized.split("/", 1)[0]
    if first_segment in _SPA_ROUTE_PREFIXES:
        return index_path
    return None


@app.get("/")
async def root():
    frontend_index = _frontend_index_path()
    if frontend_index is not None:
        return FileResponse(frontend_index)
    return {"message": "Hello from PCBGPT"}


@app.get("/{frontend_path:path}")
async def frontend_app(frontend_path: str):
    first_segment = frontend_path.split("/", 1)[0] if frontend_path else ""
    if first_segment in _API_ROUTE_PREFIXES:
        raise HTTPException(status_code=404, detail="Not found.")

    asset_path = _resolve_frontend_asset(frontend_path)
    if asset_path is None:
        raise HTTPException(status_code=404, detail="Not found.")

    media_type, _ = mimetypes.guess_type(str(asset_path))
    return FileResponse(asset_path, media_type=media_type)
