"""
🎉 Reachy Mini Countdown
New Year's Eve or any celebration!
"""

import argparse
import base64
import io
import os
import subprocess
import sys
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

from flask import Flask, Response, render_template_string
import cv2

from reachy_mini import ReachyMini, ReachyMiniApp
from reachy_mini.utils import create_head_pose


class ReachyMiniCountdown(ReachyMiniApp):
    """Countdown app with celebration dance at zero."""

    custom_app_url: str | None = None  # Set dynamically based on port
    CELEBRATION_DURATION = 60
    # Classic "Auld Lang Syne" - traditional New Year's song
    AULD_LANG_SYNE_URL = "https://www.youtube.com/watch?v=Al7ONqrdscY&t=3s"
    _easter_egg_activated = False  # 🥚 Easter egg state

    def __init__(
        self,
        target: datetime | None = None,
        *,
        celebration_duration_s: int | None = None,
        once: bool = False,
    ):
        self._target_override = target
        self._once = once
        if celebration_duration_s is not None:
            self.CELEBRATION_DURATION = celebration_duration_s

    def run(self, reachy_mini: ReachyMini, stop_event: threading.Event):
        """Main entry point - called by dashboard."""
        # Get shared state if available (set by main())
        countdown_state = getattr(self, '_countdown_state', None)
        control_state = getattr(self, '_control_state', None)
        
        # Start with a gentle reset pose - ensure head is up high
        self._reset_pose(reachy_mini)
        time.sleep(1.0)  # Give more time for head to move up
        
        # Double-check head is up high
        head = create_head_pose(yaw=0, pitch=-30, roll=0, degrees=True)
        reachy_mini.goto_target(head=head, duration=0.8)
        time.sleep(0.5)
        
        # Wait for start command if control_state exists
        if control_state is not None:
            while not stop_event.is_set():
                action = control_state.get('action')
                if action == 'start':
                    seconds = control_state.get('seconds', 30)
                    target = datetime.now() + timedelta(seconds=seconds)
                    control_state['action'] = None  # Clear action
                    control_state['running'] = True
                    print(f"🎊 Starting {seconds} second countdown!")
                    break
                elif action == 'reset':
                    control_state['action'] = None
                    control_state['running'] = False
                    countdown_state['remaining'] = 0
                    self._reset_pose(reachy_mini)
                time.sleep(0.5)
        else:
            # Default behavior - use target override or midnight
            target = self._target_override or self._get_next_midnight()
            print(f"🎊 Countdown to: {target}")

        while not stop_event.is_set():
            # Check for stop command
            if control_state is not None:
                if control_state.get('action') == 'stop':
                    control_state['action'] = None
                    control_state['running'] = False
                    print("⏹️ Countdown stopped")
                    self._reset_pose(reachy_mini)
                    # Wait for new start command
                    while not stop_event.is_set():
                        action = control_state.get('action')
                        if action == 'start':
                            seconds = control_state.get('seconds', 30)
                            target = datetime.now() + timedelta(seconds=seconds)
                            control_state['action'] = None
                            control_state['running'] = True
                            print(f"🎊 Starting {seconds} second countdown!")
                            break
                        elif action == 'reset':
                            control_state['action'] = None
                            control_state['running'] = False
                            countdown_state['remaining'] = 0
                            self._reset_pose(reachy_mini)
                        time.sleep(0.5)
                    continue
                elif control_state.get('action') == 'reset':
                    control_state['action'] = None
                    control_state['running'] = False
                    countdown_state['remaining'] = 0
                    self._reset_pose(reachy_mini)
                    target = datetime.now() + timedelta(seconds=30)  # Default 30s
                    continue
            
            remaining = (target - datetime.now()).total_seconds()
            
            # Update shared state for web UI
            if countdown_state is not None:
                countdown_state['remaining'] = remaining
                countdown_state['target'] = str(target)

            if remaining <= 0:
                self._celebrate(reachy_mini, stop_event)
                if self._once:
                    break
                # Check if we should continue or wait for new start
                if control_state is not None:
                    control_state['running'] = False
                    # Wait for new start command
                    while not stop_event.is_set():
                        action = control_state.get('action')
                        if action == 'start':
                            seconds = control_state.get('seconds', 30)
                            target = datetime.now() + timedelta(seconds=seconds)
                            control_state['action'] = None
                            control_state['running'] = True
                            print(f"🎊 Starting {seconds} second countdown!")
                            break
                        time.sleep(0.5)
                    continue
                target = self._get_next_midnight() if self._target_override is None else self._target_override
            elif remaining <= 10:
                # Countdown from 10 to 1
                countdown_number = int(remaining)
                if countdown_number > 0:
                    self._final_ten(reachy_mini, countdown_number)
                    # Wait until next second
                    time.sleep(1.0)
                else:
                    time.sleep(0.1)
            elif remaining <= 60:
                self._final_minute(reachy_mini, int(remaining))
                time.sleep(1)
            else:
                # Keep head up during idle
                head = create_head_pose(pitch=-30, degrees=True)
                reachy_mini.goto_target(head=head, duration=0.3)
                self._waiting_idle(reachy_mini)
                time.sleep(5)

        self._reset_pose(reachy_mini)

    def _get_next_midnight(self) -> datetime:
        now = datetime.now()
        tomorrow = now + timedelta(days=1)
        return tomorrow.replace(hour=0, minute=0, second=0, microsecond=0)

    def _reset_pose(self, reachy: ReachyMini):
        # Keep head up (not too low)
        head = create_head_pose(yaw=0, pitch=-30, roll=0, degrees=True)
        reachy.goto_target(head=head, antennas=[0, 0], duration=0.8)
        time.sleep(0.3)  # Ensure movement completes

    def _waiting_idle(self, reachy: ReachyMini):
        """Gentle idle animation."""
        # Keep head up during idle
        head = create_head_pose(pitch=-30, degrees=True)
        reachy.goto_target(head=head, antennas=[-0.2, 0.2], duration=0.5)
        reachy.goto_target(antennas=[0.2, -0.2], duration=0.5)

    def _final_minute(self, reachy: ReachyMini, seconds_remaining: int):
        """Antennas rise during final 60 seconds."""
        progress = 1 - (seconds_remaining / 60)  # 0.0 → 1.0
        antenna_pos = -0.4 + (progress * 0.8)    # -0.4 to 0.4 radians
        
        reachy.goto_target(antennas=[antenna_pos, antenna_pos], duration=0.5)
        
        # Head tilts up, starting from -30 degrees
        pitch = -30 - (progress * 15)  # -30 to -45 degrees
        head = create_head_pose(pitch=pitch, degrees=True)
        reachy.goto_target(head=head, duration=0.5)
        
        print(f"⏱️ {seconds_remaining}s...")

    def _final_ten(self, reachy: ReachyMini, seconds_remaining: int):
        """Countdown with head bobs for final 10 seconds."""
        # Antennas fully up
        reachy.goto_target(antennas=[0.5, 0.5], duration=0.2)
        
        # Head bob (keep head up, no downward movement)
        head_mid = create_head_pose(pitch=-35, degrees=True)
        head_up = create_head_pose(pitch=-45, degrees=True)
        reachy.goto_target(head=head_mid, duration=0.2)
        reachy.goto_target(head=head_up, duration=0.2)
        
        # Print and speak countdown number (10, 9, 8, 7, 6, 5, 4, 3, 2, 1)
        if seconds_remaining > 0:
            print(f"🔥 {seconds_remaining}...")
            self._speak_countdown(seconds_remaining)
        else:
            print("🎉 ZERO! 🎉")

    def _speak_countdown(self, number: int):
        """Speak the countdown number using system text-to-speech."""
        try:
            if sys.platform == 'darwin':
                # macOS - use 'say' command
                subprocess.Popen(['say', str(number)], 
                               stdout=subprocess.DEVNULL, 
                               stderr=subprocess.DEVNULL)
            elif sys.platform.startswith('linux'):
                # Linux - try espeak or festival
                for tts in ['espeak', 'festival']:
                    try:
                        if tts == 'espeak':
                            subprocess.Popen(['espeak', str(number)],
                                           stdout=subprocess.DEVNULL,
                                           stderr=subprocess.DEVNULL)
                        else:
                            subprocess.Popen(['festival', '--tts'], 
                                           input=f"{number}\n".encode(),
                                           stdout=subprocess.DEVNULL,
                                           stderr=subprocess.DEVNULL)
                        break
                    except FileNotFoundError:
                        continue
            else:
                # Windows - use SAPI or PowerShell
                try:
                    import win32com.client
                    speaker = win32com.client.Dispatch("SAPI.SpVoice")
                    speaker.Speak(str(number))
                except ImportError:
                    # Fallback to PowerShell
                    subprocess.Popen(['powershell', '-Command', 
                                    f'Add-Type -AssemblyName System.Speech; '
                                    f'$speak = New-Object System.Speech.Synthesis.SpeechSynthesizer; '
                                    f'$speak.Speak("{number}")'],
                                   stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL)
        except Exception:
            # Silently fail if TTS is not available
            pass

    def _play_youtube_audio(self, url: str, stop_event: threading.Event):
        """Play audio from a YouTube video in the background."""
        try:
            import yt_dlp
            import tempfile
            
            # Download audio to temporary file
            temp_dir = tempfile.gettempdir()
            output_template = os.path.join(temp_dir, 'auld_lang_syne_%(id)s.%(ext)s')
            
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': output_template,
                'quiet': True,
                'no_warnings': True,
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
                # Change extension to .mp3 after extraction
                audio_file = os.path.splitext(filename)[0] + '.mp3'
                
                if os.path.exists(audio_file):
                    # Play audio using system's default player
                    if sys.platform == 'darwin':
                        # macOS
                        subprocess.Popen(['afplay', audio_file], 
                                       stdout=subprocess.DEVNULL, 
                                       stderr=subprocess.DEVNULL)
                    elif sys.platform.startswith('linux'):
                        # Linux - try multiple players
                        for player in ['paplay', 'aplay', 'mpg123', 'ffplay']:
                            try:
                                subprocess.Popen([player, audio_file],
                                               stdout=subprocess.DEVNULL,
                                               stderr=subprocess.DEVNULL)
                                break
                            except FileNotFoundError:
                                continue
                    else:
                        # Windows
                        subprocess.Popen(['start', audio_file], shell=True,
                                       stdout=subprocess.DEVNULL,
                                       stderr=subprocess.DEVNULL)
                    print("🎵 Playing Auld Lang Syne from YouTube...")
                else:
                    print("⚠️  Audio file not found after download")
        except ImportError:
            print("⚠️  yt-dlp not installed. Install with: uv sync or pip install yt-dlp")
        except Exception as e:
            print(f"⚠️  Could not play YouTube audio: {e}")
            # Fallback to beep pattern
            try:
                self._play_auld_lang_syne_beeps(stop_event)
            except:
                pass

    def _celebrate(self, reachy: ReachyMini, stop_event: threading.Event):
        """🎉 CELEBRATION!"""
        # Check for easter egg
        control_state = getattr(self, '_control_state', None)
        easter_egg = control_state.get('easter_egg', False) if control_state else False
        
        if easter_egg:
            print("\n🥚🥚🥚 EASTER EGG ACTIVATED! 🥚🥚🥚\n")
            print("🎊 Special celebration mode! 🎊\n")
            self._easter_egg_celebration(reachy, stop_event)
            # Reset easter egg
            if control_state:
                control_state['easter_egg'] = False
            return
        
        print("\n🎉🎉🎉 HAPPY NEW YEAR! 🎉🎉🎉\n")
        
        # Start playing Auld Lang Syne from YouTube in background
        audio_thread = threading.Thread(
            target=self._play_youtube_audio,
            args=(self.AULD_LANG_SYNE_URL, stop_event),
            daemon=True
        )
        audio_thread.start()

        # Initial burst - 3 big spins (slower and smoother, with error handling)
        for _ in range(3):
            if stop_event.is_set():
                return
            try:
                reachy.goto_target(antennas=[0.6, -0.4], duration=0.4)
                head = create_head_pose(roll=15, pitch=-35, yaw=-20, degrees=True)
                reachy.goto_target(head=head, duration=0.4)
                
                reachy.goto_target(antennas=[-0.4, 0.6], duration=0.4)
                head = create_head_pose(roll=-15, pitch=-35, yaw=20, degrees=True)
                reachy.goto_target(head=head, duration=0.4)
            except (TimeoutError, Exception) as e:
                print(f"Spin timeout (continuing): {type(e).__name__}")
                time.sleep(0.2)

        # Victory pose
        reachy.goto_target(antennas=[0.6, 0.6], duration=0.2)
        head = create_head_pose(pitch=-45, degrees=True)
        reachy.goto_target(head=head, duration=0.3)
        time.sleep(0.5)

        # Celebration loop
        start = time.time()
        beat = 0
        
        while time.time() - start < self.CELEBRATION_DURATION:
            if stop_event.is_set():
                return
            
            beat += 1
            time.sleep(0.1)  # Small delay to prevent overwhelming the daemon
            
            # Alternating dance (smoother, with error handling)
            try:
                if beat % 2 == 0:
                    reachy.goto_target(antennas=[0.5, -0.2], duration=0.4)
                    head = create_head_pose(roll=10, pitch=-30, yaw=-15, degrees=True)
                else:
                    reachy.goto_target(antennas=[-0.2, 0.5], duration=0.4)
                    head = create_head_pose(roll=-10, pitch=-30, yaw=15, degrees=True)
                
                reachy.goto_target(head=head, duration=0.4)
            except (TimeoutError, Exception) as e:
                # If movement times out, just continue
                print(f"Movement timeout (continuing): {type(e).__name__}")
            
            # Big move every 5 beats
            if beat % 5 == 0:
                try:
                    reachy.goto_target(antennas=[0.6, 0.6], duration=0.5)
                    head = create_head_pose(pitch=-40, degrees=True)
                    reachy.goto_target(head=head, duration=0.5)
                    time.sleep(0.3)
                except (TimeoutError, Exception) as e:
                    print(f"Big move timeout (continuing): {type(e).__name__}")
                    time.sleep(0.2)

        print("🎊 Celebration complete!")
    
    def _easter_egg_celebration(self, reachy: ReachyMini, stop_event: threading.Event):
        """🥚 Special easter egg celebration - extra special dance!"""
        print("🌟 Performing special easter egg dance! 🌟")
        
        # Super celebration - extra spins and movements
        for i in range(5):  # More spins
            if stop_event.is_set():
                return
            try:
                # Fast alternating spins
                reachy.goto_target(antennas=[0.8, -0.6], duration=0.3)
                head = create_head_pose(roll=20, pitch=-40, yaw=-30, degrees=True)
                reachy.goto_target(head=head, duration=0.3)
                
                reachy.goto_target(antennas=[-0.6, 0.8], duration=0.3)
                head = create_head_pose(roll=-20, pitch=-40, yaw=30, degrees=True)
                reachy.goto_target(head=head, duration=0.3)
            except Exception as e:
                print(f"Easter egg move error: {type(e).__name__}")
                time.sleep(0.1)
        
        # Victory pose with extra flair
        for _ in range(3):
            if stop_event.is_set():
                return
            try:
                reachy.goto_target(antennas=[0.7, 0.7], duration=0.2)
                head = create_head_pose(pitch=-50, roll=10, yaw=0, degrees=True)
                reachy.goto_target(head=head, duration=0.2)
                time.sleep(0.2)
                
                reachy.goto_target(antennas=[0.7, 0.7], duration=0.2)
                head = create_head_pose(pitch=-50, roll=-10, yaw=0, degrees=True)
                reachy.goto_target(head=head, duration=0.2)
                time.sleep(0.2)
            except Exception as e:
                print(f"Easter egg pose error: {type(e).__name__}")
        
        print("✨ Easter egg celebration complete! ✨")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Reachy Mini countdown app")

    parser.add_argument(
        "--wireless",
        action="store_true",
        help="Use this if your script runs on your computer and your Reachy Mini is on the network.",
    )
    parser.add_argument(
        "--target",
        type=str,
        default=None,
        help="Target local datetime in ISO format, for example 2025-12-31T23:59:50",
    )
    parser.add_argument(
        "--test-seconds",
        type=int,
        default=None,
        help="Start a short countdown from now, for example 15 (overrides --target).",
    )
    parser.add_argument(
        "--celebration-seconds",
        type=int,
        default=ReachyMiniCountdown.CELEBRATION_DURATION,
        help="How long to celebrate once the timer reaches zero.",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Exit after the first celebration completes (useful for testing).",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=5001,
        help="Port for the web UI (default: 5001)",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Host address for the web UI (default: 0.0.0.0, use 127.0.0.1 for localhost only)",
    )
    parser.add_argument(
        "--record",
        action="store_true",
        help="Record the countdown and celebration as a video file",
    )
    parser.add_argument(
        "--video-output",
        type=str,
        default=None,
        help="Output video filename (default: countdown_YYYYMMDD_HHMMSS.mp4)",
    )
    return parser.parse_args()


def _start_camera_ui(
    reachy_mini: ReachyMini,
    stop_event: threading.Event,
    countdown_state: dict,
    control_state: dict,
    port: int = 5001,
    host: str = "0.0.0.0",
    record_video: bool = False,
    video_filename: str | None = None,
) -> None:
    """Start Flask web server to display camera feed and countdown."""
    app = Flask(__name__)
    
    # Import Flask request for POST handling
    from flask import request, jsonify
    
    # Video recording setup
    video_writer = None
    if record_video:
        if video_filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            video_filename = f"countdown_{timestamp}.mp4"
        
        # Get frame size from first frame
        try:
            test_frame = reachy_mini.media.get_frame()
            if test_frame is not None:
                height, width = test_frame.shape[:2]
                fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                video_writer = cv2.VideoWriter(video_filename, fourcc, 30.0, (width, height))
                print(f"📹 Recording video to: {video_filename}")
        except Exception as e:
            print(f"⚠️  Could not initialize video recording: {e}")
            record_video = False
    
    HTML_TEMPLATE = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Reachy Mini Countdown</title>
        <meta charset="utf-8">
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body {
                background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
                color: white;
                font-family: 'Arial', sans-serif;
                min-height: 100vh;
                display: flex;
                flex-direction: column;
                align-items: center;
                padding: 20px;
            }
            .header {
                text-align: center;
                margin-bottom: 30px;
                position: relative;
            }
            .logo-container {
                position: relative;
                display: inline-block;
                padding: 20px 40px;
                background: linear-gradient(135deg, rgba(255,215,0,0.15) 0%, rgba(255,107,107,0.15) 100%);
                border-radius: 20px;
                border: 2px solid rgba(255,215,0,0.3);
                box-shadow: 0 8px 32px rgba(0,0,0,0.3),
                            0 0 40px rgba(255,215,0,0.2);
                animation: logoGlow 3s ease-in-out infinite;
            }
            @keyframes logoGlow {
                0%, 100% {
                    box-shadow: 0 8px 32px rgba(0,0,0,0.3),
                                0 0 40px rgba(255,215,0,0.2);
                }
                50% {
                    box-shadow: 0 8px 32px rgba(0,0,0,0.3),
                                0 0 60px rgba(255,215,0,0.4),
                                0 0 80px rgba(255,107,107,0.3);
                }
            }
            h1 {
                font-size: 3em;
                font-weight: 900;
                background: linear-gradient(135deg, #ffd700 0%, #ff6b6b 50%, #4ecdc4 100%);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                background-clip: text;
                text-shadow: none;
                margin: 0;
                letter-spacing: 2px;
                animation: logoPulse 2s ease-in-out infinite;
                position: relative;
            }
            @keyframes logoPulse {
                0%, 100% {
                    transform: scale(1);
                }
                50% {
                    transform: scale(1.02);
                }
            }
            h1::before {
                content: '🎉';
                position: absolute;
                left: -50px;
                top: 50%;
                transform: translateY(-50%);
                font-size: 0.8em;
                animation: emojiSpin 4s linear infinite;
            }
            h1::after {
                content: '🎊';
                position: absolute;
                right: -50px;
                top: 50%;
                transform: translateY(-50%);
                font-size: 0.8em;
                animation: emojiSpin 4s linear infinite reverse;
            }
            @keyframes emojiSpin {
                0% {
                    transform: translateY(-50%) rotate(0deg);
                }
                100% {
                    transform: translateY(-50%) rotate(360deg);
                }
            }
            .countdown-display {
                font-size: 4em;
                font-weight: bold;
                color: #ff6b6b;
                text-shadow: 3px 3px 6px rgba(0,0,0,0.7);
                margin: 20px 0;
                min-height: 80px;
            }
            .status {
                font-size: 1.2em;
                color: #4ecdc4;
                margin-bottom: 20px;
            }
            .camera-container {
                max-width: 900px;
                width: 100%;
                margin: 0 auto;
            }
            #camera {
                width: 100%;
                max-width: 900px;
                border: 4px solid #ffd700;
                border-radius: 15px;
                box-shadow: 0 8px 32px rgba(0,0,0,0.5);
                display: block;
                background: #000;
                min-height: 400px;
                object-fit: contain;
            }
            .camera-error {
                background: #333;
                color: #ff6b6b;
                padding: 20px;
                text-align: center;
                border-radius: 15px;
                border: 2px solid #ff6b6b;
            }
            .info {
                text-align: center;
                margin-top: 20px;
                color: #ccc;
                font-size: 0.9em;
            }
            .controls {
                background: rgba(255,255,255,0.1);
                padding: 20px;
                border-radius: 10px;
                margin-top: 20px;
                max-width: 600px;
                margin-left: auto;
                margin-right: auto;
            }
            .controls h3 {
                color: #ffd700;
                margin-bottom: 15px;
            }
            .controls p {
                margin: 5px 0;
                font-size: 0.9em;
            }
            .button-group {
                display: flex;
                gap: 10px;
                justify-content: center;
                margin-top: 15px;
                flex-wrap: wrap;
            }
            button {
                padding: 12px 24px;
                font-size: 1em;
                border: none;
                border-radius: 8px;
                cursor: pointer;
                font-weight: bold;
                transition: all 0.3s;
            }
            .btn-start {
                background: #4ecdc4;
                color: white;
            }
            .btn-start:hover {
                background: #45b8b0;
                transform: scale(1.05);
            }
            .btn-stop {
                background: #ff6b6b;
                color: white;
            }
            .btn-stop:hover {
                background: #ee5a5a;
                transform: scale(1.05);
            }
            .btn-reset {
                background: #ffd700;
                color: #1a1a2e;
            }
            .btn-reset:hover {
                background: #e6c200;
                transform: scale(1.05);
            }
            button:disabled {
                opacity: 0.5;
                cursor: not-allowed;
                transform: none;
            }
            .input-group {
                margin: 15px 0;
                display: flex;
                gap: 10px;
                align-items: center;
                justify-content: center;
            }
            .input-group input {
                padding: 8px 12px;
                font-size: 1em;
                border: 2px solid #4ecdc4;
                border-radius: 6px;
                background: rgba(255,255,255,0.1);
                color: white;
                width: 80px;
            }
            .input-group label {
                color: #ccc;
            }
        </style>
    </head>
    <body>
        <div class="header">
            <div class="logo-container">
                <h1>Reachy Mini Countdown</h1>
            </div>
            <div class="countdown-display" id="countdown">--:--:--</div>
            <div class="status" id="status">Initializing...</div>
        </div>
        <div class="camera-container">
            <img id="camera" src="/video_feed" alt="Camera Feed" 
                 onerror="this.style.display='none'; document.getElementById('camera-error').style.display='block';"
                 onload="this.style.display='block'; document.getElementById('camera-error').style.display='none';">
            <div id="camera-error" class="camera-error" style="display:none;">
                <p>⚠️ Camera feed not available</p>
                <p style="font-size:0.8em; margin-top:10px;">Make sure the robot camera is connected and permissions are granted.</p>
            </div>
        </div>
        <div class="info">
            <p>Watch the robot countdown and celebrate!</p>
        </div>
        <div class="controls">
            <h3>📋 Status</h3>
            <p><strong>Camera:</strong> <span id="camera-status">Active</span></p>
            <p><strong>Robot:</strong> <span id="robot-status">Connected</span></p>
            <p><strong>Head Position:</strong> <span id="head-status">High (35-45°)</span></p>
            
            <h3>🎮 Controls</h3>
            <div class="button-group">
                <button class="btn-start" id="btn-start" onclick="startCountdown()">▶️ Start</button>
                <button class="btn-stop" id="btn-stop" onclick="stopCountdown()" disabled>⏹️ Stop</button>
                <button class="btn-reset" id="btn-reset" onclick="resetCountdown()">🔄 Reset</button>
            </div>
            
            <div class="input-group">
                <label for="countdown-seconds">Countdown (seconds):</label>
                <input type="number" id="countdown-seconds" value="30" min="5" max="3600">
                <button class="btn-start" onclick="startCustomCountdown()">Start Custom</button>
            </div>
            <p style="text-align: center; margin-top: 15px; font-size: 0.75em; color: #888; opacity: 0.6;">
                🥚 Try the Konami code: ↑↑↓↓←→←→BA
            </p>
        </div>
        
        <script>
            function updateCountdown() {
                fetch('/countdown')
                    .then(r => r.json())
                    .then(data => {
                        const countdownEl = document.getElementById('countdown');
                        const statusEl = document.getElementById('status');
                        
                        if (data.remaining <= 0) {
                            countdownEl.textContent = '🎉🎉🎉';
                            statusEl.textContent = 'CELEBRATING!';
                            statusEl.style.color = '#ffd700';
                        } else if (data.remaining <= 10) {
                            countdownEl.textContent = data.formatted;
                            statusEl.textContent = '🔥 Final seconds!';
                            statusEl.style.color = '#ff6b6b';
                        } else if (data.remaining <= 60) {
                            countdownEl.textContent = data.formatted;
                            statusEl.textContent = '⏱️ Final minute!';
                            statusEl.style.color = '#ffd700';
                        } else {
                            countdownEl.textContent = data.formatted;
                            statusEl.textContent = 'Waiting for countdown...';
                            statusEl.style.color = '#4ecdc4';
                        }
                    })
                    .catch(e => console.error('Countdown update error:', e));
            }
            
            // Update every second
            setInterval(updateCountdown, 1000);
            updateCountdown();
            
            // 🥚 Easter egg: Konami code detection
            let konamiCode = [];
            const konamiSequence = ['ArrowUp', 'ArrowUp', 'ArrowDown', 'ArrowDown', 
                                   'ArrowLeft', 'ArrowRight', 'ArrowLeft', 'ArrowRight', 
                                   'KeyB', 'KeyA'];
            document.addEventListener('keydown', (e) => {
                konamiCode.push(e.code);
                if (konamiCode.length > konamiSequence.length) {
                    konamiCode.shift();
                }
                if (konamiCode.join(',') === konamiSequence.join(',')) {
                    fetch('/easter-egg/konami')
                        .then(r => r.json())
                        .then(data => {
                            if (data.success) {
                                alert('🥚 Easter Egg Activated! ' + data.message);
                            }
                        });
                    konamiCode = [];
                }
            });
            
            // Control functions
            function startCountdown() {
                fetch('/control/start', {method: 'POST'})
                    .then(r => r.json())
                    .then(data => {
                        if (data.success) {
                            document.getElementById('btn-start').disabled = true;
                            document.getElementById('btn-stop').disabled = false;
                        }
                    });
            }
            
            function startCustomCountdown() {
                const seconds = parseInt(document.getElementById('countdown-seconds').value);
                if (seconds < 5 || seconds > 3600) {
                    alert('Please enter a value between 5 and 3600 seconds');
                    return;
                }
                fetch('/control/start', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({seconds: seconds})
                })
                .then(r => r.json())
                .then(data => {
                    if (data.success) {
                        document.getElementById('btn-start').disabled = true;
                        document.getElementById('btn-stop').disabled = false;
                    }
                });
            }
            
            function stopCountdown() {
                fetch('/control/stop', {method: 'POST'})
                    .then(r => r.json())
                    .then(data => {
                        if (data.success) {
                            document.getElementById('btn-start').disabled = false;
                            document.getElementById('btn-stop').disabled = true;
                        }
                    });
            }
            
            function resetCountdown() {
                fetch('/control/reset', {method: 'POST'})
                    .then(r => r.json())
                    .then(data => {
                        if (data.success) {
                            document.getElementById('btn-start').disabled = false;
                            document.getElementById('btn-stop').disabled = true;
                        }
                    });
            }
            
            // 🥚 Easter egg: Konami code detection
            let konamiCode = [];
            const konamiSequence = ['ArrowUp', 'ArrowUp', 'ArrowDown', 'ArrowDown', 
                                   'ArrowLeft', 'ArrowRight', 'ArrowLeft', 'ArrowRight', 
                                   'KeyB', 'KeyA'];
            document.addEventListener('keydown', (e) => {
                konamiCode.push(e.code);
                if (konamiCode.length > konamiSequence.length) {
                    konamiCode.shift();
                }
                if (konamiCode.join(',') === konamiSequence.join(',')) {
                    fetch('/easter-egg/konami')
                        .then(r => r.json())
                        .then(data => {
                            if (data.success) {
                                alert('🥚 Easter Egg Activated! ' + data.message);
                            }
                        });
                    konamiCode = [];
                }
            });
        </script>
    </body>
    </html>
    """
    
    @app.route('/')
    def index():
        return render_template_string(HTML_TEMPLATE)
    
    @app.route('/easter-egg/<secret>')
    def easter_egg(secret: str):
        """🥚 Secret easter egg endpoint - try 'konami' or '1337'"""
        if secret.lower() in ['konami', '1337', 'secret', 'easter']:
            control_state['easter_egg'] = True
            return jsonify({
                'success': True, 
                'message': '🥚 Easter egg activated! Check the celebration!',
                'hint': 'The robot will do something special next time it celebrates...'
            })
        return jsonify({'success': False, 'message': 'Not the right secret...'}), 404
    
    @app.route('/countdown')
    def get_countdown():
        """Return current countdown state as JSON."""
        remaining = countdown_state.get('remaining', 0)
        hours = int(remaining // 3600)
        minutes = int((remaining % 3600) // 60)
        seconds = int(remaining % 60)
        formatted = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        
        return {
            'remaining': remaining,
            'formatted': formatted,
            'target': countdown_state.get('target', ''),
            'running': control_state.get('running', False)
        }
    
    @app.route('/control/start', methods=['POST'])
    def start_countdown():
        """Start a new countdown."""
        try:
            data = request.get_json() or {}
            seconds = data.get('seconds', 30)
            
            control_state['action'] = 'start'
            control_state['seconds'] = seconds
            control_state['running'] = True
            
            return jsonify({'success': True, 'message': f'Starting {seconds} second countdown'})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/control/stop', methods=['POST'])
    def stop_countdown():
        """Stop the current countdown."""
        try:
            control_state['action'] = 'stop'
            control_state['running'] = False
            return jsonify({'success': True, 'message': 'Countdown stopped'})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/control/reset', methods=['POST'])
    def reset_countdown():
        """Reset the countdown."""
        try:
            control_state['action'] = 'reset'
            control_state['running'] = False
            countdown_state['remaining'] = 0
            return jsonify({'success': True, 'message': 'Countdown reset'})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
    
    def generate_frames():
        """Generate camera frames as JPEG stream and optionally record video."""
        while not stop_event.is_set():
            try:
                frame = reachy_mini.media.get_frame()
                if frame is not None:
                    # Record to video file if enabled
                    if record_video and video_writer is not None:
                        video_writer.write(frame)
                    
                    # Stream to web UI
                    ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                    if ret:
                        frame_bytes = buffer.tobytes()
                        yield (b'--frame\r\n'
                               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
                time.sleep(0.033)  # ~30 FPS
            except Exception as e:
                print(f"Camera frame error: {e}")
                time.sleep(0.1)
        
        # Clean up video writer
        if video_writer is not None:
            video_writer.release()
            print(f"✅ Video saved to: {video_filename}")
    
    @app.route('/video_feed')
    def video_feed():
        """Stream camera feed as MJPEG."""
        return Response(
            generate_frames(),
            mimetype='multipart/x-mixed-replace; boundary=frame'
        )
    
    @app.route('/camera/test')
    def camera_test():
        """Test endpoint to check if camera is working."""
        try:
            frame = reachy_mini.media.get_frame()
            if frame is not None:
                ret, buffer = cv2.imencode('.jpg', frame)
                if ret:
                    from flask import send_file
                    import io
                    return send_file(
                        io.BytesIO(buffer.tobytes()),
                        mimetype='image/jpeg'
                    )
            return jsonify({'error': 'No frame available'}), 404
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    try:
        local_url = f"http://127.0.0.1:{port}" if host == "0.0.0.0" else f"http://{host}:{port}"
        print(f"📹 Camera UI starting at {local_url}")
        if record_video:
            print(f"🎥 Video recording enabled: {video_filename}")
        app.run(host=host, port=port, debug=False, use_reloader=False)
    except Exception as e:
        print(f"Camera UI error: {e}")
    finally:
        # Ensure video writer is closed
        if video_writer is not None:
            video_writer.release()


def main() -> None:
    args = _parse_args()

    target: datetime | None = None
    if args.test_seconds is not None:
        target = datetime.now() + timedelta(seconds=args.test_seconds)
    elif args.target is not None:
        target = datetime.fromisoformat(args.target)

    # SDK quickstart note:
    # If you have a Reachy Mini Wireless and run the script on your computer, you need localhost_only=False.
    localhost_only = not args.wireless

    stop_event = threading.Event()
    countdown_state = {'remaining': 0, 'target': ''}
    control_state = {'action': None, 'running': False, 'seconds': 30}
    
    # Determine the URL for the web UI
    if args.host == "0.0.0.0" or args.host == "127.0.0.1":
        ui_url = f"http://127.0.0.1:{args.port}"
    else:
        ui_url = f"http://{args.host}:{args.port}"
    
    try:
        # Increase connection timeout for daemon startup
        print("🔌 Connecting to Reachy Mini daemon...")
        with ReachyMini(localhost_only=localhost_only, timeout=30) as mini:
            # Start camera web UI in background thread
            app_thread = threading.Thread(
                target=_start_camera_ui,
                args=(mini, stop_event, countdown_state, control_state, args.port, args.host, args.record, args.video_output),
                daemon=True
            )
            app_thread.start()
            time.sleep(1)  # Give UI time to start
            
            app_instance = ReachyMiniCountdown(
                target,
                celebration_duration_s=args.celebration_seconds,
                once=args.once,
            )
            # Override YouTube URL if provided
            if args.youtube_url:
                app_instance.AULD_LANG_SYNE_URL = args.youtube_url
            app_instance.custom_app_url = ui_url  # Set the URL dynamically
            app_instance._countdown_state = countdown_state  # Share state
            app_instance._control_state = control_state  # Share control state
            
            # If no target specified, wait for web UI start command
            if target is None and args.test_seconds is None:
                print("⏸️  Waiting for start command from web UI...")
                print(f"📹 Open {ui_url} to control the countdown")
            
            app_instance.run(mini, stop_event)
    except KeyboardInterrupt:
        stop_event.set()
    except Exception as e:
        print(f"Error: {e}")
        stop_event.set()
        raise


if __name__ == "__main__":
    main()