from dataclasses import dataclass
from pathlib import Path

from backend.core.agents import Agent

from backend.agent.Core.schematic_toolkit import build_schematic_tools
from backend.agent.Prompts.generation import build_agent_instructions_interative



@dataclass
class AgentContext:
    circuit: str | None = None
    kicad_project_name: str | None = None
    kicad_project_path: str | None = None
    schematic_pdf_path: str | None = None
    schematic_pdf_base64: str | None = None
    kicad_errors: str | None = None
    prompt_description: str | None = None
    generation_model_name: str | None = None
    validation_model_name: str | None = None
    validation_enabled: bool | None = None
    validation_session_id: str | None = None
    validation_has_run: bool = False
    sync_folder_path: str | None = None
    sync_mode: str | None = None
    sync_display_path: str | None = None
    client_folder_name: str | None = None
    imported_netlist: str | None = None
    project_version: int = 0



README_PATH = Path(__file__).resolve().parents[2] / "Circuit" / "readme.md"

with README_PATH.open("r", encoding="utf-8") as f:
    circuit_how_to_build = f.read()

agent_instructions = build_agent_instructions_interative(circuit_how_to_build)


_tools = [
    *build_schematic_tools(),
]

agent = Agent(
    name="PCBGPT Agent",
    instructions=agent_instructions,
    model=None,
    tools=_tools,
)
