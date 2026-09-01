import asyncio
import os
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from backend.data.Component.UserPartLibrary import install_uploaded_part
from backend.data.Component.Search import search_components_paginated

router = APIRouter(prefix="/parts", tags=["parts"])
_REINDEX_JOBS: dict[str, dict[str, Any]] = {}


class ReindexPartsPayload(BaseModel):
    symbol_path: str = ""
    footprint_path: str = ""
    model_path: str = ""
    embedding_model: str = ""


class EmbeddingModelPayload(BaseModel):
    embedding_model: str


def _count_jsonl_entries(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8") as file:
        return sum(1 for line in file if line.strip())


def _part_index_status() -> dict[str, Any]:
    from backend.data.Component.Embedding import embedding_index_stats
    from backend.data.Component.EmbeddingConfig import get_component_embedding_model
    from backend.data.Component.Search import component_text_index_stats
    from backend.runtime_paths import datasets_dir

    dataset_path = datasets_dir()
    symbol_file = dataset_path / "kicad_symbols.jsonl"
    footprint_file = dataset_path / "kicad_footprints.jsonl"
    embedding_model = get_component_embedding_model()
    expected_count = _count_jsonl_entries(symbol_file)

    chroma_stats = embedding_index_stats(embedding_model)
    whoosh_stats = component_text_index_stats()

    # The embedding index is only usable when it was built with the currently
    # selected model and holds every parsed component.
    embedding_models = chroma_stats.get("embedding_models") or []
    embedding_model_match = bool(
        embedding_model
        and chroma_stats.get("collection_exists")
        and embedding_models == [embedding_model]
    )
    index_counts_ok = bool(
        expected_count > 0
        and chroma_stats.get("count") == expected_count
        and whoosh_stats.get("exists")
        and whoosh_stats.get("count") == expected_count
    )
    needs_reindex = not (embedding_model_match and index_counts_ok)

    return {
        "datasets_path": str(dataset_path),
        "component_count": expected_count,
        "footprint_count": _count_jsonl_entries(footprint_file),
        "symbol_index_exists": symbol_file.exists(),
        "footprint_index_exists": footprint_file.exists(),
        "embedding_model": embedding_model,
        "chromadb": {
            "collection_exists": chroma_stats.get("collection_exists", False),
            "count": chroma_stats.get("count", 0),
            "embedding_models": embedding_models,
        },
        "whoosh": {
            "index_exists": bool(whoosh_stats.get("exists")),
            "count": whoosh_stats.get("count", 0),
        },
        "expected_part_count": expected_count,
        "embedding_model_match": embedding_model_match,
        "index_counts_ok": index_counts_ok,
        "needs_reindex": needs_reindex,
    }


def _set_reindex_progress(
    job_id: str | None,
    *,
    progress: int,
    message: str,
    status: str = "running",
    result: dict[str, Any] | None = None,
    error: str | None = None,
) -> None:
    if not job_id:
        return
    job = _REINDEX_JOBS.setdefault(job_id, {})
    job.update(
        {
            "job_id": job_id,
            "status": status,
            "progress": max(0, min(100, int(progress))),
            "message": message,
            "result": result,
            "error": error,
        }
    )


def _verify_reindexed_indexes(*, expected_count: int) -> dict[str, Any]:
    """Verify that ChromaDB and the Whoosh index both hold every parsed part."""
    from backend.data.Component.Embedding import embedding_index_stats
    from backend.data.Component.EmbeddingConfig import get_component_embedding_model
    from backend.data.Component.Search import component_text_index_stats

    chroma_stats = embedding_index_stats()
    whoosh_stats = component_text_index_stats()
    selected_model = get_component_embedding_model()
    problems: list[str] = []

    if not chroma_stats.get("collection_exists"):
        problems.append("ChromaDB collection 'kicad_components' is missing.")
    elif chroma_stats.get("count") != expected_count:
        problems.append(
            f"ChromaDB holds {chroma_stats.get('count')} parts, expected {expected_count}."
        )

    if not whoosh_stats.get("exists"):
        problems.append("Whoosh text search index is missing.")
    elif whoosh_stats.get("count") != expected_count:
        problems.append(
            f"Whoosh index holds {whoosh_stats.get('count')} parts, expected {expected_count}."
        )

    embedding_models = chroma_stats.get("embedding_models") or []
    if embedding_models and embedding_models != [selected_model]:
        problems.append(
            "Embedding index was built with "
            f"{', '.join(embedding_models)}, expected '{selected_model}'."
        )

    return {
        "ok": not problems,
        "problems": problems,
        "expected_part_count": expected_count,
        "chromadb": {
            "collection_exists": chroma_stats.get("collection_exists", False),
            "count": chroma_stats.get("count", 0),
            "embedding_models": embedding_models,
        },
        "whoosh": {
            "index_exists": bool(whoosh_stats.get("exists")),
            "count": whoosh_stats.get("count", 0),
        },
        "embedding_model": selected_model,
    }


def _run_part_reindex(
    symbol_path: str = "",
    footprint_path: str = "",
    model_path: str = "",
    embedding_model: str = "",
    *,
    job_id: str | None = None,
) -> dict[str, Any]:
    from backend.agent.tools.kicad_utils import (
        _is_valid_footprint_dir,
        _is_valid_model_dir,
        _is_valid_symbol_dir,
        configure_kicad_paths,
        detect_kicad_paths,
    )
    from backend.data.Component import ComponentParser, FootprintParser
    from backend.data.Component.Embedding import rebuild_component_embeddings
    from backend.data.Component.EmbeddingConfig import (
        get_component_embedding_model,
        save_component_embedding_model,
    )
    from backend.data.Component.KiCadComponent import reload_kicad_components
    from backend.data.Component.Search import rebuild_component_text_index
    from backend.runtime_paths import datasets_dir

    _set_reindex_progress(job_id, progress=5, message="Checking KiCad paths")
    symbol_path = str(symbol_path or "").strip()
    footprint_path = str(footprint_path or "").strip()
    model_path = str(model_path or "").strip()
    embedding_model = str(embedding_model or "").strip()
    if embedding_model:
        save_component_embedding_model(embedding_model)
    selected_embedding_model = get_component_embedding_model()
    if not selected_embedding_model:
        raise ValueError("Component embedding model is not configured. Choose one before reindexing.")
    configure_kicad_paths(
        symbol_path=symbol_path,
        footprint_path=footprint_path,
        model_path=model_path,
    )

    detected_paths = detect_kicad_paths()
    resolved_symbol_path = detected_paths.get("symbol_path")
    resolved_footprint_path = detected_paths.get("footprint_path")
    resolved_model_path = detected_paths.get("model_path")

    if symbol_path:
        candidate = Path(symbol_path).expanduser().resolve()
        if not _is_valid_symbol_dir(candidate):
            raise ValueError("KiCad symbol path is not configured or is not valid.")
        resolved_symbol_path = str(candidate)
    if footprint_path:
        candidate = Path(footprint_path).expanduser().resolve()
        if not _is_valid_footprint_dir(candidate):
            raise ValueError("KiCad footprint path is not configured or is not valid.")
        resolved_footprint_path = str(candidate)
    if model_path:
        candidate = Path(model_path).expanduser().resolve()
        if not _is_valid_model_dir(candidate):
            raise ValueError("KiCad 3D model path is not configured or is not valid.")
        resolved_model_path = str(candidate)

    if not resolved_symbol_path:
        raise ValueError("KiCad symbol path is not configured or is not valid.")
    if not resolved_footprint_path:
        raise ValueError("KiCad footprint path is not configured or is not valid.")

    os.environ["KICAD_SYMBOL_PATH"] = resolved_symbol_path
    os.environ["KICAD_FOOTPRINT_PATH"] = resolved_footprint_path
    if resolved_model_path:
        os.environ["KICAD_3D_MODEL_PATH"] = resolved_model_path
        os.environ["KICAD_3DMODEL_DIR"] = resolved_model_path
    ComponentParser.KICAD_SYMBOL_PATH = resolved_symbol_path
    ComponentParser.KICAD_FOOTPRINT_PATH = resolved_footprint_path
    FootprintParser.KICAD_FOOTPRINT_PATH = resolved_footprint_path

    _set_reindex_progress(job_id, progress=15, message="Parsing KiCad symbols")
    components = ComponentParser.parse_and_store_components()
    _set_reindex_progress(job_id, progress=35, message="Parsing KiCad footprints")
    footprints = FootprintParser.parse_all_footprints()
    _set_reindex_progress(job_id, progress=55, message=f"Rebuilding embedding database ({selected_embedding_model})")
    rebuild_component_embeddings(components, model_name=selected_embedding_model)
    _set_reindex_progress(job_id, progress=85, message="Rebuilding text index")
    rebuild_component_text_index()
    _set_reindex_progress(job_id, progress=92, message="Verifying indexes")
    verification = _verify_reindexed_indexes(expected_count=len(components))
    if not verification["ok"]:
        raise ValueError(
            "Reindex verification failed: " + " ".join(verification["problems"])
        )
    _set_reindex_progress(job_id, progress=95, message="Refreshing in-memory indexes")
    reload_kicad_components(strict=True)
    FootprintParser.reload_all_footprints()

    result = {
        "ok": True,
        "symbol_path": resolved_symbol_path,
        "footprint_path": resolved_footprint_path,
        "model_path": resolved_model_path,
        "datasets_path": str(datasets_dir()),
        "component_count": len(components),
        "footprint_count": len(footprints),
        "embedding_model": selected_embedding_model,
        "embedding_index_rebuilt": True,
        "whoosh_index_rebuilt": True,
        "verification": verification,
    }
    _set_reindex_progress(
        job_id,
        progress=100,
        message="Reindex complete",
        status="completed",
        result=result,
    )
    return result


def _run_reindex_job(
    job_id: str,
    symbol_path: str,
    footprint_path: str,
    model_path: str,
    embedding_model: str,
) -> None:
    try:
        _run_part_reindex(
            symbol_path,
            footprint_path,
            model_path,
            embedding_model,
            job_id=job_id,
        )
    except Exception as exc:
        _set_reindex_progress(
            job_id,
            progress=100,
            message="Reindex failed",
            status="failed",
            error=str(exc),
        )


@router.get("/search")
async def search_parts(query: str = "", page: int = 1, page_size: int = 25):
    try:
        payload = search_components_paginated(
            query,
            page=page,
            page_size=page_size,
            include_footprints=True,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Part search failed: {exc}") from exc
    return payload


@router.get("/index-status")
async def part_index_status():
    try:
        return _part_index_status()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Part index status failed: {exc}") from exc


@router.post("/embedding-model")
async def save_embedding_model(payload: EmbeddingModelPayload):
    try:
        from backend.data.Component.EmbeddingConfig import save_component_embedding_model

        model_name = save_component_embedding_model(payload.embedding_model)
        return {
            "embedding_model": model_name,
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/reindex/{job_id}")
async def reindex_status(job_id: str):
    job = _REINDEX_JOBS.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Reindex job not found.")
    return job


@router.post("/reindex")
async def reindex_parts(payload: ReindexPartsPayload):
    job_id = uuid4().hex
    _set_reindex_progress(job_id, progress=0, message="Queued", status="queued")
    asyncio.create_task(
        asyncio.to_thread(
            _run_reindex_job,
            job_id,
            payload.symbol_path,
            payload.footprint_path,
            payload.model_path,
            payload.embedding_model,
        )
    )
    return _REINDEX_JOBS[job_id]


@router.post("/upload")
async def upload_part(
    kicad_sym: UploadFile = File(...),
    kicad_mod: UploadFile = File(...),
    step_file: UploadFile | None = File(None),
):
    try:
        symbol_bytes = await kicad_sym.read()
        footprint_bytes = await kicad_mod.read()
        step_bytes = await step_file.read() if step_file is not None else None
        if not symbol_bytes:
            raise ValueError("Uploaded symbol file is empty.")
        if not footprint_bytes:
            raise ValueError("Uploaded footprint file is empty.")
        payload = install_uploaded_part(
            symbol_filename=kicad_sym.filename or "",
            symbol_bytes=symbol_bytes,
            footprint_filename=kicad_mod.filename or "",
            footprint_bytes=footprint_bytes,
            step_filename=step_file.filename if step_file is not None else None,
            step_bytes=step_bytes,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Part upload failed: {exc}") from exc
    return payload
