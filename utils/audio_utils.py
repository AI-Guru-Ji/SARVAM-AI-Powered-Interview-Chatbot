"""
audio_utils.py — Record microphone input and play audio files.

Requires: pyaudio, pydub
Install:  pip install pyaudio pydub
          (on Ubuntu: sudo apt-get install portaudio19-dev first)
"""

import wave
import os
import subprocess
import threading
import time

try:
    import pyaudio
    PYAUDIO_AVAILABLE = True
except ImportError:
    PYAUDIO_AVAILABLE = False
    print("[WARN] pyaudio not installed — microphone recording disabled. "
          "You can still use pre-recorded .wav files.")


# ─────────────────────────────────────────────
# RECORDING SETTINGS
# ─────────────────────────────────────────────
CHUNK = 1024
FORMAT_CODE = 8          # paInt16 = 8
CHANNELS = 1
RATE = 16000             # 16kHz — optimal for Sarvam STT
MAX_SECONDS = 30         # Sarvam REST STT limit


def record_audio(output_path: str, duration: int = 15) -> str:
    """
    Record from microphone for `duration` seconds and save as WAV.

    Args:
        output_path : File path to save recording (e.g. "answer_1.wav")
        duration    : Recording length in seconds (max 30 for Sarvam REST)

    Returns:
        Path to the saved WAV file.
    """
    if not PYAUDIO_AVAILABLE:
        raise RuntimeError("pyaudio not installed. Install it with: pip install pyaudio")

    import pyaudio

    pa = pyaudio.PyAudio()
    stream = pa.open(
        format=pyaudio.paInt16,
        channels=CHANNELS,
        rate=RATE,
        input=True,
        frames_per_buffer=CHUNK
    )

    print(f"\n🎙  Recording for {duration} seconds... Speak now!")
    frames = []
    for _ in range(0, int(RATE / CHUNK * duration)):
        data = stream.read(CHUNK, exception_on_overflow=False)
        frames.append(data)

    print("⏹  Recording stopped.")
    stream.stop_stream()
    stream.close()
    pa.terminate()

    # Save as WAV
    with wave.open(output_path, "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(pa.get_sample_size(pyaudio.paInt16))
        wf.setframerate(RATE)
        wf.writeframes(b"".join(frames))

    return output_path


def play_audio(file_path: str):
    """
    Play a WAV file. Tries multiple backends (aplay → afplay → playsound).
    """
    if not os.path.exists(file_path):
        print(f"[WARN] Audio file not found: {file_path}")
        return

    # Linux / Ubuntu
    try:
        subprocess.run(["aplay", "-q", file_path], check=True)
        return
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass

    # macOS
    try:
        subprocess.run(["afplay", file_path], check=True)
        return
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass

    # Windows / fallback
    try:
        from playsound import playsound
        playsound(file_path)
        return
    except ImportError:
        pass

    print(f"[INFO] Could not play audio automatically. File saved at: {file_path}")


def countdown_timer(seconds: int):
    """Show a live countdown in the terminal while recording."""
    for i in range(seconds, 0, -1):
        print(f"\r⏱  Time remaining: {i:2d}s ", end="", flush=True)
        time.sleep(1)
    print("\r⏱  Time's up!              ")
