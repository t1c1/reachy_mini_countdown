#!/bin/bash
# Quick start script for Reachy Mini Countdown

cd "$(dirname "$0")"

echo "🎉 Starting Reachy Mini Countdown..."
echo ""
echo "Make sure the Reachy Mini daemon is running first!"
echo "If not, run: uv run reachy-mini-daemon --sim"
echo ""
echo "Starting app in 3 seconds..."
sleep 3

uv run python main.py --test-seconds 15 --once
