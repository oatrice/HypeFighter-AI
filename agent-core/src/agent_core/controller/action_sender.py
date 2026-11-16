"""Non-blocking UDP Action Sender.

Transmits verified FighterAction commands from the 60Hz Safety Gatekeeper
to Ikemen GO's bridge.lua on UDP port 9998 with sub-millisecond latency.
"""
import json
import logging
import socket
from typing import Any, Dict
from agent_core.models.telemetry import FighterAction

logger = logging.getLogger(__name__)


class ActionUDPSender:
    """Sends serialized fighter actions over local UDP to Ikemen GO."""

    def __init__(self, target_host: str = "127.0.0.1", target_port: int = 9998):
        self.target_host = target_host
        self.target_port = target_port
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.setblocking(False)

    def serialize_action(self, action: FighterAction, frame: int) -> Dict[str, Any]:
        """Encodes FighterAction into a compact dictionary for Lua consumption."""
        return {
            "frame": frame,
            "dir": action.direction.value,
            "btn": action.button.value,
            "cmd": action.cmd or "",
            "h_axis": action.absolute_horizontal,
            "f_lock": action.forward_locked,
            "reaction": action.reaction_type or "",
            "intent": action.macro_intent.value,
        }

    def send(self, action: FighterAction, frame: int) -> int:
        """Sends action datagram over UDP. Returns bytes sent."""
        payload_dict = self.serialize_action(action, frame)
        payload_bytes = json.dumps(payload_dict, separators=(",", ":")).encode("utf-8")
        try:
            return self._sock.sendto(payload_bytes, (self.target_host, self.target_port))
        except Exception as exc:
            logger.debug("Failed to send action UDP datagram: %s", exc)
            return 0

    def close(self):
        """Closes UDP socket cleanly."""
        try:
            self._sock.close()
        except Exception:
            pass
