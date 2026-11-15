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

# Auto-provision distinct character identities if not yet present
if [ ! -d "./chars/framewhisper" ]; then
    echo "Configuring FrameWhisper AI character identity..."
    cp -r "./chars/kfm" "./chars/framewhisper"
    sed -i '' 's/name = "Kung Fu Man"/name = "FrameWhisper"/' "./chars/framewhisper/kfm.def"
    sed -i '' 's/displayname = "Kung Fu Man"/displayname = "FrameWhisper AI"/' "./chars/framewhisper/kfm.def"
    mv "./chars/framewhisper/kfm.def" "./chars/framewhisper/framewhisper.def"
fi

if [ ! -d "./chars/shadow_kfm" ]; then
    echo "Configuring Shadow Rival character identity..."
    cp -r "./chars/kfm" "./chars/shadow_kfm"
    sed -i '' 's/name = "Kung Fu Man"/name = "Shadow KFM"/' "./chars/shadow_kfm/kfm.def"
    sed -i '' 's/displayname = "Kung Fu Man"/displayname = "Shadow Rival"/' "./chars/shadow_kfm/kfm.def"
    sed -i '' 's/pal.defaults = 1,2,3,4/pal.defaults = 6,5,4,3/' "./chars/shadow_kfm/kfm.def"
    mv "./chars/shadow_kfm/kfm.def" "./chars/shadow_kfm/shadow_kfm.def"
fi

# Launch with custom fighter identities: FrameWhisper AI vs Shadow Rival
./I.K.E.M.E.N-Go.app/Contents/MacOS/Ikemen_GO_MacOSARM \
    -loadmotif \
    -p1 framewhisper \
    -p2 shadow_kfm \
    -p1.ai 8 \
    -p2.ai 8 \
    -p2.color 6 \
    -s stages/tournament.def \
    -rounds 2 \
    -time 99 \
    -windowed \
    -width 1280 \
    -height 720

echo "Match completed."
