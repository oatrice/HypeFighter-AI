import asyncio
import json
import socket
import pytest
from agent_core.controller.action_sender import ActionUDPSender
from agent_core.models.telemetry import (
    FighterAction,
    DirectionInput,
    ButtonInput,
    EgoCentricIntent,
)


def test_action_sender_payload_serialization():
    sender = ActionUDPSender(target_host="127.0.0.1", target_port=9998)
    action = FighterAction(
        direction=DirectionInput.BACK,
        button=ButtonInput.HEAVY_PUNCH,
        cmd="TripleKFPalm",
        macro_intent=EgoCentricIntent.HOLD_SAFE_PUNISH,
        forward_locked=True,
        safe_back_zone=True,
        is_reaction=True,
        reaction_type="PUNISH_IN_PLACE",
        absolute_horizontal=-1,
    )

    payload_dict = sender.serialize_action(action, frame=105)
    assert payload_dict["frame"] == 105
    assert payload_dict["dir"] == "BACK"
    assert payload_dict["btn"] == "HP"
    assert payload_dict["cmd"] == "TripleKFPalm"
    assert payload_dict["h_axis"] == -1
    assert payload_dict["f_lock"] is True
    assert payload_dict["reaction"] == "PUNISH_IN_PLACE"


def test_action_sender_transmits_datagram_over_udp():
    # Setup test receiver socket
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_sock.bind(("127.0.0.1", 0))
    actual_port = server_sock.getsockname()[1]
    server_sock.settimeout(1.0)

    sender = ActionUDPSender(target_host="127.0.0.1", target_port=actual_port)
    action = FighterAction(
        direction=DirectionInput.FORWARD,
        button=ButtonInput.LIGHT_PUNCH,
        macro_intent=EgoCentricIntent.RUSHDOWN,
        forward_locked=False,
        absolute_horizontal=1,
    )

    # Transmit action
    bytes_sent = sender.send(action, frame=200)
    assert bytes_sent > 0

    # Verify datagram received by server
    data, addr = server_sock.recvfrom(2048)
    received_payload = json.loads(data.decode("utf-8"))

    assert received_payload["frame"] == 200
    assert received_payload["dir"] == "FORWARD"
    assert received_payload["btn"] == "LP"
    assert received_payload["h_axis"] == 1
    assert received_payload["f_lock"] is False

    sender.close()
    server_sock.close()
