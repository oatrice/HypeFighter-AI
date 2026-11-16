#!/usr/bin/env python3
"""Combat metrics and performance analyzer for FrameWhisper match telemetry logs.

Computes:
- Total defensive engagements & block success rate
- Guard breakdown (Low, High, Air, Combo Abort)
- Clean hits taken vs chip/blocked damage
- Anti-Air reaction punishes
- Special hit-confirms (QCF_x) & Super moves (TripleKFPalm)
- Rushdown & forward commitment frames
- Stage edge & corner positioning
"""
import sys
import re
from typing import Dict, Any


def analyze_combat_metrics(file_path: str) -> Dict[str, Any]:
    total_frames = 0
    guard_counts = {
        "INSTANT_BLOCK_LOW": 0,
        "INSTANT_BLOCK_HIGH": 0,
        "INSTANT_BLOCK_AIR": 0,
        "COMBO_ABORT_BLOCK": 0,
    }
    anti_air_count = 0
    special_hits = 0
    super_punish = 0
    super_finisher = 0
    rushdown_frames = 0
    retreat_frames = 0
    zoning_frames = 0
    corner_frames = 0

    prev_p1_hp = None
    prev_action = None
    p1_clean_hits_taken = 0
    p1_chip_or_block_damage = 0
    p1_clean_damage_taken = 0

    block_engagements = 0
    in_block = False

    line_pattern = re.compile(
        r"\[F:(\d+)\]\s+P1:(\d+)\s+\(([-\d\.]+),([-\d\.]+)\)\s+\(P:(\d+)\)\s+\|\s+"
        r"P2:(\d+)\s+\(([-\d\.]+),([-\d\.]+)\)\s+\|\s+Dist:([-\d\.]+)\s+\|\s+Action:([^\s\|]+(?:\s+\[[^\]]+\])?)(?:\s+CMD:([^\s\|]+))?"
    )

    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            m = line_pattern.search(line)
            if not m:
                continue
            frame, p1_hp, p1_x, p1_y, p1_p, p2_hp, p2_x, p2_y, dist, action, cmd = m.groups()
            frame = int(frame)
            p1_hp = int(p1_hp)
            p1_x = float(p1_x)
            dist = float(dist)
            action = action.strip()
            cmd = cmd.strip() if cmd else ""

            total_frames += 1

            # Corner tracking
            if abs(p1_x) >= 140.0:
                corner_frames += 1

            # Action macro intents
            if "Rushdown" in action:
                rushdown_frames += 1
            elif "Retreat" in action:
                retreat_frames += 1
            elif "Zoning" in action:
                zoning_frames += 1

            # Guard tracking
            is_guard = any(g in action for g in guard_counts)
            if is_guard and not in_block:
                block_engagements += 1
                in_block = True
            elif not is_guard:
                in_block = False

            for g in guard_counts:
                if g in action:
                    guard_counts[g] += 1

            if "ANTI_AIR" in action:
                anti_air_count += 1
            if "SPECIAL_HIT_CONFIRM" in action or cmd == "QCF_x":
                special_hits += 1
            if "SUPER_PUNISH_IN_PLACE" in action:
                super_punish += 1
            if "SUPER_HIT_CONFIRM" in action or cmd == "TripleKFPalm":
                super_finisher += 1

            # Damage tracking
            if prev_p1_hp is not None and prev_action:
                if p1_hp < prev_p1_hp:
                    dmg = prev_p1_hp - p1_hp
                    if any(g in prev_action for g in guard_counts):
                        p1_chip_or_block_damage += dmg
                    else:
                        p1_clean_damage_taken += dmg
                        p1_clean_hits_taken += 1

            prev_p1_hp = p1_hp
            prev_action = action

    total_guard_frames = sum(guard_counts.values())
    total_defensive_interactions = block_engagements + p1_clean_hits_taken
    block_success_rate = (
        (block_engagements / total_defensive_interactions * 100.0)
        if total_defensive_interactions > 0
        else 100.0
    )

    print("============================================================")
    print(f"📊 FrameWhisper Combat Metrics Report: {file_path}")
    print("============================================================")
    print(f"Total Match Telemetry Frames:   {total_frames} frames ({total_frames/60.0:.1f}s)")
    print()
    print("--- 🛡️ DEFENSIVE EFFICIENCY ---")
    print(f"Defensive Engagements (Blocked): {block_engagements} times")
    print(f"Clean Hits Taken (Guard Broken): {p1_clean_hits_taken} times")
    print(f"🛡️ Guard Success Rate:           {block_success_rate:.1f}%")
    print(f"Damage Mitigated (Chip Damage):  {p1_chip_or_block_damage} HP")
    print(f"Unmitigated Damage Taken:        {p1_clean_damage_taken} HP")
    print()
    print("--- 🥋 GUARD ACTIONS BREAKDOWN ---")
    print(f"• INSTANT_BLOCK_LOW:             {guard_counts['INSTANT_BLOCK_LOW']} frames")
    print(f"• INSTANT_BLOCK_HIGH:            {guard_counts['INSTANT_BLOCK_HIGH']} frames")
    print(f"• INSTANT_BLOCK_AIR:             {guard_counts['INSTANT_BLOCK_AIR']} frames")
    print(f"• COMBO_ABORT_BLOCK:             {guard_counts['COMBO_ABORT_BLOCK']} frames")
    print(f"Total Guarding Active Frames:    {total_guard_frames} frames ({total_guard_frames/total_frames*100.0:.1f}% of match)")
    print()
    print("--- 💥 OFFENSIVE & SPECIAL MOVES ---")
    print(f"• Anti-Air Punishes (ANTI_AIR):  {anti_air_count} frames")
    print(f"• Special Hit-Confirms (QCF_x):  {special_hits} frames")
    print(f"• Super Punishes (Safe-Zone):    {super_punish} frames")
    print(f"• Super Hit-Confirms (Finisher): {super_finisher} frames")
    print()
    print("--- 📐 SPATIAL & STANCE DISTRIBUTION ---")
    print(f"• Rushdown (Forward Pressure):   {rushdown_frames} frames ({rushdown_frames/total_frames*100.0:.1f}%)")
    print(f"• Retreat (Spacing/Defense):     {retreat_frames} frames ({retreat_frames/total_frames*100.0:.1f}%)")
    print(f"• Zoning (Projectile Control):   {zoning_frames} frames ({zoning_frames/total_frames*100.0:.1f}%)")
    print(f"• Stage Corner Proximity:        {corner_frames} frames ({corner_frames/total_frames*100.0:.1f}%)")
    print("============================================================")

    return {
        "total_frames": total_frames,
        "block_success_rate": block_success_rate,
        "block_engagements": block_engagements,
        "p1_clean_hits_taken": p1_clean_hits_taken,
        "guard_counts": guard_counts,
        "special_hits": special_hits,
        "super_punish": super_punish,
        "super_finisher": super_finisher,
        "anti_air_count": anti_air_count,
    }


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "match_history6.txt"
    analyze_combat_metrics(path)
