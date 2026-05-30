"""
behavioral_eval_service.py — Score the candidate's behavioral interview.

Runs the LLM rubric prompt once over the 5 scenario answers and parses
the result into a BehavioralEvaluation. Adds deterministic trust signals
from the audio-timing metadata captured in profile_view (Phase D).

Never raises — falls back to a BehavioralEvaluation with
``generation_failed=True`` so the report view can hide the section
gracefully if Sarvam returns garbage.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional

from constants.app_constants import (
    LANGUAGE_NAMES,
    LLM_EVAL_TEMPERATURE,
)
from models.schemas import BehavioralEvaluation
from prompts.behavioral_eval_prompt import build_behavioral_eval_prompts
from services.sarvam_llm_service import SarvamLlmService
from utils.exceptions import (
    LlmBudgetExceededError,
    LlmFailedError,
    LlmInvalidResponseError,
)
from utils.helpers import parse_json_lenient, strip_code_fences
from utils.logger import get_logger


logger = get_logger(__name__)


_EVAL_MAX_TOKENS = 1800  # bumped from 1200 — Devanagari input eats ~3× tokens


def _dump_raw_to_debug(raw: str, tag: str) -> None:
    """Persist a raw LLM response so the cause of a parse failure can be
    diagnosed later. Best-effort — never raises."""
    try:
        debug_dir = Path("output") / "debug"
        debug_dir.mkdir(parents=True, exist_ok=True)
        path = debug_dir / f"behavioral_llm_{tag}_{datetime.now():%Y%m%d_%H%M%S}.txt"
        path.write_text(raw, encoding="utf-8")
        logger.info("Behavioral raw LLM response saved to %s", path)
    except Exception:  # pragma: no cover
        pass


def _regex_recover(raw: str) -> dict:
    """Extract trait scores + summary from a truncated/malformed LLM response.

    Mirrors the regex recovery in ``evaluation_service`` so a single
    truncated response still yields a usable trust profile instead of
    a blank ``generation_failed=True`` card.
    """
    clean = strip_code_fences(raw)

    def _num(key: str) -> Optional[float]:
        m = re.search(rf'"{key}"\s*:\s*(\d+(?:\.\d+)?)', clean)
        if not m:
            return None
        try:
            return float(m.group(1))
        except ValueError:
            return None

    def _str(key: str) -> Optional[str]:
        m = re.search(rf'"{key}"\s*:\s*"((?:[^"\\]|\\.)*?)"', clean, re.DOTALL)
        if not m:
            return None
        try:
            return json.loads(f'"{m.group(1)}"')
        except json.JSONDecodeError:
            return m.group(1).strip()

    # Per-trait reasoning: look for a nested object after the key
    reasoning: dict[str, str] = {}
    rm = re.search(
        r'"per_trait_reasoning"\s*:\s*\{(.*?)\}', clean, re.DOTALL,
    )
    if rm:
        for k, v in re.findall(
            r'"(\w+)"\s*:\s*"((?:[^"\\]|\\.)*?)"', rm.group(1), re.DOTALL,
        ):
            try:
                reasoning[k] = json.loads(f'"{v}"')
            except json.JSONDecodeError:
                reasoning[k] = v.strip()

    consistency = _str("cross_question_consistency")
    if consistency:
        consistency = consistency.strip().lower()
        if consistency not in ("high", "medium", "low"):
            consistency = None

    return {
        "honesty": _num("honesty"),
        "reliability": _num("reliability"),
        "stress_tolerance": _num("stress_tolerance"),
        "customer_orientation": _num("customer_orientation"),
        "earning_attitude": _num("earning_attitude"),
        "overall_summary": _str("overall_summary"),
        "per_trait_reasoning": reasoning,
        "answer_specificity": _num("answer_specificity"),
        "cross_question_consistency": consistency,
    }


def _clamp_score(value, default: float = 5.0) -> float:
    """Coerce LLM output to a 0-10 number; default if unparseable."""
    try:
        f = float(value)
        return max(0.0, min(10.0, f))
    except (TypeError, ValueError):
        return default


class BehavioralEvalService:
    """Score the 5 behavioral traits + compute trust signals."""

    def __init__(self, llm_service: SarvamLlmService) -> None:
        self._llm = llm_service

    # ----------------------------------------------------------------
    def evaluate(
        self,
        *,
        role: str,
        language: str,
        transcripts: Iterable[dict],
    ) -> BehavioralEvaluation:
        """Return a BehavioralEvaluation. Never raises.

        Args:
            role:        Role key (e.g. 'security_guard').
            language:    Candidate's interview language code.
            transcripts: Iterable of dicts shaped like:
                         {"question": "...", "answer": "...",
                          "response_seconds": float | None}
                         Order matters — must match the order of
                         BEHAVIORAL_QUESTIONS.
        """
        items = [t for t in transcripts if t]
        if not items:
            logger.warning("Behavioral evaluator received empty transcript list")
            return BehavioralEvaluation(generation_failed=True)

        # Build numbered Q&A block for the prompt
        qa_pairs_text = "\n".join(
            f"Q{i+1}: {t['question']}\nA{i+1}: {t.get('answer', '').strip() or '(no answer)'}"
            for i, t in enumerate(items)
        )

        role_label = role.replace("_", " ").title()
        lang_name = LANGUAGE_NAMES.get(language, "an Indian language")

        system_prompt, user_message = build_behavioral_eval_prompts(
            role=role_label,
            candidate_lang_name=lang_name,
            qa_pairs_text=qa_pairs_text,
        )

        raw: str = ""
        try:
            completion = self._llm.chat_completion(
                messages=[{"role": "user", "content": user_message}],
                system_prompt=system_prompt,
                max_tokens=_EVAL_MAX_TOKENS,
                temperature=LLM_EVAL_TEMPERATURE,
            )
            raw = (completion.content or "").strip()
        except LlmBudgetExceededError as e:
            # Sarvam ran out of tokens mid-output. Try to recover whatever
            # partial JSON was emitted before the cutoff.
            logger.warning(
                "Behavioral LLM hit token budget — attempting partial recovery (partial=%d chars)",
                len(e.partial or ""),
            )
            raw = (e.partial or "").strip()
        except (LlmFailedError, LlmInvalidResponseError) as e:
            logger.warning("Behavioral LLM call failed: %s", e)
            _dump_raw_to_debug(str(e), tag="api_error")
            return self._fallback_with_signals(items)

        if not raw:
            logger.warning("Behavioral LLM returned empty content")
            return self._fallback_with_signals(items)

        # First try lenient JSON parse, then fall back to regex recovery
        # (mirrors evaluation_service partial-JSON recovery).
        data: Optional[dict] = None
        try:
            parsed = parse_json_lenient(raw)
            if isinstance(parsed, dict):
                data = parsed
        except Exception as e:  # pragma: no cover
            logger.warning("Behavioral JSON parse failed: %s", e)

        if data is None:
            logger.warning(
                "Behavioral JSON parse failed — attempting regex recovery on response (%d chars)",
                len(raw),
            )
            _dump_raw_to_debug(raw, tag="parse_failed")
            data = _regex_recover(raw)

        if not data or not any(
            data.get(k) is not None
            for k in ("honesty", "reliability", "stress_tolerance",
                      "customer_orientation", "earning_attitude")
        ):
            logger.warning("Behavioral recovery yielded no usable scores")
            return self._fallback_with_signals(items)

        # Per-trait reasoning dict — coerce string keys/values
        raw_reasoning = data.get("per_trait_reasoning") or {}
        if isinstance(raw_reasoning, dict):
            reasoning = {
                str(k): str(v).strip()
                for k, v in raw_reasoning.items()
                if v and str(v).strip()
            }
        else:
            reasoning = {}

        consistency_raw = str(data.get("cross_question_consistency", "")).strip().lower()
        consistency = consistency_raw if consistency_raw in ("high", "medium", "low") else None

        # Deterministic timing signal from audio capture
        avg_response = self._avg_response_time(items)

        # Coerce summary (handle list-typed bug like in evaluation_service)
        raw_summary = data.get("overall_summary")
        if isinstance(raw_summary, list):
            raw_summary = " ".join(str(s).strip() for s in raw_summary if s)
        summary = str(raw_summary or "").strip() or "—"

        evaluation = BehavioralEvaluation(
            honesty=_clamp_score(data.get("honesty")),
            reliability=_clamp_score(data.get("reliability")),
            stress_tolerance=_clamp_score(data.get("stress_tolerance")),
            customer_orientation=_clamp_score(data.get("customer_orientation")),
            earning_attitude=_clamp_score(data.get("earning_attitude")),
            overall_summary=summary,
            per_trait_reasoning=reasoning,
            avg_response_seconds=avg_response,
            answer_specificity=_clamp_score(data.get("answer_specificity"), default=5.0),
            cross_question_consistency=consistency,
        )

        logger.info(
            "Behavioral eval: H=%.1f R=%.1f S=%.1f C=%.1f E=%.1f  avg_response=%s consistency=%s",
            evaluation.honesty, evaluation.reliability, evaluation.stress_tolerance,
            evaluation.customer_orientation, evaluation.earning_attitude,
            f"{avg_response:.1f}s" if avg_response else "n/a",
            consistency or "n/a",
        )
        return evaluation

    # ----------------------------------------------------------------
    def _fallback_with_signals(
        self,
        items: list[dict],
    ) -> BehavioralEvaluation:
        """When LLM fails, still surface the deterministic timing signal."""
        return BehavioralEvaluation(
            generation_failed=True,
            avg_response_seconds=self._avg_response_time(items),
        )

    # ----------------------------------------------------------------
    @staticmethod
    def _avg_response_time(items: list[dict]) -> float | None:
        """Mean time-to-first-word in seconds across all answered Qs."""
        values = [
            float(t["response_seconds"])
            for t in items
            if t.get("response_seconds") is not None and t.get("answer", "").strip()
        ]
        if not values:
            return None
        return sum(values) / len(values)
