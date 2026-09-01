from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional

from backend.core.exceptions import CircuitException

if TYPE_CHECKING:
    from backend.Circuit.Circuit import Circuit
    from backend.Circuit.Pin import Pin


class Net:
    def __init__(self, name: str, circuit: "Circuit | None" = None):
        self._name = name
        self._pins: List["Pin"] = []
        self.net: Optional["Net"] = None
        self._ref: Optional[str] = None
        self._circuit: "Circuit | None" = None
        self._canonical_parent: Optional["Net"] = None

        target_circuit = circuit or self._resolve_current_circuit()
        if target_circuit is not None:
            target_circuit._register_net_instance(self, preferred_base=name)

    def _canonical(self) -> "Net":
        parent = self._canonical_parent
        if parent is None:
            return self
        root = parent._canonical()
        if root is not parent:
            self._canonical_parent = root
        return root

    @property
    def pins(self) -> List["Pin"]:
        return self._canonical()._pins

    @pins.setter
    def pins(self, value: List["Pin"]) -> None:
        self._canonical()._pins = value

    @property
    def name(self) -> str:
        return self._canonical()._name

    @name.setter
    def name(self, value: str) -> None:
        self._canonical()._name = value

    @property
    def ref(self) -> Optional[str]:
        return self._canonical()._ref

    @ref.setter
    def ref(self, value: Optional[str]) -> None:
        self._canonical()._ref = value

    @property
    def circuit(self) -> "Circuit | None":
        return self._canonical()._circuit

    @circuit.setter
    def circuit(self, value: "Circuit | None") -> None:
        self._canonical()._circuit = value

    def __and__(self, other):
        from backend.Circuit.Pin import Pin
        from backend.Circuit.FlexiblePin import FlexiblePin

        if isinstance(other, Net):
            target = self._canonical()
            source = other._canonical()
            if target is source:
                return target
            target, source = target._merge_order(source)
            for pin in list(source._pins):
                if pin not in target.pins:
                    target.pins.append(pin)
                pin.net = target
            source._pins = []
            source._detach_from_circuit_registry()
            source._canonical_parent = target
            return target

        if isinstance(other, Pin):
            target = self._canonical()
            other_net = other.net._canonical() if other.net is not None else None
            if other_net is not None and other_net is not target:
                target = target & other_net
            if other.net is not None and other in other.net.pins:
                other.net.pins.remove(other)
            other.net = target
            if other not in target.pins:
                target.pins.append(other)
            return target

        if isinstance(other, FlexiblePin):
            target = self._canonical()
            target & other.actual
            if target.circuit is None:
                raise CircuitException("FlexiblePin requires a net registered to a circuit.")
            target.circuit.register_flexible_pin(target, other.actual, other.alternatives)
            return target

        raise CircuitException("Unsupported operand type(s) for &: 'Net' and '{}'".format(type(other).__name__))

    @staticmethod
    def _resolve_current_circuit() -> "Circuit | None":
        from backend.Circuit.Circuit import Circuit

        return Circuit.current()

    def _merge_order(self, other: "Net") -> tuple["Net", "Net"]:
        left = self._canonical()
        right = other._canonical()
        self_rank = left._merge_priority()
        other_rank = right._merge_priority()
        if self_rank < other_rank:
            return left, right
        if other_rank < self_rank:
            return right, left
        self_key = left.ref or left.name
        other_key = right.ref or right.name
        if self_key <= other_key:
            return left, right
        return right, left

    def _merge_priority(self) -> tuple[int, int]:
        # Prefer explicit named rails/nets over auto-generated implicit nets.
        canonical = self._canonical()
        is_implicit = int(canonical._is_implicit_net_name())
        # Prefer already-populated nets when both have the same naming quality.
        return (is_implicit, -len(canonical._pins))

    def _is_implicit_net_name(self) -> bool:
        label = (self.name or "").strip()
        if not label:
            return True
        return "__" in label or label == "NET"

    def _detach_from_circuit_registry(self) -> None:
        circuit = self._circuit
        ref = self._ref
        if circuit is None or not ref:
            return
        if getattr(circuit, "nets", {}).get(ref) is self:
            circuit.nets.pop(ref, None)
        self._circuit = None
