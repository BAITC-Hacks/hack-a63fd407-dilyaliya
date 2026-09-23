#!/bin/sh
set -eu
cd "$(dirname "$0")"
if [ -x .venv/bin/python ]; then exec .venv/bin/python launch.py "$@"; fi
if command -v python3.11 >/dev/null 2>&1; then exec python3.11 launch.py "$@"; fi
if command -v python3 >/dev/null 2>&1; then exec python3 launch.py "$@"; fi
printf '%s\n' 'Установите CPython 3.11 или используйте docker compose up --build.' >&2
exit 1
