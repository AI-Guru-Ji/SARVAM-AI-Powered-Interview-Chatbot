"""
streamlit_app.py — Web UI for the Blue Collar Interview Bot.

Run:
    streamlit run streamlit_app.py

Requires (in addition to requirements.txt):
    pip install streamlit>=1.42
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime
from typing import Optional

import streamlit as st
from audio_recorder_streamlit import audio_recorder

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from utils.sarvam_api import (
    speech_to_text,
    text_to_speech,
    evaluate_candidate,
    decide_next_turn,
    run_health_check,
)
from utils.profile_builder import (
    build_profile_json,
    build_resume_text,
    build_resume_pdf,
    _count_populated_fields,
)
from data.question_bank import (
    QUESTION_BANK,
    OPENING_MESSAGE,
    CLOSING_MESSAGE,
    LANGUAGES,
)
from data.profile_questions import (
    PROFILE_QUESTIONS,
    PROFILE_INTRO,
    PROFILE_OUTRO,
)


# ─────────────────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────────────────
MAX_FOLLOW_UPS_PER_QUESTION = 1
SILENCE_PAUSE_SECONDS = 3   # auto-stop after this much continuous silence
TEMP_DIR = ROOT / "output" / "temp"
TEMP_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR = ROOT / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ─────────────────────────────────────────────────────────────────────────────
# PAGE
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Blue-Collar Multilingual Voice Interview Bot",
    page_icon="🎙",
    layout="centered",
)

# ─────────────────────────────────────────────────────────────────────────────
# AVATARS & STYLE
# ─────────────────────────────────────────────────────────────────────────────
BOT_AVATAR_URL = (
    "https://api.dicebear.com/7.x/bottts-neutral/svg"
    "?seed=Recruiter&backgroundColor=4f8ef7&radius=50"
)


def candidate_avatar_url(name: str) -> str:
    """Generate a unique cartoon avatar from candidate's name."""
    seed = (name or "Candidate").replace(" ", "-")
    return (
        f"https://api.dicebear.com/7.x/avataaars/svg?seed={seed}"
        "&backgroundColor=b6e3f4,c0aede,d1d4f9,ffd5dc,ffdfbf"
    )


# Inject custom CSS once per page load
st.markdown(
    """
    <style>
    /* Chat bubbles */
    [data-testid="stChatMessage"] {
        border-radius: 14px !important;
        padding: 14px !important;
        margin-bottom: 10px !important;
        box-shadow: 0 1px 3px rgba(0,0,0,0.06);
    }
    /* Bot bubble — soft blue */
    [data-testid="stChatMessage"]:has(img[src*="bottts"]) {
        background: linear-gradient(135deg, rgba(79,142,247,0.10), rgba(79,142,247,0.04)) !important;
        border-left: 3px solid #4f8ef7 !important;
    }
    /* Candidate bubble — soft green */
    [data-testid="stChatMessage"]:has(img[src*="avataaars"]) {
        background: linear-gradient(135deg, rgba(46,204,113,0.10), rgba(46,204,113,0.04)) !important;
        border-left: 3px solid #2ecc71 !important;
    }
    /* Avatar size */
    [data-testid="stChatMessage"] img {
        border-radius: 50% !important;
        width: 42px !important;
        height: 42px !important;
        background: white;
        box-shadow: 0 1px 3px rgba(0,0,0,0.10);
    }
    /* Pulsing live indicator */
    .pulse-dot {
        display: inline-block;
        width: 10px;
        height: 10px;
        background: #e74c3c;
        border-radius: 50%;
        margin-right: 6px;
        animation: pulse 1.4s infinite;
    }
    @keyframes pulse {
        0%, 100% { opacity: 1; transform: scale(1); }
        50% { opacity: 0.4; transform: scale(1.25); }
    }
    /* "Your turn" callout */
    .your-turn-banner {
        text-align: center;
        padding: 14px;
        background: linear-gradient(135deg, #2ecc71, #27ae60);
        color: white;
        border-radius: 10px;
        margin: 12px 0;
        font-weight: 600;
        font-size: 1.05rem;
        box-shadow: 0 2px 8px rgba(46,204,113,0.35);
        animation: pulse-banner 2s infinite;
    }
    @keyframes pulse-banner {
        0%, 100% { box-shadow: 0 2px 8px rgba(46,204,113,0.35); }
        50% { box-shadow: 0 2px 18px rgba(46,204,113,0.6); }
    }
    /* "Bot speaking" caption */
    .bot-speaking {
        color: #4f8ef7;
        font-size: 1.0rem;
        font-style: italic;
    }

    /* ──────────────────────────────────────────────────────────────────
       Senior-friendly font sizing — defaults are too small for older
       blue-collar candidates to read comfortably. Bump everything up.
       ────────────────────────────────────────────────────────────── */

    /* Base body text */
    html, body, [class*="st-"], .stApp, .main, .block-container {
        font-size: 19px !important;
        line-height: 1.55 !important;
    }
    /* Page titles (st.title) */
    h1, .stMarkdown h1 {
        font-size: 2.4rem !important;
        line-height: 1.2 !important;
    }
    h2, .stMarkdown h2 { font-size: 1.9rem !important; }
    h3, .stMarkdown h3 { font-size: 1.5rem !important; }
    /* Paragraph + markdown body */
    p, .stMarkdown p, .stMarkdown li {
        font-size: 1.15rem !important;
        line-height: 1.6 !important;
    }
    /* Captions — keep slightly smaller but still readable */
    .stCaption, [data-testid="stCaptionContainer"] {
        font-size: 1.0rem !important;
    }
    /* Buttons */
    .stButton button, .stDownloadButton button, .stFormSubmitButton button {
        font-size: 1.2rem !important;
        font-weight: 600 !important;
        padding: 12px 18px !important;
    }
    /* Text inputs and select boxes */
    .stTextInput input, .stSelectbox div[data-baseweb="select"] {
        font-size: 1.15rem !important;
    }
    .stTextInput label, .stSelectbox label {
        font-size: 1.1rem !important;
        font-weight: 600 !important;
    }
    /* Chat message bubbles (bot/candidate dialogue) */
    [data-testid="stChatMessage"] p,
    [data-testid="stChatMessage"] li,
    [data-testid="stChatMessage"] .stMarkdown {
        font-size: 1.2rem !important;
        line-height: 1.55 !important;
    }
    [data-testid="stChatMessage"] strong {
        font-size: 1.25rem !important;
    }
    /* "Your turn" banner — make it easy to spot */
    .your-turn-banner {
        font-size: 1.2rem !important;
    }
    /* Status panel (the profile-building progress block) */
    [data-testid="stStatusWidget"] p,
    [data-testid="stStatusWidget"] div {
        font-size: 1.1rem !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ─────────────────────────────────────────────────────────────────────────────
# SESSION STATE
# ─────────────────────────────────────────────────────────────────────────────
def init_state():
    defaults = {
        # setup | profile_intro | profile | profile_building | profile_review
        # | greeting | interview | closing | evaluating | report
        "stage": "setup",
        "role": None,
        "lang": "en",
        "lang_code": "en-IN",
        "candidate_name": "",
        "question_idx": 0,
        "follow_up_count": 0,
        "current_question": "",
        "current_question_audio": None,   # bytes for st.audio()
        "questions_asked": [],
        "transcripts": [],
        "evaluation": None,
        "report_saved_path": None,
        "greeting_text": "",
        "greeting_audio": None,
        "closing_text": "",
        "closing_audio": None,
        # Profile (pre-interview onboarding) state
        "profile_intro_text": "",
        "profile_intro_audio": None,
        "profile_q_idx": 0,
        "profile_current_audio": None,    # TTS bytes for the current profile question
        "profile_transcripts": [],        # list of {"field","question","answer"}
        "profile_json": None,             # populated after build_profile()
        "profile_resume": None,           # populated after build_profile()
        "profile_resume_pdf": None,       # PDF bytes for download button
        "profile_saved_paths": None,      # (json_path, pdf_path)
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


init_state()


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────
def generate_tts(text: str) -> Optional[bytes]:
    """Generate TTS audio and return raw WAV bytes (None on failure)."""
    try:
        path = TEMP_DIR / f"tts_{abs(hash(text)) % 10**8}.wav"
        text_to_speech(text, str(path), language_code=st.session_state.lang_code)
        return path.read_bytes()
    except Exception as e:
        st.warning(f"TTS failed: {e}")
        return None


def transcribe(audio_bytes: bytes) -> Optional[str]:
    """Save raw WAV bytes to disk and run STT.

    Returns:
        - str: transcript (possibly empty if the candidate stayed silent)
        - None: STT call failed — the caller should let the user re-record
                instead of advancing.
    """
    wav_path = (
        TEMP_DIR
        / f"answer_{st.session_state.question_idx}_{st.session_state.follow_up_count}.wav"
    )
    with open(wav_path, "wb") as f:
        f.write(audio_bytes)
    try:
        return speech_to_text(str(wav_path), language_code=st.session_state.lang_code)
    except Exception as e:
        msg = str(e)
        if "Audio too short" in msg:
            st.error(
                "🎙 The microphone didn't capture any sound. "
                "Check that your browser has mic permission "
                "(look for the 🎙 icon in the address bar), then click the mic and try again."
            )
        else:
            st.error(f"STT failed: {e}")
        return None


def set_current_question(text: str):
    st.session_state.current_question = text
    with st.spinner("🔊 Generating audio..."):
        st.session_state.current_question_audio = generate_tts(text)


def advance_to_main_question(idx: int):
    questions = QUESTION_BANK[st.session_state.role]["questions"]
    if idx >= len(questions):
        # All questions done → go to closing stage (play farewell audio)
        closing_text = CLOSING_MESSAGE[st.session_state.lang]
        st.session_state.closing_text = closing_text
        with st.spinner("🔊 Preparing closing message..."):
            st.session_state.closing_audio = generate_tts(closing_text)
        st.session_state.stage = "closing"
        return
    st.session_state.question_idx = idx
    st.session_state.follow_up_count = 0
    set_current_question(questions[idx][st.session_state.lang])


def reset_all():
    for k in list(st.session_state.keys()):
        del st.session_state[k]


def _profile_prompt(idx: int) -> str:
    """Return the localized profile question text at index ``idx`` with the
    `{role}` placeholder substituted with the candidate's applied role
    (e.g. "Housekeeping"). Use this everywhere the bot reads a profile
    question — never index PROFILE_QUESTIONS directly.
    """
    role_title = QUESTION_BANK[st.session_state.role]["title"]
    raw = PROFILE_QUESTIONS[idx]["prompts"][st.session_state.lang]
    # Only the experience_years question (Q5) uses {role}, but format() is
    # a safe no-op on prompts that don't contain it.
    try:
        return raw.format(role=role_title)
    except (KeyError, IndexError):
        return raw


# ─────────────────────────────────────────────────────────────────────────────
# STAGE: SETUP
# ─────────────────────────────────────────────────────────────────────────────
def render_setup():
    st.title("🎙 Blue Collar Interview Bot")
    st.caption("Powered by Sarvam AI")

    with st.form("setup_form"):
        col1, col2 = st.columns(2)
        with col1:
            role_keys = list(QUESTION_BANK.keys())
            role_titles = [QUESTION_BANK[r]["title"] for r in role_keys]
            role_pick = st.selectbox("Select role", role_titles)
            role = role_keys[role_titles.index(role_pick)]
        with col2:
            lang_pick = st.selectbox("Language", list(LANGUAGES.keys()))
            lang, lang_code = LANGUAGES[lang_pick]

        candidate_name = st.text_input(
            "Candidate name", placeholder="e.g. Ramesh Babu"
        )

        submitted = st.form_submit_button(
            "Start Profile Building ▶", use_container_width=True, type="primary"
        )

    # ── Pre-demo health check ────────────────────────────────────────────
    # A collapsible panel for the recruiter to verify Sarvam APIs are
    # healthy BEFORE introducing the candidate. Catches outages, expired
    # keys, or slow days early so you don't discover them mid-demo.
    with st.expander("🔍 System Health Check (run before live demo)", expanded=False):
        st.caption(
            "Quickly probes Sarvam's TTS and LLM endpoints with tiny "
            "payloads to confirm everything is responsive. Takes ~5–10 seconds."
        )
        if st.button("▶  Run health check", key="run_health_check_btn"):
            with st.spinner("Probing Sarvam APIs…"):
                results = run_health_check()
            all_ok = all(r["ok"] for r in results)
            if all_ok:
                st.success("✅  All systems responsive — ready for demo.")
            else:
                st.error("⚠️  One or more checks failed. Review the details below before starting.")
            for r in results:
                icon = "✅" if r["ok"] else "❌"
                latency = f"  ({r['latency_s']:.1f}s)" if r["latency_s"] else ""
                st.markdown(
                    f"**{icon}  {r['name']}**{latency}  \n"
                    f"<span style='color:#666;'>{r['detail']}</span>",
                    unsafe_allow_html=True,
                )

    if submitted:
        if not candidate_name.strip():
            st.error("Please enter the candidate's name.")
            return
        st.session_state.role = role
        st.session_state.lang = lang
        st.session_state.lang_code = lang_code
        st.session_state.candidate_name = candidate_name.strip()
        # First stop is the friendly onboarding chat, then the interview.
        st.session_state.stage = "profile_intro"

        # Pre-generate the onboarding intro audio so it autoplays smoothly.
        intro_text = PROFILE_INTRO[lang].format(name=candidate_name.strip())
        st.session_state.profile_intro_text = intro_text
        with st.spinner("🔊 Preparing your warm welcome…"):
            st.session_state.profile_intro_audio = generate_tts(intro_text)

        # Pre-generate the interview greeting too — it'll autoplay after the
        # profile section is complete.
        greeting_text = OPENING_MESSAGE[lang].format(
            role=QUESTION_BANK[role]["title"]
        )
        st.session_state.greeting_text = greeting_text
        with st.spinner("🔊 Preparing interview greeting…"):
            st.session_state.greeting_audio = generate_tts(greeting_text)
        st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# STAGE: PROFILE INTRO (warm onboarding welcome)
# ─────────────────────────────────────────────────────────────────────────────
def render_profile_intro():
    """Friendly bubble + autoplay TTS introducing the onboarding section."""
    role_title = QUESTION_BANK[st.session_state.role]["title"]

    col_l, col_m, col_r = st.columns([2, 3, 2])
    with col_l:
        st.image(candidate_avatar_url(st.session_state.candidate_name), width=44)
        st.markdown(f"**{st.session_state.candidate_name}**")
        st.caption(role_title)
    with col_m:
        st.progress(0.0, text="Getting to know you")
    with col_r:
        st.markdown(
            "<div style='text-align:right; font-weight:600;'>"
            "<span class='pulse-dot'></span>"
            "ONBOARDING"
            "</div>",
            unsafe_allow_html=True,
        )
    st.divider()

    with st.chat_message("assistant", avatar=BOT_AVATAR_URL):
        st.markdown(f"**{st.session_state.profile_intro_text}**")
        if st.session_state.profile_intro_audio:
            played = st.session_state.get("profile_intro_played", False)
            st.audio(
                st.session_state.profile_intro_audio,
                format="audio/wav",
                autoplay=not played,
            )
            st.session_state.profile_intro_played = True

    st.markdown("&nbsp;")
    if st.button(
        "▶  Begin",
        type="primary",
        use_container_width=True,
    ):
        st.session_state.stage = "profile"
        st.session_state.profile_q_idx = 0
        # Pre-render TTS for the first question
        first_q_text = _profile_prompt(0)
        with st.spinner("🔊 Generating audio..."):
            st.session_state.profile_current_audio = generate_tts(first_q_text)
        st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# STAGE: PROFILE (conversational Q&A onboarding loop)
# ─────────────────────────────────────────────────────────────────────────────
def render_profile():
    questions = PROFILE_QUESTIONS
    total = len(questions)
    idx = st.session_state.profile_q_idx

    role_title = QUESTION_BANK[st.session_state.role]["title"]

    # Top bar
    col_l, col_m, col_r = st.columns([2, 3, 2])
    with col_l:
        st.image(candidate_avatar_url(st.session_state.candidate_name), width=44)
        st.markdown(f"**{st.session_state.candidate_name}**")
        st.caption(role_title)
    with col_m:
        st.progress(idx / total, text=f"About you — {idx + 1} of {total}")
    with col_r:
        st.markdown(
            "<div style='text-align:right; font-weight:600;'>"
            "<span class='pulse-dot'></span>"
            "ONBOARDING"
            "</div>",
            unsafe_allow_html=True,
        )
    st.divider()

    # Past Q&A history
    for turn in st.session_state.profile_transcripts:
        with st.chat_message("assistant", avatar=BOT_AVATAR_URL):
            st.markdown(turn["question"])
        with st.chat_message(
            "user",
            avatar=candidate_avatar_url(st.session_state.candidate_name),
        ):
            st.markdown(turn["answer"] if turn["answer"] else "_(skipped)_")

    # Current question bubble
    current_q_text = _profile_prompt(idx)
    with st.chat_message("assistant", avatar=BOT_AVATAR_URL):
        st.markdown(
            "<span class='bot-speaking'>🔊 AI Assistant is asking…</span>",
            unsafe_allow_html=True,
        )
        st.markdown(f"**{current_q_text}**")
        if st.session_state.profile_current_audio:
            play_flag = f"profile_played_{idx}"
            should_autoplay = not st.session_state.get(play_flag, False)
            st.audio(
                st.session_state.profile_current_audio,
                format="audio/wav",
                autoplay=should_autoplay,
            )
            st.session_state[play_flag] = True

    # Your-turn banner
    st.markdown(
        f"<div class='your-turn-banner'>"
        f"🎙 YOUR TURN — click the mic, then speak. "
        f"Recording auto-stops after {SILENCE_PAUSE_SECONDS:.1f}s of silence."
        f"</div>",
        unsafe_allow_html=True,
    )

    # Mic + auto-submit (same widget config as the interview stage)
    MIN_REAL_AUDIO_BYTES = 6_000
    with st.chat_message(
        "user",
        avatar=candidate_avatar_url(st.session_state.candidate_name),
    ):
        c1, c2, c3 = st.columns([1, 2, 1])
        with c2:
            audio_bytes = audio_recorder(
                text="",
                energy_threshold=(0.01, 0.05),
                pause_threshold=SILENCE_PAUSE_SECONDS,
                sample_rate=16_000,
                neutral_color="#4f8ef7",
                recording_color="#e74c3c",
                icon_name="microphone",
                icon_size="3x",
                key=f"profile_recorder_{idx}",
            )

        if audio_bytes and len(audio_bytes) >= MIN_REAL_AUDIO_BYTES:
            audio_hash = hash(audio_bytes)
            processed_key = f"profile_processed_{idx}"

            if st.session_state.get(processed_key) != audio_hash:
                st.session_state[processed_key] = audio_hash

                with st.spinner("📝 Transcribing…"):
                    answer = transcribe(audio_bytes)
                if answer is None:
                    st.stop()

                clean = (answer or "").strip()
                if clean:
                    # Real answer captured → store and advance.
                    st.session_state.profile_transcripts.append({
                        "field": questions[idx]["field"],
                        "question": current_q_text,
                        "answer": clean,
                    })
                    if idx + 1 >= total:
                        st.session_state.stage = "profile_building"
                    else:
                        st.session_state.profile_q_idx = idx + 1
                        next_q_text = _profile_prompt(idx + 1)
                        with st.spinner("🔊 Preparing next question…"):
                            st.session_state.profile_current_audio = generate_tts(next_q_text)
                    st.rerun()
                else:
                    # STT returned an empty transcript — the mic captured
                    # silence or background noise. Don't advance silently
                    # (otherwise the whole profile becomes null). Flag it
                    # so the next render shows Retry / Skip controls.
                    st.session_state[f"profile_empty_{idx}"] = True
                    st.rerun()

    # If the last capture for this question was empty, show a clear
    # warning with Retry / Skip choices instead of letting the candidate
    # accidentally walk away with a fully-null profile.
    if st.session_state.get(f"profile_empty_{idx}"):
        st.warning(
            "🎙 I couldn't hear an answer. Please click the mic and speak "
            "clearly, or skip this question if you'd rather not answer."
        )
        col_retry, col_skip = st.columns(2)
        with col_retry:
            if st.button(
                "🔁 Try again",
                use_container_width=True,
                key=f"retry_{idx}",
            ):
                # Clear the empty flag AND the processed dedup so the next
                # mic click is treated as a fresh recording.
                st.session_state.pop(f"profile_empty_{idx}", None)
                st.session_state.pop(f"profile_processed_{idx}", None)
                st.rerun()
        with col_skip:
            if st.button(
                "⏭ Skip this question",
                use_container_width=True,
                key=f"skip_{idx}",
            ):
                st.session_state.pop(f"profile_empty_{idx}", None)
                st.session_state.profile_transcripts.append({
                    "field": questions[idx]["field"],
                    "question": current_q_text,
                    "answer": "",
                })
                if idx + 1 >= total:
                    st.session_state.stage = "profile_building"
                else:
                    st.session_state.profile_q_idx = idx + 1
                    next_q_text = _profile_prompt(idx + 1)
                    with st.spinner("🔊 Preparing next question…"):
                        st.session_state.profile_current_audio = generate_tts(next_q_text)
                st.rerun()

    # Sidebar
    with st.sidebar:
        st.markdown("### 👋 Onboarding")
        st.caption(f"Candidate: **{st.session_state.candidate_name}**")
        st.caption(f"Role: **{role_title}**")
        st.caption(f"Language: **{st.session_state.lang_code}**")
        st.divider()
        st.markdown("**Progress**")
        st.caption(f"Question {idx + 1} / {total}")
        st.divider()
        if st.button("❌ Abort", use_container_width=True):
            reset_all()
            st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# STAGE: PROFILE BUILDING (calls the LLM to generate JSON + resume)
# ─────────────────────────────────────────────────────────────────────────────
def render_profile_building():
    st.title("✨ Building your profile…")
    st.caption("Turning your answers into a structured profile and a resume.")

    qa_pairs = [
        (t["question"], t["answer"])
        for t in st.session_state.profile_transcripts
    ]

    # Guard: if every answer is empty, calling the LLM just produces a
    # fully-null profile (which is what the user saw with candidate
    # "sdfgddg"). Surface this clearly and let them retry the onboarding
    # instead of paying for a useless LLM call.
    if not any(a and a.strip() for _, a in qa_pairs):
        st.error(
            "We didn't capture any answers during onboarding — every "
            "recording came through empty. Please redo the onboarding "
            "and speak clearly into the microphone."
        )
        col_redo, col_skip = st.columns(2)
        with col_redo:
            if st.button("🔁 Redo onboarding", type="primary", use_container_width=True):
                st.session_state.profile_transcripts = []
                st.session_state.profile_q_idx = 0
                # Clear any per-question dedup / empty flags so each
                # question accepts a fresh recording.
                for k in list(st.session_state.keys()):
                    if k.startswith("profile_processed_") or k.startswith("profile_empty_") or k.startswith("profile_played_"):
                        del st.session_state[k]
                first_q_text = _profile_prompt(0)
                with st.spinner("🔊 Generating audio..."):
                    st.session_state.profile_current_audio = generate_tts(first_q_text)
                st.session_state.stage = "profile"
                st.rerun()
        with col_skip:
            if st.button("Skip profile, go to interview", use_container_width=True):
                st.session_state.stage = "greeting"
                st.rerun()
        return

    # Big animated icon + reassurance line. Keeps the candidate engaged
    # during the ~15-25s of LLM work that follows.
    st.markdown(
        """
        <div style="text-align:center; padding:20px 0;">
            <div style="font-size:96px; animation:pulse-icon 1.6s ease-in-out infinite;">⚙️</div>
            <p style="color:#666; margin-top:8px; font-size:0.95rem;">
                Please stay on this page — we're putting your profile together.
            </p>
        </div>
        <style>
        @keyframes pulse-icon {
            0%, 100% { transform: scale(1); opacity: 1; }
            50%      { transform: scale(1.18); opacity: 0.75; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # Step-by-step live status — gives the candidate a sense of progress
    # rather than a single opaque spinner. Calls the two underlying
    # builders separately so each step's spinner reflects real work.
    try:
        with st.status("✨ Building your candidate profile…", expanded=True) as status:
            st.write(f"📥  Captured {len(qa_pairs)} answers from your onboarding chat.")

            st.write("📝  Extracting structured details (name, education, skills, …) …")
            profile = build_profile_json(
                candidate_name=st.session_state.candidate_name,
                role=st.session_state.role,
                language=st.session_state.lang,
                qa_pairs=qa_pairs,
            )
            populated = _count_populated_fields(profile)
            st.write(f"✓  Extracted {populated} fields from your answers.")

            st.write("📃  Formatting your 1-page resume …")
            resume = build_resume_text(profile)
            st.write("✓  Resume ready.")

            status.update(label="✅ All ready!", state="complete", expanded=False)

        # If the JSON came back nearly empty even though the candidate
        # answered, surface that clearly instead of showing a sparse resume
        # silently. The raw LLM response is saved to output/debug/ for
        # inspection.
        if populated < 3 and any(a and a.strip() for _, a in qa_pairs):
            st.warning(
                f"⚠️ Only {populated} field(s) were extracted from your answers. "
                "The profile may look sparse. Check `output/debug/` for the raw "
                "LLM response if you want to investigate, or redo onboarding."
            )
    except Exception as e:
        st.error(f"Could not build profile: {e}")
        if st.button("Continue to interview anyway"):
            st.session_state.stage = "greeting"
            st.rerun()
        return

    st.session_state.profile_json = profile
    st.session_state.profile_resume = resume

    # Render the PDF once (used by the download button + persisted to disk).
    pdf_bytes = build_resume_pdf(resume, candidate_name=st.session_state.candidate_name)
    st.session_state.profile_resume_pdf = pdf_bytes

    # Persist all three artefacts to disk.
    safe_name = st.session_state.candidate_name.replace(" ", "_")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = OUTPUT_DIR / f"profile_{safe_name}_{ts}.json"
    pdf_path = OUTPUT_DIR / f"resume_{safe_name}_{ts}.pdf"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(profile, f, ensure_ascii=False, indent=2)
    with open(pdf_path, "wb") as f:
        f.write(pdf_bytes)
    st.session_state.profile_saved_paths = (str(json_path), str(pdf_path))

    st.session_state.stage = "profile_review"
    st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# STAGE: PROFILE REVIEW (shows JSON + resume before the interview starts)
# ─────────────────────────────────────────────────────────────────────────────
def render_profile_review():
    role_title = QUESTION_BANK[st.session_state.role]["title"]
    profile = st.session_state.profile_json
    resume = st.session_state.profile_resume
    pdf_bytes = st.session_state.get("profile_resume_pdf")
    json_path, pdf_path = st.session_state.profile_saved_paths or (None, None)

    col_l, col_m, col_r = st.columns([2, 3, 2])
    with col_l:
        st.image(candidate_avatar_url(st.session_state.candidate_name), width=44)
        st.markdown(f"**{st.session_state.candidate_name}**")
        st.caption(role_title)
    with col_m:
        st.progress(1.0, text="Profile ready")
    with col_r:
        st.markdown(
            "<div style='text-align:right; font-weight:600; color:#2ecc71;'>"
            "✓ PROFILE BUILT"
            "</div>",
            unsafe_allow_html=True,
        )
    st.divider()

    st.title(f"📄 {st.session_state.candidate_name}")
    st.caption("Here's your resume. Review it and click Continue when ready for the interview.")

    # Pretty card-based resume rendering. The structured JSON is still
    # saved to disk (and available via the download button below); it's
    # only the on-screen JSON tree that's been removed for cleaner UX.
    _render_pretty_resume(resume)

    st.markdown("&nbsp;")
    col_dl_pdf, col_dl_json = st.columns(2)
    with col_dl_pdf:
        if pdf_bytes and pdf_path:
            st.download_button(
                "⬇  Download resume (.pdf)",
                data=pdf_bytes,
                file_name=Path(pdf_path).name,
                mime="application/pdf",
                use_container_width=True,
                type="primary",
            )
    with col_dl_json:
        if json_path:
            st.download_button(
                "⬇  Download structured data (.json)",
                data=json.dumps(profile, ensure_ascii=False, indent=2),
                file_name=Path(json_path).name,
                mime="application/json",
                use_container_width=True,
            )

    st.markdown("&nbsp;")
    if st.button(
        "▶  Continue to Interview",
        type="primary",
        use_container_width=True,
    ):
        st.session_state.stage = "greeting"
        st.rerun()


# Map resume section titles → (icon, accent colour) for the pretty card
# renderer. Matches the section names the LLM resume prompt produces;
# any unrecognised section falls back to a default style.
_RESUME_SECTION_STYLE = {
    "professional summary":      ("📋", "#4f8ef7"),
    "summary":                   ("📋", "#4f8ef7"),
    "work experience":           ("💼", "#2ecc71"),
    "experience":                ("💼", "#2ecc71"),
    "education & certifications":("🎓", "#9b59b6"),
    "education and certifications":("🎓", "#9b59b6"),
    "education":                 ("🎓", "#9b59b6"),
    "core skills & tools":       ("🔧", "#e67e22"),
    "skills & tools":            ("🔧", "#e67e22"),
    "skills and tools":          ("🔧", "#e67e22"),
    "core skills":               ("🔧", "#e67e22"),
    "skills":                    ("🔧", "#e67e22"),
    "languages known":           ("🗣", "#16a085"),
    "languages":                 ("🗣", "#16a085"),
    "objective":                 ("🎯", "#4f8ef7"),
}


def _parse_resume_sections(resume_text: str):
    """Split the resume text into (header_lines, [(title, icon, colour, body_lines)])."""
    lines = resume_text.splitlines()
    header: list[str] = []
    sections: list[tuple[str, str, str, list[str]]] = []
    current: tuple[str, str, str, list[str]] | None = None

    def normalize(s: str) -> str:
        return s.strip().rstrip(":").strip().lower()

    for raw in lines:
        norm = normalize(raw)
        if norm and norm in _RESUME_SECTION_STYLE:
            if current is not None:
                sections.append(current)
            icon, colour = _RESUME_SECTION_STYLE[norm]
            current = (raw.strip().rstrip(":"), icon, colour, [])
        elif current is None:
            if raw.strip():
                header.append(raw.strip())
        else:
            current[3].append(raw)

    if current is not None:
        sections.append(current)
    return header, sections


def _render_pretty_resume(resume_text: str):
    """Render the resume as a series of colour-accented Streamlit cards."""
    import html as _html
    header, sections = _parse_resume_sections(resume_text)

    # Header card (name + contact placeholders)
    name = header[0] if header else "Candidate"
    contact_lines = header[1:] if len(header) > 1 else []
    contact_html = "<br>".join(_html.escape(l) for l in contact_lines) or "&nbsp;"
    st.markdown(
        f"""
        <div style="
            background: linear-gradient(135deg, #4f8ef7 0%, #6a5acd 100%);
            color: white; padding: 26px 28px; border-radius: 12px;
            box-shadow: 0 4px 12px rgba(79,142,247,0.25);
            margin-bottom: 16px;
        ">
            <div style="font-size: 2.1rem; font-weight: 700; letter-spacing: 0.5px;">
                {_html.escape(name)}
            </div>
            <div style="opacity: 0.95; margin-top: 8px; font-size: 1.15rem;">
                {contact_html}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # One card per section
    if not sections:
        # No recognisable sections — fall back to plain monospace dump so
        # the candidate still sees the resume content.
        st.code(resume_text, language="text")
        return

    for title, icon, colour, body in sections:
        body_clean = [l for l in body if l.strip() or True]
        # Trim leading/trailing blank lines inside the section
        while body_clean and not body_clean[0].strip():
            body_clean.pop(0)
        while body_clean and not body_clean[-1].strip():
            body_clean.pop()
        body_html_parts = []
        for ln in body_clean:
            if not ln.strip():
                body_html_parts.append("<div style='height:6px;'></div>")
                continue
            escaped = _html.escape(ln.rstrip())
            # Indent bullet lines slightly more for hierarchy.
            if ln.lstrip().startswith(("-", "•", "*")):
                body_html_parts.append(
                    f"<div style='margin-left:14px; padding:2px 0; color:#333;'>"
                    f"<span style='color:{colour}; margin-right:6px;'>•</span>"
                    f"{escaped.lstrip()[1:].lstrip()}</div>"
                )
            else:
                body_html_parts.append(
                    f"<div style='padding:2px 0; color:#333;'>{escaped}</div>"
                )
        body_html = "\n".join(body_html_parts)
        st.markdown(
            f"""
            <div style="
                background: white;
                border-left: 5px solid {colour};
                border-radius: 8px;
                padding: 16px 20px;
                margin-bottom: 12px;
                box-shadow: 0 2px 6px rgba(0,0,0,0.06);
                transition: box-shadow 0.2s ease, transform 0.2s ease;
            "
            onmouseover="this.style.boxShadow='0 4px 14px rgba(0,0,0,0.12)';this.style.transform='translateY(-1px)';"
            onmouseout="this.style.boxShadow='0 2px 6px rgba(0,0,0,0.06)';this.style.transform='translateY(0)';"
            >
                <div style="
                    font-size: 1.3rem; font-weight: 700; color: {colour};
                    margin-bottom: 10px; text-transform: uppercase; letter-spacing: 0.5px;
                ">
                    <span style="margin-right:6px;">{icon}</span>{_html.escape(title)}
                </div>
                <div style="font-size: 1.15rem; line-height: 1.65;">
                    {body_html}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


# ─────────────────────────────────────────────────────────────────────────────
# STAGE: GREETING
# ─────────────────────────────────────────────────────────────────────────────
def render_greeting():
    role_title = QUESTION_BANK[st.session_state.role]["title"]

    col_l, col_m, col_r = st.columns([2, 3, 2])
    with col_l:
        st.image(candidate_avatar_url(st.session_state.candidate_name), width=44)
        st.markdown(f"**{st.session_state.candidate_name}**")
        st.caption(role_title)
    with col_m:
        st.progress(0.0, text="Welcome")
    with col_r:
        st.markdown(
            "<div style='text-align:right; font-weight:600;'>"
            "<span class='pulse-dot'></span>"
            "LIVE Interview"
            "</div>",
            unsafe_allow_html=True,
        )
    st.divider()

    # Greeting bubble — autoplay
    with st.chat_message("assistant", avatar=BOT_AVATAR_URL):
        st.markdown(f"**{st.session_state.greeting_text}**")
        if st.session_state.greeting_audio:
            should_autoplay = not st.session_state.get("greeting_played", False)
            st.audio(
                st.session_state.greeting_audio,
                format="audio/wav",
                autoplay=should_autoplay,
            )
            st.session_state.greeting_played = True

    st.markdown("&nbsp;")
    if st.button(
        "▶  Begin First Question",
        type="primary",
        use_container_width=True,
    ):
        st.session_state.stage = "interview"
        advance_to_main_question(0)
        st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# STAGE: INTERVIEW (chat-style, autoplay, auto-submit)
# ─────────────────────────────────────────────────────────────────────────────
def render_interview():
    questions = QUESTION_BANK[st.session_state.role]["questions"]
    total = len(questions)
    idx = st.session_state.question_idx
    fc = st.session_state.follow_up_count

    # ── Top bar ──────────────────────────────────────────────────────────────
    col_l, col_m, col_r = st.columns([2, 3, 2])
    with col_l:
        st.image(candidate_avatar_url(st.session_state.candidate_name), width=44)
        st.markdown(f"**{st.session_state.candidate_name}**")
        st.caption(QUESTION_BANK[st.session_state.role]["title"])
    with col_m:
        st.progress(idx / total, text=f"Question {idx + 1} of {total}")
    with col_r:
        st.markdown(
            "<div style='text-align:right; font-weight:600;'>"
            "<span class='pulse-dot'></span>"
            "LIVE Interview"
            "</div>",
            unsafe_allow_html=True,
        )
    st.divider()

    # ── Past turns (chat history) ────────────────────────────────────────────
    past_turns = list(
        zip(
            st.session_state.questions_asked,
            st.session_state.transcripts,
        )
    )
    # Render history (all completed turns)
    for q, a in past_turns:
        with st.chat_message("assistant", avatar=BOT_AVATAR_URL):
            st.markdown(q)
        with st.chat_message("user", avatar=candidate_avatar_url(st.session_state.candidate_name)):
            st.markdown(a if a else "_(no answer)_")

    # ── Current question (the one we're waiting on) ──────────────────────────
    with st.chat_message("assistant", avatar=BOT_AVATAR_URL):
        if fc > 0:
            st.caption(f"↳ Follow-up {fc} of {MAX_FOLLOW_UPS_PER_QUESTION}")
        st.markdown(
            "<span class='bot-speaking'>🔊 AI Recruiter is asking…</span>",
            unsafe_allow_html=True,
        )
        st.markdown(f"**{st.session_state.current_question}**")

        if st.session_state.current_question_audio:
            play_flag = f"played_{idx}_{fc}"
            should_autoplay = not st.session_state.get(play_flag, False)
            st.audio(
                st.session_state.current_question_audio,
                format="audio/wav",
                autoplay=should_autoplay,
            )
            st.session_state[play_flag] = True

    # ── "Your turn" pulsing banner ───────────────────────────────────────────
    st.markdown(
        f"<div class='your-turn-banner'>"
        f"🎙 YOUR TURN — click the mic, then speak. "
        f"Recording auto-stops after {SILENCE_PAUSE_SECONDS:.1f}s of silence."
        f"</div>",
        unsafe_allow_html=True,
    )

    # ── User's turn (mic + silence auto-stop + auto-submit) ──────────────────
    with st.chat_message("user", avatar=candidate_avatar_url(st.session_state.candidate_name)):
        # Center the mic button with columns
        c1, c2, c3 = st.columns([1, 2, 1])
        with c2:
            audio_bytes = audio_recorder(
                text="",
                # Silence detection. The library's default (-1.0, 1.0) often
                # never triggers because background noise stays above it.
                # Tuple is (silence_threshold, speech_threshold):
                #   - audio energy BELOW silence_threshold → counts as silence
                #   - audio energy ABOVE speech_threshold → counts as speech
                # Lower numbers = more sensitive to silence (will stop sooner).
                # Raise these if your room is noisy and it stops too early.
                energy_threshold=(0.01, 0.05),
                pause_threshold=SILENCE_PAUSE_SECONDS,
                sample_rate=16_000,           # matches Sarvam STT preferred rate
                neutral_color="#4f8ef7",      # blue when idle
                recording_color="#e74c3c",    # red while listening
                icon_name="microphone",
                icon_size="3x",
                key=f"recorder_{idx}_{fc}",
            )

        # The audio_recorder widget sometimes returns a header-only WAV (~44
        # bytes) on first render of a new question — before the user has
        # actually clicked. Ignore those silently so the user doesn't see a
        # spurious "mic didn't capture sound" error. 16 kHz mono PCM is
        # ≈32 KB/sec, so anything under ~6 KB is well under 200 ms of audio
        # and definitely not a real answer.
        MIN_REAL_AUDIO_BYTES = 6_000

        if audio_bytes and len(audio_bytes) >= MIN_REAL_AUDIO_BYTES:
            # Auto-submit: process this recording once
            audio_hash = hash(audio_bytes)
            processed_key = f"processed_{idx}_{fc}"

            if st.session_state.get(processed_key) != audio_hash:
                st.session_state[processed_key] = audio_hash

                with st.spinner("📝 Transcribing your answer..."):
                    answer = transcribe(audio_bytes)

                # Hard STT failure (e.g. empty/silent mic capture). Don't
                # advance — the error is already shown by transcribe(), and
                # the user can re-click the mic to record again. The
                # processed_key blocks reprocessing of the SAME bad bytes;
                # new audio gets a fresh hash and runs normally.
                if answer is None:
                    st.stop()

                if not answer.strip():
                    answer = "No answer provided."

                st.session_state.questions_asked.append(
                    st.session_state.current_question
                )
                st.session_state.transcripts.append(answer)

                with st.spinner("🤔 Bot is thinking..."):
                    decision = decide_next_turn(
                        role=st.session_state.role,
                        question=st.session_state.current_question,
                        answer=answer,
                        follow_up_count=st.session_state.follow_up_count,
                        language=st.session_state.lang,
                        max_follow_ups=MAX_FOLLOW_UPS_PER_QUESTION,
                    )

                if decision["action"] == "follow_up":
                    st.session_state.follow_up_count += 1
                    set_current_question(decision["question"])
                else:
                    advance_to_main_question(idx + 1)

                st.rerun()

    # ── Sidebar: status + abort ──────────────────────────────────────────────
    with st.sidebar:
        st.markdown("### 🎙 Live Interview")
        st.caption(f"Candidate: **{st.session_state.candidate_name}**")
        st.caption(f"Role: **{QUESTION_BANK[st.session_state.role]['title']}**")
        st.caption(f"Language: **{st.session_state.lang_code}**")
        st.divider()
        st.markdown("**Status**")
        st.caption(f"🟢 Question {idx + 1} / {total}")
        if fc > 0:
            st.caption(f"↳ Follow-up {fc} / {MAX_FOLLOW_UPS_PER_QUESTION}")
        st.caption(f"💬 Turns recorded: {len(past_turns)}")
        st.divider()
        if st.button("❌ Abort interview", use_container_width=True):
            reset_all()
            st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# STAGE: CLOSING
# ─────────────────────────────────────────────────────────────────────────────
def render_closing():
    role_title = QUESTION_BANK[st.session_state.role]["title"]

    col_l, col_m, col_r = st.columns([2, 3, 2])
    with col_l:
        st.image(candidate_avatar_url(st.session_state.candidate_name), width=44)
        st.markdown(f"**{st.session_state.candidate_name}**")
        st.caption(role_title)
    with col_m:
        st.progress(1.0, text="Interview complete")
    with col_r:
        st.markdown(
            "<div style='text-align:right; font-weight:600; color:#2ecc71;'>"
            "✓ INTERVIEW COMPLETE"
            "</div>",
            unsafe_allow_html=True,
        )
    st.divider()

    # Closing bubble — autoplay
    with st.chat_message("assistant", avatar=BOT_AVATAR_URL):
        st.markdown(f"**{st.session_state.closing_text}**")
        if st.session_state.closing_audio:
            should_autoplay = not st.session_state.get("closing_played", False)
            st.audio(
                st.session_state.closing_audio,
                format="audio/wav",
                autoplay=should_autoplay,
            )
            st.session_state.closing_played = True

    st.markdown("&nbsp;")
    if st.button(
        "📊  View Evaluation Report",
        type="primary",
        use_container_width=True,
    ):
        st.session_state.stage = "evaluating"
        st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# STAGE: EVALUATING
# ─────────────────────────────────────────────────────────────────────────────
def render_evaluating():
    st.title("⏳ Evaluating your interview...")
    st.caption("This may take 10–30 seconds.")
    with st.spinner("LLM is scoring the answers..."):
        try:
            evaluation = evaluate_candidate(
                role=st.session_state.role,
                questions=st.session_state.questions_asked,
                answers=st.session_state.transcripts,
                language=st.session_state.lang,
            )
        except Exception as e:
            # evaluate_candidate already handles the common LLM-truncation
            # case internally. This catch is a final safety net so that
            # any unexpected exception (network blip, transient API error,
            # etc.) still shows a friendly fallback instead of a red
            # traceback on stage.
            print(f"[render_evaluating] evaluate_candidate raised unexpectedly: {e}")
            evaluation = {
                "overall_score": None,
                "communication": None,
                "domain_knowledge": None,
                "confidence": None,
                "summary": (
                    "Automatic evaluation could not be generated this time. "
                    "Please click 'Retry Evaluation' below to try again."
                ),
                "hire_recommendation": None,
                "strengths": [],
                "improvements": [],
                "_generation_failed": True,
            }
    st.session_state.evaluation = evaluation
    st.session_state.stage = "report"
    st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# STAGE: REPORT
# ─────────────────────────────────────────────────────────────────────────────
def render_report():
    report = st.session_state.evaluation
    if report is None:
        st.error("No evaluation available.")
        return

    # If the LLM evaluation failed even after the auto-retry, show a
    # friendly retry screen instead of a broken report with empty scores.
    # This keeps any demo-visible UI clean.
    if report.get("_generation_failed"):
        st.title("⚠️ Evaluation Could Not Be Completed")
        st.markdown(
            f"<div style='font-size:1.15rem; color:#555; margin-top:8px;'>"
            f"{report.get('summary', '')}"
            f"</div>",
            unsafe_allow_html=True,
        )
        st.markdown("&nbsp;")
        col_retry, col_skip = st.columns(2)
        with col_retry:
            if st.button(
                "🔁  Retry Evaluation",
                type="primary",
                use_container_width=True,
            ):
                st.session_state.evaluation = None
                st.session_state.stage = "evaluating"
                st.rerun()
        with col_skip:
            if st.button(
                "🔄  Start New Interview",
                use_container_width=True,
            ):
                reset_all()
                st.rerun()
        return

    st.title("📋 Interview Score Report")
    st.caption(
        f"**{st.session_state.candidate_name}** · "
        f"{QUESTION_BANK[st.session_state.role]['title']} · "
        f"{datetime.now().strftime('%d %b %Y, %I:%M %p')}"
    )

    # Top metrics
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Overall", f"{report.get('overall_score', 0)}/10")
    col2.metric("Communication", f"{report.get('communication', 'N/A')}/10")
    col3.metric("Domain", f"{report.get('domain_knowledge', 'N/A')}/10")
    col4.metric("Confidence", f"{report.get('confidence', 'N/A')}/10")

    # Hire recommendation
    if report.get("hire_recommendation"):
        st.success("✅ **Hire Recommendation: YES**")
    else:
        st.error("❌ **Hire Recommendation: NO**")

    # Summary
    st.markdown("### 📝 Summary")
    st.write(report.get("summary", "—"))

    # Strengths / improvements. The LLM is asked for a JSON array, but
    # sometimes returns a single string — iterating over a string yields
    # one character per bullet (which is what produced the broken Hindi
    # report screenshot). Normalize defensively before rendering.
    def _as_list(val) -> list:
        if val is None or val == "":
            return ["—"]
        if isinstance(val, str):
            # Try splitting on common separators; fall back to single item.
            for sep in ("\n", ";", " | ", ", "):
                if sep in val:
                    parts = [p.strip() for p in val.split(sep) if p.strip()]
                    if len(parts) > 1:
                        return parts
            return [val]
        if isinstance(val, list):
            return [str(x) for x in val if str(x).strip()] or ["—"]
        return [str(val)]

    col_s, col_i = st.columns(2)
    with col_s:
        st.markdown("### ✅ Strengths")
        for s in _as_list(report.get("strengths")):
            st.markdown(f"- {s}")
    with col_i:
        st.markdown("### ⚠️ Areas to Improve")
        for imp in _as_list(report.get("improvements")):
            st.markdown(f"- {imp}")

    # Full transcript
    with st.expander("📜 Full transcript"):
        for i, (q, a) in enumerate(
            zip(st.session_state.questions_asked, st.session_state.transcripts), 1
        ):
            st.markdown(f"**Q{i}:** {q}")
            st.markdown(f"**A{i}:** {a}")
            st.divider()

    # Save & download
    safe_name = st.session_state.candidate_name.replace(" ", "_")
    full_report = {
        "candidate": st.session_state.candidate_name,
        "role": st.session_state.role,
        "language": st.session_state.lang_code,
        "date": datetime.now().isoformat(),
        "questions": st.session_state.questions_asked,
        "answers": st.session_state.transcripts,
        "evaluation": report,
    }

    if st.session_state.report_saved_path is None:
        report_path = (
            OUTPUT_DIR
            / f"report_{safe_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(full_report, f, ensure_ascii=False, indent=2)
        st.session_state.report_saved_path = str(report_path)

    st.caption(f"Saved to: `{st.session_state.report_saved_path}`")

    col_dl, col_new = st.columns(2)
    with col_dl:
        st.download_button(
            "⬇ Download JSON",
            data=json.dumps(full_report, ensure_ascii=False, indent=2),
            file_name=Path(st.session_state.report_saved_path).name,
            mime="application/json",
            use_container_width=True,
        )
    with col_new:
        if st.button("🔄 New interview", use_container_width=True, type="primary"):
            reset_all()
            st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# DISPATCHER
# ─────────────────────────────────────────────────────────────────────────────
stage = st.session_state.stage
if stage == "setup":
    render_setup()
elif stage == "profile_intro":
    render_profile_intro()
elif stage == "profile":
    render_profile()
elif stage == "profile_building":
    render_profile_building()
elif stage == "profile_review":
    render_profile_review()
elif stage == "greeting":
    render_greeting()
elif stage == "interview":
    render_interview()
elif stage == "closing":
    render_closing()
elif stage == "evaluating":
    render_evaluating()
elif stage == "report":
    render_report()
