import time
import pytest
from agent_core.controller.safety_gatekeeper import SafetyGatekeeper
from agent_core.models.telemetry import (
    EgoCentricIntent,
    MatchSnapshot,
    PlayerState,
    Position,
)


def test_safety_gatekeeper_latency_budget_and_burst_stress():
    """Stress test: 2,500 continuous evaluation frames ensuring < 100 microseconds/frame."""
    gatekeeper = SafetyGatekeeper()

    p1 = PlayerState(id=1, life=1000, power=500, pos=Position(x=0.0, y=0.0), facing=1, movetype="I")
    p2 = PlayerState(id=2, life=900, power=200, pos=Position(x=70.0, y=0.0), facing=-1, movetype="A", stateno=220)

    num_frames = 2500
    latencies = []

    for f in range(num_frames):
        snap = MatchSnapshot(
            frame=f,
            timestamp_ms=f * 16,
            distance=70.0,
            safe_back_zone=False,
            p1=p1,
            p2=p2,
        )
        t0 = time.perf_counter()
        action = gatekeeper.evaluate(snap, desired_intent=EgoCentricIntent.RETREAT)
        t1 = time.perf_counter()
        latencies.append((t1 - t0) * 1e6)  # microseconds
        assert action is not None

    avg_latency_us = sum(latencies) / len(latencies)
    p99_latency_us = sorted(latencies)[int(0.99 * len(latencies))]

    print(f"\nBurst Stress: Avg = {avg_latency_us:.2f} us, P99 = {p99_latency_us:.2f} us")

    # Invariants for 60Hz loop (Budget is 16,666 us; safety gatekeeper target is < 100 us)
    assert avg_latency_us < 50.0, f"Average latency {avg_latency_us:.2f} us exceeds 50 us limit"
    assert p99_latency_us < 150.0, f"P99 latency {p99_latency_us:.2f} us exceeds 150 us limit"
