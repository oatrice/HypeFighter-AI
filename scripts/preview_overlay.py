#!/usr/bin/env python3
"""Interactive browser preview server for FrameWhisper Overlay UI.

Launches:
1. Static HTTP file server for overlay-ui/ on http://localhost:8080
2. WebSocket server on ws://127.0.0.1:8765 (streaming live thoughts or simulation)
3. Opens default browser automatically for instant testing.
"""
import asyncio
import http.server
import json
import math
import os
import socketserver
import sys
import threading
import time
import webbrowser
from typing import Set

try:
    import websockets
except ImportError:
    print("Installing websockets...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "websockets"])
    import websockets

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OVERLAY_DIR = os.path.join(PROJECT_ROOT, "overlay-ui")
THOUGHT_FILE = "/tmp/framewhisper_thought.json"
HTTP_PORT = 8080
WS_PORT = 8765

CONNECTED_CLIENTS: Set[any] = set()


class QuietHTTPHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=OVERLAY_DIR, **kwargs)

    def log_message(self, format, *args):
        pass  # Suppress HTTP access noise


def start_http_server():
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("127.0.0.1", HTTP_PORT), QuietHTTPHandler) as httpd:
        httpd.serve_forever()


async def ws_handler(websocket):
    CONNECTED_CLIENTS.add(websocket)
    try:
        await websocket.wait_closed()
    finally:
        CONNECTED_CLIENTS.remove(websocket)


async def broadcast_thoughts():
    step = 0
    demo_stances = [
        ("WHIFF PUNISH", "เขาต่อยไปทางขวาเปิดหลังโล่ง สวนกลับตรงนี้เลย!", 50),
        ("ANTI-AIR", "ศัตรูกระโดดลอยมาแบบนี้ สอยร่วงด้วยหมัดหนัก (HP)!", 70),
        ("RUSHDOWN", "คู่ต่อสู้เลือดวิกฤต เดินหน้าบุกกดดันปิดฉาก!", 85),
        ("SUPER MOVE", "เกจพลังเต็ม 1000 ปลดปล่อยท่าไม้ตาย TripleKFPalm พลิกเกม!", 98),
        ("CORNER SPACING", "เกือบติดมุมฉาก ดึงระยะคุมเชิงรักษาระยะปลอดภัย", 60),
    ]

    last_thought_mtime = 0

    while True:
        await asyncio.sleep(0.05)  # 20Hz update
        if not CONNECTED_CLIENTS:
            continue

        step += 1
        t = step * 0.05

        # Check for real live match thoughts from agent runner
        if os.path.exists(THOUGHT_FILE):
            try:
                mtime = os.path.getmtime(THOUGHT_FILE)
                if mtime != last_thought_mtime:
                    last_thought_mtime = mtime
                    with open(THOUGHT_FILE, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    
                    payload = json.dumps({
                        "type": "AI_THOUGHT",
                        "stance": data.get("stance", "TACTICAL"),
                        "thought": data.get("internal_monologue", data.get("thought", "...")),
                        "pos_x": math.sin(t) * 80,
                        "pos_y": 0.0,
                    })
                    await asyncio.gather(*[client.send(payload) for client in CONNECTED_CLIENTS], return_exceptions=True)
                    continue
            except Exception:
                pass

        # Otherwise broadcast simulated demonstration stream
        stance, thought, hype = demo_stances[(step // 50) % len(demo_stances)]
        pos_x = math.sin(t * 1.5) * 120
        pos_y = -abs(math.sin(t * 3.0)) * 25

        payload_thought = json.dumps({
            "type": "AI_THOUGHT",
            "stance": stance,
            "thought": thought,
            "pos_x": pos_x,
            "pos_y": pos_y,
        })
        payload_hype = json.dumps({
            "type": "HYPE_UPDATE",
            "hype_percentage": min(100, max(10, hype + math.sin(t * 2) * 10)),
        })

        await asyncio.gather(
            *[client.send(payload_thought) for client in CONNECTED_CLIENTS],
            *[client.send(payload_hype) for client in CONNECTED_CLIENTS],
            return_exceptions=True
        )


async def main():
    print("============================================================")
    print("🥊 FrameWhisper Overlay UI Live Preview Server")
    print("============================================================")
    print(f"🌐 HTTP Web Server:      http://127.0.0.1:{HTTP_PORT}")
    print(f"⚡ WebSocket Live Stream: ws://127.0.0.1:{WS_PORT}")
    print("💡 กำลังเปิดเบราว์เซอร์เพื่อแสดงผล Overlay ตัวอย่าง...")
    print("💡 กด Ctrl+C เพื่อหยุดการทำงาน")
    print("============================================================")

    # Start HTTP in daemon thread
    t = threading.Thread(target=start_http_server, daemon=True)
    t.start()

    # Open Browser
    webbrowser.open(f"http://127.0.0.1:{HTTP_PORT}")

    # Start WebSocket Server
    async with websockets.serve(ws_handler, "127.0.0.1", WS_PORT):
        await broadcast_thoughts()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutdown overlay preview.")
