#!/usr/bin/env bash
set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

NUM_MATCHES="${1:-5}"
SPEED="${2:-30}"

echo "============================================================"
echo "🥊 Running FrameWhisper Fast-Forward Benchmark Batch"
echo "Matches: $NUM_MATCHES | Simulation Speed: ${SPEED}x"
echo "============================================================"

# Prepare Python environment
cd "$PROJECT_ROOT/agent-core"
if [ ! -d ".venv" ]; then
    uv venv
    source .venv/bin/activate
    uv pip install -e ".[dev]"
else
    source .venv/bin/activate
fi

for ((i=1; i<=NUM_MATCHES; i++)); do
    echo ""
    echo "------------------------------------------------------------"
    echo "▶️ [Match $i / $NUM_MATCHES] Starting match..."
    echo "------------------------------------------------------------"

    MATCH_LOG="$PROJECT_ROOT/match_history_batch_${i}.txt"
    rm -f "$MATCH_LOG" /tmp/framewhisper_telemetry.json /tmp/framewhisper_action.json /tmp/framewhisper_thought.json

    # Launch AI Agent Core (direct redirect ensures $! is the python process)
    python3 -u -m agent_core.runner > "$MATCH_LOG" 2>&1 &
    AGENT_PID=$!

    sleep 1

    # Launch Ikemen GO in fast-forward mode
    cd "$PROJECT_ROOT/engine"
    ./I.K.E.M.E.N-Go.app/Contents/MacOS/Ikemen_GO_MacOSARM \
        -loadmotif \
        -p1 framewhisper \
        -p2 shadow_kfm \
        -p1.ai 8 \
        -p2.ai 8 \
        -p2.color 3 \
        -s stages/tournament.def \
        -rounds 2 \
        -time 99 \
        -nosound \
        -speedtest "$SPEED" \
        -windowed \
        -width 640 \
        -height 360 > /dev/null 2>&1 || true

    # Stop AI agent core
    kill -9 $AGENT_PID 2>/dev/null || true
    wait $AGENT_PID 2>/dev/null || true

    # Record match metrics into benchmark ledger
    cd "$PROJECT_ROOT"
    if [ -f "$MATCH_LOG" ] && [ -s "$MATCH_LOG" ]; then
        python3 "$PROJECT_ROOT/scripts/analyze_combat_metrics.py" "$MATCH_LOG" --record
    fi
done

echo ""
echo "============================================================"
echo "✅ Batch Benchmark Completed: $NUM_MATCHES matches recorded"
echo "============================================================"
python3 "$PROJECT_ROOT/scripts/benchmark_stats.py"
