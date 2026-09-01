from __future__ import annotations

import keyword
import re

from backend.Circuit.Circuit import Circuit, SubCircuitResult
from backend.Circuit.Component import Component
from backend.core.exceptions import CircuitException
from backend.Circuit.ImporterExporter.NetlistImporterExporter import (
    NetlistImporterExporter,
)
from backend.Circuit.Net import Net


class CircuitCodeError(Exception):
    """Raised when stored circuit code cannot be executed or exported."""


_NO_CIRCUIT_ERROR = (
    "Circuit code executed, but no Circuit instance was found. "
    "Ensure the code assigns the circuit to a variable."
)


def _coerce_to_circuit(candidate: object) -> Circuit | None:
    if isinstance(candidate, Circuit):
        return candidate
    if isinstance(candidate, SubCircuitResult):
        return candidate.circuit
    return None


def _circuits_from_values(values: list[object]) -> list[Circuit]:
    circuits: list[Circuit] = []
    for value in values:
        circuit = _coerce_to_circuit(value)
        if circuit is not None:
            circuits.append(circuit)
    return circuits


def _circuits_from_components(values: list[object]) -> list[Circuit]:
    circuits: list[Circuit] = []
    seen_ids: set[int] = set()
    for value in values:
        if isinstance(value, (Component, Net)) and value.circuit is not None:
            circuit = value.circuit
            circuit_id = id(circuit)
            if circuit_id in seen_ids:
                continue
            seen_ids.add(circuit_id)
            circuits.append(circuit)
    return circuits


def _invoke_circuit_builders(exec_env: dict[str, object]) -> list[Circuit]:
    circuits: list[Circuit] = []
    seen_builders: set[int] = set()
    for name, value in exec_env.items():
        if name.startswith("__"):
            continue
        if not callable(value):
            continue
        if not getattr(value, "_is_circuit_builder", False):
            continue
        builder_id = id(value)
        if builder_id in seen_builders:
            continue
        seen_builders.add(builder_id)
        try:
            result = value()
        except TypeError as exc:  # noqa: BLE001 - surface useful problems
            message = str(exc)
            if "required positional argument" in message or "positional arguments" in message:
                continue
            raise CircuitCodeError(
                f"Circuit builder '{name}' raised an error: {exc}",
            ) from exc
        except Exception as exc:  # noqa: BLE001 - bubble up builder failures
            raise CircuitCodeError(
                f"Circuit builder '{name}' raised an error: {exc}",
            ) from exc

        circuit = _coerce_to_circuit(result)
        if circuit is not None:
            circuits.append(circuit)
    return circuits


def extract_circuit_from_exec_env(exec_env: dict[str, object]) -> Circuit:
    """Return the last Circuit detected in the executed environment."""

    user_values = [value for key, value in exec_env.items() if not key.startswith("__")]

    circuits = _circuits_from_values(user_values)
    if not circuits:
        circuits = _circuits_from_components(user_values)
    if not circuits:
        circuits = _invoke_circuit_builders(exec_env)

    if not circuits:
        raise CircuitCodeError(_NO_CIRCUIT_ERROR)
    return circuits[-1]


def build_circuit_from_code(circuit_code: str) -> Circuit:
    """Execute saved circuit code and return the resulting Circuit instance."""
    exec_env: dict[str, object] = {}
    try:
        exec(circuit_code, exec_env)  # noqa: S102 - executing trusted schematic code
    except Exception as exc:  # noqa: BLE001 - bubble up useful error context
        raise CircuitCodeError(
            f"Stored circuit code failed to execute: {exc}",
        ) from exc

    return extract_circuit_from_exec_env(exec_env)


def convert_code_to_netlist(circuit_code: str) -> str:
    """Convert stored circuit code to a KiCad netlist string."""

    circuit = build_circuit_from_code(circuit_code)
    exporter = NetlistImporterExporter()
    try:
        return exporter.export_circuit(circuit)
    except CircuitException as exc:
        raise CircuitCodeError(f"Failed to export circuit netlist: {exc}") from exc


def _net_var_name(net_name: str) -> str:
    raw = (net_name or "net").strip().lower()
    # Convert arbitrary net labels (e.g. "Net-(BC1-B)") into valid identifiers.
    var = re.sub(r"[^0-9a-zA-Z_]+", "_", raw)
    var = re.sub(r"_+", "_", var).strip("_")
    if not var:
        var = "net"
    if var[0].isdigit():
        var = f"net_{var}"
    if keyword.iskeyword(var):
        var = f"net_{var}"
    return var


def _component_var_name(ref: str) -> str:
    raw = (ref or "component").strip()
    var = re.sub(r"[^0-9a-zA-Z_]+", "_", raw)
    var = re.sub(r"_+", "_", var).strip("_")
    if not var:
        var = "component"
    if var[0].isdigit():
        var = f"component_{var}"
    if keyword.iskeyword(var):
        var = f"component_{var}"
    return var


def export_circuit_as_code(circuit: Circuit, include_imports: bool = True) -> str:
    """Serialize a Circuit instance into executable Python schematic code."""
    if circuit is None:
        raise CircuitCodeError("No circuit provided.")

    lines: list[str] = []
    if include_imports:
        lines.append("from backend.Circuit import Circuit")
        lines.append("")
    lines.append("circuit = Circuit()")
    lines.append("with circuit:")
    indent = "    "

    pin_lookup: dict[int, tuple[str, str]] = {}
    component_var_names: dict[str, str] = {}
    used_component_vars: set[str] = set()
    for ref, comp in sorted(circuit.components.items()):
        base_var = _component_var_name(ref)
        comp_var = base_var
        suffix = 2
        while comp_var in used_component_vars:
            comp_var = f"{base_var}_{suffix}"
            suffix += 1
        used_component_vars.add(comp_var)
        component_var_names[ref] = comp_var
        component_args = [f"name={comp.name!r}", f"library={comp.library!r}"]
        if comp.value is not None:
            component_args.append(f"value={comp.value!r}")
        if comp.footprint is not None:
            component_args.append(f"footprint={comp.footprint!r}")
        if getattr(comp, "optional", False):
            component_args.append("optional=True")
        if not getattr(comp, "compare_value", True):
            component_args.append("compare_value=False")
        value_tolerance = getattr(comp, "value_tolercance", None)
        if value_tolerance is not None:
            component_args.append(f"value_tolercance={value_tolerance!r}")
        lines.append(
            f"{indent}{comp_var} = circuit.add_component({', '.join(component_args)})"
        )
        for pin_name, pin in comp.pins.items():
            pin_lookup[id(pin)] = (comp_var, pin_name)

    ordered_nets = sorted(circuit.nets.values(), key=lambda n: n.ref or n.name or "")
    skipped_net_names: set[str] = set()
    net_var_names: dict[str, str] = {}
    used_net_vars: set[str] = set()
    for net in ordered_nets:
        net_name = net.name or (net.ref or "NET")
        if "unconnected" in net_name.lower():
            skipped_net_names.add(net_name)
            continue
        base_var = _net_var_name(net_name)
        net_var = base_var
        suffix = 2
        while net_var in used_net_vars:
            net_var = f"{base_var}_{suffix}"
            suffix += 1
        used_net_vars.add(net_var)
        net_var_names[net_name] = net_var
        lines.append(f"{indent}{net_var} = circuit.add_net({net_name!r})")

    for net in ordered_nets:
        net_name = net.name or (net.ref or "NET")
        if net_name in skipped_net_names:
            continue
        net_var = net_var_names[net_name]
        for pin in net.pins:
            comp_ref, pin_name = pin_lookup.get(id(pin), (None, None))
            if comp_ref is None:
                continue
            lines.append(f"{indent}{net_var} & {comp_ref}.pins[{pin_name!r}]")

    return "\n".join(lines)
