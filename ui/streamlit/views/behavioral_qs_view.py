"""
behavioral_qs_view.py — Stage 11b: 5-question voice loop for the
behavioral / personality round. Free-form like the technical interview
(no per-question voice confirmation — these are open scenario answers).

For Phase D (timing signals), we capture ``response_seconds`` per
question — the wall-clock time between when the question's TTS finished
playing and when the candidate's mic recording arrived back. This feeds
the deterministic "Trust Signal" on the dashboard.
"""

from __future__ import annotations

import time

import streamlit as st
from audio_recorder_streamlit import audio_recorder

from constants.app_constants import (
    AUDIO_SAMPLE_RATE,
    BEHAVIORAL_QUESTION_COUNT,
    MIN_REAL_AUDIO_BYTES,
    SILENCE_PAUSE_SECONDS,
    STAGE_BEHAVIORAL_DONE,
)
from data.behavioral_questions import get_behavioral_questions_for_role
from services.sarvam_stt_service import SarvamSttService
from services.sarvam_tts_service import SarvamTtsService
from ui.streamlit.components import (
    bot_avatar_url,
    candidate_avatar_url,
    generate_tts,
    render_top_bar,
    render_your_turn_banner,
    transcribe,
    voice_waveform_html,
)
from ui.streamlit.state import reset_interview


def _question_prompt(idx: int) -> str:
    """Return the current question text in the candidate's language."""
    questions = get_behavioral_questions_for_role(st.session_state.role)
    q = questions[idx]
    return q["prompts"].get(st.session_state.lang) or q["prompts"]["en"]


def _advance(*, tts_service: SarvamTtsService) -> None:
    """Move to the next behavioral question, or transition to evaluating."""
    next_idx = st.session_state.behavioral_q_idx + 1
    if next_idx >= BEHAVIORAL_QUESTION_COUNT:
        st.session_state.stage = STAGE_BEHAVIORAL_DONE
        return
    st.session_state.behavioral_q_idx = next_idx
    next_q_text = _question_prompt(next_idx)
    with st.spinner("🔊 Preparing next question…"):
        st.session_state.behavioral_current_audio = generate_tts(next_q_text, tts_service)


def render(
    *,
    tts_service: SarvamTtsService,
    stt_service: SarvamSttService,
) -> None:
    idx = st.session_state.behavioral_q_idx
    total = BEHAVIORAL_QUESTION_COUNT
    current_q_text = _question_prompt(idx)

    render_top_bar(
        progress=(idx) / total,
        badge_text=f"Behavioral · {idx + 1} of {total}",
        badge_colour="#6366f1",
    )

    # Lazy-generate the first Q's TTS the moment we arrive here
    if idx == 0 and not st.session_state.behavioral_current_audio:
        with st.spinner("🔊 Preparing the first question…"):
            st.session_state.behavioral_current_audio = generate_tts(
                current_q_text, tts_service,
            )

    # Past behavioral Q&A bubbles
    for turn in st.session_state.behavioral_transcripts:
        with st.chat_message("assistant", avatar=bot_avatar_url()):
            st.markdown(turn["question"])
        with st.chat_message(
            "user",
            avatar=candidate_avatar_url(st.session_state.candidate_name),
        ):
            st.markdown(turn.get("answer") or "_(skipped)_")

    # ── Current question ────────────────────────────────────────
    with st.chat_message("assistant", avatar=bot_avatar_url()):
        st.markdown(
            "<div style='display:flex; align-items:center; gap:10px;'>"
            "<span class='bot-speaking'>AI Interviewer is asking</span>"
            f"{voice_waveform_html('bot')}"
            "</div>",
            unsafe_allow_html=True,
        )
        st.markdown(f"**{current_q_text}**")
        if st.session_state.behavioral_current_audio:
            play_flag = f"behavioral_played_{idx}"
            should_autoplay = not st.session_state.get(play_flag, False)
            st.audio(
                st.session_state.behavioral_current_audio,
                format="audio/wav",
                autoplay=should_autoplay,
            )
            if not st.session_state.get(play_flag, False):
                # Mark the moment the question audio is shown — this is
                # our "question delivered at T0" timestamp for Phase D.
                st.session_state[f"behavioral_start_ts_{idx}"] = time.time()
                st.session_state[play_flag] = True

    render_your_turn_banner(SILENCE_PAUSE_SECONDS)

    # ── User's turn ─────────────────────────────────────────────
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
                sample_rate=AUDIO_SAMPLE_RATE,
                neutral_color="#6366f1",
                recording_color="#e74c3c",
                icon_name="microphone",
                icon_size="3x",
                key=f"behavioral_recorder_{idx}",
            )

        if audio_bytes and len(audio_bytes) >= MIN_REAL_AUDIO_BYTES:
            audio_hash = hash(audio_bytes)
            processed_key = f"behavioral_processed_{idx}"
            if st.session_state.get(processed_key) != audio_hash:
                st.session_state[processed_key] = audio_hash

                # Capture response time
                t0 = st.session_state.get(f"behavioral_start_ts_{idx}")
                response_seconds = (time.time() - t0) if t0 else None

                with st.spinner("📝 Transcribing…"):
                    answer = transcribe(
                        audio_bytes, stt_service, file_prefix="behavioral",
                    )
                if answer is None:
                    st.stop()
                clean = (answer or "").strip()

                if not clean:
                    st.session_state[f"behavioral_empty_{idx}"] = True
                    st.rerun()

                st.session_state.behavioral_transcripts.append({
                    "question": current_q_text,
                    "answer": clean,
                    "response_seconds": response_seconds,
                })
                _advance(tts_service=tts_service)
                st.rerun()

    # Empty-capture retry / skip
    if st.session_state.get(f"behavioral_empty_{idx}"):
        st.warning(
            "🎙 I couldn't hear an answer. Try again, or skip — recruiters "
            "can still see your other answers."
        )
        col_retry, col_skip = st.columns(2)
        with col_retry:
            if st.button("🔁 Try again", use_container_width=True,
                         key=f"retry_{idx}"):
                st.session_state.pop(f"behavioral_empty_{idx}", None)
                st.session_state.pop(f"behavioral_processed_{idx}", None)
                st.rerun()
        with col_skip:
            if st.button("⏭ Skip this question", use_container_width=True,
                         key=f"skip_{idx}"):
                st.session_state.pop(f"behavioral_empty_{idx}", None)
                st.session_state.behavioral_transcripts.append({
                    "question": current_q_text,
                    "answer": "",
                    "response_seconds": None,
                })
                _advance(tts_service=tts_service)
                st.rerun()

    # Sidebar
    with st.sidebar:
        st.markdown("### 🧭 Behavioral round")
        st.caption(f"Question {idx + 1} / {total}")
        st.caption("5 short scenario questions to surface personality.")
        st.divider()
        if st.button("❌ Abort", use_container_width=True):
            reset_interview()
            st.rerun()
