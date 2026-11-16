"""Tests for Combo Macro Engine and Hit-Confirm Chaining."""
import pytest
from agent_core.models.telemetry import (
    MatchSnapshot,
    PlayerState,
    Position,
    DirectionInput,
    ButtonInput,
    EgoCentricIntent,
    FighterAction,
)
from agent_core.controller.combo_engine import ComboEngine, ComboState


def make_snapshot(
    p1_life=1000,
    p1_power=1500,
    p1_movetype="A",
    p2_life=1000,
    p2_power=0,
    p2_movetype="H",
    distance=40.0,
    frame=100,
    p1_y=0.0,
    p2_y=0.0,
) -> MatchSnapshot:
    p1 = PlayerState(
        id=1,
        life=p1_life,
        life_max=1000,
        power=p1_power,
        power_max=3000,
        pos=Position(x=0.0, y=p1_y),
        facing=1,
        stateno=200,
        movetype=p1_movetype,
        ctrl=True,
    )
    p2 = PlayerState(
        id=2,
        life=p2_life,
        life_max=1000,
        power=p2_power,
        power_max=3000,
        pos=Position(x=40.0, y=p2_y),
        facing=-1,
        stateno=5000,  # Standard hitstun state
        movetype=p2_movetype,
        ctrl=False,
    )
    return MatchSnapshot(
        frame=frame,
        timestamp_ms=1700000000000 + frame * 16,
        distance=distance,
        safe_back_zone=False,
        p1=p1,
        p2=p2,
    )


def test_combo_engine_starts_in_idle():
    engine = ComboEngine()
    assert engine.state == ComboState.IDLE
    assert engine.current_step == 0


def test_combo_engine_initiates_on_attack():
    engine = ComboEngine()
    snap = make_snapshot(p1_movetype="A", p2_movetype="I", frame=1)
    engine.update(snap)
    assert engine.state == ComboState.INITIATING


def test_combo_engine_hit_confirm_triggers_chain():
    engine = ComboEngine()
    # Step 1: Initiating
    snap1 = make_snapshot(p1_movetype="A", p2_movetype="I", frame=1)
    engine.update(snap1)

    # Step 2: Opponent enters hitstun (Hit Confirmed!)
    snap2 = make_snapshot(p1_movetype="A", p2_movetype="H", p1_power=500, frame=2)
    action = engine.update(snap2)

    assert engine.state == ComboState.CONFIRMED
    assert action is not None
    # Power < 1000 should chain into meterless special move
    assert action.cmd == "QCF_x" or action.button == ButtonInput.HEAVY_PUNCH


def test_combo_engine_super_move_finisher_when_meter_available():
    engine = ComboEngine()
    # P1 has >= 1000 power
    snap1 = make_snapshot(p1_movetype="A", p2_movetype="I", p1_power=1200, frame=1)
    engine.update(snap1)

    # Hit confirm
    snap2 = make_snapshot(p1_movetype="A", p2_movetype="H", p1_power=1200, frame=2)
    action = engine.update(snap2)

    assert engine.state == ComboState.CONFIRMED
    assert action is not None
    # Must spend meter on Super Move "TripleKFPalm"
    assert action.cmd == "TripleKFPalm"
    assert action.reaction_type == "SUPER_HIT_CONFIRM"


def test_combo_engine_aborts_on_real_blockstun():
    engine = ComboEngine()
    # P1 attacks in close combat (distance 40px)
    snap1 = make_snapshot(p1_movetype="A", p2_movetype="I", distance=40.0, frame=1)
    engine.update(snap1)

    # Opponent blocks attack (Ikemen GO state 150: Stand Guard Hit, movetype="H")
    snap2 = make_snapshot(p1_movetype="I", p2_movetype="H", distance=40.0, frame=15)
    snap2.p2.stateno = 150  # Guard state in 120-155
    action = engine.update(snap2)

    # Engine must abort combo to prevent unsafe punish
    assert engine.state == ComboState.IDLE
    assert action is not None
    assert action.reaction_type == "COMBO_ABORT_BLOCK"
    assert action.direction == DirectionInput.DOWN_BACK


def test_no_combo_abort_block_at_long_range():
    engine = ComboEngine()
    # P1 whiffs attack at long range (distance 300px > 130px)
    snap1 = make_snapshot(p1_movetype="A", p2_movetype="I", distance=300.0, frame=1)
    engine.update(snap1)

    # P1 finishes attack animation while P2 is idle far away
    snap2 = make_snapshot(p1_movetype="I", p2_movetype="I", distance=300.0, frame=15)
    snap2.p2.stateno = 0
    action = engine.update(snap2)

    # Must NOT trigger COMBO_ABORT_BLOCK when fighters are far apart
    assert engine.state == ComboState.IDLE
    if action is not None:
        assert action.reaction_type != "COMBO_ABORT_BLOCK"


def test_no_combo_abort_block_when_opponent_not_guarding():
    engine = ComboEngine()
    # P1 attacks in close range, but P2 was never in guard state (e.g. idle or walk stateno 20)
    snap1 = make_snapshot(p1_movetype="A", p2_movetype="I", distance=50.0, frame=1)
    engine.update(snap1)

    snap2 = make_snapshot(p1_movetype="I", p2_movetype="I", distance=50.0, frame=15)
    snap2.p2.stateno = 0  # Neutral idle, not 120-155 guard
    action = engine.update(snap2)

    # Should reset cleanly to IDLE without false COMBO_ABORT_BLOCK
    assert engine.state == ComboState.IDLE
    if action is not None:
        assert action.reaction_type != "COMBO_ABORT_BLOCK"


def test_no_combo_abort_block_when_p2_airborne():
    engine = ComboEngine()
    # P1 attacks on ground at close range
    snap1 = make_snapshot(p1_movetype="A", p2_movetype="I", distance=50.0, p1_y=0.0, p2_y=0.0, frame=1)
    engine.update(snap1)

    # P2 is airborne (y = -35.0 < -5.0) and in air-guard state (stateno 152)
    snap2 = make_snapshot(p1_movetype="I", p2_movetype="H", distance=50.0, p1_y=0.0, p2_y=-35.0, frame=15)
    snap2.p2.stateno = 152
    action = engine.update(snap2)

    # Must NOT return COMBO_ABORT_BLOCK when P2 is airborne; must reset quietly to IDLE
    assert engine.state == ComboState.IDLE
    assert action is None


def test_no_combo_abort_block_when_p1_airborne():
    engine = ComboEngine()
    # P1 is airborne (y = -20.0 < -5.0) and attacks
    snap1 = make_snapshot(p1_movetype="A", p2_movetype="I", distance=50.0, p1_y=-20.0, p2_y=0.0, frame=1)
    engine.update(snap1)

    # P2 guards on ground (stateno 150)
    snap2 = make_snapshot(p1_movetype="I", p2_movetype="H", distance=50.0, p1_y=-20.0, p2_y=0.0, frame=15)
    snap2.p2.stateno = 150
    action = engine.update(snap2)

    # Must NOT return COMBO_ABORT_BLOCK when P1 is airborne; must reset quietly to IDLE
    assert engine.state == ComboState.IDLE
    assert action is None


def test_combo_engine_does_not_initiate_at_long_range():
    engine = ComboEngine()
    # P1 throws zoning projectile at distance 250px (> 130px)
    snap1 = make_snapshot(p1_movetype="A", p2_movetype="I", distance=250.0, frame=1)
    action = engine.update(snap1)

    # Engine must NOT initiate close-combat combo at long range
    assert engine.state == ComboState.IDLE
    assert action is None



def test_combo_engine_clutch_comeback_mode():
    engine = ComboEngine()
    # Low HP (<= 400), Power >= 1000
    snap = make_snapshot(
        p1_life=300,
        p1_power=1000,
        p1_movetype="A",
        p2_movetype="H",
        frame=50,
    )
    engine.state = ComboState.INITIATING
    action = engine.update(snap)

    assert action is not None
    assert action.cmd == "TripleKFPalm"
    assert "CLUTCH" in (action.reaction_type or "")


def test_combo_engine_airborne_p1_suppresses_ground_special():
    engine = ComboEngine()
    # P1 is airborne at y = -25.0 (< -5.0)
    snap = make_snapshot(p1_movetype="A", p2_movetype="H", p1_power=200, frame=10)
    snap.p1.pos.y = -25.0
    engine.state = ComboState.INITIATING

    action = engine.update(snap)
    # Ground palm QCF_x must NOT be executed mid-air
    if action is not None:
        assert action.cmd != "QCF_x"


def test_combo_engine_target_ceiling_suppresses_ground_special():
    engine = ComboEngine()
    # P2 is knocked high at y = -140.0 (< -120.0)
    snap = make_snapshot(p1_movetype="A", p2_movetype="H", p1_power=200, frame=10)
    snap.p2.pos.y = -140.0
    engine.state = ComboState.INITIATING

    action = engine.update(snap)
    # Ground palm QCF_x must NOT be executed when target is out of ceiling reach
    if action is not None:
        assert action.cmd != "QCF_x"

