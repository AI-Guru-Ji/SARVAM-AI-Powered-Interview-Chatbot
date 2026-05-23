"""
interview_bot.py — Main entrypoint for the Blue Collar Interview Bot.

Usage:
    python interview_bot.py

Flow:
    1. Select job role (housekeeping, electrician, plumber, security_guard)
    2. Select language (Hindi / English)
    3. Bot greets candidate via TTS
    4. For each question:
        a. Bot speaks the question (TTS)
        b. Candidate answers (microphone → WAV)
        c. Answer transcribed (STT)
        d. Bot gives a short acknowledgement (LLM + TTS)
    5. LLM evaluates all answers and prints score report
    6. Score report saved as JSON

Requirements:
    pip install requests pyaudio python-dotenv pydub colorama
    Copy .env.example to .env and add your SARVAM_API_KEY
"""

import os
import sys
import json
import threading
import time
from pathlib import Path
from datetime import datetime
from colorama import Fore, Style, init

# ── ensure imports work from any cwd ──────────────────────────────────────────
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from utils.sarvam_api import speech_to_text, text_to_speech, chat_completion, evaluate_candidate, decide_next_turn
from utils.audio_utils import record_audio, play_audio, countdown_timer
from data.question_bank import QUESTION_BANK, OPENING_MESSAGE, CLOSING_MESSAGE

init(autoreset=True)  # colorama

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────────────────
RECORDING_DURATION = 20      # seconds per answer
MAX_FOLLOW_UPS_PER_QUESTION = 1   # cap on adaptive follow-ups per main question
TEMP_DIR = ROOT / "output" / "temp"
TEMP_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_DIR = ROOT / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────
def speak(text: str, language_code: str, filename: str = "bot_speak.wav"):
    """Convert text to speech and play it."""
    audio_path = str(TEMP_DIR / filename)
    try:
        text_to_speech(text, audio_path, language_code)
        play_audio(audio_path)
    except Exception as e:
        print(f"{Fore.YELLOW}[TTS fallback] Could not play audio: {e}")
        print(f"{Fore.CYAN}Bot: {text}")


def listen(question_id) -> str:
    """Record candidate's answer and return transcription.

    `question_id` can be an int (e.g. 3) or a string (e.g. "3_followup_1") —
    it's used only to name the saved WAV file.
    """
    wav_path = str(TEMP_DIR / f"answer_{question_id}.wav")

    # Run countdown in background while recording
    timer_thread = threading.Thread(
        target=countdown_timer, args=(RECORDING_DURATION,), daemon=True
    )

    try:
        timer_thread.start()
        record_audio(wav_path, duration=RECORDING_DURATION)
        timer_thread.join()
    except RuntimeError as e:
        # pyaudio not available — accept typed input as fallback
        print(f"{Fore.YELLOW}{e}")
        text_answer = input(f"{Fore.GREEN}Type your answer: {Style.RESET_ALL}")
        return text_answer

    # Transcribe
    try:
        transcript = speech_to_text(wav_path, language_code=lang_code)
        return transcript
    except Exception as e:
        print(f"{Fore.RED}[STT Error] {e}")
        return ""


def get_acknowledgement(question: str, answer: str, language: str) -> str:
    """Generate a short, encouraging acknowledgement from the LLM."""
    lang_instruction = "in Hindi" if language == "hi" else "in English"
    prompt = f"""You are a friendly interviewer. Give a SHORT (1 sentence only) encouraging 
acknowledgement {lang_instruction} to a blue-collar job candidate who just answered: '{answer[:200]}'.
Do not evaluate yet. Just say something like 'Thank you' briefly."""

    try:
        return chat_completion(
            messages=[{"role": "user", "content": prompt}]
        )
    except Exception:
        return "Shukriya" if language == "hi" else "Thank you."


def print_score_report(report: dict, role: str, candidate_name: str):
    """Pretty-print the evaluation report to terminal."""
    print(f"\n{Fore.CYAN}{'='*55}")
    print(f"{Fore.CYAN}  📋  INTERVIEW SCORE REPORT")
    print(f"{Fore.CYAN}{'='*55}")
    print(f"  Candidate  : {Fore.WHITE}{candidate_name}")
    print(f"  Role       : {Fore.WHITE}{role.title()}")
    print(f"  Date       : {Fore.WHITE}{datetime.now().strftime('%d %b %Y, %I:%M %p')}")
    print(f"{Fore.CYAN}{'-'*55}")

    score = report.get("overall_score", 0)
    color = Fore.GREEN if score >= 7 else (Fore.YELLOW if score >= 5 else Fore.RED)
    print(f"  Overall Score   : {color}{score}/10")
    print(f"  Communication   : {Fore.WHITE}{report.get('communication', 'N/A')}/10")
    print(f"  Domain Knowledge: {Fore.WHITE}{report.get('domain_knowledge', 'N/A')}/10")
    print(f"  Confidence      : {Fore.WHITE}{report.get('confidence', 'N/A')}/10")

    print(f"\n{Fore.CYAN}  Summary:")
    print(f"  {Fore.WHITE}{report.get('summary', '')}")

    strengths = report.get("strengths", [])
    if strengths:
        print(f"\n{Fore.GREEN}  Strengths:")
        for s in strengths:
            print(f"    ✓ {s}")

    improvements = report.get("improvements", [])
    if improvements:
        print(f"\n{Fore.YELLOW}  Areas to improve:")
        for imp in improvements:
            print(f"    • {imp}")

    hire = report.get("hire_recommendation", False)
    print(f"\n  Hire Recommendation: {Fore.GREEN + '✅ YES' if hire else Fore.RED + '❌ NO'}")
    print(f"{Fore.CYAN}{'='*55}\n")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN INTERVIEW LOOP
# ─────────────────────────────────────────────────────────────────────────────
def run_interview():
    global lang_code

    print(f"\n{Fore.CYAN}╔══════════════════════════════════════════╗")
    print(f"{Fore.CYAN}║   🎙  Blue Collar AI Interview Bot        ║")
    print(f"{Fore.CYAN}║   Powered by Sarvam AI                   ║")
    print(f"{Fore.CYAN}╚══════════════════════════════════════════╝\n")

    # ── 1. Select role ────────────────────────────────────────────────────────
    print(f"{Fore.WHITE}Select job role:")
    roles = list(QUESTION_BANK.keys())
    for i, role in enumerate(roles, 1):
        print(f"  {i}. {QUESTION_BANK[role]['title']}")

    role_idx = int(input(f"\n{Fore.GREEN}Enter number (1-{len(roles)}): {Style.RESET_ALL}")) - 1
    selected_role = roles[role_idx]

    # ── 2. Select language ────────────────────────────────────────────────────
    print(f"\n{Fore.WHITE}Select language:")
    print("  1. Hindi (हिंदी)")
    print("  2. English")
    lang_choice = input(f"{Fore.GREEN}Enter 1 or 2: {Style.RESET_ALL}").strip()
    lang = "hi" if lang_choice == "1" else "en"
    lang_code = "hi-IN" if lang == "hi" else "en-IN"

    # ── 3. Candidate name ─────────────────────────────────────────────────────
    candidate_name = input(f"\n{Fore.GREEN}Candidate name: {Style.RESET_ALL}").strip() or "Candidate"

    # ── 4. Greeting ───────────────────────────────────────────────────────────
    greeting = OPENING_MESSAGE[lang].format(role=QUESTION_BANK[selected_role]["title"])
    print(f"\n{Fore.CYAN}Bot: {greeting}")
    speak(greeting, lang_code, "greeting.wav")
    time.sleep(1)

    # ── 5. Ask questions ──────────────────────────────────────────────────────
    questions_data = QUESTION_BANK[selected_role]["questions"]
    transcripts = []
    questions_asked = []

    for i, q_data in enumerate(questions_data):
        main_question = q_data[lang]

        print(f"\n{Fore.CYAN}─── Question {i+1} of {len(questions_data)} ───")
        print(f"{Fore.WHITE}Bot: {main_question}")
        speak(main_question, lang_code, f"question_{i+1}.wav")
        time.sleep(0.5)

        # Multi-turn loop: main question + up to MAX_FOLLOW_UPS_PER_QUESTION follow-ups
        current_question = main_question
        follow_up_count = 0
        turn_label = f"{i+1}"

        while True:
            # ── Record answer ────────────────────────────────────────────────
            print(f"\n{Fore.GREEN}🎙  Your turn — please speak your answer.")
            answer = listen(turn_label)

            if answer:
                print(f"{Fore.WHITE}You said: {answer}")
                transcripts.append(answer)
            else:
                print(f"{Fore.YELLOW}(No answer recorded)")
                transcripts.append("No answer provided.")
            questions_asked.append(current_question)

            # ── Decide: follow-up or move on? ────────────────────────────────
            decision = decide_next_turn(
                role=selected_role,
                question=current_question,
                answer=answer,
                follow_up_count=follow_up_count,
                language=lang,
                max_follow_ups=MAX_FOLLOW_UPS_PER_QUESTION,
            )

            if decision["action"] == "follow_up":
                follow_up_count += 1
                current_question = decision["question"]
                turn_label = f"{i+1}_followup_{follow_up_count}"
                print(f"\n{Fore.MAGENTA}↳ Follow-up ({follow_up_count}/{MAX_FOLLOW_UPS_PER_QUESTION}):")
                print(f"{Fore.WHITE}Bot: {current_question}")
                speak(current_question, lang_code, f"followup_{i+1}_{follow_up_count}.wav")
                time.sleep(0.5)
                continue

            # ── No follow-up — acknowledge and move on ───────────────────────
            ack = get_acknowledgement(current_question, answer, lang)
            print(f"{Fore.CYAN}Bot: {ack}")
            speak(ack, lang_code, f"ack_{i+1}.wav")
            time.sleep(0.5)
            break

    # ── 6. Closing message ────────────────────────────────────────────────────
    closing = CLOSING_MESSAGE[lang]
    print(f"\n{Fore.CYAN}Bot: {closing}")
    speak(closing, lang_code, "closing.wav")

    # ── 7. Evaluate ───────────────────────────────────────────────────────────
    print(f"\n{Fore.YELLOW}⏳ Evaluating answers... please wait.")
    evaluation = evaluate_candidate(
        role=selected_role,
        questions=questions_asked,
        answers=transcripts,
        language=lang
    )

    # ── 8. Print + save report ────────────────────────────────────────────────
    print_score_report(evaluation, selected_role, candidate_name)

    report_path = OUTPUT_DIR / f"report_{candidate_name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    full_report = {
        "candidate": candidate_name,
        "role": selected_role,
        "language": lang_code,
        "date": datetime.now().isoformat(),
        "questions": questions_asked,
        "answers": transcripts,
        "evaluation": evaluation
    }
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(full_report, f, ensure_ascii=False, indent=2)

    print(f"{Fore.GREEN}✅ Report saved to: {report_path}\n")


if __name__ == "__main__":
    run_interview()
