#!/usr/bin/env python3
"""Replay match_history4.txt through current MatchRunner to generate match_history5.txt."""
import sys
import re
import contextlib
from agent_core.runner import MatchRunner
from agent_core.models.telemetry import MatchSnapshot, PlayerState, Position


def replay_log(input_path: str, output_path: str):
    print(f"🔄 Replaying {input_path} through updated MatchRunner into {output_path}...")
    runner = MatchRunner()

    line_pattern = re.compile(
        r"\[F:(\d+)\]\s+P1:(\d+)\s+\(([-\d\.]+),([-\d\.]+)\)\s+\(P:(\d+)\)\s+\|\s+"
        r"P2:(\d+)\s+\(([-\d\.]+),([-\d\.]+)\)\s+\|\s+Dist:([-\d\.]+)\s+\|\s+Action:([^\s\|]+(?:\s+\[[^\]]+\])?)(?:\s+CMD:([^\s\|]+))?"
    )

    with open(input_path, "r", encoding="utf-8") as in_f, open(output_path, "w", encoding="utf-8") as out_f:
        with contextlib.redirect_stdout(out_f):
            for line in in_f:
                m = line_pattern.search(line)
                if not m:
                    continue
                (
                    frame_s,
                    p1_hp_s,
                    p1_x_s,
                    p1_y_s,
                    p1_p_s,
                    p2_hp_s,
                    p2_x_s,
                    p2_y_s,
                    dist_s,
                    act_s,
                    cmd_s,
                ) = m.groups()

                frame = int(frame_s)
                p1_hp = int(p1_hp_s)
                p2_hp = int(p2_hp_s)
                p1_x = float(p1_x_s)
                p1_y = float(p1_y_s)
                p1_p = int(p1_p_s)
                p2_x = float(p2_x_s)
                p2_y = float(p2_y_s)
                dist = float(dist_s)

                # Determine facing based on positions
                p1_facing = 1 if p2_x >= p1_x else -1
                p2_facing = -1 if p2_x >= p1_x else 1

                # If original action was hit-confirm or attacking, pass relevant movetypes
                p1_movetype = "A" if "HIT_CONFIRM" in act_s or "CMD:" in line else "I"
                p2_movetype = "H" if "HIT_CONFIRM" in act_s or "BLOCK" in act_s else "I"
                # If original action had COMBO_ABORT_BLOCK, original P2 was in blockstun
                p2_stateno = 150 if "COMBO_ABORT_BLOCK" in act_s else (5000 if "HIT_CONFIRM" in act_s else 0)

                # Safe back zone check
                safe_back = False
                if "PUNISH_IN_PLACE" in act_s:
                    safe_back = True

                p1 = PlayerState(
                    id=1,
                    life=p1_hp,
                    life_max=1000,
                    power=p1_p,
                    power_max=3000,
                    pos=Position(x=p1_x, y=p1_y),
                    facing=p1_facing,
                    stateno=200 if p1_movetype == "A" else 0,
                    movetype=p1_movetype,
                    ctrl=True,
                    invincible=False,
                    armor=False,
                )
                p2 = PlayerState(
                    id=2,
                    life=p2_hp,
                    life_max=1000,
                    power=0,
                    power_max=3000,
                    pos=Position(x=p2_x, y=p2_y),
                    facing=p2_facing,
                    stateno=p2_stateno,
                    movetype=p2_movetype,
                    ctrl=False,
                    invincible=False,
                    armor=False,
                )
                snap = MatchSnapshot(
                    frame=frame,
                    timestamp_ms=frame * 16,
                    distance=dist,
                    safe_back_zone=safe_back,
                    p1=p1,
                    p2=p2,
                )
                runner.on_snapshot(snap)

    print(f"✅ Replay complete! Saved to {output_path}")


if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else "match_history4.txt"
    dst = sys.argv[2] if len(sys.argv) > 2 else "match_history5.txt"
    replay_log(src, dst)
