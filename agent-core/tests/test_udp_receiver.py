import asyncio
import json
import socket
import pytest
from agent_core.receiver.udp_receiver import TelemetryUDPReceiver
from agent_core.models.telemetry import MatchSnapshot


@pytest.mark.asyncio
async def test_udp_receiver_receives_and_parses_packet():
    received_snapshots = []

    def on_snapshot(snapshot: MatchSnapshot):
        received_snapshots.append(snapshot)

    receiver = TelemetryUDPReceiver(host="127.0.0.1", port=0, on_snapshot=on_snapshot)
    await receiver.start()

    actual_port = receiver.bound_port
    assert actual_port > 0

    # Create UDP client to send telemetry
    payload = {
        "frame": 42,
        "timestamp_ms": 1700000000042,
        "distance": 85.0,
        "safe_back_zone": True,
        "p1": {
            "id": 1,
            "life": 1000,
            "life_max": 1000,
            "power": 300,
            "power_max": 3000,
            "pos": {"x": -20.0, "y": 0.0},
            "facing": 1,
            "stateno": 0,
            "movetype": "I",
            "ctrl": True,
            "invincible": False,
            "armor": False
        },
        "p2": {
            "id": 2,
            "life": 900,
            "life_max": 1000,
            "power": 100,
            "power_max": 3000,
            "pos": {"x": 65.0, "y": 0.0},
            "facing": 1,
            "stateno": 220,
            "movetype": "A",
            "ctrl": False,
            "invincible": False,
            "armor": False
        },
        "events": []
    }

    client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    client.sendto(json.dumps(payload).encode("utf-8"), ("127.0.0.1", actual_port))
    client.close()

    # Wait briefly for async packet processing
    await asyncio.sleep(0.05)

    assert len(received_snapshots) == 1
    assert received_snapshots[0].frame == 42
    assert receiver.latest_snapshot is not None
    assert receiver.latest_snapshot.frame == 42
    assert receiver.latest_snapshot.safe_back_zone is True

    await receiver.stop()


@pytest.mark.asyncio
async def test_udp_receiver_handles_malformed_packet_gracefully():
    receiver = TelemetryUDPReceiver(host="127.0.0.1", port=0)
    await receiver.start()
    actual_port = receiver.bound_port

    client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    client.sendto(b"NOT_A_VALID_JSON_PACKET", ("127.0.0.1", actual_port))
    client.close()

    await asyncio.sleep(0.05)
    # Should not crash and latest_snapshot remains None
    assert receiver.latest_snapshot is None

    await receiver.stop()
