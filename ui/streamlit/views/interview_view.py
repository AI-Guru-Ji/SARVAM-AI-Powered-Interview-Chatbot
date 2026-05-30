"""
interview_view.py — Stage 7: voice interview with up to 1 follow-up per question.
"""

from __future__ import annotations

import streamlit as st
from audio_recorder_streamlit import audio_recorder

from constants.app_constants import (
    AUDIO_SAMPLE_RATE,
    MAX_FOLLOW_UPS_PER_QUESTION,
    MIN_REAL_AUDIO_BYTES,
    SILENCE_PAUSE_SECONDS,
    STAGE_CLOSING,
)
from data.interview_questions import CLOSING_MESSAGE, QUESTION_BANK
from services.decide_next_turn_service import DecideNextTurnService
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


def _advance_to_main_question(idx: int, tts_service: SarvamTtsService) -> None:
    questions = QUESTION_BANK[st.session_state.role]["questions"]
    if idx >= len(questions):
        closing_text = CLOSING_MESSAGE[st.session_state.lang]
        st.session_state.closing_text = closing_text
        with st.spinner("🔊 Preparing closing message..."):
            st.session_state.closing_audio = generate_tts(closing_text, tts_service)
        st.session_state.stage = STAGE_CLOSING
        return
    st.session_state.question_idx = idx
    st.session_state.follow_up_count = 0
    q_text = questions[idx][st.session_state.lang]
    st.session_state.current_question = q_text
    with st.spinner("🔊 Generating audio..."):
        st.session_state.current_question_audio = generate_tts(q_text, tts_service)


def _set_current_question(text: str, tts_service: SarvamTtsService) -> None:
    st.session_state.current_question = text
    with st.spinner("🔊 Generating audio..."):
        st.session_state.current_question_audio = generate_tts(text, tts_service)


def render(
    *,
    tts_service: SarvamTtsService,
    stt_service: SarvamSttService,
    decide_service: DecideNextTurnService,
) -> None:
    questions = QUESTION_BANK[st.session_state.role]["questions"]
    total = len(questions)
    idx = st.session_state.question_idx
    fc = st.session_state.follow_up_count

    render_top_bar(
        progress=idx / total,
        badge_text=f"Question {idx + 1} of {total}",
    )

    # Past turns
    past_turns = list(
        zip(st.session_state.questions_asked, st.session_state.transcripts)
    )
    for q, a in past_turns:
        with st.chat_message("assistant", avatar=bot_avatar_url()):
            st.markdown(q)
        with st.chat_message(
            "user",
            avatar=candidate_avatar_url(st.session_state.candidate_name),
        ):
            st.markdown(a if a else "_(no answer)_")

    # Current question
    with st.chat_message("assistant", avatar=bot_avatar_url()):
        if fc > 0:
            st.caption(f"↳ Follow-up {fc} of {MAX_FOLLOW_UPS_PER_QUESTION}")
        st.markdown(
            "<div style='display:flex; align-items:center; gap:10px;'>"
            "<span class='bot-speaking'>AI Recruiter is asking</span>"
            f"{voice_waveform_html('bot')}"
            "</div>",
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

    render_your_turn_banner(SILENCE_PAUSE_SECONDS)

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
                neutral_color="#4f8ef7",
                recording_color="#e74c3c",
                icon_name="microphone",
                icon_size="3x",
                key=f"recorder_{idx}_{fc}",
            )

        if audio_bytes and len(audio_bytes) >= MIN_REAL_AUDIO_BYTES:
            audio_hash = hash(audio_bytes)
            processed_key = f"processed_{idx}_{fc}"

            if st.session_state.get(processed_key) != audio_hash:
                st.session_state[processed_key] = audio_hash

                with st.spinner("📝 Transcribing your answer..."):
                    answer = transcribe(audio_bytes, stt_service)
                if answer is None:
                    st.stop()
                if not answer.strip():
                    answer = "No answer provided."

                st.session_state.questions_asked.append(st.session_state.current_question)
                st.session_state.transcripts.append(answer)

                with st.spinner("🤔 Bot is thinking..."):
                    decision = decide_service.decide(
                        role=st.session_state.role,
                        question=st.session_state.current_question,
                        answer=answer,
                        follow_up_count=st.session_state.follow_up_count,
                        language=st.session_state.lang,
                    )

                if decision.action == "follow_up" and decision.question:
                    st.session_state.follow_up_count += 1
                    _set_current_question(decision.question, tts_service)
                else:
                    _advance_to_main_question(idx + 1, tts_service)

                st.rerun()

    # Sidebar
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
            reset_interview()
            st.rerun()
