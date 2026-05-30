"""
Shared fixtures for the FastAPI backend tests.

The Sarvam HTTP layer is mocked at the service level — exactly the same
pattern as ``tests/conftest.py``. No real Sarvam calls happen here.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest


# Point the SQLite DB + output dir at a temp path BEFORE we import
# anything that opens the engine (db.py reads env at first call).
@pytest.fixture
def temp_workspace(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("DEMO_MODE", "1")
    monkeypatch.setenv("SARVAM_BACKEND_DB_URL", f"sqlite:///{tmp_path / 'test.db'}")
    # Force output dir into tmp_path
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "output"))
    # Reset DB module's lazy state — fresh engine per test
    from ui.fastapi import db as db_mod
    db_mod._engine = None
    db_mod._SessionFactory = None
    # Reset deps cache so the new env is picked up
    from ui.fastapi import deps
    deps.get_services.cache_clear()
    yield tmp_path


@pytest.fixture
def mock_services(monkeypatch, temp_workspace):
    """Replace SarvamLlm/Stt/Tts with deterministic mocks via the container."""
    from models.schemas import (
        BehavioralEvaluation,
        Evaluation,
        SttResult,
        TtsResult,
        TurnDecision,
    )
    from ui.fastapi import deps

    services = deps.get_services()

    # STT — always returns the same transcript so the FSM can advance.
    services.stt = MagicMock()
    services.stt.speech_to_text.return_value = SttResult(
        transcript="mocked answer", language_code="hi-IN",
    )

    # TTS — write a tiny WAV header so the file-existence checks pass.
    def _fake_tts(text: str, output_path: str, language_code: str = "hi-IN"):
        Path(output_path).write_bytes(b"RIFF" + b"\x00" * 40)
        return TtsResult(audio_bytes=b"RIFF" + b"\x00" * 40, saved_path=output_path)
    services.tts = MagicMock()
    services.tts.text_to_speech.side_effect = _fake_tts

    # Decide service — always "next" so we don't follow-up forever
    services.decide = MagicMock()
    services.decide.decide.return_value = TurnDecision(action="next")

    # Evaluation + behavioral — pre-baked scorecards
    services.evaluation = MagicMock()
    services.evaluation.evaluate.return_value = Evaluation(
        overall_score=8.0, communication=8, domain_knowledge=8,
        safety_awareness=7, confidence=8,
        summary="Solid candidate.", hire_recommendation=True,
        strengths=["clear answers"], improvements=["more safety detail"],
    )
    services.behavioral_eval = MagicMock()
    services.behavioral_eval.evaluate.return_value = BehavioralEvaluation(
        honesty=8, reliability=7, stress_tolerance=7,
        customer_orientation=8, earning_attitude=6,
        overall_summary="Trustworthy and customer-aware.",
        per_trait_reasoning={"honesty": "Said they would return money."},
        avg_response_seconds=3.4, answer_specificity=7,
        cross_question_consistency="high",
    )

    # Health — pretend Sarvam is reachable
    from models.schemas import HealthCheckReport, HealthCheckResult
    services.health = MagicMock()
    services.health.run.return_value = HealthCheckReport(
        results=[HealthCheckResult(name="tts", ok=True, latency_s=0.1, detail="ok")],
        all_ok=True,
    )

    # Profile + enrichment + resume — quick deterministic returns
    from models.schemas import CandidateProfile, ProfileEnrichment
    services.profile = MagicMock()
    services.profile.build_profile.return_value = CandidateProfile(
        name="Test Candidate", applied_role="housekeeping", language="hi",
    )
    services.profile_enrich = MagicMock()
    services.profile_enrich.enrich.return_value = ProfileEnrichment()
    # The profile extractor is only called for HIGH_RISK_FIELDS during
    # the asking phase. Returning empty disables the confirmation
    # sub-FSM so the e2e test can loop one-answer-per-question.
    services.profile_extract = MagicMock()
    services.profile_extract.extract.return_value = ""
    services.resume = MagicMock()
    services.resume.build_resume_text.return_value = "Test resume"
    services.resume.build_resume_pdf.return_value = b"%PDF-1.4 fake"

    return services


@pytest.fixture
def client(mock_services):
    """FastAPI TestClient with the mocked service container active."""
    from fastapi.testclient import TestClient
    from ui.fastapi.app import app
    return TestClient(app)
