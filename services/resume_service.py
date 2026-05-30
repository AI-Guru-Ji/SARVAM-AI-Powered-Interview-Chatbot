"""
resume_service.py — Convert a CandidateProfile into a polished English
resume (text + PDF).

Strategy: two LLM attempts, then a deterministic Python fallback. The
deterministic fallback is never crashy and works for every language —
it just preserves the candidate's verbatim answers under English
section labels.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional

from constants.app_constants import (
    LLM_RESUME_TEMPERATURE,
    QUESTION_FIELD_ORDER,
    RESUME_FIELD_LABELS,
)
from models.schemas import CandidateProfile
from prompts.resume_prompt import RESUME_SYSTEM_PROMPT, build_resume_user_message
from services.sarvam_llm_service import SarvamLlmService
from utils.exceptions import SarvamApiError
from utils.helpers import (
    extract_contact_from_transcripts,
    extract_phone_and_email,
    strip_code_fences,
)
from utils.logger import get_logger
from utils.pdf_renderer import render_resume_to_pdf


logger = get_logger(__name__)

MAX_RESUME_ATTEMPTS = 2


class ResumeService:
    """Generate resume text + PDF for a CandidateProfile."""

    def __init__(
        self,
        llm_service: SarvamLlmService,
        debug_dir: Optional[Path] = None,
    ) -> None:
        self._llm = llm_service
        self._debug_dir = debug_dir

    # ----------------------------------------------------------------
    def build_resume_text(self, profile: CandidateProfile) -> str:
        """Generate a 1-page English resume. Always returns a usable
        string — never raises.

        Tries the LLM twice; if both attempts fail, falls back to a
        deterministic Python formatter that displays the candidate's
        verbatim answers under English section labels.
        """
        for attempt in range(1, MAX_RESUME_ATTEMPTS + 1):
            try:
                return self._llm_resume_text(profile)
            except SarvamApiError as e:
                logger.warning(
                    "Resume LLM attempt %d/%d failed: %s",
                    attempt, MAX_RESUME_ATTEMPTS, e,
                )
                if attempt < MAX_RESUME_ATTEMPTS:
                    logger.info("Retrying resume generation once...")
        logger.error("Both LLM attempts exhausted — using deterministic fallback")
        return self._deterministic_resume_text(profile)

    # ----------------------------------------------------------------
    @staticmethod
    def build_resume_pdf(resume_text: str, candidate_name: str = "Candidate") -> bytes:
        """Render the resume text as an A4 PDF."""
        return render_resume_to_pdf(resume_text, candidate_name)

    # ----------------------------------------------------------------
    def _llm_resume_text(self, profile: CandidateProfile) -> str:
        """Single attempt: call sarvam-30b with the resume-writer prompt."""
        name = profile.name or "Candidate"
        role = profile.applied_role.replace("_", " ")
        answers = profile.answers

        transcript_lines: list[str] = []
        for i, field in enumerate(QUESTION_FIELD_ORDER, start=1):
            slot = answers.get(field)
            q = slot.question if slot else ""
            a = (slot.answer if slot and slot.answer else "(no answer)")
            transcript_lines.append(f"Q{i} ({field}): {q}")
            transcript_lines.append(f"A{i}: {a}")
        transcript = "\n".join(transcript_lines)

        # Deterministically extract the phone number so the LLM cannot
        # invent or miss it. Email is intentionally NOT asked during the
        # voice interview, so the resume always shows an
        # "Email: [To be filled]" placeholder (recruiters capture email
        # via WhatsApp/SMS after the call).
        #
        # Strategy for phone:
        #   1. First read the dedicated `mobile` slot. If voice-confirmed,
        #      `extracted_value` holds the clean 10-digit form.
        #   2. If missing, scan EVERY answer — candidates sometimes
        #      re-state their number when asked something else.
        def _slot_value(field: str) -> str:
            slot = answers.get(field)
            if not slot:
                return ""
            # Prefer the voice-confirmed extracted value when present.
            return (slot.extracted_value or slot.answer or "").strip()

        mobile_raw = _slot_value("mobile")
        phone, _maybe_email = extract_phone_and_email(mobile_raw)
        if not phone:
            all_answers = [
                slot.answer for slot in answers.values() if slot and slot.answer
            ]
            fb_phone, _ = extract_contact_from_transcripts(all_answers)
            phone = phone or fb_phone
        logger.info("Resume contact extraction: phone=%s", phone or "(none)")
        phone_line = f"Phone: {phone}" if phone else "Phone: [To be filled]"

        user_message = build_resume_user_message(
            name=name,
            role=role,
            language=profile.language,    # makes the prompt language-aware
            transcript=transcript,
            phone_line=phone_line,
        )

        completion = self._llm.chat_completion(
            messages=[{"role": "user", "content": user_message}],
            system_prompt=RESUME_SYSTEM_PROMPT,
            temperature=LLM_RESUME_TEMPERATURE,
        )

        self._write_debug_snapshot(transcript, completion.content)

        text = strip_code_fences(completion.content)
        if not text.strip():
            raise SarvamApiError("LLM returned empty resume content")
        return text

    # ----------------------------------------------------------------
    @staticmethod
    def _deterministic_resume_text(profile: CandidateProfile) -> str:
        """Never-fails fallback: just lay out the verbatim Q&A under
        English section labels."""
        name = profile.name or "Candidate"
        role = profile.applied_role or "—"
        answers = profile.answers

        lines: list[str] = []
        lines.append(str(name).upper())
        lines.append(f"Applied for: {role.replace('_', ' ').title()}")
        lines.append("")
        lines.append("OBJECTIVE")
        lines.append(f"  Seeking a {role.replace('_', ' ')} role.")
        lines.append("")

        for field in QUESTION_FIELD_ORDER:
            slot = answers.get(field)
            if not slot:
                continue
            # Prefer the voice-confirmed extracted value when present;
            # fall back to the verbatim transcript.
            display = (slot.extracted_value or slot.answer or "").strip()
            if not display:
                continue
            label = RESUME_FIELD_LABELS.get(field, field.replace("_", " ").title())
            lines.append(label.upper())
            for chunk in _wrap_text(display, width=78):
                lines.append(f"  {chunk}")
            lines.append("")

        while lines and lines[-1] == "":
            lines.pop()
        return "\n".join(lines)

    # ----------------------------------------------------------------
    def _write_debug_snapshot(self, transcript: str, raw_resume: str) -> None:
        if not self._debug_dir:
            return
        try:
            self._debug_dir.mkdir(parents=True, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            (self._debug_dir / f"resume_llm_{ts}.txt").write_text(
                "=== TRANSCRIPT SENT TO LLM ===\n"
                f"{transcript}\n\n"
                "=== RAW LLM RESUME ===\n"
                f"{raw_resume or '(empty)'}",
                encoding="utf-8",
            )
        except Exception as e:  # pragma: no cover
            logger.warning("(non-fatal) couldn't write resume debug snapshot: %s", e)


# Module-level helper (not part of the public service surface).
def _wrap_text(text: str, width: int = 78) -> list[str]:
    """Wrap a line at word boundaries while preserving multi-byte words."""
    words = text.split(" ")
    if not words:
        return [text]
    out: list[str] = []
    current = ""
    for w in words:
        if not current:
            current = w
        elif len(current) + 1 + len(w) <= width:
            current += " " + w
        else:
            out.append(current)
            current = w
    if current:
        out.append(current)
    return out
