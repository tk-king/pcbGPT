from pathlib import Path

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from backend.core.exceptions import CircuitException
from backend.data.Component.KiCadFootprint import KiCadFootprint
from backend.runtime_paths import datasets_dir


class KiCadComponent(BaseModel):
    name: str
    library: str
    description: str
    pins: list[str]
    base_names: list[str] = Field(default_factory=list)
    extends: str | None = None
    datasheet: str | None = None
    keywords: str | None = None
    fp_filters: str
    default_footprint: str | None = None
    footprints: list[KiCadFootprint] = Field(default_factory=list)
    # Full geometric information extracted from the KiCad symbol:
    # - pin_geometries holds the raw pin S-expression data in a structured form
    #   including coordinates, orientation, and length.
    # - graphics holds all drawing primitives (rectangles, circles, arcs, etc.)
    #   with their coordinates.
    # - bbox is a simple bounding box over pins + graphics.
    pin_geometries: List[Dict[str, Any]] = Field(default_factory=list)
    graphics: List[Dict[str, Any]] = Field(default_factory=list)
    bbox: Optional[Dict[str, float]] = None


DEFAULT_KICAD_SYMBOLS_PATH = datasets_dir() / "kicad_symbols.jsonl"
_ALL_KICAD_COMPONENTS: list["KiCadComponent"] | None = None
_COMPONENTS_BY_LIBRARY_AND_NAME: dict[tuple[str, str], "KiCadComponent"] | None = None
_KNOWN_LIBRARIES: set[str] | None = None


def load_kicad_component_from_json(
    path: Path = DEFAULT_KICAD_SYMBOLS_PATH, *, strict: bool = True
) -> list["KiCadComponent"]:
    if not path.exists():
        if strict:
            raise CircuitException(
                f"KiCad symbol dataset not found at '{path}'. "
                "Generate it first by running Parts → Reindex in the application."
            )
        return []
    components: list[KiCadComponent] = []
    with path.open("r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if not line:
                continue
            components.append(KiCadComponent.model_validate_json(line))
    return components


def get_all_kicad_components(*, strict: bool = True) -> list["KiCadComponent"]:
    global _ALL_KICAD_COMPONENTS
    if _ALL_KICAD_COMPONENTS is None:
        _ALL_KICAD_COMPONENTS = load_kicad_component_from_json(strict=strict)
    return _ALL_KICAD_COMPONENTS


def reload_kicad_components(*, strict: bool = True) -> list["KiCadComponent"]:
    global _ALL_KICAD_COMPONENTS, _COMPONENTS_BY_LIBRARY_AND_NAME, _KNOWN_LIBRARIES
    _ALL_KICAD_COMPONENTS = load_kicad_component_from_json(strict=strict)
    _COMPONENTS_BY_LIBRARY_AND_NAME = None
    _KNOWN_LIBRARIES = None
    return _ALL_KICAD_COMPONENTS


def get_kicad_component_by_library_and_name(library: str, name: str) -> KiCadComponent | None:
    global _COMPONENTS_BY_LIBRARY_AND_NAME, _KNOWN_LIBRARIES

    if _COMPONENTS_BY_LIBRARY_AND_NAME is None or _KNOWN_LIBRARIES is None:
        all_components = get_all_kicad_components(strict=True)
        _COMPONENTS_BY_LIBRARY_AND_NAME = {
            (component.library, component.name): component for component in all_components
        }
        _KNOWN_LIBRARIES = {component.library for component in all_components}

    assert _COMPONENTS_BY_LIBRARY_AND_NAME is not None
    assert _KNOWN_LIBRARIES is not None

    if library not in _KNOWN_LIBRARIES:
        raise CircuitException(f"KiCad library '{library}' not found.")

    component = _COMPONENTS_BY_LIBRARY_AND_NAME.get((library, name))
    if component is not None:
        return component

    raise CircuitException(f"Component '{name}' not found in KiCad library '{library}'.")
