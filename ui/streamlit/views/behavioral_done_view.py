"""
behavioral_done_view.py — short "ready for results" screen shown right
after the candidate finishes the 5 personality questions.

Clicking the primary button moves to STAGE_EVALUATING, which now runs
BOTH the technical and behavioral LLM evaluations back-to-back before
showing the final report.
"""

from __future__ import annotations

import streamlit as st

from constants.app_constants import STAGE_EVALUATING
from ui.streamlit.components import bot_avatar_url, render_top_bar


def render() -> None:
    render_top_bar(
        progress=0.95,
        badge_text="✓ PERSONALITY ROUND COMPLETE",
        badge_colour="#6366f1",
    )

    with st.chat_message("assistant", avatar=bot_avatar_url()):
        st.markdown(
            "**Thank you — both rounds are done.** "
            "Click the button below to generate your final report. "
            "We'll combine your technical answers and your personality answers "
            "into one scorecard."
        )

    st.markdown("&nbsp;")
    if st.button(
        "📊  Generate Final Report  →",
        type="primary",
        use_container_width=True,
    ):
        st.session_state.stage = STAGE_EVALUATING
        st.rerun()
