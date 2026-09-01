from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Set

from backend.core.exceptions import CircuitException
from backend.Circuit.ImporterExporter.ImporterExporter import ImporterExporter


class NetlistImporterExporter(ImporterExporter):
    from backend.Circuit import Circuit

    def export_circuit(self, circuit: "Circuit") -> Any:
        from datetime import datetime

        from backend.Circuit.Circuit import Circuit
        from backend.data.Component.KiCadComponent import get_kicad_component_by_library_and_name

        if not isinstance(circuit, Circuit):
            raise CircuitException("export_circuit expects a Circuit instance.")

        if not circuit.components:
            raise CircuitException("Circuit must contain at least one component to export a netlist.")

        def q(value: Optional[str]) -> str:
            safe = "" if value is None else str(value)
            return safe.replace('"', r"\"")

        def indent(level: int, text: str) -> str:
            return f'{"  " * level}{text}'

        # Prepare component ordering for deterministic output.
        ordered_components = sorted(circuit.components.items(), key=lambda item: item[0])

        # Collect metadata for libparts, libraries, and component descriptors.
        libparts: Dict[tuple[str, str], Dict[str, Any]] = {}
        library_names: Set[str] = set()
        component_descriptors: list[tuple[str, "Component", str, str, Optional[Any]]] = []
        component_metadata: Dict[str, Dict[str, Any]] = {}

        for comp_ref, component in ordered_components:
            library = component.library or "Device"
            part_name = component.name or library
            library_names.add(library)

            try:
                kicad_component = get_kicad_component_by_library_and_name(library, part_name)
            except CircuitException:
                kicad_component = None

            component_descriptors.append((comp_ref, component, library, part_name, kicad_component))

            lib_entry = libparts.setdefault(
                (library, part_name),
                {
                    "description": None,
                    "datasheet": None,
                    "docs": "~",
                    "fp_filters": set(),
                    "footprints": set(),
                    "pins": {},
                    "reference": None,
                    "keywords": None,
                    "sim_pins": None,
                },
            )

            component_metadata[comp_ref] = {
                "library": library,
                "part_name": part_name,
                "kicad_component": kicad_component,
                "lib_entry": lib_entry,
            }

            if kicad_component:
                if kicad_component.description and not lib_entry["description"]:
                    lib_entry["description"] = kicad_component.description
                if kicad_component.datasheet and kicad_component.datasheet != "~":
                    lib_entry["datasheet"] = kicad_component.datasheet
                if kicad_component.keywords and not lib_entry["keywords"]:
                    lib_entry["keywords"] = kicad_component.keywords
                if kicad_component.fp_filters:
                    lib_entry["fp_filters"].update(filter(None, kicad_component.fp_filters.split()))
                for footprint in getattr(kicad_component, "footprints", []) or []:
                    fp_name = getattr(footprint, "name", "")
                    fp_library = getattr(footprint, "library", "")
                    if fp_library and fp_name:
                        fp_repr = f"{fp_library}:{fp_name}"
                    else:
                        fp_repr = fp_name or fp_library
                    if fp_repr:
                        lib_entry["footprints"].add(fp_repr)
                if kicad_component.pins:
                    pin_mappings: list[str] = []
                    for pin_spec in kicad_component.pins:
                        num, name = self._parse_pin_spec(pin_spec)
                        pin_entry = lib_entry["pins"].setdefault(num, {"name": name or "", "type": "passive"})
                        if name and not pin_entry["name"]:
                            pin_entry["name"] = name
                        if name:
                            pin_mappings.append(f"{num}={name}")
                    if pin_mappings and not lib_entry["sim_pins"]:
                        lib_entry["sim_pins"] = " ".join(pin_mappings)

            if component.footprint:
                lib_entry["footprints"].add(component.footprint)

            if component.ref and not lib_entry["reference"]:
                ref_prefix = "".join(ch for ch in str(component.ref) if ch.isalpha())
                lib_entry["reference"] = ref_prefix

            for pin in component.pins.values():
                pin_entry = lib_entry["pins"].setdefault(pin.number, {"name": pin.name or "", "type": "passive"})
                if pin.name and not pin_entry["name"]:
                    pin_entry["name"] = pin.name

        for info in libparts.values():
            if not info.get("sim_pins"):
                derived = [
                    f"{num}={pin_info['name']}"
                    for num, pin_info in sorted(info["pins"].items())
                    if pin_info.get("name")
                ]
                if derived:
                    info["sim_pins"] = " ".join(derived)

        libraries = sorted(library_names)

        # Prepare nets with deterministic ordering.
        ordered_nets = sorted(circuit.nets.values(), key=lambda net: (net.name or "", getattr(net, "ref", "")))

        timestamp = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

        lines: list[str] = []
        lines.append('(export (version "E")')
        lines.append(indent(1, "(design"))
        lines.append(indent(2, '(source "")'))
        lines.append(indent(2, f'(date "{timestamp}")'))
        lines.append(indent(2, '(tool "pcbgpt-netlist-collection")'))
        lines.append(indent(2, '(sheet (number "1") (name "/") (tstamps "/")'))
        lines.append(indent(3, "(title_block"))
        lines.append(indent(4, "(title)"))
        lines.append(indent(4, "(company)"))
        lines.append(indent(4, "(rev)"))
        lines.append(indent(4, f'(date "{timestamp[:10]}")'))
        lines.append(indent(4, '(source "")'))
        for idx in range(1, 5):
            lines.append(indent(4, f'(comment (number "{idx}") (value ""))'))
        lines.append(indent(3, ")"))
        lines.append(indent(2, ")"))
        lines.append(indent(1, ")"))

        lines.append(indent(1, "(components"))
        for comp_ref, component, library, part_name, kicad_component in component_descriptors:
            lib_entry = component_metadata[comp_ref]["lib_entry"]
            description = lib_entry.get("description") or component.name or ""
            footprint = component.footprint or ""
            datasheet_value = lib_entry.get("datasheet")
            if datasheet_value == "~":
                datasheet_value = None
            keywords = lib_entry.get("keywords")
            fp_filter_values = sorted(lib_entry.get("fp_filters", set()))
            sim_pins_value = lib_entry.get("sim_pins")

            lines.append(indent(2, f'(comp (ref "{q(comp_ref)}")'))
            value = component.value if component.value is not None else component.name
            lines.append(indent(3, f'(value "{q(value)}")'))
            lines.append(indent(3, f'(description "{q(description)}")'))
            if footprint:
                lines.append(indent(3, f'(footprint "{q(footprint)}")'))

            lines.append(indent(3, "(fields"))
            if sim_pins_value:
                lines.append(indent(4, f'(field (name "Sim.Pins") "{q(sim_pins_value)}")'))
            lines.append(indent(4, f'(field (name "Footprint") "{q(footprint)}")'))
            lines.append(indent(4, f'(field (name "Datasheet") "{q(datasheet_value or "")}")'))
            lines.append(indent(4, f'(field (name "Description") "{q(description)}")'))
            lines.append(indent(3, ")"))

            libsource_parts = [f'(lib "{q(library)}")', f'(part "{q(part_name)}")']
            if description:
                libsource_parts.append(f'(description "{q(description)}")')
            lines.append(indent(3, "(libsource " + " ".join(libsource_parts) + ")"))

            if footprint:
                lines.append(indent(3, f'(property (name "Footprint") (value "{q(footprint)}"))'))

            if sim_pins_value:
                lines.append(indent(3, f'(property (name "Sim.Pins") (value "{q(sim_pins_value)}"))'))
            lines.append(indent(3, '(property (name "Sheetname") (value "Root"))'))
            lines.append(indent(3, '(property (name "Sheetfile") (value ""))'))
            if keywords:
                lines.append(indent(3, f'(property (name "ki_keywords") (value "{q(keywords)}"))'))
            if fp_filter_values:
                lines.append(
                    indent(
                        3,
                        f'(property (name "ki_fp_filters") (value "{q(" ".join(fp_filter_values))}"))',
                    )
                )
            lines.append(indent(3, '(sheetpath (names "/") (tstamps "/"))'))
            lines.append(indent(3, f'(tstamps "{q(getattr(component, "ref", comp_ref))}")'))
            lines.append(indent(2, ")"))
        lines.append(indent(1, ")"))

        lines.append(indent(1, "(libparts"))
        for (library, part_name), info in sorted(libparts.items()):
            lines.append(indent(2, f'(libpart (lib "{q(library)}") (part "{q(part_name)}")'))
            description = info.get("description") or part_name
            lines.append(indent(3, f'(description "{q(description)}")'))
            docs_value = info.get("docs") or "~"
            lines.append(indent(3, f'(docs "{q(docs_value)}")'))
            lines.append(indent(3, "(footprints"))
            footprint_entries: list[str] = []
            if info.get("fp_filters"):
                footprint_entries.extend(sorted(info["fp_filters"]))
            elif info.get("footprints"):
                footprint_entries.extend(sorted(info["footprints"]))
            for fp in footprint_entries:
                lines.append(indent(4, f'(fp "{q(fp)}")'))
            lines.append(indent(3, ")"))
            lines.append(indent(3, "(fields"))
            ref_value = info.get("reference") or ""
            lines.append(indent(4, f'(field (name "Reference") "{q(ref_value)}")'))
            lines.append(indent(4, f'(field (name "Value") "{q(part_name)}")'))
            lines.append(indent(4, '(field (name "Footprint"))'))
            datasheet_entry = info.get("datasheet") or "~"
            lines.append(indent(4, f'(field (name "Datasheet") "{q(datasheet_entry)}")'))
            lines.append(indent(4, f'(field (name "Description") "{q(description)}")'))
            if info.get("sim_pins"):
                lines.append(indent(4, f'(field (name "Sim.Pins") "{q(info["sim_pins"])}")'))
            lines.append(indent(3, ")"))
            lines.append(indent(3, "(pins"))
            def _pin_sort_key(raw) -> tuple[int, object, str]:
                text = str(raw)
                if text.isdigit():
                    return (0, int(text), text)
                return (1, text, text)

            for pin_number in sorted(info["pins"], key=_pin_sort_key):
                pin_info = info["pins"][pin_number]
                pin_name = pin_info.get("name", "")
                pin_type = pin_info.get("type", "passive")
                lines.append(
                    indent(
                        4,
                        f'(pin (num "{q(pin_number)}") (name "{q(pin_name)}") (type "{q(pin_type)}"))',
                    )
                )
            lines.append(indent(3, ")"))
            lines.append(indent(2, ")"))
        lines.append(indent(1, ")"))

        lines.append(indent(1, "(libraries"))
        for library in libraries:
            lines.append(indent(2, f'(library (logical "{q(library)}") (uri ""))'))
        lines.append(indent(1, ")"))

        lines.append(indent(1, "(nets"))
        for code, net in enumerate(ordered_nets, start=1):
            net_name = net.name or f"Net-{code}"
            net_code = code
            lines.append(indent(2, f'(net (code "{net_code}") (name "{q(net_name)}") (class "Default")'))

            pin_nodes = []
            for comp_ref, component, library, part_name, _ in component_descriptors:
                lib_entry = component_metadata[comp_ref]["lib_entry"]
                for pin_number, pin in component.pins.items():
                    if pin.net is net:
                        pin_nodes.append((comp_ref, pin.number, pin, lib_entry))

            pin_nodes.sort(key=lambda item: (item[0], item[1]))
            for comp_ref, pin_number, pin, lib_entry in pin_nodes:
                pin_info = lib_entry["pins"].get(pin_number, {"type": "passive"})
                pin_type = pin_info.get("type", "passive")
                pin_function = pin.name or pin_info.get("name", "")
                node_line = f'(node (ref "{q(comp_ref)}") (pin "{q(pin_number)}")'
                if pin_function:
                    node_line += f' (pinfunction "{q(pin_function)}")'
                node_line += f' (pintype "{q(pin_type)}"))'
                lines.append(indent(3, node_line))
            lines.append(indent(2, ")"))
        lines.append(indent(1, ")"))
        lines.append(")")

        return "\n".join(lines)

    def import_circuit(self, netlist_data: str | Path, force_footprints: bool = True) -> "Circuit":
        """Parse a KiCad netlist string (or file path) into a Circuit instance."""
        from backend.Circuit.Circuit import Circuit
        from backend.Circuit.Component import Component
        from backend.Circuit.Net import Net
        from backend.Circuit.Pin import Pin

        try:
            from kinparse import parse_netlist
        except ImportError as exc:  # pragma: no cover - defensive
            raise CircuitException("kinparse is required to import KiCad netlists.") from exc

        if netlist_data is None:
            raise CircuitException("No netlist data supplied.")

        netlist_text = self._load_netlist_source(netlist_data)
        try:
            parsed_netlist = parse_netlist(netlist_text)
        except Exception as exc:  # pragma: no cover - kinparse provides rich exceptions
            raise CircuitException(f"Failed to parse KiCad netlist: {exc}") from exc

        parts = getattr(parsed_netlist, "parts", None)
        nets = getattr(parsed_netlist, "nets", None)
        if parts is None or nets is None:
            raise CircuitException("Parsed netlist is missing parts or nets information.")

        circuit = Circuit(force_footprints=force_footprints)
        component_lookup: Dict[str, Component] = {}

        for part in parts:
            component_ref = getattr(part, "ref", None)
            if not component_ref or not isinstance(component_ref, str):
                raise CircuitException("Encountered component without a valid reference designator.")

            library = self._extract_attribute(part, ("lib", "library"))
            name = self._extract_attribute(part, ("name", "part"))
            if library is None or name is None:
                libsource = getattr(part, "libsource", None)
                if libsource is not None:
                    library = library or getattr(libsource, "lib", None)
                    name = name or getattr(libsource, "part", None)
            if library is None or name is None:
                raise CircuitException(f"Component '{component_ref}' is missing library/name metadata.")

            value = self._extract_attribute(part, ("value",), default=None)
            footprint = self._extract_attribute(part, ("footprint", "fp"), default=None)

            component_value = value if value else None
            try:
                component = Component(
                    name=name,
                    library=library,
                    value=component_value,
                    footprint=footprint if footprint else None,
                    force_footprints=force_footprints,
                )
            except CircuitException as exc:
                # KiCad netlists usually include a "value" for every symbol, even when
                # the local circuit DSL intentionally forbids arbitrary values on that
                # component family. Retry without the value so schematic imports can
                # reconstruct the connectivity and symbol choice.
                if component_value is None:
                    raise
                component = Component(
                    name=name,
                    library=library,
                    value=None,
                    footprint=footprint if footprint else None,
                    force_footprints=force_footprints,
                )
            # Non-strict component construction skips footprint discovery and drops
            # assignments. The footprint parsed from the KiCad netlist is still
            # authoritative import data, so preserve it without validating it
            # against the locally installed footprint libraries.
            if not force_footprints and footprint:
                component.footprint = str(footprint)
            circuit._register_component_instance(component, preferred_base=name, ref=component_ref)
            component_lookup[component_ref] = component

            for pin in getattr(part, "pins", []) or []:
                pin_num = str(getattr(pin, "num", "") or getattr(pin, "pin", "")).strip()
                pin_name = getattr(pin, "name", None)
                if not pin_num:
                    continue
                self._get_or_create_pin(component, pin_num, pin_name)

        net_lookup: Dict[str, Net] = {}
        for net in nets:
            net_code = str(getattr(net, "code", "")).strip()
            net_name = self._extract_attribute(net, ("name",), default=None)
            if not net_name:
                net_name = f"N{net_code}" if net_code else "__unnamed_net__"

            net_ref = net_code if net_code else net_name
            circuit_net = Net(net_name)
            circuit._register_net_instance(circuit_net, preferred_base=net_name, ref=net_ref)
            net_lookup[net_ref] = circuit_net
            if net_name and net_name != net_ref:
                net_lookup[net_name] = circuit_net

        for net in nets:
            net_code = str(getattr(net, "code", "")).strip()
            net_ref = net_code if net_code else self._extract_attribute(net, ("name",), default="__unnamed_net__")
            circuit_net = net_lookup.get(net_ref)
            if circuit_net is None:
                continue

            kin_pins: Iterable = getattr(net, "pins", getattr(net, "nodes", [])) or []
            for kin_pin in kin_pins:
                comp_ref = getattr(kin_pin, "ref", None)
                pin_number = str(getattr(kin_pin, "num", "") or getattr(kin_pin, "pin", "")).strip()
                pin_function = getattr(kin_pin, "pinfunction", None)
                if not comp_ref or not pin_number:
                    continue

                component = component_lookup.get(comp_ref)
                if component is None:
                    raise CircuitException(f"Net references unknown component '{comp_ref}'.")

                pin_obj = self._get_or_create_pin(component, pin_number, pin_function)
                if pin_obj.net is not None and pin_obj.net is not circuit_net:
                    if pin_obj in pin_obj.net.pins:
                        pin_obj.net.pins.remove(pin_obj)

                if pin_obj not in circuit_net.pins:
                    circuit_net.pins.append(pin_obj)
                pin_obj.net = circuit_net

        return circuit

    @staticmethod
    def _get_or_create_pin(component: "Component", pin_number: str, pin_name: Optional[str] = None) -> Pin:
        from backend.Circuit.Pin import Pin

        normalized = pin_number.strip()
        if not normalized:
            raise CircuitException("Pin number cannot be empty.")

        pin_obj = component.pins.get(normalized)
        if pin_obj is None:
            for key, existing_pin in list(component.pins.items()):
                candidate_number = getattr(existing_pin, "number", key)
                if candidate_number == normalized:
                    pin_obj = existing_pin
                    if key != normalized:
                        component.pins[normalized] = component.pins.pop(key)
                    break

        if pin_obj is None:
            pin_obj = Pin(normalized, name=pin_name, component=component)
            component.pins[normalized] = pin_obj
        else:
            if getattr(pin_obj, "number", None) != normalized:
                pin_obj.number = normalized
            if pin_name and not getattr(pin_obj, "name", None):
                pin_obj.name = pin_name
            if getattr(pin_obj, "component", None) is None:
                pin_obj.component = component

        return pin_obj

    @staticmethod
    def _parse_pin_spec(pin_spec: Any) -> tuple[str, Optional[str]]:
        if pin_spec is None:
            return "", None
        text = str(pin_spec)
        if ":" in text:
            number, name = text.split(":", 1)
            return number.strip(), name.strip() or None
        return text.strip(), None

    @staticmethod
    def _load_netlist_source(source: str | Path) -> str:
        if isinstance(source, Path):
            if not source.exists():
                raise CircuitException(f"Netlist file '{source}' does not exist.")
            return source.read_text(encoding="utf-8")

        if isinstance(source, str):
            stripped = source.strip()
            if "\n" in source or stripped.startswith("("):
                return source
            path_candidate = Path(source)
            try:
                if path_candidate.exists():
                    return path_candidate.read_text(encoding="utf-8")
            except OSError:
                return source
            return source

        raise CircuitException("Netlist source must be a path or string of netlist contents.")

    @staticmethod
    def _extract_attribute(obj: object, names: Iterable[str], default: Optional[str] = None) -> Optional[str]:
        for name in names:
            value = getattr(obj, name, None)
            if value:
                return value
        return default
