# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.0] - 2026-11-16

### Added
- **Okizeme & Meaty Knockdown Pressure (`combo_engine.py`)**: aggressive approach upon enemy knockdown ($Dist > 55\text{px}$) and frame-1 meaty buffer (`c.LK` / `OKIZEME_MEATY`) upon opponent rising from floor (`stateno 5120`) (#15).
- **High-Low Offensive Mixup (`combo_engine.py`)**: breaks opponent holding guard for $\ge 30$ consecutive frames by alternating between crouching sweeps (`DOWN + LK`) and standing high pokes (`LP`) (#15).
- **Frame-1 Invincible Wakeup Reversal (`safety_gatekeeper.py`)**: detects P1 recovering from knockdown (`stateno 5120 -> 0`) and punishes incoming melee attacks with frame-1 `SmashKFUpper` (or `TripleKFPalm` if $Power \ge 1000$) (#15).
- **Air-to-Air Priority Collision (`safety_gatekeeper.py`)**: contests aerial collisions with air heavy punch normal (`AIR_TO_AIR_ENGAGE`) when both fighters are airborne ($Y < -15\text{px}$) within close proximity ($Dist \le 90\text{px}$) (#15).
- **Contextual In-Game Commentary & Overlay Thought Stream (`runner.py`)**: added reaction-synced Thai internal monologue and public fight chat for okizeme pressure, mixups, wakeup reversals, and air clashes with atomic IPC thought state updates (#15).
- **Combat Telemetry Metrics Breakdown**: enhanced `scripts/analyze_combat_metrics.py` to parse and track okizeme meaty attacks, high-low mixups, wakeup reversals, and air clashes in match history logs.
- **Expanded Test Suite**: added tests across `test_combo_engine.py`, `test_safety_gatekeeper.py`, and `test_runner.py`, expanding total deterministic verification matrix to 82 tests with 100% pass rate.

## [0.2.0] - 2026-11-16

### Added
- **Combat Macro Engine (`combo_engine.py`)**: 3-stage combat engine (`IDLE`, `INITIATING`, `CONFIRMED`) with hit-confirm chaining, special cancels (`QCF_x`), and super moves (`TripleKFPalm`) (#10).
- **High/Low & Aerial Defense Gate (`safety_gatekeeper.py`)**: dynamic guard mixup detection (`INSTANT_BLOCK_LOW`, `INSTANT_BLOCK_HIGH`, `INSTANT_BLOCK_AIR`) based on opponent and self altitudes (#10, #11).
- **Super Punish In-Place & Cooldown Guard**: executes super move finisher upon safe-zone detection when power meter $\ge 1000$ with 45-frame cooldown enforcement (#12).
- **Corner-Avoidance Boundary Spacing**: clamps retreat movement to neutral when backed against stage boundaries ($|X| \ge 140.0$) (#14).
- **Sustained Rushdown Commitment**: 12-frame forward commitment counter eliminating 1-frame intent flicker during close combat or opponent closeout ($HP \le 250$) (#14).
- **Combat Telemetry Metrics CLI (`scripts/analyze_combat_metrics.py`)**: automated tool calculating guard success rate, damage mitigation, super execution, and stance distributions (#14).
- **Continuous Integration Pipeline (`.gitlab-ci.yml`)**: GitLab CI configuration with lint, unit tests, security fuzzing, latency benchmark, and package build stages.
- **Expanded Testing Suites**: Fuzzing & security injection suite (`test_security_fuzzing.py`), combinatorial pairwise matrix (`test_pairwise_matrix.py`), and burst stress testing (`test_performance_stress.py`). Total 71 tests passing with 100% success rate.

### Changed
- **Strict Combo Abort Guards**: 5-condition validation requiring both fighters grounded and within close range ($\le 130\text{px}$) before allowing aborts, eliminating false abort triggers (#13).
- **State Hygiene & Round Reset**: resets `ComboEngine`, purges commentary cache, increments `round_epoch`, and restores baseline 1000 HP state immediately on `ROUND RESET` (#11, #14).
- **Ground Gate Filter**: central suppression of grounded specials and rushdown punch buttons when airborne ($Y < -5.0$), preserving mid-air combo juggles (#12, #14).
- **Real-Time Distance Synchronization**: ensures monologue distances dynamically reflect actual telemetry snapshot distance (#12, #13).
- **Overlay Accessibility & Security**: added ARIA landmarks, WCAG-compliant badge contrast, and safe numeric coordinate clamping in `overlay-ui/index.html`.

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
