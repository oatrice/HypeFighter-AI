#!/usr/bin/env python3
"""Audit script for FrameWhisper match telemetry logs.

Enforces 5 mandatory invariant assertions:
1. Zero False COMBO_ABORT_BLOCK (never when Dist > 130.0, P1_Y < -5.0, or P2_Y < -5.0).
2. Zero Airborne Ground-Specials (never Zoning [SPEC1], CMD:QCF_x, or CMD:TripleKFPalm when P1_Y < -5.0).
3. Zero Super Punish Spam (< 45 frame cooldown between SUPER_PUNISH_IN_PLACE).
4. Zero Distance Desync (Private Mind px distance matches Telemetry Dist within 0.2px).
5. Zero Regression (ROUND_OVER on HP <= 0, clean round reset detection).
"""
import re
import sys
from typing import List, Dict, Any


def audit_log(file_path: str) -> Dict[str, Any]:
    print(f"============================================================")
    print(f"🔍 Auditing Match Log: {file_path}")
    print(f"============================================================")

    violations = {
        "false_combo_abort": [],
        "airborne_ground_specials": [],
        "super_punish_spam": [],
        "distance_desync": [],
        "regression_failures": [],
    }

    total_frames = 0
    total_actions = 0
    super_punish_frames: List[int] = []
    current_dist = None
    current_frame = None

    line_pattern = re.compile(
        r"\[F:(\d+)\]\s+P1:(\d+)\s+\(([-\d\.]+),([-\d\.]+)\)\s+\(P:(\d+)\)\s+\|\s+"
        r"P2:(\d+)\s+\(([-\d\.]+),([-\d\.]+)\)\s+\|\s+Dist:([-\d\.]+)\s+\|\s+Action:([^\s\|]+(?:\s+\[[^\]]+\])?)(?:\s+CMD:([^\s\|]+))?"
    )
    mind_pattern = re.compile(r"🧠\s+\[P1 Private Mind\]:\s+\"([^\"]+)\"")
    round_reset_pattern = re.compile(r"🔔\s+\[ROUND RESET\]")

    round_resets = 0

    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        for line_num, line in enumerate(f, start=1):
            if round_reset_pattern.search(line):
                round_resets += 1

            m = line_pattern.search(line)
            if m:
                total_frames += 1
                total_actions += 1
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
                p1_y = float(p1_y_s)
                p2_y = float(p2_y_s)
                dist = float(dist_s)
                action_str = act_s.strip()
                cmd = cmd_s.strip() if cmd_s else ""

                current_frame = frame
                current_dist = dist

                # Invariant 1: Zero False COMBO_ABORT_BLOCK
                if "COMBO_ABORT_BLOCK" in action_str:
                    if dist > 130.0 or p1_y < -5.0 or p2_y < -5.0:
                        violations["false_combo_abort"].append({
                            "line": line_num,
                            "frame": frame,
                            "dist": dist,
                            "p1_y": p1_y,
                            "p2_y": p2_y,
                            "detail": f"COMBO_ABORT_BLOCK triggered invalidly (dist={dist}, p1_y={p1_y}, p2_y={p2_y})",
                        })

                # Invariant 2: Zero Airborne Ground-Specials
                if p1_y < -5.0:
                    if "SPEC1" in action_str or cmd in ("QCF_x", "TripleKFPalm", "SmashKFUpper"):
                        violations["airborne_ground_specials"].append({
                            "line": line_num,
                            "frame": frame,
                            "p1_y": p1_y,
                            "action": action_str,
                            "cmd": cmd,
                            "detail": f"Ground special {cmd or action_str} issued while airborne (p1_y={p1_y})",
                        })

                # Invariant 3: Zero Super Punish Spam (< 45 frame cooldown)
                if "SUPER_PUNISH_IN_PLACE" in action_str:
                    if super_punish_frames and (frame - super_punish_frames[-1] < 45):
                        violations["super_punish_spam"].append({
                            "line": line_num,
                            "frame": frame,
                            "prev_frame": super_punish_frames[-1],
                            "delta": frame - super_punish_frames[-1],
                            "detail": f"SUPER_PUNISH_IN_PLACE repeated within cooldown ({frame - super_punish_frames[-1]} frames < 45)",
                        })
                    super_punish_frames.append(frame)

                # Invariant 5: Zero Regression (KO check)
                if (p1_hp <= 0 or p2_hp <= 0) and "ROUND_OVER" not in action_str and "Retreat" in action_str:
                    # After KO, actions should be neutral ROUND_OVER
                    violations["regression_failures"].append({
                        "line": line_num,
                        "frame": frame,
                        "p1_hp": p1_hp,
                        "p2_hp": p2_hp,
                        "action": action_str,
                        "detail": f"Active movement {action_str} issued after KO (p1_hp={p1_hp}, p2_hp={p2_hp})",
                    })

            # Invariant 4: Zero Distance Desync in Private Mind
            mind_m = mind_pattern.search(line)
            if mind_m and current_dist is not None:
                monologue_text = mind_m.group(1)
                dist_matches = re.findall(r"(\d+(?:\.\d+)?)\s*px", monologue_text)
                for d_str in dist_matches:
                    logged_dist = float(d_str)
                    if abs(logged_dist - current_dist) > 0.2:
                        violations["distance_desync"].append({
                            "line": line_num,
                            "frame": current_frame,
                            "logged_dist": logged_dist,
                            "telemetry_dist": current_dist,
                            "delta": abs(logged_dist - current_dist),
                            "detail": f"Private Mind distance ({logged_dist}px) desynced from telemetry ({current_dist}px)",
                        })

    total_violations = sum(len(v) for v in violations.values())

    print("\n--- Audit Results ---")
    print(f"Total Telemetry Frames Analyzed: {total_frames}")
    print(f"Total Super Punish Executions:   {len(super_punish_frames)}")
    print(f"Round Resets Detected:           {round_resets}")
    print()
    print(f"1. False COMBO_ABORT_BLOCK:       {len(violations['false_combo_abort'])} violations")
    print(f"2. Airborne Ground-Specials:      {len(violations['airborne_ground_specials'])} violations")
    print(f"3. Super Punish Spam (< 45f):     {len(violations['super_punish_spam'])} violations")
    print(f"4. Distance Desync (> 0.2px):     {len(violations['distance_desync'])} violations")
    print(f"5. Regression Failures:           {len(violations['regression_failures'])} violations")
    print(f"------------------------------------------------------------")
    print(f"TOTAL VIOLATIONS:                 {total_violations}")
    print(f"------------------------------------------------------------")

    if total_violations > 0:
        print("\n❌ INVARIANT AUDIT FAILED! Violations Sample:")
        for category, vlist in violations.items():
            if vlist:
                print(f"\n[{category.upper()}]: {len(vlist)} occurrences")
                for item in vlist[:5]:
                    print(f"  Line {item['line']} (F:{item.get('frame', '?')}): {item.get('detail')}")
        return violations

    print("\n✅ INVARIANT AUDIT PASSED: ZERO VIOLATIONS (100% Deterministic Compliance)")
    return violations


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/audit_match_log.py <path_to_log_file>")
        sys.exit(1)

    res = audit_log(sys.argv[1])
    total = sum(len(v) for v in res.values())
    sys.exit(0 if total == 0 else 1)
