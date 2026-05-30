"""
sarvam_stt_service.py — Sarvam speech-to-text wrapper (Saaras v3).

The size guard (MIN_REAL_AUDIO_BYTES) rejects header-only WAVs the
browser audio widget sometimes emits, BEFORE we spend an API call on
them. That bug used to cause spurious 400 errors during demos.
"""

from __future__ import annotations

import os
import requests

from config.settings import Settings
from constants.app_constants import (
    HTTP_TIMEOUT_STT,
    MIN_REAL_AUDIO_BYTES,
    STT_MODEL,
    STT_PATH,
)
from models.schemas import SttResult
from utils.exceptions import SttAudioTooShortError, SttFailedError
from utils.logger import get_logger


logger = get_logger(__name__)


class SarvamSttService:
    """Wrapper around POST /speech-to-text."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._url = f"{settings.sarvam_base_url}{STT_PATH}"

    def speech_to_text(
        self,
        audio_file_path: str,
        language_code: str = "hi-IN",
    ) -> SttResult:
        """Transcribe a WAV file using Saaras v3.

        Args:
            audio_file_path: Path to a .wav file (max 30 seconds).
            language_code:   BCP-47 code or "unknown" for auto-detect.

        Raises:
            SttAudioTooShortError: WAV is too small to contain real audio.
            SttFailedError:        Sarvam returned non-2xx.
        """
        with open(audio_file_path, "rb") as f:
            audio_bytes = f.read()

        if len(audio_bytes) < MIN_REAL_AUDIO_BYTES:
            raise SttAudioTooShortError(
                f"Audio too short ({len(audio_bytes)} bytes). "
                "Please click the mic and speak for at least 1 second."
            )

        files = {
            "file": (
                os.path.basename(audio_file_path),
                audio_bytes,
                "audio/wav",
            ),
        }
        data = {"model": STT_MODEL, "language_code": language_code}
        headers = {"api-subscription-key": self._settings.sarvam_api_key}

        response = requests.post(
            self._url,
            headers=headers,
            files=files,
            data=data,
            timeout=HTTP_TIMEOUT_STT,
        )

        if not response.ok:
            raise SttFailedError(
                f"Sarvam STT {response.status_code}: {response.text[:500]}"
            )

        result = response.json()
        transcript = (result.get("transcript") or "").strip()
        logger.info("STT transcribed: %s", transcript[:120])
        return SttResult(transcript=transcript, language_code=language_code)
