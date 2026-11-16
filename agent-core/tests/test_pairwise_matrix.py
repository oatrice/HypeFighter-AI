import pytest
from agent_core.controller.safety_gatekeeper import SafetyGatekeeper
from agent_core.models.telemetry import (
    ButtonInput,
    DirectionInput,
    EgoCentricIntent,
    MatchSnapshot,
    PlayerState,
    Position,
)


def _generate_pairwise_scenarios():
    """Generates a representative pairwise combination of fighter states.
    Parameters:
      - p1_y: 0.0 (ground) vs -45.0 (airborne)
      - p2_y: 0.0 (ground) vs -45.0 (airborne)
      - p1_facing: 1 (right) vs -1 (left)
      - distance: 50.0 (close) vs 120.0 (mid) vs 250.0 (far)
      - p1_power: 0 (empty) vs 1500 (full)
      - p2_movetype: "A" (attacking) vs "I" (idle) vs "H" (hurt)
      - p1_x: 0.0 (mid-stage) vs -150.0 (corner-left) vs 150.0 (corner-right)
      - intent: RETREAT vs RUSHDOWN vs ZONING
    """
    scenarios = [
        # Airborne P1 must never emit grounded specials/punches unless juggling hurt opponent
        {"p1_y": -45.0, "p2_y": 0.0, "p1_facing": 1, "dist": 50.0, "power": 1500, "movetype": "I", "p1_x": 0.0, "intent": EgoCentricIntent.RUSHDOWN},
        {"p1_y": -45.0, "p2_y": -45.0, "p1_facing": 1, "dist": 80.0, "power": 1500, "movetype": "H", "p1_x": 0.0, "intent": EgoCentricIntent.RUSHDOWN},
        {"p1_y": -45.0, "p2_y": 0.0, "p1_facing": -1, "dist": 200.0, "power": 0, "movetype": "I", "p1_x": 0.0, "intent": EgoCentricIntent.ZONING},
        # Corner retreat prevention
        {"p1_y": 0.0, "p2_y": 0.0, "p1_facing": 1, "dist": 150.0, "power": 0, "movetype": "I", "p1_x": -150.0, "intent": EgoCentricIntent.RETREAT},
        {"p1_y": 0.0, "p2_y": 0.0, "p1_facing": -1, "dist": 150.0, "power": 0, "movetype": "I", "p1_x": 150.0, "intent": EgoCentricIntent.RETREAT},
        # Grounded defense: airborne attacker triggers anti-air or high block
        {"p1_y": 0.0, "p2_y": -40.0, "p1_facing": 1, "dist": 60.0, "power": 0, "movetype": "A", "p1_x": 0.0, "intent": EgoCentricIntent.RETREAT},
        # Grounded defense: grounded attacker triggers low block
        {"p1_y": 0.0, "p2_y": 0.0, "p1_facing": 1, "dist": 60.0, "power": 0, "movetype": "A", "p1_x": 0.0, "intent": EgoCentricIntent.RETREAT},
        # Airborne defense: airborne P1 defending against attack triggers air block
        {"p1_y": -30.0, "p2_y": -30.0, "p1_facing": 1, "dist": 60.0, "power": 0, "movetype": "A", "p1_x": 0.0, "intent": EgoCentricIntent.RETREAT},
        # Super punish when ready in safe back zone
        {"p1_y": 0.0, "p2_y": 0.0, "p1_facing": 1, "dist": 70.0, "power": 1200, "movetype": "A", "p1_x": 0.0, "intent": EgoCentricIntent.HOLD_SAFE_PUNISH, "safe_back": True},
    ]
    return scenarios


@pytest.mark.parametrize("sc", _generate_pairwise_scenarios())
def test_safety_gatekeeper_pairwise_combinatorial_invariants(sc):
    gatekeeper = SafetyGatekeeper()

    p1 = PlayerState(
        id=1,
        life=1000,
        power=sc["power"],
        pos=Position(x=sc["p1_x"], y=sc["p1_y"]),
        facing=sc["p1_facing"],
        movetype="I",
    )
    p2_facing = -sc["p1_facing"] if not sc.get("safe_back") else sc["p1_facing"]
    p2_x = sc["p1_x"] + (sc["dist"] if sc["p1_facing"] == 1 else -sc["dist"])

    p2 = PlayerState(
        id=2,
        life=1000,
        power=0,
        pos=Position(x=p2_x, y=sc["p2_y"]),
        facing=p2_facing,
        movetype=sc["movetype"],
        stateno=220 if sc["movetype"] == "A" else (5000 if sc["movetype"] == "H" else 0),
    )

    snapshot = MatchSnapshot(
        frame=100,
        timestamp_ms=1600,
        distance=sc["dist"],
        safe_back_zone=sc.get("safe_back", False),
        p1=p1,
        p2=p2,
    )

    action = gatekeeper.evaluate(snapshot, desired_intent=sc["intent"])

    # INVARIANT 1: Airborne P1 must never emit grounded SPECIAL_1 or grounded normals unless juggling
    if sc["p1_y"] < -5.0:
        assert action.button != ButtonInput.SPECIAL_1
        assert action.cmd != "TripleKFPalm"
        if sc["movetype"] != "H":
            assert action.button != ButtonInput.LIGHT_PUNCH

    # INVARIANT 2: Corner Avoidance: Backed against wall must not retreat further back
    if (sc["p1_facing"] == 1 and sc["p1_x"] <= -140.0) or (sc["p1_facing"] == -1 and sc["p1_x"] >= 140.0):
        if sc["movetype"] == "I":
            assert action.direction != DirectionInput.BACK

    # INVARIANT 3: Action must always have valid directional and button enums
    assert isinstance(action.direction, DirectionInput)
    assert isinstance(action.button, ButtonInput)
