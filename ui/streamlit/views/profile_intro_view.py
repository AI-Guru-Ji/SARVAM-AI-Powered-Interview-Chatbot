"""
profile_intro_view.py — Stage 2: warm onboarding welcome bubble + "Begin" button.
"""

from __future__ import annotations

import streamlit as st

from constants.app_constants import STAGE_PROFILE
from ui.streamlit.components import bot_avatar_url
from services.sarvam_tts_service import SarvamTtsService
from ui.streamlit.components import (
    generate_tts,
    profile_prompt,
    render_top_bar,
)


def render(*, tts_service: SarvamTtsService) -> None:
    render_top_bar(progress=0.0, badge_text="ONBOARDING")

    with st.chat_message("assistant", avatar=bot_avatar_url()):
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
        st.session_state.stage = STAGE_PROFILE
        st.session_state.profile_q_idx = 0
        first_q_text = profile_prompt(0)
        with st.spinner("🔊 Generating audio..."):
            st.session_state.profile_current_audio = generate_tts(first_q_text, tts_service)
        st.rerun()
