import json
import pytest
from agent_core.models.telemetry import (
    PlayerState,
    Position,
    MatchSnapshot,
    CombatMicroEvent,
    EgoCentricIntent,
    FighterAction,
)


def test_position_model():
    pos = Position(x=120.5, y=-40.0)
    assert pos.x == 120.5
    assert pos.y == -40.0


def test_player_state_model():
    player = PlayerState(
        id=1,
        life=950,
        life_max=1000,
        power=1500,
        power_max=3000,
        pos=Position(x=-80.0, y=0.0),
        facing=1,
        stateno=0,
        movetype="I",
        ctrl=True,
        invincible=False,
        armor=False,
    )
    assert player.id == 1
    assert player.life == 950
    assert player.is_attacking is False
    assert player.is_hurt is False
    assert player.is_idle is True


def test_player_state_attacking_and_hurt_helpers():
    atk = PlayerState(
        id=2,
        life=1000,
        life_max=1000,
        power=0,
        power_max=3000,
        pos=Position(x=50.0, y=0.0),
        facing=1,
        stateno=200,
        movetype="A",
        ctrl=False,
    )
    assert atk.is_attacking is True
    assert atk.is_idle is False

    hurt = PlayerState(
        id=1,
        life=800,
        life_max=1000,
        power=500,
        power_max=3000,
        pos=Position(x=-50.0, y=0.0),
        facing=1,
        stateno=5000,
        movetype="H",
        ctrl=False,
    )
    assert hurt.is_hurt is True


def test_match_snapshot_from_json():
    raw_payload = json.dumps({
        "frame": 120,
        "timestamp_ms": 1700000000120,
        "distance": 130.0,
        "safe_back_zone": True,
        "p1": {
            "id": 1,
            "life": 1000,
            "life_max": 1000,
            "power": 1000,
            "power_max": 3000,
            "pos": {"x": -80.0, "y": 0.0},
            "facing": 1,
            "stateno": 0,
            "movetype": "I",
            "ctrl": True,
            "invincible": False,
            "armor": False
        },
        "p2": {
            "id": 2,
            "life": 850,
            "life_max": 1000,
            "power": 200,
            "power_max": 3000,
            "pos": {"x": 50.0, "y": 0.0},
            "facing": 1,
            "stateno": 210,
            "movetype": "A",
            "ctrl": False,
            "invincible": False,
            "armor": False
        },
        "events": [
            {
                "type": "WHIFF_DETECTED",
                "actor": "p2",
                "target": "p1",
                "stateno": 210,
                "frame": 120,
                "timestamp_ms": 1700000000120
            }
        ]
    })

    snapshot = MatchSnapshot.model_validate_json(raw_payload)
    assert snapshot.frame == 120
    assert snapshot.safe_back_zone is True
    assert snapshot.p1.pos.x == -80.0
    assert snapshot.p2.is_attacking is True
    assert len(snapshot.events) == 1
    assert snapshot.events[0].type == "WHIFF_DETECTED"
