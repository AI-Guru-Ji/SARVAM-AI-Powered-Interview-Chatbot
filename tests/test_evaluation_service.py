"""Tests for EvaluationService — partial-JSON recovery + retry behaviour."""

from __future__ import annotations

from models.schemas import LlmCompletion
from services.evaluation_service import (
    EvaluationService,
    _parse_or_recover_evaluation,
)
from utils.exceptions import LlmBudgetExceededError


# ──────────────────────────────────────────────────────────────────────
# Partial-JSON recovery — the real production failure case
# ──────────────────────────────────────────────────────────────────────
class TestPartialJsonRecovery:
    def test_recovers_scores_and_summary_from_truncated_response(self):
        # Exactly the failure the user saw in their Mayank Shukla report:
        # JSON cut off mid-"hire_recommendation":
        truncated = (
            '{ "overall_score": 5, "communication": 4, "domain_knowledge": 5, '
            '"confidence": 3, "summary": "उम्मीदवार के पास सुरक्षा कार्य का बुनियादी '
            'अनुभव है लेकिन ज्ञान की गहराई कम है।", "hire_recommendation":'
        )
        result = _parse_or_recover_evaluation(truncated)
        assert result["overall_score"] == 5
        assert result["communication"] == 4
        assert result["domain_knowledge"] == 5
        assert result["confidence"] == 3
        assert "बुनियादी" in result["summary"]
        assert result["strengths"] == []      # truncated before this field
        assert result["improvements"] == []

    def test_clean_json_path(self):
        clean = (
            '{"overall_score": 8, "communication": 7, "domain_knowledge": 9, '
            '"confidence": 7, "summary": "Strong candidate.", '
            '"hire_recommendation": true, "strengths": ["a", "b"], '
            '"improvements": ["c"]}'
        )
        result = _parse_or_recover_evaluation(clean)
        assert result["hire_recommendation"] is True
        assert result["strengths"] == ["a", "b"]


# ──────────────────────────────────────────────────────────────────────
# Service-level: short-circuits and retries
# ──────────────────────────────────────────────────────────────────────
class TestEvaluationService:
    def test_empty_transcript_short_circuits_without_llm_call(self, mock_llm):
        service = EvaluationService(mock_llm)
        evaluation = service.evaluate(
            role="housekeeping",
            questions=["Q1", "Q2"],
            answers=["No answer provided.", ""],
            language="hi",
        )
        assert evaluation.overall_score == 0
        assert evaluation.hire_recommendation is False
        assert not mock_llm.chat_completion.called

    def test_native_language_attempt_succeeds(self, mock_llm):
        mock_llm.chat_completion.return_value = LlmCompletion(
            content=(
                '{"overall_score": 7, "communication": 6, "domain_knowledge": 8, '
                '"confidence": 7, "summary": "Good.", '
                '"hire_recommendation": true, "strengths": ["s1"], '
                '"improvements": ["i1"]}'
            ),
            finish_reason="stop",
        )
        service = EvaluationService(mock_llm)
        evaluation = service.evaluate(
            role="housekeeping",
            questions=["Q1"],
            answers=["A real answer with substance."],
            language="hi",
        )
        assert evaluation.overall_score == 7
        assert evaluation.strengths == ["s1"]
        assert evaluation.generation_failed is False
        # Only one LLM call needed — the native attempt succeeded.
        assert mock_llm.chat_completion.call_count == 1

    # Note: the legacy "fall back from candidate's language to English"
    # path was removed when evaluations were switched to always-English
    # output (single attempt). The old test
    # `test_falls_back_to_english_on_first_failure` was specifically
    # exercising that two-attempt pattern and has been removed.

    def test_returns_failure_flag_when_attempt_fails(self, mock_llm):
        """Single English attempt fails → generation_failed True."""
        mock_llm.chat_completion.side_effect = LlmBudgetExceededError("length", 4096)
        service = EvaluationService(mock_llm)
        evaluation = service.evaluate(
            role="housekeeping",
            questions=["Q1"],
            answers=["An answer."],
            language="hi",
        )
        assert evaluation.generation_failed is True
        assert evaluation.overall_score is None
        # Exactly one call now (no Hindi-first fallback chain).
        assert mock_llm.chat_completion.call_count == 1

    def test_evaluation_output_language_is_english(self, mock_llm):
        """evaluate() must pass `output_lang='English'` to build_evaluation_prompts."""
        good = LlmCompletion(
            content=(
                '{"overall_score": 7, "communication": 7, "domain_knowledge": 7, '
                '"safety_awareness": 7, "confidence": 7, "summary": "OK.", '
                '"hire_recommendation": true, "strengths": ["s"], "improvements": ["i"]}'
            ),
            finish_reason="stop",
        )
        mock_llm.chat_completion.return_value = good
        service = EvaluationService(mock_llm)
        service.evaluate(
            role="electrician",
            questions=["Q1"],
            answers=["A1"],
            language="hi",   # Hindi candidate
        )
        # Sanity: only one call (the always-English attempt)
        assert mock_llm.chat_completion.call_count == 1
        # The system prompt sent to the LLM must explicitly request English output.
        call_args = mock_llm.chat_completion.call_args
        system_prompt = call_args.kwargs["system_prompt"]
        assert "English" in system_prompt
        # The prompt must not ASK FOR OUTPUT in Hindi (the candidate's
        # language). It's allowed to mention Hindi when telling the model
        # to translate INTO English.
        assert "sentences in Hindi" not in system_prompt
        assert "summary in Hindi" not in system_prompt
        assert "strings in Hindi" not in system_prompt
