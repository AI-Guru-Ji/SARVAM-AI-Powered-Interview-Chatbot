"""
profile_building_view.py — Stage 4: animated loader → builds JSON + resume.
"""

from __future__ import annotations

import json
from datetime import datetime

import streamlit as st

from config.settings import Settings
from constants.app_constants import (
    PROFILE_JSON_FILENAME_TEMPLATE,
    PROFILE_SPARSE_FIELD_THRESHOLD,
    QUESTION_FIELD_ORDER,
    RESUME_PDF_FILENAME_TEMPLATE,
    STAGE_GREETING,
    STAGE_PROFILE,
    STAGE_PROFILE_REVIEW,
)
from services.profile_enrich_service import ProfileEnrichService
from services.profile_service import ProfileService
from services.resume_service import ResumeService
from services.sarvam_tts_service import SarvamTtsService
from ui.streamlit.components import generate_tts, profile_prompt


def render(
    *,
    settings: Settings,
    tts_service: SarvamTtsService,
    profile_service: ProfileService,
    profile_enrich_service: ProfileEnrichService,
    resume_service: ResumeService,
) -> None:
    st.title("✨ Building your profile…")
    st.caption("Turning your answers into a structured profile and a resume.")

    # 3-tuple (question, answer, extracted_value) — preserves the
    # voice-confirmed LLM-cleaned value for high-risk fields so the
    # CandidateProfile (and downstream dashboard) shows the clean English
    # form instead of the raw Hindi/Indic transcript.
    qa_pairs = [
        (t["question"], t["answer"], t.get("extracted_value"))
        for t in st.session_state.profile_transcripts
    ]

    # All-empty guard (look at the answer field, ignoring extracted_value)
    if not any(a and a.strip() for _, a, _ in qa_pairs):
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
                for k in list(st.session_state.keys()):
                    if (
                        k.startswith("profile_processed_")
                        or k.startswith("profile_empty_")
                        or k.startswith("profile_played_")
                    ):
                        del st.session_state[k]
                first_q_text = profile_prompt(0)
                with st.spinner("🔊 Generating audio..."):
                    st.session_state.profile_current_audio = generate_tts(
                        first_q_text, tts_service,
                    )
                st.session_state.stage = STAGE_PROFILE
                st.rerun()
        with col_skip:
            if st.button("Skip profile, go to interview", use_container_width=True):
                st.session_state.stage = STAGE_GREETING
                st.rerun()
        return

    # Engaging loader
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

    try:
        with st.status("✨ Building your candidate profile…", expanded=True) as status:
            st.write(f"📥  Captured {len(qa_pairs)} answers from your onboarding chat.")

            st.write("📝  Extracting structured details (name, education, skills, …) …")
            profile = profile_service.build_profile(
                candidate_name=st.session_state.candidate_name,
                role=st.session_state.role,
                language=st.session_state.lang,
                qa_pairs=qa_pairs,
            )
            populated = profile_service.count_populated_fields(profile)
            st.write(f"✓  Extracted {populated} fields from your answers.")

            st.write("📃  Formatting your 1-page resume …")
            resume = resume_service.build_resume_text(profile)
            st.write("✓  Resume ready.")

            st.write("🔧  Extracting skills and work history for the dashboard …")
            enrichment = profile_enrich_service.enrich(profile)
            st.session_state.profile_enrichment = enrichment
            st.write(
                f"✓  Found {len(enrichment.skills)} skills and "
                f"{len(enrichment.work_history)} past role(s)."
            )

            status.update(label="✅ All ready!", state="complete", expanded=False)

        if populated < PROFILE_SPARSE_FIELD_THRESHOLD and any(a and a.strip() for _, a in qa_pairs):
            st.warning(
                f"⚠️ Only {populated} field(s) were extracted from your answers. "
                "The profile may look sparse. Check `output/debug/` for the raw "
                "LLM response if you want to investigate, or redo onboarding."
            )
    except Exception as e:
        st.error(f"Could not build profile: {e}")
        if st.button("Continue to interview anyway"):
            st.session_state.stage = STAGE_GREETING
            st.rerun()
        return

    # Build PDF + persist artefacts
    pdf_bytes = resume_service.build_resume_pdf(
        resume, candidate_name=st.session_state.candidate_name,
    )

    st.session_state.profile_json = profile.model_dump()
    st.session_state.profile_resume = resume
    st.session_state.profile_resume_pdf = pdf_bytes

    safe_name = st.session_state.candidate_name.replace(" ", "_")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = settings.output_dir / PROFILE_JSON_FILENAME_TEMPLATE.format(
        safe_name=safe_name, ts=ts,
    )
    pdf_path = settings.output_dir / RESUME_PDF_FILENAME_TEMPLATE.format(
        safe_name=safe_name, ts=ts,
    )
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(profile.model_dump(), f, ensure_ascii=False, indent=2)
    with open(pdf_path, "wb") as f:
        f.write(pdf_bytes)
    st.session_state.profile_saved_paths = (str(json_path), str(pdf_path))

    st.session_state.stage = STAGE_PROFILE_REVIEW
    st.rerun()
