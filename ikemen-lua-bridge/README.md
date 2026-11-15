# Ikemen GO Lua Telemetry & Combat Bridge

This module integrates directly into the **Ikemen GO** Lua runtime to stream 60 FPS real-time fighter telemetry and combat micro-events over UDP.

## Architecture

- **Sub-millisecond Latency:** Sends compact JSON packets to `127.0.0.1:9999` using `LuaSocket` (`udp:settimeout(0)` non-blocking).
- **Engine State Extraction:** Captures life, power, exact coordinates (`x, y`), facing direction, animation state numbers, movement types (`I` / `A` / `H`), control flags, and invulnerability.
- **Micro-Event Engine:** Emits structured frame-stamped combat logs:
  - `WHIFF_DETECTED`: Enemy swung and missed while AI remained safe.
  - `DAMAGE_TAKEN`: Damage received with exact delta.
  - `BLOCK_STRING`: Consecutive blockstun sequence.
- **Safe-Zone Detector:** Evaluates whether Player 1 is positioned in the `SAFE_BACK_ZONE` behind an opponent who is actively attacking in the opposite direction.
- **Timestamped for Shoutcaster:** Each packet and micro-event includes `frame` and `timestamp_ms` to synchronize with video highlight clips for the future AI shoutcaster pipeline.

## Installation into Ikemen GO

1. Place `bridge.lua` in your Ikemen GO `script/` folder.
2. In `script/main.lua` or inside your match loop hook:
   ```lua
   local bridge = require("script.bridge")
   bridge.init({ host = "127.0.0.1", port = 9999, debug = true })

   -- Inside your 60 FPS game tick / hook:
   bridge.tick(player(1), player(2))
   ```
