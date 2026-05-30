"""
audio.py — TTS audio streaming for the current question.

Two endpoints:

  GET /v1/sessions/{id}/audio       lazy-generate (or cached) WAV for
                                    the current question
  GET /v1/sessions/{id}/audio/{f}   stream a specific TTS WAV file
                                    (returned in /audio responses so
                                    clients can cache + replay)
"""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse

from ui.fastapi import db
from ui.fastapi.auth import require_api_key
from ui.fastapi.deps import ServiceContainer, get_services
from ui.fastapi.routes.sessions import load_or_404


router = APIRouter(prefix="/v1/sessions", tags=["audio"])


def _audio_dir(settings) -> Path:
    p = settings.temp_audio_dir
    p.mkdir(parents=True, exist_ok=True)
    return p


@router.get("/{session_id}/audio", name="get_current_audio")
def get_current_audio(
    session_id: str,
    services: ServiceContainer = Depends(get_services),
    _token: str = Depends(require_api_key),
):
    state, _, _ = load_or_404(session_id)
    text = state.get("current_question_text")
    if not text:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No current question — nothing to synthesize",
        )

    filename = state.get("current_question_audio_filename")
    audio_path: Path | None = None
    if filename:
        candidate = _audio_dir(services.settings) / filename
        if candidate.exists():
            audio_path = candidate

    if audio_path is None:
        # Lazy-generate
        filename = f"q_{session_id}_{uuid.uuid4().hex}.wav"
        audio_path = _audio_dir(services.settings) / filename
        services.tts.text_to_speech(
            text=text,
            output_path=str(audio_path),
            language_code=state["lang_code"],
        )
        state["current_question_audio_filename"] = filename
        db.save_state(session_id, state)

    return FileResponse(
        path=audio_path,
        media_type="audio/wav",
        filename=filename,
    )


@router.get("/{session_id}/audio/{filename}")
def get_audio_file(
    session_id: str,
    filename: str,
    services: ServiceContainer = Depends(get_services),
    _token: str = Depends(require_api_key),
):
    # Defence: prevent path traversal — only allow files matching our
    # own naming convention.
    if not filename.startswith("q_") or not filename.endswith(".wav"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid filename",
        )
    path = _audio_dir(services.settings) / filename
    if not path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found",
        )
    return FileResponse(path=path, media_type="audio/wav", filename=filename)
