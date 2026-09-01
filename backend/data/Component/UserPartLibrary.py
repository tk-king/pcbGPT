from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import sexpdata

from backend.config import KICAD_FOOTPRINT_PATH, KICAD_SYMBOL_PATH
from backend.data.Component.ComponentParser import parse_kicad_symbol_lib_file
from backend.data.Component.FootprintParser import parse_footprint_file, reload_all_footprints
from backend.data.Component.KiCadComponent import KiCadComponent, reload_kicad_components
from backend.data.Component.KiCadFootprint import KiCadFootprint
from backend.data.Component.Search import rebuild_component_text_index, serialize_component
from backend.runtime_paths import datasets_dir


def _sanitize_filename(filename: str, expected_suffix: str) -> str:
    name = Path(filename or "").name
    if not name:
        raise ValueError(f"Missing {expected_suffix} filename.")
    if Path(name).suffix.lower() != expected_suffix.lower():
        raise ValueError(f"Expected a {expected_suffix} file, got '{name}'.")
    cleaned = re.sub(r"[^A-Za-z0-9._+-]", "_", name)
    if not cleaned.lower().endswith(expected_suffix.lower()):
        raise ValueError(f"Expected a {expected_suffix} file, got '{name}'.")
    return cleaned


def _resolve_user_library_root() -> Path:
    explicit = os.getenv("PCBGPT_KICAD_LIBRARY_ROOT")
    if explicit:
        return Path(explicit).expanduser()
    home = Path.home()
    if os.name == "nt":
        appdata = os.getenv("APPDATA")
        base = Path(appdata).expanduser() if appdata else home / "AppData" / "Roaming"
        return base / "kicad" / "pcbgpt-libraries"
    if (home / "Library").exists():
        return home / "Library" / "Application Support" / "kicad" / "pcbgpt-libraries"
    return home / ".local" / "share" / "kicad" / "pcbgpt-libraries"


def _resolve_symbol_root() -> Path:
    return _resolve_user_library_root() / "symbols"


def _resolve_footprint_root() -> Path:
    return _resolve_user_library_root() / "footprints"


def _resolve_step_root() -> Path:
    return _resolve_user_library_root() / "3dmodels"


def _configured_kicad_roots() -> tuple[Path | None, Path | None, Path | None]:
    symbol_root = Path(KICAD_SYMBOL_PATH).expanduser() if KICAD_SYMBOL_PATH else None
    footprint_root = Path(KICAD_FOOTPRINT_PATH).expanduser() if KICAD_FOOTPRINT_PATH else None
    model_root = None
    try:
        from backend.agent.tools.kicad_utils import detect_kicad_paths

        paths = detect_kicad_paths()
        symbol_root = Path(paths["symbol_path"]).expanduser() if paths.get("symbol_path") else symbol_root
        footprint_root = Path(paths["footprint_path"]).expanduser() if paths.get("footprint_path") else footprint_root
        model_root = Path(paths["model_path"]).expanduser() if paths.get("model_path") else None
    except Exception:
        raw_model_root = os.getenv("KICAD_3D_MODEL_PATH") or os.getenv("KICAD_3DMODEL_DIR")
        model_root = Path(raw_model_root).expanduser() if raw_model_root else None
    return symbol_root, footprint_root, model_root


def _mirror_if_writable(target: Path, data: bytes) -> str | None:
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    except Exception as exc:
        return str(exc)
    return None


def _attach_step_model_if_missing(footprint_path: Path, step_path: Path) -> None:
    footprint_text = footprint_path.read_text(encoding="utf-8")
    if "(model " in footprint_text:
        return
    model_block = (
        f'\n  (model "{step_path.as_posix()}"\n'
        "    (offset (xyz 0 0 0))\n"
        "    (scale (xyz 1 1 1))\n"
        "    (rotate (xyz 0 0 0))\n"
        "  )\n"
    )
    marker = footprint_text.rfind(")")
    if marker < 0:
        raise ValueError(f"Invalid KiCad footprint file: {footprint_path}")
    updated = footprint_text[:marker] + model_block + footprint_text[marker:]
    footprint_path.write_text(updated, encoding="utf-8")


def _components_dataset_path() -> Path:
    return datasets_dir() / "kicad_symbols.jsonl"


def _footprints_dataset_path() -> Path:
    return datasets_dir() / "kicad_footprints.jsonl"


def _write_component_dataset(updated_components: list[KiCadComponent]) -> None:
    dataset_path = _components_dataset_path()
    dataset_path.parent.mkdir(parents=True, exist_ok=True)
    serialized = [
        component.model_dump_json()
        for component in sorted(
            updated_components,
            key=lambda component: (component.library.lower(), component.name.lower()),
        )
    ]
    dataset_path.write_text("\n".join(serialized), encoding="utf-8")


def _write_footprint_dataset(updated_footprints: list[KiCadFootprint]) -> None:
    dataset_path = _footprints_dataset_path()
    dataset_path.parent.mkdir(parents=True, exist_ok=True)
    serialized = [
        footprint.model_dump_json()
        for footprint in sorted(
            updated_footprints,
            key=lambda footprint: (footprint.library.lower(), footprint.name.lower()),
        )
    ]
    dataset_path.write_text("\n".join(serialized), encoding="utf-8")


def _load_existing_components() -> list[KiCadComponent]:
    dataset_path = _components_dataset_path()
    if not dataset_path.exists():
        return []
    return reload_kicad_components(strict=False)


def _load_existing_footprints() -> list[KiCadFootprint]:
    dataset_path = _footprints_dataset_path()
    if not dataset_path.exists():
        return []
    return reload_all_footprints()


def _kicad_preferences_root() -> Path:
    explicit = os.getenv("KICAD_CONFIG_HOME")
    if explicit:
        return Path(explicit).expanduser()
    home = Path.home()
    if (home / "Library" / "Preferences" / "kicad").exists():
        return home / "Library" / "Preferences" / "kicad"
    if os.name == "nt":
        appdata = os.getenv("APPDATA")
        base = Path(appdata).expanduser() if appdata else home / "AppData" / "Roaming"
        return base / "kicad"
    return home / ".config" / "kicad"


def _table_dirs() -> list[Path]:
    root = _kicad_preferences_root()
    candidates: list[Path] = []
    if (root / "sym-lib-table").exists() or (root / "fp-lib-table").exists():
        candidates.append(root)
    if root.exists():
        versioned = sorted(
            [path for path in root.iterdir() if path.is_dir()],
            key=lambda path: tuple(int(part) if part.isdigit() else part for part in path.name.replace("-", ".").split(".")),
        )
        for path in versioned:
            if (
                (path / "sym-lib-table").exists()
                or (path / "fp-lib-table").exists()
                or bool(re.fullmatch(r"\d+(?:\.\d+)*", path.name))
            ):
                candidates.append(path)
    if not candidates and root.exists():
        candidates.append(root)
    return candidates


def _sexp_symbol(name: str) -> sexpdata.Symbol:
    return sexpdata.Symbol(name)


def _sexp_key(value: Any) -> str:
    if hasattr(value, "value"):
        return str(value.value()).lower()
    return str(value).lower()


def _lib_name(entry: list[Any]) -> str | None:
    for item in entry[1:]:
        if isinstance(item, list) and item and _sexp_key(item[0]) == "name" and len(item) >= 2:
            return str(item[1])
    return None


def _load_table(path: Path, table_name: str) -> list[list[Any]]:
    if not path.exists():
        return []
    loaded = sexpdata.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, list) or not loaded or _sexp_key(loaded[0]) != table_name:
        raise ValueError(f"Invalid KiCad table: {path}")
    entries: list[list[Any]] = []
    for item in loaded[1:]:
        if isinstance(item, list) and item and _sexp_key(item[0]) == "lib":
            entries.append(item)
    return entries


def _write_table(path: Path, table_name: str, entries: list[list[Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"({table_name}"]
    for entry in entries:
        lines.append(f"  {sexpdata.dumps(entry)}")
    lines.append(")")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _upsert_table_entry(path: Path, table_name: str, new_entry: list[Any]) -> None:
    entries = _load_table(path, table_name)
    target_name = _lib_name(new_entry)
    updated: list[list[Any]] = []
    replaced = False
    for entry in entries:
        if _lib_name(entry) == target_name:
            updated.append(new_entry)
            replaced = True
        else:
            updated.append(entry)
    if not replaced:
        updated.append(new_entry)
    _write_table(path, table_name, updated)


def _symbol_table_entry(library_name: str, symbol_path: Path) -> list[Any]:
    return [
        _sexp_symbol("lib"),
        [_sexp_symbol("name"), library_name],
        [_sexp_symbol("type"), "KiCad"],
        [_sexp_symbol("uri"), symbol_path.as_posix()],
        [_sexp_symbol("options"), ""],
        [_sexp_symbol("descr"), f"PCBGPT uploaded symbols for {library_name}"],
    ]


def _footprint_table_entry(library_name: str, footprint_dir: Path) -> list[Any]:
    return [
        _sexp_symbol("lib"),
        [_sexp_symbol("name"), library_name],
        [_sexp_symbol("type"), "KiCad"],
        [_sexp_symbol("uri"), footprint_dir.as_posix()],
        [_sexp_symbol("options"), ""],
        [_sexp_symbol("descr"), f"PCBGPT uploaded footprints for {library_name}"],
    ]


def _register_in_kicad_tables(library_name: str, symbol_path: Path, footprint_dir: Path) -> list[str]:
    updated_paths: list[str] = []
    for table_dir in _table_dirs():
        sym_table = table_dir / "sym-lib-table"
        fp_table = table_dir / "fp-lib-table"
        _upsert_table_entry(sym_table, "sym_lib_table", _symbol_table_entry(library_name, symbol_path))
        _upsert_table_entry(fp_table, "fp_lib_table", _footprint_table_entry(library_name, footprint_dir))
        updated_paths.append(str(sym_table))
        updated_paths.append(str(fp_table))
    return updated_paths


def install_uploaded_part(
    *,
    symbol_filename: str,
    symbol_bytes: bytes,
    footprint_filename: str,
    footprint_bytes: bytes,
    step_filename: str | None = None,
    step_bytes: bytes | None = None,
) -> dict[str, Any]:
    symbol_root = _resolve_symbol_root()
    footprint_root = _resolve_footprint_root()
    step_root = _resolve_step_root()
    symbol_root.mkdir(parents=True, exist_ok=True)
    footprint_root.mkdir(parents=True, exist_ok=True)
    step_root.mkdir(parents=True, exist_ok=True)

    safe_symbol_name = _sanitize_filename(symbol_filename, ".kicad_sym")
    safe_footprint_name = _sanitize_filename(footprint_filename, ".kicad_mod")

    safe_step_name: str | None = None
    if step_filename:
        step_suffix = Path(step_filename).suffix
        if not step_suffix:
            raise ValueError("STEP filename must include an extension.")
        safe_step_name = _sanitize_filename(step_filename, step_suffix)

    symbol_target = symbol_root / safe_symbol_name
    symbol_target.write_bytes(symbol_bytes)

    library_name = symbol_target.stem
    footprint_library_dir = footprint_root / f"{library_name}.pretty"
    footprint_library_dir.mkdir(parents=True, exist_ok=True)
    footprint_target = footprint_library_dir / safe_footprint_name
    footprint_target.write_bytes(footprint_bytes)

    step_target: Path | None = None
    if safe_step_name and step_bytes is not None:
        step_library_dir = step_root / f"{library_name}.3dshapes"
        step_library_dir.mkdir(parents=True, exist_ok=True)
        step_target = step_library_dir / safe_step_name
        step_target.write_bytes(step_bytes)
        _attach_step_model_if_missing(footprint_target, step_target)

    new_components = parse_kicad_symbol_lib_file(symbol_target)
    parsed_footprint = parse_footprint_file(footprint_target, library_name)
    if parsed_footprint is None:
        raise ValueError(f"Failed to parse uploaded footprint '{footprint_target.name}'.")

    existing_components = _load_existing_components()
    merged_components = {
        (component.library, component.name): component for component in existing_components
    }
    for component in new_components:
        merged_components[(component.library, component.name)] = component
    _write_component_dataset(list(merged_components.values()))
    reload_kicad_components(strict=False)

    existing_footprints = _load_existing_footprints()
    merged_footprints = {
        (footprint.library, footprint.name): footprint for footprint in existing_footprints
    }
    merged_footprints[(parsed_footprint.library, parsed_footprint.name)] = parsed_footprint
    _write_footprint_dataset(list(merged_footprints.values()))
    reload_all_footprints()

    warnings: list[str] = []
    try:
        from backend.data.Component.Embedding import upsert_component_embeddings

        upsert_component_embeddings(new_components)
    except Exception as exc:
        warnings.append(f"Embedding update failed: {exc}")

    try:
        rebuild_component_text_index()
    except Exception as exc:
        warnings.append(f"Text index rebuild failed: {exc}")

    registered_tables = _register_in_kicad_tables(
        library_name=library_name,
        symbol_path=symbol_target,
        footprint_dir=footprint_library_dir,
    )

    mirrored_files: dict[str, str | None] = {
        "symbol": None,
        "footprint": None,
        "step": None,
    }
    configured_symbol_root, configured_footprint_root, configured_model_root = _configured_kicad_roots()
    if configured_symbol_root is not None:
        mirror_error = _mirror_if_writable(configured_symbol_root / safe_symbol_name, symbol_bytes)
        if mirror_error:
            warnings.append(f"Shared symbol library mirror skipped: {mirror_error}")
        else:
            mirrored_files["symbol"] = str(configured_symbol_root / safe_symbol_name)
    if configured_footprint_root is not None:
        mirror_path = configured_footprint_root / f"{library_name}.pretty" / safe_footprint_name
        mirror_error = _mirror_if_writable(mirror_path, footprint_target.read_bytes())
        if mirror_error:
            warnings.append(f"Shared footprint library mirror skipped: {mirror_error}")
        else:
            mirrored_files["footprint"] = str(mirror_path)
    if step_target is not None and configured_model_root is not None:
        mirror_path = configured_model_root / f"{library_name}.3dshapes" / step_target.name
        mirror_error = _mirror_if_writable(mirror_path, step_target.read_bytes())
        if mirror_error:
            warnings.append(f"Shared STEP library mirror skipped: {mirror_error}")
        else:
            mirrored_files["step"] = str(mirror_path)

    return {
        "library": library_name,
        "message": f"Installed {len(new_components)} part(s) into KiCad library '{library_name}'.",
        "installed_files": {
            "symbol": str(symbol_target),
            "footprint": str(footprint_target),
            "step": str(step_target) if step_target else None,
        },
        "mirrored_files": mirrored_files,
        "registered_tables": registered_tables,
        "components": [serialize_component(component) for component in new_components],
        "warnings": warnings,
    }
