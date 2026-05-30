"""
closing_view.py — Stage 8: thank-you after the technical interview.

The button does NOT show the report yet — it moves the candidate into
the personality / behavioral round. The final evaluation runs only
after both rounds are done.
"""

from __future__ import annotations

import streamlit as st

from constants.app_constants import STAGE_BEHAVIORAL_INTRO
from ui.streamlit.components import bot_avatar_url
from ui.streamlit.components import render_top_bar


def render() -> None:
    render_top_bar(
        progress=0.7,
        badge_text="✓ TECHNICAL ROUND COMPLETE",
        badge_colour="#2ecc71",
    )

    with st.chat_message("assistant", avatar=bot_avatar_url()):
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
    st.caption(
        "Next: 5 short scenario questions to surface personality — "
        "honesty, reliability, stress tolerance, customer focus, earning attitude."
    )
    if st.button(
        "🧭  Continue to personality round  →",
        type="primary",
        use_container_width=True,
    ):
        st.session_state.stage = STAGE_BEHAVIORAL_INTRO
        st.rerun()
