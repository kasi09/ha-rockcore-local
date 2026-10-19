"""Talk to the Hi-Flying WiFi module (HF-LPT270 and relatives) over UDP 48899.

Used only by the config flow: to find the module, read its firmware and
socket B setting, and - after the user confirmed it - point socket B to Home
Assistant. Socket A (the vendor cloud) is never touched.

Protocol: send the assist password, the module answers ``ip,mac,model``;
``+ok`` enters command mode; commands end with ``\\r`` and are answered with
``+ok=...`` or ``+ERR=...``; ``AT+Q`` leaves command mode.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

PORT = 48899
ASSIST = b"HF-A11ASSISTHREAD"
TIMEOUT = 3.0


class ModuleError(Exception):
    """The module did not answer."""


@dataclass(frozen=True)
class ModuleInfo:
    ip: str
    mac: str          # 12 hex digits as sent by the module
    model: str


class _Udp(asyncio.DatagramProtocol):
    def __init__(self) -> None:
        self.queue: asyncio.Queue[tuple[bytes, tuple]] = asyncio.Queue()

    def datagram_received(self, data: bytes, addr: tuple) -> None:
        self.queue.put_nowait((data, addr))


async def _endpoint(broadcast: bool = False):
    loop = asyncio.get_running_loop()
    transport, proto = await loop.create_datagram_endpoint(
        _Udp, local_addr=("0.0.0.0", 0), allow_broadcast=broadcast
    )
    return transport, proto


def _info(data: bytes) -> ModuleInfo | None:
    parts = data.decode(errors="replace").strip().split(",")
    if len(parts) >= 3 and len(parts[1]) == 12:
        return ModuleInfo(parts[0], parts[1].upper(), parts[2])
    return None


async def discover(timeout: float = TIMEOUT) -> list[ModuleInfo]:
    """Modules answering the assist broadcast in the local network."""
    transport, proto = await _endpoint(broadcast=True)
    found: dict[str, ModuleInfo] = {}
    try:
        transport.sendto(ASSIST, ("255.255.255.255", PORT))
        loop = asyncio.get_running_loop()
        end = loop.time() + timeout
        while (left := end - loop.time()) > 0:
            try:
                data, _addr = await asyncio.wait_for(proto.queue.get(), left)
            except TimeoutError:
                break
            if info := _info(data):
                found[info.mac] = info
    finally:
        transport.close()
    return list(found.values())


async def command(host: str, *commands: str, timeout: float = TIMEOUT) -> tuple[ModuleInfo, dict[str, str]]:
    """Run AT commands; returns module info and the answer per command."""
    transport, proto = await _endpoint()

    async def ask(payload: bytes) -> bytes:
        transport.sendto(payload, (host, PORT))
        try:
            data, _addr = await asyncio.wait_for(proto.queue.get(), timeout)
        except TimeoutError as err:
            raise ModuleError(f"no answer from {host}") from err
        return data

    try:
        info = _info(await ask(ASSIST))
        if info is None:
            raise ModuleError("unexpected answer to assist request")
        transport.sendto(b"+ok", (host, PORT))
        answers: dict[str, str] = {}
        for cmd in commands:
            answers[cmd] = (await ask(cmd.encode() + b"\r")).decode(errors="replace").strip()
        transport.sendto(b"AT+Q\r", (host, PORT))
        return info, answers
    finally:
        transport.close()


def answer_value(answer: str) -> str | None:
    """``+ok=TCP,8899,1.2.3.4`` -> ``TCP,8899,1.2.3.4``; errors -> None."""
    if answer.startswith("+ok="):
        return answer[4:]
    return "" if answer == "+ok" else None


def socket_b_target(value: str | None) -> tuple[str, int] | None:
    """``TCP,8899,1.2.3.4`` -> ("1.2.3.4", 8899); NONE or garbage -> None."""
    if not value:
        return None
    parts = value.split(",")
    if len(parts) == 3 and parts[0].upper() == "TCP" and parts[1].isdigit():
        return parts[2], int(parts[1])
    return None
