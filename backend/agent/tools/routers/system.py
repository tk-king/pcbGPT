from fastapi import APIRouter
from pydantic import BaseModel

from backend.agent.tools.kicad_utils import configure_kicad_paths, detect_kicad_paths

router = APIRouter(prefix="/system", tags=["system"])


class KicadPathsPayload(BaseModel):
    symbol_path: str = ""
    footprint_path: str = ""
    model_path: str = ""


@router.get("/kicad-check")
async def kicad_check():
    return detect_kicad_paths()


@router.post("/kicad-configure")
async def kicad_configure(payload: KicadPathsPayload):
    return configure_kicad_paths(
        symbol_path=payload.symbol_path,
        footprint_path=payload.footprint_path,
        model_path=payload.model_path,
    )
