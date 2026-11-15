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
    p1_power=0,
    p2_power=0,
) -> MatchSnapshot:
    p1 = PlayerState(
        id=1,
        life=p1_life,
        life_max=1000,
        power=p1_power,
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
    assert action.reaction_type == "PUNISH_IN_PLACE"
    # Direction should be neutral, never forward towards enemy attack hitbox
    assert action.direction != DirectionInput.FORWARD


def test_guardrail_executes_super_punish_when_power_meter_ready(gatekeeper):
    # AI is in SAFE_BACK_ZONE with power >= 1000 on ground
    snapshot = create_snapshot(p1_x=-50.0, p1_y=0.0, p2_x=50.0, p2_y=0.0, p2_facing=1, p2_movetype="A", p1_power=1000)
    action = gatekeeper.evaluate(snapshot, desired_intent=EgoCentricIntent.RUSHDOWN)

    assert action.forward_locked is True
    assert action.safe_back_zone is True
    assert action.is_reaction is True
    assert action.reaction_type == "SUPER_PUNISH_IN_PLACE"
    assert action.cmd == "TripleKFPalm"


def test_airborne_p1_cannot_super_punish(gatekeeper):
    # AI is in SAFE_BACK_ZONE with power >= 1000, BUT P1 is airborne (y = -20.0 < -5.0)
    snapshot = create_snapshot(p1_x=-50.0, p1_y=-20.0, p2_x=50.0, p2_y=0.0, p2_facing=1, p2_movetype="A", p1_power=1000)
    action = gatekeeper.evaluate(snapshot, desired_intent=EgoCentricIntent.RUSHDOWN)

    # Must NOT output grounded Super Move mid-air!
    assert action.cmd != "TripleKFPalm"
    assert action.reaction_type != "SUPER_PUNISH_IN_PLACE"


def test_super_punish_target_out_of_reach(gatekeeper):
    # P1 is grounded, but P2 is airborne high above reach (p2_y = -90.0 < -80.0)
    snapshot = create_snapshot(p1_x=-50.0, p1_y=0.0, p2_x=50.0, p2_y=-90.0, p2_facing=1, p2_movetype="A", p1_power=1000)
    action = gatekeeper.evaluate(snapshot, desired_intent=EgoCentricIntent.RUSHDOWN)

    # Must NOT fire grounded Super Move when opponent is way up in the air
    assert action.cmd != "TripleKFPalm"
    assert action.reaction_type != "SUPER_PUNISH_IN_PLACE"


def test_super_punish_cooldown_enforced(gatekeeper):
    # First execution on frame 100
    snap1 = create_snapshot(p1_x=-50.0, p1_y=0.0, p2_x=50.0, p2_y=0.0, p2_facing=1, p2_movetype="A", p1_power=1000)
    snap1.frame = 100
    act1 = gatekeeper.evaluate(snap1, desired_intent=EgoCentricIntent.RUSHDOWN)
    assert act1.cmd == "TripleKFPalm"

    # Frame 105 (within 45-frame cooldown): Must NOT spam Super Move again!
    snap2 = create_snapshot(p1_x=-50.0, p1_y=0.0, p2_x=50.0, p2_y=0.0, p2_facing=1, p2_movetype="A", p1_power=1000)
    snap2.frame = 105
    act2 = gatekeeper.evaluate(snap2, desired_intent=EgoCentricIntent.RUSHDOWN)
    assert act2.cmd != "TripleKFPalm"
    assert act2.reaction_type != "SUPER_PUNISH_IN_PLACE"

    # Frame 160 (cooldown expired): Can execute Super Move again if opening still valid
    snap3 = create_snapshot(p1_x=-50.0, p1_y=0.0, p2_x=50.0, p2_y=0.0, p2_facing=1, p2_movetype="A", p1_power=1000)
    snap3.frame = 160
    act3 = gatekeeper.evaluate(snap3, desired_intent=EgoCentricIntent.RUSHDOWN)
    assert act3.cmd == "TripleKFPalm"


def test_centralized_ground_gate_strips_airborne_specials(gatekeeper):
    # P1 is airborne at y = -54.9 (like F:00367 in telemetry)
    # High-level intent commands ZONING
    snapshot = create_snapshot(p1_x=-50.0, p1_y=-54.9, p2_x=50.0, p2_y=0.0, p2_facing=-1, p2_movetype="I")
    action = gatekeeper.evaluate(snapshot, desired_intent=EgoCentricIntent.ZONING)

    # Button must be NONE, never SPECIAL_1
    assert action.button != ButtonInput.SPECIAL_1
    assert action.button == ButtonInput.NONE
    assert action.cmd is None




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
    # Opponent at x=50 facing left (-1) attacking toward P1 at x=0 from ground
    snapshot = create_snapshot(
        p1_x=0.0, p1_y=0.0, p1_facing=1, p1_movetype="I",
        p2_x=50.0, p2_y=0.0, p2_facing=-1, p2_movetype="A"
    )
    action = gatekeeper.evaluate(snapshot, desired_intent=EgoCentricIntent.RUSHDOWN)
    
    # Must activate crouching defensive guard (DOWN_BACK) and lock forward
    assert action.forward_locked is True
    assert action.direction == DirectionInput.DOWN_BACK
    assert action.is_reaction is True
    assert action.reaction_type == "INSTANT_BLOCK_LOW"


def test_instant_block_high_guard_when_opponent_overhead_without_anti_air(gatekeeper):
    # Opponent is airborne attacking (p2_y = -40) but outside anti-air distance (distance = 150 > 120)
    # P1 should stand block (BACK)
    snapshot = create_snapshot(
        p1_x=0.0, p1_y=0.0, p1_facing=1, p1_movetype="I",
        p2_x=150.0, p2_y=-40.0, p2_facing=-1, p2_movetype="A"
    )
    # Set danger proximity threshold high enough to trigger block
    gk = SafetyGatekeeper(proximity_danger_threshold=160.0, anti_air_distance=120.0)
    action = gk.evaluate(snapshot, desired_intent=EgoCentricIntent.RUSHDOWN)

    assert action.forward_locked is True
    assert action.direction == DirectionInput.BACK
    assert action.is_reaction is True
    assert action.reaction_type == "INSTANT_BLOCK_HIGH"


def test_air_combos_allowed_at_high_altitude(gatekeeper):
    # P1 is at y = -350.0 executing an air combo / juggle on airborne P2 in hitstun (movetype="H")
    # Camera vertical follow + zoomout covers this height; Gatekeeper MUST NOT interrupt air combos!
    snapshot = create_snapshot(
        p1_x=0.0, p1_y=-350.0, p1_facing=1, p1_movetype="A",
        p2_x=30.0, p2_y=-340.0, p2_facing=-1, p2_movetype="H"
    )
    action = gatekeeper.evaluate(snapshot, desired_intent=EgoCentricIntent.RUSHDOWN)

    # Air combo should proceed normally without being forced into ALTITUDE_CEILING_RECOVERY
    assert action.reaction_type != "ALTITUDE_CEILING_RECOVERY"
    assert action.button == ButtonInput.LIGHT_PUNCH


def test_altitude_ceiling_guardrail_prevents_offscreen_stall(gatekeeper):
    # P1 breaches the extreme stage altitude bound (p1_y = -760.0 near stage bound -800.0)
    # High-level intent requests continuing jump attacks
    snapshot = create_snapshot(
        p1_x=0.0, p1_y=-760.0, p1_facing=1, p1_movetype="A",
        p2_x=30.0, p2_y=-750.0, p2_facing=-1, p2_movetype="H"
    )
    action = gatekeeper.evaluate(snapshot, desired_intent=EgoCentricIntent.CROSS_UP)

    # Must detect extreme altitude ceiling breach and enforce neutral recovery to prevent engine clipping
    assert action.is_reaction is True
    assert action.reaction_type == "ALTITUDE_CEILING_RECOVERY"
    assert action.direction in (DirectionInput.NEUTRAL, DirectionInput.DOWN)
    assert action.forward_locked is True


def test_airborne_p1_cannot_crouch_block(gatekeeper):
    # P1 is airborne at y = -35.0 (< -5.0).
    # Opponent P2 attacks from ground (p2_y = 0.0) in proximity.
    # Gatekeeper MUST NOT output DOWN_BACK when P1 is mid-air!
    snapshot = create_snapshot(
        p1_x=0.0, p1_y=-35.0, p1_facing=1, p1_movetype="I",
        p2_x=50.0, p2_y=0.0, p2_facing=-1, p2_movetype="A"
    )
    action = gatekeeper.evaluate(snapshot, desired_intent=EgoCentricIntent.RUSHDOWN)

    assert action.direction != DirectionInput.DOWN_BACK
    assert action.direction == DirectionInput.BACK
    assert action.reaction_type in ("INSTANT_BLOCK_AIR", "INSTANT_BLOCK_HIGH")


def test_airborne_p1_anti_air_suppressed(gatekeeper):
    # P1 is airborne at y = -30.0 (< -5.0).
    # Opponent is airborne attacking overhead.
    # P1 cannot execute a grounded anti-air punch while mid-air!
    snapshot = create_snapshot(
        p1_x=-20.0, p1_y=-30.0, p1_facing=1, p1_movetype="I",
        p2_x=30.0, p2_y=-60.0, p2_facing=-1, p2_movetype="A"
    )
    action = gatekeeper.evaluate(snapshot, desired_intent=EgoCentricIntent.ZONING)

    # Anti-air should be suppressed or translated to air-safe guard
    assert action.reaction_type != "ANTI_AIR"


def test_ko_state_neutralizes_actions(gatekeeper):
    # When P1 life is 0 (KO)
    snapshot_p1_ko = create_snapshot(
        p1_x=0.0, p1_y=0.0, p1_facing=1, p1_movetype="H", p1_life=0,
        p2_x=50.0, p2_y=0.0, p2_facing=-1, p2_movetype="I", p2_life=500
    )
    action_p1_ko = gatekeeper.evaluate(snapshot_p1_ko, desired_intent=EgoCentricIntent.RUSHDOWN)
    assert action_p1_ko.direction == DirectionInput.NEUTRAL
    assert action_p1_ko.button == ButtonInput.NONE
    assert action_p1_ko.reaction_type == "ROUND_OVER"

    # When P2 life is 0 (KO)
    snapshot_p2_ko = create_snapshot(
        p1_x=0.0, p1_y=0.0, p1_facing=1, p1_movetype="I", p1_life=800,
        p2_x=50.0, p2_y=0.0, p2_facing=-1, p2_movetype="H", p2_life=0
    )
    action_p2_ko = gatekeeper.evaluate(snapshot_p2_ko, desired_intent=EgoCentricIntent.RUSHDOWN)
    assert action_p2_ko.direction == DirectionInput.NEUTRAL
    assert action_p2_ko.button == ButtonInput.NONE
    assert action_p2_ko.reaction_type == "ROUND_OVER"

