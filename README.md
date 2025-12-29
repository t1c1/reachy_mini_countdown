---
title: Reachy Mini Countdown
emoji: 🎉
colorFrom: yellow
colorTo: orange
sdk: static
pinned: false
tags:
  - reachy_mini
  - reachy_mini_python_app
---

# 🎉 Reachy Mini Countdown

A fun countdown app for New Year's Eve or any celebration! Watch Reachy Mini count down, dance, and celebrate when the timer hits zero.

**[Install from Hugging Face](https://huggingface.co/spaces/t1c1/reachy_mini_countdown)** | **[View on GitHub](https://github.com/t1c1/reachy_mini_countdown)**

## Features

- ⏱️ **Countdown Timer**: Set any duration (5 to 3600 seconds)
- 💃 **Celebration Dance**: Intense head bobs and antenna flips at zero
- 🎵 **Custom Music**: Set any YouTube URL for the celebration
- 🗣️ **Voice Countdown**: Speaks the final 10 seconds (macOS)
- 🌐 **Web UI**: Control everything from your browser

## Quick Install

**From the Reachy Mini Dashboard:**
1. Go to http://localhost:8000
2. Find "Reachy Mini Countdown" in the app list
3. Click Install
4. Toggle it ON
5. Click ⚙️ to open controls

**Or install manually:**
```bash
pip install git+https://huggingface.co/spaces/t1c1/reachy_mini_countdown
```

## How It Works

1. **Waiting**: Gentle antenna metronome sway
2. **Final Minute**: Antennas rise, head tilts up, alternating antenna flips
3. **Final 10 Seconds**: Big antenna flips, head bobs, spoken countdown
4. **Celebration**: Full dance routine with your chosen music!

## Web UI Controls

Open http://localhost:5001 when the app is running:

- **▶️ Start**: Begin countdown with default 30 seconds
- **⏹️ Stop**: Pause the countdown
- **🔄 Reset**: Clear and return to ready state
- **Custom Duration**: Enter seconds and click Start Custom
- **🎵 Save Music**: Set a YouTube URL for celebration

## Development Setup

If you want to modify the app locally:

```bash
# Clone the repo
git clone https://github.com/t1c1/reachy_mini_countdown
cd reachy_mini_countdown

# Install uv (recommended)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create virtual environment
uv venv .venv --python 3.12
source .venv/bin/activate

# Install dependencies
uv sync

# Run the daemon (for USB Reachy Mini or simulation)
uv run reachy-mini-daemon        # USB
uv run reachy-mini-daemon --sim  # Simulation

# Install the app in dev mode
pip install -e /path/to/my_reachy_apps/reachy_mini_countdown
```

## Project Structure

```
reachy_mini_countdown/
├── reachy_mini_countdown/
│   ├── __init__.py
│   └── main.py              # App logic + embedded web UI
├── index.html               # HF Space landing page
├── style.css                # HF Space styles
├── README.md
└── pyproject.toml
```

## Links

- **Hugging Face Space**: https://huggingface.co/spaces/t1c1/reachy_mini_countdown
- **GitHub**: https://github.com/t1c1/reachy_mini_countdown
- **Reachy Mini SDK**: https://github.com/pollen-robotics/reachy_mini

## Author

Created by [t1c1](https://huggingface.co/t1c1)

## License

MIT
