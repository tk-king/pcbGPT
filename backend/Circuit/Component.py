from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set

from backend.core.exceptions import CircuitException, record_circuit_error
from backend.data.Component.KiCadComponent import KiCadComponent
from backend.data.Component.KiCadComponent import get_kicad_component_by_library_and_name
from backend.data.Component.FootprintParser import get_footprint_for_component
from backend.Circuit.Pin import Pin

if TYPE_CHECKING:
    from backend.Circuit.Circuit import Circuit


class _PinMap(dict[str, Pin]):
    """Dictionary-like helper that raises richer errors when a pin is missing."""

    def __init__(self, component: "Component"):
        super().__init__()
        self._component = component

    def __getitem__(self, key: str) -> Pin:
        key = str(key)
        try:
            return super().__getitem__(key)
        except KeyError as exc:  # noqa: PERF203 - richer error for users
            component_label = (
                self._component.ref
                or f"{self._component.library}:{self._component.name}"
            )
            available = sorted(self.keys())
            if len(available) > 20:
                available_preview = ", ".join(available[:20]) + ", ..."
            else:
                available_preview = ", ".join(available)
            raise CircuitException(
                f"Pin '{key}' does not exist on component '{component_label}'. "
                f"Available pins: {available_preview or 'none'}"
            ) from exc


class Component:
    _component_catalog: Dict[str, Set[str]] | None = None
    _VALUE_RULES: Dict[str, tuple[re.Pattern[str], str]] = {
        "resistor": (
            re.compile(r"^\d+(?:\.\d+)?(?:R|k|M)?$"),
            "Resistor values must use ohms with no spaces, for example '330', '4.7k', or '1M'.",
        ),
        "capacitor": (
            re.compile(r"^\d+(?:\.\d+)?(?:pF|nF|uF|mF|F)$"),
            "Capacitor values must use explicit capacitance units with no spaces, for example '100nF', '1uF', or '220uF'. Use ASCII 'u', not 'µ'.",
        ),
        "inductor": (
            re.compile(r"^\d+(?:\.\d+)?(?:nH|uH|mH|H)$"),
            "Inductor values must use explicit inductance units with no spaces, for example '10uH', '1mH', or '22uH'. Use ASCII 'u', not 'µ'.",
        ),
    }

    def __init__(
        self,
        name: str,
        library: str,
        value: Optional[str] = None,
        footprint: Optional[str] = None,
        optional: bool = False,
        compare_value: bool = True,
        value_tolercance: float | int | None = None,
        circuit: "Circuit | None" = None,
        force_footprints: Optional[bool] = None,
    ):
        self.name = name
        self.library = library
        self.value = self._validate_value(name=name, value=value)
        self.footprint = footprint
        self.optional = bool(optional)
        self.compare_value = bool(compare_value)
        self.value_tolercance = (
            float(value_tolercance) if value_tolercance is not None else None
        )
        self.pins: Dict[str, Pin] = _PinMap(self)
        self.ref: Optional[str] = None
        self.circuit: "Circuit | None" = None
        self.functional_block: str | None = None
        self.graphics: List[Dict[str, Any]] = []
        self.pin_geometries: List[Dict[str, Any]] = []

        target_circuit = circuit or self._resolve_current_circuit()
        effective_force_footprints = (
            force_footprints
            if force_footprints is not None
            else (
                target_circuit.force_footprints if target_circuit is not None else True
            )
        )

        try:
            kicad_component: KiCadComponent | None = (
                get_kicad_component_by_library_and_name(library, name)
            )
        except CircuitException as exc:
            if record_circuit_error(exc):
                kicad_component = KiCadComponent(
                    name=name,
                    library=library,
                    description="",
                    pins=[],
                    fp_filters="",
                )
            else:
                raise
        if effective_force_footprints:
            kicad_component = get_footprint_for_component(kicad_component)
        else:
            # Footprint expansion is expensive and unnecessary when footprints are disabled.
            kicad_component.footprints = []
        self.graphics = kicad_component.graphics
        self.pin_geometries = kicad_component.pin_geometries
        available_footprints = [
            f"{fp.library}:{fp.name}" for fp in kicad_component.footprints
        ]
        if not effective_force_footprints:
            # In non-strict mode, explicitly drop footprint assignments.
            # This is useful for importing noisy netlists with invalid/out-of-tree footprints.
            self.footprint = None
            footprint = None

        if (
            effective_force_footprints
            and footprint is None
            and kicad_component.footprints
        ):
            exc = CircuitException(
                f"You need to assign a footprint to this component! "
                f"Component: '{library}:{name}'. "
                f"Found footprints (not all shown): {available_footprints[:50]}"
            )
            if record_circuit_error(exc):
                footprint = None
            else:
                raise exc

        if footprint is not None:
            if effective_force_footprints:
                if ":" not in footprint:
                    exc = CircuitException(
                        f"Footprint '{footprint}' must be provided in '<library>:<name>' "
                        "format to avoid ambiguity. "
                        f"Available options (not all shown): {available_footprints[:50]}"
                    )
                    if record_circuit_error(exc):
                        footprint = None
                    else:
                        raise exc

                matching_footprints = [
                    fp
                    for fp in kicad_component.footprints
                    if f"{fp.library}:{fp.name}" == footprint
                ]
                if not matching_footprints:
                    if not kicad_component.footprints:
                        footprint = None
                    else:
                        exc = CircuitException(
                            f"Footprint '{footprint}' not found for component '{library}:{name}'. "
                            f"Available footprints (not all shown): {available_footprints[:50]}"
                        )
                        if record_circuit_error(exc):
                            footprint = None
                        else:
                            raise exc

            self.footprint = footprint
        else:
            self.footprint = None

        # Copy pins from Kicad component if available
        for pin_identifier in kicad_component.pins:
            if ":" in pin_identifier:
                pin_number, pin_name = pin_identifier.split(":", 1)
            else:
                pin_number, pin_name = pin_identifier, None
            pin_number = pin_number.strip()
            pin_name = pin_name.strip() if pin_name else None

            existing_pin = self.pins.get(pin_number)
            if existing_pin is None:
                self.pins[pin_number] = Pin(pin_number, name=pin_name, component=self)
            else:
                if existing_pin.name is None and pin_name:
                    existing_pin.name = pin_name
                existing_pin.component = self

        if target_circuit is not None:
            target_circuit._register_component_instance(self, preferred_base=name)

    @staticmethod
    def _resolve_current_circuit() -> "Circuit | None":
        from backend.Circuit.Circuit import Circuit

        return Circuit.current()

    @classmethod
    def _validate_value(cls, *, name: str, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        normalized = str(value).strip()
        if not normalized:
            return None

        family = cls._value_family(name)
        if family is None:
            raise CircuitException(
                f"Component '{name}' must not define a value. "
                "Only resistor-, capacitor-, and inductor-style components may use the value field."
            )

        pattern, message = cls._VALUE_RULES[family]
        if not pattern.fullmatch(normalized):
            raise CircuitException(
                f"Invalid value '{normalized}' for component '{name}'. {message}"
            )
        return normalized

    @staticmethod
    def _value_family(name: str) -> str | None:
        normalized = name.strip().upper()
        if normalized in {"R", "R_SMALL", "R_PHOTO", "R_POTENTIOMETER"} or normalized.startswith("R_"):
            return "resistor"
        if normalized in {"C", "C_POLARIZED"} or normalized.startswith("C_"):
            return "capacitor"
        if normalized in {"L", "L_IRON"} or normalized.startswith("L_"):
            return "inductor"
        return None
