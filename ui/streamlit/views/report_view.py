"""
report_view.py — Stage 10: recruiter dashboard (profile + interview
scores in one pane) + download buttons.

For failed evaluations, falls back to a graceful retry screen.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import streamlit as st

from config.settings import Settings
from constants.app_constants import (
    COLOR_NEUTRAL_500,
    REPORT_JSON_FILENAME_TEMPLATE,
    STAGE_EVALUATING,
)
from models.schemas import (
    BehavioralEvaluation,
    CandidateProfile,
    Evaluation,
    ProfileEnrichment,
)
from ui.streamlit.dashboard import build_dashboard_html, render_candidate_dashboard
from ui.streamlit.state import reset_interview


def _failed_evaluation_screen(report: dict) -> None:
    st.title("⚠️ Evaluation Could Not Be Completed")
    st.markdown(
        f"<div style='font-size:1.15rem; color:{COLOR_NEUTRAL_500}; margin-top:8px;'>"
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
            st.session_state.stage = STAGE_EVALUATING
            st.rerun()
    with col_skip:
        if st.button("🔄  Start New Interview", use_container_width=True):
            reset_interview()
            st.rerun()


# ──────────────────────────────────────────────────────────────────────
# Main entry
# ──────────────────────────────────────────────────────────────────────
def render(*, settings: Settings) -> None:
    report_dict = st.session_state.evaluation
    if report_dict is None:
        st.error("No evaluation available.")
        return

    # Graceful retry screen — no dashboard, just a friendly action.
    if report_dict.get("_generation_failed") or report_dict.get("generation_failed"):
        _failed_evaluation_screen(report_dict)
        return

    # Reconstruct typed models from the session-stored dicts
    profile_dict = st.session_state.profile_json
    if not profile_dict:
        st.error("Profile data missing — can't render the dashboard.")
        return
    profile = CandidateProfile.model_validate(profile_dict)
    enrichment: ProfileEnrichment | None = st.session_state.get("profile_enrichment")
    evaluation = Evaluation.model_validate(report_dict)

    # Behavioral eval is optional — may be None if the behavioral round
    # was skipped (e.g. because technical eval failed and we routed
    # straight to the report), or may indicate generation_failed=True.
    behavioral_dict = st.session_state.get("behavioral_eval")
    behavioral: BehavioralEvaluation | None = (
        BehavioralEvaluation.model_validate(behavioral_dict)
        if behavioral_dict else None
    )

    # ── The dashboard ───────────────────────────────────────────────
    render_candidate_dashboard(
        profile=profile,
        enrichment=enrichment,
        evaluation=evaluation,
        behavioral=behavioral,
    )

    st.markdown("&nbsp;")

    # ── Full transcript expander ────────────────────────────────────
    with st.expander("📜 Full technical interview transcript"):
        for i, (q, a) in enumerate(
            zip(st.session_state.questions_asked, st.session_state.transcripts), 1
        ):
            st.markdown(f"**Q{i}:** {q}")
            st.markdown(f"**A{i}:** {a}")
            st.divider()

    # ── Behavioral transcript expander (new) ─────────────────────────
    behavioral_transcripts = st.session_state.get("behavioral_transcripts") or []
    if behavioral_transcripts:
        with st.expander("🧭 Behavioral round transcript"):
            for i, turn in enumerate(behavioral_transcripts, 1):
                st.markdown(f"**Q{i}:** {turn.get('question', '')}")
                st.markdown(f"**A{i}:** {turn.get('answer', '') or '_(skipped)_'}")
                rt = turn.get("response_seconds")
                if rt is not None:
                    st.caption(f"Response time: {rt:.1f}s")
                st.divider()

    # ── Persist & download ──────────────────────────────────────────
    safe_name = st.session_state.candidate_name.replace(" ", "_")
    full_report = {
        "candidate": st.session_state.candidate_name,
        "role": st.session_state.role,
        "language": st.session_state.lang_code,
        "date": datetime.now().isoformat(),
        "questions": st.session_state.questions_asked,
        "answers": st.session_state.transcripts,
        "evaluation": report_dict,
        "profile": profile_dict,
        "enrichment": (enrichment.model_dump() if enrichment else None),
        # Behavioral round
        "behavioral_evaluation": (behavioral.model_dump() if behavioral else None),
        "behavioral_transcripts": behavioral_transcripts,
    }
    if st.session_state.report_saved_path is None:
        report_path = settings.output_dir / REPORT_JSON_FILENAME_TEMPLATE.format(
            safe_name=safe_name,
            ts=datetime.now().strftime("%Y%m%d_%H%M%S"),
        )
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(full_report, f, ensure_ascii=False, indent=2)
        st.session_state.report_saved_path = str(report_path)

    st.caption(f"Saved to: `{st.session_state.report_saved_path}`")

    # ── Download buttons ────────────────────────────────────────────
    # Try to render the dashboard as a PDF for download. If the PDF
    # library isn't available (or fails), we silently skip that button
    # and still offer the JSON download.
    pdf_bytes: bytes | None = None
    try:
        from services.dashboard_pdf_service import build_dashboard_pdf
        pdf_html = build_dashboard_html(
            profile=profile,
            enrichment=enrichment,
            evaluation=evaluation,
            behavioral=behavioral,
        )
        pdf_bytes = build_dashboard_pdf(pdf_html)
    except Exception as e:  # pragma: no cover — PDF is a nice-to-have
        st.caption(f"_PDF download unavailable: {e}_")

    col_pdf, col_json, col_new = st.columns(3)
    with col_pdf:
        if pdf_bytes:
            st.download_button(
                "⬇  Dashboard PDF",
                data=pdf_bytes,
                file_name=f"dashboard_{safe_name}.pdf",
                mime="application/pdf",
                use_container_width=True,
                type="primary",
            )
        else:
            st.button(
                "PDF unavailable",
                use_container_width=True,
                disabled=True,
            )
    with col_json:
        st.download_button(
            "⬇  Full report (.json)",
            data=json.dumps(full_report, ensure_ascii=False, indent=2),
            file_name=Path(st.session_state.report_saved_path).name,
            mime="application/json",
            use_container_width=True,
        )
    with col_new:
        if st.button("🔄  New interview", use_container_width=True):
            reset_interview()
            st.rerun()
