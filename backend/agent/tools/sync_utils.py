import base64
import re
import subprocess
from pathlib import Path
from fastapi import HTTPException
import rich

from backend.agent.tools.circuit_export import (
    export_circuit_as_code,
)
from backend.data.converter.kicad_sch_to_netlist import kicad_sch_to_netlist


def resolve_kicad_cli() -> str:
    """Return kicad-cli path with env override and PATH fallback."""
    import os

    cli = os.getenv("KICAD_CLI", "/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli")
    if not Path(cli).exists():
        cli = "kicad-cli"
    return cli


def _upgrade_a4_schematic_to_a3(sch_path: Path) -> bool:
    """Change an imported standard A4 schematic to DIN A3 in place."""
    schematic = sch_path.read_text(encoding="utf-8")
    upgraded, replacements = re.subn(
        r'(?m)^(?P<indent>[ \t]*)\(paper[ \t]+"A4"\)[ \t]*$',
        lambda match: f'{match.group("indent")}(paper "A3")',
        schematic,
        count=1,
    )
    if replacements == 0:
        return False
    sch_path.write_text(upgraded, encoding="utf-8")
    return True


def import_kicad_folder(folder: Path, context: dict) -> dict:
    """Load .kicad_sch, export net/pdf, update context."""
    context = context or {}
    context["project_version"] = context.get("project_version", 0) + 1
    sch_files = list(folder.glob("*.kicad_sch"))
    if not sch_files:
        raise HTTPException(status_code=404, detail="No .kicad_sch found in folder.")
    sch_path = sch_files[0]
    project_name = sch_path.stem
    _upgrade_a4_schematic_to_a3(sch_path)

    # export netlist
    net_path = sch_path.with_suffix(".net")
    kicad_cli = resolve_kicad_cli()
    try:
        subprocess.run(
            [kicad_cli, "sch", "export", "netlist", "-o", str(net_path), str(sch_path)],
            check=False,
            timeout=60,
            capture_output=True,
            text=True,
        )
    except Exception as exc:  # noqa: BLE001
        rich.print(f"[red]kicad-cli export netlist failed:[/red] {exc}")

    netlist_content = net_path.read_text(encoding="utf-8") if net_path.exists() else None
    if netlist_content is None:
        try:
            netlist_content = kicad_sch_to_netlist(sch_path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            rich.print(f"[red]kicad_sch_to_netlist failed:[/red] {exc}")

    # Try importing the KiCad netlist back into the Python DSL representation.
    circuit_code = None
    if netlist_content:
        try:
            from backend.Circuit.ImporterExporter.NetlistImporterExporter import NetlistImporterExporter

            importer = NetlistImporterExporter()
            netlist_content = netlist_content.replace("\ufeff", "")
            circuit = importer.import_circuit(netlist_content, force_footprints=False)
            circuit_code = export_circuit_as_code(circuit)
        except Exception as exc:  # noqa: BLE001
            rich.print(f"[yellow]import_circuit failed:[/yellow] {exc}")
            circuit_code = None

    pdf_path = sch_path.with_suffix(".pdf")
    try:
        subprocess.run(
            [kicad_cli, "sch", "export", "pdf", "-o", str(pdf_path), str(sch_path)],
            check=False,
            timeout=60,
            capture_output=True,
            text=True,
        )
    except Exception as exc:  # noqa: BLE001
        rich.print(f"[red]kicad-cli export pdf failed:[/red] {exc}")

    pdf_b64 = None
    if pdf_path.exists():
        pdf_b64 = base64.b64encode(pdf_path.read_bytes()).decode("ascii")

    context.update(
        {
            "sync_folder_path": str(folder),
            "sync_mode": "imported",
            "kicad_project_path": str(folder),
            "kicad_project_name": project_name,
            "schematic_pdf_path": str(pdf_path) if pdf_path.exists() else None,
            "schematic_pdf_base64": pdf_b64,
            "circuit": circuit_code,
            "imported_netlist": netlist_content,
        }
    )
    context.setdefault("sync_display_path", str(folder))
    return context
