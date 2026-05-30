"""
finalize.py — POST /v1/sessions/{id}/finalize

Runs BOTH evaluations (technical + behavioral), builds the candidate
profile + resume, persists the report JSON, and dispatches the
recruiter email. After this call, the session is in stage
``completed`` and the report endpoints return real data.

Long-running (~30-60s) — clients should treat the POST as a blocking
call with a long timeout. A future revision can switch this to a
"start finalization" + WebSocket progress stream.
"""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status

from constants.app_constants import REPORT_JSON_FILENAME_TEMPLATE
from models.schemas import CandidateProfile
from ui.fastapi import db
from ui.fastapi.auth import require_api_key
from ui.fastapi.deps import ServiceContainer, get_services
from ui.fastapi.notifier import notify_recruiter
from ui.fastapi.routes.sessions import build_session_view, load_or_404
from ui.fastapi.schemas import SessionStateView
from ui.fastapi.state_machine import (
    STAGE_AWAITING_FINALIZE,
    STAGE_COMPLETED,
    STAGE_EVALUATING,
)


router = APIRouter(prefix="/v1/sessions", tags=["finalize"])


@router.post("/{session_id}/finalize", response_model=SessionStateView)
def finalize(
    session_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    services: ServiceContainer = Depends(get_services),
    _token: str = Depends(require_api_key),
) -> SessionStateView:
    state, _, recruiter_email = load_or_404(session_id)
    if state["stage"] == STAGE_COMPLETED:
        return build_session_view(session_id, state, request)
    if state["stage"] != STAGE_AWAITING_FINALIZE:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Cannot finalize — session is in stage "
                f"{state['stage']!r}, expected {STAGE_AWAITING_FINALIZE!r}"
            ),
        )

    state["stage"] = STAGE_EVALUATING
    db.save_state(session_id, state)

    # ── 1) Build profile + resume ────────────────────────────────────
    qa_tuples = [
        (t["question"], t.get("answer") or "", t.get("extracted_value"))
        for t in state.get("profile_transcripts", [])
    ]
    profile = services.profile.build_profile(
        candidate_name=state["candidate_name"],
        role=state["role"],
        language=state["language"],
        qa_pairs=qa_tuples,
    )
    state["profile_json"] = profile.model_dump()

    # Best-effort enrichment — never fail the whole finalize if it errors.
    try:
        enrichment = services.profile_enrich.enrich(profile=profile)
        state["enrichment"] = enrichment.model_dump() if enrichment else None
    except Exception:  # noqa: BLE001
        state["enrichment"] = None

    # Resume PDF
    try:
        resume_text = services.resume.build_resume_text(profile)
        resume_bytes = services.resume.build_resume_pdf(
            resume_text, candidate_name=profile.name,
        )
        safe_name = profile.name.replace(" ", "_")
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        resume_path = services.settings.output_dir / f"resume_{safe_name}_{ts}.pdf"
        resume_path.write_bytes(resume_bytes)
        state["resume_pdf_path"] = str(resume_path)
    except Exception:  # noqa: BLE001
        state["resume_pdf_path"] = None

    # ── 2) Technical evaluation ─────────────────────────────────────
    technical_eval = services.evaluation.evaluate(
        role=state["role"],
        questions=state["questions_asked"],
        answers=state["transcripts"],
        language=state["language"],
    )
    state["evaluation"] = technical_eval.model_dump(by_alias=True)

    # ── 3) Behavioral evaluation ────────────────────────────────────
    behavioral_eval = services.behavioral_eval.evaluate(
        role=state["role"],
        language=state["language"],
        transcripts=state.get("behavioral_transcripts") or [],
    )
    state["behavioral_eval"] = behavioral_eval.model_dump()

    # ── 4) Persist full report JSON ─────────────────────────────────
    safe_name = state["candidate_name"].replace(" ", "_")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_filename = REPORT_JSON_FILENAME_TEMPLATE.format(
        safe_name=safe_name, ts=ts,
    )
    report_path = services.settings.output_dir / report_filename
    report = {
        "candidate": state["candidate_name"],
        "role": state["role"],
        "language": state["language"],
        "date": datetime.now().isoformat(),
        "questions": state.get("questions_asked", []),
        "answers": state.get("transcripts", []),
        "evaluation": state.get("evaluation"),
        "profile": state.get("profile_json"),
        "enrichment": state.get("enrichment"),
        "behavioral_evaluation": state.get("behavioral_eval"),
        "behavioral_transcripts": state.get("behavioral_transcripts", []),
    }
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8",
    )
    state["report_json_path"] = str(report_path)
    state["stage"] = STAGE_COMPLETED
    state["finalized_at"] = time.time()
    db.save_state(session_id, state)

    # ── 5) Email recruiter — fire-and-forget in the background ─────
    report_url = str(request.url_for("get_report", session_id=session_id))
    background_tasks.add_task(
        notify_recruiter,
        recruiter_email=recruiter_email,
        candidate_name=state["candidate_name"],
        role=state["role"],
        overall_score=technical_eval.overall_score,
        hire_recommendation=technical_eval.hire_recommendation,
        behavioral_summary=(behavioral_eval.overall_summary or "")[:240],
        report_url=report_url,
    )

    return build_session_view(session_id, state, request)
