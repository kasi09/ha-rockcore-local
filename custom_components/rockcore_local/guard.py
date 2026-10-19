"""Keep meter readings plausible before Home Assistant sees them.

A meter reading is ``total_increasing`` in Home Assistant, and HA treats
every decrease as a new meter cycle: the next value is added to the
long-term statistics in full. One glitch therefore costs the whole meter
reading once more - the same failure mode as a single corrupted heat meter
telegram of 1025 MWh. A reader that reboots and briefly reports 0 kWh does
exactly that.

Rules:
* A reading may not go down. A lower value is held back; only if it stays
  lower for ``RESET_AFTER`` polls in a row is it accepted as a real meter
  exchange.
* A reading may not jump further than ``MAX_KW`` could deliver in the time
  since the last accepted value.
"""

from __future__ import annotations

from dataclasses import dataclass, field

MAX_KW = 250.0          # far above any household connection
RESET_AFTER = 30        # polls; 5 minutes at 10 s

_TO_KWH = {"wh": 0.001, "kwh": 1.0, "mwh": 1000.0, "varh": 0.001, "kvarh": 1.0}


@dataclass
class MeterGuard:
    """Per-sensor state of the plausibility check."""

    last: float | None = None
    last_time: float | None = None
    lower_count: int = 0
    rejected: int = field(default=0)

    def check(self, value: float, unit: str | None, now: float) -> float | None:
        """Return the value to publish, or the previous one if implausible."""
        if self.last is None or self.last_time is None:
            self._accept(value, now)
            return value
        if value < self.last:
            self.lower_count += 1
            if self.lower_count >= RESET_AFTER:
                self._accept(value, now)
                return value
            self.rejected += 1
            return self.last
        self.lower_count = 0
        factor = _TO_KWH.get((unit or "kwh").lower(), 1.0)
        hours = max(now - self.last_time, 1.0) / 3600.0
        if (value - self.last) * factor > MAX_KW * hours:
            self.rejected += 1
            return self.last
        self._accept(value, now)
        return value

    def _accept(self, value: float, now: float) -> None:
        self.last, self.last_time, self.lower_count = value, now, 0
