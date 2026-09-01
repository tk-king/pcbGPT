from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.agent.tools.app_state import _SESSION_CONTEXTS
from backend.agent.tools.session_store import append_assistant_message, persist_context, sync_import_message
from backend.agent.tools.sync_utils import import_kicad_folder
from backend.agent.tools.utils import (
    _extract_archive_to_workspace,
    _init_context,
    _locate_project_folder,
)

router = APIRouter(prefix="/sync", tags=["sync"])


class SyncPayload(BaseModel):
    session_id: str
    folder_path: str | None = None
    folder_name: str | None = None
    archive_b64: str | None = None


def _folder_from_payload(payload: SyncPayload) -> tuple[Path, str]:
    if payload.folder_path:
        folder = Path(payload.folder_path).expanduser().resolve()
        if not folder.is_dir():
            raise HTTPException(status_code=404, detail="Folder not found.")
        return _locate_project_folder(folder), "local"

    if payload.archive_b64:
        return (
            _locate_project_folder(
                _extract_archive_to_workspace(payload.session_id, payload.archive_b64)
            ),
            "upload",
        )

    raise HTTPException(
        status_code=400,
        detail="Sync requires either folder_path or archive_b64.",
    )


@router.post("/import")
async def import_project(payload: SyncPayload):
    context = _init_context(payload.session_id)
    context.setdefault("project_version", context.get("project_version", 0) or 0)
    folder, sync_origin = _folder_from_payload(payload)
    context["sync_origin"] = sync_origin

    if folder is None or not folder.exists():
        raise HTTPException(status_code=404, detail="Folder not found.")

    sch_files = list(folder.glob("*.kicad_sch"))
    context["sync_display_path"] = payload.folder_path or payload.folder_name or folder.name
    context["client_folder_name"] = payload.folder_name or folder.name
    if not sch_files:
        context.update(
            {
                "sync_folder_path": str(folder),
                "sync_mode": "output_only",
                "kicad_project_path": str(folder),
                "kicad_project_name": None,
                "schematic_pdf_path": None,
                "schematic_pdf_base64": None,
                "circuit": None,
                "imported_netlist": None,
            }
        )
    else:
        context = import_kicad_folder(folder, context)
    import_message = sync_import_message(context) if sch_files else None
    _SESSION_CONTEXTS[payload.session_id] = context
    if import_message:
        append_assistant_message(payload.session_id, import_message)
    persist_context(payload.session_id, context)
    response = {"session_id": payload.session_id, "context": context}
    if import_message:
        response["import_message"] = import_message
    return response


@router.post("/reimport")
async def reimport_project(payload: SyncPayload):
    context = _init_context(payload.session_id)
    context.setdefault("project_version", context.get("project_version", 0) or 0)
    folder, sync_origin = _folder_from_payload(payload)
    context["sync_origin"] = sync_origin
    if payload.folder_path or payload.folder_name:
        context["sync_display_path"] = payload.folder_path or payload.folder_name
        context["client_folder_name"] = payload.folder_name or folder.name
    if folder is None or not folder.exists():
        raise HTTPException(status_code=404, detail="Folder not found.")

    sch_files = list(folder.glob("*.kicad_sch"))
    if not sch_files:
        if context.get("sync_mode") == "output_only":
            context.update(
                {
                    "sync_folder_path": str(folder),
                    "kicad_project_path": str(folder),
                    "kicad_project_name": None,
                    "schematic_pdf_path": None,
                    "schematic_pdf_base64": None,
                    "circuit": None,
                    "imported_netlist": None,
                }
            )
            _SESSION_CONTEXTS[payload.session_id] = context
            persist_context(payload.session_id, context)
            return {"session_id": payload.session_id, "context": context}
        raise HTTPException(
            status_code=404,
            detail="No .kicad_sch found in folder. Please sync a valid KiCad project.",
        )

    context = import_kicad_folder(folder, context)
    import_message = sync_import_message(context)
    _SESSION_CONTEXTS[payload.session_id] = context
    append_assistant_message(payload.session_id, import_message)
    persist_context(payload.session_id, context)
    return {
        "session_id": payload.session_id,
        "context": context,
        "import_message": import_message,
    }


@router.post("/local-folder")
async def choose_local_folder(payload: SyncPayload):
    return await import_project(payload)
