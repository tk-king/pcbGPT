# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
import sys
import os

from PyInstaller.utils.hooks import collect_all


project_root = Path(SPECPATH).resolve().parents[1]
icon_assets_dir = project_root / "packaging" / "pyinstaller" / "assets"


def env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


include_seed_datasets = env_flag("PCBGPT_INCLUDE_SEED_DATASETS", False)
include_playwright = env_flag("PCBGPT_INCLUDE_PLAYWRIGHT", False)
include_ml_stack = env_flag("PCBGPT_INCLUDE_ML_STACK", False)

app_icon = None
if sys.platform == "darwin":
    app_icon = str(icon_assets_dir / "pcbgpt.icns")
elif sys.platform == "win32":
    app_icon = str(icon_assets_dir / "pcbgpt.ico")

datas = [
    (str(project_root / "frontend" / "dist"), "frontend-dist"),
    (str(project_root / "backend" / "Circuit" / "readme.md"), "backend/Circuit"),
    (str(project_root / "backend" / "Circuit" / "readme_llm.md"), "backend/Circuit"),
    (str(project_root / "backend" / "agent" / "Prompts" / "agent_interactive.md"), "backend/agent/Prompts"),
]

if include_seed_datasets and (project_root / "Datasets").is_dir():
    datas.append((str(project_root / "Datasets"), "seed/Datasets"))

binaries = []
hiddenimports = []
excludes = [
    "torch",
    "transformers",
    "sentence_transformers",
    "onnxruntime",
    "pyarrow",
    "pandas",
    "scipy",
    "sklearn",
    "selenium",
    "kubernetes",
]

if not include_playwright:
    excludes.append("playwright")

package_names = [
    "uvicorn",
    "fastapi",
    "starlette",
    "webview",
    "openai",
    "chromadb",
    "pymupdf",
    "langchain_openai",
]

if include_playwright:
    package_names.append("playwright")

if include_ml_stack:
    package_names.extend(
        [
            "sentence_transformers",
            "transformers",
            "torch",
        ]
    )

for package_name in package_names:
    package_datas, package_binaries, package_hiddenimports = collect_all(package_name)
    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_hiddenimports

a = Analysis(
    [str(project_root / "desktop_launcher.py")],
    pathex=[str(project_root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    name="PCBGPT",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=app_icon if sys.platform == "win32" else None,
)

if sys.platform == "darwin":
    app = BUNDLE(
        exe,
        name="PCBGPT.app",
        icon=app_icon,
        bundle_identifier="com.pcbgpt.desktop",
    )
