"""
evaluation_service.py — LLM-based scoring of the interview transcript.

Returns a typed ``Evaluation`` model. The model includes a
``generation_failed`` flag (mapped from JSON key ``_generation_failed``)
so the UI can render a "Retry Evaluation" screen instead of a broken
report when both attempts hit the LLM's token budget.

Resilience features baked in:
  * Two LLM attempts (native language → English) — native may use ~3×
    more output tokens than English, so the retry is more reliable.
  * Partial-JSON regex recovery — scores + summary survive even when the
    response was truncated mid-JSON.
  * Strengths/improvements retry — small focused follow-up call to fill
    in the trailing fields when the primary call truncated late.
  * Empty-transcript short-circuit — never calls the LLM when there is
    nothing to evaluate.
"""

from __future__ import annotations

import json
import re
from typing import Iterable, Optional

from constants.app_constants import (
    EVALUATION_SKIP_SUBSTRINGS,
    LANGUAGE_NAMES,
    LLM_EVAL_TEMPERATURE,
)
from models.schemas import Evaluation
from prompts.evaluation_prompt import (
    build_evaluation_prompts,
    build_strengths_retry_prompts,
)
from services.sarvam_llm_service import SarvamLlmService
from utils.exceptions import SarvamApiError
from utils.helpers import coerce_str_list, parse_json_lenient, strip_code_fences
from utils.logger import get_logger


logger = get_logger(__name__)


class EvaluationService:
    """Score an interview transcript using sarvam-30b."""

    def __init__(self, llm_service: SarvamLlmService) -> None:
        self._llm = llm_service

    # ----------------------------------------------------------------
    def evaluate(
        self,
        *,
        role: str,
        questions: Iterable[str],
        answers: Iterable[str],
        language: str = "en",
    ) -> Evaluation:
        """Return an ``Evaluation`` model. Never raises — UI-safe.

        On both-attempts failure, returns ``Evaluation`` with
        ``generation_failed=True`` so the UI can show a Retry button.
        """
        filtered = [
            (q, a)
            for q, a in zip(questions, answers)
            if not _is_empty(a)
        ]
        if not filtered:
            return _empty_transcript_evaluation()

        qa_pairs_text = "\n".join(
            f"Q{i+1}: {q}\nA{i+1}: {a}" for i, (q, a) in enumerate(filtered)
        )
        # Design decision: evaluation summary/strengths/improvements are
        # ALWAYS produced in English, regardless of the candidate's
        # interview language. The dashboard is recruiter-facing, and
        # English keeps it consistent across all 11 supported languages.
        # The candidate themselves never reads the evaluation.
        # The `native_lang_name` variable is kept only for the
        # strengths/improvements retry, which preserves backward
        # compatibility if the system prompt ever needs the source
        # language context.
        native_lang_name = LANGUAGE_NAMES.get(language, "English")

        attempts: list[tuple[str, str]] = [
            ("English", "English (recruiter-facing default)"),
        ]

        response_text: Optional[str] = None
        last_error: Optional[Exception] = None
        for attempt_no, (output_lang, why) in enumerate(attempts, start=1):
            sp, um = build_evaluation_prompts(
                role=role,
                language_code=language,
                output_lang=output_lang,
                qa_pairs_text=qa_pairs_text,
            )
            try:
                completion = self._llm.chat_completion(
                    messages=[{"role": "user", "content": um}],
                    system_prompt=sp,
                    temperature=LLM_EVAL_TEMPERATURE,
                )
                response_text = completion.content
                if attempt_no > 1:
                    logger.info(
                        "evaluate: recovered on attempt %d using %s",
                        attempt_no, why,
                    )
                break
            except SarvamApiError as e:
                last_error = e
                logger.warning(
                    "evaluate: attempt %d/%d (%s) failed: %s",
                    attempt_no, len(attempts), why, e,
                )
                if attempt_no < len(attempts):
                    logger.info("evaluate: retrying with %s...", attempts[attempt_no][1])

        if response_text is None:
            logger.error(
                "evaluate: both attempts exhausted. Last error: %s", last_error,
            )
            return _generation_failed_evaluation()

        evaluation_dict = _parse_or_recover_evaluation(response_text)

        # If primary call truncated before strengths/improvements,
        # run a tiny focused follow-up to fill them in.
        needs_retry = (
            (not evaluation_dict["strengths"] or not evaluation_dict["improvements"])
            and evaluation_dict["summary"]
            and evaluation_dict["summary"] != "—"
        )
        if needs_retry:
            try:
                extras = self._retry_strengths_and_improvements(
                    role=role,
                    qa_pairs_text=qa_pairs_text,
                    summary=evaluation_dict["summary"],
                    output_lang="English",
                )
                if not evaluation_dict["strengths"]:
                    evaluation_dict["strengths"] = extras["strengths"]
                if not evaluation_dict["improvements"]:
                    evaluation_dict["improvements"] = extras["improvements"]
            except SarvamApiError as e:
                logger.warning(
                    "evaluate: strengths/improvements retry failed (%s) — leaving empty",
                    e,
                )

        return Evaluation(**evaluation_dict)

    # ----------------------------------------------------------------
    def _retry_strengths_and_improvements(
        self,
        *,
        role: str,
        qa_pairs_text: str,
        summary: str,
        output_lang: str,
    ) -> dict:
        sp, um = build_strengths_retry_prompts(
            role=role,
            qa_pairs_text=qa_pairs_text,
            summary=summary,
            output_lang=output_lang,
        )
        completion = self._llm.chat_completion(
            messages=[{"role": "user", "content": um}],
            system_prompt=sp,
            temperature=LLM_EVAL_TEMPERATURE,
        )
        parsed = _parse_or_recover_evaluation(completion.content)
        return {
            "strengths": parsed["strengths"],
            "improvements": parsed["improvements"],
        }


# ──────────────────────────────────────────────────────────────────────
# Module-level helpers (kept private; tested via the service)
# ──────────────────────────────────────────────────────────────────────
def _is_empty(answer: str) -> bool:
    if not answer or not answer.strip():
        return True
    lo = answer.strip().lower()
    return any(tok in lo for tok in EVALUATION_SKIP_SUBSTRINGS)


def _empty_transcript_evaluation() -> Evaluation:
    return Evaluation(
        overall_score=0,
        communication=0,
        domain_knowledge=0,
        safety_awareness=0,
        confidence=0,
        summary="Candidate did not provide answers to the interview questions.",
        hire_recommendation=False,
        strengths=[],
        improvements=["Provide spoken answers to each question."],
    )


def _generation_failed_evaluation() -> Evaluation:
    return Evaluation(
        overall_score=None,
        communication=None,
        domain_knowledge=None,
        safety_awareness=None,
        confidence=None,
        summary=(
            "Automatic evaluation could not be generated this time. "
            "Please click 'Retry Evaluation' below to try again."
        ),
        hire_recommendation=None,
        strengths=[],
        improvements=[],
        generation_failed=True,
    )


def _parse_or_recover_evaluation(raw: str) -> dict:
    """Parse the evaluator's JSON output. Falls back to regex recovery
    when the LLM truncated mid-JSON. Never raises.

    Returns a dict matching the Evaluation schema (minus the failure
    flag). Use ``Evaluation(**dict)`` to construct the model.
    """
    parsed = parse_json_lenient(raw)
    if parsed is not None:
        return _normalise(parsed)

    logger.warning(
        "evaluate: JSON parse failed — attempting regex recovery on truncated response",
    )
    clean = strip_code_fences(raw)

    def _num(pattern: str):
        m = re.search(pattern, clean)
        if not m:
            return None
        try:
            v = m.group(1)
            return int(v) if "." not in v else float(v)
        except (ValueError, IndexError):
            return None

    def _str(pattern: str):
        m = re.search(pattern, clean, re.DOTALL)
        if not m:
            return None
        s = m.group(1)
        try:
            return json.loads(f'"{s}"')
        except json.JSONDecodeError:
            return s.strip()

    def _bool(pattern: str):
        m = re.search(pattern, clean)
        return m.group(1).lower() == "true" if m else None

    def _list(pattern: str):
        m = re.search(pattern, clean, re.DOTALL)
        if not m:
            return None
        return [s for s in re.findall(r'"((?:[^"\\]|\\.)*)"', m.group(1)) if s.strip()]

    return _normalise({
        "overall_score": _num(r'"overall_score"\s*:\s*(\d+(?:\.\d+)?)') or 0,
        "communication": _num(r'"communication"\s*:\s*(\d+(?:\.\d+)?)') or 0,
        "domain_knowledge": _num(r'"domain_knowledge"\s*:\s*(\d+(?:\.\d+)?)') or 0,
        "safety_awareness": _num(r'"safety_awareness"\s*:\s*(\d+(?:\.\d+)?)') or 0,
        "confidence": _num(r'"confidence"\s*:\s*(\d+(?:\.\d+)?)') or 0,
        "summary": _str(r'"summary"\s*:\s*"((?:[^"\\]|\\.)*?)"')
                   or "Evaluation could not be fully generated. Please retry.",
        "hire_recommendation": _bool(r'"hire_recommendation"\s*:\s*(true|false)') or False,
        "strengths": _list(r'"strengths"\s*:\s*\[(.*?)\]') or [],
        "improvements": _list(r'"improvements"\s*:\s*\[(.*?)\]') or [],
    })


def _normalise(d: dict) -> dict:
    """Coerce evaluator output to the expected shape.

    Especially: handle the bug where the LLM returns strengths or
    improvements as a single string (which would render as one bullet
    per character if iterated).
    """
    # Bug seen in production: LLM sometimes returns `summary` as a JSON
    # array of sentences. `str([..])` would leak Python list repr to the
    # dashboard. Coerce to a single string here.
    raw_summary = d.get("summary")
    if isinstance(raw_summary, list):
        raw_summary = " ".join(
            str(s).strip() for s in raw_summary if s and str(s).strip()
        )

    return {
        "overall_score": d.get("overall_score") or 0,
        "communication": d.get("communication") or 0,
        "domain_knowledge": d.get("domain_knowledge") or 0,
        "safety_awareness": d.get("safety_awareness") or 0,
        "confidence": d.get("confidence") or 0,
        "summary": str(raw_summary or "").strip() or "—",
        "hire_recommendation": bool(d.get("hire_recommendation")),
        "strengths": coerce_str_list(d.get("strengths")),
        "improvements": coerce_str_list(d.get("improvements")),
    }
