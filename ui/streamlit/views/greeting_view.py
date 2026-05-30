"""
greeting_view.py — Stage 6: interview greeting bubble + Begin button.
"""

from __future__ import annotations

import streamlit as st

from constants.app_constants import STAGE_INTERVIEW
from ui.streamlit.components import bot_avatar_url
from data.interview_questions import QUESTION_BANK
from services.sarvam_tts_service import SarvamTtsService
from ui.streamlit.components import generate_tts, render_top_bar


def render(*, tts_service: SarvamTtsService) -> None:
    render_top_bar(progress=0.0, badge_text="LIVE Interview")

    # Greeting bubble — autoplay
    with st.chat_message("assistant", avatar=bot_avatar_url()):
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
        st.session_state.stage = STAGE_INTERVIEW
        # Pre-load first question
        questions = QUESTION_BANK[st.session_state.role]["questions"]
        st.session_state.question_idx = 0
        st.session_state.follow_up_count = 0
        first_q = questions[0][st.session_state.lang]
        st.session_state.current_question = first_q
        with st.spinner("🔊 Generating audio..."):
            st.session_state.current_question_audio = generate_tts(first_q, tts_service)
        st.rerun()
