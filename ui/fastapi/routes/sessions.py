"""
sessions.py — Session lifecycle.

  POST   /v1/sessions          create a new interview session
  GET    /v1/sessions/{id}     read current state + next question
  DELETE /v1/sessions/{id}     abort + delete a session
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status

from ui.fastapi import db
from ui.fastapi.auth import require_api_key
from ui.fastapi.deps import ServiceContainer, get_services
from ui.fastapi.schemas import (
    CreateSessionRequest,
    QuestionInfo,
    SessionStateView,
)
from ui.fastapi.state_machine import (
    StateMachine,
    initial_state,
    STAGE_AWAITING_FINALIZE,
    STAGE_BEHAVIORAL_INTRO,
    STAGE_COMPLETED,
    STAGE_PROFILE_REVIEW,
)


router = APIRouter(prefix="/v1/sessions", tags=["sessions"])


# ──────────────────────────────────────────────────────────────────────
# Helpers shared with other routes
# ──────────────────────────────────────────────────────────────────────
def build_session_view(
    session_id: str,
    state: dict,
    request: Request,
) -> SessionStateView:
    """Convert raw state dict → wire-format SessionStateView."""
    stage = state["stage"]
    question_text = state.get("current_question_text")
    audio_filename = state.get("current_question_audio_filename")
    current_q = None
    if question_text and stage not in (
        STAGE_AWAITING_FINALIZE, STAGE_COMPLETED, STAGE_PROFILE_REVIEW,
        STAGE_BEHAVIORAL_INTRO,
    ):
        # Audio URL is always served by the same endpoint — the route
        # generates the WAV on demand if filename is None.
        audio_url = str(request.url_for("get_current_audio", session_id=session_id))
        current_q = QuestionInfo(text=question_text, audio_url=audio_url)

    final_report_url = None
    if stage == STAGE_COMPLETED:
        final_report_url = str(request.url_for("get_report", session_id=session_id))

    # Progress recalculated from state (avoid stale stored value)
    from ui.fastapi.state_machine import StateMachine as _SM  # late to dodge cycles
    sm = _SM(state, stt_service=None, decide_service=None)

    return SessionStateView(
        session_id=session_id,
        stage=stage,
        progress=sm.progress(),
        is_terminal=stage in (
            STAGE_AWAITING_FINALIZE, STAGE_COMPLETED, STAGE_PROFILE_REVIEW,
        STAGE_BEHAVIORAL_INTRO,
        ),
        candidate_name=state["candidate_name"],
        role=state["role"],
        language=state["language"],
        current_question=current_q,
        final_report_url=final_report_url,
    )


def load_or_404(session_id: str) -> tuple[dict, str, str]:
    """Load state from DB or raise 404."""
    record = db.load_session(session_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"session {session_id} not found",
        )
    return record


# ──────────────────────────────────────────────────────────────────────
# Routes
# ──────────────────────────────────────────────────────────────────────
@router.post("", response_model=SessionStateView, status_code=status.HTTP_201_CREATED)
def create_session(
    payload: CreateSessionRequest,
    request: Request,
    _token: str = Depends(require_api_key),
) -> SessionStateView:
    try:
        state = initial_state(
            role=payload.role,
            language=payload.language,
            candidate_name=payload.candidate_name,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    sid = db.create_session(
        state=state,
        candidate_phone=payload.candidate_phone,
        recruiter_email=payload.recruiter_email,
    )
    return build_session_view(sid, state, request)


@router.get("/{session_id}", response_model=SessionStateView)
def get_session(
    session_id: str,
    request: Request,
    _token: str = Depends(require_api_key),
) -> SessionStateView:
    state, _, _ = load_or_404(session_id)
    return build_session_view(session_id, state, request)


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def abort_session(
    session_id: str,
    _token: str = Depends(require_api_key),
) -> None:
    if not db.delete_session(session_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"session {session_id} not found",
        )
    return None
