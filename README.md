## Reachy Mini Countdown

This repo contains a simple countdown app for Reachy Mini.

### Step by step (matches the official SDK docs)

Reference docs: `https://github.com/pollen-robotics/reachy_mini/tree/main/docs/SDK`

1. Install `uv` (the SDK docs recommend it).

2. Install Python 3.12 via `uv`:

```bash
uv python install 3.12 --default
```

3. Create and activate a virtual environment:

```bash
uv venv reachy_mini_env --python 3.12
source reachy_mini_env/bin/activate
```

4. Install dependencies for this project:

```bash
uv sync
```

5. Ensure the daemon is running.

For Reachy Mini Wireless: the daemon runs on the robot when powered on. Ensure your computer and Reachy Mini are on the same network.

For Reachy Mini Lite (USB): run:

```bash
uv run reachy-mini-daemon
```

For simulation:

```bash
uv run reachy-mini-daemon --sim
```

6. Verify the dashboard is reachable:

Open `http://localhost:8000` in your browser.

7. Run the countdown.

If you are using Reachy Mini Wireless and running on your computer:

```bash
python main.py --wireless
```

If you are running locally on the same machine as the daemon:

```bash
python main.py
```

8. Open the Web UI in your browser:

```
http://localhost:5001
```

The web UI shows:
- **Live camera feed** from Reachy Mini
- **Countdown timer** (updates every second)
- **Status messages** that change as countdown progresses

### Quick Test Mode

Test with a short countdown (no need to wait until midnight):

```bash
python main.py --test-seconds 30 --once
```

Then open `http://localhost:5001` to see the camera and countdown!

### Custom Address and Port

Use a different port or host:

```bash
# Use port 8080
python main.py --port 8080

# Use localhost only (127.0.0.1)
python main.py --host 127.0.0.1 --port 5001

# Use a specific IP address
python main.py --host 192.168.1.100 --port 5001
```

### Video Recording

Record the countdown and celebration as a video file:

```bash
# Record with default filename (countdown_YYYYMMDD_HHMMSS.mp4)
python main.py --record

# Record with custom filename
python main.py --record --video-output my_countdown.mp4

# Test with recording
python main.py --test-seconds 30 --once --record
```

Videos are saved in the current directory as MP4 files at 30 FPS.

## How It Works

See [HOW_IT_WORKS.md](HOW_IT_WORKS.md) for a detailed explanation of the architecture, threading model, and how all the pieces fit together.

