"""
sarvam_tts_service.py — Sarvam text-to-speech wrapper (Bulbul v3).
"""

from __future__ import annotations

import base64

import requests

from config.settings import Settings
from constants.app_constants import (
    HTTP_TIMEOUT_TTS,
    TTS_DEFAULT_SPEAKER,
    TTS_MODEL,
    TTS_PATH,
    TTS_SAMPLE_RATE,
)
from models.schemas import TtsResult
from utils.exceptions import TtsFailedError
from utils.logger import get_logger


logger = get_logger(__name__)


class SarvamTtsService:
    """Wrapper around POST /text-to-speech."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._url = f"{settings.sarvam_base_url}{TTS_PATH}"
        self._headers = {
            "api-subscription-key": settings.sarvam_api_key,
            "Content-Type": "application/json",
        }

    def text_to_speech(
        self,
        text: str,
        output_path: str,
        language_code: str = "hi-IN",
    ) -> TtsResult:
        """Synthesize speech using Bulbul v3 and write the WAV to disk.

        Args:
            text:          Text to convert (keep under 500 chars per call).
            output_path:   Filesystem path to write the .wav file to.
            language_code: BCP-47 code (e.g. "hi-IN", "en-IN").

        Raises:
            TtsFailedError: Sarvam returned non-2xx or no audio.
        """
        payload = {
            "text": text,
            "target_language_code": language_code,
            "speaker": TTS_DEFAULT_SPEAKER,
            "speech_sample_rate": TTS_SAMPLE_RATE,
            "model": TTS_MODEL,
        }

        response = requests.post(
            self._url,
            headers=self._headers,
            json=payload,
            timeout=HTTP_TIMEOUT_TTS,
        )
        if not response.ok:
            logger.warning("TTS HTTP %s — %s", response.status_code, response.text[:200])
            raise TtsFailedError(
                f"Sarvam TTS {response.status_code}: {response.text[:500]}"
            )

        result = response.json()
        audio_data = result.get("audios", [None])[0]
        if not audio_data:
            raise TtsFailedError("No audio returned from TTS API")

        audio_bytes = base64.b64decode(audio_data)
        with open(output_path, "wb") as f:
            f.write(audio_bytes)

        logger.debug("TTS audio saved to %s (%d bytes)", output_path, len(audio_bytes))
        return TtsResult(audio_bytes=audio_bytes, saved_path=output_path)
