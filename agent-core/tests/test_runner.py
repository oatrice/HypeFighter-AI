"""Unit tests for MatchRunner round reset, log throttling, and fresh distance sync."""
import pytest
from unittest.mock import MagicMock
from agent_core.runner import MatchRunner
from agent_core.models.telemetry import (
    MatchSnapshot,
    PlayerState,
    Position,
)


@pytest.fixture
def runner():
    return MatchRunner(
        telemetry_file="/tmp/test_runner_tele.json",
        action_file="/tmp/test_runner_act.json",
    )


def test_runner_round_reset_detected(runner):
    # Step 1: Initial damage
    p1 = PlayerState(id=1, life=800, pos=Position(x=0.0, y=0.0), facing=1)
    p2 = PlayerState(id=2, life=900, pos=Position(x=50.0, y=0.0), facing=-1)
    snap1 = MatchSnapshot(frame=100, timestamp_ms=1000, distance=50.0, safe_back_zone=False, p1=p1, p2=p2)
    runner.on_snapshot(snap1)
    assert runner._had_combat_damage is True

    # Setup spy / mock on reset
    runner.combo_engine.reset = MagicMock()
    runner.tactical_brain.reset_round = MagicMock()

    # Step 2: Round resets to 1000 / 1000
    p1_reset = PlayerState(id=1, life=1000, pos=Position(x=0.0, y=0.0), facing=1)
    p2_reset = PlayerState(id=2, life=1000, pos=Position(x=50.0, y=0.0), facing=-1)
    snap2 = MatchSnapshot(frame=101, timestamp_ms=1016, distance=50.0, safe_back_zone=False, p1=p1_reset, p2=p2_reset)
    runner.on_snapshot(snap2)

    assert runner._had_combat_damage is False
    runner.combo_engine.reset.assert_called_once()
    runner.tactical_brain.reset_round.assert_called_once()


def test_runner_reaction_log_throttling(runner, capsys):
    # Opponent attacking from ground in proximity -> triggers INSTANT_BLOCK_LOW consecutively
    for f in range(1, 6):
        p1 = PlayerState(id=1, life=1000, pos=Position(x=0.0, y=0.0), facing=1, movetype="I")
        p2 = PlayerState(id=2, life=1000, pos=Position(x=50.0, y=0.0), facing=-1, movetype="A")
        snap = MatchSnapshot(frame=f, timestamp_ms=1000 + f * 16, distance=50.0, safe_back_zone=False, p1=p1, p2=p2)
        runner.on_snapshot(snap)

    captured = capsys.readouterr().out
    # Private mind should only appear once on initial reaction transition, not on every frame
    count_private_mind = captured.count("P1 Private Mind")
    assert count_private_mind <= 1, f"Expected throttled Private Mind logs <= 1, but got {count_private_mind}"


def test_runner_fresh_distance_sync(runner, capsys):
    from agent_core.tactician.tactical_brain import TacticalDecision
    from agent_core.models.telemetry import EgoCentricIntent

    # Set decision with stale distance (e.g. 427.1px)
    runner._latest_decision = TacticalDecision(
        stance="neutral_footsies",
        macro_intent=EgoCentricIntent.ZONING,
        thought="คุมระยะ",
        internal_monologue="สถานการณ์สมดุล ระยะห่าง 427.1px รักษาพื้นที่คุมจังหวะ Zoning",
        public_chat="เข้ามาเลย Shadow!",
    )

    # Frame 60 snapshot with fresh distance 164.6
    p1 = PlayerState(id=1, life=1000, pos=Position(x=0.0, y=0.0), facing=1, movetype="I")
    p2 = PlayerState(id=2, life=1000, pos=Position(x=164.6, y=0.0), facing=-1, movetype="I")
    snap = MatchSnapshot(frame=60, timestamp_ms=2000, distance=164.6, safe_back_zone=False, p1=p1, p2=p2)
    runner.on_snapshot(snap)

    out = capsys.readouterr().out
    assert "164.6px" in out
    assert "427.1px" not in out


def test_reaction_synced_narrative_special_hit_confirm(runner, capsys):
    from agent_core.tactician.tactical_brain import TacticalDecision
    from agent_core.models.telemetry import EgoCentricIntent, FighterAction, ButtonInput

    runner._latest_decision = TacticalDecision(
        stance="neutral_footsies",
        macro_intent=EgoCentricIntent.ZONING,
        thought="คุมระยะ",
        internal_monologue="สถานการณ์สมดุล ระยะห่าง 100.0px รักษาพื้นที่คุมจังหวะ Zoning",
        public_chat="เข้ามาเลย Shadow!",
    )

    # Mock ComboEngine to return a SPECIAL_HIT_CONFIRM action
    runner.combo_engine.update = MagicMock(return_value=FighterAction(
        button=ButtonInput.HEAVY_PUNCH,
        cmd="QCF_x",
        macro_intent=EgoCentricIntent.HOLD_SAFE_PUNISH,
        is_reaction=True,
        reaction_type="SPECIAL_HIT_CONFIRM",
    ))

    p1 = PlayerState(id=1, life=1000, pos=Position(x=0.0, y=0.0), facing=1, movetype="A")
    p2 = PlayerState(id=2, life=900, pos=Position(x=65.4, y=0.0), facing=-1, movetype="H")
    snap = MatchSnapshot(frame=100, timestamp_ms=2000, distance=65.4, safe_back_zone=False, p1=p1, p2=p2)
    runner.on_snapshot(snap)

    out = capsys.readouterr().out
    assert "65.4px" in out
    # Monologue must reflect hit-confirm, NOT stale Zoning monologue!
    assert "Zoning" not in out
    assert "QCF_x" in out or "Kung Fu Palm" in out or "คอมโบ" in out


def test_reaction_synced_narrative_super_punish(runner, capsys):
    from agent_core.tactician.tactical_brain import TacticalDecision
    from agent_core.models.telemetry import EgoCentricIntent

    runner._latest_decision = TacticalDecision(
        stance="neutral_footsies",
        macro_intent=EgoCentricIntent.RETREAT,
        thought="คุมระยะ",
        internal_monologue="ถอยคุมระยะ 200.0px",
        public_chat="ถอยตั้งหลัก",
    )

    # Frame with safe back zone and 1000 power -> triggers SUPER_PUNISH_IN_PLACE
    p1 = PlayerState(id=1, life=1000, power=1000, pos=Position(x=-50.0, y=0.0), facing=1, movetype="I")
    p2 = PlayerState(id=2, life=1000, power=0, pos=Position(x=50.0, y=0.0), facing=1, movetype="A")
    snap = MatchSnapshot(frame=200, timestamp_ms=3000, distance=100.0, safe_back_zone=True, p1=p1, p2=p2)
    runner.on_snapshot(snap)

    out = capsys.readouterr().out
    assert "100.0px" in out
    assert "Triple Kung Fu Palm" in out
    assert "เปิดช่องโหว่ด้านหลัง" in out or "สวนกลับด้วยท่าไม้ตาย" in out



