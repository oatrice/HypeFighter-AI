#!/usr/bin/env bash
# Wrapper to launch the Python thought monitor cleanly
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec python3 "$PROJECT_ROOT/scripts/watch_thoughts.py"
