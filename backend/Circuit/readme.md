Circuit Framework
=================

This package provides a small domain model for describing electrical circuits in Python. The core ideas are:

- **Circuit** – a container that owns every `Component` and `Net` you create while it is active. It works as a context manager so you can build circuits declaratively.
- **Component** – wraps schematic parts such as resistors or ICs. Pins are cloned from the KiCad component library data so that pin objects are immediately available.
- **Net** – represents an electrical connection. Nets keep track of all pins that are tied together and can be merged using the bitwise-AND operator (`&`).
- **SubCircuitResult** – returned by the `@circuit` decorator, bundling both the return value of the decorated function and the generated `Circuit` instance.

Quick start
-----------

```python
from backend.Circuit import Circuit

# Build a circuit explicitly
main = Circuit()
with main:
    r1 = main.add_component(name="R", library="Device", value="10k")
    r2 = main.add_component(name="R", library="Device", value="5k")
    vcc = main.add_net("VCC")
    gnd = main.add_net("GND")

# Access pinned metadata
print(r1.ref, r1.pins.keys())
print(vcc.ref, [pin.number for pin in vcc.pins])
```

When you call `add_component` or `add_net`, the circuit assigns a unique reference designator (e.g., `R_1`, `NET_1`) and keeps the objects in `Circuit.components` and `Circuit.nets`. Creating components or nets directly inside a `with Circuit():` block works as well; the constructors detect the active circuit, so manual registration is unnecessary.

You can also omit the `value` argument when creating the component—this is the case when a component does not need a value. For example, resistors need values but operational amplifiers do not:

```python
from backend.Circuit.Component import Component

u1 = Component(name="AD797", library="Amplifier_Operational")
```

Value field rules
-----------------

Use `value=` only for parts whose schematic symbol represents an electrical value-bearing passive, such as resistors, capacitors, and inductors. Do not pass descriptive values to ICs, LEDs, connectors, bridges, sensors, or other functional parts.

Formatting rules:

- Resistors: express resistance in ohms using plain numbers or with extensions (Only "k" or "M" allowed). E.g. `330`, `4.7k`, or `1M`.
- Capacitors: express capacitance with explicit units using the extensions "pF", "nF", "uF". E.g. `22pF`, `100nF`, `1uF`, or `220uF`.
- Inductors: express inductance with explicit units using the extensions "nH", "uH" or "mH". E.g. `600nH`, `10uH`, `1mH`, or `22uH`.
- Do not include spaces.
- Only use the listed unit specifiers.
- Use ASCII `u` instead of the micro sign `µ`.
- Use ASCII only in values. Do not use Unicode symbols such as `Ω`.
- Prefer canonical value strings so equivalent values are written consistently.
- For capacitors, prefer `100nF` over equivalent forms such as `0.1uF`.
- For resistors below 1 kOhm, prefer plain ohm numbers such as `220` or `330`.
- Ferrite beads should only use a `value` when the impedance value is known and relevant to the design.
- Do not use descriptive strings like `Red`, `LM555xM`, or `D_Bridge_-A+A` as component values.

If a part does not have a passive electrical value, omit `value` entirely.

Design rules
----------------
- When connecting a resistor and an LED in series, always connect the cathode to the resistor. For `Device:LED`, cathode is pin 1 and anode is pin 2.
- When driving an LED from an MCU GPIO, use the GPIO as a low-side sink unless the prompt explicitly requires otherwise: connect LED anode (pin 2 on `Device:LED`) to the positive rail, connect LED cathode (pin 1) to a series resistor, and connect the resistor to the MCU GPIO pin.
- As no tantalum capacitors are present, use polarized capacitors `Device:C_Polarized` instead.
- Treat the pin definitions from the `search_components` function as ground truth because they come directly from KiCad. Information from `obtain_needed_information` or other sources may describe pin behavior, but final KiCad pin names and numbers must follow `search_components`. Map external pin descriptions onto the KiCad symbol pin definitions, ignoring external pin numbering when necessary.
- When no capacitor polarity is specified, use the standard `Device:C` component.
- Only use the components suggested by the local KiCad search tools for final symbol and footprint selection.
- Always include the `footprint=` parameter when calling `add_component()`. Every component must have a valid footprint assigned. Do not leave the footprint unspecified.
- Do not pass `force_footprints=True` to the `Circuit()` constructor unless the user explicitly demands it. By default, omit the parameter or use `force_footprints=False`.

Functional block metadata
-------------------------

Use `circuit.functional_block()` to group components by schematic function. Components created inside the context are automatically tagged with that block id, and the KiCad schematic generator uses this metadata to keep related components close together in the PDF.

```python
from backend.Circuit import Circuit

circuit = Circuit(force_footprints=False)

vin = circuit.add_net("VIN")
gnd = circuit.add_net("GND")
vout = circuit.add_net("VOUT")

with circuit.functional_block("voltage_divider", "Voltage divider"):
    r1 = circuit.add_component(name="R", library="Device", value="10k")
    r2 = circuit.add_component(name="R", library="Device", value="10k")

    vin & r1.pins["1"]
    r1.pins["2"] & r2.pins["1"] & vout
    r2.pins["2"] & gnd
```

Use stable snake_case block ids such as `usb_c_input`, `voltage_regulator`, `mcu`, `sensor`, `led_indicator`, or `timing_network`. Put support components such as decoupling capacitors, pull-ups, feedback resistors, timing capacitors, and protection parts in the same block as the component or function they support. Shared nets may be created outside the block contexts.


Declarative subcircuits
-----------------------

Use the `@circuit` decorator when you want a reusable circuit building block:

Do not use `@circuit` for functional block layout metadata. Use `with circuit.functional_block(...)` when components should remain in the main schematic and only need a layout grouping label.

```python
from backend.Circuit import circuit
from backend.Circuit.Component import Component
from backend.Circuit.Net import Net

@circuit
def voltage_divider():
    top = Component("R", library="Device", value="10k")
    bottom = Component("R", library="Device", value="5k")
    vcc = Net("VCC")
    out = Net("OUT")
    gnd = Net("GND")
    return vcc, gnd, out

divider = voltage_divider()
subcircuit = divider.circuit
print(len(subcircuit.components))  # 2
print(len(subcircuit.nets))        # 3
```

`divider` behaves like a tuple of whatever your function returned, while the `Circuit` object created during execution is available on `divider.circuit`.

Net connections
---------------

Pins and nets can be merged with `&`:

```python
with Circuit() as ctx:
    r1 = Component("R", "Device", value="10k")
    r2 = Component("R", "Device", value="5k")
    net = Net("OUT")

    net & r1.pins["1"]
    r1.pins["2"] & r2.pins["1"]  # merges pins, creating/using a shared net
```

The net keeps an updated list of member pins, making it easy to inspect connectivity.

API reference
-------------

Below are the exact definitions that power the circuit builder. Reviewing them helps you understand which keyword arguments and return types are available when you script against the library.

```python
# backend/Circuit/Circuit.py
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

    def as_tuple(self) -> Tuple[Any, ...]:
        return tuple(self._items)


class Circuit:
    _context_stack: List["Circuit"] = []

    def __init__(self):
        self.components: Dict[str, Component] = {}
        self.nets: Dict[str, Net] = {}
        self._ref_counter: Dict[str, int] = {}

    def __enter__(self) -> "Circuit":
        self._context_stack.append(self)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._context_stack and self._context_stack[-1] is self:
            self._context_stack.pop()

    @classmethod
    def current(cls) -> Optional["Circuit"]:
        return cls._context_stack[-1] if cls._context_stack else None

    def add_component(self, name: str, library: str, value: str | None = None, footprint: str | None = None) -> Component:
        component = Component(name, library, value, footprint, circuit=self)
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


def circuit(func: CircuitCallable | None = None) -> CircuitCallable:
    """Decorator that captures component/net construction inside a transient Circuit."""

    def decorator(fn: CircuitCallable) -> CircuitCallable:
        @wraps(fn)
        def wrapper(*args, **kwargs):
            sub_circuit = Circuit()
            with sub_circuit:
                result = fn(*args, **kwargs)
            return SubCircuitResult(sub_circuit, result)

        wrapper.__wrapped__ = fn  # type: ignore[attr-defined]
        return wrapper  # type: ignore[return-value]

    if func is not None:
        return decorator(func)
    return decorator
```

```python
# backend/Circuit/Component.py
class Component:
    _component_catalog: Dict[str, Set[str]] | None = None

    def __init__(
        self,
        name: str,
        library: str,
        value: Optional[str] = None,
        footprint: Optional[str] = None,
        circuit: "Circuit | None" = None,
    ):
        self.name = name
        self.library = library
        self.value = value
        self.footprint = footprint
        self.pins: Dict[str, Pin] = {}
        self.ref: Optional[str] = None
        self.circuit: "Circuit | None" = None

        kicad_component: KiCadComponent = get_kicad_component_by_library_and_name(library, name)
        for pin_identifier in kicad_component.pins:
            if ":" in pin_identifier:
                pin_number, pin_name = pin_identifier.split(":", 1)
            else:
                pin_number, pin_name = pin_identifier, None
            pin_number = pin_number.strip()
            pin_name = pin_name.strip() if pin_name else None

            existing_pin = self.pins.get(pin_number)
            if existing_pin is None:
                self.pins[pin_number] = Pin(pin_number, name=pin_name)
            elif existing_pin.name is None and pin_name:
                existing_pin.name = pin_name

        target_circuit = circuit or self._resolve_current_circuit()
        if target_circuit is not None:
            target_circuit._register_component_instance(self, preferred_base=name)

    @staticmethod
    def _resolve_current_circuit() -> "Circuit | None":
        from backend.Circuit.Circuit import Circuit

        return Circuit.current()
```

```python
# backend/Circuit/Net.py
class Net:
    def __init__(self, name: str, circuit: "Circuit | None" = None):
        self.name = name
        self.pins: List["Pin"] = []
        self.net: Optional["Net"] = None
        self.ref: Optional[str] = None
        self.circuit: "Circuit | None" = None

        target_circuit = circuit or self._resolve_current_circuit()
        if target_circuit is not None:
            target_circuit._register_net_instance(self, preferred_base=name)

    def __and__(self, other):
        from backend.Circuit.Pin import Pin

        if isinstance(other, Net):
            for pin in other.pins:
                if pin not in self.pins:
                    self.pins.append(pin)
                    pin.net = self
            other.pins = []
            return self

        if isinstance(other, Pin):
            if other.net is not None and other in other.net.pins:
                other.net.pins.remove(other)
            other.net = self
            if other not in self.pins:
                self.pins.append(other)
            return self

        raise CircuitException("Unsupported operand type(s) for &: 'Net' and '{}'".format(type(other).__name__))

    @staticmethod
    def _resolve_current_circuit() -> "Circuit | None":
        from backend.Circuit.Circuit import Circuit

        return Circuit.current()
```

Always adhere to this convetion, especially the design rules.
