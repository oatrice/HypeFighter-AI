#!/usr/bin/env python3
"""Benchmark comparison CLI for FrameWhisper combat progress across git commits.

Aggregates:
- Win/Loss/Draw record per commit
- Guard success rate progression
- Damage mitigation efficiency
- Offensive confirms & Super finisher frequency
"""
import json
import os
import sys
from typing import Dict, Any, List


def generate_benchmark_summary(ledger_path: str = "benchmarks/match_ledger.jsonl") -> Dict[str, Any]:
    if not os.path.exists(ledger_path):
        return {
            "total_matches": 0,
            "total_p1_wins": 0,
            "overall_win_rate": 0.0,
            "commits": {},
        }

    records: List[Dict[str, Any]] = []
    with open(ledger_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except Exception:
                    pass

    total_matches = len(records)
    total_wins = sum(1 for r in records if r.get("match_result") == "P1_WIN")
    total_losses = sum(1 for r in records if r.get("match_result") == "P1_LOSS")
    total_draws = sum(1 for r in records if r.get("match_result") == "DRAW")
    overall_win_rate = (total_wins / total_matches * 100.0) if total_matches > 0 else 0.0

    commits_dict: Dict[str, Any] = {}
    for r in records:
        c = r.get("git_commit", "unknown")
        if c not in commits_dict:
            commits_dict[c] = {
                "commit": c,
                "branch": r.get("git_branch", "unknown"),
                "message": r.get("git_message", "unknown"),
                "matches": 0,
                "wins": 0,
                "losses": 0,
                "draws": 0,
                "guard_rates": [],
                "mitigated_hp": 0,
                "anti_air_count": 0,
                "super_finishers": 0,
            }

        st = commits_dict[c]
        st["matches"] += 1
        res = r.get("match_result", "DRAW")
        if res == "P1_WIN":
            st["wins"] += 1
        elif res == "P1_LOSS":
            st["losses"] += 1
        else:
            st["draws"] += 1

        if "guard_success_rate" in r:
            st["guard_rates"].append(r["guard_success_rate"])
        st["mitigated_hp"] += r.get("damage_mitigated_hp", 0)
        st["anti_air_count"] += r.get("anti_air_count", 0)
        st["super_finishers"] += r.get("super_finisher", 0)

    # Compute averages per commit
    for c, st in commits_dict.items():
        st["win_rate"] = (st["wins"] / st["matches"] * 100.0) if st["matches"] > 0 else 0.0
        st["avg_guard_rate"] = (
            sum(st["guard_rates"]) / len(st["guard_rates"]) if st["guard_rates"] else 0.0
        )

    return {
        "total_matches": total_matches,
        "total_p1_wins": total_wins,
        "total_p1_losses": total_losses,
        "total_draws": total_draws,
        "overall_win_rate": round(overall_win_rate, 1),
        "commits": commits_dict,
    }


def print_benchmark_table(summary: Dict[str, Any]) -> None:
    print("==========================================================================================")
    print("🥊 FrameWhisper Git Commit Combat Benchmark & Progress Tracker")
    print("==========================================================================================")
    print(
        f"Total Matches: {summary['total_matches']} | "
        f"P1 Wins: {summary.get('total_p1_wins', 0)} | "
        f"P1 Losses: {summary.get('total_p1_losses', 0)} | "
        f"Overall Win Rate: {summary['overall_win_rate']:.1f}%"
    )
    print("------------------------------------------------------------------------------------------")
    header = (
        f"{'Commit':<10} {'Branch':<12} {'Record (W-L-D)':<16} {'Win Rate':<10} "
        f"{'Avg Guard%':<12} {'Mitigated':<12} {'Anti-Air':<10} {'Super':<8}"
    )
    print(header)
    print("-" * len(header))

    for c, st in summary.get("commits", {}).items():
        record_str = f"{st['wins']}W - {st['losses']}L - {st['draws']}D"
        win_rate_str = f"{st['win_rate']:.1f}%"
        guard_str = f"{st['avg_guard_rate']:.1f}%"
        mit_str = f"{st['mitigated_hp']} HP"
        print(
            f"{c:<10} {st['branch']:<12} {record_str:<16} {win_rate_str:<10} "
            f"{guard_str:<12} {mit_str:<12} {st['anti_air_count']:<10} {st['super_finishers']:<8}"
        )
    print("==========================================================================================")


if __name__ == "__main__":
    ledger = sys.argv[1] if len(sys.argv) > 1 else "benchmarks/match_ledger.jsonl"
    data = generate_benchmark_summary(ledger)
    print_benchmark_table(data)
