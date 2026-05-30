"""
tools/regenerate_welcome.py — Pre-generate the setup-screen welcome audio.

Run this whenever you change ``SETUP_WELCOME_TEXT`` (in
``data/interview_questions.py``). It calls Sarvam TTS once and saves
the WAV to ``assets/welcome.wav``. The setup view reads from that file
on every page load, so there is zero Sarvam API latency on the demo
landing page.

Usage::

    python tools/regenerate_welcome.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Make the project root importable regardless of where the script is launched
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from config.settings import get_settings
from data.interview_questions import SETUP_WELCOME_LANG_CODE, SETUP_WELCOME_TEXT
from services.sarvam_tts_service import SarvamTtsService


WELCOME_PATH = _ROOT / "assets" / "welcome.wav"


def main() -> int:
    settings = get_settings()
    if not settings.sarvam_api_key:
        print("✗ SARVAM_API_KEY is not set — cannot generate welcome audio.")
        print("  Set it in .env first, then re-run.")
        return 1

    tts = SarvamTtsService(settings)

    print("Generating setup-screen welcome audio…")
    print(f"  Language: {SETUP_WELCOME_LANG_CODE}")
    print(f"  Text:     {SETUP_WELCOME_TEXT[:80]}{'…' if len(SETUP_WELCOME_TEXT) > 80 else ''}")

    WELCOME_PATH.parent.mkdir(parents=True, exist_ok=True)
    result = tts.text_to_speech(
        text=SETUP_WELCOME_TEXT,
        output_path=str(WELCOME_PATH),
        language_code=SETUP_WELCOME_LANG_CODE,
    )
    size_kb = len(result.audio_bytes) / 1024
    print(f"✓ Saved: {WELCOME_PATH}  ({size_kb:.1f} KB)")
    print()
    print("The setup screen will now play this file instantly on page load.")
    print("Re-run this script any time you change SETUP_WELCOME_TEXT.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
