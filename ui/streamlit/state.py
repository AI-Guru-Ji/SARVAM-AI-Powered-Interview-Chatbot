"""
state.py — Streamlit session-state defaults and reset helpers.

State is split into two lifecycle buckets:

  * SESSION_LEVEL — persists across multiple consecutive interviews on
    the same browser tab. The welcome unlock flag, the TTS audio cache,
    and the "welcome already played once" flag all belong here.
    Wiping them would needlessly replay the welcome and re-show the
    unlock overlay between interviews.

  * INTERVIEW_LEVEL — one interview's worth of data. Everything from
    "who is the candidate" through to the final evaluation report.
    This bucket gets wiped when starting a new interview.

Use ``reset_interview()`` for the "🔄 New interview" / "❌ Abort" flows.
Use ``reset_all()`` only for genuine session resets (rare; effectively
equivalent to a hard browser refresh).
"""

from __future__ import annotations

import copy

import streamlit as st

from constants.app_constants import STAGE_SETUP


# ──────────────────────────────────────────────────────────────────────
# INTERVIEW-LEVEL defaults — wiped on "New interview" / "Abort"
# ──────────────────────────────────────────────────────────────────────
_INTERVIEW_DEFAULTS: dict = {
    # FSM stage
    "stage": STAGE_SETUP,
    # Setup choices
    "role": None,
    "lang": "en",
    "lang_code": "en-IN",
    "candidate_name": "",
    # Interview Q&A loop
    "question_idx": 0,
    "follow_up_count": 0,
    "current_question": "",
    "current_question_audio": None,
    "questions_asked": [],
    "transcripts": [],
    "evaluation": None,
    "report_saved_path": None,
    # Greeting / closing audio
    "greeting_text": "",
    "greeting_audio": None,
    "greeting_played": False,
    "closing_text": "",
    "closing_audio": None,
    "closing_played": False,
    # Pre-interview onboarding
    "profile_intro_text": "",
    "profile_intro_audio": None,
    "profile_intro_played": False,
    "profile_q_idx": 0,
    "profile_current_audio": None,
    "profile_transcripts": [],
    "profile_json": None,
    "profile_resume": None,
    "profile_resume_pdf": None,
    "profile_saved_paths": None,
    # Structured enrichment (skills + work history) — built once during
    # profile_building and used by both profile_review and report views.
    "profile_enrichment": None,
    # Behavioral interview round (5 scenario questions, run after the
    # technical evaluation completes).
    "behavioral_intro_text": "",
    "behavioral_intro_audio": None,
    "behavioral_intro_played": False,
    "behavioral_q_idx": 0,
    "behavioral_current_audio": None,
    "behavioral_transcripts": [],   # list of {question, answer, response_seconds}
    "behavioral_eval": None,         # dict (BehavioralEvaluation.model_dump())
    # Voice-confirmation sub-FSM (for HIGH_RISK_FIELDS only). When the
    # candidate finishes recording an answer for a high-risk field, we
    # enter "confirming" — the bot reads back the LLM-extracted value
    # and listens for yes/no. Reset after the field is accepted.
    "profile_phase": "asking",          # "asking" | "confirming"
    "profile_pending_field": None,      # field key being confirmed
    "profile_pending_question": "",     # the original Q text
    "profile_pending_raw": "",          # verbatim STT transcript
    "profile_pending_value": "",        # LLM-extracted clean value
    "profile_confirm_audio": None,      # TTS bytes for the confirmation script
    "profile_confirm_retries": 0,       # how many times the candidate said "no"
}

# ──────────────────────────────────────────────────────────────────────
# SESSION-LEVEL defaults — preserved between consecutive interviews
# ──────────────────────────────────────────────────────────────────────
_SESSION_DEFAULTS: dict = {
    # Welcome / unlock overlay state — only fires on the first visit of
    # a session. Don't reset between interviews on the same tab.
    "welcome_unlocked": False,
    "setup_welcome_played": False,
    # TTS audio cache — keyed by (text, language). Repopulating it
    # between every interview would mean a redundant Sarvam round-trip
    # on every "New Interview" click. Keep it across interviews.
    "_tts_cache": {},
}


# Per-stage transient keys live with dynamic suffixes (e.g.
# ``profile_played_0``, ``processed_2_1``, ``profile_empty_3``,
# ``retry_5``). We don't list them in defaults — they're created on
# demand inside views. Listed here as PREFIXES so reset_interview()
# can sweep them out.
_STAGE_KEY_PREFIXES: tuple[str, ...] = (
    "profile_played_",
    "profile_processed_",
    "profile_empty_",
    "profile_confirm_played_",
    "profile_confirm_processed_",
    "played_",
    "processed_",
    "retry_",
    "skip_",
    # Behavioral round transient flags
    "behavioral_played_",
    "behavioral_processed_",
    "behavioral_empty_",
    "behavioral_start_ts_",
)


def init_state() -> None:
    """Populate session_state with default values if missing.

    Idempotent — safe to call on every Streamlit rerun. Combines
    session-level and interview-level defaults.

    Each default value is deep-copied before being assigned. Without
    this, mutable defaults like ``"transcripts": []`` would all share
    the SAME list object with the module-level dict — so
    ``session_state["transcripts"].append(...)`` during an interview
    would mutate ``_INTERVIEW_DEFAULTS["transcripts"]`` too, and the
    next interview would see the previous candidate's data.
    """
    for k, v in {**_SESSION_DEFAULTS, **_INTERVIEW_DEFAULTS}.items():
        if k not in st.session_state:
            st.session_state[k] = copy.deepcopy(v)


def reset_interview() -> None:
    """Wipe one interview's worth of state, keep session-level state.

    Use this for the "🔄 New interview" button on the report screen
    and the "❌ Abort" button on the profile / interview screens.

    Preserves: ``welcome_unlocked``, ``setup_welcome_played``,
               ``_tts_cache`` → no welcome replay, no redundant TTS.
    Clears:    every interview-specific key + every per-stage dedup
               flag (profile_played_*, processed_*, profile_empty_*, …)

    Each default is deep-copied — see ``init_state`` docstring for why.
    """
    # Wipe interview-level keys back to FRESH copies of the defaults.
    for k, v in _INTERVIEW_DEFAULTS.items():
        st.session_state[k] = copy.deepcopy(v)

    # Sweep transient per-stage dedup keys (they have dynamic suffixes
    # so we can't enumerate them in _INTERVIEW_DEFAULTS).
    stale_keys = [
        k for k in list(st.session_state.keys())
        if any(k.startswith(prefix) for prefix in _STAGE_KEY_PREFIXES)
    ]
    for k in stale_keys:
        del st.session_state[k]


def reset_all() -> None:
    """Wipe ALL session state — nuclear option.

    Equivalent to opening the app in a fresh browser tab. The welcome
    overlay will show again and the TTS cache will be cold.

    In normal user flows, prefer :func:`reset_interview`. ``reset_all``
    is kept as an escape hatch for debugging or genuine session resets.
    """
    for k in list(st.session_state.keys()):
        del st.session_state[k]
