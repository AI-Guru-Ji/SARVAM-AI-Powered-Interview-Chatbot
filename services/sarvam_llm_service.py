"""
sarvam_llm_service.py — Sarvam chat-completions API wrapper.

Thin transport layer. Higher-level services (evaluation, resume,
decide_next_turn) build prompts and call ``chat_completion`` here.

Raises:
    LlmFailedError:           non-2xx response or unparsable body
    LlmInvalidResponseError:  200 OK but JSON shape is unexpected
    LlmBudgetExceededError:   content=None with finish_reason='length'
"""

from __future__ import annotations

import requests

from config.settings import Settings
from constants.app_constants import (
    HTTP_TIMEOUT_LLM,
    LLM_DEFAULT_MAX_TOKENS,
    LLM_DEFAULT_TEMPERATURE,
    LLM_MODEL,
    LLM_PATH,
    LLM_REASONING_EFFORT,
)
from models.schemas import LlmCompletion
from utils.exceptions import (
    LlmBudgetExceededError,
    LlmFailedError,
    LlmInvalidResponseError,
)
from utils.logger import get_logger


logger = get_logger(__name__)


class SarvamLlmService:
    """Wrapper around POST /v1/chat/completions."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._url = f"{settings.sarvam_base_url}{LLM_PATH}"
        self._headers = {
            "api-subscription-key": settings.sarvam_api_key,
            "Content-Type": "application/json",
        }

    def chat_completion(
        self,
        *,
        messages: list[dict],
        system_prompt: str = "",
        max_tokens: int = LLM_DEFAULT_MAX_TOKENS,
        temperature: float = LLM_DEFAULT_TEMPERATURE,
    ) -> LlmCompletion:
        """Send a chat request and return the typed completion.

        Raises one of LlmFailedError / LlmInvalidResponseError /
        LlmBudgetExceededError on failure. Callers catch and decide
        whether to retry, fall back, or surface a graceful error.
        """
        full_messages: list[dict] = []
        if system_prompt:
            full_messages.append({"role": "system", "content": system_prompt})
        full_messages.extend(messages)

        payload = {
            "model": LLM_MODEL,
            "messages": full_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "reasoning_effort": LLM_REASONING_EFFORT,
        }

        response = requests.post(
            self._url,
            headers=self._headers,
            json=payload,
            timeout=HTTP_TIMEOUT_LLM,
        )
        logger.debug("LLM HTTP %s — body (first 400 chars): %s",
                     response.status_code, response.text[:400])

        if not response.ok:
            raise LlmFailedError(
                f"Sarvam LLM {response.status_code}: {response.text[:500]}"
            )

        result = response.json()
        try:
            choice = result["choices"][0]
            reply = choice["message"]["content"]
        except (KeyError, IndexError, TypeError) as e:
            raise LlmInvalidResponseError(
                f"Unexpected LLM response shape ({e}): {result}"
            ) from e

        if reply is None:
            finish = choice.get("finish_reason", "unknown")
            partial = (
                (choice.get("message") or {}).get("reasoning_content")
                or (choice.get("delta") or {}).get("content")
                or ""
            )
            raise LlmBudgetExceededError(
                finish_reason=str(finish),
                max_tokens=max_tokens,
                partial=str(partial),
            )

        return LlmCompletion(
            content=reply,
            finish_reason=choice.get("finish_reason"),
        )
