"""
profile_service.py — Build the structured candidate profile from Q&A.

Deterministic, no LLM call. Maps each onboarding question by index to a
known field (the order is fixed by constants.QUESTION_FIELD_ORDER and
data/profile_questions.py). The candidate's verbatim answers go into
the corresponding slots in their original language.

This is the LLM-free path that replaces the failing
"Hindi → English → JSON" extraction chain — instant, never fails, never
invents.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Iterable

from config.settings import Settings
from constants.app_constants import QUESTION_FIELD_ORDER
from models.schemas import CandidateProfile, OnboardingAnswer
from utils.logger import get_logger


logger = get_logger(__name__)


class ProfileService:
    """Build candidate profiles deterministically from onboarding Q&A."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    # ----------------------------------------------------------------
    def build_profile(
        self,
        *,
        candidate_name: str,
        role: str,
        language: str,
        qa_pairs: Iterable,
    ) -> CandidateProfile:
        """Build a CandidateProfile from raw Q&A tuples.

        Args:
            candidate_name: Name captured at setup time.
            role:           Role key (e.g. "housekeeping").
            language:       Short language code (en/hi/...).
            qa_pairs:       Iterable of tuples in the order PROFILE_QUESTIONS
                            were asked. Each tuple is either:
                              - (question, answer)               — 2-tuple,
                                legacy / free-form fields
                              - (question, answer, extracted_value) — 3-tuple,
                                for voice-confirmed high-risk fields where the
                                LLM-cleaned value is preserved.

                            The 3-tuple form is REQUIRED for high-risk fields
                            (name/mobile/age/location) — otherwise the
                            recruiter dashboard falls back to the raw Indic
                            transcript instead of the clean extracted value.
        """
        answers: dict[str, OnboardingAnswer] = {}
        pairs_for_debug: list[tuple[str, str]] = []
        for i, tup in enumerate(qa_pairs):
            if i >= len(QUESTION_FIELD_ORDER):
                break
            # Accept both legacy 2-tuple and current 3-tuple forms.
            if len(tup) == 3:
                question, answer, extracted_value = tup
            else:
                question, answer = tup
                extracted_value = None

            field = QUESTION_FIELD_ORDER[i]
            clean_answer = (answer or "").strip()
            clean_extracted = (extracted_value or "").strip() if extracted_value else None

            answers[field] = OnboardingAnswer(
                question=question,
                answer=clean_answer if clean_answer else None,
                extracted_value=clean_extracted if clean_extracted else None,
            )
            pairs_for_debug.append((question, clean_answer))

        profile = CandidateProfile(
            name=candidate_name,
            applied_role=role,
            language=language,
            answers=answers,
        )

        self._write_debug_snapshot(profile, pairs_for_debug)
        populated = self.count_populated_fields(profile)
        logger.info(
            "Built profile with %d/%d answers (no LLM call)",
            populated, len(QUESTION_FIELD_ORDER),
        )
        return profile

    # ----------------------------------------------------------------
    @staticmethod
    def count_populated_fields(profile: CandidateProfile) -> int:
        """How many onboarding answers did the candidate actually give?"""
        return sum(
            1
            for slot in profile.answers.values()
            if slot.answer and slot.answer.strip()
        )

    # ----------------------------------------------------------------
    def _write_debug_snapshot(
        self,
        profile: CandidateProfile,
        qa_pairs: Iterable[tuple[str, str]],
    ) -> None:
        """Persist the profile (and the raw transcript) for diagnostics."""
        try:
            debug_dir: Path = self._settings.debug_dir
            debug_dir.mkdir(parents=True, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            transcript = "\n".join(
                f"Q: {q}\nA: {a if a and a.strip() else '(no answer)'}"
                for q, a in qa_pairs
            )
            payload = {
                "name": profile.name,
                "applied_role": profile.applied_role,
                "language": profile.language,
                "answers": {
                    k: v.model_dump() for k, v in profile.answers.items()
                },
            }
            (debug_dir / f"profile_build_{ts}.txt").write_text(
                "=== INPUT TRANSCRIPT ===\n"
                f"{transcript}\n\n"
                "=== DETERMINISTIC PROFILE (no LLM call) ===\n"
                f"{json.dumps(payload, ensure_ascii=False, indent=2)}",
                encoding="utf-8",
            )
        except Exception as e:  # pragma: no cover — diagnostic only
            logger.warning("(non-fatal) couldn't write profile debug snapshot: %s", e)
