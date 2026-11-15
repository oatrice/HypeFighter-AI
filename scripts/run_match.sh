#!/usr/bin/env bash
set -e

# Base directory
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

echo "============================================================"
echo "🥊 Starting FrameWhisper Match Spectator (Ikemen GO + AI)"
echo "============================================================"

# Clean previous temp files
rm -f /tmp/framewhisper_telemetry.json /tmp/framewhisper_action.json

# 1. Activate Python Environment
cd "$PROJECT_ROOT/agent-core"
if [ ! -d ".venv" ]; then
    echo "Creating Python virtualenv..."
    uv venv
    source .venv/bin/activate
    uv pip install -e ".[dev]"
else
    source .venv/bin/activate
fi

# 2. Launch AI Agent Core in background with unbuffered output (-u)
echo "Starting 60Hz AI Agent Core..."
python3 -u -m agent_core.runner &
AGENT_PID=$!

# Trap signals to ensure background python process is killed on exit
cleanup() {
    echo ""
    echo "Shutting down FrameWhisper..."
    kill $AGENT_PID 2>/dev/null || true
    wait $AGENT_PID 2>/dev/null || true
    echo "Clean shutdown complete."
}
trap cleanup EXIT INT TERM

# Wait a brief moment for UDP sockets to bind
sleep 1

# 3. Launch Ikemen GO Engine (Watch Mode with Dynamic Tournament Camera)
echo "Launching Ikemen GO Engine in Watch Mode..."
cd "$PROJECT_ROOT/engine"

# Ensure quarantine flag is removed on macOS
xattr -d com.apple.quarantine "./I.K.E.M.E.N-Go.app" 2>/dev/null || true
chmod +x "./I.K.E.M.E.N-Go.app/Contents/MacOS/Ikemen_GO_MacOSARM" 2>/dev/null || true

# Launch with -loadmotif to enter match immediately
./I.K.E.M.E.N-Go.app/Contents/MacOS/Ikemen_GO_MacOSARM \
    -loadmotif \
    -p1 kfm \
    -p2 kfm \
    -p1.ai 8 \
    -p2.ai 8 \
    -s stages/tournament.def \
    -rounds 2 \
    -time 99 \
    -windowed \
    -width 1280 \
    -height 720

echo "Match completed."
