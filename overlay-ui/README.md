# Interactive Overlay UI (Floating Thought Bubble + Crowd Coaching)

A transparent browser source or desktop overlay (Electron / Tauri / OBS Browser Source) layered directly over Ikemen GO.

## Features

1. **Floating Comic Thought Bubble:**
   - Tracks `p1.pos.x, p1.pos.y` in real time via WebSocket to pin a thought bubble dynamically above the AI fighter.
   - Smoothly renders the AI's internal thoughts, tactical stances, and Thai banter (e.g., *"เขาต่อยไปทางขวาเปิดหลังโล่ง สวนกลับตรงนี้เลย!"*).

2. **Live Crowd Coaching & Hype Meter:**
   - Connects to YouTube Live, Twitch, or local WebSocket chat.
   - Filters and ranks chat suggestions.
   - Fills the **Hype / Morale Meter** when chat engagement spikes, triggering tactical comeback shifts (aggressive meter usage, counter-stances).

## Technology Stack

- **Renderer:** Transparent WebGL / HTML Canvas or CSS transform tracking.
- **Transport:** WebSocket / SSE from `agent-core` on `ws://127.0.0.1:8765`.
- **Display Modes:** OBS Browser Source with transparent background or Tauri frameless borderless window.
