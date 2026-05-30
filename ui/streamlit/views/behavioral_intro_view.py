"""
behavioral_intro_view.py — Stage 11a: brief intro before the 5 behavioral
scenario questions. Plays a one-line voice prompt explaining what's
coming, then waits for the candidate to click "Begin".
"""

from __future__ import annotations

import streamlit as st

from constants.app_constants import (
    BEHAVIORAL_QUESTION_COUNT,
    STAGE_BEHAVIORAL_QS,
)
from data.behavioral_questions import BEHAVIORAL_INTRO
from services.sarvam_tts_service import SarvamTtsService
from ui.streamlit.components import (
    bot_avatar_url,
    generate_tts,
    render_top_bar,
)


def render(*, tts_service: SarvamTtsService) -> None:
    lang = st.session_state.lang

    render_top_bar(
        progress=0.5,
        badge_text=f"Behavioral round · {BEHAVIORAL_QUESTION_COUNT} questions",
        badge_colour="#6366f1",
    )

    # Lazy-generate intro audio on first arrival
    if not st.session_state.get("behavioral_intro_text"):
        st.session_state.behavioral_intro_text = (
            BEHAVIORAL_INTRO.get(lang) or BEHAVIORAL_INTRO["en"]
        )
    if not st.session_state.get("behavioral_intro_audio"):
        with st.spinner("🔊 Preparing the behavioral intro…"):
            st.session_state.behavioral_intro_audio = generate_tts(
                st.session_state.behavioral_intro_text, tts_service,
            )

    with st.chat_message("assistant", avatar=bot_avatar_url()):
        st.markdown(f"**{st.session_state.behavioral_intro_text}**")
        if st.session_state.behavioral_intro_audio:
            should_autoplay = not st.session_state.get("behavioral_intro_played", False)
            st.audio(
                st.session_state.behavioral_intro_audio,
                format="audio/wav",
                autoplay=should_autoplay,
            )
            st.session_state.behavioral_intro_played = True

    st.markdown("&nbsp;")
    if st.button(
        f"▶  Begin behavioral round ({BEHAVIORAL_QUESTION_COUNT} questions)",
        type="primary",
        use_container_width=True,
    ):
        st.session_state.behavioral_q_idx = 0
        st.session_state.behavioral_current_audio = None
        st.session_state.stage = STAGE_BEHAVIORAL_QS
        st.rerun()
