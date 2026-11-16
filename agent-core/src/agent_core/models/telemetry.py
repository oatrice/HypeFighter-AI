"""Pydantic data models for Ikemen GO fighter telemetry and actions."""
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class Position(BaseModel):
    x: float = 0.0
    y: float = 0.0


class PlayerState(BaseModel):
    id: int
    life: int = 1000
    life_max: int = 1000
    power: int = 0
    power_max: int = 3000
    pos: Position = Field(default_factory=Position)
    facing: int = 1  # 1 = Right, -1 = Left
    stateno: int = 0
    movetype: str = "I"  # "I" = Idle, "A" = Attack, "H" = Hit/Hurt
    ctrl: bool = False
    invincible: bool = False
    armor: bool = False

    @property
    def is_attacking(self) -> bool:
        return self.movetype.upper() == "A"

    @property
    def is_hurt(self) -> bool:
        return self.movetype.upper() == "H"

    @property
    def is_idle(self) -> bool:
        return self.movetype.upper() == "I"


class CombatMicroEvent(BaseModel):
    type: str  # e.g., "WHIFF_DETECTED", "DAMAGE_TAKEN", "BLOCK_STRING"
    actor: Optional[str] = None
    target: Optional[str] = None
    attacker: Optional[str] = None
    defender: Optional[str] = None
    stateno: Optional[int] = None
    amount: Optional[int] = None
    remaining_life: Optional[int] = None
    frame: int = 0
    timestamp_ms: int = 0


class MatchSnapshot(BaseModel):
    frame: int
    timestamp_ms: int
    distance: float = 0.0
    safe_back_zone: bool = False
    p1: PlayerState
    p2: PlayerState
    events: List[CombatMicroEvent] = Field(default_factory=list)
    meta: Dict[str, Any] = Field(default_factory=dict)


class EgoCentricIntent(str, Enum):
    HOLD_SAFE_PUNISH = "Hold_Safe_Punish"
    RETREAT = "Retreat"
    ZONING = "Zoning"
    RUSHDOWN = "Rushdown"
    CROSS_UP = "Cross_Up"


class DirectionInput(str, Enum):
    NEUTRAL = "NEUTRAL"
    FORWARD = "FORWARD"
    BACK = "BACK"
    UP = "UP"
    DOWN = "DOWN"
    UP_FORWARD = "UP_FORWARD"
    UP_BACK = "UP_BACK"
    DOWN_FORWARD = "DOWN_FORWARD"
    DOWN_BACK = "DOWN_BACK"


class ButtonInput(str, Enum):
    NONE = "NONE"
    LIGHT_PUNCH = "LP"
    MEDIUM_PUNCH = "MP"
    HEAVY_PUNCH = "HP"
    LIGHT_KICK = "LK"
    MEDIUM_KICK = "MK"
    HEAVY_KICK = "HK"
    SPECIAL_1 = "SPEC1"
    SPECIAL_2 = "SPEC2"


class FighterAction(BaseModel):
    direction: DirectionInput = DirectionInput.NEUTRAL
    button: ButtonInput = ButtonInput.NONE
    cmd: Optional[str] = None
    macro_intent: EgoCentricIntent = EgoCentricIntent.RETREAT
    forward_locked: bool = False
    safe_back_zone: bool = False
    is_reaction: bool = False
    reaction_type: Optional[str] = None
    absolute_horizontal: int = 0  # -1 = Left, 0 = Neutral, 1 = Right
    meta: Dict[str, Any] = Field(default_factory=dict)
