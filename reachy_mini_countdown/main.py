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
import numpy as np

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
        # Track any local audio processes to stop them cleanly
        self._audio_procs: list[subprocess.Popen] = []
        self._audio_stop_event: threading.Event | None = None
        # Pre-generated countdown audio files
        self._countdown_audio_files: dict[int, str] = {}
        self._pre_generate_countdown_audio()

    def run(self, reachy_mini: ReachyMini, stop_event: threading.Event):
        """Main entry point - called by dashboard."""
        # Get shared state if available (set by main())
        countdown_state = getattr(self, '_countdown_state', None)
        control_state = getattr(self, '_control_state', None)
        audio_stop = None
        
        # Start with a gentle reset pose - ensure head is up high
        # Stop audio if running
        if audio_stop is None:
            audio_stop = getattr(self, "_audio_stop_event", None)
        self._stop_audio_playback(reachy_mini, audio_stop)
        self._reset_pose(reachy_mini)
        time.sleep(1.0)  # Give more time for head to move up
        
        # Double-check head is up high
        head = create_head_pose(yaw=0, pitch=-30, roll=0, degrees=True)
        reachy_mini.goto_target(head=head, duration=0.8)
        time.sleep(0.5)
        
        # Wait for start command if control_state exists
        self._last_spoken = -1  # Track which countdown numbers have been spoken
        if control_state is not None:
            while not stop_event.is_set():
                action = control_state.get('action')
                if action == 'start':
                    seconds = control_state.get('seconds', 30)
                    target = datetime.now() + timedelta(seconds=seconds)
                    control_state['action'] = None  # Clear action
                    control_state['running'] = True
                    self._last_spoken = -1
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
                            self._last_spoken = -1
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
                            self._last_spoken = -1
                            print(f"🎊 Starting {seconds} second countdown!")
                            break
                        time.sleep(0.5)
                    continue
                target = self._get_next_midnight() if self._target_override is None else self._target_override
            elif remaining <= 10:
                # Countdown from 10 to 1
                countdown_number = int(remaining)
                if countdown_number > 0 and countdown_number != getattr(self, '_last_spoken', -1):
                    self._last_spoken = countdown_number
                    self._final_ten(reachy_mini, countdown_number)
                # Sleep shorter to catch each second
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
        antenna_pos = -0.6 + (progress * 1.2)    # -0.6 to 0.6 radians (more lift)
        
        reachy.goto_target(antennas=[antenna_pos, antenna_pos], duration=0.4)
        
        # Head tilts up, starting from -30 degrees
        pitch = -30 - (progress * 20)  # -30 to -50 degrees (more tilt)
        head = create_head_pose(pitch=pitch, degrees=True)
        reachy.goto_target(head=head, duration=0.4)
        
        # Quick antenna flip every 10 seconds to add excitement
        if seconds_remaining % 10 == 0 and seconds_remaining > 0:
            reachy.goto_target(antennas=[0.8, -0.8], duration=0.25)
            reachy.goto_target(antennas=[-0.8, 0.8], duration=0.25)
            reachy.goto_target(antennas=[antenna_pos, antenna_pos], duration=0.25)
            # Speak interval if enabled
            control_state = getattr(self, '_control_state', None)
            if control_state and control_state.get('speak_intervals', False):
                self._speak_countdown(seconds_remaining, reachy)
        
        print(f"⏱️ {seconds_remaining}s...")

    def _final_ten(self, reachy: ReachyMini, seconds_remaining: int):
        """Countdown with antenna flip for each second."""
        # Print and speak countdown number
        if seconds_remaining > 0:
            print(f"🔥 {seconds_remaining}...")
            # Speak in background thread so we don't block
            threading.Thread(
                target=self._speak_countdown,
                args=(seconds_remaining, reachy),
                daemon=True
            ).start()
            # Antenna flip in background (non-blocking)
            threading.Thread(
                target=self._antenna_flip,
                args=(reachy, seconds_remaining),
                daemon=True
            ).start()
        else:
            print("🎉 ZERO! 🎉")
    
    def _antenna_flip(self, reachy: ReachyMini, seconds_remaining: int):
        """Quick antenna flip - runs in background."""
        try:
            if seconds_remaining % 2 == 0:
                reachy.goto_target(antennas=[0.7, -0.7], duration=0.2)
            else:
                reachy.goto_target(antennas=[-0.7, 0.7], duration=0.2)
        except Exception:
            pass  # Ignore errors in background thread

    def _pre_generate_countdown_audio(self):
        """Pre-generate audio files for countdown numbers 1-60 at startup."""
        import tempfile
        temp_dir = tempfile.gettempdir()
        
        print("🔊 Pre-generating countdown audio files...")
        # Generate for 1-10 (final countdown) plus 10, 20, 30, 40, 50, 60 (intervals)
        numbers_to_generate = list(range(1, 11)) + [20, 30, 40, 50, 60]
        
        for number in numbers_to_generate:
            try:
                if sys.platform == 'darwin':
                    aiff_file = os.path.join(temp_dir, f'countdown_{number}.aiff')
                    wav_file = os.path.join(temp_dir, f'countdown_{number}.wav')
                    
                    # Generate AIFF with say (default format)
                    subprocess.run(
                        ['say', '-o', aiff_file, str(number)],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        timeout=5
                    )
                    
                    if os.path.exists(aiff_file):
                        # Convert to WAV (16kHz for robot)
                        subprocess.run(
                            ['afconvert', '-f', 'WAVE', '-d', 'LEI16@16000', aiff_file, wav_file],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            timeout=5
                        )
                        if os.path.exists(wav_file):
                            self._countdown_audio_files[number] = wav_file
                            
                elif sys.platform.startswith('linux'):
                    wav_file = os.path.join(temp_dir, f'countdown_{number}.wav')
                    subprocess.run(
                        ['espeak', '-w', wav_file, str(number)],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        timeout=5
                    )
                    if os.path.exists(wav_file):
                        self._countdown_audio_files[number] = wav_file
                        
            except Exception as e:
                print(f"⚠️  Failed to generate audio for {number}: {e}")
        
        print(f"✅ Generated {len(self._countdown_audio_files)} countdown audio files")
    
    def _speak_countdown(self, number: int, reachy: ReachyMini | None = None):
        """Speak the countdown number - uses pre-generated audio for speed."""
        # Use pre-generated audio file if available
        if number in self._countdown_audio_files and reachy is not None:
            try:
                audio_file = self._countdown_audio_files[number]
                reachy.media.audio.play_sound(audio_file)
                print(f"🔊 {number}")
                return
            except Exception as e:
                print(f"⚠️  Robot audio failed ({e})")
        
        # Fallback to computer speaker
        self._speak_countdown_local(number)
    
    def _speak_countdown_local(self, number: int):
        """Fallback: speak using local system TTS."""
        try:
            if sys.platform == 'darwin':
                subprocess.Popen(['say', str(number)], 
                               stdout=subprocess.DEVNULL, 
                               stderr=subprocess.DEVNULL)
            elif sys.platform.startswith('linux'):
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
                try:
                    import win32com.client
                    speaker = win32com.client.Dispatch("SAPI.SpVoice")
                    speaker.Speak(str(number))
                except ImportError:
                    subprocess.Popen(['powershell', '-Command', 
                                    f'Add-Type -AssemblyName System.Speech; '
                                    f'$speak = New-Object System.Speech.Synthesis.SpeechSynthesizer; '
                                    f'$speak.Speak("{number}")'],
                                   stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL)
        except Exception:
            pass

    def _stop_audio_playback(self, reachy: ReachyMini, audio_stop_event: threading.Event | None = None) -> None:
        """Stop any ongoing audio playback both on the robot and local fallbacks."""
        if audio_stop_event is not None:
            audio_stop_event.set()
        try:
            if hasattr(reachy, "media") and getattr(reachy.media, "audio", None):
                reachy.media.audio.stop_playing()
        except Exception:
            pass
        # Stop local fallback processes
        still_running: list[subprocess.Popen] = []
        for proc in self._audio_procs:
            if proc.poll() is None:
                try:
                    proc.terminate()
                except Exception:
                    pass
            if proc.poll() is None:
                still_running.append(proc)
        self._audio_procs = still_running

    def _play_youtube_audio(self, url: str, stop_event: threading.Event, audio_stop: threading.Event, reachy: ReachyMini):
        """Play audio from a YouTube video in the background on the robot speaker when possible."""
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
                    # Try to play on the robot speaker first
                    try:
                        if hasattr(reachy.media, "audio") and hasattr(reachy.media.audio, "play_sound"):
                            reachy.media.audio.play_sound(audio_file)
                            print("🎵 Playing YouTube audio on Reachy Mini speaker...")
                        else:
                            raise AttributeError("media.audio.play_sound not available")
                    except Exception as play_err:
                        print(f"⚠️  Could not play on robot speaker ({play_err}), playing locally")
                        # Fallback: play locally using system player
                        proc: subprocess.Popen | None = None
                        if sys.platform == 'darwin':
                            proc = subprocess.Popen(['afplay', audio_file],
                                                   stdout=subprocess.DEVNULL,
                                                   stderr=subprocess.DEVNULL)
                        elif sys.platform.startswith('linux'):
                            for player in ['paplay', 'aplay', 'mpg123', 'ffplay']:
                                try:
                                    proc = subprocess.Popen([player, audio_file],
                                                           stdout=subprocess.DEVNULL,
                                                           stderr=subprocess.DEVNULL)
                                    break
                                except FileNotFoundError:
                                    continue
                        else:
                            proc = subprocess.Popen(['start', audio_file], shell=True,
                                                   stdout=subprocess.DEVNULL,
                                                   stderr=subprocess.DEVNULL)
                        print("🎵 Playing YouTube audio locally...")
                        if proc is not None:
                            self._audio_procs.append(proc)
                            # Wait and allow stop
                            while proc.poll() is None:
                                if stop_event.is_set() or audio_stop.is_set():
                                    try:
                                        proc.terminate()
                                    except Exception:
                                        pass
                                    break
                                time.sleep(0.25)
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
        audio_stop = threading.Event()
        self._audio_stop_event = audio_stop
        audio_url = control_state.get('youtube_url') if control_state else None
        if not audio_url:
            audio_url = self.AULD_LANG_SYNE_URL
        audio_thread = threading.Thread(
            target=self._play_youtube_audio,
            args=(audio_url, stop_event, audio_stop, reachy),
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
        # Stop any lingering audio (robot or local fallback)
        self._stop_audio_playback(reachy, audio_stop)
        # Stop any lingering audio (robot or local fallback)
        audio_stop.set()
        self._stop_audio_playback(reachy)
    
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
    parser.add_argument(
        "--youtube-url",
        type=str,
        default=None,
        help="Custom YouTube URL for celebration music",
    )
    parser.add_argument(
        "--emoji",
        type=str,
        default="🎉",
        help="Emoji used in the UI celebration display",
    )
    parser.add_argument(
        "--no-camera",
        action="store_true",
        help="Disable camera (useful for headless simulation mode)",
    )
    parser.add_argument(
        "--speak-intervals",
        action="store_true",
        help="Speak at every 10 second interval (60, 50, 40, 30, 20, 10)",
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
    emoji: str = "🎉",
    camera_available: bool = True,
    youtube_url: str = "",
) -> None:
    """Start Flask web server to display camera feed and countdown."""
    app = Flask(__name__)
    
    # Import Flask request for POST handling
    from flask import request, jsonify
    
    # Video recording setup
    video_writer = None
    if record_video:
        if reachy_mini.media.camera is None:
            print("⚠️  Video recording disabled: no camera available")
            record_video = False
        else:
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
                background: #f5f7fb;
                color: #1f2a3d;
                font-family: 'Inter', 'Arial', sans-serif;
                min-height: 100vh;
                display: flex;
                flex-direction: column;
                align-items: center;
                padding: 24px;
            }
            .header {
                text-align: center;
                margin-bottom: 24px;
            }
            .logo-container {
                display: inline-block;
                padding: 12px 20px;
                background: #ffffff;
                border-radius: 14px;
                border: 1px solid #e5e8ef;
                box-shadow: 0 8px 18px rgba(31,42,61,0.08);
            }
            h1 {
                font-size: 2.2em;
                font-weight: 800;
                color: #1f2a3d;
                letter-spacing: 0.5px;
            }
            h1::before, h1::after {
                content: '__EMOJI__';
                margin: 0 10px;
                font-size: 0.9em;
                vertical-align: middle;
            }
            .countdown-display {
                font-size: 6em;
                font-weight: 700;
                color: #1f2a3d;
                margin: 12px 0 4px;
                min-height: 64px;
            }
            .status {
                font-size: 1em;
                color: #4d7cff;
                margin-bottom: 16px;
                font-weight: 600;
            }
            .camera-container {
                max-width: 900px;
                width: 100%;
                margin: 0 auto;
                position: relative;
            }
            #camera {
                width: 100%;
                max-width: 900px;
                border: 1px solid #e5e8ef;
                border-radius: 14px;
                box-shadow: 0 10px 22px rgba(31,42,61,0.08);
                display: block;
                background: #000;
                min-height: 420px;
                object-fit: contain;
            }
            .camera-overlay {
                position: absolute;
                top: 12px;
                left: 12px;
                background: rgba(0, 0, 0, 0.55);
                color: #fff;
                padding: 10px 12px;
                border-radius: 10px;
                display: flex;
                flex-direction: column;
                gap: 4px;
                box-shadow: 0 6px 14px rgba(0,0,0,0.25);
            }
            .camera-overlay .countdown-display {
                color: #f5a524;
                margin: 0;
            }
            .camera-overlay .status {
                margin: 0;
                color: #c9ddff;
            }
            .camera-error {
                background: #f7f8fb;
                color: #c0392b;
                padding: 18px;
                text-align: center;
                border-radius: 14px;
                border: 1px solid #f0d9d4;
                box-shadow: 0 8px 18px rgba(31,42,61,0.05);
            }
            .info {
                text-align: center;
                margin-top: 16px;
                color: #6b7280;
                font-size: 0.95em;
            }
            .controls {
                background: #ffffff;
                padding: 18px 20px;
                border-radius: 14px;
                margin-top: 20px;
                max-width: 640px;
                margin-left: auto;
                margin-right: auto;
                border: 1px solid #e5e8ef;
                box-shadow: 0 10px 22px rgba(31,42,61,0.08);
            }
            .controls h3 {
                color: #f5a524;
                margin-bottom: 12px;
                display: flex;
                align-items: center;
                gap: 6px;
                font-size: 1em;
                font-weight: 700;
            }
            .controls p {
                margin: 4px 0;
                font-size: 0.95em;
                color: #2f3a4d;
            }
            .button-group {
                display: flex;
                gap: 10px;
                justify-content: center;
                margin-top: 12px;
                flex-wrap: wrap;
            }
            button {
                padding: 10px 18px;
                font-size: 0.95em;
                border: 1px solid transparent;
                border-radius: 8px;
                cursor: pointer;
                font-weight: 700;
                transition: all 0.15s ease;
            }
            .btn-start {
                background: #4d7cff;
                color: #ffffff;
                border-color: #4d7cff;
            }
            .btn-start:hover { background: #3c68e0; }
            .btn-stop {
                background: #ec5b56;
                color: #ffffff;
                border-color: #ec5b56;
            }
            .btn-stop:hover { background: #d64a46; }
            .btn-reset {
                background: #ffd24c;
                color: #1f2a3d;
                border-color: #ffd24c;
            }
            .btn-reset:hover { background: #f5c635; }
            button:disabled {
                opacity: 0.6;
                cursor: not-allowed;
            }
            .input-group {
                margin: 14px 0;
                display: flex;
                gap: 10px;
                align-items: center;
                justify-content: center;
            }
            .input-group input {
                padding: 9px 10px;
                font-size: 0.95em;
                border: 1px solid #d6d9e2;
                border-radius: 8px;
                background: #fff;
                color: #1f2a3d;
                width: 90px;
            }
            .input-group label {
                color: #4b5563;
                font-size: 0.95em;
            }
        </style>
    </head>
    <body>
        <div class="header">
            <div class="logo-container">
                <h1>Reachy Mini Countdown</h1>
            </div>
        </div>
        __CAMERA_BLOCK__
        <div class="info">
            <p>Watch the robot countdown and celebrate!</p>
        </div>
        <div class="controls">
            <h3>📋 Status</h3>
            <p><strong>Camera:</strong> <span id="camera-status">__CAM_STATUS__</span></p>
            <p><strong>Robot:</strong> <span id="robot-status">Connected</span></p>
            
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
            <div class="input-group" style="flex-direction: column; align-items: stretch; gap: 8px;">
                <label for="youtube-url">Celebration YouTube URL:</label>
                <input type="text" id="youtube-url" value="__YT_URL__" style="width: 100%; max-width: 480px;">
                <div class="button-group" style="justify-content: flex-start;">
                    <button class="btn-reset" onclick="setYoutube()">Save Music</button>
                </div>
            </div>
            <div class="input-group">
                <input type="checkbox" id="speak-intervals" __SPEAK_INTERVALS_CHECKED__ onchange="toggleSpeakIntervals()">
                <label for="speak-intervals">Speak at 10-second intervals (60, 50, 40...)</label>
            </div>
        </div>
        
        <script>
            function updateCountdown() {
                fetch('/countdown')
                    .then(r => r.json())
                    .then(data => {
                        const countdownEl = document.getElementById('countdown');
                        const statusEl = document.getElementById('status');
                        
                        if (data.remaining <= 0) {
                            countdownEl.textContent = '__EMOJI_TRIPLE__';
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

            function setYoutube() {
                const url = document.getElementById('youtube-url').value.trim();
                if (!url) {
                    alert('Please enter a YouTube URL');
                    return;
                }
                fetch('/control/music', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({url})
                })
                .then(r => r.json())
                .then(data => {
                    if (data.success) {
                        alert('Music updated');
                    } else {
                        alert('Could not update music: ' + (data.error || 'unknown error'));
                    }
                })
                .catch(() => alert('Network error while updating music'));
            }
            
            function toggleSpeakIntervals() {
                const checked = document.getElementById('speak-intervals').checked;
                fetch('/control/speak-intervals', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({enabled: checked})
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
    
    # Build camera block depending on availability
    if camera_available:
        camera_block = """
        <div class="camera-container">
            <img id="camera" src="/video_feed" alt="Camera Feed" 
                 onerror="this.style.display='none'; document.getElementById('camera-error').style.display='block';"
                 onload="this.style.display='block'; document.getElementById('camera-error').style.display='none';">
            <div class="camera-overlay">
                <div class="countdown-display" id="countdown">--:--:--</div>
                <div class="status" id="status">Initializing...</div>
            </div>
            <div id="camera-error" class="camera-error" style="display:none;">
                <p>⚠️ Camera feed not available</p>
                <p style="font-size:0.8em; margin-top:10px;">Make sure the robot camera is connected and permissions are granted.</p>
            </div>
        </div>
        """
        cam_status = "Active"
    else:
        camera_block = """
        <div class="camera-container">
            <div class="camera-overlay">
                <div class="countdown-display" id="countdown">--:--:--</div>
                <div class="status" id="status">Initializing...</div>
            </div>
            <div class="camera-error" style="display:block;">
                <p>Camera disabled</p>
                <p style="font-size:0.8em; margin-top:10px;">Running without camera stream.</p>
            </div>
        </div>
        """
        cam_status = "Disabled"
    
    # Inject emoji, music URL, and camera blocks into template
    yt_value = control_state.get('youtube_url') or youtube_url or ""
    speak_checked = "checked" if control_state.get('speak_intervals', False) else ""
    templ = (
        HTML_TEMPLATE
        .replace("__EMOJI__", emoji)
        .replace("__EMOJI_TRIPLE__", emoji * 3)
        .replace("__YT_URL__", yt_value)
        .replace("__CAMERA_BLOCK__", camera_block)
        .replace("__CAM_STATUS__", cam_status)
        .replace("__SPEAK_INTERVALS_CHECKED__", speak_checked)
    )
    
    @app.route('/')
    def index():
        return render_template_string(templ)
    
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

    @app.route('/control/music', methods=['POST'])
    def set_music():
        """Set custom YouTube URL for celebration."""
        try:
            data = request.get_json() or {}
            url = data.get('url')
            if not url or not isinstance(url, str):
                return jsonify({'success': False, 'error': 'Invalid URL'}), 400
            control_state['youtube_url'] = url
            return jsonify({'success': True, 'message': 'Music updated', 'url': url})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
    
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
    
    @app.route('/control/speak-intervals', methods=['POST'])
    def set_speak_intervals():
        """Toggle speaking at 10-second intervals."""
        try:
            data = request.get_json() or {}
            enabled = data.get('enabled', False)
            control_state['speak_intervals'] = enabled
            return jsonify({'success': True, 'enabled': enabled})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
    
    def generate_frames():
        """Generate camera frames as JPEG stream and optionally record video."""
        # Check if camera is available
        if reachy_mini.media.camera is None:
            # Generate a placeholder frame
            placeholder = np.zeros((480, 640, 3), dtype=np.uint8)
            cv2.putText(placeholder, "Camera not available", (120, 240), 
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
            cv2.putText(placeholder, "(Headless simulation mode)", (140, 280), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (150, 150, 150), 1)
            ret, buffer = cv2.imencode('.jpg', placeholder)
            if ret:
                frame_bytes = buffer.tobytes()
                while not stop_event.is_set():
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
                    time.sleep(1)  # Slow update for placeholder
            return
            
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
    control_state = {
        'action': None,
        'running': False,
        'seconds': 30,
        'youtube_url': None,
        'speak_intervals': args.speak_intervals,
    }
    
    # Determine the URL for the web UI
    if args.host == "0.0.0.0" or args.host == "127.0.0.1":
        ui_url = f"http://127.0.0.1:{args.port}"
    else:
        ui_url = f"http://{args.host}:{args.port}"
    
    try:
        # Increase connection timeout for daemon startup
        print("🔌 Connecting to Reachy Mini daemon...")
        media_backend = "no_media" if args.no_camera else "default"
        with ReachyMini(localhost_only=localhost_only, timeout=30, media_backend=media_backend) as mini:
            # Start camera web UI in background thread
            camera_available = mini.media.camera is not None
            app_instance = ReachyMiniCountdown(
                target,
                celebration_duration_s=args.celebration_seconds,
                once=args.once,
            )
            # Override YouTube URL if provided
            if args.youtube_url is not None:
                app_instance.AULD_LANG_SYNE_URL = args.youtube_url
            control_state['youtube_url'] = app_instance.AULD_LANG_SYNE_URL
            app_instance.custom_app_url = ui_url  # Set the URL dynamically
            app_instance._countdown_state = countdown_state  # Share state
            app_instance._control_state = control_state  # Share control state
            
            app_thread = threading.Thread(
                target=_start_camera_ui,
                kwargs={
                    "reachy_mini": mini,
                    "stop_event": stop_event,
                    "countdown_state": countdown_state,
                    "control_state": control_state,
                    "port": args.port,
                    "host": args.host,
                    "record_video": args.record,
                    "video_filename": args.video_output,
                    "emoji": args.emoji,
                    "camera_available": camera_available,
                    "youtube_url": app_instance.AULD_LANG_SYNE_URL,
                },
                daemon=True
            )
            app_thread.start()
            time.sleep(1)  # Give UI time to start
            
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