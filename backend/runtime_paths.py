from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


APP_NAME = "PCBGPT"


def resource_root() -> Path:
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass)
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def default_runtime_root() -> Path:
    if not getattr(sys, "frozen", False):
        return Path.cwd()
    home = Path.home()
    if sys.platform == "win32":
        appdata = os.getenv("APPDATA")
        base = Path(appdata).expanduser() if appdata else home / "AppData" / "Roaming"
        return base / APP_NAME
    if sys.platform == "darwin":
        return home / "Library" / "Application Support" / APP_NAME
    return home / ".local" / "share" / APP_NAME


def runtime_root() -> Path:
    explicit = os.getenv("PCBGPT_RUNTIME_ROOT")
    return Path(explicit).expanduser() if explicit else default_runtime_root()


def datasets_dir() -> Path:
    return Path(os.getenv("PCBGPT_DATASETS_DIR", runtime_root() / "Datasets"))


def datasheets_dir() -> Path:
    return Path(os.getenv("PCBGPT_DATASHEETS_DIR", runtime_root() / "datasheets"))


def cache_dir() -> Path:
    return Path(os.getenv("PCBGPT_CACHE_DIR", runtime_root() / ".cache"))


def frontend_dist_dir() -> Path:
    explicit = os.getenv("PCBGPT_FRONTEND_DIST")
    if explicit:
        path = Path(explicit)
        if (path / "index.html").is_file():
            return path

    root = resource_root()
    candidates = [
        root / "frontend-dist",
        root / "Resources" / "frontend-dist",
        root.parent / "Resources" / "frontend-dist",
        root.parent.parent / "Resources" / "frontend-dist",
    ]

    executable_path = Path(sys.executable).resolve()
    candidates.extend(
        [
            executable_path.parent / "frontend-dist",
            executable_path.parent.parent / "Resources" / "frontend-dist",
        ]
    )

    seen: set[Path] = set()
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        if (resolved / "index.html").is_file():
            return resolved

    return candidates[0]


def settings_db_path() -> Path:
    return Path(os.getenv("PCBGPT_SETTINGS_DB_PATH", runtime_root() / "settings.db"))


def sessions_db_path() -> Path:
    return Path(os.getenv("PCBGPT_SESSIONS_DB_PATH", runtime_root() / "sessions.db"))


def custom_sessions_db_path() -> Path:
    return Path(
        os.getenv("PCBGPT_CUSTOM_SESSIONS_DB_PATH", runtime_root() / "custom_sessions.db")
    )


def sync_root() -> Path:
    return Path(os.getenv("PCBGPT_SYNC_ROOT", runtime_root() / "sync-workspaces"))


def temp_root() -> Path:
    return Path(os.getenv("PCBGPT_TMP_DIR", runtime_root() / "tmp"))


def seed_root() -> Path:
    return resource_root() / "seed"


def _copy_missing(source: Path, destination: Path) -> None:
    if source.is_dir():
        destination.mkdir(parents=True, exist_ok=True)
        for child in source.iterdir():
            _copy_missing(child, destination / child.name)
        return
    if destination.exists():
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def prepare_packaged_runtime() -> Path:
    root = runtime_root()
    root.mkdir(parents=True, exist_ok=True)
    datasets_dir().mkdir(parents=True, exist_ok=True)
    datasheets_dir().mkdir(parents=True, exist_ok=True)
    cache_dir().mkdir(parents=True, exist_ok=True)
    sync_root().mkdir(parents=True, exist_ok=True)
    temp_root().mkdir(parents=True, exist_ok=True)

    os.environ.setdefault("PCBGPT_RUNTIME_ROOT", str(root))
    os.environ.setdefault("PCBGPT_DATASETS_DIR", str(datasets_dir()))
    os.environ.setdefault("PCBGPT_DATASHEETS_DIR", str(datasheets_dir()))
    os.environ.setdefault("PCBGPT_CACHE_DIR", str(cache_dir()))
    os.environ.setdefault("PCBGPT_FRONTEND_DIST", str(frontend_dist_dir()))
    os.environ.setdefault("PCBGPT_SETTINGS_DB_PATH", str(settings_db_path()))
    os.environ.setdefault("PCBGPT_SESSIONS_DB_PATH", str(sessions_db_path()))
    os.environ.setdefault("PCBGPT_CUSTOM_SESSIONS_DB_PATH", str(custom_sessions_db_path()))
    os.environ.setdefault("PCBGPT_SYNC_ROOT", str(sync_root()))
    os.environ.setdefault("PCBGPT_TMP_DIR", str(temp_root()))

    bundle_seed_root = seed_root()
    bundled_datasets = bundle_seed_root / "Datasets"
    if bundled_datasets.exists():
        _copy_missing(bundled_datasets, datasets_dir())

    return root
