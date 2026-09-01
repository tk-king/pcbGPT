from __future__ import annotations

import base64
import os
import subprocess
import tempfile
import traceback
import uuid
import shutil
from pathlib import Path

from backend.core.agents import RunContextWrapper
from backend.Circuit.ImporterExporter.NetlistImporterExporter import NetlistImporterExporter
from backend.agent.Core.validation_runner import run_validation_sync
from backend.core.exceptions import collect_circuit_errors


def _env_truthy(name: str) -> bool:
    value = os.getenv(name, "").strip().lower()
    return value in {"1", "true", "yes", "on"}


def _validation_enabled(context: object) -> bool:
    override = getattr(context, "validation_enabled", None)
    if override is None:
        return _env_truthy("AGENT_USE_VALIDATOR_FEEDBACK")
    return bool(override)


def _sync_kicad_project_output(source_dir: Path, dest_dir: Path) -> None:
    """Copy generated KiCad outputs into the user-selected sync folder."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    extensions = {
        item.suffix
        for item in source_dir.iterdir()
        if item.is_file() and item.suffix
    }
    for ext in extensions:
        for existing in dest_dir.glob(f"*{ext}"):
            if existing.is_file():
                existing.unlink()
    for item in source_dir.iterdir():
        target = dest_dir / item.name
        if item.is_dir():
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(item, target)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, target)


def _auto_complete_final_step(context: object) -> None:
    """Mark the final plan step done when circuit generation succeeds."""
    steps = getattr(context, "plan_steps", None)
    if not isinstance(steps, list) or not steps:
        return

    if str(getattr(context, "plan_status", "")) == "completed":
        return

    try:
        current_idx = int(getattr(context, "plan_current_index", 0) or 0)
    except Exception:
        return

    if current_idx != len(steps) - 1:
        return

    for idx, step in enumerate(steps):
        if not isinstance(step, dict):
            continue
        if idx < current_idx:
            step["status"] = "done"
        elif idx == current_idx:
            step["status"] = "done"
            if not step.get("summary"):
                step["summary"] = "Completed after successful write_circuit_code execution."
        else:
            step["status"] = "pending"

    setattr(context, "plan_current_index", len(steps))
    setattr(context, "plan_status", "completed")

def execute_circuit_code(wrapper: RunContextWrapper, code: str) -> str:
    """Execute the provided Python circuit code and update the agent context."""
    keep_project = bool(getattr(wrapper.context, "sync_folder_path", None))

    exec_env: dict[str, object] = {}
    with collect_circuit_errors() as circuit_errors:
        try:
            exec(code, exec_env)  # noqa: S102 - executing generated circuit code is expected.
        except Exception:
            error_message = f"Error executing circuit code:\n{traceback.format_exc()}"
            setattr(wrapper.context, "kicad_errors", error_message)
            return error_message

    if circuit_errors:
        lines = [f"- {err}" for err in circuit_errors]
        error_message = "Circuit code did not execute due to errors:\n" + "\n".join(lines)
        setattr(wrapper.context, "kicad_errors", error_message)
        return error_message

    circuit = None
    try:
        from backend.agent.tools.circuit_export import extract_circuit_from_exec_env

        circuit = extract_circuit_from_exec_env(exec_env)
    except Exception as exc:
        error_message = f"Error extracting circuit from code:\n{exc}"
        setattr(wrapper.context, "kicad_errors", error_message)
        return error_message

    feedback = ""
    if _validation_enabled(wrapper.context) and circuit is not None:
        # Validate the candidate before changing the stored circuit or writing to
        # the user's synced KiCad folder. A rejected candidate must leave the
        # last known project intact so the agent can safely revise and retry it.
        try:
            exporter = NetlistImporterExporter()
            netlist_content = exporter.export_circuit(circuit)
            prompt_text = getattr(wrapper.context, "prompt_description", None) or getattr(
                wrapper.context, "prompt", None
            )
            validation_model_name = getattr(wrapper.context, "validation_model_name", None)
            validation_output = run_validation_sync(
                code=code,
                netlist_content=netlist_content,
                prompt_text=prompt_text,
                max_turns=20,
                context=wrapper.context,
                validation_model_name=validation_model_name,
            )

            if hasattr(validation_output, "context_wrapper") and hasattr(validation_output.context_wrapper, "usage"):
                wrapper.usage.merge(validation_output.context_wrapper.usage)

            result = getattr(validation_output, "final_output", None)
            issues = getattr(result, "issues", None)
            is_working = getattr(result, "is_working", None)
            if is_working is False or (isinstance(issues, list) and issues):
                feedback_payload = {
                    "is_working": is_working,
                    "issues": issues or [],
                }
                error_message = f"Circuit validation failed:\n{feedback_payload}"
                setattr(wrapper.context, "kicad_errors", error_message)
                return error_message
        except Exception as exc:
            feedback = f"\nValidation feedback unavailable: {exc}"

    for field in (
        "schematic_pdf_path",
        "schematic_pdf_base64",
        "kicad_errors",
    ):
        setattr(wrapper.context, field, None)
    if not keep_project:
        wrapper.context.kicad_project_name = None
        wrapper.context.kicad_project_path = None

    wrapper.context.circuit = code

    try:
        from backend.Circuit.ImporterExporter.KiCADProject.project_generator import (
            generate_kicad_project,
        )

        sync_dir = getattr(wrapper.context, "sync_folder_path", None)
        sync_path = Path(sync_dir) if sync_dir else None
        staging_root: Path | None = None
        if sync_path:
            sync_path.mkdir(parents=True, exist_ok=True)
            preferred_name = getattr(wrapper.context, "client_folder_name", None) or sync_path.name
            wrapper.context.client_folder_name = preferred_name
            project_name = preferred_name
            staging_root = Path(tempfile.mkdtemp(prefix="pcbgpt_kicad_sync_"))
            output_root = staging_root
        else:
            project_name = f"schematic_{uuid.uuid4().hex[:8]}"
            output_root = Path(tempfile.mkdtemp(prefix="pcbgpt_kicad_"))

        try:
            generated_path = generate_kicad_project(
                circuits=[circuit],
                output_dir=output_root,
                project_name=project_name,
            )

            if sync_path:
                _sync_kicad_project_output(Path(generated_path), sync_path)
                project_path = sync_path
            else:
                project_path = Path(generated_path)
        finally:
            if staging_root is not None:
                shutil.rmtree(staging_root, ignore_errors=True)

        wrapper.context.kicad_project_name = project_name
        wrapper.context.kicad_project_path = str(project_path)

        sch_path = project_path / f"{project_name}.kicad_sch"
        pdf_path = project_path / f"{project_name}.pdf"
        kicad_cli = os.getenv(
            "KICAD_CLI", "/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli"
        )
        if not os.path.exists(kicad_cli):
            kicad_cli = "kicad-cli"

        pdf_result = subprocess.run(
            [kicad_cli, "sch", "export", "pdf",
                "-o", str(pdf_path), str(sch_path)],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if pdf_result.returncode != 0:
            stderr = pdf_result.stderr.strip()
            stdout = pdf_result.stdout.strip()
            details = stderr or stdout or "unknown error"
            wrapper.context.kicad_errors = f"kicad-cli failed: {details}"
        elif pdf_path.exists():
            wrapper.context.schematic_pdf_path = str(pdf_path)
            with open(pdf_path, "rb") as f:
                wrapper.context.schematic_pdf_base64 = base64.b64encode(f.read()).decode(
                    "ascii"
                )
        else:
            wrapper.context.kicad_errors = f"kicad-cli did not generate pdf at {pdf_path}"
    except Exception as exc:
        wrapper.context.kicad_errors = f"kicad project/pdf generation failed: {exc}"

    try:
        if getattr(wrapper.context, "kicad_project_path", None):
            current_version = getattr(wrapper.context, "project_version", 0) or 0
            wrapper.context.project_version = current_version + 1
    except Exception:
        pass

    try:
        _auto_complete_final_step(wrapper.context)
    except Exception:
        pass

    return "Circuit code executed successfully." + feedback
