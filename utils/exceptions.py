"""
exceptions.py — Custom exception hierarchy for the interview bot.

Services raise the most specific exception possible so callers can
react precisely (e.g. show a "retry" button only on token-budget errors
versus a generic error toast on network problems).

Hierarchy::

    InterviewBotError                   (base)
    ├── SarvamApiError                  (any Sarvam REST failure)
    │   ├── SttAudioTooShortError       (client-side rejection before sending)
    │   ├── SttFailedError              (Sarvam STT returned non-2xx or bad JSON)
    │   ├── TtsFailedError              (Sarvam TTS returned non-2xx or bad JSON)
    │   ├── LlmFailedError              (Sarvam LLM returned non-2xx)
    │   ├── LlmInvalidResponseError     (200 OK but response shape is wrong)
    │   └── LlmBudgetExceededError      (finish_reason='length', content=None)
    └── ProfileBuildError               (profile / resume failed to build)
"""

from __future__ import annotations


class InterviewBotError(Exception):
    """Base class for every exception raised by this codebase."""


class SarvamApiError(InterviewBotError):
    """Base class for any error talking to a Sarvam endpoint."""


class SttAudioTooShortError(SarvamApiError):
    """Client-side guard tripped: WAV is too short to contain real audio.

    Raised before the HTTP request is sent, so no API quota is spent.
    """


class SttFailedError(SarvamApiError):
    """Sarvam STT returned a non-2xx response or unparsable body."""


class TtsFailedError(SarvamApiError):
    """Sarvam TTS returned a non-2xx response or contained no audio."""


class LlmFailedError(SarvamApiError):
    """Sarvam LLM returned a non-2xx response."""


class LlmInvalidResponseError(SarvamApiError):
    """LLM responded with 200 OK but the body shape is unexpected."""


class LlmBudgetExceededError(SarvamApiError):
    """LLM returned content=None with finish_reason='length'.

    The model exhausted ``max_tokens`` on its reasoning preamble before
    emitting any answer. Callers typically catch this and retry with a
    smaller request or a different language.

    Attributes:
        finish_reason: The model's reported finish reason (always 'length' here).
        max_tokens:    The ``max_tokens`` cap that was hit.
        partial:       Any reasoning_content / partial text the model produced.
    """

    def __init__(self, finish_reason: str, max_tokens: int, partial: str = "") -> None:
        self.finish_reason = finish_reason
        self.max_tokens = max_tokens
        self.partial = partial
        super().__init__(
            f"LLM returned content=None (finish_reason={finish_reason!r}, "
            f"max_tokens={max_tokens}). "
            f"Partial output: {partial[:300]}"
        )


class ProfileBuildError(InterviewBotError):
    """Something went wrong building the candidate profile or resume."""
