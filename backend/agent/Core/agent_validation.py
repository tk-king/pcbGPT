from pathlib import Path
from typing import Annotated
from backend.tools.collection.component_knowledge import obtain_needed_information
import backend.config as config_module
from pydantic import BaseModel, Field
from backend.core.agents import Agent, RunContextWrapper, function_tool
from backend.agent.Prompts.validation import build_validation_agent_instructions


def _query_component_usage_for_validation(
    wrapper: RunContextWrapper,
    library: Annotated[str, "KiCad library name of the component."],
    name: Annotated[str, "KiCad part name of the component."],
) -> str:
    configured_name = getattr(wrapper.context, "validation_model_name", None)
    print(
        f"[validation_agent] obtain_needed_information for {library}:{name} "
        f"using validation model {configured_name}"
    )
    return obtain_needed_information(
        library,
        name,
        model=configured_name,
    )


def get_component_knowledge_for_validation(
    library: str,
    name: str,
    model_name: str | None = None,
) -> dict:
    print(
        f"[validation_agent] precomputing component knowledge for {library}:{name} "
        f"using validation model {model_name}"
    )
    return {
        "part_name": f"{library}:{name}",
        "source": "datasheet",
        "knowledge": obtain_needed_information(
            library,
            name,
            model=model_name,
        ),
    }


schematic_tools = [
    function_tool(
        _query_component_usage_for_validation,
        name="query_component_usage_for_validation",
        description=(
            "Use this validation-only tool to retrieve the full datasheet-derived schematic-design "
            "knowledge for a complex component, including pin behavior, required external parts, "
            "reference circuits, constraints, and usage notes."
        ),
    ),
]

README_PATH = Path(__file__).resolve().parents[2] / "Circuit" / "readme.md"

with README_PATH.open("r", encoding="utf-8") as f:
    circuit_how_to_build = f.read()



class ValidationOutput(BaseModel):
    """Result of validating a PCB schematic."""
    is_working: bool = Field(
        ...,
        description=(
            "Set to false if you find even a single issue. "
            "Only set to true if the schematic fully works and there are no issues."
        ),
    )
    issues: list[str] = Field(
        default_factory=list,
        description=(
            "Each element must describe one DISTINCT root-cause issue in the schematic.\n"
            "- Do NOT add multiple entries that describe the same underlying problem.\n"
            "- If several sentences are needed for one issue, combine them into ONE string.\n"
            "- If there is only one root-cause problem, this list must contain exactly one element."
        ),
    )


def build_validation_agent(model_name: str) -> Agent:
    model = config_module.build_chat_model(model_name)
    return Agent(
        name="Schematic Validation Agent",
        instructions=build_validation_agent_instructions(circuit_how_to_build),
        model=model,
        tools=schematic_tools,
        output_type=ValidationOutput,
    )
