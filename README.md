# FrameWhisper (CornerCoach) 🥊🤖

[![Version](https://img.shields.io/badge/version-0.2.0-blue.svg)](CHANGELOG.md)
[![Platform](https://img.shields.io/badge/platform-macOS%20%7C%20Windows-lightgrey.svg)]()
[![Engine](https://img.shields.io/badge/engine-Ikemen%20GO-red.svg)](https://github.com/ikemen-engine/Ikemen-GO)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

Real-Time AI Fighting Game Agent & Interactive Crowd Overlay for **Ikemen GO** (open-source Go + Lua evolution of M.U.G.E.N).

---

## 🌟 Key Features

1. **Sub-Millisecond Engine Telemetry & Combat Micro-Events (`ikemen-lua-bridge/`):**
   - 60 FPS non-blocking UDP stream from Ikemen GO's Lua runtime.
   - Extracts character life, power meter, positions (`x, y`), facing direction (`1` = right, `-1` = left), animation states (`stateno`), movement types (`I` / `A` / `H`), control flags, and invulnerability states.
   - Micro-event engine emitting structured events: `WHIFF_DETECTED`, `BLOCK_STRING`, `PROJECTILE_ACTIVE`, and `DAMAGE_TAKEN` with millisecond timestamps.

2. **2-Tier Hierarchical AI Architecture (`agent-core/`):**
   - **Tier 1 (60Hz Reactive Safety Gatekeeper):** Runs locally with zero LLM/network latency. Enforces spatial hitbox guardrails (e.g. locks forward movement when behind an opponent attacking in the opposite direction and executes `PUNISH_IN_PLACE`). Translates high-level ego-centric intents (`Hold_Safe_Punish`, `Retreat`, `Zoning`, `Rushdown`, `Cross_Up`) into player inputs without hardcoding left/right.
   - **Tier 2 (2–5Hz Tactical SLM/LLM Brain):** Ingests sliding-window combat summaries and crowd chat advice to adjust macro-intents, stances, and comic thought bubbles.

3. **Interactive Live Overlay (`overlay-ui/`):**
   - Floating thought bubble tracked to fighter positions in real time.
   - Live Twitch/YouTube chat coaching and Hype/Morale comeback meter.

4. **Future AI Shoutcaster & Highlights Pipeline:**
   - Synchronized match gameplay recording with micro-event timestamp stream for automated commentary and expressive TTS (Tracked in GitLab Issue #1).

---

## 📁 Repository Structure

```text
HypeFighter-AI/
├── ikemen-lua-bridge/        # Lua hooks for Ikemen GO (telemetry + micro-events)
│   ├── README.md
│   └── bridge.lua            # 60 FPS UDP streamer & safe-zone evaluator
├── agent-core/               # Python AI controller & tactical services
│   ├── pyproject.toml
│   ├── src/
│   │   ├── models/           # Pydantic telemetry & event schemas
│   │   ├── receiver/         # Async UDP telemetry listener
│   │   ├── controller/       # 60Hz Safety Gatekeeper & intent translator
│   │   ├── tactician/        # Tactical SLM brain interface
│   │   └── mcp/              # MCP Server for character tuning
│   └── tests/                # Automated pytest suite
└── overlay-ui/               # Transparent overlay for stream & game window
    └── README.md
```

---

## 🚀 Quick Start

### 1. Agent Core (Python)

```bash
cd agent-core
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"
pytest tests/ -v
```

### 2. Ikemen GO Bridge Setup

1. Copy `ikemen-lua-bridge/bridge.lua` into your Ikemen GO `script/` directory.
2. In your `script/main.lua` or system loop, require the bridge:
   ```lua
   local bridge = require("script.bridge")
   bridge.init({ host = "127.0.0.1", port = 9999 })
   ```
3. Run Ikemen GO and start `agent-core` to receive telemetry at 60 FPS.
