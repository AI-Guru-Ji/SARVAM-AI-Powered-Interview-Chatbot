"""
reports.py — Recruiter-facing report endpoints.

  GET /v1/sessions/{id}/report      Returns the full report as JSON.
  GET /v1/sessions/{id}/report.pdf  Returns the dashboard PDF.

These are the URLs we put in the recruiter notification email.
"""

from __future__ import annotations

import io

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from models.schemas import (
    BehavioralEvaluation,
    CandidateProfile,
    Evaluation,
    ProfileEnrichment,
)
from ui.fastapi.auth import require_api_key
from ui.fastapi.routes.sessions import load_or_404
from ui.fastapi.schemas import ReportResponse


router = APIRouter(prefix="/v1/sessions", tags=["reports"])


@router.get("/{session_id}/report", response_model=ReportResponse, name="get_report")
def get_report(
    session_id: str,
    _token: str = Depends(require_api_key),
) -> ReportResponse:
    state, _, _ = load_or_404(session_id)
    if not state.get("evaluation"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Report not ready — call POST /finalize first",
        )
    return ReportResponse(
        session_id=session_id,
        candidate_name=state["candidate_name"],
        role=state["role"],
        language=state["language"],
        finalized_at=state.get("finalized_at"),
        evaluation=state.get("evaluation"),
        behavioral_eval=state.get("behavioral_eval"),
        profile=state.get("profile_json"),
        enrichment=state.get("enrichment"),
        questions_asked=state.get("questions_asked", []),
        transcripts=state.get("transcripts", []),
        behavioral_transcripts=state.get("behavioral_transcripts", []),
    )


@router.get("/{session_id}/report.pdf")
def get_report_pdf(
    session_id: str,
    _token: str = Depends(require_api_key),
):
    state, _, _ = load_or_404(session_id)
    if not state.get("evaluation"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Report not ready — call POST /finalize first",
        )

    # Lazy-import the dashboard renderer to avoid pulling WeasyPrint into
    # the import graph if it's not installed (cairo system libs).
    try:
        from services.dashboard_pdf_service import build_dashboard_pdf
        from ui.streamlit.dashboard import build_dashboard_html
    except Exception as e:  # pragma: no cover
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Dashboard PDF unavailable: {e}",
        )

    profile = CandidateProfile.model_validate(state.get("profile_json") or {})
    enrichment_dict = state.get("enrichment")
    enrichment = ProfileEnrichment.model_validate(enrichment_dict) if enrichment_dict else None
    evaluation = Evaluation.model_validate(state.get("evaluation") or {})
    behavioral_dict = state.get("behavioral_eval")
    behavioral = BehavioralEvaluation.model_validate(behavioral_dict) if behavioral_dict else None

    html = build_dashboard_html(
        profile=profile,
        enrichment=enrichment,
        evaluation=evaluation,
        behavioral=behavioral,
    )
    pdf_bytes = build_dashboard_pdf(html)

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f'inline; filename="dashboard_{state["candidate_name"].replace(" ", "_")}.pdf"'
            ),
        },
    )
