"""
decide_next_turn_service.py — Decide whether to ask a follow-up or move on.

Called after every candidate answer during the interview stage. Returns
``{"action": "follow_up", "question": "..."}`` or ``{"action": "next"}``.

Errors are caught internally and default to "next" so the interview
never stalls on an LLM blip.
"""

from __future__ import annotations

from constants.app_constants import MAX_FOLLOW_UPS_PER_QUESTION
from models.schemas import TurnDecision
from prompts.decide_next_turn_prompt import build_decide_next_turn_prompts
from services.sarvam_llm_service import SarvamLlmService
from utils.exceptions import SarvamApiError
from utils.helpers import parse_json_lenient
from utils.logger import get_logger


logger = get_logger(__name__)


class DecideNextTurnService:
    """In-interview follow-up decision."""

    def __init__(self, llm_service: SarvamLlmService) -> None:
        self._llm = llm_service

    def decide(
        self,
        *,
        role: str,
        question: str,
        answer: str,
        follow_up_count: int,
        language: str = "en",
        max_follow_ups: int = MAX_FOLLOW_UPS_PER_QUESTION,
    ) -> TurnDecision:
        """Return the bot's next-action decision."""
        # Hard caps first — never call the LLM if we can short-circuit.
        if follow_up_count >= max_follow_ups:
            return TurnDecision(action="next")
        if not answer or not answer.strip() or answer.strip().lower().startswith("no answer"):
            return TurnDecision(action="next")

        lang_name = "Hindi" if language == "hi" else "English"
        sp, um = build_decide_next_turn_prompts(
            role=role,
            question=question,
            answer=answer,
            follow_up_count=follow_up_count,
            max_follow_ups=max_follow_ups,
            lang_name=lang_name,
        )

        try:
            completion = self._llm.chat_completion(
                messages=[{"role": "user", "content": um}],
                system_prompt=sp,
            )
        except SarvamApiError as e:
            logger.warning("decide_next_turn LLM error (%s) — defaulting to 'next'", e)
            return TurnDecision(action="next")

        decision = parse_json_lenient(completion.content)
        if decision is None:
            logger.warning("decide_next_turn could not parse JSON — defaulting to 'next'")
            return TurnDecision(action="next")

        if decision.get("action") == "follow_up" and decision.get("question"):
            return TurnDecision(
                action="follow_up",
                question=str(decision["question"]).strip(),
            )
        return TurnDecision(action="next")
