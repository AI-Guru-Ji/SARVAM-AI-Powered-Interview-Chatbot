"""
conftest.py — Shared pytest fixtures.

Builds a Settings instance with a fake API key and a temp output dir so
unit tests never hit the real Sarvam API or write into the project's
output/ folder.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from config.settings import Settings
from services.sarvam_llm_service import SarvamLlmService


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    s = Settings(
        sarvam_api_key="test-key",
        sarvam_base_url="https://test.invalid",
        output_dir=tmp_path,
        log_level="DEBUG",
    )
    s.ensure_dirs()
    return s


@pytest.fixture
def mock_llm() -> MagicMock:
    """A MagicMock standing in for SarvamLlmService.

    Use ``mock_llm.chat_completion.return_value = LlmCompletion(content=..., finish_reason="stop")``
    to script responses per test.
    """
    return MagicMock(spec=SarvamLlmService)
