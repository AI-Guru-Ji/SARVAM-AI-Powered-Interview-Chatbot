"""
meta.py — Public ``/v1/config`` endpoint.

Returns the list of supported roles and languages so the mobile app's
setup screen stays in sync with the backend without an app update.
"""

from __future__ import annotations

from fastapi import APIRouter

from constants.app_constants import BEHAVIORAL_QUESTION_COUNT
from data.interview_questions import LANGUAGES, QUESTION_BANK
from data.profile_questions import PROFILE_QUESTIONS
from ui.fastapi.schemas import (
    ConfigResponse,
    LanguageOption,
    RoleOption,
)


router = APIRouter(prefix="/v1", tags=["meta"])


@router.get("/config", response_model=ConfigResponse)
def config() -> ConfigResponse:
    roles = [
        RoleOption(key=k, title=v.get("title", k))
        for k, v in QUESTION_BANK.items()
    ]
    languages = [
        LanguageOption(code=code, label=label, bcp47=bcp47)
        for label, (code, bcp47) in LANGUAGES.items()
    ]
    return ConfigResponse(
        roles=roles,
        languages=languages,
        behavioral_question_count=BEHAVIORAL_QUESTION_COUNT,
        profile_question_count=len(PROFILE_QUESTIONS),
    )
