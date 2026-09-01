from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.agent.tools.session_store import (
    delete_core_agents_session,
    delete_sync_workspace,
    delete_session_row,
    list_sessions,
    load_session,
    normalize_custom_title,
    set_session_custom_title,
    session_exists,
)
from backend.runtime_paths import custom_sessions_db_path
from backend.agent.tools.app_state import _SESSION_CONTEXTS, _SESSION_HISTORIES

router = APIRouter(prefix="/sessions", tags=["sessions"])


class SessionTitlePayload(BaseModel):
    title: str | None = None


@router.get("/{session_id}")
async def get_session(session_id: str):
    context, history = load_session(session_id)
    if context is None or history is None:
        raise HTTPException(status_code=404, detail="Session not found.")
    return {"session_id": session_id, "context": context, "history": history}


@router.delete("/{session_id}")
async def delete_session(session_id: str):
    if not session_exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found.")

    _SESSION_CONTEXTS.pop(session_id, None)
    _SESSION_HISTORIES.pop(session_id, None)

    delete_session_row(session_id)
    delete_core_agents_session(
        session_id,
        db_path=str(custom_sessions_db_path()),
    )
    delete_sync_workspace(session_id)

    return {"deleted": True, "session_id": session_id, "sessions": list_sessions()}


@router.patch("/{session_id}/title")
async def rename_session(session_id: str, payload: SessionTitlePayload):
    updated = set_session_custom_title(session_id, payload.title)
    if not updated:
        raise HTTPException(status_code=404, detail="Session not found.")
    normalized_title = normalize_custom_title(payload.title)
    return {
        "session_id": session_id,
        "title": normalized_title,
        "sessions": list_sessions(),
    }
