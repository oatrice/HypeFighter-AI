import json
import os
import tempfile
import pytest
from scripts.analyze_combat_metrics import analyze_combat_metrics, record_match_benchmark
from scripts.benchmark_stats import generate_benchmark_summary


def test_analyze_combat_metrics_round_and_outcome(tmp_path):
    # Simulated log with P1 winning 2 rounds, P2 winning 1 round (Score 2-1 -> P1_WIN)
    log_content = """=== FrameWhisper AI Agent Core Running ===
[F:00100] P1:1000 (-70.0,0.0) (P:0) | P2:1000 (70.0,0.0) | Dist:140.0 | Action:Zoning [SPEC1]
[F:00200] P1:0800 (-50.0,0.0) (P:200) | P2:0000 (60.0,0.0) | Dist:110.0 | Action:ROUND_OVER [NONE]
🔔 [ROUND RESET]: Frame 250 - Both HP reset to 1000
[F:00300] P1:0000 (-60.0,0.0) (P:0) | P2:0400 (40.0,0.0) | Dist:100.0 | Action:ROUND_OVER [NONE]
🔔 [ROUND RESET]: Frame 350 - Both HP reset to 1000
[F:00400] P1:0500 (-30.0,0.0) (P:500) | P2:0000 (30.0,0.0) | Dist:60.0 | Action:ROUND_OVER [NONE]
"""
    log_file = tmp_path / "test_match.txt"
    log_file.write_text(log_content, encoding="utf-8")

    stats = analyze_combat_metrics(str(log_file))

    assert stats["p1_rounds"] == 2
    assert stats["p2_rounds"] == 1
    assert stats["match_result"] == "P1_WIN"
    assert stats["score"] == "2-1"
    assert "git_commit" in stats
    assert "git_branch" in stats


def test_record_match_benchmark(tmp_path):
    ledger_file = tmp_path / "match_ledger.jsonl"
    md_file = tmp_path / "BENCHMARKS.md"

    dummy_stats = {
        "timestamp": "2026-11-16T10:00:00+07:00",
        "git_commit": "abcdef1",
        "git_branch": "main",
        "git_message": "feat: test combat engine",
        "match_file": "match_history.txt",
        "match_result": "P1_WIN",
        "score": "2-1",
        "p1_rounds": 2,
        "p2_rounds": 1,
        "total_frames": 6000,
        "duration_sec": 100.0,
        "guard_success_rate": 88.5,
        "block_engagements": 30,
        "clean_hits_taken": 4,
        "damage_mitigated_hp": 800,
        "clean_damage_taken_hp": 300,
        "anti_air_count": 5,
        "special_hits": 8,
        "super_finisher": 1,
        "corner_pct": 10.0,
        "rushdown_pct": 20.0,
        "zoning_pct": 45.0,
    }

    record_match_benchmark(dummy_stats, ledger_path=str(ledger_file), md_path=str(md_file))

    assert ledger_file.exists()
    lines = ledger_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    recorded = json.loads(lines[0])
    assert recorded["git_commit"] == "abcdef1"
    assert recorded["match_result"] == "P1_WIN"

    assert md_file.exists()
    md_content = md_file.read_text(encoding="utf-8")
    assert "abcdef1" in md_content
    assert "WIN" in md_content
    assert "88.5%" in md_content


def test_benchmark_stats_summary(tmp_path):
    ledger_file = tmp_path / "match_ledger.jsonl"
    records = [
        {
            "timestamp": "2026-11-16T09:00:00+07:00",
            "git_commit": "commit1",
            "git_branch": "staging",
            "git_message": "initial commit",
            "match_result": "P1_LOSS",
            "score": "1-2",
            "guard_success_rate": 75.0,
            "damage_mitigated_hp": 500,
            "anti_air_count": 2,
            "super_finisher": 0,
        },
        {
            "timestamp": "2026-11-16T10:00:00+07:00",
            "git_commit": "commit2",
            "git_branch": "main",
            "git_message": "combat upgrade",
            "match_result": "P1_WIN",
            "score": "2-1",
            "guard_success_rate": 90.0,
            "damage_mitigated_hp": 1200,
            "anti_air_count": 6,
            "super_finisher": 1,
        },
    ]
    with open(ledger_file, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")

    summary = generate_benchmark_summary(str(ledger_file))
    assert summary["total_matches"] == 2
    assert summary["total_p1_wins"] == 1
    assert summary["overall_win_rate"] == 50.0
    assert len(summary["commits"]) == 2
    assert summary["commits"]["commit2"]["win_rate"] == 100.0
    assert summary["commits"]["commit1"]["win_rate"] == 0.0
