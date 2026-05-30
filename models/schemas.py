"""
schemas.py — Pydantic v2 models for typed I/O between services.

These are the *contracts* between the core layer (services) and the
presentation layer (ui/streamlit). Any future UI (FastAPI, CLI, React)
consumes the same models.

Raw dicts are still acceptable inside streamlit's session state (which
is itself dict-like), but anything crossing a service boundary should be
typed.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# ──────────────────────────────────────────────────────────────────────
# Sarvam API response wrappers
# ──────────────────────────────────────────────────────────────────────
class SttResult(BaseModel):
    """Result of a speech-to-text call."""
    transcript: str = Field(description="Transcribed text. Empty string when the candidate stayed silent.")
    language_code: str = Field(description="BCP-47 locale used for the STT call (e.g. 'hi-IN').")


class TtsResult(BaseModel):
    """Result of a text-to-speech call."""
    audio_bytes: bytes = Field(description="WAV audio payload, ready for playback.")
    saved_path: Optional[str] = Field(
        default=None,
        description="Optional filesystem path the audio was written to.",
    )

    model_config = ConfigDict(arbitrary_types_allowed=True)


class LlmCompletion(BaseModel):
    """Successful chat-completion response."""
    content: str = Field(description="The model's reply text.")
    finish_reason: Optional[str] = Field(
        default=None,
        description="OpenAI-style finish reason ('stop', 'length', ...).",
    )


# ──────────────────────────────────────────────────────────────────────
# Onboarding profile
# ──────────────────────────────────────────────────────────────────────
class OnboardingAnswer(BaseModel):
    """One Q&A pair captured during the onboarding chat."""
    question: str = Field(description="The exact question text the bot spoke.")
    answer: Optional[str] = Field(
        default=None,
        description="Transcribed candidate answer. None if the candidate skipped.",
    )
    extracted_value: Optional[str] = Field(
        default=None,
        description=(
            "LLM-cleaned value for high-risk fields (name, mobile, email, age, "
            "location). Set only after voice confirmation. None for free-form "
            "fields. Resumes/PDFs should prefer this over `answer` when present."
        ),
    )


class CandidateProfile(BaseModel):
    """Structured profile built from the 9 onboarding answers."""
    name: str
    applied_role: str = Field(description="Role key (e.g. 'housekeeping').")
    language: str = Field(description="Short language code (en/hi/bn/te/pa/gu).")
    answers: dict[str, OnboardingAnswer] = Field(
        default_factory=dict,
        description="Field key (matches QUESTION_FIELD_ORDER) → onboarding answer.",
    )


# ──────────────────────────────────────────────────────────────────────
# Interview evaluation
# ──────────────────────────────────────────────────────────────────────
class Evaluation(BaseModel):
    """LLM-generated scorecard for an interview."""
    overall_score: Optional[float] = Field(default=None, ge=0, le=10)
    communication: Optional[float] = Field(default=None, ge=0, le=10)
    domain_knowledge: Optional[float] = Field(default=None, ge=0, le=10)
    safety_awareness: Optional[float] = Field(
        default=None, ge=0, le=10,
        description=(
            "0-10 rating of the candidate's awareness of workplace safety "
            "protocols (PPE, emergency response, hazard handling). "
            "Especially important for blue-collar trades."
        ),
    )
    confidence: Optional[float] = Field(default=None, ge=0, le=10)
    summary: str = ""
    hire_recommendation: Optional[bool] = None
    strengths: list[str] = Field(default_factory=list)
    improvements: list[str] = Field(default_factory=list)
    generation_failed: bool = Field(
        default=False,
        description="True when both LLM attempts failed; UI should show a Retry button.",
        alias="_generation_failed",
    )

    model_config = ConfigDict(populate_by_name=True)


# ──────────────────────────────────────────────────────────────────────
# Profile enrichment (structured skills + work history)
# ──────────────────────────────────────────────────────────────────────
class WorkHistoryEntry(BaseModel):
    """One job in the candidate's work history. All free-form short strings."""
    title: str = Field(description="Role title, e.g. 'Electrician Helper'.")
    employer: str = Field(description="Company / employer / site name + location if mentioned.")
    dates: str = Field(default="", description="Approximate dates, e.g. 'Jan 2021 - Present'. Empty if unknown.")
    duration: str = Field(default="", description="Human-readable duration, e.g. '3 yrs'. Empty if unknown.")


# ──────────────────────────────────────────────────────────────────────
# Behavioral / personality evaluation (Trust Profile)
# ──────────────────────────────────────────────────────────────────────
class BehavioralEvaluation(BaseModel):
    """LLM-generated scorecard for the behavioral interview round.

    Five personality traits scored 0-10, plus per-question rationale
    so the dashboard can render an explainable "why this score" drilldown,
    plus deterministic trust signals computed from audio timing.
    """
    # ── 5 trait scores ──────────────────────────────────────────
    honesty: Optional[float] = Field(default=None, ge=0, le=10,
        description="Truthfulness, willingness to admit gaps, concrete details.")
    reliability: Optional[float] = Field(default=None, ge=0, le=10,
        description="Will they show up, will they stay, stable past tenure.")
    stress_tolerance: Optional[float] = Field(default=None, ge=0, le=10,
        description="Action orientation under pressure, accountability, learning mindset.")
    customer_orientation: Optional[float] = Field(default=None, ge=0, le=10,
        description="Listens first, de-escalates, empathy with users.")
    earning_attitude: Optional[float] = Field(default=None, ge=0, le=10,
        description="Money vs growth balance, long-term thinking, retention risk.")

    # ── Narrative ──────────────────────────────────────────────
    overall_summary: str = Field(default="",
        description="2-3 sentence English summary of the candidate's behavioral profile.")
    per_trait_reasoning: dict[str, str] = Field(default_factory=dict,
        description="Trait key → 1-line explanation of the score (for drilldown).")

    # ── Deterministic trust signals (audio-timing derived) ─────
    avg_response_seconds: Optional[float] = Field(default=None,
        description="Average time-to-first-word across the 5 behavioral questions.")
    answer_specificity: Optional[float] = Field(default=None, ge=0, le=10,
        description="LLM rating of how concrete/specific the candidate's answers were (0-10).")
    cross_question_consistency: Optional[str] = Field(default=None,
        description="One of 'high', 'medium', 'low' — did their answers align with each other?")

    generation_failed: bool = Field(default=False,
        description="True when the LLM call failed and the dashboard should hide this section.")


class ProfileEnrichment(BaseModel):
    """Structured extraction of skills + work history + English summary
    versions of free-form profile fields from the profile transcript.

    Built once during the profile-building stage by ProfileEnrichService.
    Used by the recruiter dashboard to render skill chips, work cards,
    and clean English personal-details rows (instead of raw Hindi/Indic
    transcripts).
    """
    skills: list[str] = Field(
        default_factory=list,
        description="Short skill / tool names. Empty list if nothing extractable.",
    )
    work_history: list[WorkHistoryEntry] = Field(
        default_factory=list,
        description="Past jobs in reverse-chronological order.",
    )

    # English summary versions of free-form fields. Used by the
    # recruiter dashboard in place of the raw STT transcript so the
    # dashboard reads cleanly in English even when the candidate
    # spoke a different language.
    education_en: str = Field(
        default="",
        description="Short English label, e.g. '12th Pass · Lucknow Inter College'.",
    )
    salary_en: str = Field(
        default="",
        description="Short English label, e.g. '₹15,000 / month expected'.",
    )
    availability_en: str = Field(
        default="",
        description="Short English label, e.g. 'Available immediately · Full time'.",
    )
    marital_status_en: str = Field(
        default="",
        description="Short English label: 'Married' / 'Single' / 'Prefer not to say'.",
    )
    dependents_en: str = Field(
        default="",
        description="Short English label, e.g. '2 children · supports parents'.",
    )


# ──────────────────────────────────────────────────────────────────────
# Follow-up decision
# ──────────────────────────────────────────────────────────────────────
class TurnDecision(BaseModel):
    """Decision returned by the next-turn LLM call."""
    action: str = Field(description="Either 'follow_up' or 'next'.")
    question: Optional[str] = Field(
        default=None,
        description="Follow-up question text. Present only when action == 'follow_up'.",
    )


# ──────────────────────────────────────────────────────────────────────
# Pre-demo health check
# ──────────────────────────────────────────────────────────────────────
class HealthCheckResult(BaseModel):
    """Result of probing one Sarvam endpoint."""
    name: str
    ok: bool
    latency_s: float
    detail: str


class HealthCheckReport(BaseModel):
    """Aggregate result of running all health-check probes."""
    results: list[HealthCheckResult]
    all_ok: bool
