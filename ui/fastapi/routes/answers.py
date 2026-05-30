"""
answers.py — The single most important endpoint of the backend.

  POST /v1/sessions/{id}/answer

Multipart upload of the candidate's WAV. The route writes the audio
to disk, hands the path to the FSM's :meth:`StateMachine.submit_answer`,
saves the new state back to SQLite, and returns the next question (text
+ audio URL) so the mobile client can immediately render it.
"""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status

from ui.fastapi import db
from ui.fastapi.auth import require_api_key
from ui.fastapi.deps import ServiceContainer, get_services
from ui.fastapi.routes.sessions import build_session_view, load_or_404
from ui.fastapi.schemas import AnswerResponse
from ui.fastapi.state_machine import (
    STAGE_AWAITING_FINALIZE,
    STAGE_COMPLETED,
    StateMachine,
)


router = APIRouter(prefix="/v1/sessions", tags=["answers"])


@router.post("/{session_id}/answer", response_model=AnswerResponse)
async def submit_answer(
    session_id: str,
    request: Request,
    audio: UploadFile = File(..., description="Candidate's WAV recording"),
    services: ServiceContainer = Depends(get_services),
    _token: str = Depends(require_api_key),
) -> AnswerResponse:
    state, _, _ = load_or_404(session_id)
    if state["stage"] in (STAGE_AWAITING_FINALIZE, STAGE_COMPLETED):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"session is in stage {state['stage']!r}; nothing to answer",
        )

    # Write upload to a temp file the STT service can read.
    tmp_dir: Path = services.settings.temp_audio_dir
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tmp_path = tmp_dir / f"upload_{session_id}_{uuid.uuid4().hex}.wav"
    contents = await audio.read()
    tmp_path.write_bytes(contents)

    # Drive the FSM. We pass everything it could need:
    #   - stt + decide for the standard turn loop
    #   - profile_extract for HIGH_RISK_FIELDS read-back confirmation
    #   - profile + resume + settings so it can generate the resume PDF
    #     when the last profile question is answered (PROFILE_REVIEW).
    sm = StateMachine(
        state,
        stt_service=services.stt,
        decide_service=services.decide,
        profile_extract_service=services.profile_extract,
        profile_service=services.profile,
        resume_service=services.resume,
        settings=services.settings,
    )
    try:
        result = sm.submit_answer(tmp_path)
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )
    finally:
        # Best-effort cleanup of the upload; do not crash on EBUSY
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass

    # Persist new state
    db.save_state(session_id, state)

    # Build the wire response — start with the standard session view,
    # then attach the transcript of the answer we just received.
    base_view = build_session_view(session_id, state, request)
    return AnswerResponse(
        session_id=base_view.session_id,
        stage=base_view.stage,
        progress=base_view.progress,
        is_terminal=base_view.is_terminal,
        candidate_name=base_view.candidate_name,
        role=base_view.role,
        language=base_view.language,
        current_question=base_view.current_question,
        final_report_url=base_view.final_report_url,
        last_transcript=result.transcript,
    )
