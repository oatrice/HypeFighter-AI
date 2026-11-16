#!/usr/bin/env python3
"""E2E Simulation & Telemetry Injection Harness for FrameWhisper.

Simulates 6,000+ frames of live match telemetry through MatchRunner:
- Round 1: Neutral footsies, close-range combos, opponent block reactions (ground & airborne)
- High-Meter Scenarios: P1 reaches 1000+ power, tests grounded Super Punish vs airborne inhibition and 45-frame cooldown
- Hit-confirm combos: Special Kung Fu Palm (QCF_x) and Super Finisher
- Round 1 KO -> Round 2 Reset -> Round 2 Conclusion
Outputs full runner telemetry log to the specified log file.
"""
import sys
import io
import contextlib
from agent_core.runner import MatchRunner
from agent_core.models.telemetry import MatchSnapshot, PlayerState, Position


def run_e2e_simulation(output_log_path: str):
    print(f"🎮 Starting E2E Telemetry Injection Simulation (6,000 frames)...")
    runner = MatchRunner()

    log_file = open(output_log_path, "w", encoding="utf-8")

    # Divert runner stdout to log_file
    with contextlib.redirect_stdout(log_file):
        p1_hp = 1000
        p2_hp = 1000
        p1_power = 0
        p2_power = 0
        p1_x = -60.0
        p1_y = 0.0
        p2_x = 60.0
        p2_y = 0.0
        p1_facing = 1
        p2_facing = -1
        round_num = 1

        for frame in range(1, 6001):
            timestamp_ms = frame * 16
            dist = abs(p2_x - p1_x)
            safe_zone = False
            p1_movetype = "I"
            p2_movetype = "I"
            p1_stateno = 0
            p2_stateno = 0

            # --- Phase A: Footsies & In-Combat (Frames 1 - 1000) ---
            if frame < 1000:
                p1_x = -40.0 + (frame % 30) * 0.5
                p2_x = 40.0 - (frame % 30) * 0.5
                p1_power = min(1500, p1_power + 1)
                p2_power = min(1500, p2_power + 1)

            # --- Phase B: Test COMBO_ABORT_BLOCK Strict Guards (Frames 1000 - 2000) ---
            elif frame < 2000:
                # Sub-scenario B1 (F:1050-1065): P1 attacks on ground, P2 guards on ground (Valid Blockstun)
                if 1050 <= frame <= 1065:
                    p1_x = -20.0
                    p1_y = 0.0
                    p2_x = 20.0
                    p2_y = 0.0
                    p1_movetype = "A" if frame == 1050 else "I"
                    p2_movetype = "H"
                    p2_stateno = 150  # Stand guard hit

                # Sub-scenario B2 (F:1200-1215): P1 attacks on ground, P2 guards in mid-air (P2_Y = -35.0) -> Must NOT COMBO_ABORT_BLOCK
                elif 1200 <= frame <= 1215:
                    p1_x = -20.0
                    p1_y = 0.0
                    p2_x = 20.0
                    p2_y = -35.0
                    p1_movetype = "A" if frame == 1200 else "I"
                    p2_movetype = "H"
                    p2_stateno = 152  # Air guard

                # Sub-scenario B3 (F:1350-1365): P1 is airborne (P1_Y = -30.0), P2 guards on ground -> Must NOT COMBO_ABORT_BLOCK
                elif 1350 <= frame <= 1365:
                    p1_x = -20.0
                    p1_y = -30.0
                    p2_x = 20.0
                    p2_y = 0.0
                    p1_movetype = "A" if frame == 1350 else "I"
                    p2_movetype = "H"
                    p2_stateno = 150

                # Sub-scenario B4 (F:1500-1515): Long distance (dist = 200px), P2 in guard -> Must NOT COMBO_ABORT_BLOCK
                elif 1500 <= frame <= 1515:
                    p1_x = -100.0
                    p1_y = 0.0
                    p2_x = 100.0
                    p2_y = 0.0
                    p1_movetype = "A" if frame == 1500 else "I"
                    p2_movetype = "H"
                    p2_stateno = 150
                else:
                    p1_x = -40.0
                    p1_y = 0.0
                    p2_x = 40.0
                    p2_y = 0.0

            # --- Phase C: High-Meter Super Punish Verification (Frames 2000 - 3200) ---
            elif frame < 3200:
                p1_power = 1200  # P1 has > 1000 power
                # Sub-scenario C1 (F:2100-2130): Enemy exposes back on ground -> Super Punish triggered at F:2100
                if 2100 <= frame <= 2130:
                    p1_x = -30.0
                    p1_y = 0.0
                    p2_x = 30.0
                    p2_y = 0.0
                    p2_facing = 1  # P2 faces away from P1 (exposing back)
                    p2_movetype = "A"  # P2 attacking away
                    safe_zone = True

                # Sub-scenario C2 (F:2131-2170): Next frame after cooldown expires at F:2146
                elif 2150 <= frame <= 2160:
                    p1_x = -30.0
                    p1_y = 0.0
                    p2_x = 30.0
                    p2_y = 0.0
                    p2_facing = 1
                    p2_movetype = "A"
                    safe_zone = True

                # Sub-scenario C3 (F:2300-2330): Airborne P1 (y = -40.0) with P >= 1000 in safe back zone -> Must NOT super punish
                elif 2300 <= frame <= 2330:
                    p1_x = -30.0
                    p1_y = -40.0
                    p2_x = 30.0
                    p2_y = 0.0
                    p2_facing = 1
                    p2_movetype = "A"
                    safe_zone = True
                else:
                    p1_x = -40.0
                    p1_y = 0.0
                    p2_x = 40.0
                    p2_y = 0.0
                    p2_facing = -1

            # --- Phase D: Hit-Confirm Specials & KO (Frames 3200 - 3600) ---
            elif frame < 3600:
                # P1 hits P2 with normal attack
                if 3300 <= frame <= 3310:
                    p1_x = -20.0
                    p1_y = 0.0
                    p2_x = 20.0
                    p2_y = 0.0
                    p1_movetype = "A" if frame == 3300 else "I"
                    p2_movetype = "H"
                    p2_stateno = 5000  # Hitstun
                    p2_hp = max(0, p2_hp - 100)
                elif frame >= 3500:
                    p2_hp = 0  # Round 1 KO!

            # --- Phase E: Round Reset Detection (Frames 3601 - 3700) ---
            elif frame == 3650:
                # Engine resets HP to 1000 for Round 2!
                p1_hp = 1000
                p2_hp = 1000
                p1_power = 500
                p2_power = 500
                p1_x = -80.0
                p1_y = 0.0
                p2_x = 80.0
                p2_y = 0.0
                round_num = 2

            # --- Phase F: Round 2 Combat & Clean Finisher (Frames 3701 - 6000) ---
            else:
                p1_x = -35.0 + (frame % 40) * 0.4
                p2_x = 35.0 - (frame % 40) * 0.4
                p1_power = min(2000, p1_power + 2)
                p2_power = min(2000, p2_power + 1)
                # F:5000: P1 executes anti-air against jump-in
                if 5000 <= frame <= 5010:
                    p2_y = -45.0
                    p2_movetype = "A"
                else:
                    p2_y = 0.0
                # F:5800: Round 2 KO
                if frame >= 5800:
                    p2_hp = 0

            p1 = PlayerState(
                id=1,
                life=p1_hp,
                life_max=1000,
                power=p1_power,
                power_max=3000,
                pos=Position(x=p1_x, y=p1_y),
                facing=p1_facing,
                stateno=p1_stateno,
                movetype=p1_movetype,
                ctrl=True,
                invincible=False,
                armor=False,
            )
            p2 = PlayerState(
                id=2,
                life=p2_hp,
                life_max=1000,
                power=p2_power,
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
                timestamp_ms=timestamp_ms,
                distance=dist,
                safe_back_zone=safe_zone,
                p1=p1,
                p2=p2,
                meta={"round": round_num},
            )
            runner.on_snapshot(snap)

    log_file.close()
    print(f"✅ Simulation complete! Log saved to {output_log_path}")


if __name__ == "__main__":
    out_path = sys.argv[1] if len(sys.argv) > 1 else "match_history_e2e_sim.log"
    run_e2e_simulation(out_path)
