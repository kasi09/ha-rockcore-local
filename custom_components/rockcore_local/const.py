"""Constants for the Rockcore Micro Inverter (local) integration."""

from datetime import timedelta
from typing import Final

DOMAIN: Final = "rockcore_local"
DEFAULT_PORT: Final = 8899
LISTEN_HOST: Final = "0.0.0.0"
CONF_MAC: Final = "mac"
CONF_MODULE_FW: Final = "module_firmware"
# socket B as found before this integration changed it, restored on removal
CONF_PREVIOUS_SOCKB: Final = "previous_socket_b"

# Frames come every ~30 s while the sun shines. After this long without one
# the inverter is considered asleep: power 0 W, grid values unknown.
STALE: Final = timedelta(minutes=10)
# Re-evaluate staleness even when no frames arrive (e.g. at night).
TICK: Final = timedelta(minutes=1)
