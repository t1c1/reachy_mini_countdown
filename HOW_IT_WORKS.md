# How the Reachy Mini Countdown App Works

## Overview

This app creates a countdown timer that makes Reachy Mini celebrate when it reaches zero. It includes a web UI that shows the camera feed and live countdown.

## Architecture

### 1. **Main Countdown Logic** (`ReachyMiniCountdown.run()`)
- Calculates time remaining until target (midnight by default)
- Controls robot movements based on time remaining:
  - **> 60 seconds**: Gentle idle animation (antennas sway)
  - **60-10 seconds**: Antennas rise, head tilts up
  - **10-0 seconds**: Head bobs, antennas fully up
  - **0 seconds**: Celebration dance!

### 2. **Web UI** (`_start_camera_ui()`)
- Flask web server running on port 5001
- Shows live camera feed from Reachy Mini
- Displays countdown timer that updates every second
- Accessible at: `http://localhost:5001`

### 3. **State Sharing**
- `countdown_state` dictionary shared between threads:
  - Main thread updates `remaining` seconds
  - Web UI reads it via `/countdown` API endpoint
  - JavaScript polls every second to update display

### 4. **Camera Streaming**
- Uses `reachy_mini.media.get_frame()` to get camera frames
- Encodes frames as JPEG
- Streams via MJPEG (Motion JPEG) format
- Browser auto-updates the `<img>` tag

## How to Use

### Step 1: Start the Daemon
```bash
export PATH="$HOME/.local/bin:$PATH"
source .venv/bin/activate
uv run reachy-mini-daemon
```

### Step 2: Run the App
```bash
# In a new terminal:
export PATH="$HOME/.local/bin:$PATH"
source .venv/bin/activate
python main.py
```

### Step 3: Open the Web UI
Open your browser to: `http://localhost:5001`

You'll see:
- Live camera feed from Reachy Mini
- Countdown timer (HH:MM:SS format)
- Status messages that change as countdown progresses

### Test Mode (Quick Test)
```bash
python main.py --test-seconds 30 --once
```
This starts a 30-second countdown for testing.

## File Structure

```
main.py
├── ReachyMiniCountdown (ReachyMiniApp)
│   ├── run() - Main countdown loop
│   ├── _celebrate() - Celebration dance
│   ├── _final_ten() - Final 10 seconds
│   └── _final_minute() - Final 60 seconds
├── _start_camera_ui() - Flask web server
│   ├── / - Main HTML page
│   ├── /video_feed - MJPEG camera stream
│   └── /countdown - JSON API for countdown state
└── main() - Entry point, starts everything
```

## Threading Model

1. **Main Thread**: Runs countdown logic, controls robot
2. **UI Thread**: Runs Flask server, serves web pages
3. **Camera Thread**: Inside Flask, generates video frames

All threads share `stop_event` to coordinate shutdown.

## Key Technologies

- **Reachy Mini SDK**: Robot control (`ReachyMini`, `ReachyMiniApp`)
- **Flask**: Web server framework
- **OpenCV (cv2)**: Camera frame encoding
- **MJPEG**: Video streaming protocol
- **JavaScript**: Client-side countdown updates

## Customization

- Change celebration duration: `--celebration-seconds 30`
- Set custom target time: `--target "2025-12-31T23:59:50"`
- Test mode: `--test-seconds 15 --once`
now