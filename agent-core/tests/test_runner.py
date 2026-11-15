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

