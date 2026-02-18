#!/bin/bash
# Bu script botni to'g'ri Python muhiti (env) bilan SAFE restart qiladi.
set -e

PYTHON_PATH="/Users/macbookpro/Desktop/Antigravity_Projects/.venv/bin/python"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

cd "$SCRIPT_DIR"

echo "Eski bot processlari to'xtatilmoqda..."
pkill -f "main.py" >/dev/null 2>&1 || true

echo "Bot ishga tushirilmoqda..."
"$PYTHON_PATH" main.py
