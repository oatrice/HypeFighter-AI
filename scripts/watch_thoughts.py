#!/usr/bin/env python3
"""Live monitor for FrameWhisper AI thoughts, speech, and spectator interactions."""
import json
import os
import sys
import time

THOUGHT_FILE = "/tmp/framewhisper_thought.json"
CHAT_FILE = "/tmp/framewhisper_chat.txt"

def main():
    print("👀 Watching FrameWhisper AI Live Thought Stream... (Press Ctrl+C to stop)\n")
    last_thought = ""

    while True:
        try:
            if os.path.exists(THOUGHT_FILE):
                with open(THOUGHT_FILE, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                if content and content != last_thought:
                    last_thought = content
                    d = json.loads(content)
                    
                    # Clear screen and print rich monitor board
                    sys.stdout.write("\033[2J\033[H")
                    sys.stdout.flush()
                    print("=" * 64)
                    print("🥊 FrameWhisper AI Live Thought & Communication Board")
                    print("=" * 64)
                    print(f"🎯 Stance:   \033[1;33m{d.get('stance', 'UNKNOWN')}\033[0m (Intent: {d.get('macro_intent')})")
                    print(f"🧠 Private:  \033[1;36m{d.get('internal_monologue', '')}\033[0m")
                    print(f"💬 In-Game:  \033[1;32m{d.get('public_chat', '')}\033[0m")
                    if d.get("audience_reply"):
                        print(f"📣 Chat Rep: \033[1;35m{d.get('audience_reply')}\033[0m")
                    print(f"💭 Bubble:   \033[1;37m{d.get('thought_bubble', '')}\033[0m")
                    print("=" * 64)
                    print("💡 พิมพ์แชทสดโค้ชได้ที่อีกหน้าต่าง: ./scripts/chat.sh สวนหลังเลยพี่")
                    sys.stdout.flush()
            else:
                sys.stdout.write("\r⏳ กำลังรอให้แมตช์เริ่มทำงาน (เปิด ./scripts/run_match.sh ในอีกหน้าต่าง)...")
                sys.stdout.flush()
        except Exception:
            pass
        time.sleep(0.3)

if __name__ == "__main__":
    main()
