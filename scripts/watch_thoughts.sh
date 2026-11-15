#!/usr/bin/env bash
# Helper script to watch live AI thoughts in real-time on macOS without external 'watch' tool

echo "👀 Watching FrameWhisper Live Thought Stream (Press Ctrl+C to stop)..."
while true; do
    if [ -f /tmp/framewhisper_thought.json ]; then
        python3 -c '
import json
try:
    with open("/tmp/framewhisper_thought.json") as f:
        d = json.load(f)
    print("\033[2J\033[H", end="")
    print("============================================================")
    print("💭 FrameWhisper AI Live Thoughts (Real-Time)")
    print("============================================================")
    print(f"🎯 Stance:   {d.get(\"stance\")} ({d.get(\"macro_intent\")})")
    print(f"🧠 Private:  {d.get(\"internal_monologue\")}")
    print(f"💬 Public:   {d.get(\"public_chat\")}")
    if d.get("audience_reply"):
        print(f"📣 Reply:    {d.get(\"audience_reply\")}")
    print(f"💭 Bubble:   {d.get(\"thought_bubble\")}")
    print("============================================================")
    print("💡 พิมพ์แชทสดได้ที่อีกหน้าต่าง: ./scripts/chat.sh สวนเลยพี่")
except Exception:
    pass
' 2>/dev/null
    else
        echo "⏳ กำลังรอให้เริ่มแมตช์ (เปิด ./scripts/run_match.sh ในอีกหน้าต่าง)..."
    fi
    sleep 0.4
done
