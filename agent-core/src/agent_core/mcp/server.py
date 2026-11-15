"""MCP Server interface for character tuning and match inspection."""
from typing import Any, Dict, Optional
from agent_core.models.telemetry import MatchSnapshot


class FighterMCPServer:
    """Provides tools for external AI coding agents (Claude Code / OpenCode / Antigravity)."""

    def __init__(self):
        self._current_snapshot: Optional[MatchSnapshot] = None
        self._frame_data_cache: Dict[int, Dict[str, Any]] = {
            200: {"name": "Standing Light Punch", "startup": 4, "active": 3, "recovery": 7, "on_block": +2},
            210: {"name": "Standing Medium Punch", "startup": 6, "active": 4, "recovery": 11, "on_block": -1},
            220: {"name": "Standing Heavy Punch", "startup": 9, "active": 5, "recovery": 18, "on_block": -6},
        }

    def update_snapshot(self, snapshot: MatchSnapshot):
        self._current_snapshot = snapshot

    def get_match_snapshot(self) -> Dict[str, Any]:
        """Returns the latest match snapshot or an idle status dict."""
        if not self._current_snapshot:
            return {"status": "WAITING_FOR_MATCH"}
        return self._current_snapshot.model_dump()

    def query_frame_data(self, stateno: int) -> Dict[str, Any]:
        """Queries frame data by animation state number."""
        if stateno in self._frame_data_cache:
            return {"stateno": stateno, "data": self._frame_data_cache[stateno]}
        return {"stateno": stateno, "status": "UNKNOWN_STATENO"}

    def execute_tactical_macro(self, macro_name: str) -> Dict[str, Any]:
        """Executes a pre-defined tactical combo macro or override."""
        valid_macros = {"punish_whiff", "anti_air_dp", "retreat_fireball", "crossup_mixup"}
        if macro_name in valid_macros:
            return {"status": "SUCCESS", "macro": macro_name, "message": f"Macro {macro_name} queued"}
        return {"status": "INVALID_MACRO", "macro": macro_name, "valid_options": list(valid_macros)}
