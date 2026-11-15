# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.2] - 2026-11-15

### Changed
- Relaxed Safety Gatekeeper altitude threshold from `-200.0` to `-750.0`, allowing full aerial combos and juggling while ensuring camera tracking keeps fighters visible without premature recovery interrupts.
- Set Shadow Rival (`shadow_kfm`, P2) default palette to Palette 3 (Red Gi, white headband) instead of Palette 6 (Green Gi).
- Enabled global dynamic auto-zoom and vertical follow across all stages in `engine/save/config.ini` (`ForceStageAutoZoom = 1`, `ForceStageZoomout = 0.70`, `ForceStageZoomin = 1.10`) for universal multi-character support.
- Updated `stage0.def` and `stage0-720.def` bounds to `-800` ceiling and full `verticalfollow = 1.0`.

### Added
- Unit test `test_air_combos_allowed_at_high_altitude` asserting air combos proceed uninterrupted at $y = -350.0$.
- Auto-provisioning routine for `stages/tournament.def` inside `scripts/run_match.sh`.

## [0.1.1] - 2026-11-15

### Added
- Reverse Input Injection loop via UDP port 9998: `ActionUDPSender` in Python and native command buffer injection in `bridge.lua`.
- Altitude Ceiling Guardrail in `SafetyGatekeeper`: prevents infinite off-screen aerial stalls and enforces gravity recovery when $y < -200.0$.
- Ikemen GO official macOS release bundle setup in `.gitignore` path `engine/`.
- Dynamic Tournament Arena Stage (`engine/stages/tournament.def`) with vertical camera follow (`verticalfollow = 1.0`, `boundhigh = -800`) and dynamic zoom-out (`zoomout = 0.70`).
- Spectator Match Runner script (`scripts/run_match.sh`) for launching Ikemen GO in Watch Mode with live AI console telemetry.
- Unit test suite expanded to 22 tests with 100% pass rate.

## [0.1.0] - 2026-11-15

### Added
- Monorepo project layout separating `ikemen-lua-bridge/`, `agent-core/`, and `overlay-ui/`.
- Ikemen GO Lua telemetry hook (`ikemen-lua-bridge/bridge.lua`) streaming 60 FPS combat data and micro-events via UDP.
- Python 60Hz Safety Gatekeeper (`agent-core`) with spatial hitbox awareness, `SAFE_BACK_ZONE` punishment guardrails, and ego-centric relative intent translation.
- Async non-blocking UDP telemetry receiver in Python.
- Comprehensive unit test suite with 100% pass rate for safety controller and telemetry parser.
- Architecture specification and backlog ticket (#1) for future Automated Video Recording & AI Shoutcaster Pipeline.
