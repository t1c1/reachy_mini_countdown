#!/bin/bash
# Kill all and start fresh

cd "$(dirname "$0")"

echo "🛑 Killing all processes..."
pkill -9 -f "python.*main.py" 2>/dev/null
pkill -9 -f "uv run python.*main" 2>/dev/null
sleep 2

echo "✅ Starting Reachy Mini Countdown..."
echo ""
echo "Make sure Reachy Mini Control app is running!"
echo ""

uv run python main.py --test-seconds 15 --once
