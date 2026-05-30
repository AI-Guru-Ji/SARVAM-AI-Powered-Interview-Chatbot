"""Tests for ResumeService — LLM path + deterministic fallback + PDF render."""

from __future__ import annotations

from models.schemas import (
    CandidateProfile,
    LlmCompletion,
    OnboardingAnswer,
)
from services.resume_service import ResumeService
from utils.exceptions import LlmBudgetExceededError


def _sample_profile() -> CandidateProfile:
    return CandidateProfile(
        name="Ramesh Kumar",
        applied_role="housekeeping",
        language="hi",
        answers={
            "contact_info": OnboardingAnswer(
                question="Contact?",
                answer="Ramesh, 9876543210, ramesh@example.com",
            ),
            "location_and_age": OnboardingAnswer(question="Where?", answer="Bareilly, 30 years"),
            "languages": OnboardingAnswer(question="Languages?", answer="Hindi, English"),
            "family": OnboardingAnswer(question="Family?", answer="married, two children"),
            "experience_years": OnboardingAnswer(question="Years?", answer="4 years"),
            "experience": OnboardingAnswer(question="Past work?", answer="Hotel Taj, 2 years"),
            "education": OnboardingAnswer(question="Education?", answer="12th pass"),
            "salary": OnboardingAnswer(question="Salary?", answer="15000 expected"),
            "availability": OnboardingAnswer(question="When?", answer="next week"),
        },
    )


class TestLlmPath:
    def test_returns_llm_text_on_success(self, mock_llm):
        mock_llm.chat_completion.return_value = LlmCompletion(
            content=(
                "Ramesh Kumar\nPhone: 9876543210\nEmail: ramesh@example.com\n\n"
                "PROFESSIONAL SUMMARY\n  Detail-oriented housekeeping professional.\n"
            ),
            finish_reason="stop",
        )
        service = ResumeService(mock_llm)
        resume = service.build_resume_text(_sample_profile())
        assert "Ramesh Kumar" in resume
        assert "PROFESSIONAL SUMMARY" in resume
        assert mock_llm.chat_completion.call_count == 1

    def test_retries_once_on_failure(self, mock_llm):
        good = LlmCompletion(
            content="Ramesh Kumar\nPhone: 9876543210\n\nOBJECTIVE\n  Seeking work.\n",
            finish_reason="stop",
        )
        mock_llm.chat_completion.side_effect = [
            LlmBudgetExceededError("length", 4096),
            good,
        ]
        service = ResumeService(mock_llm)
        resume = service.build_resume_text(_sample_profile())
        assert "Ramesh Kumar" in resume
        assert mock_llm.chat_completion.call_count == 2

    def test_falls_back_to_deterministic_when_llm_fails_twice(self, mock_llm):
        mock_llm.chat_completion.side_effect = LlmBudgetExceededError("length", 4096)
        service = ResumeService(mock_llm)
        resume = service.build_resume_text(_sample_profile())
        # Deterministic fallback uses ALL-CAPS name + verbatim answers
        assert "RAMESH KUMAR" in resume
        assert "Hotel Taj" in resume   # candidate's verbatim answer
        assert mock_llm.chat_completion.call_count == 2


class TestPdfRendering:
    def test_pdf_bytes_have_valid_magic(self, mock_llm):
        # Use the deterministic fallback path so this test doesn't need
        # a fake LLM response to be parseable.
        mock_llm.chat_completion.side_effect = LlmBudgetExceededError("length", 4096)
        service = ResumeService(mock_llm)
        resume = service.build_resume_text(_sample_profile())
        pdf_bytes = service.build_resume_pdf(resume, candidate_name="Ramesh Kumar")
        assert pdf_bytes[:4] == b"%PDF"
