"""
deps.py — Dependency injection container for the FastAPI backend.

Mirrors the ``_build_services()`` composition root in
``ui/streamlit/app.py``. Services are constructed once per process
(cached with ``@lru_cache``) and yielded to route handlers via FastAPI's
``Depends`` mechanism.
"""

from __future__ import annotations

import os
from functools import lru_cache

from config.settings import Settings, get_settings
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


# ──────────────────────────────────────────────────────────────────────
# Process-wide service container
# ──────────────────────────────────────────────────────────────────────
class ServiceContainer:
    """Holds every long-lived service. Inject via :func:`get_services`."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        llm = SarvamLlmService(settings)
        self.tts = SarvamTtsService(settings)
        self.stt = SarvamSttService(settings)
        self.llm = llm
        self.profile = ProfileService(settings)
        self.profile_extract = ProfileExtractService(llm)
        self.profile_enrich = ProfileEnrichService(llm)
        self.resume = ResumeService(llm, debug_dir=settings.debug_dir)
        self.evaluation = EvaluationService(llm)
        self.behavioral_eval = BehavioralEvalService(llm)
        self.decide = DecideNextTurnService(llm)
        self.health = HealthCheckService(settings)


@lru_cache(maxsize=1)
def get_services() -> ServiceContainer:
    """Process-wide singleton — built on first request."""
    settings = get_settings()
    return ServiceContainer(settings)


# ──────────────────────────────────────────────────────────────────────
# Runtime flags
# ──────────────────────────────────────────────────────────────────────
def is_demo_mode() -> bool:
    """``DEMO_MODE=1`` (or true/yes/on) bypasses OTP + uses stubs for
    paid integrations. Default on for safety during local dev."""
    return os.getenv("DEMO_MODE", "1").strip().lower() in (
        "1", "true", "yes", "on",
    )


def resend_api_key() -> str:
    """Resend API key for sending recruiter notifications. Empty in demo."""
    return os.getenv("RESEND_API_KEY", "").strip()


def api_key() -> str:
    """Optional bearer token. When set, the backend requires
    ``Authorization: Bearer <token>`` on every request. Empty disables
    the check — fine for local dev / demo."""
    return os.getenv("SARVAM_BACKEND_API_KEY", "").strip()
