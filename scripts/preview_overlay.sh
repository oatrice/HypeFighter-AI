#!/usr/bin/env bash
set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

if [ -f "$PROJECT_ROOT/agent-core/.venv/bin/activate" ]; then
    source "$PROJECT_ROOT/agent-core/.venv/bin/activate"
fi

exec python3 -u "$PROJECT_ROOT/scripts/preview_overlay.py"
