import pytest
from agent_core.tactician.tactical_brain import TacticalBrain, TacticalDecision
from agent_core.models.telemetry import (
    MatchSnapshot,
    PlayerState,
    Position,
    CombatMicroEvent,
    EgoCentricIntent,
)


def test_tactical_brain_summarize_and_fallback():
    brain = TacticalBrain(history_seconds=1.0, fps=60)
    
    # Empty window
    summary_empty = brain.summarize_window()
    assert summary_empty["status"] == "NO_DATA"

    # Ingest snapshots
    p1 = PlayerState(id=1, life=1000, pos=Position(x=-50.0, y=0.0), facing=1)
    p2 = PlayerState(id=2, life=900, pos=Position(x=50.0, y=0.0), facing=1, movetype="A")
    event = CombatMicroEvent(type="WHIFF_DETECTED", actor="p2", frame=1, timestamp_ms=1000)

    snapshot = MatchSnapshot(
        frame=1,
        timestamp_ms=1000,
        distance=100.0,
        safe_back_zone=True,
        p1=p1,
        p2=p2,
        events=[event],
    )

    brain.ingest_snapshot(snapshot)
    brain.ingest_chat_message("สวนเลยพี่!")

    summary = brain.summarize_window()
    assert summary["p1_life"] == 1000
    assert summary["safe_back_zone"] is True
    assert summary["whiffs_detected"] == 1
    assert "สวนเลยพี่!" in summary["recent_chat"]

    decision = brain.fallback_tactical_rule(summary)
    assert decision.stance == "whiff_punish"
    assert decision.macro_intent == EgoCentricIntent.HOLD_SAFE_PUNISH
    assert "เปิดหลังโล่ง" in decision.thought


def test_dual_channel_among_us_cognition():
    """Tests Among Us-style dual-channel cognition: private inner thoughts vs public in-game chat."""
    brain = TacticalBrain(history_seconds=1.0, fps=60)
    p1 = PlayerState(id=1, life=1000, pos=Position(x=-40.0, y=0.0), facing=1)
    p2 = PlayerState(id=2, life=850, pos=Position(x=50.0, y=0.0), facing=1, movetype="A")

    snapshot = MatchSnapshot(
        frame=100,
        timestamp_ms=1000,
        distance=90.0,
        safe_back_zone=True,
        p1=p1,
        p2=p2,
    )
    brain.ingest_snapshot(snapshot)
    brain.ingest_chat_message("ต่อยสวนหลังเลย!")

    summary = brain.summarize_window()
    decision = brain.fallback_tactical_rule(summary)

    # 1. Private Mind (Internal Monologue / CoT): Detailed tactical reasoning in its head
    assert hasattr(decision, "internal_monologue")
    assert len(decision.internal_monologue) > 20
    assert "หลัง" in decision.internal_monologue

    # 2. Public In-Game Chat: Talking to the opponent (Shadow Rival)
    assert hasattr(decision, "public_chat")
    assert len(decision.public_chat) > 5
    assert any(w in decision.public_chat for w in ("Shadow", "หมัด", "ช่องโหว่", "หลัง"))

    # 3. Audience/Spectator Chat Interaction:
    assert hasattr(decision, "audience_reply")
    assert decision.audience_reply is not None
    assert "@" in decision.audience_reply

    # 4. Floating Thought Bubble Overlay:
    assert hasattr(decision, "thought_bubble")
    assert len(decision.thought_bubble) > 0
