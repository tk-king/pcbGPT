import logging
import os
from pathlib import Path
from typing import Any, List, Optional, Set

from dotenv import load_dotenv
import sexpdata
from tqdm.auto import tqdm
import re

from backend.data.Component.KiCadFootprint import KiCadFootprint
from backend.data.Component.KiCadComponent import KiCadComponent
from backend.runtime_paths import datasets_dir

logger = logging.getLogger(__name__)
_ALL_KICAD_FOOTPRINTS: List[KiCadFootprint] | None = None

# Load .env for local runs without pulling in the full `backend.config` side effects.
load_dotenv()
KICAD_FOOTPRINT_PATH = os.getenv("KICAD_FOOTPRINT_PATH", None)




def parse_all_footprints() -> List[KiCadFootprint]:
    """
    Parse all KiCad footprints found under KICAD_FOOTPRINT_PATH.

    Returns a flat list of KiCadFootprint instances containing metadata
    extracted from each ``.kicad_mod`` file.
    """
    if not KICAD_FOOTPRINT_PATH:
        raise ValueError("KICAD_FOOTPRINT_PATH is not configured")

    root_path = Path(KICAD_FOOTPRINT_PATH)
    if not root_path.exists():
        raise FileNotFoundError(f"KICAD_FOOTPRINT_PATH does not exist: {root_path}")

    footprint_dirs = sorted(p for p in root_path.glob("*.pretty") if p.is_dir())
    logger.info("Found %d footprint libraries to parse", len(footprint_dirs))

    footprints: List[KiCadFootprint] = []
    for library_dir in tqdm(footprint_dirs, desc="Parsing KiCad footprints"):
        library_name = library_dir.stem
        for footprint_file in sorted(library_dir.glob("*.kicad_mod")):
            footprint = _parse_footprint_file(footprint_file, library_name)
            if footprint:
                footprints.append(footprint)

    logger.info(
        "Parsed %d footprints across %d libraries",
        len(footprints),
        len(footprint_dirs),
    )
    data_dir = datasets_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    save_path = data_dir / "kicad_footprints.jsonl"
    json_footprints = [footprint.model_dump_json() for footprint in footprints]
    save_path.write_text("\n".join(json_footprints), encoding="utf-8")
    logger.info("Saved parsed footprints to %s", save_path)
    return footprints


def _parse_footprint_file(
    file_path: Path, library_name: str
) -> Optional[KiCadFootprint]:
    """
    Parse a single KiCad ``.kicad_mod`` footprint file.
    """
    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception as exc:
        logger.warning("Failed to read footprint %s: %s", file_path, exc)
        return None

    try:
        sexp = sexpdata.loads(content)
    except Exception as exc:
        logger.warning("Cannot parse footprint %s: %s", file_path, exc)
        return None

    if not isinstance(sexp, list) or not sexp:
        logger.debug("Skipping empty or invalid footprint: %s", file_path)
        return None

    description = ""
    tags = ""
    pad_count = 0
    pad_types: Set[str] = set()

    for element in sexp[1:]:
        if not isinstance(element, list) or not element:
            continue

        key = _key(element[0])
        if key == "descr" and len(element) >= 2:
            description = _stringify(element[1])
        elif key == "tags" and len(element) >= 2:
            tags = _stringify(element[1])
        elif key == "pad":
            pad_count += 1
            pad_type = _resolve_pad_type(element)
            if pad_type:
                pad_types.add(pad_type)

    keywords = _build_keywords(tags, description)

    return KiCadFootprint(
        library=library_name,
        name=file_path.stem,
        description=description,
        tags=tags,
        keywords=keywords,
        pad_count=pad_count,
        pad_types=pad_types,
    )


def parse_footprint_file(file_path: Path, library_name: str) -> Optional[KiCadFootprint]:
    return _parse_footprint_file(file_path, library_name)


def _resolve_pad_type(pad_expr: List[Any]) -> Optional[str]:
    """
    Extract pad type from a pad S-expression.
    The KiCad format looks like: (pad "1" smd rect ...)
    where the third token is the pad type.
    """
    try:
        if len(pad_expr) >= 3:
            pad_type_token = pad_expr[2]
            return _key(pad_type_token)
    except Exception as exc:
        logger.debug("Failed to resolve pad type in %s: %s", pad_expr, exc)
    return None

def get_footprint_for_component(component: KiCadComponent) -> KiCadComponent:
    footprints: list[KiCadFootprint] = load_all_footprints()
    fp_filters = component.fp_filters.strip()
    default_footprint = (component.default_footprint or "").strip()

    # KiCad stores multiple footprint filters as a space separated string, so expand
    # them into individual glob expressions and match either footprint name or
    # library-qualified name (lib:footprint).
    raw_filters = [flt for flt in re.split(r"\s+", fp_filters) if flt]
    if not raw_filters and default_footprint:
        raw_filters = [default_footprint]
    if not raw_filters:
        component.footprints = []
        return component

    def _compile_filter(pattern: str) -> re.Pattern[str]:
        regex = (
            "^"
            + re.escape(pattern).replace(r"\?", ".").replace(r"\*", ".*")
            + "$"
        )
        return re.compile(regex)

    compiled_filters = [_compile_filter(flt) for flt in raw_filters]

    def _matches(fp: KiCadFootprint) -> bool:
        candidates = (fp.name, f"{fp.library}:{fp.name}")
        return any(pattern.match(candidate) for pattern in compiled_filters for candidate in candidates)

    matching_footprints = [fp for fp in footprints if _matches(fp)]
    component.footprints = matching_footprints
    return component

def load_all_footprints() -> List[KiCadFootprint]:
    """
    Load all parsed KiCad footprints from the saved JSONL file.

    Returns a list of KiCadFootprint instances.
    """
    global _ALL_KICAD_FOOTPRINTS
    if _ALL_KICAD_FOOTPRINTS is not None:
        return _ALL_KICAD_FOOTPRINTS

    data_dir = datasets_dir()
    save_path = data_dir / "kicad_footprints.jsonl"
    if not save_path.exists():
        raise FileNotFoundError(f"Footprint data file not found: {save_path}")

    footprints: List[KiCadFootprint] = []
    with save_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                footprint = KiCadFootprint.model_validate_json(line)
                footprints.append(footprint)
            except ValueError as exc:
                logger.warning("Failed to parse footprint JSON: %s", exc)

    logger.info("Loaded %d footprints from %s", len(footprints), save_path)
    _ALL_KICAD_FOOTPRINTS = footprints
    return _ALL_KICAD_FOOTPRINTS


def reload_all_footprints() -> List[KiCadFootprint]:
    global _ALL_KICAD_FOOTPRINTS
    _ALL_KICAD_FOOTPRINTS = None
    return load_all_footprints()


def _build_keywords(tags: str, description: str) -> str:
    """
    Construct a simple keyword string from tags and description content.
    """
    keywords: Set[str] = set()
    if tags:
        keywords.update(word for word in tags.lower().split() if word)
    if description:
        description_words = description.lower().split()
        keywords.update(description_words[:50])
    return " ".join(sorted(keywords))


def _stringify(value: Any) -> str:
    if hasattr(value, "value"):
        return str(value.value())
    return str(value)


def _key(token: Any) -> str:
    if hasattr(token, "value"):
        return token.value().lower()
    return str(token).lower()
