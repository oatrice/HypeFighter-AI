"""Tier 2: 2-5Hz Tactical Brain (Local SLM / LLM).

Processes sliding-window combat log summaries and audience chat coaching
to output high-level tactical macro-intents and comic thought bubbles.
"""
from collections import deque
from typing import Any, Dict, List, Optional
from pydantic import BaseModel
from agent_core.models.telemetry import EgoCentricIntent, MatchSnapshot


class TacticalDecision(BaseModel):
    stance: str  # e.g., "whiff_punish", "zoning_keepout", "crossup_pressure", "clutch_comeback"
    macro_intent: EgoCentricIntent
    thought: str  # e.g., "เขาต่อยไปทางขวาเปิดหลังโล่ง สวนกลับตรงนี้เลย!"
    internal_monologue: str = ""  # Private internal monologue / CoT in head (Among Us private chat)
    public_chat: str = ""  # Public in-game chat to opponents/all players (Among Us game chat)
    audience_reply: Optional[str] = None  # Reply to viewer coaching
    thought_bubble: str = ""  # Concise text for floating thought bubble overlay
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
        """Fast heuristic fallback with dual-channel cognition (Private Inner Mind vs Public Chat)."""
        recent_chat = summary.get("recent_chat", [])
        latest_chat = recent_chat[-1] if recent_chat else None
        dist = summary.get("current_distance", 100.0)

        if summary.get("safe_back_zone"):
            thought = "ศัตรูต่อยไปทางเปิดหลังโล่ง สวนกลับตรงนี้เลย!"
            return TacticalDecision(
                stance="whiff_punish",
                macro_intent=EgoCentricIntent.HOLD_SAFE_PUNISH,
                thought=thought,
                thought_bubble=thought,
                internal_monologue=(
                    f"ตรวจพบจังหวะเปิดหลัง! P2 กำลังออกหมัดไปข้างหน้า แต่ตำแหน่งของเราอยู่อีกฝั่งอย่างปลอดภัย "
                    f"ระยะห่าง {dist:.1f}px ฮิตบ็อกซ์ของเขาไม่ถึงเรา สัญชาตญาณความปลอดภัยล็อกไม่ให้เดินหน้า "
                    f"ฉวยโอกาสลงโทษด้วยหมัดหนักตรงนี้ทันที!"
                ),
                public_chat="หมัดวืดไปไกลเลยนะ Shadow! หลังเปิดโล่งแบบนี้เสร็จแน่!",
                audience_reply=f"@Chat: รับทราบตามที่บอก '{latest_chat}'! ดักสวนจังหวะวืดเน้นๆ!" if latest_chat else None,
                morale_boost=True,
                confidence=0.95,
            )

        if summary.get("p1_life", 1000) < 250:
            thought = "เลือดเหลือน้อยแล้ว ตั้งการ์ดรอจังหวะสวน!"
            return TacticalDecision(
                stance="clutch_defense",
                macro_intent=EgoCentricIntent.RETREAT,
                thought=thought,
                thought_bubble=thought,
                internal_monologue=(
                    f"วิกฤต! เลือดเราเหลือต่ำกว่า 25% ({summary.get('p1_life')} HP) P2 กำลังกดดันอย่างหนัก "
                    f"ห้ามเสี่ยงเปิดหน้าแลกเด็ดขาด ต้องถอยคุมระยะ ตั้งการ์ดแน่น รอจับจังหวะเขาหลุดคอมโบเพื่อพลิกเกม!"
                ),
                public_chat="อย่าเพิ่งคิดว่าจะชนะง่ายๆ นะเพื่อน เลือดยังไม่หมดก็ยังไม่แพ้!",
                audience_reply=f"@Chat: '{latest_chat}' - กำลังตั้งรับ เลือดน้อยขอปลอดภัยไว้ก่อน!" if latest_chat else None,
                morale_boost=False,
                confidence=0.8,
            )

        thought = "คุมระยะให้ดี รอจับจังหวะเขาพลาด"
        return TacticalDecision(
            stance="neutral_footsies",
            macro_intent=EgoCentricIntent.ZONING,
            thought=thought,
            thought_bubble=thought,
            internal_monologue=(
                f"สถานการณ์สมดุล ระยะห่าง {dist:.1f}px รักษาพื้นที่คุมจังหวะ Zoning ดูเชิงการเดินของ P2 "
                f"รอให้เขาเป็นฝ่ายเปิดช่องโหว่ก่อน"
            ),
            public_chat="เข้ามาเลย Shadow อยากดูว่าจะงัดท่าไหนออกมา!",
            audience_reply=f"@Chat: ขอบคุณคำแนะนำ '{latest_chat}' กำลังดูเชิงอยู่!" if latest_chat else None,
            morale_boost=False,
            confidence=0.7,
        )
