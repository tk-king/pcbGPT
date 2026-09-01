import json
import os
import re
import shutil
from pathlib import Path
from typing import Annotated, Any

import chromadb
import chromadb.utils.embedding_functions as embedding_functions
import rich

import backend.config as config_module
from backend.data.Component.FootprintParser import get_footprint_for_component
from backend.data.Component.EmbeddingConfig import get_component_embedding_model
from backend.data.Component.KiCadComponent import KiCadComponent, get_all_kicad_components
from backend.runtime_paths import datasets_dir

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
                "Embedding search requires OPENAI_API_KEY or CHROMA_OPENAI_API_KEY."
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




def _component_search_backend() -> str:
    return os.getenv("COMPONENT_SEARCH_BACKEND", "whoosh+embedding").strip().lower()

def _component_search_backends() -> list[str]:
    raw = _component_search_backend()
    parts = [part.strip().lower() for part in raw.split("+") if part.strip()]
    return parts or ["embedding"]


def _component_text(component: KiCadComponent) -> str:
    text_parts = [
        component.name,
        component.library,
        component.description,
        component.keywords or "",
        component.fp_filters,
        component.default_footprint or "",
        component.extends or "",
    ]
    if component.footprints:
        text_parts.extend(f"{fp.library}:{fp.name}" for fp in component.footprints)
    return " ".join(part for part in text_parts if part).lower()


def _component_key(component: KiCadComponent) -> str:
    return f"{component.library}:{component.name}"


def _whoosh_index_dir() -> Path:
    return datasets_dir() / "whoosh_components_index"


def _build_whoosh_index(index_dir: Path) -> None:
    from whoosh import index
    from whoosh.fields import ID, TEXT, Schema

    index_dir.mkdir(parents=True, exist_ok=True)
    schema = Schema(
        key=ID(stored=True, unique=True),
        name=TEXT(stored=True),
        library=TEXT(stored=True),
        description=TEXT(stored=True),
        keywords=TEXT(stored=True),
        content=TEXT,
    )

    ix = index.create_in(index_dir, schema)
    writer = ix.writer()
    for component in get_all_kicad_components(strict=True):
        writer.add_document(
            key=_component_key(component),
            name=component.name,
            library=component.library,
            description=component.description or "",
            keywords=component.keywords or "",
            content=_component_text(component),
        )
    writer.commit()


def rebuild_component_text_index() -> None:
    index_dir = _whoosh_index_dir()
    if index_dir.exists():
        shutil.rmtree(index_dir)
    _build_whoosh_index(index_dir)


def component_text_index_stats() -> dict[str, Any]:
    """Report whether the Whoosh text index exists and how many docs it holds."""
    from whoosh import index as whoosh_index

    index_dir = _whoosh_index_dir()
    if not whoosh_index.exists_in(index_dir):
        return {"exists": False, "count": 0}
    ix = whoosh_index.open_dir(index_dir)
    return {"exists": True, "count": ix.doc_count()}


def search_components_whoosh(
    query: Annotated[str, "The search query for the component."],
    top_k: int = 5,
    rebuild_index: bool = False,
) -> list[KiCadComponent]:
    """Search for components using a Whoosh text index."""
    try:
        from whoosh import index
        from whoosh.qparser import MultifieldParser, OrGroup
    except ImportError as exc:
        raise RuntimeError(
            "Whoosh is required for search_components_whoosh. "
            "Install it with `pip install whoosh`."
        ) from exc

    index_dir = _whoosh_index_dir()
    if rebuild_index or not index.exists_in(index_dir):
        _build_whoosh_index(index_dir)

    ix = index.open_dir(index_dir)
    parser = MultifieldParser(
        ["name", "library", "description", "keywords", "content"],
        schema=ix.schema,
        group=OrGroup.factory(0.9),
    )
    query_obj = parser.parse(query)

    components = get_all_kicad_components(strict=True)
    key_to_component = {_component_key(component): component for component in components}
    with ix.searcher() as searcher:
        results = searcher.search(query_obj, limit=top_k)
        return [
            key_to_component[hit["key"]]
            for hit in results
            if hit["key"] in key_to_component
        ]


def search_components(query: Annotated[str, "The search query for the component."], top_k: int = 5) -> list[KiCadComponent]:
    """Search for components in the KiCad component database."""
    chroma_client = chromadb.PersistentClient(path=str(datasets_dir() / "chroma_db"))
    collection = chroma_client.get_or_create_collection(
        name="kicad_components",
        embedding_function=_embedding_function(),
    )
    # Print size of the collection
    rich.print(f"Collection '{collection.name}' has {collection.count()} documents.")
    rich.print(f"Searching for components matching query: '{query}'")

    query_results = collection.query(
        query_texts=[query],
        n_results=top_k
    )

    components: list[KiCadComponent] = []
    metadatas = query_results.get("metadatas", [])
    for metadata_group in metadatas:
        for metadata in metadata_group or []:
            component_json = metadata.get("component")
            if not component_json:
                continue
            try:
                component = KiCadComponent.model_validate_json(component_json)
            except ValueError:
                rich.print(f"[yellow]Warning:[/] Failed to parse component metadata: {metadata}")
                continue
            components.append(component)

    return components


def serialize_component(component: KiCadComponent) -> dict[str, Any]:
    component_data = component.model_dump()
    return_component_data: dict[str, Any] = {}

    pin_entries: list[dict[str, str | None]] = []
    for pin_spec in component_data.get("pins", []) or []:
        if ":" in pin_spec:
            pin_number, pin_name = pin_spec.split(":", 1)
        else:
            pin_number, pin_name = pin_spec, None
        pin_number = pin_number.strip()
        pin_name = pin_name.strip() if pin_name else None
        display_name = pin_name if pin_name else pin_number

        pin_entries.append(
            {
                "pin_number": pin_number,
                "pin_name": pin_name,
                "pin_display_name": display_name,
            }
        )
    return_component_data["pins"] = pin_entries
    return_component_data["footprints"] = [f"{fp.library}:{fp.name}" for fp in component.footprints[:10]]
    return_component_data["name"] = component_data.get("name")
    return_component_data["library"] = component_data.get("library")
    return_component_data["description"] = component_data.get("description")
    return_component_data["keywords"] = component_data.get("keywords", [])
    return_component_data["fp_filters"] = component_data.get("fp_filters")
    return_component_data["default_footprint"] = component_data.get("default_footprint")
    return_component_data["extends"] = component_data.get("extends")
    return_component_data["datasheet"] = component_data.get("datasheet")
    return_component_data["base_names"] = component_data.get("base_names", [])
    return_component_data["pin_count"] = len(pin_entries)
    return_component_data["footprint_count"] = len(component.footprints)
    return_component_data["key"] = _component_key(component)
    return return_component_data




def search_components_paginated(
    query: str,
    *,
    page: int = 1,
    page_size: int = 25,
    include_footprints: bool = True,
) -> dict[str, Any]:
    normalized_page = max(1, int(page))
    normalized_page_size = max(1, min(int(page_size), 100))
    offset = (normalized_page - 1) * normalized_page_size
    normalized_query = str(query or "").strip()

    if normalized_query:
        top_k = min(max(offset + normalized_page_size, normalized_page_size), 250)
        backends = _component_search_backends()
        components: list[KiCadComponent] = []
        for backend in backends:
            if backend in {"whoosh", "woosh"}:
                try:
                    components.extend(search_components_whoosh(normalized_query, top_k))
                except RuntimeError as exc:
                    rich.print(f"[yellow]Warning:[/] {exc} Skipping Whoosh search.")
            elif backend == "embedding":
                try:
                    components.extend(search_components(normalized_query, top_k))
                except Exception as exc:
                    rich.print(f"[yellow]Warning:[/] Embedding search failed: {exc}. Skipping.")
            else:
                rich.print(f"[yellow]Warning:[/] Unknown search backend '{backend}'. Skipping.")

        seen: set[str] = set()
        deduped: list[KiCadComponent] = []
        for component in components:
            key = _component_key(component)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(component)

        total = len(deduped)
        page_components = deduped[offset : offset + normalized_page_size]
    else:
        components = sorted(
            get_all_kicad_components(strict=True),
            key=lambda component: (component.library.lower(), component.name.lower()),
        )
        total = len(components)
        page_components = components[offset : offset + normalized_page_size]

    if include_footprints:
        page_components = [get_footprint_for_component(component) for component in page_components]

    return {
        "query": normalized_query,
        "page": normalized_page,
        "page_size": normalized_page_size,
        "total": total,
        "results": [serialize_component(component) for component in page_components],
    }


def tool_search_components(query: Annotated[str, "The search query for the component."], top_k: int = 5) -> str:
    """This tool allows to search for components which can be used in schematic designs. Query only by part names or types. e.g., 'ATmega328P', 'LM393 comparator', 'resistor', 'capacitor', 'LED red 5mm'."""
    print(f"Searching components for query: '{query}'")
    payload = search_components_paginated(query, page=1, page_size=top_k, include_footprints=True)
    components = payload["results"]
    if not components:
        result = f"No components found for query '{query}'."
        rich.print(result)
        return result

    formatted_results = [
        f"Result {idx}:\n{json.dumps(component, indent=2)}"
        for idx, component in enumerate(components, start=1)
    ]

    instructions = (
        "Pins must be referenced by their pin_number when wiring components. "
        "Use pin_name only as contextual description."
    )

    result = (
        f"Search results for '{query}':\n\n{instructions}\n\n" +
        "\n\n---\n\n".join(formatted_results)
    )

    return result
