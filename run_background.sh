#!/bin/bash
set -e

PYTHON_PATH="/Users/macbookpro/Desktop/Antigravity_Projects/.venv/bin/python"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

cd "$SCRIPT_DIR"

echo "Eski bot processlari to'xtatilmoqda..."
pkill -f "main.py" >/dev/null 2>&1 || true

echo "Bot fon rejimida ishga tushirilmoqda..."
nohup "$PYTHON_PATH" main.py > bot.log 2>&1 &
echo "Bot ishga tushdi! Loglarni ko'rish uchun: tail -f bot.log"
echo "To'xtatish uchun: pkill -f main.py"
