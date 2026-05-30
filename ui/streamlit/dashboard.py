"""
dashboard.py — Recruiter-facing evaluation scorecard.

Simple 4-section layout focused on what a recruiter actually needs:

  1. Hero: avatar + name + role + interview language + score + hire badge
  2. About: the LLM-generated HR summary
  3. Strengths + Areas to Improve (two columns)
  4. Score breakdown: 4 horizontal score bars

Profile-level fields (mobile, location, age, education, salary, …)
are intentionally NOT shown here. They live in the resume PDF + the
profile JSON download. This keeps the recruiter dashboard fully in
English regardless of the candidate's interview language — there's
simply nothing on it that can leak a non-English transcript.

`build_dashboard_html` is used by both the Streamlit view and the
WeasyPrint PDF service so the on-screen layout and the downloadable
PDF always match.
"""

from __future__ import annotations

import html as _html
import math
from typing import Optional

import streamlit as st

from constants.app_constants import BEHAVIORAL_TRAITS
from data.interview_questions import QUESTION_BANK, LANGUAGE_NAMES
from models.schemas import (
    BehavioralEvaluation,
    CandidateProfile,
    Evaluation,
    ProfileEnrichment,
)


# ──────────────────────────────────────────────────────────────────────
# Tiny helpers
# ──────────────────────────────────────────────────────────────────────
def _e(s: str) -> str:
    return _html.escape(str(s or ""))


def _initials(name: str) -> str:
    parts = [p for p in (name or "").strip().split() if p]
    if not parts:
        return "?"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()


def _score_row(label: str, value: Optional[float]) -> str:
    """One horizontal score bar row: label · track · number."""
    if value is None:
        v = 0.0
        display = "—"
    else:
        v = max(0.0, min(10.0, float(value)))
        display = f"{v:g}"
    pct = int(round(v * 10))
    return (
        '<div class="scorecard-row">'
        f'<span class="scorecard-row-label">{_e(label)}</span>'
        '<span class="scorecard-row-track">'
        f'<span class="scorecard-row-bar" style="width:{pct}%;"></span>'
        '</span>'
        f'<span class="scorecard-row-num">{display}</span>'
        '</div>'
    )


def _radar_chart_svg(scores: list[tuple[str, float]]) -> str:
    """Render an SVG radar chart for the behavioral traits.

    Args:
        scores: List of (label, value 0-10) pairs. Typically 5 entries
                matching the 5 BEHAVIORAL_TRAITS.

    Returns:
        Self-contained SVG markup. Works in both Streamlit (via st.markdown)
        AND WeasyPrint PDF output — no Plotly dependency.
    """
    n = len(scores)
    if n < 3:
        return ""  # too few points to draw a polygon

    # Geometry
    cx, cy = 175, 165          # chart centre
    radius = 110               # max radius (= score 10)
    label_radius = radius + 26 # where to place axis labels
    # Axes start at the top (-90°) and go clockwise
    angle_offset = -math.pi / 2

    def polar(score: float, axis_idx: int) -> tuple[float, float]:
        r = max(0.0, min(10.0, score)) / 10.0 * radius
        a = angle_offset + (2 * math.pi * axis_idx / n)
        return cx + r * math.cos(a), cy + r * math.sin(a)

    # Background grid: 4 concentric polygons at 25, 50, 75, 100%
    grid_polys: list[str] = []
    for fraction in (0.25, 0.5, 0.75, 1.0):
        pts = []
        for i in range(n):
            a = angle_offset + (2 * math.pi * i / n)
            pts.append(f"{cx + fraction * radius * math.cos(a):.1f},"
                       f"{cy + fraction * radius * math.sin(a):.1f}")
        grid_polys.append(
            f'<polygon points="{ " ".join(pts) }" '
            f'fill="rgba(99,102,241,{0.04 if fraction < 1 else 0})" '
            f'stroke="#e4e4e7" stroke-width="1"/>'
        )

    # Axis lines (centre → each apex)
    axis_lines: list[str] = []
    for i in range(n):
        x, y = polar(10.0, i)
        axis_lines.append(
            f'<line x1="{cx}" y1="{cy}" x2="{x:.1f}" y2="{y:.1f}" '
            f'stroke="#e4e4e7" stroke-width="1"/>'
        )

    # Data polygon
    data_pts = [polar(score, i) for i, (_, score) in enumerate(scores)]
    data_pts_str = " ".join(f"{x:.1f},{y:.1f}" for x, y in data_pts)
    data_polygon = (
        f'<polygon points="{data_pts_str}" '
        f'fill="rgba(99,102,241,0.30)" stroke="#6366f1" stroke-width="2"/>'
    )
    # Data points (dots)
    data_dots = "".join(
        f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.5" fill="#6366f1"/>'
        for x, y in data_pts
    )

    # Axis labels — place outside the apex, anchor based on quadrant
    labels: list[str] = []
    for i, (label, score) in enumerate(scores):
        a = angle_offset + (2 * math.pi * i / n)
        lx = cx + label_radius * math.cos(a)
        ly = cy + label_radius * math.sin(a)
        # Choose text-anchor by horizontal position
        if abs(math.cos(a)) < 0.2:
            anchor = "middle"
        elif math.cos(a) > 0:
            anchor = "start"
        else:
            anchor = "end"
        labels.append(
            f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="{anchor}" '
            f'font-size="10" font-weight="600" fill="#3F3F46" '
            f'font-family="Inter, sans-serif">{_e(label)}</text>'
        )
        labels.append(
            f'<text x="{lx:.1f}" y="{ly + 12:.1f}" text-anchor="{anchor}" '
            f'font-size="11" font-weight="700" fill="#6366f1" '
            f'font-family="Inter, sans-serif">{score:g}</text>'
        )

    return (
        '<svg viewBox="0 0 350 320" width="100%" '
        'preserveAspectRatio="xMidYMid meet" '
        'style="max-width:340px; display:block; margin:0 auto;">'
        + "".join(grid_polys)
        + "".join(axis_lines)
        + data_polygon
        + data_dots
        + "".join(labels)
        + '</svg>'
    )


def _bullet_list(items: list[str], tick: str, colour: str) -> str:
    """Render a list of strings as styled bullets."""
    if not items:
        return '<div class="scorecard-empty">—</div>'
    return "".join(
        '<div class="scorecard-bullet">'
        f'<span class="scorecard-bullet-tick" style="color:{colour};">{tick}</span>'
        f'<span>{_e(item)}</span>'
        '</div>'
        for item in items[:4]
    )


# ──────────────────────────────────────────────────────────────────────
# Main HTML builder
# ──────────────────────────────────────────────────────────────────────
def build_dashboard_html(
    *,
    profile: CandidateProfile,
    enrichment: Optional[ProfileEnrichment] = None,   # accepted but unused now
    evaluation: Optional[Evaluation] = None,
    behavioral: Optional[BehavioralEvaluation] = None,
    role_title_override: Optional[str] = None,
) -> str:
    """Build the recruiter scorecard HTML.

    Args:
        profile:             Required. Used for name + role + language.
        enrichment:          Accepted for backward compatibility but no
                             longer rendered — the dashboard doesn't show
                             skills/work_history/personal_details now.
        evaluation:          Technical scorecard. If None, hero shows
                             a 'pending' state.
        behavioral:          Behavioral / personality scorecard. If None
                             or generation_failed=True, the behavioral
                             section is hidden.
        role_title_override: Optional human-readable role label.
    """
    name = profile.name or "Candidate"
    role_key = profile.applied_role
    role_title = (
        role_title_override
        or QUESTION_BANK.get(role_key, {}).get("title", role_key.replace("_", " ").title())
    )
    # The role title sometimes includes a native-language alias after "|"
    # ("Housekeeping | घर का काम"). Strip that so the dashboard stays English.
    role_short = role_title.split("|")[0].strip()

    interview_lang = LANGUAGE_NAMES.get(profile.language, profile.language.upper())

    # ── HERO ────────────────────────────────────────────────────
    if evaluation is not None:
        overall = evaluation.overall_score
        score_display = f"{overall:g}" if overall is not None else "—"
        hire = evaluation.hire_recommendation
        if hire is True:
            badge_html = '<div class="scorecard-badge yes">✓  Recommended</div>'
        elif hire is False:
            badge_html = '<div class="scorecard-badge no">✕  Not recommended</div>'
        else:
            badge_html = '<div class="scorecard-badge pending">○  No verdict</div>'
    else:
        score_display = "—"
        badge_html = '<div class="scorecard-badge pending">○  Awaiting interview</div>'

    hero_html = (
        '<div class="scorecard-hero">'
        '<div class="scorecard-hero-left">'
        f'<div class="scorecard-avatar">{_e(_initials(name))}</div>'
        '<div>'
        f'<div class="scorecard-name">{_e(name)}</div>'
        f'<div class="scorecard-sub">{_e(role_short)} '
        f'<span class="scorecard-sub-dot">·</span> '
        f'{_e(interview_lang)} interview</div>'
        '</div>'
        '</div>'
        '<div class="scorecard-hero-right">'
        f'<div class="scorecard-score-num">{score_display}</div>'
        '<div class="scorecard-score-suffix">/ 10</div>'
        f'{badge_html}'
        '</div>'
        '</div>'
    )

    # ── ABOUT (summary) ─────────────────────────────────────────
    if evaluation is not None and evaluation.summary and evaluation.summary != "—":
        about_html = (
            '<div class="scorecard-section">'
            '<div class="scorecard-section-label">About this candidate</div>'
            f'<div class="scorecard-paragraph">{_e(evaluation.summary)}</div>'
            '</div>'
        )
    else:
        about_html = (
            '<div class="scorecard-section">'
            '<div class="scorecard-section-label">About this candidate</div>'
            '<div class="scorecard-empty">Summary will appear after the interview.</div>'
            '</div>'
        )

    # ── STRENGTHS / IMPROVEMENTS (2 columns) ────────────────────
    if evaluation is not None:
        strengths = list(evaluation.strengths or [])
        improvements = list(evaluation.improvements or [])
    else:
        strengths, improvements = [], []
    pros_cons_html = (
        '<div class="scorecard-row-pair">'
        '<div class="scorecard-section">'
        '<div class="scorecard-section-label">'
        '<span style="color:#10b981;">✓</span> Strengths'
        '</div>'
        f'{_bullet_list(strengths, "✓", "#10b981")}'
        '</div>'
        '<div class="scorecard-section">'
        '<div class="scorecard-section-label">'
        '<span style="color:#f59e0b;">⚠</span> Areas to improve'
        '</div>'
        f'{_bullet_list(improvements, "▸", "#f59e0b")}'
        '</div>'
        '</div>'
    )

    # ── SCORE BREAKDOWN ─────────────────────────────────────────
    if evaluation is not None:
        breakdown_html = (
            '<div class="scorecard-section">'
            '<div class="scorecard-section-label">Score breakdown</div>'
            + _score_row("Domain knowledge", evaluation.domain_knowledge)
            + _score_row("Communication", evaluation.communication)
            + _score_row("Safety awareness", evaluation.safety_awareness)
            + _score_row("Confidence", evaluation.confidence)
            + '</div>'
        )
    else:
        breakdown_html = (
            '<div class="scorecard-section">'
            '<div class="scorecard-section-label">Score breakdown</div>'
            '<div class="scorecard-empty">Scores will appear after the interview.</div>'
            '</div>'
        )

    # ── BEHAVIORAL / TRUST PROFILE (new) ────────────────────────
    # When the round didn't run or failed, show an explanatory notice
    # instead of silently hiding the section.
    behavioral_html = ""
    if behavioral is None:
        behavioral_html = (
            '<div class="trust-section">'
            '<div class="scorecard-section-label">🧭 Trust Profile (Behavioral Round)</div>'
            '<div class="scorecard-empty">'
            'Behavioral round was not completed for this interview. '
            'It runs automatically after the technical round on a fresh interview.'
            '</div>'
            '</div>'
        )
    elif behavioral.generation_failed:
        avg = behavioral.avg_response_seconds
        timing_note = (
            f' Avg response time captured: <b>{avg:.1f}s</b>.'
            if avg is not None else ''
        )
        behavioral_html = (
            '<div class="trust-section">'
            '<div class="scorecard-section-label">🧭 Trust Profile (Behavioral Round)</div>'
            '<div class="scorecard-empty">'
            f'Behavioral evaluation could not be scored by the LLM this time.{timing_note}'
            '</div>'
            '</div>'
        )
    elif behavioral is not None and not behavioral.generation_failed:
        # 5 trait scores → radar chart
        trait_scores: list[tuple[str, float]] = []
        for field_key, label, _icon in BEHAVIORAL_TRAITS:
            value = getattr(behavioral, field_key, None) or 0.0
            trait_scores.append((label, float(value)))
        radar_svg = _radar_chart_svg(trait_scores)

        # Per-trait bars (paired with radar — bars are scannable, radar is "wow")
        trait_rows = "".join(
            f'<div class="trust-trait-row">'
            f'<span class="trust-trait-icon">{icon}</span>'
            f'<span class="trust-trait-label">{_e(label)}</span>'
            f'<span class="trust-trait-track">'
            f'<span class="trust-trait-bar" style="width:{int(round((getattr(behavioral, key, 0) or 0) * 10))}%;"></span>'
            f'</span>'
            f'<span class="trust-trait-num">{(getattr(behavioral, key, 0) or 0):g}</span>'
            f'</div>'
            for key, label, icon in BEHAVIORAL_TRAITS
        )

        # Summary paragraph
        bsummary = (behavioral.overall_summary or "").strip() or "—"
        summary_html = (
            f'<div class="trust-summary">{_e(bsummary)}</div>'
        )

        # Why-this-score drilldown
        reasoning = behavioral.per_trait_reasoning or {}
        if reasoning:
            reason_items = []
            for key, label, icon in BEHAVIORAL_TRAITS:
                if key in reasoning and reasoning[key]:
                    reason_items.append(
                        f'<div class="trust-reason-item">'
                        f'<span class="trust-reason-icon">{icon}</span>'
                        f'<span><b>{_e(label)}:</b> {_e(reasoning[key])}</span>'
                        f'</div>'
                    )
            reasoning_html = (
                '<div class="trust-reasoning">'
                + "".join(reason_items)
                + '</div>'
            )
        else:
            reasoning_html = ""

        # Trust signals row (timing + specificity + consistency)
        signals = []
        if behavioral.avg_response_seconds is not None:
            signals.append(
                f'<span class="trust-signal-item">⏱  Avg response time: '
                f'<b>{behavioral.avg_response_seconds:.1f}s</b></span>'
            )
        if behavioral.answer_specificity is not None:
            signals.append(
                f'<span class="trust-signal-item">📝  Answer specificity: '
                f'<b>{behavioral.answer_specificity:g}/10</b></span>'
            )
        if behavioral.cross_question_consistency:
            cons_colour = {
                "high": "#10b981", "medium": "#f59e0b", "low": "#ef4444",
            }.get(behavioral.cross_question_consistency, "#71717A")
            signals.append(
                f'<span class="trust-signal-item">🔗  Consistency: '
                f'<b style="color:{cons_colour};">{behavioral.cross_question_consistency}</b></span>'
            )
        signals_html = (
            '<div class="trust-signals">' + "".join(signals) + '</div>'
            if signals else ""
        )

        behavioral_html = (
            '<div class="trust-section">'
            '<div class="scorecard-section-label">🧭 Trust Profile (Behavioral Round)</div>'
            f'{summary_html}'
            '<div class="trust-grid">'
            f'<div class="trust-radar">{radar_svg}</div>'
            f'<div class="trust-bars">{trait_rows}</div>'
            '</div>'
            f'{signals_html}'
            f'{reasoning_html}'
            '</div>'
        )

    # ── Assemble ────────────────────────────────────────────────
    return (
        '<div class="scorecard">'
        f'{hero_html}'
        f'{about_html}'
        f'{pros_cons_html}'
        f'{breakdown_html}'
        f'{behavioral_html}'
        '</div>'
    )


# ──────────────────────────────────────────────────────────────────────
# Streamlit-facing convenience wrapper
# ──────────────────────────────────────────────────────────────────────
def render_candidate_dashboard(
    *,
    profile: CandidateProfile,
    enrichment: Optional[ProfileEnrichment] = None,
    evaluation: Optional[Evaluation] = None,
    behavioral: Optional[BehavioralEvaluation] = None,
) -> None:
    """Render the candidate scorecard in the current Streamlit view."""
    html = build_dashboard_html(
        profile=profile,
        enrichment=enrichment,
        evaluation=evaluation,
        behavioral=behavioral,
    )
    st.markdown(html, unsafe_allow_html=True)
