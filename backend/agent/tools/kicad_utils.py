import os
import sqlite3
import sys
from pathlib import Path

from backend.runtime_paths import settings_db_path


def _db_conn():
    db_path = settings_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(db_path)


def _init_table():
    with _db_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS kicad_config (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        conn.commit()


def _db_get(key: str) -> str | None:
    _init_table()
    with _db_conn() as conn:
        row = conn.execute(
            "SELECT value FROM kicad_config WHERE key = ?", (key,)
        ).fetchone()
        return row[0] if row else None


def _db_set(key: str, value: str) -> None:
    _init_table()
    with _db_conn() as conn:
        conn.execute(
            "INSERT INTO kicad_config (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
        conn.commit()


def _load_saved_paths() -> dict:
    sp = _db_get("symbol_path")
    fp = _db_get("footprint_path")
    mp = _db_get("model_path")
    result: dict[str, str | None] = {}
    if sp:
        result["symbol_path"] = sp
    if fp:
        result["footprint_path"] = fp
    if mp:
        result["model_path"] = mp
    return result


def _save_paths(symbol_path: str | None, footprint_path: str | None, model_path: str | None = None) -> None:
    if symbol_path:
        _db_set("symbol_path", symbol_path)
    if footprint_path:
        _db_set("footprint_path", footprint_path)
    if model_path:
        _db_set("model_path", model_path)


def _common_kicad_roots() -> list[Path]:
    roots: list[Path] = []
    if sys.platform == "darwin":
        for path in [
            "/Applications/KiCad/KiCad.app/Contents/SharedSupport",
            "/Applications/KiCad/KiCad.app/Contents/SharedSupport",
        ]:
            p = Path(path)
            if p.exists():
                roots.append(p)
        app_dir = Path("/Applications")
        if app_dir.exists():
            for entry in app_dir.iterdir():
                if entry.name.startswith("KiCad") and entry.is_dir():
                    candidate = entry / "Contents" / "SharedSupport"
                    if candidate.exists() and candidate not in roots:
                        roots.append(candidate)
    elif sys.platform == "win32":
        for base in [
            Path(os.environ.get("ProgramFiles", "C:\\Program Files")),
            Path(os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)")),
        ]:
            kicad_dir = base / "KiCad"
            if kicad_dir.exists():
                for entry in kicad_dir.iterdir():
                    candidate = entry / "share" / "kicad"
                    if candidate.exists():
                        roots.append(candidate)
    elif sys.platform == "linux":
        for path in [
            "/usr/share/kicad",
            "/usr/local/share/kicad",
        ]:
            p = Path(path)
            if p.exists():
                roots.append(p)
    return roots


def _is_valid_symbol_dir(path: Path) -> bool:
    return path.is_dir() and any(path.glob("*.kicad_sym"))


def _is_valid_footprint_dir(path: Path) -> bool:
    if not path.is_dir():
        return False
    return any(child.is_dir() and child.suffix == ".pretty" for child in path.iterdir()) or any(
        path.glob("*.kicad_mod")
    )


def _is_valid_model_dir(path: Path) -> bool:
    return path.is_dir()


def _find_symbol_dir(root: Path) -> Path | None:
    for candidate in [
        root / "symbols",
        root / "kicad" / "symbols",
    ]:
        if _is_valid_symbol_dir(candidate):
            return candidate
    return None


def _find_footprint_dir(root: Path) -> Path | None:
    for candidate in [
        root / "footprints",
        root / "kicad" / "footprints",
        root / "modules",
    ]:
        if _is_valid_footprint_dir(candidate):
            return candidate
    return None


def _find_model_dir(root: Path) -> Path | None:
    for candidate in [
        root / "3dmodels",
        root / "kicad" / "3dmodels",
        root / "packages3d",
    ]:
        if _is_valid_model_dir(candidate):
            return candidate
    return None


def _env_model_path() -> str | None:
    for key, value in os.environ.items():
        if key in {"KICAD_3D_MODEL_PATH", "KICAD_3DMODEL_DIR"} or (
            key.startswith("KICAD") and key.endswith("_3DMODEL_DIR")
        ):
            if value:
                p = Path(value)
                if _is_valid_model_dir(p):
                    return str(p.resolve())
    return None


def _env_paths() -> dict:
    env_symbol = os.getenv("KICAD_SYMBOL_PATH")
    env_footprint = os.getenv("KICAD_FOOTPRINT_PATH")
    env_model = _env_model_path()
    result: dict[str, str | None] = {
        "symbol_path": None,
        "footprint_path": None,
        "model_path": None,
    }
    if env_symbol:
        p = Path(env_symbol)
        if _is_valid_symbol_dir(p):
            result["symbol_path"] = str(p.resolve())
    if env_footprint:
        p = Path(env_footprint)
        if _is_valid_footprint_dir(p):
            result["footprint_path"] = str(p.resolve())
    if env_model:
        result["model_path"] = env_model
    return result


def detect_kicad_paths() -> dict:
    result = {
        "symbol_path": None,
        "footprint_path": None,
        "model_path": None,
        "symbol_path_valid": False,
        "footprint_path_valid": False,
        "model_path_valid": False,
        "error": None,
    }

    # 1. Check env vars first (explicit user configuration via .env)
    env_paths = _env_paths()
    if env_paths["symbol_path"]:
        result["symbol_path"] = env_paths["symbol_path"]
    if env_paths["footprint_path"]:
        result["footprint_path"] = env_paths["footprint_path"]
    if env_paths["model_path"]:
        result["model_path"] = env_paths["model_path"]
    if env_paths["symbol_path"] and env_paths["footprint_path"] and env_paths["model_path"]:
        result["symbol_path_valid"] = True
        result["footprint_path_valid"] = True
        result["model_path_valid"] = True
        return result

    # 2. Check saved config (from previous user setup via the UI)
    saved = _load_saved_paths()
    if saved.get("symbol_path") or saved.get("footprint_path") or saved.get("model_path"):
        sp = saved.get("symbol_path")
        fp = saved.get("footprint_path")
        mp = saved.get("model_path")
        if sp:
            p = Path(sp)
            if _is_valid_symbol_dir(p):
                result["symbol_path"] = str(p.resolve())
        if fp:
            p = Path(fp)
            if _is_valid_footprint_dir(p):
                result["footprint_path"] = str(p.resolve())
        if mp:
            p = Path(mp)
            if _is_valid_model_dir(p):
                result["model_path"] = str(p.resolve())
        if result["symbol_path"] and result["footprint_path"] and result["model_path"]:
            result["symbol_path_valid"] = True
            result["footprint_path_valid"] = True
            result["model_path_valid"] = True
            return result

    # 3. Fill in any missing from env/saved with auto-detection
    roots = _common_kicad_roots()
    for root in roots:
        if not result["symbol_path"]:
            sym = _find_symbol_dir(root)
            if sym is not None:
                result["symbol_path"] = str(sym.resolve())
        if not result["footprint_path"]:
            fp = _find_footprint_dir(root)
            if fp is not None:
                result["footprint_path"] = str(fp.resolve())
        if not result["model_path"]:
            mp = _find_model_dir(root)
            if mp is not None:
                result["model_path"] = str(mp.resolve())
        if result["symbol_path"] and result["footprint_path"] and result["model_path"]:
            result["symbol_path_valid"] = result["symbol_path"] is not None
            result["footprint_path_valid"] = result["footprint_path"] is not None
            result["model_path_valid"] = result["model_path"] is not None
            return result

    result["symbol_path_valid"] = result["symbol_path"] is not None
    result["footprint_path_valid"] = result["footprint_path"] is not None
    result["model_path_valid"] = result["model_path"] is not None
    result["error"] = "Could not find KiCad installation. Install KiCad or provide paths to the symbol, footprint, and 3D model directories."
    return result


def configure_kicad_paths(symbol_path: str = "", footprint_path: str = "", model_path: str = "") -> dict:
    result = {
        "kicad_symbol_valid": False,
        "kicad_footprint_valid": False,
        "kicad_model_valid": False,
    }

    if symbol_path:
        p = Path(symbol_path).expanduser().resolve()
        result["kicad_symbol_valid"] = _is_valid_symbol_dir(p)
    if footprint_path:
        p = Path(footprint_path).expanduser().resolve()
        result["kicad_footprint_valid"] = _is_valid_footprint_dir(p)
    if model_path:
        p = Path(model_path).expanduser().resolve()
        result["kicad_model_valid"] = _is_valid_model_dir(p)

    # Auto-detect any missing paths
    if not symbol_path or not footprint_path or not model_path:
        detected = detect_kicad_paths()
        if not symbol_path:
            result["kicad_symbol_valid"] = bool(detected.get("symbol_path_valid"))
        if not footprint_path:
            result["kicad_footprint_valid"] = bool(detected.get("footprint_path_valid"))
        if not model_path:
            result["kicad_model_valid"] = bool(detected.get("model_path_valid"))

    valid_symbol_path = symbol_path if result["kicad_symbol_valid"] and symbol_path else None
    valid_footprint_path = footprint_path if result["kicad_footprint_valid"] and footprint_path else None
    valid_model_path = model_path if result["kicad_model_valid"] and model_path else None

    # Persist and expose only valid user-provided paths. Auto-detected paths are
    # handled by detect_kicad_paths and should not rewrite the visible fields.
    _save_paths(valid_symbol_path, valid_footprint_path, valid_model_path)
    if valid_symbol_path:
        os.environ["KICAD_SYMBOL_PATH"] = str(Path(valid_symbol_path).expanduser().resolve())
    if valid_footprint_path:
        os.environ["KICAD_FOOTPRINT_PATH"] = str(Path(valid_footprint_path).expanduser().resolve())
    if valid_model_path:
        resolved_model_path = str(Path(valid_model_path).expanduser().resolve())
        os.environ["KICAD_3D_MODEL_PATH"] = resolved_model_path
        os.environ["KICAD_3DMODEL_DIR"] = resolved_model_path

    return result
