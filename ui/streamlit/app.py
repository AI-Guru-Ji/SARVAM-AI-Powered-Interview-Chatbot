"""
ui/streamlit/app.py — Streamlit entry point.

Run with::

    streamlit run ui/streamlit/app.py

This file is intentionally thin: it does page setup, instantiates the
services from `config.settings`, injects CSS, initialises session state,
and dispatches to one render function per stage. All business logic
lives in `services/`.
"""

from __future__ import annotations

# Ensure the project root is on sys.path even when streamlit runs this
# file directly (streamlit doesn't auto-resolve relative parent imports).
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import streamlit as st

from config.settings import get_settings
from constants.app_constants import (
    APP_PAGE_ICON,
    APP_PAGE_TITLE,
    STAGE_BEHAVIORAL_DONE,
    STAGE_BEHAVIORAL_INTRO,
    STAGE_BEHAVIORAL_QS,
    STAGE_CLOSING,
    STAGE_EVALUATING,
    STAGE_GREETING,
    STAGE_INTERVIEW,
    STAGE_PROFILE,
    STAGE_PROFILE_BUILDING,
    STAGE_PROFILE_INTRO,
    STAGE_PROFILE_REVIEW,
    STAGE_REPORT,
    STAGE_SETUP,
)
from services.behavioral_eval_service import BehavioralEvalService
from services.decide_next_turn_service import DecideNextTurnService
from services.evaluation_service import EvaluationService
from services.health_check_service import HealthCheckService
from services.profile_enrich_service import ProfileEnrichService
from services.profile_extract_service import ProfileExtractService
from services.profile_service import ProfileService
from services.resume_service import ResumeService
from services.sarvam_llm_service import SarvamLlmService
from services.sarvam_stt_service import SarvamSttService
from services.sarvam_tts_service import SarvamTtsService
from ui.streamlit.components import render_brand_header
from ui.streamlit.state import init_state
from ui.streamlit.styles import inject_global_css
from ui.streamlit.views import (
    behavioral_done_view,
    behavioral_intro_view,
    behavioral_qs_view,
    closing_view,
    evaluating_view,
    greeting_view,
    interview_view,
    profile_building_view,
    profile_intro_view,
    profile_review_view,
    profile_view,
    report_view,
    setup_view,
)


# ──────────────────────────────────────────────────────────────────────
# Page configuration (must run before any other streamlit call)
# ──────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title=APP_PAGE_TITLE,
    page_icon=APP_PAGE_ICON,
    layout="centered",
)


# ──────────────────────────────────────────────────────────────────────
# Build services once per session — cached via st.cache_resource so
# Streamlit's hot-reload doesn't re-create them on every interaction.
# ──────────────────────────────────────────────────────────────────────
@st.cache_resource
def _build_services() -> dict:
    settings = get_settings()
    llm = SarvamLlmService(settings)
    return {
        "settings": settings,
        "tts": SarvamTtsService(settings),
        "stt": SarvamSttService(settings),
        "llm": llm,
        "profile": ProfileService(settings),
        "profile_extract": ProfileExtractService(llm),
        "profile_enrich": ProfileEnrichService(llm),
        "resume": ResumeService(llm, debug_dir=settings.debug_dir),
        "evaluation": EvaluationService(llm),
        "behavioral_eval": BehavioralEvalService(llm),
        "decide": DecideNextTurnService(llm),
        "health": HealthCheckService(settings),
    }


def main() -> None:
    services = _build_services()
    settings = services["settings"]

    inject_global_css()
    init_state()
    render_brand_header()   # appears once at the top of every stage

    stage = st.session_state.stage

    if stage == STAGE_SETUP:
        setup_view.render(
            tts_service=services["tts"],
            health_check_service=services["health"],
        )
    elif stage == STAGE_PROFILE_INTRO:
        profile_intro_view.render(tts_service=services["tts"])
    elif stage == STAGE_PROFILE:
        profile_view.render(
            tts_service=services["tts"],
            stt_service=services["stt"],
            extract_service=services["profile_extract"],
        )
    elif stage == STAGE_PROFILE_BUILDING:
        profile_building_view.render(
            settings=settings,
            tts_service=services["tts"],
            profile_service=services["profile"],
            profile_enrich_service=services["profile_enrich"],
            resume_service=services["resume"],
        )
    elif stage == STAGE_PROFILE_REVIEW:
        profile_review_view.render()
    elif stage == STAGE_GREETING:
        greeting_view.render(tts_service=services["tts"])
    elif stage == STAGE_INTERVIEW:
        interview_view.render(
            tts_service=services["tts"],
            stt_service=services["stt"],
            decide_service=services["decide"],
        )
    elif stage == STAGE_CLOSING:
        closing_view.render()
    elif stage == STAGE_BEHAVIORAL_INTRO:
        behavioral_intro_view.render(tts_service=services["tts"])
    elif stage == STAGE_BEHAVIORAL_QS:
        behavioral_qs_view.render(
            tts_service=services["tts"],
            stt_service=services["stt"],
        )
    elif stage == STAGE_BEHAVIORAL_DONE:
        behavioral_done_view.render()
    elif stage == STAGE_EVALUATING:
        # Combined evaluation: technical + behavioral, then → report.
        evaluating_view.render(
            evaluation_service=services["evaluation"],
            behavioral_eval_service=services["behavioral_eval"],
        )
    elif stage == STAGE_REPORT:
        report_view.render(settings=settings)
    else:
        st.error(f"Unknown stage: {stage!r}")


# Streamlit runs this file as __main__ on every rerun, so this is the
# single dispatch point.
main()
