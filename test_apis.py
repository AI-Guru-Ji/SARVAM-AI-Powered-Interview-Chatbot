"""
test_apis.py — Quick smoke-test for all three Sarvam APIs.

Run this BEFORE the main bot to verify your API key works.
Usage: python test_apis.py
"""

import sys
import os
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from utils.sarvam_api import text_to_speech, chat_completion, evaluate_candidate


def test_tts():
    print("\n[1/3] Testing Text-to-Speech (Bulbul v3)...")
    out = str(ROOT / "output" / "test_tts.wav")
    os.makedirs(ROOT / "output", exist_ok=True)
    try:
        text_to_speech(
            "Namaste! Main aapka interview bot hoon.",
            out,
            "hi-IN"
        )
        print(f"  ✅ TTS OK — audio saved to {out}")
    except Exception as e:
        print(f"  ❌ TTS FAILED: {e}")


def test_llm():
    print("\n[2/3] Testing LLM Chat (sarvam-30b)...")
    try:
        response = chat_completion(
            messages=[{"role": "user", "content": "Reply with exactly the words: API working"}]
        )
        print(f"  ✅ LLM OK — Response: {response}")
    except Exception as e:
        print(f"  ❌ LLM FAILED: {e}")


def test_evaluation():
    print("\n[3/3] Testing Candidate Evaluation...")
    try:
        result = evaluate_candidate(
            role="housekeeping",
            questions=["Tell me about your cleaning experience."],
            answers=["I have 3 years experience cleaning hotels, I know how to use disinfectants safely."],
            language="en"
        )
        print(f"  ✅ Evaluation OK — Overall score: {result.get('overall_score')}/10")
        print(f"     Summary: {result.get('summary', '')[:100]}")
    except Exception as e:
        print(f"  ❌ Evaluation FAILED: {e}")


if __name__ == "__main__":
    print("=" * 45)
    print("  Sarvam AI — API Connection Test")
    print("=" * 45)

    api_key = os.getenv("SARVAM_API_KEY")
    if not api_key or api_key == "your_api_key_here":
        print("\n❌  SARVAM_API_KEY not set.")
        print("   Copy .env.example to .env and add your key.")
        sys.exit(1)

    print(f"  API Key: ...{api_key[-6:]}")

    test_tts()
    test_llm()
    test_evaluation()

    print("\n✅ All tests complete.\n")
