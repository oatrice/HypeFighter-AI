"""Async UDP Telemetry Receiver for 60 FPS Ikemen GO stream."""
import asyncio
import logging
from typing import Callable, Optional
from agent_core.models.telemetry import MatchSnapshot

logger = logging.getLogger(__name__)


class _TelemetryProtocol(asyncio.DatagramProtocol):
    def __init__(self, receiver: "TelemetryUDPReceiver"):
        self.receiver = receiver

    def datagram_received(self, data: bytes, addr):
        try:
            snapshot = MatchSnapshot.model_validate_json(data)
            self.receiver.latest_snapshot = snapshot
            if self.receiver.on_snapshot:
                self.receiver.on_snapshot(snapshot)
        except Exception as exc:
            logger.debug("Failed to decode or parse telemetry packet from %s: %s", addr, exc)

    def error_received(self, exc):
        logger.warning("UDP error received: %s", exc)


class TelemetryUDPReceiver:
    """Async, zero-allocation UDP receiver handling 60 FPS combat snapshots."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 9999,
        on_snapshot: Optional[Callable[[MatchSnapshot], None]] = None,
    ):
        self.host = host
        self.port = port
        self.on_snapshot = on_snapshot
        self.latest_snapshot: Optional[MatchSnapshot] = None
        self._transport: Optional[asyncio.DatagramTransport] = None
        self._protocol: Optional[_TelemetryProtocol] = None

    @property
    def bound_port(self) -> int:
        """Returns the actual bound port (useful when bound to port 0)."""
        if self._transport:
            sock = self._transport.get_extra_info("socket")
            if sock:
                return sock.getsockname()[1]
        return self.port

    async def start(self):
        """Starts the async UDP listener."""
        loop = asyncio.get_running_loop()
        transport, protocol = await loop.create_datagram_endpoint(
            lambda: _TelemetryProtocol(self),
            local_addr=(self.host, self.port),
        )
        self._transport = transport
        self._protocol = protocol
        logger.info("TelemetryUDPReceiver listening on %s:%d", self.host, self.bound_port)

    async def stop(self):
        """Closes the UDP listener cleanly."""
        if self._transport:
            self._transport.close()
            self._transport = None
            self._protocol = None
            logger.info("TelemetryUDPReceiver stopped.")
