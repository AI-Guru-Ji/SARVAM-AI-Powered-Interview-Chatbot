"""
evaluating_view.py — Combined evaluation screen. Runs the technical
LLM eval AND the behavioral LLM eval back-to-back, then transitions
to the final report.

Showing two staged status updates ("Scoring technical answers...",
"Analysing personality...") so the user has visibility into what's
happening during the ~30-60s wait.
"""

from __future__ import annotations

import streamlit as st

from constants.app_constants import STAGE_REPORT
from models.schemas import Evaluation
from services.behavioral_eval_service import BehavioralEvalService
from services.evaluation_service import EvaluationService
from utils.logger import get_logger


logger = get_logger(__name__)


def render(
    *,
    evaluation_service: EvaluationService,
    behavioral_eval_service: BehavioralEvalService,
) -> None:
    st.title("⏳  Generating your final report…")
    st.caption(
        "Scoring the technical answers and analysing personality. "
        "This usually takes 30 to 60 seconds."
    )

    progress_block = st.empty()

    # ── 1) Technical evaluation ──────────────────────────────────
    progress_block.markdown(
        "🔎  **Step 1 / 2** — Scoring technical answers…",
    )
    with st.spinner("LLM is scoring the technical interview…"):
        try:
            technical_eval = evaluation_service.evaluate(
                role=st.session_state.role,
                questions=st.session_state.questions_asked,
                answers=st.session_state.transcripts,
                language=st.session_state.lang,
            )
        except Exception as e:
            logger.error("Technical evaluate raised unexpectedly: %s", e)
            technical_eval = Evaluation(
                summary=(
                    "Automatic evaluation could not be generated this time. "
                    "Please click 'Retry Evaluation' below to try again."
                ),
                generation_failed=True,
            )
    st.session_state.evaluation = technical_eval.model_dump(by_alias=True)

    # ── 2) Behavioral evaluation ─────────────────────────────────
    progress_block.markdown(
        "🧭  **Step 2 / 2** — Analysing personality (5 traits)…",
    )
    with st.spinner("LLM is scoring the behavioral round…"):
        behavioral_eval = behavioral_eval_service.evaluate(
            role=st.session_state.role,
            language=st.session_state.lang,
            transcripts=st.session_state.behavioral_transcripts or [],
        )
    st.session_state.behavioral_eval = behavioral_eval.model_dump()

    # ── Done ─────────────────────────────────────────────────────
    progress_block.markdown("✅  **Both rounds scored — opening the report…**")
    st.session_state.stage = STAGE_REPORT
    st.rerun()
