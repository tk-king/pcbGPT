from __future__ import annotations

import json
from typing import Dict, List

from pydantic import BaseModel, Field


class ValidationComponentInfo(BaseModel):
    library: str = Field(default="", description="KiCad library name, e.g. Device.")
    part: str = Field(default="", description="Component part name, e.g. R or NE555P.")
    refs: List[str] = Field(default_factory=list, description="Reference designators for this part.")
    values: List[str] = Field(default_factory=list, description="Values used for this part.")
    description: str = Field(default="", description="Library description for the part.")
    footprint: str = Field(default="", description="Footprint for the part.")
    datasheet: str = Field(default="", description="Datasheet URL if present.")
    pins: Dict[str, str] = Field(
        default_factory=dict,
        description="Pin number to pin name mapping when available.",
    )
    functional_description: str = Field(
        default="",
        description="Short functional description of the component.",
    )


class ValidationComponentInput(BaseModel):
    components: List[ValidationComponentInfo] = Field(default_factory=list)


def _tokenize_sexp(text: str) -> list[str]:
    tokens: list[str] = []
    idx = 0
    length = len(text)
    while idx < length:
        char = text[idx]
        if char.isspace():
            idx += 1
            continue
        if char in "()":
            tokens.append(char)
            idx += 1
            continue
        if char == '"':
            idx += 1
            buf: list[str] = []
            while idx < length:
                cur = text[idx]
                if cur == "\\" and idx + 1 < length:
                    buf.append(text[idx + 1])
                    idx += 2
                    continue
                if cur == '"':
                    idx += 1
                    break
                buf.append(cur)
                idx += 1
            tokens.append("".join(buf))
            continue
        start = idx
        while idx < length and not text[idx].isspace() and text[idx] not in "()":
            idx += 1
        tokens.append(text[start:idx])
    return tokens


def _parse_sexp(tokens: list[str]) -> list[object]:
    root: list[object] = []
    stack: list[list[object]] = [root]
    for token in tokens:
        if token == "(":
            node: list[object] = []
            stack[-1].append(node)
            stack.append(node)
            continue
        if token == ")":
            if len(stack) == 1:
                raise ValueError("Unexpected closing parenthesis while parsing netlist.")
            stack.pop()
            continue
        stack[-1].append(token)
    if len(stack) != 1:
        raise ValueError("Unclosed parenthesis while parsing netlist.")
    return root


def _find_sexp_section(node: list[object], head: str) -> list[object] | None:
    for child in node:
        if isinstance(child, list):
            if child and child[0] == head:
                return child
            nested = _find_sexp_section(child, head)
            if nested is not None:
                return nested
    return None


def _sexp_find_first(node: list[object], head: str) -> list[object] | None:
    for child in node:
        if isinstance(child, list) and child and child[0] == head:
            return child
    return None


def build_validation_component_input(netlist_content: str) -> ValidationComponentInput:
    if not netlist_content.strip():
        return ValidationComponentInput()

    try:
        tokens = _tokenize_sexp(netlist_content)
        parsed = _parse_sexp(tokens)
    except ValueError:
        return ValidationComponentInput()

    components_section = _find_sexp_section(parsed, "components")
    if not components_section:
        return ValidationComponentInput()

    grouped: dict[tuple[str, str, str, str, str, str], dict[str, list[str]]] = {}
    for item in components_section[1:]:
        if not isinstance(item, list) or not item or item[0] != "comp":
            continue

        ref_node = _sexp_find_first(item, "ref")
        value_node = _sexp_find_first(item, "value")
        description_node = _sexp_find_first(item, "description")
        footprint_node = _sexp_find_first(item, "footprint")
        libsource_node = _sexp_find_first(item, "libsource")

        ref = ref_node[1] if ref_node and len(ref_node) > 1 else ""
        value = value_node[1] if value_node and len(value_node) > 1 else ""
        description = description_node[1] if description_node and len(description_node) > 1 else ""
        footprint = footprint_node[1] if footprint_node and len(footprint_node) > 1 else ""

        lib = ""
        part = ""
        if libsource_node:
            lib_node = _sexp_find_first(libsource_node, "lib")
            part_node = _sexp_find_first(libsource_node, "part")
            lib = lib_node[1] if lib_node and len(lib_node) > 1 else ""
            part = part_node[1] if part_node and len(part_node) > 1 else ""

        fields_node = _sexp_find_first(item, "fields")
        field_map: dict[str, str] = {}
        if fields_node:
            for field in fields_node[1:]:
                if not isinstance(field, list) or not field or field[0] != "field":
                    continue
                field_name = ""
                field_value = ""
                for entry in field[1:]:
                    if isinstance(entry, list) and entry and entry[0] == "name" and len(entry) > 1:
                        field_name = entry[1]
                    elif isinstance(entry, list) and entry and entry[0] == "value" and len(entry) > 1:
                        field_value = entry[1]
                    elif isinstance(entry, str):
                        field_value = entry
                if field_name:
                    field_map[field_name] = field_value

        property_node_values: dict[str, str] = {}
        for prop in item:
            if not isinstance(prop, list) or not prop or prop[0] != "property":
                continue
            prop_name = ""
            prop_value = ""
            for entry in prop[1:]:
                if isinstance(entry, list) and entry and entry[0] == "name" and len(entry) > 1:
                    prop_name = entry[1]
                elif isinstance(entry, list) and entry and entry[0] == "value" and len(entry) > 1:
                    prop_value = entry[1]
            if prop_name:
                property_node_values[prop_name] = prop_value

        datasheet = field_map.get("Datasheet") or property_node_values.get("Datasheet") or ""
        sim_pins = field_map.get("Sim.Pins") or property_node_values.get("Sim.Pins") or ""

        key = (lib, part, description, footprint, datasheet, sim_pins)
        entry = grouped.setdefault(key, {"refs": [], "values": []})
        if ref:
            entry["refs"].append(ref)
        if value:
            entry["values"].append(value)

    components: list[ValidationComponentInfo] = []
    for (lib, part, description, footprint, datasheet, sim_pins), entry in sorted(
        grouped.items(),
        key=lambda item: (item[0][0], item[0][1], item[1]["refs"]),
    ):
        pins: Dict[str, str] = {}
        if sim_pins:
            for pair in sim_pins.split():
                if "=" not in pair:
                    continue
                number, name = pair.split("=", 1)
                if number and name:
                    pins[number] = name

        components.append(
            ValidationComponentInfo(
                library=lib,
                part=part,
                refs=entry["refs"],
                values=entry["values"],
                description=description,
                footprint=footprint,
                datasheet=datasheet,
                pins=pins,
                functional_description="",
            )
        )

    return ValidationComponentInput(components=components)


def _get_validation_component_input(netlist_content: str) -> str:
    payload = build_validation_component_input(netlist_content)
    return json.dumps(payload.model_dump(), indent=2)
