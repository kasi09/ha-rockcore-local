"""Frames a Rockcore micro inverter sends through its Hi-Flying WiFi module.

The inverter talks to the module over UART (115200 8N1); the module passes
the bytes through to the vendor cloud on socket A. Socket B can send a copy
of the same bytes to a second TCP server - that is how this integration
reads the inverter locally without touching the cloud connection.

Frame layout (verified on 2064 frames, all CRCs correct)::

    0x68 | ... | byte 3 = length | ... | crc16 (2 bytes, LE) | 0x16
    total length = byte 3 + 7
    crc = CRC16/MODBUS over everything before the CRC

    byte 15 = type, byte 22 = subtype
    bytes 24-31 = timestamp, ms since 1970 (LE)    (types 1 and 3)
    payload from byte 36

Values, verified against the RCMI app on 19.10.2026:

    type 3/2, every ~31 s: payload u16 LE at
        3-7 serial number (BCD), 8/10/12/14 power PV1-PV4 in W,
        16/18 voltage PV1/PV2 in 0.5 V, 24 grid voltage in V,
        26 grid frequency in 0.01 Hz, 28 temperature in degC
    type 3/1, every ~29 s: payload u16 at 0 = total power in 0.1 W
    type 1/2, every 5 min: u16 at 2 = total power in 0.1 W,
                           u32 at 6 = lifetime energy in Wh

The inverter also writes ``AT+\\r`` to the module now and then; anything that
is not a valid frame is skipped.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

START, END = 0x68, 0x16
MAX_FRAME = 512


def crc16_modbus(data: bytes) -> int:
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc


def frame_ok(frame: bytes) -> bool:
    return (
        len(frame) >= 10
        and frame[0] == START
        and frame[-1] == END
        and len(frame) == frame[3] + 7
        and crc16_modbus(frame[:-3]) == int.from_bytes(frame[-3:-1], "little")
    )


class FrameBuffer:
    """Cuts a TCP byte stream into valid frames. Garbage is dropped."""

    def __init__(self) -> None:
        self._buf = bytearray()
        self.dropped = 0

    def feed(self, data: bytes) -> list[bytes]:
        self._buf += data
        frames: list[bytes] = []
        while True:
            start = self._buf.find(START)
            if start < 0:
                self.dropped += len(self._buf)
                self._buf.clear()
                break
            if start:
                self.dropped += start
                del self._buf[:start]
            if len(self._buf) < 4:
                break
            length = self._buf[3] + 7
            if length > MAX_FRAME:
                self.dropped += 1
                del self._buf[0]
                continue
            if len(self._buf) < length:
                break
            candidate = bytes(self._buf[:length])
            if frame_ok(candidate):
                frames.append(candidate)
                del self._buf[:length]
            else:                     # not a frame start after all
                self.dropped += 1
                del self._buf[0]
        return frames


def _u16(b: bytes, i: int) -> int:
    return int.from_bytes(b[i:i + 2], "little")


@dataclass(frozen=True)
class Reading:
    kind: str                     # "channels", "power", "energy"
    time: datetime | None
    values: dict[str, Any]


def decode(frame: bytes) -> Reading | None:
    """Decode a valid frame. Unknown types return None."""
    ftype, sub = frame[15], frame[22]
    if ftype not in (1, 3) or len(frame) < 40:
        return None
    try:
        time = datetime.fromtimestamp(int.from_bytes(frame[24:32], "little") / 1000, UTC)
    except (OverflowError, OSError, ValueError):
        time = None
    p = frame[36:-3]
    if ftype == 3 and sub == 2 and len(p) >= 30:
        return Reading("channels", time, {
            "serial": p[3:8].hex(),
            "pv1_power": _u16(p, 8), "pv2_power": _u16(p, 10),
            "pv3_power": _u16(p, 12), "pv4_power": _u16(p, 14),
            "pv1_voltage": _u16(p, 16) / 2, "pv2_voltage": _u16(p, 18) / 2,
            "grid_voltage": _u16(p, 24), "grid_frequency": _u16(p, 26) / 100,
            "temperature": _u16(p, 28),
        })
    if ftype == 3 and sub == 1 and len(p) >= 2:
        return Reading("power", time, {"power": _u16(p, 0) / 10})
    if ftype == 1 and sub == 2 and len(p) >= 10:
        return Reading("energy", time, {
            "power": _u16(p, 2) / 10,
            "energy_wh": int.from_bytes(p[6:10], "little"),
        })
    return None
