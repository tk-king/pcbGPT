Circuit authoring reference
===========================

Use `value=` only for passive electrical values such as resistors, capacitors, and inductors. Do not pass descriptive values to ICs, LEDs, connectors, bridges, sensors, or other functional parts.

Value field rules
-----------------

- Resistors: use plain ohm numbers or `k` and `M`, for example `330`, `4.7k`, `1M`.
- Capacitors: use explicit units `pF`, `nF`, or `uF`, for example `22pF`, `100nF`, `1uF`.
- Inductors: use explicit units `nH`, `uH`, or `mH`, for example `600nH`, `10uH`, `1mH`.
- Do not include spaces.
- Use ASCII only in values. Use `u` instead of `µ`, and never use `Ω`.
- Prefer canonical value strings. For capacitors, prefer `100nF` over equivalent forms such as `0.1uF`.
- For resistors below 1 kOhm, prefer plain numbers such as `220` or `330`.
- Ferrite beads should only use a `value` when the impedance is known and relevant.
- If a part does not have a passive electrical value, omit `value`.

Design rules
------------

- When connecting a resistor and `Device:LED` in series, always connect the resistor to the LED cathode. For `Device:LED`, pin 1 is cathode and pin 2 is anode.
- When adding pull-up resistors, use `10k` by default. For I2C pull-ups, use `4.7k`.
- As no tantalum capacitors are present, use polarized capacitors `Device:C_Polarized` instead.
- Treat the pin definitions from `search_components` as ground truth because they come directly from KiCad. Information from `obtain_needed_information` may describe pin behavior, but final KiCad pin names and numbers must follow `search_components`.
- When no capacitor polarity is specified, use the standard `Device:C` component.
- `Device:C` is unpolarized. Polarized capacitor symbols include `polarized` in the symbol name.

Net connections
---------------

- Connect pins and nets with `&`.
- Do not use control flow such as `for` or `if` in circuit code.
- Do not add voltage sources or ground symbols as components. Create named nets such as `VCC`, `GND`, `3V3`, or `5V` and connect them directly.
- Always expose the final schematic as a global variable named `circuit`.
