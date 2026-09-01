from __future__ import annotations

from typing import Any
import uuid
import re

from backend.core.agents import Runner, SQLiteSession
from backend.runtime_paths import custom_sessions_db_path

from backend.Circuit.Utils import _get_validation_component_input, build_validation_component_input
from backend.agent.Core.agent_validation import (
    build_validation_agent,
    get_component_knowledge_for_validation,
)


def _extract_required_nets(prompt_text: str | None, section: str) -> list[str]:
    """Extract required net names from prompt sections like 'Required input nets'."""
    if not prompt_text:
        return []
    pattern = re.compile(
        rf"required\s+{section}\s+nets[^\n]*:\s*\n(?P<body>(?:\s*-\s*.+\n)+)",
        flags=re.IGNORECASE,
    )
    match = pattern.search(prompt_text)
    if not match:
        return []
    nets: list[str] = []
    for raw_line in match.group("body").splitlines():
        line = raw_line.strip()
        if not line.startswith("-"):
            continue
        net_name = line.lstrip("-").strip()
        if net_name:
            nets.append(net_name)
    return nets


def _build_interface_contract(prompt_text: str | None) -> str:
    input_nets = _extract_required_nets(prompt_text, "input")
    output_nets = _extract_required_nets(prompt_text, "output")
    if not input_nets and not output_nets:
        return "N/A"
    return (
        "Use this interface contract as authoritative:\n"
        f"- required_input_nets: {input_nets or []}\n"
        f"- required_output_nets: {output_nets or []}\n"
        "- Interpret required net names as interface labels unless the prompt explicitly says they are fixed rails.\n"
        "- Do NOT fail validation only because a required net name looks like a power rail (e.g., +5V, 3V3, GND).\n"
    )


def _run_validation_sync(
    agent,
    input_text: str,
    max_turns: int = 20,
    session: SQLiteSession | None = None,
    context: Any | None = None,
):
    if session is None:
        return Runner.run_sync(agent, input_text, context=context, max_turns=max_turns)
    return Runner.run_sync(
        agent,
        input_text,
        context=context,
        max_turns=max_turns,
        session=session,
    )


def build_validation_input(
    *,
    prompt_text: str | None,
    code: str,
    netlist_content: str,
    validation_model_name: str | None = None,
) -> str:
    component_summary = _get_validation_component_input(netlist_content)
    component_input = build_validation_component_input(netlist_content)
    interface_contract = _build_interface_contract(prompt_text)
    component_knowledge: dict[str, object] = {}
    for component in component_input.components:
        library = component.library.strip().lower()
        part = component.part.strip().lower()
        if library == "device":
            if not (part.startswith("d") or part.startswith("led")):
                continue
        key = f"{component.library}:{component.part}"
        if key in component_knowledge:
            continue
        try:
            component_knowledge[key] = get_component_knowledge_for_validation(
                component.library,
                component.part,
                model_name=validation_model_name,
            )
        except Exception as exc:
            component_knowledge[key] = {"error": str(exc)}

    prefix = (
        (f"Here is the PCB schematic code generated for the following prompt:\n"
         f"{prompt_text}\n\n") if prompt_text else ""
    )
    return prefix + (
        "Validate the following PCB schematic code and report any issues.\n\n"
        "INTERFACE_CONTRACT:\n"
        f"{interface_contract}\n\n"
        "COMPONENT_SUMMARY:\n"
        f"{component_summary or 'N/A'}\n\n"
        "COMPONENT_KNOWLEDGE:\n"
        f"{component_knowledge or 'N/A'}\n\n"
        "CIRCUIT_CODE_PYTHON:\n"
        f"{code}\n"
    )

def build_followup_validation_input(code: str) -> str:
    return "I have tried to correct the circuit:\n" + code


def run_validation_sync(
    *,
    code: str,
    netlist_content: str,
    prompt_text: str | None,
    max_turns: int = 20,
    context: Any | None = None,
    validation_model_name: str | None = None,
) -> Any:
    validation_model_name = validation_model_name or getattr(context, "validation_model_name", None)
    if not validation_model_name:
        raise ValueError("No validation LLM configured.")
    active_validation_agent = build_validation_agent(validation_model_name)
    has_run = bool(getattr(context, "validation_has_run", False)) if context is not None else False
    if has_run:
        validation_input = build_followup_validation_input(code)
    else:
        validation_input = build_validation_input(
            prompt_text=prompt_text,
            code=code,
            netlist_content=netlist_content,
            validation_model_name=validation_model_name,
        )
    session = _get_validation_session(context)
    if session is None:
        result = _run_validation_sync(
            active_validation_agent,
            validation_input,
            max_turns=max_turns,
            context=context,
        )
    else:
        result = _run_validation_sync(
            active_validation_agent,
            validation_input,
            max_turns=max_turns,
            session=session,
            context=context,
        )
    if context is not None:
        context.validation_has_run = True
    return result



def _get_validation_session(context: Any | None) -> SQLiteSession | None:
    if context is None:
        return None
    if getattr(context, "validation_session_id", None) is None:
        context.validation_session_id = uuid.uuid4().hex
    return SQLiteSession(
        context.validation_session_id,
        db_path=str(custom_sessions_db_path()),
    )
