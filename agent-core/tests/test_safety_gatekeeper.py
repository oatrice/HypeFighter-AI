import pytest
from agent_core.models.telemetry import (
    PlayerState,
    Position,
    MatchSnapshot,
    EgoCentricIntent,
    FighterAction,
    DirectionInput,
    ButtonInput,
)
from agent_core.controller.safety_gatekeeper import SafetyGatekeeper


@pytest.fixture
def gatekeeper():
    return SafetyGatekeeper()


def create_snapshot(
    p1_x=-50.0,
    p1_y=0.0,
    p1_facing=1,
    p1_movetype="I",
    p2_x=50.0,
    p2_y=0.0,
    p2_facing=1,
    p2_movetype="A",
    p1_life=1000,
    p2_life=1000,
) -> MatchSnapshot:
    p1 = PlayerState(
        id=1,
        life=p1_life,
        life_max=1000,
        power=1000,
        power_max=3000,
        pos=Position(x=p1_x, y=p1_y),
        facing=p1_facing,
        stateno=0,
        movetype=p1_movetype,
        ctrl=True,
    )
    p2 = PlayerState(
        id=2,
        life=p2_life,
        life_max=1000,
        power=500,
        power_max=3000,
        pos=Position(x=p2_x, y=p2_y),
        facing=p2_facing,
        stateno=200,
        movetype=p2_movetype,
        ctrl=False,
    )
    return MatchSnapshot(
        frame=100,
        timestamp_ms=1700000000100,
        distance=abs(p1_x - p2_x),
        safe_back_zone=False,  # Gatekeeper re-verifies this
        p1=p1,
        p2=p2,
    )


def test_safe_back_zone_detection_opponent_facing_right(gatekeeper):
    # Opponent at x=50 facing right (1) attacking right.
    # AI is at x=-50 (behind opponent on left).
    snapshot = create_snapshot(p1_x=-50.0, p2_x=50.0, p2_facing=1, p2_movetype="A")
    assert gatekeeper.is_in_safe_back_zone(snapshot.p1, snapshot.p2) is True


def test_safe_back_zone_detection_opponent_facing_left(gatekeeper):
    # Opponent at x=-50 facing left (-1) attacking left.
    # AI is at x=50 (behind opponent on right).
    snapshot = create_snapshot(p1_x=50.0, p2_x=-50.0, p2_facing=-1, p2_movetype="A")
    assert gatekeeper.is_in_safe_back_zone(snapshot.p1, snapshot.p2) is True


def test_safe_back_zone_false_when_in_front_of_attack(gatekeeper):
    # Opponent at x=50 facing left (-1) attacking left toward AI at x=-50.
    # AI is directly in the path of attack!
    snapshot = create_snapshot(p1_x=-50.0, p2_x=50.0, p2_facing=-1, p2_movetype="A")
    assert gatekeeper.is_in_safe_back_zone(snapshot.p1, snapshot.p2) is False


def test_safe_back_zone_false_when_opponent_not_attacking(gatekeeper):
    # Opponent is idle
    snapshot = create_snapshot(p1_x=-50.0, p2_x=50.0, p2_facing=1, p2_movetype="I")
    assert gatekeeper.is_in_safe_back_zone(snapshot.p1, snapshot.p2) is False


def test_guardrail_locks_forward_movement_and_forces_punish_in_place(gatekeeper):
    # AI is behind attacking opponent in SAFE_BACK_ZONE.
    # High-level intent naively commands Rushdown (forward movement).
    # Safety Gatekeeper MUST lock forward movement into active attack hitbox
    # and execute PUNISH_IN_PLACE from current safe spot!
    snapshot = create_snapshot(p1_x=-50.0, p2_x=50.0, p2_facing=1, p2_movetype="A")
    
    action = gatekeeper.evaluate(snapshot, desired_intent=EgoCentricIntent.RUSHDOWN)
    
    assert action.forward_locked is True
    assert action.safe_back_zone is True
    assert action.macro_intent == EgoCentricIntent.HOLD_SAFE_PUNISH
    assert action.button == ButtonInput.HEAVY_PUNCH  # Punish button
    # Direction should be neutral, never forward towards enemy attack hitbox
    assert action.direction != DirectionInput.FORWARD


def test_ego_centric_relative_intent_retreat_facing_right(gatekeeper):
    # P1 facing right (1) retreats -> relative BACK is directional LEFT
    snapshot = create_snapshot(p1_x=-100.0, p1_facing=1, p2_x=100.0, p2_facing=-1, p2_movetype="I")
    action = gatekeeper.evaluate(snapshot, desired_intent=EgoCentricIntent.RETREAT)
    
    assert action.direction == DirectionInput.BACK
    assert action.absolute_horizontal == -1  # Left in engine coords


def test_ego_centric_relative_intent_retreat_facing_left(gatekeeper):
    # P1 facing left (-1) retreats -> relative BACK is directional RIGHT
    snapshot = create_snapshot(p1_x=100.0, p1_facing=-1, p2_x=-100.0, p2_facing=1, p2_movetype="I")
    action = gatekeeper.evaluate(snapshot, desired_intent=EgoCentricIntent.RETREAT)
    
    assert action.direction == DirectionInput.BACK
    assert action.absolute_horizontal == 1  # Right in engine coords


def test_ego_centric_relative_intent_rushdown_facing_right(gatekeeper):
    # Opponent is idle, safe to approach
    snapshot = create_snapshot(p1_x=-100.0, p1_facing=1, p2_x=100.0, p2_facing=-1, p2_movetype="I")
    action = gatekeeper.evaluate(snapshot, desired_intent=EgoCentricIntent.RUSHDOWN)
    
    assert action.forward_locked is False
    assert action.direction == DirectionInput.FORWARD
    assert action.absolute_horizontal == 1  # Right in engine coords


def test_ego_centric_relative_intent_rushdown_facing_left(gatekeeper):
    # Opponent is idle, P1 facing left
    snapshot = create_snapshot(p1_x=100.0, p1_facing=-1, p2_x=-100.0, p2_facing=1, p2_movetype="I")
    action = gatekeeper.evaluate(snapshot, desired_intent=EgoCentricIntent.RUSHDOWN)
    
    assert action.forward_locked is False
    assert action.direction == DirectionInput.FORWARD
    assert action.absolute_horizontal == -1  # Left in engine coords


def test_anti_air_reaction_when_opponent_airborne_attacking(gatekeeper):
    # Opponent is in the air attacking (p2_y < -30) in proximity
    snapshot = create_snapshot(
        p1_x=-20.0, p1_y=0.0, p1_facing=1, p1_movetype="I",
        p2_x=30.0, p2_y=-60.0, p2_facing=-1, p2_movetype="A"
    )
    action = gatekeeper.evaluate(snapshot, desired_intent=EgoCentricIntent.ZONING)
    
    assert action.is_reaction is True
    assert action.reaction_type == "ANTI_AIR"
    assert action.button == ButtonInput.HEAVY_PUNCH


def test_instant_block_when_opponent_attacking_in_proximity(gatekeeper):
    # Opponent at x=50 facing left (-1) attacking toward P1 at x=0
    snapshot = create_snapshot(
        p1_x=0.0, p1_y=0.0, p1_facing=1, p1_movetype="I",
        p2_x=50.0, p2_y=0.0, p2_facing=-1, p2_movetype="A"
    )
    action = gatekeeper.evaluate(snapshot, desired_intent=EgoCentricIntent.RUSHDOWN)
    
    # Must activate defensive guard and lock forward
    assert action.forward_locked is True
    assert action.direction == DirectionInput.BACK
    assert action.is_reaction is True
    assert action.reaction_type == "INSTANT_BLOCK"
