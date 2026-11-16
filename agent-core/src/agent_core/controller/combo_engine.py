"""60Hz Deterministic Combo Macro Engine & Hit-Confirm Chaining.

Monitors player hitstun and blockstun transitions to:
1. Capitalize on confirmed attacks by executing multi-hit specials and Super moves.
2. Abort unsafe strings if opponent blocks or whiffs.
3. Dynamically spend power meter (>= 1000) for Super Hypers during confirmed punishes or clutch comebacks.
"""
from enum import Enum
from typing import Optional
import logging
from agent_core.models.telemetry import (
    MatchSnapshot,
    FighterAction,
    DirectionInput,
    ButtonInput,
    EgoCentricIntent,
)

logger = logging.getLogger(__name__)


class ComboState(str, Enum):
    IDLE = "IDLE"
    INITIATING = "INITIATING"
    CONFIRMED = "CONFIRMED"


class ComboEngine:
    """Deterministic finite state machine for combo sequencing and hit-confirms."""

    def __init__(self, timeout_frames: int = 30):
        self.timeout_frames = timeout_frames
        self.state: ComboState = ComboState.IDLE
        self.current_step: int = 0
        self.last_attack_frame: int = 0
        self.p2_consecutive_block_frames: int = 0
        self.last_mixup_was_low: bool = False

    def reset(self):
        """Resets the combo engine to IDLE state."""
        self.state = ComboState.IDLE
        self.current_step = 0
        self.last_attack_frame = 0

    def update(self, snapshot: MatchSnapshot) -> Optional[FighterAction]:
        """Evaluates match snapshot frame-by-frame and produces combo actions if applicable."""
        p1 = snapshot.p1
        p2 = snapshot.p2
        frame = snapshot.frame

        is_p1_grounded = p1.pos.y >= -5.0
        is_p2_blocking = (120 <= p2.stateno <= 155) or p2.stateno in (120, 130, 140, 150)
        if is_p2_blocking:
            self.p2_consecutive_block_frames += 1
        else:
            self.p2_consecutive_block_frames = 0

        # Okizeme Knockdown Pressure & Meaty Buffering
        is_p2_knockdown = p2.stateno in (5100, 5110, 5120)
        if is_p2_knockdown and is_p1_grounded:
            if self.state != ComboState.IDLE:
                self.reset()
            if p2.stateno == 5120 and snapshot.distance <= 55.0:
                return FighterAction(
                    direction=DirectionInput.DOWN,
                    button=ButtonInput.LIGHT_KICK,
                    macro_intent=EgoCentricIntent.RUSHDOWN,
                    forward_locked=False,
                    is_reaction=True,
                    reaction_type="OKIZEME_MEATY",
                    absolute_horizontal=0,
                    meta={"detail": "Okizeme meaty: buffering frame-1 c.LK on rising opponent (5120)"},
                )
            elif snapshot.distance > 55.0:
                return FighterAction(
                    direction=DirectionInput.FORWARD,
                    button=ButtonInput.NONE,
                    macro_intent=EgoCentricIntent.RUSHDOWN,
                    forward_locked=False,
                    is_reaction=True,
                    reaction_type="OKIZEME_APPROACH",
                    absolute_horizontal=1 if p1.facing == 1 else -1,
                    meta={"detail": "Okizeme approach: advancing forward into meaty strike distance"},
                )

        # High-Low Offensive Mixup against sustained turtling (holding block >= 30 frames)
        if self.p2_consecutive_block_frames >= 30 and snapshot.distance <= 75.0 and is_p1_grounded:
            if self.state != ComboState.IDLE:
                self.reset()
            if self.last_mixup_was_low:
                self.last_mixup_was_low = False
                return FighterAction(
                    direction=DirectionInput.NEUTRAL,
                    button=ButtonInput.LIGHT_PUNCH,
                    macro_intent=EgoCentricIntent.RUSHDOWN,
                    forward_locked=False,
                    is_reaction=True,
                    reaction_type="HIGH_LOW_MIXUP",
                    absolute_horizontal=0,
                    meta={"detail": "High-low offensive mixup: standing high attack (LP)"},
                )
            else:
                self.last_mixup_was_low = True
                return FighterAction(
                    direction=DirectionInput.DOWN,
                    button=ButtonInput.LIGHT_KICK,
                    macro_intent=EgoCentricIntent.RUSHDOWN,
                    forward_locked=False,
                    is_reaction=True,
                    reaction_type="HIGH_LOW_MIXUP",
                    absolute_horizontal=0,
                    meta={"detail": "High-low offensive mixup: crouching low sweep (DOWN+LK)"},
                )

        # 1. State: IDLE -> Transition to INITIATING on attack startup in close combat range
        if self.state == ComboState.IDLE:
            if (p1.is_attacking or p1.movetype == "A") and snapshot.distance <= 130.0:
                self.state = ComboState.INITIATING
                self.current_step = 1
                self.last_attack_frame = frame
            return None

        # 2. State: INITIATING -> Check for Hit-Confirm vs Block/Whiff
        if self.state == ComboState.INITIATING:
            if self.last_attack_frame == 0:
                self.last_attack_frame = frame

            # Check timeout
            if frame - self.last_attack_frame > self.timeout_frames:
                self.reset()
                return None

            is_p1_grounded = p1.pos.y >= -5.0
            is_p2_grounded = p2.pos.y >= -5.0
            is_p2_reachable = p2.pos.y >= -80.0
            is_p2_guarding = (120 <= p2.stateno <= 155 and (p2.movetype == "H" or p2.is_hurt))
            is_p2_hit = (p2.is_hurt or p2.movetype == "H") and not is_p2_guarding

            # Case A: Real Blockstun in Close Ground Combat (Requires ALL 5 strict conditions)
            if is_p2_guarding:
                self.reset()
                # Strict 5 conditions: Active state, Dist <= 130, Grounded P1, Grounded P2, True Guard State
                if snapshot.distance <= 130.0 and is_p1_grounded and is_p2_grounded:
                    return FighterAction(
                        direction=DirectionInput.DOWN_BACK,
                        button=ButtonInput.NONE,
                        macro_intent=EgoCentricIntent.RETREAT,
                        forward_locked=True,
                        is_reaction=True,
                        reaction_type="COMBO_ABORT_BLOCK",
                        absolute_horizontal=0,
                        meta={"detail": f"Opponent blocked attack (stateno={p2.stateno}) - aborting combo into ground guard"},
                    )
                # If any condition fails (airborne or distant), reset quietly without COMBO_ABORT_BLOCK
                return None

            # Case B: Hit Confirmed! (Opponent in true hitstun, not guarding)
            if is_p2_hit:
                self.state = ComboState.CONFIRMED
                self.current_step += 1

                # Check Clutch Comeback (Low HP <= 40% and power >= 1000)
                if p1.life <= 400 and p1.power >= 1000 and is_p1_grounded and is_p2_reachable:
                    return FighterAction(
                        direction=DirectionInput.NEUTRAL,
                        button=ButtonInput.NONE,
                        cmd="TripleKFPalm",
                        macro_intent=EgoCentricIntent.HOLD_SAFE_PUNISH,
                        forward_locked=True,
                        is_reaction=True,
                        reaction_type="SUPER_HIT_CONFIRM_CLUTCH",
                        absolute_horizontal=0,
                        meta={"detail": "Clutch Super Hit-Confirm (Triple Kung Fu Palm)"},
                    )

                # Standard Super Move Finisher (Power >= 1000)
                if p1.power >= 1000 and is_p1_grounded and is_p2_reachable:
                    return FighterAction(
                        direction=DirectionInput.NEUTRAL,
                        button=ButtonInput.NONE,
                        cmd="TripleKFPalm",
                        macro_intent=EgoCentricIntent.HOLD_SAFE_PUNISH,
                        forward_locked=True,
                        is_reaction=True,
                        reaction_type="SUPER_HIT_CONFIRM",
                        absolute_horizontal=0,
                        meta={"detail": "Super Move Hit-Confirm (Triple Kung Fu Palm)"},
                    )

                # Meterless Special Move Chaining (Power < 1000)
                is_p2_special_reachable = p2.pos.y >= -120.0
                if is_p1_grounded and is_p2_special_reachable:
                    return FighterAction(
                        direction=DirectionInput.NEUTRAL,
                        button=ButtonInput.HEAVY_PUNCH,
                        cmd="QCF_x",
                        macro_intent=EgoCentricIntent.HOLD_SAFE_PUNISH,
                        forward_locked=True,
                        is_reaction=True,
                        reaction_type="SPECIAL_HIT_CONFIRM",
                        absolute_horizontal=0,
                        meta={"detail": "Meterless Special Hit-Confirm (Kung Fu Palm QCF_x)"},
                    )
                else:
                    return FighterAction(
                        direction=DirectionInput.NEUTRAL,
                        button=ButtonInput.HEAVY_PUNCH,
                        cmd=None,
                        macro_intent=EgoCentricIntent.HOLD_SAFE_PUNISH,
                        forward_locked=True,
                        is_reaction=True,
                        reaction_type="JUGGLE_HIT_CONFIRM",
                        absolute_horizontal=0,
                        meta={"detail": "Aerial/Ceiling target juggle hit-confirm (Normal Attack)"},
                    )

            # Case C: Attack whiffs without block contact, or distance too far
            if not p1.is_attacking and p1.movetype != "A" and not is_p2_hit:
                self.reset()
                return None

            return None

        # 3. State: CONFIRMED -> Combo finisher issued, wait for sequence resolution
        if self.state == ComboState.CONFIRMED:
            if not p2.is_hurt and p2.movetype != "H":
                self.reset()
            elif frame - self.last_attack_frame > self.timeout_frames:
                self.reset()
            return None

        return None
