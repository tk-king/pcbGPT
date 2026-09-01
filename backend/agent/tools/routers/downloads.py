import json
import shutil
import tempfile
from pathlib import Path

import rich
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from backend.agent.tools.app_state import _SESSION_CONTEXTS
from backend.agent.tools.circuit_export import CircuitCodeError, build_circuit_from_code, convert_code_to_netlist
from backend.agent.tools.session_store import load_session
from backend.Circuit.ImporterExporter.KiCADProject.project_generator import (
    generate_kicad_project,
)
from backend.runtime_paths import custom_sessions_db_path

router = APIRouter(prefix="/download", tags=["download"])


def _zip_and_return(project_dir: Path, project_name: str) -> Response:
    with tempfile.TemporaryDirectory(prefix="pcbgpt_kicad_zip_") as tmpdir:
        zip_path = Path(tmpdir) / f"{project_name}.zip"
        shutil.make_archive(str(zip_path.with_suffix("")), "zip", project_dir)
        data = zip_path.read_bytes()
    return Response(
        content=data,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{project_name}.zip"'},
    )




@router.get("/netlist/{session_id}")
async def download_netlist(session_id: str):
    context = _SESSION_CONTEXTS.get(session_id)
    if not context:
        context, _ = load_session(session_id)
        if not context:
            raise HTTPException(
                status_code=404, detail="No session context found for this ID."
            )
    circuit_code = context.get("circuit")
    if not circuit_code:
        raise HTTPException(
            status_code=404,
            detail="No circuit code is available for this session. Ask the agent to generate a schematic first.",
        )

    try:
        netlist_content = convert_code_to_netlist(circuit_code)
    except CircuitCodeError as exc:
        rich.print(f"[red]Error converting circuit code to netlist:[/red] {exc}")
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    filename = f"circuit_{session_id[:8]}.net"
    return Response(
        content=netlist_content,
        media_type="text/plain",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/project/{session_id}")
async def download_kicad_project(session_id: str):
    context = _SESSION_CONTEXTS.get(session_id)
    if not context:
        context, _ = load_session(session_id)
    if not context:
        raise HTTPException(
            status_code=404, detail="No session context found for this ID."
        )

    project_path = context.get("kicad_project_path")
    project_name = context.get("kicad_project_name") or "kicad_project"
    circuit_code: str | None = context.get("circuit")

    if project_path:
        project_dir = Path(project_path)
        if project_dir.exists():
            return _zip_and_return(project_dir, project_name)

    # Project folder doesn't exist on disk — try to regenerate from circuit code.
    if circuit_code:
        try:
            circuit = build_circuit_from_code(circuit_code)
            output_root = Path(tempfile.mkdtemp(prefix="pcbgpt_kicad_regen_"))
            try:
                generated_path = generate_kicad_project(
                    circuits=[circuit],
                    output_dir=output_root,
                    project_name=project_name,
                )
                project_dir = Path(generated_path)
                context["kicad_project_path"] = str(project_dir)
                return _zip_and_return(project_dir, project_name)
            finally:
                shutil.rmtree(output_root, ignore_errors=True)
        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail=f"Could not regenerate KiCad project from circuit code: {exc}",
            ) from exc

    raise HTTPException(
        status_code=404,
        detail="No KiCad project is available for this session. Generate a schematic first.",
    )
