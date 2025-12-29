---
title: Reachy Mini Countdown
emoji: 🎉
colorFrom: yellow
colorTo: red
sdk: static
pinned: false
short_description: Countdown timer with celebration dance!
tags:
  - reachy_mini
  - reachy_mini_python_app
---

# 🎉 Reachy Mini Countdown

A countdown app for Reachy Mini. Set a timer, watch the robot get increasingly excited, then celebrate when it hits zero.

**[Install from Hugging Face](https://huggingface.co/spaces/t1c1/reachy_mini_countdown)**

## What It Does

- **Countdown Timer**: 5 to 3600 seconds
- **Celebration Dance**: Head bobs and antenna flips at zero
- **Voice Countdown**: Robot speaks "10, 9, 8..." through its speaker
- **Custom Music**: Set any YouTube URL for the celebration
- **Web UI**: Control everything from your browser

## Install

From the Reachy Mini Dashboard (http://localhost:8000):
1. Find "reachy-mini-countdown" in the app list
2. Click Install
3. Toggle it ON
4. Click ⚙️ to open controls at http://localhost:5001

Or install manually:
```bash
pip install git+https://huggingface.co/spaces/t1c1/reachy_mini_countdown
```

## How It Works

| Phase | What Happens |
|-------|--------------|
| Waiting | Gentle antenna sway |
| Final 60s | Antennas rise, head tilts up |
| Final 10s | Big antenna flips, head bobs, voice countdown |
| Zero | Celebration dance with music! |

## Controls

When running, open http://localhost:5001:

- **▶️ Start**: 30 second countdown
- **⏹️ Stop**: Pause
- **🔄 Reset**: Clear and return to ready
- **Custom Duration**: Enter seconds, click Start Custom
- **Speak Intervals**: Checkbox to announce 60, 50, 40... 
- **🎵 Save Music**: Set YouTube URL for celebration

## Development

```bash
git clone https://github.com/t1c1/reachy_mini_countdown
cd reachy_mini_countdown

# Setup
uv venv reachy_mini_env --python 3.12
source reachy_mini_env/bin/activate
uv sync

# Run daemon
uv run reachy-mini-daemon        # USB robot
uv run reachy-mini-daemon --sim  # Simulation

# Install in dev mode
pip install -e .
```

## Project Structure

```
reachy_mini_countdown/
├── reachy_mini_countdown/
│   ├── __init__.py
│   └── main.py              # App logic + web UI
├── index.html               # HF Space landing page
├── style.css
├── pyproject.toml
└── README.md
```

## Links

- [Hugging Face Space](https://huggingface.co/spaces/t1c1/reachy_mini_countdown)
- [GitHub](https://github.com/t1c1/reachy_mini_countdown)
- [Reachy Mini SDK](https://github.com/pollen-robotics/reachy_mini)
