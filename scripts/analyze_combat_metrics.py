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
- Round winners, match outcome (P1_WIN / P1_LOSS / DRAW), and git commit provenance
"""
import datetime
import json
import os
import re
import subprocess
import sys
from typing import Dict, Any, Optional


def get_git_info() -> Dict[str, str]:
    """Retrieve current git commit hash, branch, and commit subject."""
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], text=True, stderr=subprocess.DEVNULL
        ).strip()
    except Exception:
        commit = "unknown"

    try:
        branch = subprocess.check_output(
            ["git", "branch", "--show-current"], text=True, stderr=subprocess.DEVNULL
        ).strip()
        if not branch:
            # Detached HEAD or CI environment
            branch = subprocess.check_output(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"], text=True, stderr=subprocess.DEVNULL
            ).strip()
    except Exception:
        branch = "unknown"

    try:
        msg = subprocess.check_output(
            ["git", "log", "-1", "--pretty=%s"], text=True, stderr=subprocess.DEVNULL
        ).strip()
    except Exception:
        msg = "unknown"

    return {
        "git_commit": commit,
        "git_branch": branch,
        "git_message": msg,
    }


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
    okizeme_meaty_count = 0
    high_low_mixup_count = 0
    wakeup_reversal_count = 0
    air_to_air_count = 0
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

    # Round & Outcome Tracking
    p1_rounds = 0
    p2_rounds = 0
    in_round_over = False

    line_pattern = re.compile(
        r"\[F:(\d+)\]\s+P1:(\d+)\s+\(([-\d\.]+),([-\d\.]+)\)\s+\(P:(\d+)\)\s+\|\s+"
        r"P2:(\d+)\s+\(([-\d\.]+),([-\d\.]+)\)\s+\|\s+Dist:([-\d\.]+)\s+\|\s+Action:([^\s\|]+(?:\s+\[[^\]]+\])?)(?:\s+CMD:([^\s\|]+))?"
    )

    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        for raw_line in f:
            # Round reset boundary resets round-over latch
            if "ROUND RESET" in raw_line:
                in_round_over = False
                continue

            m = line_pattern.search(raw_line)
            if not m:
                continue
            frame, p1_hp, p1_x, p1_y, p1_p, p2_hp, p2_x, p2_y, dist, action, cmd = m.groups()
            frame = int(frame)
            p1_hp = int(p1_hp)
            p2_hp = int(p2_hp)
            p1_x = float(p1_x)
            dist = float(dist)
            action = action.strip()
            cmd = cmd.strip() if cmd else ""

            total_frames += 1

            # Round winner detection upon entering ROUND_OVER
            if "Action:ROUND_OVER" in raw_line or action.startswith("ROUND_OVER"):
                if not in_round_over:
                    in_round_over = True
                    if p1_hp == 0 and p2_hp > 0:
                        p2_rounds += 1
                    elif p2_hp == 0 and p1_hp > 0:
                        p1_rounds += 1
            else:
                if in_round_over and p1_hp > 0 and p2_hp > 0:
                    in_round_over = False

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
            if "OKIZEME_MEATY" in action:
                okizeme_meaty_count += 1
            if "HIGH_LOW_MIXUP" in action:
                high_low_mixup_count += 1
            if "WAKEUP_REVERSAL" in action or "WAKEUP_REVERSAL_SUPER" in action:
                wakeup_reversal_count += 1
            if "AIR_TO_AIR_ENGAGE" in action:
                air_to_air_count += 1

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

    # Determine overall match outcome
    if p1_rounds > p2_rounds:
        match_result = "P1_WIN"
    elif p2_rounds > p1_rounds:
        match_result = "P1_LOSS"
    else:
        match_result = "DRAW"

    total_guard_frames = sum(guard_counts.values())
    total_defensive_interactions = block_engagements + p1_clean_hits_taken
    block_success_rate = (
        (block_engagements / total_defensive_interactions * 100.0)
        if total_defensive_interactions > 0
        else 100.0
    )

    git_info = get_git_info()
    timestamp = datetime.datetime.now().astimezone().isoformat()
    duration_sec = round(total_frames / 60.0, 1)

    result_badge = {
        "P1_WIN": "🏆 P1 WIN",
        "P1_LOSS": "❌ P1 LOSS",
        "DRAW": "⚖️ DRAW",
    }[match_result]

    print("============================================================")
    print(f"📊 FrameWhisper Combat Metrics Report: {file_path}")
    print("============================================================")
    print(f"Outcome: {result_badge} (Score: {p1_rounds} - {p2_rounds})")
    print(f"Git Provenance: [{git_info['git_commit']}] ({git_info['git_branch']}) {git_info['git_message']}")
    print(f"Total Match Telemetry Frames:   {total_frames} frames ({duration_sec}s)")
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
    pct_guard = (total_guard_frames / total_frames * 100.0) if total_frames > 0 else 0.0
    print(f"Total Guarding Active Frames:    {total_guard_frames} frames ({pct_guard:.1f}% of match)")
    print()
    print("--- 💥 OFFENSIVE & SPECIAL MOVES ---")
    print(f"• Anti-Air Punishes (ANTI_AIR):  {anti_air_count} frames")
    print(f"• Special Hit-Confirms (QCF_x):  {special_hits} frames")
    print(f"• Super Punishes (Safe-Zone):    {super_punish} frames")
    print(f"• Super Hit-Confirms (Finisher): {super_finisher} frames")
    print(f"• Okizeme Meaty Pressure:        {okizeme_meaty_count} frames")
    print(f"• High-Low Mixups:               {high_low_mixup_count} frames")
    print(f"• Wakeup Reversals:              {wakeup_reversal_count} frames")
    print(f"• Air-to-Air Clashes:            {air_to_air_count} frames")
    print()
    print("--- 📐 SPATIAL & STANCE DISTRIBUTION ---")
    rush_pct = (rushdown_frames / total_frames * 100.0) if total_frames > 0 else 0.0
    ret_pct = (retreat_frames / total_frames * 100.0) if total_frames > 0 else 0.0
    zone_pct = (zoning_frames / total_frames * 100.0) if total_frames > 0 else 0.0
    corner_pct = (corner_frames / total_frames * 100.0) if total_frames > 0 else 0.0
    print(f"• Rushdown (Forward Pressure):   {rushdown_frames} frames ({rush_pct:.1f}%)")
    print(f"• Retreat (Spacing/Defense):     {retreat_frames} frames ({ret_pct:.1f}%)")
    print(f"• Zoning (Projectile Control):   {zoning_frames} frames ({zone_pct:.1f}%)")
    print(f"• Stage Corner Proximity:        {corner_frames} frames ({corner_pct:.1f}%)")
    print("============================================================")

    return {
        "timestamp": timestamp,
        "git_commit": git_info["git_commit"],
        "git_branch": git_info["git_branch"],
        "git_message": git_info["git_message"],
        "match_file": os.path.basename(file_path),
        "match_result": match_result,
        "score": f"{p1_rounds}-{p2_rounds}",
        "p1_rounds": p1_rounds,
        "p2_rounds": p2_rounds,
        "total_frames": total_frames,
        "duration_sec": duration_sec,
        "guard_success_rate": round(block_success_rate, 1),
        "block_engagements": block_engagements,
        "clean_hits_taken": p1_clean_hits_taken,
        "damage_mitigated_hp": p1_chip_or_block_damage,
        "clean_damage_taken_hp": p1_clean_damage_taken,
        "guard_counts": guard_counts,
        "special_hits": special_hits,
        "super_punish": super_punish,
        "super_finisher": super_finisher,
        "anti_air_count": anti_air_count,
        "okizeme_meaty_count": okizeme_meaty_count,
        "high_low_mixup_count": high_low_mixup_count,
        "wakeup_reversal_count": wakeup_reversal_count,
        "air_to_air_count": air_to_air_count,
        "corner_pct": round(corner_pct, 1),
        "rushdown_pct": round(rush_pct, 1),
        "zoning_pct": round(zone_pct, 1),
    }


def record_match_benchmark(
    stats: Dict[str, Any],
    ledger_path: str = "benchmarks/match_ledger.jsonl",
    md_path: str = "benchmarks/BENCHMARKS.md",
) -> None:
    """Record match stats into JSONL ledger and update Markdown dashboard table."""
    os.makedirs(os.path.dirname(ledger_path) or ".", exist_ok=True)
    os.makedirs(os.path.dirname(md_path) or ".", exist_ok=True)

    # 1. Append to JSON Lines ledger
    with open(ledger_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(stats, ensure_ascii=False) + "\n")

    # 2. Read all historical entries
    entries = []
    with open(ledger_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except Exception:
                    pass

    # 3. Compute Aggregates
    total_matches = len(entries)
    p1_wins = sum(1 for e in entries if e.get("match_result") == "P1_WIN")
    p1_losses = sum(1 for e in entries if e.get("match_result") == "P1_LOSS")
    draws = sum(1 for e in entries if e.get("match_result") == "DRAW")
    win_rate = (p1_wins / total_matches * 100.0) if total_matches > 0 else 0.0

    valid_guard_rates = [e.get("guard_success_rate", 0) for e in entries if "guard_success_rate" in e]
    avg_guard_rate = (sum(valid_guard_rates) / len(valid_guard_rates)) if valid_guard_rates else 0.0

    # 4. Generate Markdown Dashboard
    md_lines = [
        "# FrameWhisper Combat Benchmark & Match Ledger 🥊📈",
        "",
        "Tracking automated combat progress, win rates, and defensive efficiency per git commit.",
        "",
        "## 🏆 Performance Overview",
        "",
        f"- **Total Matches Tracked:** {total_matches}",
        f"- **P1 Overall Record:** {p1_wins}W - {p1_losses}L - {draws}D (**{win_rate:.1f}% Win Rate**)",
        f"- **Mean Guard Success Rate:** {avg_guard_rate:.1f}%",
        "",
        "## 📊 Match History Ledger",
        "",
        "| Date / Time | Commit | Branch | Outcome | Score | Guard % | Chip Saved | Clean Dmg | Anti-Air | Super | Commit Message |",
        "| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |",
    ]

    for e in reversed(entries):
        ts = e.get("timestamp", "")[:19].replace("T", " ")
        commit = e.get("git_commit", "unknown")
        branch = e.get("git_branch", "unknown")
        res = e.get("match_result", "DRAW")
        score = e.get("score", "0-0")
        guard_rate = f"{e.get('guard_success_rate', 0.0):.1f}%"
        mitigated = e.get("damage_mitigated_hp", 0)
        clean_dmg = e.get("clean_damage_taken_hp", 0)
        anti_air = e.get("anti_air_count", 0)
        super_fin = e.get("super_finisher", 0)
        msg = e.get("git_message", "")[:40]

        badge = {
            "P1_WIN": "🟢 WIN",
            "P1_LOSS": "🔴 LOSS",
            "DRAW": "⚪ DRAW",
        }.get(res, res)

        md_lines.append(
            f"| {ts} | `{commit}` | `{branch}` | **{badge}** | `{score}` | {guard_rate} | {mitigated} HP | {clean_dmg} HP | {anti_air} | {super_fin} | {msg} |"
        )

    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines) + "\n")

    print(f"\n📁 Benchmark recorded: {ledger_path} & {md_path}")


if __name__ == "__main__":
    record = False
    args = sys.argv[1:]
    if "--record" in args:
        record = True
        args.remove("--record")

    path = args[0] if len(args) > 0 else "match_history.txt"
    metrics = analyze_combat_metrics(path)

    if record:
        record_match_benchmark(metrics)
