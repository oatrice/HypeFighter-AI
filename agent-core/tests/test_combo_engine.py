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
) -> MatchSnapshot:
    p1 = PlayerState(
        id=1,
        life=p1_life,
        life_max=1000,
        power=p1_power,
        power_max=3000,
        pos=Position(x=0.0, y=0.0),
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
        pos=Position(x=40.0, y=0.0),
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


def test_combo_engine_aborts_on_blockstun():
    engine = ComboEngine()
    snap1 = make_snapshot(p1_movetype="A", p2_movetype="I", frame=1)
    engine.update(snap1)

    # Opponent is NOT in hitstun, but in block/idle after attack hits guard
    snap2 = make_snapshot(p1_movetype="I", p2_movetype="I", frame=15)
    action = engine.update(snap2)

    # Engine must abort combo to prevent unsafe whiff/punish
    assert engine.state == ComboState.IDLE
    assert action is None or action.direction == DirectionInput.DOWN_BACK


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

