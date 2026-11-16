#!/usr/bin/env python3
"""Zero-dependency interactive browser preview server for FrameWhisper Overlay UI.

Launches:
1. Static HTTP file server for overlay-ui/ on http://localhost:8080
2. Pure-Python RFC 6455 WebSocket server on ws://127.0.0.1:8765 (zero pip/uv packages required!)
3. Automatically opens default browser for instant testing.
"""
import asyncio
import base64
import hashlib
import http.server
import json
import math
import os
import socketserver
import struct
import threading
import time
import webbrowser
from typing import Set

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OVERLAY_DIR = os.path.join(PROJECT_ROOT, "overlay-ui")
THOUGHT_FILE = "/tmp/framewhisper_thought.json"
HTTP_PORT = 8080
WS_PORT = 8765

CONNECTED_WRITERS: Set[asyncio.StreamWriter] = set()


class QuietHTTPHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=OVERLAY_DIR, **kwargs)

    def log_message(self, format, *args):
        pass  # Suppress HTTP access noise


def start_http_server():
    socketserver.TCPServer.allow_reuse_address = True
    try:
        with socketserver.TCPServer(("127.0.0.1", HTTP_PORT), QuietHTTPHandler) as httpd:
            httpd.serve_forever()
    except Exception:
        pass


def make_ws_handshake_response(key: str) -> bytes:
    GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
    sha1 = hashlib.sha1((key.strip() + GUID).encode("utf-8")).digest()
    accept = base64.b64encode(sha1).decode("utf-8")
    return (
        f"HTTP/1.1 101 Switching Protocols\r\n"
        f"Upgrade: websocket\r\n"
        f"Connection: Upgrade\r\n"
        f"Sec-WebSocket-Accept: {accept}\r\n\r\n"
    ).encode("utf-8")


def encode_ws_frame(message: str) -> bytes:
    payload = message.encode("utf-8")
    length = len(payload)
    if length <= 125:
        header = bytes([0x81, length])
    elif length <= 65535:
        header = struct.pack("!BBH", 0x81, 126, length)
    else:
        header = struct.pack("!BBQ", 0x81, 127, length)
    return header + payload


async def ws_client_handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    headers = {}
    try:
        # Read HTTP upgrade request headers
        while True:
            line = await reader.readline()
            if not line or line == b"\r\n":
                break
            line_str = line.decode("utf-8", errors="ignore")
            if ":" in line_str:
                k, v = line_str.split(":", 1)
                headers[k.strip().lower()] = v.strip()

        key = headers.get("sec-websocket-key")
        if not key:
            writer.close()
            return

        # Complete WebSocket RFC 6455 Handshake
        response = make_ws_handshake_response(key)
        writer.write(response)
        await writer.drain()

        CONNECTED_WRITERS.add(writer)

        # Keep connection alive until client disconnects
        while True:
            data = await reader.read(1024)
            if not data:
                break
    except Exception:
        pass
    finally:
        CONNECTED_WRITERS.discard(writer)
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass


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
        if not CONNECTED_WRITERS:
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
                    frame_bytes = encode_ws_frame(payload)
                    dead = set()
                    for w in list(CONNECTED_WRITERS):
                        try:
                            w.write(frame_bytes)
                            await w.drain()
                        except Exception:
                            dead.add(w)
                    for d in dead:
                        CONNECTED_WRITERS.discard(d)
                    continue
            except Exception:
                pass

        # Otherwise broadcast simulated demonstration stream
        stance, thought, hype = demo_stances[(step // 50) % len(demo_stances)]
        pos_x = math.sin(t * 1.5) * 120
        pos_y = -abs(math.sin(t * 3.0)) * 25
        p2_pos_x = 100 + math.sin(t * 1.2) * 60

        payload_thought = json.dumps({
            "type": "AI_THOUGHT",
            "stance": stance,
            "thought": thought,
            "pos_x": pos_x,
            "pos_y": pos_y,
            "p2_pos_x": p2_pos_x,
        })
        payload_hype = json.dumps({
            "type": "HYPE_UPDATE",
            "hype_percentage": min(100, max(10, hype + math.sin(t * 2) * 10)),
        })

        frame1 = encode_ws_frame(payload_thought)
        frame2 = encode_ws_frame(payload_hype)

        dead = set()
        for w in list(CONNECTED_WRITERS):
            try:
                w.write(frame1)
                w.write(frame2)
                await w.drain()
            except Exception:
                dead.add(w)
        for d in dead:
            CONNECTED_WRITERS.discard(d)


async def main():
    print("============================================================", flush=True)
    print("🥊 FrameWhisper Overlay UI Live Preview Server", flush=True)
    print("============================================================", flush=True)
    print(f"🌐 HTTP Web Server:      http://127.0.0.1:{HTTP_PORT}", flush=True)
    print(f"⚡ WebSocket Live Stream: ws://127.0.0.1:{WS_PORT}", flush=True)
    print("✨ Pure Standard-Library WebSocket (No external packages needed!)", flush=True)
    print("💡 กำลังเปิดเบราว์เซอร์เพื่อแสดงผล Overlay ตัวอย่าง...", flush=True)
    print("💡 กด Ctrl+C เพื่อหยุดการทำงาน", flush=True)
    print("============================================================", flush=True)

    # Start HTTP in daemon thread
    t = threading.Thread(target=start_http_server, daemon=True)
    t.start()

    # Open Browser asynchronously
    if os.environ.get("NO_BROWSER") != "1":
        try:
            threading.Thread(target=lambda: webbrowser.open(f"http://127.0.0.1:{HTTP_PORT}"), daemon=True).start()
        except Exception:
            pass

    # Start Pure-Python WebSocket Server
    try:
        server = await asyncio.start_server(ws_client_handler, "127.0.0.1", WS_PORT, reuse_address=True)
    except OSError as e:
        if e.errno == 48:
            print(f"⚠️ Port {WS_PORT} is already in use by another instance. Using existing preview server.", flush=True)
            return
        raise e
    async with server:
        await broadcast_thoughts()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutdown overlay preview.")
