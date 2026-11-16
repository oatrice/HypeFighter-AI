#!/usr/bin/env bash
set -e

# Base directory
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

echo "============================================================"
echo "🥊 Starting FrameWhisper Match Spectator (Ikemen GO + AI)"
echo "============================================================"

# Clean previous temp files
rm -f /tmp/framewhisper_telemetry.json /tmp/framewhisper_action.json /tmp/framewhisper_thought.json /tmp/framewhisper_chat.txt

echo "💡 [Tip] ส่งแชทโค้ชสดระหว่างสู้: ./scripts/chat.sh สวนหลังเลยพี่"
echo "💡 [Tip] ดูความคิดสดในอีก Terminal: ./scripts/watch_thoughts.sh"

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

# 2. Launch AI Agent Core in background with unbuffered output (-u) tee'd to match_history.txt
MATCH_LOG="$PROJECT_ROOT/match_history.txt"
rm -f "$MATCH_LOG"
echo "Starting 60Hz AI Agent Core (Logging to $MATCH_LOG)..."
python3 -u -m agent_core.runner 2>&1 | tee "$MATCH_LOG" &
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
    sed -i '' 's/pal.defaults = 1,2,3,4/pal.defaults = 3,9,1,2/' "./chars/shadow_kfm/kfm.def"
    mv "./chars/shadow_kfm/kfm.def" "./chars/shadow_kfm/shadow_kfm.def"
fi

if [ ! -f "./stages/tournament.def" ]; then
    echo "Configuring FrameWhisper Tournament Arena stage..."
    cp "./stages/stage0.def" "./stages/tournament.def"
    sed -i '' 's/name = "Training Room"/name = "FrameWhisper Tournament Arena"/' "./stages/tournament.def"
    sed -i '' 's/displayname = "Training Room"/displayname = "FrameWhisper Arena (Auto-Cam)"/' "./stages/tournament.def"
    sed -i '' 's/boundhigh = -25/boundhigh = -800/' "./stages/tournament.def"
    sed -i '' 's/verticalfollow = .2/verticalfollow = 1.0\nzoomout = 0.70\nzoomin = 1.10\nzoomspeed = 12\ntensionhigh = 80/' "./stages/tournament.def"
fi

# Launch with custom fighter identities: FrameWhisper AI vs Shadow Rival (Red Palette 3)
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
    -windowed \
    -width 1280 \
    -height 720

echo "Match completed."

# Auto-analyze combat metrics immediately upon match completion
if [ -f "$MATCH_LOG" ] && [ -s "$MATCH_LOG" ]; then
    echo ""
    echo "============================================================"
    echo "📊 FrameWhisper Auto Post-Match Combat Efficiency Metrics"
    echo "============================================================"
    python3 "$PROJECT_ROOT/scripts/analyze_combat_metrics.py" "$MATCH_LOG"
fi
