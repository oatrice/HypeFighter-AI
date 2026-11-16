#!/usr/bin/env bash
set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

echo "=========================================================="
echo "🎯 FrameWhisper ADLC Stage 4: Automated Evaluation Harness"
echo "=========================================================="

echo -e "\n[1/2] Running 100% Deterministic Unit & Integration Test Matrix..."
pytest agent-core/tests/ -v --maxfail=1

echo -e "\n[2/2] Running 60Hz Latency Budget & Microsecond Benchmark..."
PYTHONPATH=agent-core/src python3 -c "
import time
from agent_core.controller.safety_gatekeeper import SafetyGatekeeper
from agent_core.controller.combo_engine import ComboEngine
from agent_core.models.telemetry import MatchSnapshot, PlayerState, Position

gatekeeper = SafetyGatekeeper()
combo_engine = ComboEngine()
dummy_snap = MatchSnapshot(
    frame=1, timestamp_ms=1000, distance=60.0, safe_back_zone=False,
    p1=PlayerState(id=1, life=1000, life_max=1000, power=1500, power_max=3000, pos=Position(x=-30, y=0), facing=1, stateno=0, movetype='I', ctrl=True, invincible=False, armor=False),
    p2=PlayerState(id=2, life=1000, life_max=1000, power=0, power_max=3000, pos=Position(x=30, y=0), facing=-1, stateno=200, movetype='A', ctrl=False, invincible=False, armor=False)
)

t0 = time.perf_counter()
for _ in range(6000):
    gatekeeper.evaluate(dummy_snap)
    combo_engine.update(dummy_snap)
elapsed = time.perf_counter() - t0
avg_us = (elapsed / 6000) * 1_000_000
print(f'Average Evaluation Time: {avg_us:.2f} microseconds per frame (Target: < 800 us)')
assert avg_us < 800.0, 'Performance regression: Exceeded latency budget!'
print('Deterministic Performance Gate: PASSED')
"

echo -e "\n=========================================================="
echo "✅ ADLC Evaluation Harness: ALL GATES PASSED (100% Pass Rate)"
echo "=========================================================="
