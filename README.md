# Rockcore Micro Inverter (local) — Home Assistant integration

Reads a **Rockcore micro inverter** (e.g. MI2S-800D, the one used with the
*RCMI* app) **locally**, without the vendor cloud — power per panel input,
total power, lifetime energy, grid voltage and frequency, temperature. Ready
for the **Energy dashboard** (solar production).

## How it works

The inverter talks to its Hi-Flying WiFi module (HF-LPT270) over UART; the
module forwards everything to the vendor cloud on **socket A**. The module
has a second channel, **socket B**, that can send a copy of the same bytes to
another TCP server. This integration is that server.

* The cloud connection and the RCMI app keep working unchanged.
* Nothing is ever sent to the inverter — the integration only listens.
* The config flow finds the module, shows its current socket B setting and
  — **only after you confirm** — points socket B to Home Assistant. When the
  integration is removed, the previous setting is restored.

Every frame is checked (start/end byte, length, CRC16/MODBUS) before it is
used; values were verified against the RCMI app.

## Night

The inverter is powered by the panels and switches off at night. That is
normal, not an error:

* power shows **0 W** (physically true; energy and power-flow cards need a number)
* grid voltage, frequency and temperature become *unknown*
* the lifetime energy keeps its value; **energy today** is calculated from
  the inverter's own counter

## Statistics stay clean

The lifetime energy is `total_increasing`. A reading that goes down or jumps
further than 250 kW could deliver in the elapsed time is held back, so a
corrupted frame cannot add phantom yield to the long-term statistics.

## Installation

1. HACS → ⋮ → *Custom repositories* → add this repository, category
   *Integration*.
2. Install **Rockcore Micro Inverter (local)**, restart Home Assistant.
3. **In daylight** (the module needs power): *Settings → Devices & services →
   Add integration → Rockcore Micro Inverter (local)*.
4. Confirm that socket B may be set to Home Assistant.
5. *Settings → Dashboards → Energy → Solar panels*: add **Total energy**.

Tested with an MI2S-800D (module firmware 4.00.01). Other inverters with the
same WiFi module and frame format will probably work too.

## License

Apache-2.0
