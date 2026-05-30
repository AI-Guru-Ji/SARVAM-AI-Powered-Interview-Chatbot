"""
profile_extract_service.py — Pull one normalized field value out of a
raw STT transcript using sarvam-30b.

Used during profile-building voice confirmation. Given the candidate's
free-form spoken answer (e.g. "mera naam Rajesh Kumar hai aur main 9-8-7
naam ka mobile use karta hoon"), returns the single requested value
("Rajesh Kumar" or "9876543210").

Behaviour:
  - Tight max_tokens (≤80) — extraction output is always short.
  - Low temperature — we want determinism, not creativity.
  - Falls back to the raw transcript on any LLM failure so the
    interview never blocks. Callers should treat the returned string
    as a *best effort*, not ground truth.
"""

from __future__ import annotations

from constants.app_constants import (
    LANGUAGE_NAMES,
    LLM_EXTRACTION_TEMPERATURE,
)
from prompts.profile_extract_prompt import build_profile_extract_prompts
from services.sarvam_llm_service import SarvamLlmService
from utils.exceptions import (
    LlmBudgetExceededError,
    LlmFailedError,
    LlmInvalidResponseError,
)
from utils.helpers import extract_phone_digits, normalise_digits
from utils.logger import get_logger


logger = get_logger(__name__)


# Tight cap — extracted values are always short.
_EXTRACT_MAX_TOKENS = 80


def _trim_location(value: str) -> str:
    """Best-effort cleanup for the LLM's location output.

    If the LLM returned a whole sentence (e.g. "मैं लखनऊ में रहता हूँ"),
    try to recover just the place name. Strategy:
      1. If the value already contains Latin letters and is < 35 chars,
         trust it (it's probably already 'Lucknow' or similar).
      2. Otherwise strip common Indic location verbs/postpositions and
         return whatever non-trivial token remains.
      3. Cap at 35 chars to keep the dashboard pill clean.
    """
    if not value:
        return value
    trimmed = value.strip().rstrip(".।!?")
    has_latin = any("a" <= c.lower() <= "z" for c in trimmed)
    if has_latin and len(trimmed) <= 35:
        return trimmed

    # Strip common Indic location-context words. These are NOT exhaustive
    # but cover the most frequent leak patterns we see in practice.
    fillers = (
        "में रहता हूँ", "में रहती हूँ", "में रहता हूं", "में रहती हूं", "में रहते हैं",
        "shahar", "shahar mein", "main", "मैं", "में",
        "ਵਿੱਚ ਰਹਿੰਦਾ ਹਾਂ", "ਵਿੱਚ ਰਹਿੰਦੀ ਹਾਂ", "ਵਿੱਚ",
        "তে থাকি", "এ থাকি", "তে", "এ",
        "లో ఉంటాను", "లో",
        "ಲ್ಲಿ ವಾಸಿಸುತ್ತೇನೆ", "ನಲ್ಲಿ",
        "ൽ താമസിക്കുന്നു", "ൽ",
        "मध्ये राहतो", "मध्ये राहते", "मध्ये",
        "ରେ ରୁହେ", "ରେ",
        "இல் வசிக்கிறேன்", "இல்",
        "મા રહું છું", "માં",
    )
    for f in fillers:
        trimmed = trimmed.replace(f, " ")
    trimmed = " ".join(trimmed.split())  # collapse whitespace
    return trimmed[:35] if trimmed else value


class ProfileExtractService:
    """Extract a single normalized field value from a raw transcript."""

    def __init__(self, llm_service: SarvamLlmService) -> None:
        self._llm = llm_service

    # ----------------------------------------------------------------
    def extract(self, *, field: str, raw_answer: str, language: str) -> str:
        """Return the cleaned value for `field`, or the raw answer on failure.

        Args:
            field:      One of name / mobile / email / age / location.
            raw_answer: Verbatim STT transcript.
            language:   Short language code (en/hi/bn/te/pa/gu).

        Returns:
            A short, cleaned string. Never raises — falls back to
            `raw_answer.strip()` if the LLM call fails.
        """
        clean = (raw_answer or "").strip()
        if not clean:
            return ""

        lang_name = LANGUAGE_NAMES.get(language, "English")
        system_prompt, user_message = build_profile_extract_prompts(
            field=field,
            raw_answer=clean,
            lang_name=lang_name,
        )

        try:
            completion = self._llm.chat_completion(
                messages=[{"role": "user", "content": user_message}],
                system_prompt=system_prompt,
                max_tokens=_EXTRACT_MAX_TOKENS,
                temperature=LLM_EXTRACTION_TEMPERATURE,
            )
        except (LlmFailedError, LlmInvalidResponseError, LlmBudgetExceededError) as e:
            logger.warning(
                "Profile extraction failed for field=%s (%s) — using raw transcript",
                field, e,
            )
            return clean

        value = (completion.content or "").strip()

        # Strip common artefacts the model still occasionally emits.
        value = value.strip("'\"`").strip()
        if value.startswith("```"):
            value = value.strip("`").strip()

        # ── Field-specific deterministic post-processing ───────────────
        # The LLM extraction prompt asks for clean values, but for Indic
        # languages it sometimes returns the spoken form (e.g. Hindi
        # number words for mobile, or a full sentence for location).
        # These post-processors run AFTER the LLM call to enforce the
        # final shape we promise the rest of the pipeline.
        if field == "mobile":
            # Convert ANY digit-words/native-script digits → ASCII.
            # If we recover a 10-digit number, use it. Otherwise try the
            # raw transcript through the same pipeline (often more digits
            # are present in the raw answer than in the LLM output).
            normalised = extract_phone_digits(value, language=language)
            if not normalised:
                normalised = extract_phone_digits(clean, language=language)
            if normalised:
                logger.info("Mobile post-processed: '%s' → '%s'", value, normalised)
                value = normalised
        elif field == "age":
            # Age is at most 2 digits — same idea, simpler.
            normalised = normalise_digits(value, language=language)
            import re as _re
            digits = _re.sub(r"\D", "", normalised)
            if digits and 10 <= int(digits[:3]) <= 100:
                value = str(int(digits[:3]) if int(digits[:3]) <= 99 else int(digits[:2]))
            elif digits:
                value = digits[:2]
        elif field == "location":
            # If the LLM returned a full sentence, try to find the
            # shortest token that looks like a proper noun (1-3 words,
            # Latin-script preferred). Otherwise leave as-is so the
            # dashboard at least shows something.
            value = _trim_location(value)

        # Sentinel for "not found" — fall back to raw.
        if value in ("", "-", "—"):
            logger.info(
                "Profile extraction returned sentinel for field=%s — keeping raw",
                field,
            )
            return clean

        return value
