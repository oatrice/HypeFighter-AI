# Agent Core (60Hz Safety Gatekeeper & Tactical Brain)

The Python runtime powering real-time fighter safety, reactive anti-air/punish execution, and tactical decision making for Ikemen GO.

## Modules

- `agent_core.models`: Pydantic telemetry models and combat micro-event definitions.
- `agent_core.receiver`: High-throughput, non-blocking UDP receiver parsing 60 FPS fighter telemetry.
- `agent_core.controller`: 60Hz Reactive Safety Gatekeeper enforcing spatial hitbox collision guards, `SAFE_BACK_ZONE` punish-in-place locks, and ego-centric relative intent translation.
- `agent_core.tactician`: 2–5Hz Tactical Brain sliding-window summary analyzer and crowd chat ingestor.
- `agent_core.mcp`: MCP server for offline/live character tuning and match inspection.
