"""Tier 2: 2-5Hz Tactical Brain (Local SLM / LLM).

Processes sliding-window combat log summaries and audience chat coaching
to output high-level tactical macro-intents and comic thought bubbles.
"""
from collections import deque
from typing import Any, Dict, List, Optional
from pydantic import BaseModel
from agent_core.models.telemetry import EgoCentricIntent, MatchSnapshot


class TacticalDecision(BaseModel):
    stance: str  # e.g., "whiff_punish", "zoning_keepout", "crossup_pressure"
    macro_intent: EgoCentricIntent
    thought: str  # e.g., "เขาต่อยไปทางขวาเปิดหลังโล่ง สวนกลับตรงนี้เลย!"
    morale_boost: bool = False
    confidence: float = 1.0


class TacticalBrain:
    """Sliding-window combat log aggregator and SLM inference controller."""

    def __init__(self, history_seconds: float = 3.0, fps: int = 60):
        self.max_frames = int(history_seconds * fps)
        self.history: deque[MatchSnapshot] = deque(maxlen=self.max_frames)
        self.viewer_chat_queue: deque[str] = deque(maxlen=50)
        self.current_decision: Optional[TacticalDecision] = None

    def ingest_snapshot(self, snapshot: MatchSnapshot):
        """Pushes latest 60Hz snapshot into the sliding window."""
        self.history.append(snapshot)

    def ingest_chat_message(self, message: str):
        """Pushes spectator coaching / cheer message."""
        self.viewer_chat_queue.append(message)

    def summarize_window(self) -> Dict[str, Any]:
        """Produces a structured combat summary of the sliding window for SLM/LLM prompt."""
        if not self.history:
            return {"status": "NO_DATA"}

        latest = self.history[-1]
        earliest = self.history[0]

        total_whiffs = 0
        total_p1_damage = 0
        total_p2_damage = 0

        for s in self.history:
            for ev in s.events:
                if ev.type == "WHIFF_DETECTED":
                    total_whiffs += 1
                elif ev.type == "DAMAGE_TAKEN":
                    if ev.target == "p1" and ev.amount:
                        total_p1_damage += ev.amount
                    elif ev.target == "p2" and ev.amount:
                        total_p2_damage += ev.amount

        return {
            "window_frames": len(self.history),
            "p1_life": latest.p1.life,
            "p2_life": latest.p2.life,
            "p1_life_delta": latest.p1.life - earliest.p1.life,
            "p2_life_delta": latest.p2.life - earliest.p2.life,
            "current_distance": latest.distance,
            "safe_back_zone": latest.safe_back_zone,
            "whiffs_detected": total_whiffs,
            "recent_chat": list(self.viewer_chat_queue),
        }

    def fallback_tactical_rule(self, summary: Dict[str, Any]) -> TacticalDecision:
        """Fast heuristic fallback when local SLM is idle or loading."""
        if summary.get("safe_back_zone"):
            return TacticalDecision(
                stance="whiff_punish",
                macro_intent=EgoCentricIntent.HOLD_SAFE_PUNISH,
                thought="ศัตรูต่อยไปทางเปิดหลังโล่ง สวนกลับตรงนี้เลย!",
                morale_boost=True,
                confidence=0.95,
            )

        if summary.get("p1_life", 1000) < 250:
            return TacticalDecision(
                stance="clutch_defense",
                macro_intent=EgoCentricIntent.RETREAT,
                thought="เลือดเหลือน้อยแล้ว ตั้งการ์ดรอจังหวะสวน!",
                morale_boost=False,
                confidence=0.8,
            )

        return TacticalDecision(
            stance="neutral_footsies",
            macro_intent=EgoCentricIntent.ZONING,
            thought="คุมระยะให้ดี รอจับจังหวะเขาพลาด",
            morale_boost=False,
            confidence=0.7,
        )
