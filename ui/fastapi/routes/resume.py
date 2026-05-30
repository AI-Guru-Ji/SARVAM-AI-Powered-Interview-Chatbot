"""
resume.py — Candidate resume endpoints (used during PROFILE_REVIEW).

  GET  /v1/sessions/{id}/resume.text       Plain text resume body
  GET  /v1/sessions/{id}/resume.pdf        ATS-ready PDF
  POST /v1/sessions/{id}/advance           Move past PROFILE_REVIEW into
                                           the technical interview
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse

from ui.fastapi import db
from ui.fastapi.auth import require_api_key
from ui.fastapi.deps import ServiceContainer, get_services
from ui.fastapi.routes.sessions import build_session_view, load_or_404
from ui.fastapi.schemas import SessionStateView
from ui.fastapi.state_machine import (
    STAGE_BEHAVIORAL_INTRO,
    STAGE_PROFILE_REVIEW,
    StateMachine,
)


router = APIRouter(prefix="/v1/sessions", tags=["resume"])


@router.get("/{session_id}/resume.text")
def get_resume_text(
    session_id: str,
    _token: str = Depends(require_api_key),
) -> dict:
    state, _, _ = load_or_404(session_id)
    text = state.get("resume_text")
    if not text:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Resume not yet generated for this session.",
        )
    return {"session_id": session_id, "text": text}


@router.get("/{session_id}/resume.pdf")
def get_resume_pdf(
    session_id: str,
    _token: str = Depends(require_api_key),
):
    state, _, _ = load_or_404(session_id)
    path = state.get("resume_pdf_path")
    if not path or not Path(path).exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume PDF not yet available.",
        )
    return FileResponse(
        path=path,
        media_type="application/pdf",
        filename=Path(path).name,
    )


@router.post("/{session_id}/advance", response_model=SessionStateView)
def advance(
    session_id: str,
    request: Request,
    services: ServiceContainer = Depends(get_services),
    _token: str = Depends(require_api_key),
) -> SessionStateView:
    """Move past either of the explicit gate stages:
    PROFILE_REVIEW → INTERVIEW_GREETING, or
    BEHAVIORAL_INTRO → BEHAVIORAL."""
    state, _, _ = load_or_404(session_id)
    allowed = {STAGE_PROFILE_REVIEW, STAGE_BEHAVIORAL_INTRO}
    if state["stage"] not in allowed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"/advance only valid in one of {sorted(allowed)!r}, "
                f"current = {state['stage']!r}"
            ),
        )
    sm = StateMachine(
        state,
        stt_service=services.stt,
        decide_service=services.decide,
        profile_extract_service=services.profile_extract,
        profile_service=services.profile,
        resume_service=services.resume,
        settings=services.settings,
    )
    sm.advance()
    db.save_state(session_id, state)
    return build_session_view(session_id, state, request)
