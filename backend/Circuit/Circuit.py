from __future__ import annotations

from collections.abc import Iterable, Sequence
from contextlib import contextmanager
from functools import wraps
import json
import os
from pathlib import Path
import subprocess
import tempfile
from typing import Any, Callable, Dict, Generator, List, Optional, Tuple, TypeVar

from backend.Circuit.Component import Component
from backend.Circuit.Net import Net
from backend.core.exceptions import CircuitException

CircuitCallable = TypeVar("CircuitCallable", bound=Callable[..., Any])


class SubCircuitResult(Sequence):
    """Wrapper that behaves like a tuple while exposing the generated subcircuit."""

    def __init__(self, circuit: "Circuit", items: Any):
        if isinstance(items, SubCircuitResult):
            self._items = list(items._items)
        elif isinstance(items, Iterable) and not isinstance(items, (Component, Net, str, bytes)):
            self._items = list(items)
        else:
            self._items = [items]
        self.circuit = circuit

    def __iter__(self) -> Generator[Any, None, None]:
        yield from self._items

    def __len__(self) -> int:
        return len(self._items)

    def __getitem__(self, index: int) -> Any:
        return self._items[index]



class Circuit:
    _context_stack: List["Circuit"] = []

    def __init__(self, ref_counter: Dict[str, int] | None = None, force_footprints: bool = True):
        self.components: Dict[str, Component] = {}
        self.nets: Dict[str, Net] = {}
        self._ref_counter: Dict[str, int] = ref_counter if ref_counter is not None else {}
        self.force_footprints: bool = force_footprints
        self.functional_blocks: List[Dict[str, str]] = []
        self._functional_block_stack: List[str] = []
        self._flexible_pin_bindings: Dict[int, Dict[tuple[str, str], frozenset[tuple[str, str]]]] = {}

    # ------------------------------------------------------------------
    # Context manager helpers
    # ------------------------------------------------------------------
    def __enter__(self) -> "Circuit":
        self._context_stack.append(self)
        return self

    def __exit__(self, _exc_type, _exc_val, _exc_tb) -> None:
        if self._context_stack and self._context_stack[-1] is self:
            self._context_stack.pop()

    @classmethod
    def current(cls) -> Optional["Circuit"]:
        return cls._context_stack[-1] if cls._context_stack else None

    @contextmanager
    def functional_block(
        self, block_id: str, label: str | None = None
    ) -> Generator[str, None, None]:
        """Group components created inside the context under a functional block."""
        normalized_id = str(block_id).strip()
        if not normalized_id:
            raise CircuitException("Functional block id must not be empty.")
        normalized_label = label.strip() if label is not None else self._block_label(normalized_id)
        self._register_functional_block(normalized_id, normalized_label)
        self._functional_block_stack.append(normalized_id)
        try:
            yield normalized_id
        finally:
            self._functional_block_stack.pop()

    def _register_functional_block(self, block_id: str, label: str) -> None:
        for block in self.functional_blocks:
            if block["id"] == block_id:
                if not block.get("label") and label:
                    block["label"] = label
                return
        self.functional_blocks.append({"id": block_id, "label": label})

    @staticmethod
    def _block_label(block_id: str) -> str:
        return block_id.replace("_", " ").strip().title()

    # ------------------------------------------------------------------
    # Component / net registration
    # ------------------------------------------------------------------
    def add_component(
        self,
        name: str,
        library: str,
        value: str | None = None,
        footprint: str | None = None,
        optional: bool = False,
        compare_value: bool = True,
        value_tolercance: float | int | None = None,
    ) -> Component:
        component = Component(
            name=name,
            library=library,
            value=value,
            footprint=footprint,
            optional=optional,
            compare_value=compare_value,
            value_tolercance=value_tolercance,
            circuit=self,
            force_footprints=self.force_footprints,
        )
        if component.circuit is None:
            self._register_component_instance(component, preferred_base=name)
        elif component.circuit is not self:
            raise ValueError("Component already registered with a different circuit.")
        return component

    def add_net(self, name: str) -> Net:
        net = Net(name, circuit=self)
        if net.circuit is None:
            self._register_net_instance(net, preferred_base=name)
        elif net.circuit is not self:
            raise ValueError("Net already registered with a different circuit.")
        return net

    @staticmethod
    def _resolve_kicad_cli() -> str:
        cli = os.getenv("KICAD_CLI", "/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli")
        if Path(cli).exists():
            return cli
        return "kicad-cli"

    @staticmethod
    def _decode_json_prefix(raw_text: str) -> Dict[str, Any] | None:
        text = raw_text.lstrip()
        if not text:
            return None
        try:
            parsed, _ = json.JSONDecoder().raw_decode(text)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None

    def erc(
        self,
        output_dir: Path | str | None = None,
        project_name: str = "circuit",
        timeout: int = 60,
        raise_on_error: bool = False,
    ) -> Dict[str, Any]:
        """
        Export this Circuit as a KiCad project and run schematic ERC via kicad-cli.

        Returns a dictionary with command details and ERC output.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            from backend.Circuit.ImporterExporter.KiCADProject import generate_kicad_project

            base_output = Path(output_dir) if output_dir is not None else Path(temp_dir)
            base_output.mkdir(parents=True, exist_ok=True)

            project_dir = generate_kicad_project([self], base_output, project_name)
            sch_path = project_dir / f"{project_name}.kicad_sch"

            if not sch_path.exists():
                raise CircuitException(f"Expected KiCad schematic was not generated: {sch_path}")

            kicad_cli = self._resolve_kicad_cli()
            command = [
                kicad_cli,
                "sch",
                "erc",
                "--exit-code-violations",
                "--format",
                "json",
                "-o",
                "/dev/stdout",
                str(sch_path),
            ]

            try:
                result = subprocess.run(
                    command,
                    check=False,
                    timeout=timeout,
                    capture_output=True,
                    text=True,
                )
            except FileNotFoundError as exc:
                raise CircuitException(
                    "KiCad CLI not found. Set KICAD_CLI or install kicad-cli in PATH."
                ) from exc
            except subprocess.TimeoutExpired as exc:
                raise CircuitException(f"KiCad ERC timed out after {timeout}s.") from exc

            raw_stdout = (result.stdout or "").strip()
            raw_stderr = (result.stderr or "").strip()
            erc_json = self._decode_json_prefix(raw_stdout)
            findings: List[Dict[str, Any]] = []
            errors_count = 0
            warnings_count = 0
            if erc_json is not None:
                for sheet in erc_json.get("sheets", []):
                    sheet_path = sheet.get("path", "/")
                    for violation in sheet.get("violations", []):
                        severity = violation.get("severity", "unknown")
                        if severity == "error":
                            errors_count += 1
                        elif severity == "warning":
                            warnings_count += 1
                        findings.append(
                            {
                                "sheet": sheet_path,
                                "type": violation.get("type"),
                                "severity": severity,
                                "description": violation.get("description"),
                                "items": violation.get("items", []),
                            }
                        )
            erc_result = {
                "passed": result.returncode == 0,
                "returncode": result.returncode,
                "stdout": raw_stdout,
                "stderr": raw_stderr,
                "report": raw_stdout,
                "erc_json": erc_json,
                "findings": findings,
                "errors": errors_count,
                "warnings": warnings_count,
                "report_path": None,
                "project_dir": str(project_dir),
                "schematic_path": str(sch_path),
                "command": command,
            }
            if raise_on_error and result.returncode != 0:
                details = erc_result["stderr"] or erc_result["stdout"] or "ERC failed."
                raise CircuitException(details)
            return erc_result

    def _register_component_instance(self, component: Component, preferred_base: str | None = None, ref: str | None = None) -> str:
        base = preferred_base or component.name
        if ref is None:
            ref = self._generate_reference(base)
        else:
            base = ref.split("_", 1)[0]
            self._update_ref_counter(base, ref)

        if getattr(component, "ref", None) and component.ref != ref:
            raise ValueError(f"Component already registered with ref '{component.ref}'.")

        component.ref = ref
        component.circuit = self
        if self._functional_block_stack and not component.functional_block:
            component.functional_block = self._functional_block_stack[-1]
        self.components[ref] = component
        return ref

    def _register_net_instance(self, net: Net, preferred_base: str | None = None, ref: str | None = None) -> str:
        base = preferred_base or net.name
        if ref is None:
            ref = self._generate_reference(base)
        else:
            base = ref.split("_", 1)[0]
            self._update_ref_counter(base, ref)

        if getattr(net, "ref", None) and net.ref != ref:
            raise ValueError(f"Net already registered with ref '{net.ref}'.")

        net.ref = ref
        net.circuit = self
        self.nets[ref] = net
        return ref

    def _generate_reference(self, base: str) -> str:
        current = self._ref_counter.get(base, 0) + 1
        self._ref_counter[base] = current
        return f"{base}_{current}"

    def _update_ref_counter(self, base: str, ref: str) -> None:
        try:
            _, counter_str = ref.rsplit("_", 1)
            counter = int(counter_str)
        except (ValueError, AttributeError):
            return
        previous = self._ref_counter.get(base, 0)
        if counter > previous:
            self._ref_counter[base] = counter

    def register_flexible_pin(self, net: Net, actual: "Pin", alternatives: Iterable["Pin"]) -> None:
        from backend.Circuit.Pin import Pin

        if actual.component is None or not actual.component.ref:
            raise CircuitException("FlexiblePin actual pin must belong to a registered component.")
        allowed: set[tuple[str, str]] = {(actual.component.ref, str(actual.number))}
        actual_component = actual.component
        for pin in alternatives:
            if not isinstance(pin, Pin):
                raise CircuitException("FlexiblePin alternatives must be Pin instances.")
            if pin.component is None or not pin.component.ref:
                raise CircuitException("FlexiblePin alternative pin must belong to a registered component.")
            if pin.component is not actual_component:
                raise CircuitException("FlexiblePin alternatives must belong to the same component as the actual pin.")
            allowed.add((pin.component.ref, str(pin.number)))
        self._flexible_pin_bindings.setdefault(id(net), {})[(actual.component.ref, str(actual.number))] = frozenset(allowed)


    def __repr__(self):
        return (
            f"Circuit(components={list(self.components.keys())}, "
            f"nets={list(self.nets.keys())}, force_footprints={self.force_footprints})"
        )



def circuit(func: CircuitCallable | None = None, *, force_footprints: bool = True) -> CircuitCallable:
    """Decorator that captures component/net construction inside a transient Circuit."""

    def decorator(fn: CircuitCallable) -> CircuitCallable:
        @wraps(fn)
        def wrapper(*args, **kwargs):
            sub_circuit = Circuit(force_footprints=force_footprints)
            with sub_circuit:
                result = fn(*args, **kwargs)
            return SubCircuitResult(sub_circuit, result)

        wrapper.__wrapped__ = fn  # type: ignore[attr-defined]
        wrapper._is_circuit_builder = True  # type: ignore[attr-defined]
        return wrapper  # type: ignore[return-value]

    if func is not None:
        return decorator(func)
    return decorator
