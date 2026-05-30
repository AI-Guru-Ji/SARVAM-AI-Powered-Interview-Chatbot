"""
profile_enrich_service.py — Structured-extraction of skills + work
history from the profile-building transcript.

Runs once at the profile_building stage, alongside ProfileService.
Output feeds the recruiter dashboard (chips + work-history cards).
Never raises — falls back to an empty ProfileEnrichment on any failure
so the rest of the pipeline keeps working.
"""

from __future__ import annotations

from constants.app_constants import (
    LANGUAGE_NAMES,
    LLM_EXTRACTION_TEMPERATURE,
)
from models.schemas import CandidateProfile, ProfileEnrichment, WorkHistoryEntry
from prompts.profile_enrich_prompt import build_profile_enrich_prompts
from services.sarvam_llm_service import SarvamLlmService
from utils.exceptions import (
    LlmBudgetExceededError,
    LlmFailedError,
    LlmInvalidResponseError,
)
from utils.helpers import parse_json_lenient
from utils.logger import get_logger


logger = get_logger(__name__)


# Enrichment output now includes 5 English summary fields plus
# skills + work history. Bump token budget to keep margin.
_ENRICH_MAX_TOKENS = 1400


def _clean_str(value, max_len: int = 80) -> str:
    """Coerce LLM output to a clean short string. Empty if unusable."""
    if value is None:
        return ""
    s = str(value).strip().strip("`'\"")
    # Drop the JSON-null literal if the LLM emitted it as a string
    if s.lower() in ("null", "none", "n/a", "na", "-", "—"):
        return ""
    return s[:max_len]


class ProfileEnrichService:
    """Extract structured skills + work history from a CandidateProfile."""

    def __init__(self, llm_service: SarvamLlmService) -> None:
        self._llm = llm_service

    # ----------------------------------------------------------------
    def enrich(self, profile: CandidateProfile) -> ProfileEnrichment:
        """Return a ProfileEnrichment. Never raises — empty on failure.

        Args:
            profile: The deterministically built CandidateProfile.
        """
        role = profile.applied_role.replace("_", " ").title()
        lang_name = LANGUAGE_NAMES.get(profile.language, "an Indian language")
        transcript = self._format_transcript(profile)

        if not transcript.strip():
            logger.info("Profile transcript is empty — skipping enrichment")
            return ProfileEnrichment()

        system_prompt, user_message = build_profile_enrich_prompts(
            role=role,
            role_key=profile.applied_role,
            transcript=transcript,
            candidate_lang_name=lang_name,
        )

        try:
            completion = self._llm.chat_completion(
                messages=[{"role": "user", "content": user_message}],
                system_prompt=system_prompt,
                max_tokens=_ENRICH_MAX_TOKENS,
                temperature=LLM_EXTRACTION_TEMPERATURE,
            )
        except (LlmFailedError, LlmInvalidResponseError, LlmBudgetExceededError) as e:
            logger.warning("Profile enrichment LLM call failed: %s", e)
            return ProfileEnrichment()

        raw = (completion.content or "").strip()
        try:
            data = parse_json_lenient(raw)
        except Exception as e:  # pragma: no cover — defensive
            logger.warning("Profile enrichment JSON parse failed: %s — raw: %s", e, raw[:200])
            return ProfileEnrichment()

        if not isinstance(data, dict):
            return ProfileEnrichment()

        # Normalise skills
        raw_skills = data.get("skills") or []
        skills: list[str] = []
        if isinstance(raw_skills, list):
            seen: set[str] = set()
            for s in raw_skills:
                if not isinstance(s, str):
                    continue
                clean = s.strip()
                key = clean.lower()
                if clean and key not in seen:
                    seen.add(key)
                    skills.append(clean)

        # Normalise work history
        raw_jobs = data.get("work_history") or []
        work_history: list[WorkHistoryEntry] = []
        if isinstance(raw_jobs, list):
            for job in raw_jobs:
                if not isinstance(job, dict):
                    continue
                title = str(job.get("title", "")).strip()
                employer = str(job.get("employer", "")).strip()
                if not (title or employer):
                    continue
                work_history.append(
                    WorkHistoryEntry(
                        title=title or "(unspecified role)",
                        employer=employer or "",
                        dates=str(job.get("dates", "")).strip(),
                        duration=str(job.get("duration", "")).strip(),
                    )
                )

        # English summary labels for the dashboard's personal-details
        # section. These replace the raw Hindi/Indic transcripts that
        # were leaking into the recruiter view.
        education_en = _clean_str(data.get("education_en"))
        salary_en = _clean_str(data.get("salary_en"))
        availability_en = _clean_str(data.get("availability_en"))
        marital_status_en = _clean_str(data.get("marital_status_en"), max_len=40)
        dependents_en = _clean_str(data.get("dependents_en"))

        logger.info(
            "Profile enrichment: %d skills, %d work entries, "
            "education_en=%r, salary_en=%r, availability_en=%r, "
            "marital_status_en=%r, dependents_en=%r",
            len(skills), len(work_history),
            education_en, salary_en, availability_en,
            marital_status_en, dependents_en,
        )
        return ProfileEnrichment(
            skills=skills,
            work_history=work_history,
            education_en=education_en,
            salary_en=salary_en,
            availability_en=availability_en,
            marital_status_en=marital_status_en,
            dependents_en=dependents_en,
        )

    # ----------------------------------------------------------------
    @staticmethod
    def _format_transcript(profile: CandidateProfile) -> str:
        """Build a numbered Q&A transcript for the LLM."""
        lines: list[str] = []
        for i, (field, slot) in enumerate(profile.answers.items(), start=1):
            if not slot:
                continue
            answer = (slot.extracted_value or slot.answer or "").strip()
            if not answer:
                continue
            lines.append(f"Q{i} ({field}): {slot.question}")
            lines.append(f"A{i}: {answer}")
        return "\n".join(lines)
