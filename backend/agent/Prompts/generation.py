from backend.agent.Prompts.schematic_policy import build_schematic_generation_instructions


def build_agent_instructions_interative(circuit_how_to_build: str) -> str:
    return build_schematic_generation_instructions(
        circuit_how_to_build.strip(),
        always_generate=False,
    )
