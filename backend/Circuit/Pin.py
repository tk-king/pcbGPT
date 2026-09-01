from __future__ import annotations

from typing import TYPE_CHECKING

from backend.core.exceptions import CircuitException
from backend.Circuit.Net import Net

if TYPE_CHECKING:
    from backend.Circuit.Component import Component
    from backend.Circuit.Circuit import Circuit


class Pin:
    def __init__(self, number: str, name: str | None = None, component: Component | None = None):
        self.number = number
        self.name = name
        self.net: Net | None = None
        self.component: Component | None = component

    def __and__(self, other):
        if isinstance(other, Net):
            return other & self

        from backend.Circuit.FlexiblePin import FlexiblePin

        if isinstance(other, FlexiblePin):
            net = self & other.actual
            if net is None:
                raise CircuitException("FlexiblePin connection did not produce a net.")
            return net & other

        if isinstance(other, Pin):
            if other is self:
                return self.net

            if self.net and other.net:
                if self.net is other.net:
                    return self.net
                self.net & other.net
                return self.net

            if self.net:
                self.net & other
                return self.net

            if other.net:
                other.net & self
                return other.net

            circuit = self._resolve_circuit(other)
            if circuit is None:
                raise CircuitException("Cannot connect pins without an active circuit.")
            net_name = self._implicit_net_name(other)
            new_net = Net(net_name, circuit=circuit)
            new_net & self
            new_net & other
            return new_net

        raise CircuitException("Unsupported operand type(s) for &: 'Pin' and '{}'".format(type(other).__name__))

    def _resolve_circuit(self, peer: Pin | None = None) -> Circuit | None:
        if self.net and self.net.circuit:
            return self.net.circuit
        if self.component and self.component.circuit:
            return self.component.circuit
        if peer:
            if peer.net and peer.net.circuit:
                return peer.net.circuit
            if peer.component and peer.component.circuit:
                return peer.component.circuit
        from backend.Circuit.Circuit import Circuit

        return Circuit.current()

    def _implicit_net_name(self, peer: Pin) -> str:
        parts = [self._pin_label(self), self._pin_label(peer)]
        label = "__".join(part for part in parts if part)
        return label or "NET"

    @staticmethod
    def _pin_label(pin: Pin) -> str:
        identifier = pin.number or ""
        component = pin.component
        if component is None:
            return f"PIN{identifier}"
        if component.ref:
            return f"{component.ref}_{identifier}"
        if component.name:
            return f"{component.name}_{identifier}"
        return f"PIN{identifier}"
