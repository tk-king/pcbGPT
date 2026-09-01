import logging
import os
from typing import Any

import chromadb
import chromadb.utils.embedding_functions as embedding_functions
from tqdm import tqdm

import backend.config as config_module
from backend.data.Component.EmbeddingConfig import get_component_embedding_model
from backend.data.Component.KiCadComponent import KiCadComponent
from backend.runtime_paths import datasets_dir

logger = logging.getLogger(__name__)

_EMBEDDING_FUNCS = {}


def _normalize_openai_base_url(url: str | None) -> str | None:
    if not url:
        return None
    cleaned = url.strip().rstrip("/")
    lowered = cleaned.lower()
    if lowered.endswith("/v1") or "/v1/" in lowered:
        return cleaned
    return f"{cleaned}/v1"


def _embedding_function_kwargs(selected_model: str) -> dict:
    try:
        resolved = config_module.resolve_model_config(selected_model)
    except ValueError:
        api_key = os.getenv("OPENAI_API_KEY") or os.getenv("CHROMA_OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "Embedding updates require OPENAI_API_KEY or CHROMA_OPENAI_API_KEY."
            )
        return {
            "api_key": api_key,
            "model_name": selected_model,
        }
    return {
        "api_key": resolved.api_key or "EMPTY",
        "api_base": _normalize_openai_base_url(resolved.base_url),
        "model_name": resolved.model_name,
        "default_headers": resolved.default_headers,
    }


def _embedding_function(model_name: str | None = None):
    selected_model = model_name or get_component_embedding_model()
    if not selected_model:
        raise RuntimeError("Component embedding model is not configured. Choose one in the Available Parts modal.")
    if selected_model in _EMBEDDING_FUNCS:
        return _EMBEDDING_FUNCS[selected_model]

    embedding_func = embedding_functions.OpenAIEmbeddingFunction(
        **_embedding_function_kwargs(selected_model),
    )
    _EMBEDDING_FUNCS[selected_model] = embedding_func
    return embedding_func

def _get_embedding_string(component: KiCadComponent) -> str:
    text = (
        f"Name: {component.name}\n"
        f"Library: {component.library}\n"
        f"Description: {component.description}\n"
        f"Keywords: {component.keywords or 'N/A'}\n"
    )
    return text


def generate_component_embeddings(
    components: list[KiCadComponent],
    chunk_size: int = 100,
    model_name: str | None = None,
):
    if chunk_size <= 0:
        raise ValueError("chunk_size must be a positive integer")
    total_components = len(components)
    logger.info(f"{total_components} components to embed")
    if total_components == 0:
        logger.info("No components provided for embedding")
        return

    selected_model = model_name or get_component_embedding_model()
    if not selected_model:
        raise RuntimeError("Component embedding model is not configured. Choose one in the Available Parts modal.")
    chroma_client = chromadb.PersistentClient(path=str(datasets_dir() / "chroma_db"))
    collection = chroma_client.get_or_create_collection(
        name="kicad_components",
        embedding_function=_embedding_function(selected_model),
    )

    with tqdm(total=total_components, desc="Embedding components") as progress:
        for index in range(0, total_components, chunk_size):
            chunk = components[index : index + chunk_size]
            collection.add(
                ids=[component.library + "_" + component.name for component in chunk],
                documents=[_get_embedding_string(component) for component in chunk],
                metadatas=[
                    {
                        "component": component.model_dump_json(),
                        "embedding_model": selected_model,
                    }
                    for component in chunk
                ],
            )
            progress.update(len(chunk))


def rebuild_component_embeddings(
    components: list[KiCadComponent],
    chunk_size: int = 100,
    model_name: str | None = None,
):
    chroma_client = chromadb.PersistentClient(path=str(datasets_dir() / "chroma_db"))
    try:
        chroma_client.delete_collection(name="kicad_components")
    except Exception:
        pass
    generate_component_embeddings(components, chunk_size=chunk_size, model_name=model_name)


def upsert_component_embeddings(
    components: list[KiCadComponent],
    chunk_size: int = 100,
    model_name: str | None = None,
):
    if chunk_size <= 0:
        raise ValueError("chunk_size must be a positive integer")
    total_components = len(components)
    logger.info("%d components to upsert", total_components)
    if total_components == 0:
        return

    selected_model = model_name or get_component_embedding_model()
    if not selected_model:
        raise RuntimeError("Component embedding model is not configured. Choose one in the Available Parts modal.")
    chroma_client = chromadb.PersistentClient(path=str(datasets_dir() / "chroma_db"))
    collection = chroma_client.get_or_create_collection(
        name="kicad_components",
        embedding_function=_embedding_function(selected_model),
    )

    with tqdm(total=total_components, desc="Embedding components") as progress:
        for index in range(0, total_components, chunk_size):
            chunk = components[index : index + chunk_size]
            collection.upsert(
                ids=[component.library + "_" + component.name for component in chunk],
                documents=[_get_embedding_string(component) for component in chunk],
                metadatas=[
                    {
                        "component": component.model_dump_json(),
                        "embedding_model": selected_model,
                    }
                    for component in chunk
                ],
            )
            progress.update(len(chunk))


def embedding_index_stats(model_name: str | None = None) -> dict[str, Any]:
    """Report the state of the ChromaDB component embedding index."""
    selected_model = model_name or get_component_embedding_model()
    stats: dict[str, Any] = {
        "collection_exists": False,
        "count": 0,
        "embedding_models": [],
    }
    chroma_client = chromadb.PersistentClient(path=str(datasets_dir() / "chroma_db"))
    try:
        collection = chroma_client.get_collection(name="kicad_components")
    except Exception:
        return stats
    stats["collection_exists"] = True
    try:
        stats["count"] = collection.count()
    except Exception:
        pass

    # Collect which embedding models are present in metadata. Sampling keeps
    # this cheap; a full rebuild always produces a single uniform model.
    models: set[str] = set()
    batch_size = 250
    max_scan = 2000
    try:
        for offset in range(0, min(stats["count"], max_scan), batch_size):
            rows = collection.get(include=["metadatas"], limit=batch_size, offset=offset)
            metadatas = rows.get("metadatas") or []
            for metadata in metadatas:
                value = (metadata or {}).get("embedding_model")
                if value:
                    models.add(str(value))
            if len(metadatas) < batch_size:
                break
    except Exception:
        pass
    stats["embedding_models"] = sorted(models)
    return stats


