# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-11-15

### Added
- Monorepo project layout separating `ikemen-lua-bridge/`, `agent-core/`, and `overlay-ui/`.
- Ikemen GO Lua telemetry hook (`ikemen-lua-bridge/bridge.lua`) streaming 60 FPS combat data and micro-events via UDP.
- Python 60Hz Safety Gatekeeper (`agent-core`) with spatial hitbox awareness, `SAFE_BACK_ZONE` punishment guardrails, and ego-centric relative intent translation.
- Async non-blocking UDP telemetry receiver in Python.
- Comprehensive unit test suite with 100% pass rate for safety controller and telemetry parser.
- Architecture specification and backlog ticket (#1) for future Automated Video Recording & AI Shoutcaster Pipeline.
