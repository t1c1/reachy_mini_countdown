# Video Recording Guide

## How to Record the Countdown

The app can record the entire countdown and celebration as an MP4 video file.

### Basic Recording

```bash
# Record with auto-generated filename
python main.py --record

# Output: countdown_20251227_153045.mp4 (timestamp-based)
```

### Custom Filename

```bash
# Record with custom filename
python main.py --record --video-output my_new_year_countdown.mp4
```

### Test Mode with Recording

```bash
# Quick 30-second test with recording
python main.py --test-seconds 30 --once --record --video-output test_countdown.mp4
```

### Full Example

```bash
# Record a real countdown to midnight
python main.py --record --video-output new_year_2025.mp4
```

## Video Specifications

- **Format**: MP4 (H.264 codec)
- **Frame Rate**: 30 FPS
- **Resolution**: Matches camera resolution (typically 640x480 or higher)
- **Location**: Saved in the current working directory

## Custom Address and Port

### Change Port

```bash
# Use port 8080 instead of default 5001
python main.py --port 8080

# Then access at: http://localhost:8080
```

### Change Host Address

```bash
# Localhost only (more secure)
python main.py --host 127.0.0.1 --port 5001

# Specific IP address (for network access)
python main.py --host 192.168.1.100 --port 5001

# All interfaces (default, allows network access)
python main.py --host 0.0.0.0 --port 5001
```

### Combined Example

```bash
# Record video, use custom port, localhost only
python main.py --record --video-output party.mp4 --host 127.0.0.1 --port 9000
```

## How It Works

1. **Video Writer**: Uses OpenCV's `VideoWriter` to encode frames
2. **Frame Capture**: Captures every frame from `reachy_mini.media.get_frame()`
3. **Simultaneous**: Records while streaming to web UI (no performance impact)
4. **Auto-cleanup**: Video file is finalized when app stops

## Tips

- Videos are saved even if you interrupt with Ctrl+C
- The video includes the entire countdown from start to finish
- File size depends on duration (roughly 1-2 MB per minute)
- Make sure you have enough disk space for long recordings
