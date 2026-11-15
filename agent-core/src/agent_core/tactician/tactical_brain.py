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
        """Fast heuristic fallback with dynamic situational cognition and varied phrase pools."""
        recent_chat = summary.get("recent_chat", [])
        latest_chat = recent_chat[-1] if recent_chat else None
        dist = summary.get("current_distance", 100.0)
        p1_life = summary.get("p1_life", 1000)
        p2_life = summary.get("p2_life", 1000)
        whiffs = summary.get("whiffs_detected", 0)
        frame_mod = summary.get("window_frames", 0)

        # Helper for audience reply
        audience_reply = None
        if latest_chat:
            if any(w in latest_chat for w in ("สวน", "ตี", "ต่อย")):
                audience_reply = f"@Chat: ได้ยินแล้ว! จัดไปตามคำสั่ง '{latest_chat}' ดักสวนเน้นๆ!"
            elif any(w in latest_chat for w in ("บุก", "ลุย", "เร็ว")):
                audience_reply = f"@Chat: คำสั่งบุกมาแล้ว '{latest_chat}' ลุยเต็มสูบ!"
            elif any(w in latest_chat for w in ("กัน", "ระวัง", "ถอย")):
                audience_reply = f"@Chat: รับทราบ '{latest_chat}' กำลังตั้งการ์ดแน่น!"
            else:
                audience_reply = f"@Chat: ขอบคุณคำแนะนำ '{latest_chat}' ปรับแผนตามนี้เลย!"

        # 1. Whiff Punish in Safe Back Zone
        if summary.get("safe_back_zone"):
            thought = "ศัตรูต่อยไปทางเปิดหลังโล่ง สวนกลับตรงนี้เลย!"
            taunts = [
                "หมัดวืดไปไกลเลยนะ Shadow! หลังเปิดโล่งแบบนี้เสร็จแน่!",
                "ช่องโหว่ด้านหลังบานเบอะเลยนะเพื่อน โดนแน่!",
                "เหวี่ยงลมไปไหน? หลังเปิดโล่งแบบนี้ไม่รอดหรอก!",
            ]
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
                public_chat=taunts[frame_mod % len(taunts)],
                audience_reply=audience_reply,
                morale_boost=True,
                confidence=0.95,
            )

        # 2. Critical Clutch Defense (Low Health)
        if p1_life < 250:
            thought = "เลือดเหลือน้อยแล้ว ตั้งการ์ดรอจังหวะสวน!"
            taunts = [
                "อย่าเพิ่งคิดว่าจะชนะง่ายๆ นะเพื่อน เลือดยังไม่หมดก็ยังไม่แพ้!",
                "ยังมีก๊อกสองอยู่น่า เข้ามาสิ!",
                "เลือดแดงแล้วไง? ดักสวนทีเดียวมีพลิกกระดาน!",
            ]
            return TacticalDecision(
                stance="clutch_defense",
                macro_intent=EgoCentricIntent.RETREAT,
                thought=thought,
                thought_bubble=thought,
                internal_monologue=(
                    f"วิกฤต! เลือดเราเหลือต่ำกว่า 25% ({p1_life} HP) P2 กำลังกดดันอย่างหนัก "
                    f"ห้ามเสี่ยงเปิดหน้าแลกเด็ดขาด ต้องถอยคุมระยะ ตั้งการ์ดแน่น รอจับจังหวะเขาหลุดคอมโบเพื่อพลิกเกม!"
                ),
                public_chat=taunts[frame_mod % len(taunts)],
                audience_reply=audience_reply,
                morale_boost=False,
                confidence=0.85,
            )

        # 3. Kill Confirm Opportunity (Opponent Low Health)
        if p2_life < 250:
            thought = "ศัตรูเลือดแดงแล้ว เดินหน้าปิดฉากแมตช์นี้!"
            taunts = [
                "เลือดแดงแล้วนะ Shadow! หมัดนี้ขอปิดเกมล่ะนะ!",
                "จบลำกล้องตรงนี้แหละ เตรียมตัว!",
                "ไม่มีที่ให้ถอยแล้วนะเพื่อน!",
            ]
            return TacticalDecision(
                stance="kill_confirm",
                macro_intent=EgoCentricIntent.RUSHDOWN,
                thought=thought,
                thought_bubble=thought,
                internal_monologue=(
                    f"โอกาสทอง! P2 เลือดเหลือเพียง {p2_life} HP กำลังร่อแร่ "
                    f"ต้องเดินหน้ากดดันเต็มกำลังเพื่อปิดฉากแมตช์ ห้ามปล่อยให้เขาฟื้นจังหวะ!"
                ),
                public_chat=taunts[frame_mod % len(taunts)],
                audience_reply=audience_reply,
                morale_boost=True,
                confidence=0.90,
            )

        # 4. Advantage Lead (P1 comfortably ahead)
        if p1_life - p2_life >= 200:
            thought = "แต้มเลือดนำอยู่ คุมเชิงและบีบพื้นที่!"
            taunts = [
                f"แต้มเลือดเรานำอยู่ {p1_life - p2_life} แต้ม เริ่มใจร้อนแล้วสิ Shadow!",
                "ถ้าไม่รีบบุกเข้ามา จะหมดเวลาเอานะ!",
                "รูปเกมเป็นของเรา สบายๆ ไม่ต้องรีบ!",
            ]
            return TacticalDecision(
                stance="advantage_lead",
                macro_intent=EgoCentricIntent.ZONING,
                thought=thought,
                thought_bubble=thought,
                internal_monologue=(
                    f"เราคุมความได้เปรียบ เลือดนำอยู่ {p1_life - p2_life} HP รักษาพื้นที่ตรงกลาง "
                    f"ล่อให้เขาเป็นฝ่ายใจร้อนบุกเข้ามา แล้วค่อยดักเคาน์เตอร์!"
                ),
                public_chat=taunts[frame_mod % len(taunts)],
                audience_reply=audience_reply,
                morale_boost=False,
                confidence=0.80,
            )

        # 5. Close-quarters Infight Pressure
        if dist < 65.0:
            thought = "ประชิดตัวแล้ว ระวังหมัดแย็บและลูกเตะตัดล่าง!"
            taunts = [
                "เบียดกันขนาดนี้ หายใจรดต้นคอเลยนะ!",
                "ระยะประชิดวัดใจ หมัดใครจะไวกว่ากัน!",
                "ใกล้ขนาดนี้ หมัดหนักพร้อมงัดเสมอ!",
            ]
            return TacticalDecision(
                stance="close_infight",
                macro_intent=EgoCentricIntent.RUSHDOWN,
                thought=thought,
                thought_bubble=thought,
                internal_monologue=(
                    f"ระยะประชิดอันตราย {dist:.1f}px อยู่ในระยะหมัดของทั้งคู่ "
                    f"ระวังหมัดแย็บและลูกเตะตัดล่าง ต้องเตรียมกดดันและชิงจังหวะก่อน!"
                ),
                public_chat=taunts[frame_mod % len(taunts)],
                audience_reply=audience_reply,
                morale_boost=False,
                confidence=0.75,
            )

        # 6. Neutral Footsies (Varied)
        footsie_thoughts = [
            f"สถานการณ์สมดุล ระยะห่าง {dist:.1f}px รักษาพื้นที่คุมจังหวะ Zoning ดูเชิงการเดินของ P2 รอให้เขาเป็นฝ่ายเปิดช่องโหว่ก่อน",
            f"P2 พยายามหาจังหวะขยับตัวเข้าทำ รักษาระยะ {dist:.1f}px ไว้ อย่าเพิ่งผลีผลามเปิดช่องโหว่",
            f"เวทียังนิ่ง ระยะ {dist:.1f}px รอดูว่า Shadow จะปล่อยท่าอะไรออกมาแล้วค่อยแก้ทาง",
        ]
        footsie_taunts = [
            "เข้ามาเลย Shadow อยากดูว่าจะงัดท่าไหนออกมา!",
            "ขยับช้าไปนะเพื่อน แบบนี้อ่านทางง่าย!",
            "ยังไม่กล้าเข้าเหรอ? งั้นฉันรอตรงนี้นะ!",
        ]
        thought = "คุมระยะให้ดี รอจับจังหวะเขาพลาด"
        idx = frame_mod % len(footsie_thoughts)
        return TacticalDecision(
            stance="neutral_footsies",
            macro_intent=EgoCentricIntent.ZONING,
            thought=thought,
            thought_bubble=thought,
            internal_monologue=footsie_thoughts[idx],
            public_chat=footsie_taunts[idx],
            audience_reply=audience_reply,
            morale_boost=False,
            confidence=0.7,
        )
