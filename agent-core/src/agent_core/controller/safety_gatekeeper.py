"""60Hz Reactive Safety Gatekeeper and Spatial Hitbox Guardrail.

Guarantees zero-latency physical safety:
1. Prevents walking forward into active hitboxes when positioned in a safe spot.
2. Identifies SAFE_BACK_ZONE and forces PUNISH_IN_PLACE.
3. Translates abstract ego-centric intents into engine directional inputs relative to character facing.
"""
from typing import Optional
from agent_core.models.telemetry import (
    PlayerState,
    MatchSnapshot,
    EgoCentricIntent,
    DirectionInput,
    ButtonInput,
    FighterAction,
)


class SafetyGatekeeper:
    """Zero-latency reactive safety guardrail running at 60 FPS."""

    def __init__(
        self,
        proximity_danger_threshold: float = 85.0,
        anti_air_distance: float = 120.0,
        altitude_ceiling_threshold: float = -750.0,
    ):
        self.proximity_danger_threshold = proximity_danger_threshold
        self.anti_air_distance = anti_air_distance
        self.altitude_ceiling_threshold = altitude_ceiling_threshold

    def is_in_safe_back_zone(self, p1: PlayerState, p2: PlayerState) -> bool:
        """Determines if AI (P1) is behind the attacking opponent (P2) relative to P2's attack direction.

        - If P2 is attacking facing Right (1) while P1 is on the Left (p1.pos.x < p2.pos.x),
          P1 is in SAFE_BACK_ZONE.
        - If P2 is attacking facing Left (-1) while P1 is on the Right (p1.pos.x > p2.pos.x),
          P1 is in SAFE_BACK_ZONE.
        """
        if not p2.is_attacking:
            return False

        if p2.facing == 1 and (p1.pos.x < p2.pos.x):
            return True

        if p2.facing == -1 and (p1.pos.x > p2.pos.x):
            return True

        return False

    def _relative_to_absolute_horizontal(self, direction: DirectionInput, facing: int) -> int:
        """Converts ego-centric direction (FORWARD / BACK) to engine horizontal axis (-1, 0, 1)."""
        if direction in (DirectionInput.FORWARD, DirectionInput.UP_FORWARD, DirectionInput.DOWN_FORWARD):
            return 1 if facing == 1 else -1
        if direction in (DirectionInput.BACK, DirectionInput.UP_BACK, DirectionInput.DOWN_BACK):
            return -1 if facing == 1 else 1
        return 0

    def evaluate(
        self,
        snapshot: MatchSnapshot,
        desired_intent: Optional[EgoCentricIntent] = None,
    ) -> FighterAction:
        """Evaluates match snapshot at 60Hz and produces a safe, actionable FighterAction."""
        intent = desired_intent or EgoCentricIntent.RETREAT
        p1 = snapshot.p1
        p2 = snapshot.p2
        safe_zone = self.is_in_safe_back_zone(p1, p2)
        is_p1_grounded = p1.pos.y >= -5.0

        # -1. KO / Round-Over Guard: Stop all actions when either player is knocked out (life <= 0)
        if p1.life <= 0 or p2.life <= 0:
            return FighterAction(
                direction=DirectionInput.NEUTRAL,
                button=ButtonInput.NONE,
                macro_intent=EgoCentricIntent.RETREAT,
                forward_locked=True,
                safe_back_zone=False,
                is_reaction=True,
                reaction_type="ROUND_OVER",
                absolute_horizontal=0,
                meta={"detail": "Round concluded (KO detected) - neutralizing all actions"},
            )

        # 0. Altitude Ceiling Guardrail: Prevent out-of-bounds stage boundary clipping.
        # Note: Air combos within high aerial flight envelope (-750.0 to 0.0) are fully allowed
        # and kept visible via the dynamic camera vertical follow and zoomout.
        if p1.pos.y < self.altitude_ceiling_threshold:
            return FighterAction(
                direction=DirectionInput.NEUTRAL,
                button=ButtonInput.NONE,
                macro_intent=EgoCentricIntent.RETREAT,
                forward_locked=True,
                safe_back_zone=False,
                is_reaction=True,
                reaction_type="ALTITUDE_CEILING_RECOVERY",
                absolute_horizontal=0,
                meta={
                    "detail": f"Fighter altitude ({p1.pos.y}) breached ceiling ({self.altitude_ceiling_threshold}) - neutralizing upward inputs for gravity recovery"
                },
            )

        # 1. Anti-Air Reaction Guard: Opponent airborne and attacking above grounded P1
        if is_p1_grounded and p2.pos.y < -30.0 and p2.is_attacking and snapshot.distance <= self.anti_air_distance:
            abs_h = 0
            return FighterAction(
                direction=DirectionInput.NEUTRAL,
                button=ButtonInput.HEAVY_PUNCH,
                macro_intent=EgoCentricIntent.HOLD_SAFE_PUNISH,
                forward_locked=True,
                safe_back_zone=False,
                is_reaction=True,
                reaction_type="ANTI_AIR",
                absolute_horizontal=abs_h,
                meta={"detail": "Airborne attack detected overhead - executing anti-air punish"},
            )

        # 2. Instant Block Guard: Opponent attacking directly in proximity (High/Low Mixup Defense)
        if p2.is_attacking and not safe_zone and snapshot.distance <= self.proximity_danger_threshold:
            # 2D Fighter Standard: Default to Crouch Guard (DOWN_BACK) against ground attacks only when P1 is grounded.
            # When P1 is airborne, crouch block is impossible; must use air guard (BACK).
            if is_p1_grounded and p2.pos.y >= -15.0:
                guard_dir = DirectionInput.DOWN_BACK
                reaction = "INSTANT_BLOCK_LOW"
                detail = "Incoming ground hitbox in range - auto-blocking low (DOWN_BACK)"
            elif not is_p1_grounded:
                guard_dir = DirectionInput.BACK
                reaction = "INSTANT_BLOCK_AIR"
                detail = "Airborne fighter blocking incoming attack in mid-air (BACK)"
            else:
                guard_dir = DirectionInput.BACK
                reaction = "INSTANT_BLOCK_HIGH"
                detail = "Incoming aerial hitbox in range - auto-blocking high (BACK)"

            abs_h = self._relative_to_absolute_horizontal(guard_dir, p1.facing)
            return FighterAction(
                direction=guard_dir,
                button=ButtonInput.NONE,
                macro_intent=EgoCentricIntent.RETREAT,
                forward_locked=True,
                safe_back_zone=False,
                is_reaction=True,
                reaction_type=reaction,
                absolute_horizontal=abs_h,
                meta={"detail": detail},
            )

        # 3. Spatial Hitbox Guardrail: Safe Back Zone Punishment
        if safe_zone:
            # Under NO circumstance may the AI walk forward into the enemy hitbox
            # Lock forward movement and execute PUNISH_IN_PLACE or SUPER_PUNISH_IN_PLACE if meter ready!
            super_cmd = "TripleKFPalm" if p1.power >= 1000 else None
            reaction_type = "SUPER_PUNISH_IN_PLACE" if super_cmd else "PUNISH_IN_PLACE"
            button = ButtonInput.NONE if super_cmd else ButtonInput.HEAVY_PUNCH
            detail = (
                "Enemy attack exposed back with >= 1000 power - executing Super Triple Kung Fu Palm!"
                if super_cmd
                else "Enemy attack exposed back - locking forward and punishing in place"
            )

            return FighterAction(
                direction=DirectionInput.NEUTRAL,
                button=button,
                cmd=super_cmd,
                macro_intent=EgoCentricIntent.HOLD_SAFE_PUNISH,
                forward_locked=True,
                safe_back_zone=True,
                is_reaction=True,
                reaction_type=reaction_type,
                absolute_horizontal=0,
                meta={"detail": detail},
            )

        # 4. Standard Relative Ego-Centric Intent Translation
        direction = DirectionInput.NEUTRAL
        button = ButtonInput.NONE
        forward_locked = False

        if intent == EgoCentricIntent.RETREAT:
            direction = DirectionInput.BACK
        elif intent == EgoCentricIntent.RUSHDOWN:
            direction = DirectionInput.FORWARD
            button = ButtonInput.LIGHT_PUNCH
        elif intent == EgoCentricIntent.ZONING:
            direction = DirectionInput.BACK if snapshot.distance < 120 else DirectionInput.NEUTRAL
            button = ButtonInput.SPECIAL_1 if is_p1_grounded else ButtonInput.NONE
        elif intent == EgoCentricIntent.CROSS_UP:
            direction = DirectionInput.UP_FORWARD
            button = ButtonInput.MEDIUM_KICK
        elif intent == EgoCentricIntent.HOLD_SAFE_PUNISH:
            direction = DirectionInput.NEUTRAL
            button = ButtonInput.HEAVY_PUNCH
            forward_locked = True

        abs_h = self._relative_to_absolute_horizontal(direction, p1.facing)

        return FighterAction(
            direction=direction,
            button=button,
            macro_intent=intent,
            forward_locked=forward_locked,
            safe_back_zone=safe_zone,
            is_reaction=False,
            absolute_horizontal=abs_h,
            meta={"detail": f"Standard intent execution: {intent.value}"},
        )
