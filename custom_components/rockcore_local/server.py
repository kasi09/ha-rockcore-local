"""TCP server that receives the copy the WiFi module sends on socket B.

The server never writes to the connection: everything sent there would go
straight to the inverter's UART.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable

from .protocol import FrameBuffer, Reading, decode

_LOGGER = logging.getLogger(__name__)


class InverterServer:
    """Accepts connections from the module and hands decoded readings on."""

    def __init__(
        self,
        host: str,
        port: int,
        on_reading: Callable[[Reading], None],
        on_connection: Callable[[bool], None],
    ) -> None:
        self._host, self._port = host, port
        self._on_reading, self._on_connection = on_reading, on_connection
        self._server: asyncio.Server | None = None
        self._clients: set[asyncio.StreamWriter] = set()

    @property
    def port(self) -> int:
        if self._server and self._server.sockets:
            return self._server.sockets[0].getsockname()[1]
        return self._port

    async def start(self) -> None:
        self._server = await asyncio.start_server(self._handle, self._host, self._port)

    async def stop(self) -> None:
        for writer in list(self._clients):
            writer.close()
        if self._server:
            self._server.close()
            await self._server.wait_closed()

    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        self._clients.add(writer)
        self._on_connection(True)
        frames = FrameBuffer()
        try:
            while data := await reader.read(4096):
                for frame in frames.feed(data):
                    if reading := decode(frame):
                        self._on_reading(reading)
        except (ConnectionError, asyncio.IncompleteReadError) as err:
            _LOGGER.debug("connection from module ended: %s", err)
        finally:
            self._clients.discard(writer)
            writer.close()
            self._on_connection(bool(self._clients))
