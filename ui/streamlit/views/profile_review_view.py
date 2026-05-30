"""
profile_review_view.py — Stage 5: shows the generated resume + download
buttons. The candidate dashboard (rich visual with scores) is intentionally
NOT shown here — that's the report_view's job, after the interview. This
screen is purely about reviewing the resume document before continuing.
"""

from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from constants.app_constants import STAGE_GREETING
from ui.streamlit.components import render_pretty_resume, render_top_bar


def render() -> None:
    profile = st.session_state.profile_json
    resume = st.session_state.profile_resume
    pdf_bytes = st.session_state.get("profile_resume_pdf")
    json_path, pdf_path = st.session_state.profile_saved_paths or (None, None)

    render_top_bar(
        progress=1.0,
        badge_text="✓ PROFILE BUILT",
        badge_colour="#2ecc71",
    )

    st.title(f"📄 {st.session_state.candidate_name}")
    st.caption(
        "Here's your resume. Review it and click Continue when ready for "
        "the interview. (The full scorecard with interview ratings will "
        "appear at the end.)"
    )

    if resume:
        render_pretty_resume(resume)
    else:
        st.warning("Resume not available — please redo the onboarding.")

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
        st.session_state.stage = STAGE_GREETING
        st.rerun()
