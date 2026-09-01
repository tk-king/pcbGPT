from __future__ import annotations

from typing import Annotated

from backend.agent.Core.write_circuit_code import execute_circuit_code
from backend.core.agents import RunContextWrapper, function_tool
from backend.core.agents.builtin_tools import web_search_tool
from backend.data.Component.Search import tool_search_components
from backend.tools.collection.component_knowledge import obtain_needed_information


def _tool_search_components_default_top_k(
    query: Annotated[str, "Generic component type or package to search for."],
) -> str:
    return tool_search_components(query=query, top_k=5)


def _write_circuit_code_tool(
    wrapper: RunContextWrapper,
    code: Annotated[
        str,
        "Final Python circuit DSL code. Use this to create or update the schematic.",
    ],
) -> str:
    return execute_circuit_code(wrapper, code)


def _obtain_needed_information_tool(
    wrapper: RunContextWrapper,
    library: Annotated[str, "KiCad library name of the component, e.g. 'Battery_Management'"],
    name: Annotated[str, "KiCad component name, e.g. 'MCP73871'"],
) -> str:
    """Obtain schematic-design guidance for a specific component."""
    model_name = getattr(wrapper.context, "generation_model_name", None)
    return obtain_needed_information(library, name, model=model_name)


def build_schematic_tools():
    return [
        function_tool(
            web_search_tool,
            name="web_search",
            description="Search the web when local component and datasheet tools are insufficient.",
        ),
        function_tool(
            _tool_search_components_default_top_k,
            name="search_components",
            description="Find the KiCad symbol and footprint for a generic component type before wiring it. Use this before obtain_needed_information when you still need to identify the concrete KiCad part.",
        ),
        function_tool(
            _obtain_needed_information_tool,
            name="obtain_needed_information",
            description="Obtain datasheet-derived design guidance for a specific component, such as pin behavior, rails, decoupling, required support parts, and typical usage. Do not treat it as the final source of KiCad pin numbers when search_components provides the symbol mapping.",
        ),
        function_tool(
            _write_circuit_code_tool,
            name="write_circuit_code",
            description="Create or update the schematic by executing the final Python circuit DSL code. Use this after search_components and any required obtain_needed_information calls.",
        ),
    ]
