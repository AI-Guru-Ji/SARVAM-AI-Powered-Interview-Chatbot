"""
health_check_service.py — Pre-demo verification of Sarvam endpoints.

Probes the LLM + TTS endpoints with tiny payloads, returns a typed
``HealthCheckReport``. STT shares its credential + auth scheme with TTS,
so if TTS passes, STT's auth/connectivity is also fine — we don't ship
a sample WAV just to probe STT.
"""

from __future__ import annotations

import time

import requests

from config.settings import Settings
from constants.app_constants import (
    HTTP_TIMEOUT_HEALTH_CHECK_LLM,
    HTTP_TIMEOUT_HEALTH_CHECK_TTS,
    LLM_HEALTH_CHECK_MAX_TOKENS,
    LLM_MODEL,
    LLM_PATH,
    LLM_REASONING_EFFORT,
    TTS_DEFAULT_SPEAKER,
    TTS_MODEL,
    TTS_PATH,
)
from models.schemas import HealthCheckReport, HealthCheckResult
from utils.logger import get_logger


logger = get_logger(__name__)


class HealthCheckService:
    """Quick smoke test for Sarvam APIs before a live demo."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._headers = {
            "api-subscription-key": settings.sarvam_api_key,
            "Content-Type": "application/json",
        }

    def run(self) -> HealthCheckReport:
        results: list[HealthCheckResult] = []
        results.append(self._check_tts())
        results.append(self._check_llm())
        results.append(self._check_api_key())
        return HealthCheckReport(
            results=results,
            all_ok=all(r.ok for r in results),
        )

    # ----------------------------------------------------------------
    def _check_tts(self) -> HealthCheckResult:
        name = "TTS — Bulbul v3"
        t0 = time.time()
        try:
            url = f"{self._settings.sarvam_base_url}{TTS_PATH}"
            payload = {
                "text": "ok",
                "target_language_code": "en-IN",
                "speaker": TTS_DEFAULT_SPEAKER,
                "speech_sample_rate": 24000,
                "model": TTS_MODEL,
            }
            r = requests.post(
                url, headers=self._headers, json=payload,
                timeout=HTTP_TIMEOUT_HEALTH_CHECK_TTS,
            )
            elapsed = time.time() - t0
            if r.ok:
                return HealthCheckResult(
                    name=name, ok=True, latency_s=elapsed,
                    detail="Voice synthesis is responding.",
                )
            return HealthCheckResult(
                name=name, ok=False, latency_s=elapsed,
                detail=f"HTTP {r.status_code}: {r.text[:200]}",
            )
        except Exception as e:
            return HealthCheckResult(
                name=name, ok=False, latency_s=time.time() - t0,
                detail=f"Exception: {e}",
            )

    # ----------------------------------------------------------------
    def _check_llm(self) -> HealthCheckResult:
        name = f"LLM — {LLM_MODEL}"
        t0 = time.time()
        try:
            url = f"{self._settings.sarvam_base_url}{LLM_PATH}"
            payload = {
                "model": LLM_MODEL,
                "messages": [{"role": "user", "content": "Reply with the single word: ok"}],
                # sarvam-30b reasons even on trivial prompts (~500 tokens of
                # chain-of-thought). Setting max_tokens too low gives false
                # negatives — the model is fine, it just needs more headroom.
                "max_tokens": LLM_HEALTH_CHECK_MAX_TOKENS,
                "temperature": 0.0,
                "reasoning_effort": LLM_REASONING_EFFORT,
            }
            r = requests.post(
                url, headers=self._headers, json=payload,
                timeout=HTTP_TIMEOUT_HEALTH_CHECK_LLM,
            )
            elapsed = time.time() - t0
            if not r.ok:
                return HealthCheckResult(
                    name=name, ok=False, latency_s=elapsed,
                    detail=f"HTTP {r.status_code}: {r.text[:200]}",
                )
            d = r.json()
            ch = d.get("choices", [{}])[0]
            content = (ch.get("message") or {}).get("content")
            if content:
                return HealthCheckResult(
                    name=name, ok=True, latency_s=elapsed,
                    detail="Chat completions are responding.",
                )
            return HealthCheckResult(
                name=name, ok=False, latency_s=elapsed,
                detail=(
                    f"Model returned no content (finish_reason="
                    f"{ch.get('finish_reason')!r}). API is up but the model "
                    f"is currently slow — expect retries during demo."
                ),
            )
        except Exception as e:
            return HealthCheckResult(
                name=name, ok=False, latency_s=time.time() - t0,
                detail=f"Exception: {e}",
            )

    # ----------------------------------------------------------------
    def _check_api_key(self) -> HealthCheckResult:
        key = self._settings.sarvam_api_key
        ok = bool(key)
        return HealthCheckResult(
            name="API key (SARVAM_API_KEY)",
            ok=ok,
            latency_s=0.0,
            detail=(
                "Key set — STT uses the same key, so its auth is OK if TTS passed."
                if ok else "Key MISSING — set SARVAM_API_KEY in .env to enable interviews."
            ),
        )
