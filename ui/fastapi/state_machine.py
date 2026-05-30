"""
state_machine.py — Server-side FSM that drives a candidate interview.

This is the FastAPI equivalent of the per-view logic spread across
``ui/streamlit/views/*``. It's intentionally **headless** — it owns
state transitions, calls services, and emits the next question. It
knows nothing about HTTP or SQLAlchemy.

State is held as a plain ``dict`` so it serialises cleanly to JSON
(see :mod:`ui.fastapi.db`). Routes load the dict, hand it to a
:class:`StateMachine` instance, call a transition method, persist
the updated dict.

FSM stages (simplified for the mobile MVP):

    profile   →  interview  →  behavioral  →  awaiting_finalize
                                                    ↓
                                                completed

The Streamlit-specific intro / outro / review splash stages are
collapsed because they're pure UI screens and have no server work
to do — the mobile client renders those on its own.

Per-question voice confirmation for HIGH_RISK_FIELDS (name/mobile/
age/location) is **deferred to Phase 2**. The MVP captures raw
transcript only; recruiters can correct values from the dashboard.
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from constants.app_constants import (
    BEHAVIORAL_QUESTION_COUNT,
    HIGH_RISK_FIELDS,
    MAX_FOLLOW_UPS_PER_QUESTION,
    NO_KEYWORDS,
    PROFILE_CONFIRM_MAX_RETRIES,
    QUESTION_FIELD_ORDER,
    YES_KEYWORDS,
)
from data.behavioral_questions import (
    BEHAVIORAL_INTRO,
    get_behavioral_questions_for_role,
)
from data.interview_questions import (
    CLOSING_MESSAGE,
    LANGUAGES,
    OPENING_MESSAGE,
    QUESTION_BANK,
)
from data.profile_questions import (
    CONFIRMATION_PROMPTS,
    PROFILE_INTRO,
    PROFILE_QUESTIONS,
)


logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────
# Stage names — single source of truth for the backend FSM
# ──────────────────────────────────────────────────────────────────────
STAGE_PROFILE = "profile"
STAGE_PROFILE_REVIEW = "profile_review"           # resume preview + approval
STAGE_INTERVIEW_GREETING = "interview_greeting"   # role intro audio
STAGE_INTERVIEW = "interview"
STAGE_INTERVIEW_CLOSING = "interview_closing"     # closing thanks audio
STAGE_BEHAVIORAL_INTRO = "behavioral_intro"       # explicit "Begin personality round" gate
STAGE_BEHAVIORAL = "behavioral"
STAGE_AWAITING_FINALIZE = "awaiting_finalize"
STAGE_EVALUATING = "evaluating"                   # transient — during /finalize
STAGE_COMPLETED = "completed"

ALL_STAGES = (
    STAGE_PROFILE,
    STAGE_PROFILE_REVIEW,
    STAGE_INTERVIEW_GREETING,
    STAGE_INTERVIEW,
    STAGE_INTERVIEW_CLOSING,
    STAGE_BEHAVIORAL_INTRO,
    STAGE_BEHAVIORAL,
    STAGE_AWAITING_FINALIZE,
    STAGE_EVALUATING,
    STAGE_COMPLETED,
)


# ──────────────────────────────────────────────────────────────────────
# Result shapes returned to callers (routes)
# ──────────────────────────────────────────────────────────────────────
@dataclass
class TurnResult:
    """Outcome of a single advance() call."""
    stage: str
    progress: float                        # 0.0 .. 1.0
    transcript: str                        # what the candidate just said
    next_question_text: Optional[str]      # None when stage moves to AWAITING_FINALIZE
    next_question_audio_filename: Optional[str]
    is_terminal: bool                      # True when we hit AWAITING_FINALIZE


# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────
def _lang_code_for(short: str) -> str:
    """Map "hi" → "hi-IN" using the LANGUAGES dict from data."""
    for _, (code, locale) in LANGUAGES.items():
        if code == short:
            return locale
    return "en-IN"


def _profile_question_text(idx: int, language: str, role: str = "") -> str:
    """Get the localised profile question text for the given index.

    Some prompts contain a ``{role}`` placeholder (e.g. "How many years
    of experience do you have in {role}-related work?"). Substitute it
    with the human-readable role title before returning.
    """
    if idx < 0 or idx >= len(PROFILE_QUESTIONS):
        raise IndexError(f"profile q idx {idx} out of range")
    prompts = PROFILE_QUESTIONS[idx]["prompts"]
    text = prompts.get(language) or prompts["en"]
    if "{role}" in text:
        role_title = (
            QUESTION_BANK.get(role, {}).get("title", role)
            .split("|")[0]
            .strip()
            .replace("_", " ")
        ) or "this role"
        text = text.replace("{role}", role_title)
    return text


def _interview_question_text(role: str, idx: int, language: str) -> str:
    """Get the localised technical interview question text."""
    bank = QUESTION_BANK.get(role, {}).get("questions", [])
    if idx < 0 or idx >= len(bank):
        raise IndexError(f"interview q idx {idx} out of range for role {role!r}")
    q = bank[idx]
    return q.get(language) or q["en"]


def _behavioral_question_text(role: str, idx: int, language: str) -> str:
    """Get the localised behavioral scenario question text."""
    qs = get_behavioral_questions_for_role(role)
    if idx < 0 or idx >= len(qs):
        raise IndexError(f"behavioral q idx {idx} out of range")
    prompts = qs[idx]["prompts"]
    return prompts.get(language) or prompts["en"]


# ──────────────────────────────────────────────────────────────────────
# Voice-confirmation helpers (mirrors ui/streamlit/views/profile_view.py)
# ──────────────────────────────────────────────────────────────────────
def _classify_yes_no(transcript: str, language: str) -> Optional[str]:
    """Return 'yes', 'no', or None (ambiguous) for a confirmation utterance."""
    text = (transcript or "").lower().strip()
    if not text:
        return None
    for kw in YES_KEYWORDS.get(language, YES_KEYWORDS["en"]):
        if kw.lower() in text:
            return "yes"
    for kw in NO_KEYWORDS.get(language, NO_KEYWORDS["en"]):
        if kw.lower() in text:
            return "no"
    return None


def _format_value_for_speech(field: str, value: str) -> str:
    """Format an extracted value for TTS read-back.

    mobile  '9876543210' → '9, 8, 7, 6, 5, 4, 3, 2, 1, 0'
    age / name / location: returned as-is.
    """
    if field == "mobile":
        digits = [c for c in value if c.isdigit()]
        return ", ".join(digits) if digits else value
    return value


def _build_confirmation_script(field: str, value: str, language: str) -> str:
    """Render the bot's read-back sentence."""
    template = (
        CONFIRMATION_PROMPTS.get(field, {}).get(language)
        or CONFIRMATION_PROMPTS.get(field, {}).get("en")
        or "You said {value}. Is that correct? Please say yes or no."
    )
    return template.format(value=_format_value_for_speech(field, value))


def _opening_text(role: str, language: str, candidate_name: str) -> str:
    """Format the technical-interview opening message."""
    template = OPENING_MESSAGE.get(language) or OPENING_MESSAGE["en"]
    role_title = QUESTION_BANK.get(role, {}).get("title", role).split("|")[0].strip()
    name_part = f"{candidate_name}! " if candidate_name else ""
    return template.format(role=role_title, name=name_part)


def _closing_text(language: str) -> str:
    return CLOSING_MESSAGE.get(language) or CLOSING_MESSAGE["en"]


# ──────────────────────────────────────────────────────────────────────
# Initial state factory
# ──────────────────────────────────────────────────────────────────────
def initial_state(
    *,
    role: str,
    language: str,
    candidate_name: str,
) -> dict[str, Any]:
    """Build the initial session state dict — stage = profile, Q1 ready.

    The first profile question is preceded by the PROFILE_INTRO greeting
    so the candidate hears a welcoming voice before getting questioned.
    """
    if role not in QUESTION_BANK:
        raise ValueError(f"unknown role {role!r}; allowed: {list(QUESTION_BANK)}")
    if language not in {code for code, _ in LANGUAGES.values()}:
        raise ValueError(f"unknown language {language!r}")

    intro = (
        PROFILE_INTRO.get(language) or PROFILE_INTRO["en"]
    ).format(name=candidate_name or "")
    first_q = _profile_question_text(0, language, role)
    first_with_intro = f"{intro}\n\n{first_q}"

    return {
        # Identity / setup
        "role":           role,
        "language":       language,
        "lang_code":      _lang_code_for(language),
        "candidate_name": candidate_name,
        # FSM
        "stage": STAGE_PROFILE,
        "started_at": time.time(),
        # Profile loop
        "profile_q_idx": 0,
        "profile_transcripts": [],
        # Voice-confirmation sub-FSM for HIGH_RISK_FIELDS
        # (name / mobile / age / location). Mirrors the Streamlit flow:
        # extract → TTS read-back → STT yes/no → accept or retry.
        "profile_phase": "asking",          # "asking" | "confirming"
        "profile_pending_field": None,
        "profile_pending_question": "",
        "profile_pending_raw": "",
        "profile_pending_value": "",
        "profile_confirm_retries": 0,
        # Technical interview loop
        "question_idx": 0,
        "follow_up_count": 0,
        "questions_asked": [],
        "transcripts": [],
        "current_followup_question": "",
        # Behavioral loop
        "behavioral_q_idx": 0,
        "behavioral_transcripts": [],
        "behavioral_q_delivered_at": None,   # set when TTS sent to client
        # Current question (rendered to client)
        "current_question_text": first_with_intro,
        "current_question_audio_filename": None,   # generated by /audio route on demand
        # Final outputs (populated by finalize())
        "profile_json":     None,
        "enrichment":       None,
        "resume_pdf_path":  None,
        "evaluation":       None,
        "behavioral_eval":  None,
        "report_json_path": None,
        "report_pdf_path":  None,
        "finalized_at":     None,
    }


# ──────────────────────────────────────────────────────────────────────
# StateMachine — operates on a session-state dict
# ──────────────────────────────────────────────────────────────────────
class StateMachine:
    """Drives a single interview session forward.

    Construction is cheap — pass in the session dict and the bundle of
    services it needs. Mutates the dict in place; route handlers persist
    the dict back to SQLite after each call.
    """

    def __init__(
        self,
        state: dict[str, Any],
        *,
        stt_service,
        decide_service,
        profile_extract_service=None,
        profile_service=None,
        resume_service=None,
        settings=None,
    ) -> None:
        self.state = state
        self._stt = stt_service
        self._decide = decide_service
        self._extract = profile_extract_service
        self._profile = profile_service
        self._resume = resume_service
        self._settings = settings

    # ----------------------------------------------------------------
    # Properties
    # ----------------------------------------------------------------
    @property
    def stage(self) -> str:
        return self.state["stage"]

    @property
    def role(self) -> str:
        return self.state["role"]

    @property
    def language(self) -> str:
        return self.state["language"]

    @property
    def lang_code(self) -> str:
        return self.state["lang_code"]

    # ----------------------------------------------------------------
    # Progress reporting
    # ----------------------------------------------------------------
    def progress(self) -> float:
        """Rough completion percentage across the whole interview."""
        stage = self.stage
        if stage == STAGE_PROFILE:
            return 0.05 + 0.25 * (self.state["profile_q_idx"] / max(1, len(PROFILE_QUESTIONS)))
        if stage == STAGE_PROFILE_REVIEW:
            return 0.33
        if stage in (STAGE_INTERVIEW_GREETING, STAGE_INTERVIEW, STAGE_INTERVIEW_CLOSING):
            tech_total = len(QUESTION_BANK.get(self.role, {}).get("questions", [])) or 1
            return 0.35 + 0.30 * (self.state["question_idx"] / tech_total)
        if stage == STAGE_BEHAVIORAL:
            return 0.65 + 0.30 * (
                self.state["behavioral_q_idx"] / BEHAVIORAL_QUESTION_COUNT
            )
        if stage == STAGE_AWAITING_FINALIZE:
            return 0.95
        if stage in (STAGE_EVALUATING, STAGE_COMPLETED):
            return 1.0
        return 0.0

    # ----------------------------------------------------------------
    # Generate the next question's TTS (caller persists the filename)
    # ----------------------------------------------------------------
    def current_question(self) -> Optional[str]:
        """The candidate-facing text for the current question, if any."""
        if self.stage in (STAGE_AWAITING_FINALIZE, STAGE_EVALUATING,
                          STAGE_COMPLETED):
            return None
        return self.state.get("current_question_text") or None

    # ----------------------------------------------------------------
    # Audio submission — the central transition
    # ----------------------------------------------------------------
    def submit_answer(self, audio_path: Path) -> TurnResult:
        """Transcribe the uploaded audio and advance the FSM by one turn.

        Returns the new stage, the candidate's transcript, and the
        next-question text (if any). The route handler is responsible
        for generating the TTS audio for the next question.
        """
        # 1) STT — never let an STT failure crash the whole transition.
        try:
            stt = self._stt.speech_to_text(
                str(audio_path), language_code=self.lang_code,
            )
            transcript = (stt.transcript or "").strip()
        except Exception as e:  # noqa: BLE001
            logger.warning("STT failed: %s — treating as empty answer", e)
            transcript = ""

        # 2) Route by current stage
        if self.stage == STAGE_PROFILE:
            return self._advance_profile(transcript)
        if self.stage == STAGE_INTERVIEW:
            return self._advance_interview(transcript)
        if self.stage == STAGE_BEHAVIORAL:
            return self._advance_behavioral(transcript)
        raise RuntimeError(
            f"submit_answer not valid in stage {self.stage!r}"
        )

    # ----------------------------------------------------------------
    # Stage-specific advance helpers
    # ----------------------------------------------------------------
    def _advance_profile(self, transcript: str) -> TurnResult:
        """Drive the profile loop. Two phases:

        * ``asking``      — candidate has just answered a profile Q.
                            For HIGH_RISK_FIELDS we extract the cleaned
                            value, switch to ``confirming``, and emit a
                            read-back prompt. For other fields we just
                            store and advance.
        * ``confirming``  — candidate has just spoken yes/no to a
                            read-back. Yes → accept + advance. No →
                            re-ask up to ``PROFILE_CONFIRM_MAX_RETRIES``
                            times, then auto-accept.
        """
        s = self.state
        if s.get("profile_phase") == "confirming":
            return self._advance_profile_confirming(transcript)
        return self._advance_profile_asking(transcript)

    def _advance_profile_asking(self, transcript: str) -> TurnResult:
        s = self.state
        idx = s["profile_q_idx"]
        q_text = _profile_question_text(idx, self.language, self.role)
        field = (
            QUESTION_FIELD_ORDER[idx]
            if idx < len(QUESTION_FIELD_ORDER) else None
        )

        # HIGH-RISK field with a substantive answer → enter confirmation
        if (
            field in HIGH_RISK_FIELDS
            and self._extract is not None
            and transcript.strip()
        ):
            try:
                extracted = self._extract.extract(
                    field=field, raw_answer=transcript, language=self.language,
                ).strip()
            except Exception as e:  # noqa: BLE001
                logger.warning("ProfileExtract failed: %s — using raw transcript", e)
                extracted = transcript.strip()

            if extracted:
                s["profile_phase"] = "confirming"
                s["profile_pending_field"] = field
                s["profile_pending_question"] = q_text
                s["profile_pending_raw"] = transcript
                s["profile_pending_value"] = extracted
                # Note: profile_confirm_retries is intentionally NOT reset
                # here — it tracks "no" votes on the current field across
                # multiple re-ask cycles. Only resets when we advance to
                # the next field (see _advance_profile_confirming).
                readback = _build_confirmation_script(field, extracted, self.language)
                s["current_question_text"] = readback
                s["current_question_audio_filename"] = None
                return TurnResult(
                    stage=STAGE_PROFILE,
                    progress=self.progress(),
                    transcript=transcript,
                    next_question_text=readback,
                    next_question_audio_filename=None,
                    is_terminal=False,
                )

        # Non-confirmed path: store + advance (free-form fields, empty
        # answers, or extraction-disabled deployments).
        s["profile_transcripts"].append({
            "question": q_text,
            "answer": transcript,
            "extracted_value": None,
            "field": field,
        })
        s["profile_q_idx"] = idx + 1
        return self._after_profile_step(transcript)

    def _advance_profile_confirming(self, transcript: str) -> TurnResult:
        s = self.state
        verdict = _classify_yes_no(transcript, self.language)
        field = s["profile_pending_field"]
        q_text = s["profile_pending_question"]
        raw = s["profile_pending_raw"]
        value = s["profile_pending_value"]

        # NO (with retries remaining) → re-ask the original question
        if verdict == "no" and s["profile_confirm_retries"] < PROFILE_CONFIRM_MAX_RETRIES:
            s["profile_confirm_retries"] += 1
            s["profile_phase"] = "asking"
            s["profile_pending_field"] = None
            s["profile_pending_question"] = ""
            s["profile_pending_raw"] = ""
            s["profile_pending_value"] = ""
            s["current_question_text"] = q_text
            s["current_question_audio_filename"] = None
            return TurnResult(
                stage=STAGE_PROFILE,
                progress=self.progress(),
                transcript=transcript,
                next_question_text=q_text,
                next_question_audio_filename=None,
                is_terminal=False,
            )

        # Yes, ambiguous, OR retries exhausted → accept whatever we have
        s["profile_transcripts"].append({
            "question": q_text,
            "answer": raw,
            "extracted_value": value,
            "field": field,
        })
        idx = s["profile_q_idx"]
        s["profile_q_idx"] = idx + 1
        # Reset confirmation sub-FSM
        s["profile_phase"] = "asking"
        s["profile_pending_field"] = None
        s["profile_pending_question"] = ""
        s["profile_pending_raw"] = ""
        s["profile_pending_value"] = ""
        s["profile_confirm_retries"] = 0
        return self._after_profile_step(transcript)

    def _after_profile_step(self, transcript: str) -> TurnResult:
        """Shared transition after either an asked or confirmed answer."""
        s = self.state
        if s["profile_q_idx"] >= len(PROFILE_QUESTIONS):
            return self._enter_profile_review(transcript)
        next_text = _profile_question_text(s["profile_q_idx"], self.language, self.role)
        s["current_question_text"] = next_text
        s["current_question_audio_filename"] = None
        return TurnResult(
            stage=STAGE_PROFILE,
            progress=self.progress(),
            transcript=transcript,
            next_question_text=next_text,
            next_question_audio_filename=None,
            is_terminal=False,
        )

    def _enter_profile_review(self, last_transcript: str) -> TurnResult:
        """End of profile loop. Build the candidate profile + ATS resume
        PDF now (instead of at finalize) so the candidate can review it
        on screen before starting the technical interview.
        """
        s = self.state
        # Build profile from stored Q/A pairs
        qa_tuples = [
            (t["question"], t.get("answer") or "", t.get("extracted_value"))
            for t in s.get("profile_transcripts", [])
        ]
        if self._profile is not None:
            try:
                profile = self._profile.build_profile(
                    candidate_name=s["candidate_name"],
                    role=self.role,
                    language=self.language,
                    qa_pairs=qa_tuples,
                )
                s["profile_json"] = profile.model_dump()

                if self._resume is not None and self._settings is not None:
                    resume_text = self._resume.build_resume_text(profile)
                    pdf_bytes = self._resume.build_resume_pdf(
                        resume_text, candidate_name=profile.name,
                    )
                    safe_name = profile.name.replace(" ", "_")
                    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                    resume_path = (
                        self._settings.output_dir
                        / f"resume_{safe_name}_{ts}.pdf"
                    )
                    resume_path.write_bytes(pdf_bytes)
                    s["resume_pdf_path"] = str(resume_path)
                    s["resume_text"] = resume_text
            except Exception as e:  # noqa: BLE001
                logger.warning("Resume generation failed: %s", e)
                s["resume_text"] = (
                    "Resume could not be generated automatically. "
                    "Please continue — your answers are saved."
                )

        s["stage"] = STAGE_PROFILE_REVIEW
        s["current_question_text"] = None
        s["current_question_audio_filename"] = None
        return TurnResult(
            stage=STAGE_PROFILE_REVIEW,
            progress=self.progress(),
            transcript=last_transcript,
            next_question_text=None,
            next_question_audio_filename=None,
            is_terminal=False,
        )

    def advance(self) -> TurnResult:
        """Called by POST /v1/sessions/{id}/advance from any "gate"
        stage. Dispatches based on the current stage to the appropriate
        next-state handler.

        Currently handles two gates:
          PROFILE_REVIEW    → INTERVIEW_GREETING (start technical)
          BEHAVIORAL_INTRO  → BEHAVIORAL (start personality round)
        """
        if self.stage == STAGE_PROFILE_REVIEW:
            return self._enter_interview_greeting(last_transcript="")
        if self.stage == STAGE_BEHAVIORAL_INTRO:
            return self._begin_behavioral()
        raise RuntimeError(
            f"/advance is not valid from stage {self.stage!r}"
        )

    # Backwards-compat alias for the older name used by the resume route
    def advance_past_review(self) -> TurnResult:
        return self.advance()

    def _enter_interview_greeting(self, last_transcript: str) -> TurnResult:
        """Transition profile → interview. The very first technical
        question is preceded by the OPENING_MESSAGE so the TTS speaks
        a branded greeting before diving into questions."""
        s = self.state
        greeting = _opening_text(self.role, self.language, s["candidate_name"])
        first_q_raw = _interview_question_text(self.role, 0, self.language)
        # Prepend the greeting to the first technical question — same
        # TTS round-trip plays both, which matches the web app's flow
        # where OPENING_MESSAGE auto-plays on the greeting screen.
        first_q = f"{greeting}\n\n{first_q_raw}"
        s["stage"] = STAGE_INTERVIEW
        s["questions_asked"] = [first_q_raw]   # store the question only, not the greeting
        s["current_question_text"] = first_q   # play greeting + question
        s["current_question_audio_filename"] = None
        s["interview_greeting_text"] = greeting
        return TurnResult(
            stage=STAGE_INTERVIEW,
            progress=self.progress(),
            transcript=last_transcript,
            next_question_text=first_q,
            next_question_audio_filename=None,
            is_terminal=False,
        )

    def _advance_interview(self, transcript: str) -> TurnResult:
        s = self.state
        idx = s["question_idx"]
        bank = QUESTION_BANK[self.role]["questions"]

        current_q_text = (
            s.get("current_followup_question")
            or _interview_question_text(self.role, idx, self.language)
        )
        s["transcripts"].append(transcript)

        # Ask the follow-up decision service — it caps itself at
        # MAX_FOLLOW_UPS_PER_QUESTION so we can't loop forever.
        decision = self._decide.decide(
            role=self.role,
            question=current_q_text,
            answer=transcript,
            follow_up_count=s["follow_up_count"],
            language=self.language,
            max_follow_ups=MAX_FOLLOW_UPS_PER_QUESTION,
        )

        if decision.action == "follow_up" and decision.question:
            s["follow_up_count"] += 1
            s["current_followup_question"] = decision.question
            s["questions_asked"].append(decision.question)
            s["current_question_text"] = decision.question
            s["current_question_audio_filename"] = None
            return TurnResult(
                stage=STAGE_INTERVIEW,
                progress=self.progress(),
                transcript=transcript,
                next_question_text=decision.question,
                next_question_audio_filename=None,
                is_terminal=False,
            )

        # No follow-up — move to next base question
        s["follow_up_count"] = 0
        s["current_followup_question"] = ""
        s["question_idx"] = idx + 1

        if s["question_idx"] >= len(bank):
            return self._enter_behavioral(transcript)

        next_q = _interview_question_text(self.role, s["question_idx"], self.language)
        s["questions_asked"].append(next_q)
        s["current_question_text"] = next_q
        s["current_question_audio_filename"] = None
        return TurnResult(
            stage=STAGE_INTERVIEW,
            progress=self.progress(),
            transcript=transcript,
            next_question_text=next_q,
            next_question_audio_filename=None,
            is_terminal=False,
        )

    def _enter_behavioral(self, last_transcript: str) -> TurnResult:
        """Transition interview → BEHAVIORAL_INTRO gate. The candidate
        sees an explicit "Begin personality round" button (mirrors the
        web app's behavioral_intro_view). Tapping it calls /advance,
        which then enters STAGE_BEHAVIORAL with the first question.
        """
        s = self.state
        s["stage"] = STAGE_BEHAVIORAL_INTRO
        s["interview_closing_text"] = _closing_text(self.language)
        s["current_question_text"] = None
        s["current_question_audio_filename"] = None
        return TurnResult(
            stage=STAGE_BEHAVIORAL_INTRO,
            progress=self.progress(),
            transcript=last_transcript,
            next_question_text=None,
            next_question_audio_filename=None,
            is_terminal=True,
        )

    def _begin_behavioral(self) -> TurnResult:
        """Called by /advance from STAGE_BEHAVIORAL_INTRO. Sets up the
        first behavioral question with the intro greeting prepended for
        a single TTS round-trip."""
        s = self.state
        intro = BEHAVIORAL_INTRO.get(self.language) or BEHAVIORAL_INTRO["en"]
        first_q_raw = _behavioral_question_text(self.role, 0, self.language)
        first_q = f"{intro}\n\n{first_q_raw}"
        s["stage"] = STAGE_BEHAVIORAL
        s["current_question_text"] = first_q
        s["current_question_audio_filename"] = None
        s["behavioral_q_delivered_at"] = time.time()
        return TurnResult(
            stage=STAGE_BEHAVIORAL,
            progress=self.progress(),
            transcript="",
            next_question_text=first_q,
            next_question_audio_filename=None,
            is_terminal=False,
        )

    def _advance_behavioral(self, transcript: str) -> TurnResult:
        s = self.state
        idx = s["behavioral_q_idx"]
        q_text = _behavioral_question_text(self.role, idx, self.language)
        delivered = s.get("behavioral_q_delivered_at")
        response_seconds = (
            time.time() - delivered if delivered else None
        )
        s["behavioral_transcripts"].append({
            "question": q_text,
            "answer": transcript,
            "response_seconds": response_seconds,
        })
        s["behavioral_q_idx"] = idx + 1

        if s["behavioral_q_idx"] >= BEHAVIORAL_QUESTION_COUNT:
            # Done with the last Q — wait for /finalize.
            s["stage"] = STAGE_AWAITING_FINALIZE
            s["current_question_text"] = None
            s["current_question_audio_filename"] = None
            return TurnResult(
                stage=STAGE_AWAITING_FINALIZE,
                progress=self.progress(),
                transcript=transcript,
                next_question_text=None,
                next_question_audio_filename=None,
                is_terminal=True,
            )

        next_q = _behavioral_question_text(self.role, s["behavioral_q_idx"], self.language)
        s["current_question_text"] = next_q
        s["current_question_audio_filename"] = None
        s["behavioral_q_delivered_at"] = time.time()
        return TurnResult(
            stage=STAGE_BEHAVIORAL,
            progress=self.progress(),
            transcript=transcript,
            next_question_text=next_q,
            next_question_audio_filename=None,
            is_terminal=False,
        )

    # ----------------------------------------------------------------
    # TTS pre-generation (called by /audio route the first time the
    # client requests audio for the current question)
    # ----------------------------------------------------------------
    def assign_audio_filename(self, filename: str) -> None:
        """Record the TTS WAV filename for the current question."""
        self.state["current_question_audio_filename"] = filename
