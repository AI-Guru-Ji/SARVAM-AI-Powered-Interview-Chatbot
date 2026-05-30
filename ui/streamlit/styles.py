"""
styles.py — All Streamlit-injected CSS in one place.

The CSS string is built once with the design-system tokens from
``constants/app_constants.py`` so any palette tweak ripples across
every view without grepping. ``inject_global_css()`` runs once per
page load from ``ui/streamlit/app.py``.
"""

from __future__ import annotations

import streamlit as st

from constants.app_constants import (
    COLOR_ACCENT,
    COLOR_DANGER,
    COLOR_NEUTRAL_100,
    COLOR_NEUTRAL_200,
    COLOR_NEUTRAL_400,
    COLOR_NEUTRAL_500,
    COLOR_NEUTRAL_700,
    COLOR_NEUTRAL_900,
    COLOR_PRIMARY,
    COLOR_PRIMARY_DARK,
    COLOR_PRIMARY_SOFT,
    COLOR_SUCCESS,
)


def _build_css() -> str:
    return f"""
<!-- Google Fonts: Inter (UI) + Plus Jakarta Sans (display) + Noto Sans Devanagari (Hindi fallback) -->
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Plus+Jakarta+Sans:wght@500;600;700&family=Noto+Sans+Devanagari:wght@400;500;600;700&display=swap" rel="stylesheet">

<style>
/* ══════════════════════════════════════════════════════════════════
   Hide Streamlit's default chrome so the app feels like a product,
   not a Streamlit notebook.
   ══════════════════════════════════════════════════════════════════ */
#MainMenu, footer, header[data-testid="stHeader"], [data-testid="stToolbar"] {{
    visibility: hidden !important;
    height: 0 !important;
    padding: 0 !important;
}}
/* The "Made with Streamlit" footer (newer builds use a different id) */
[data-testid="stStatusWidget"] {{ visibility: hidden !important; }}
.viewerBadge_container__1QSob, ._terminalButton_rix23_138 {{ display: none !important; }}
.stDeployButton {{ display: none !important; }}

/* Reduce the giant default top padding so brand header sits near the top */
.block-container {{
    padding-top: 1.2rem !important;
    padding-bottom: 3rem !important;
    max-width: 880px !important;
}}

/* ══════════════════════════════════════════════════════════════════
   Typography — Inter for UI, Plus Jakarta Sans for display headings,
   Noto Sans Devanagari fallback for Hindi/Punjabi/Gujarati scripts.

   IMPORTANT: do NOT use a broad selector like [class*="st-"] here.
   Streamlit's expander toggle icons (and other UI chrome) are rendered
   with the Material Symbols icon font; overriding the font-family on
   those elements makes the ligature names (e.g. "keyboard_arrow_down")
   show as raw text. We scope the override to the page roots only and
   let typography cascade naturally from there.
   ══════════════════════════════════════════════════════════════════ */
html, body, .stApp, .main, .block-container {{
    font-family: 'Inter', 'Noto Sans Devanagari', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif !important;
    font-size: 16px !important;
    line-height: 1.6 !important;
    color: {COLOR_NEUTRAL_700} !important;
    -webkit-font-smoothing: antialiased;
    text-rendering: optimizeLegibility;
}}

/* Belt-and-braces: explicitly restore the Material Symbols font for the
   Streamlit icon elements that may have inherited "Inter" from a parent.
   The icon font ligatures only work when this exact family is set. */
[data-testid="stExpanderToggleIcon"],
[data-testid="stExpanderToggleIcon"] *,
.material-symbols-outlined,
.material-symbols-rounded,
.material-symbols-sharp,
[class*="material-icons"],
[class*="material-icons"] * {{
    font-family: 'Material Symbols Rounded', 'Material Symbols Outlined',
                 'Material Icons', 'Material Icons Outlined' !important;
}}

h1, h2, h3, .stMarkdown h1, .stMarkdown h2, .stMarkdown h3 {{
    font-family: 'Plus Jakarta Sans', 'Noto Sans Devanagari', -apple-system, sans-serif !important;
    color: {COLOR_NEUTRAL_900} !important;
    letter-spacing: -0.01em !important;
}}
h1, .stMarkdown h1 {{ font-size: 2rem !important;   font-weight: 700 !important; line-height: 1.2 !important; }}
h2, .stMarkdown h2 {{ font-size: 1.5rem !important; font-weight: 600 !important; line-height: 1.3 !important; }}
h3, .stMarkdown h3 {{ font-size: 1.2rem !important; font-weight: 600 !important; line-height: 1.35 !important; }}

p, .stMarkdown p, .stMarkdown li {{
    font-size: 1.0625rem !important;
    line-height: 1.65 !important;
    color: {COLOR_NEUTRAL_700} !important;
}}
.stCaption, [data-testid="stCaptionContainer"] {{
    font-size: 0.9rem !important;
    color: {COLOR_NEUTRAL_500} !important;
    font-weight: 500 !important;
}}

/* App-wide background */
.stApp {{ background: {COLOR_NEUTRAL_100} !important; }}

/* ══════════════════════════════════════════════════════════════════
   Buttons — primary CTA uses brand indigo, secondary uses neutral
   ══════════════════════════════════════════════════════════════════ */
.stButton button, .stDownloadButton button, .stFormSubmitButton button {{
    font-family: 'Inter', 'Noto Sans Devanagari', sans-serif !important;
    font-size: 1.05rem !important;
    font-weight: 600 !important;
    padding: 12px 22px !important;
    border-radius: 12px !important;
    border: 1px solid {COLOR_NEUTRAL_200} !important;
    transition: all 0.2s cubic-bezier(0.22, 1, 0.36, 1) !important;
    box-shadow: 0 1px 2px rgba(24, 24, 27, 0.04) !important;
}}
.stButton button:hover, .stDownloadButton button:hover, .stFormSubmitButton button:hover {{
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 14px rgba(24, 24, 27, 0.08) !important;
}}
/* Primary buttons — kind="primary".
   Streamlit wraps the button label in a <p> inside a markdown
   container; the global paragraph "color: neutral_700" rule wins
   over the button's own colour without the wildcard child selector. */
.stButton button[kind="primary"],
.stDownloadButton button[kind="primary"],
.stFormSubmitButton button[kind="primary"] {{
    background: {COLOR_PRIMARY} !important;
    border-color: {COLOR_PRIMARY} !important;
    box-shadow: 0 2px 8px rgba(79, 70, 229, 0.25) !important;
}}
.stButton button[kind="primary"],
.stButton button[kind="primary"] *,
.stDownloadButton button[kind="primary"],
.stDownloadButton button[kind="primary"] *,
.stFormSubmitButton button[kind="primary"],
.stFormSubmitButton button[kind="primary"] * {{
    color: white !important;
    fill: white !important;
}}
.stButton button[kind="primary"]:hover,
.stDownloadButton button[kind="primary"]:hover,
.stFormSubmitButton button[kind="primary"]:hover {{
    background: {COLOR_PRIMARY_DARK} !important;
    border-color: {COLOR_PRIMARY_DARK} !important;
    box-shadow: 0 6px 18px rgba(79, 70, 229, 0.35) !important;
}}

/* ══════════════════════════════════════════════════════════════════
   Form fields
   ══════════════════════════════════════════════════════════════════ */
.stTextInput input, .stSelectbox div[data-baseweb="select"] {{
    font-family: 'Inter', 'Noto Sans Devanagari', sans-serif !important;
    font-size: 1.05rem !important;
    border-radius: 10px !important;
}}
.stTextInput label, .stSelectbox label {{
    font-size: 0.95rem !important;
    font-weight: 600 !important;
    color: {COLOR_NEUTRAL_900} !important;
}}
.stTextInput input:focus {{
    border-color: {COLOR_PRIMARY} !important;
    box-shadow: 0 0 0 3px {COLOR_PRIMARY_SOFT} !important;
}}

/* ══════════════════════════════════════════════════════════════════
   Chat bubbles — neutral cards. The avatar (mic icon for the bot,
   initials for the candidate) carries the role distinction so we
   don't need different background tints per role.
   ══════════════════════════════════════════════════════════════════ */
[data-testid="stChatMessage"] {{
    background: white !important;
    border-radius: 16px !important;
    padding: 16px 18px !important;
    margin-bottom: 12px !important;
    box-shadow: 0 1px 3px rgba(24, 24, 27, 0.04) !important;
    border: 1px solid {COLOR_NEUTRAL_200} !important;
}}
[data-testid="stChatMessage"] img {{
    border-radius: 50% !important;
    width: 44px !important;
    height: 44px !important;
    box-shadow: 0 2px 6px rgba(24, 24, 27, 0.10);
}}
[data-testid="stChatMessage"] p,
[data-testid="stChatMessage"] li,
[data-testid="stChatMessage"] .stMarkdown {{
    font-size: 1.1rem !important;
    line-height: 1.55 !important;
}}
[data-testid="stChatMessage"] strong {{ font-size: 1.15rem !important; }}

/* "Bot speaking" caption */
.bot-speaking {{
    color: {COLOR_PRIMARY} !important;
    font-size: 0.95rem !important;
    font-weight: 500 !important;
    font-style: italic;
    letter-spacing: 0.01em;
}}

/* ══════════════════════════════════════════════════════════════════
   Pulse animations (live indicator + "your turn" banner)
   ══════════════════════════════════════════════════════════════════ */
.pulse-dot {{
    display: inline-block;
    width: 10px;
    height: 10px;
    background: {COLOR_DANGER};
    border-radius: 50%;
    margin-right: 6px;
    animation: pulse 1.4s infinite;
}}
@keyframes pulse {{
    0%, 100% {{ opacity: 1; transform: scale(1); }}
    50%      {{ opacity: 0.4; transform: scale(1.25); }}
}}

.your-turn-banner {{
    text-align: center;
    padding: 14px 18px;
    background: linear-gradient(135deg, {COLOR_SUCCESS}, #059669);
    color: white;
    border-radius: 14px;
    margin: 16px 0;
    font-weight: 600;
    font-size: 1.1rem;
    letter-spacing: 0.01em;
    box-shadow: 0 4px 14px rgba(16, 185, 129, 0.35);
    animation: pulse-banner 2.2s ease-in-out infinite;
}}
@keyframes pulse-banner {{
    0%, 100% {{ box-shadow: 0 4px 14px rgba(16, 185, 129, 0.35); }}
    50%      {{ box-shadow: 0 8px 24px rgba(16, 185, 129, 0.55); }}
}}

/* ══════════════════════════════════════════════════════════════════
   Hide every st.audio() player bar app-wide.
   The underlying <audio> element stays in the DOM (autoplay still
   fires); we just collapse its visual footprint so the bot's voice
   plays silently in the background instead of a clunky player bar.
   ══════════════════════════════════════════════════════════════════ */
[data-testid="stAudio"], [data-testid="stAudioContainer"] {{
    height: 0 !important;
    margin: 0 !important;
    padding: 0 !important;
    overflow: hidden !important;
    opacity: 0 !important;
    pointer-events: none !important;
}}
/* Belt-and-braces: many Streamlit versions render the <audio> tag
   inside a generic wrapper without the testid above. Catch any
   stray HTML5 audio element too. */
audio {{
    height: 0 !important;
    margin: 0 !important;
    opacity: 0 !important;
    pointer-events: none !important;
}}

/* ══════════════════════════════════════════════════════════════════
   Welcome unlock card — shown on the very first session visit so
   the recruiter clicks once before the welcome audio plays. The
   click satisfies the browser's autoplay policy.
   ══════════════════════════════════════════════════════════════════ */
.welcome-unlock-card {{
    background: linear-gradient(135deg, #ffffff 0%, {COLOR_PRIMARY_SOFT} 100%);
    border: 1px solid #E4E4E7;
    border-radius: 20px;
    padding: 44px 36px 28px 36px;
    text-align: center;
    box-shadow: 0 8px 32px rgba(79, 70, 229, 0.10);
    margin: 24px 0 16px 0;
    animation: unlock-card-in 0.4s cubic-bezier(0.22, 1, 0.36, 1);
}}
.welcome-unlock-eyebrow {{
    font-family: 'Inter', sans-serif;
    font-size: 0.85rem;
    font-weight: 700;
    color: {COLOR_PRIMARY};
    text-transform: uppercase;
    letter-spacing: 0.12em;
    margin-bottom: 12px;
}}
.welcome-unlock-title {{
    font-family: 'Plus Jakarta Sans', sans-serif;
    font-size: 1.75rem;
    font-weight: 700;
    color: {COLOR_NEUTRAL_900};
    line-height: 1.25;
    margin-bottom: 12px;
}}
.welcome-unlock-sub {{
    color: {COLOR_NEUTRAL_500};
    font-size: 1.0rem;
    line-height: 1.55;
    margin-bottom: 4px;
}}
@keyframes unlock-card-in {{
    from {{ opacity: 0; transform: translateY(8px) scale(0.99); }}
    to   {{ opacity: 1; transform: translateY(0)   scale(1);    }}
}}
/* Pulse the unlock button so the recruiter's eye is drawn to it */
button[kind="primary"][data-testid="baseButton-primary"]:has(span:contains("Click here to begin")) {{
    animation: unlock-pulse 2.2s ease-in-out infinite;
}}
@keyframes unlock-pulse {{
    0%, 100% {{ box-shadow: 0 2px 8px rgba(79, 70, 229, 0.25); }}
    50%      {{ box-shadow: 0 8px 26px rgba(79, 70, 229, 0.55); }}
}}

/* ══════════════════════════════════════════════════════════════════
   Speaking chip — floating top-right pill that confirms voice is
   playing during the setup-screen welcome. Pure CSS lifecycle:
   fades in (0-1 s) → visible (1-8 s) → fades out (8-10 s) → invisible.
   Position: fixed so it never affects page layout.
   ══════════════════════════════════════════════════════════════════ */
.speaking-chip {{
    position: fixed;
    top: 18px;
    right: 24px;
    z-index: 9999;
    background: linear-gradient(135deg, {COLOR_PRIMARY}, #6D28D9);
    color: white !important;
    padding: 10px 18px;
    border-radius: 999px;
    font-family: 'Inter', 'Noto Sans Devanagari', sans-serif;
    font-size: 0.95rem;
    font-weight: 600;
    letter-spacing: 0.01em;
    box-shadow: 0 6px 20px rgba(79, 70, 229, 0.35);
    pointer-events: none;
    animation: chip-life 10s cubic-bezier(0.22, 1, 0.36, 1) forwards;
    backdrop-filter: blur(4px);
}}
@keyframes chip-life {{
    0%   {{ opacity: 0; transform: translateY(-12px) scale(0.95); }}
    10%  {{ opacity: 1; transform: translateY(0)   scale(1);    }}
    80%  {{ opacity: 1; transform: translateY(0)   scale(1);    }}
    100% {{ opacity: 0; transform: translateY(-12px) scale(0.95); }}
}}

/* ══════════════════════════════════════════════════════════════════
   Voice waveform (used near st.audio() during bot speech / playback)
   ══════════════════════════════════════════════════════════════════ */
.voice-waveform {{
    display: inline-flex;
    align-items: flex-end;
    gap: 3px;
    height: 28px;
    padding: 4px 0;
    vertical-align: middle;
}}
.voice-waveform .bar {{
    width: 4px;
    background: {COLOR_PRIMARY};
    border-radius: 2px;
    animation: wave 1.1s ease-in-out infinite;
    transform-origin: bottom;
}}
.voice-waveform .bar:nth-child(1) {{ animation-delay: 0.00s; height: 30%; }}
.voice-waveform .bar:nth-child(2) {{ animation-delay: 0.12s; height: 80%; }}
.voice-waveform .bar:nth-child(3) {{ animation-delay: 0.24s; height: 50%; }}
.voice-waveform .bar:nth-child(4) {{ animation-delay: 0.36s; height: 95%; }}
.voice-waveform .bar:nth-child(5) {{ animation-delay: 0.48s; height: 65%; }}
.voice-waveform .bar:nth-child(6) {{ animation-delay: 0.60s; height: 40%; }}
.voice-waveform .bar:nth-child(7) {{ animation-delay: 0.72s; height: 75%; }}
@keyframes wave {{
    0%, 100% {{ transform: scaleY(0.35); opacity: 0.7; }}
    50%      {{ transform: scaleY(1);    opacity: 1; }}
}}
.voice-waveform.is-user .bar {{ background: {COLOR_SUCCESS}; }}

/* ══════════════════════════════════════════════════════════════════
   Status widget (the profile-building "✨ Building your profile…"
   block) — bigger text + cleaner styling
   ══════════════════════════════════════════════════════════════════ */
[data-testid="stStatusWidget"] p,
[data-testid="stStatusWidget"] div {{
    font-size: 1.05rem !important;
}}

/* ══════════════════════════════════════════════════════════════════
   Metric chips & progress bar polish
   ══════════════════════════════════════════════════════════════════ */
[data-testid="stMetric"] [data-testid="stMetricValue"] {{
    font-family: 'Plus Jakarta Sans', sans-serif !important;
    font-weight: 700 !important;
    color: {COLOR_NEUTRAL_900} !important;
}}
[data-testid="stProgressBar"] > div > div > div > div {{
    background: linear-gradient(90deg, {COLOR_PRIMARY}, {COLOR_ACCENT}) !important;
    border-radius: 999px !important;
}}

/* ══════════════════════════════════════════════════════════════════
   Page-change motion — subtle fade-in on each rerun
   ══════════════════════════════════════════════════════════════════ */
.block-container > div {{
    animation: page-in 0.25s cubic-bezier(0.22, 1, 0.36, 1);
}}
@keyframes page-in {{
    from {{ opacity: 0; transform: translateY(4px); }}
    to   {{ opacity: 1; transform: translateY(0); }}
}}

/* Sidebar polish */
[data-testid="stSidebar"] {{
    background: white !important;
    border-right: 1px solid {COLOR_NEUTRAL_200} !important;
}}

/* Code blocks (resume display fallback) */
.stCode {{
    border-radius: 12px !important;
    font-family: 'JetBrains Mono', ui-monospace, 'Cascadia Code', 'Source Code Pro', monospace !important;
}}

/* Streamlit's expander */
[data-testid="stExpander"] {{
    border-radius: 12px !important;
    border: 1px solid {COLOR_NEUTRAL_200} !important;
    background: white !important;
}}
/* Expander header label — make the title obvious and the arrow neat */
[data-testid="stExpander"] summary,
[data-testid="stExpander"] [data-testid="stExpanderToggleIcon"] + div,
[data-testid="stExpander"] > details > summary {{
    font-size: 1.05rem !important;
    font-weight: 600 !important;
    color: {COLOR_NEUTRAL_900} !important;
    padding: 4px 0 !important;
}}
/* The expander arrow icon — keep Material Symbols but resize cleanly */
[data-testid="stExpanderToggleIcon"] {{
    color: {COLOR_NEUTRAL_500} !important;
    font-size: 1.5rem !important;
}}


/* ─────────────────────────────────────────────────────────────────
   RECRUITER SCORECARD (report_view)
   Minimal, English-only, 4-section layout.
   ───────────────────────────────────────────────────────────────── */
.scorecard {{
    background: white;
    border: 1px solid {COLOR_NEUTRAL_200};
    border-radius: 18px;
    padding: 28px 32px;
    box-shadow: 0 1px 3px rgba(15,23,42,0.04), 0 1px 2px rgba(15,23,42,0.06);
    font-family: 'Inter', sans-serif;
    color: {COLOR_NEUTRAL_900};
}}

/* ── HERO ── */
.scorecard-hero {{
    display: flex; justify-content: space-between; align-items: center;
    gap: 24px; flex-wrap: wrap;
    padding-bottom: 22px;
    border-bottom: 1px solid {COLOR_NEUTRAL_200};
    margin-bottom: 22px;
}}
.scorecard-hero-left {{
    display: flex; align-items: center; gap: 16px;
}}
.scorecard-avatar {{
    width: 64px; height: 64px;
    border-radius: 50%;
    background: linear-gradient(135deg, #6366f1, #06b6d4);
    color: white;
    display: flex; align-items: center; justify-content: center;
    font-size: 1.35rem; font-weight: 700;
    flex-shrink: 0;
    box-shadow: 0 4px 10px rgba(99,102,241,0.25);
}}
.scorecard-name {{
    font-size: 1.6rem; font-weight: 800;
    color: {COLOR_NEUTRAL_900};
    letter-spacing: -0.02em;
    line-height: 1.1;
}}
.scorecard-sub {{
    color: {COLOR_NEUTRAL_500};
    font-size: 0.9rem;
    margin-top: 4px;
}}
.scorecard-sub-dot {{
    color: {COLOR_NEUTRAL_200};
    margin: 0 4px;
}}

.scorecard-hero-right {{
    text-align: right;
    display: flex; flex-direction: column; align-items: flex-end;
    gap: 6px;
}}
.scorecard-score-num {{
    font-size: 3.2rem;
    font-weight: 800;
    line-height: 1;
    color: #10b981;
    letter-spacing: -0.04em;
}}
.scorecard-score-suffix {{
    font-size: 0.8rem;
    color: {COLOR_NEUTRAL_500};
    margin-top: -4px;
    letter-spacing: 0.05em;
}}
.scorecard-badge {{
    display: inline-flex; align-items: center; gap: 6px;
    padding: 5px 12px;
    border-radius: 999px;
    font-size: 0.78rem; font-weight: 700;
    letter-spacing: 0.02em;
    margin-top: 6px;
}}
.scorecard-badge.yes {{
    background: rgba(16,185,129,0.10);
    color: #047857;
    border: 1px solid rgba(16,185,129,0.25);
}}
.scorecard-badge.no {{
    background: rgba(239,68,68,0.10);
    color: #b91c1c;
    border: 1px solid rgba(239,68,68,0.25);
}}
.scorecard-badge.pending {{
    background: {COLOR_NEUTRAL_100};
    color: {COLOR_NEUTRAL_500};
    border: 1px solid {COLOR_NEUTRAL_200};
}}

/* ── SECTIONS ── */
.scorecard-section {{
    margin-bottom: 22px;
}}
.scorecard-section-label {{
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: {COLOR_NEUTRAL_500};
    margin-bottom: 10px;
    display: flex; align-items: center; gap: 6px;
}}
.scorecard-paragraph {{
    font-size: 0.96rem;
    line-height: 1.6;
    color: {COLOR_NEUTRAL_700};
}}
.scorecard-empty {{
    font-size: 0.88rem;
    color: {COLOR_NEUTRAL_500};
    font-style: italic;
    padding: 8px 0;
}}

/* ── STRENGTHS / IMPROVEMENTS (2-col) ── */
.scorecard-row-pair {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 28px;
    margin-bottom: 22px;
}}
@media (max-width: 720px) {{
    .scorecard-row-pair {{ grid-template-columns: 1fr; gap: 16px; }}
}}
.scorecard-bullet {{
    display: flex; gap: 10px; align-items: flex-start;
    padding: 5px 0;
    font-size: 0.92rem;
    color: {COLOR_NEUTRAL_700};
    line-height: 1.5;
}}
.scorecard-bullet-tick {{
    font-weight: 700;
    flex-shrink: 0;
    margin-top: 1px;
}}

/* ── SCORE BREAKDOWN ── */
.scorecard-row {{
    display: flex; align-items: center; gap: 14px;
    margin-bottom: 9px;
    font-size: 0.92rem;
}}
.scorecard-row-label {{
    flex: 0 0 150px;
    color: {COLOR_NEUTRAL_700};
}}
.scorecard-row-track {{
    flex: 1;
    height: 6px;
    background: {COLOR_NEUTRAL_200};
    border-radius: 999px;
    overflow: hidden;
}}
.scorecard-row-bar {{
    height: 100%;
    background: linear-gradient(90deg, #06b6d4, #10b981);
    border-radius: 999px;
    transition: width 0.4s ease;
}}
.scorecard-row-num {{
    flex: 0 0 28px;
    text-align: right;
    font-weight: 700;
    color: {COLOR_NEUTRAL_900};
    font-variant-numeric: tabular-nums;
}}

/* ─────────────────────────────────────────────────────────────────
   TRUST PROFILE (behavioral / personality section)
   ───────────────────────────────────────────────────────────────── */
.trust-section {{
    margin-top: 26px;
    padding-top: 22px;
    border-top: 1px solid {COLOR_NEUTRAL_200};
}}
.trust-summary {{
    background: linear-gradient(135deg, rgba(99,102,241,0.04), rgba(6,182,212,0.03));
    border-left: 3px solid #6366f1;
    border-radius: 10px;
    padding: 12px 16px;
    font-size: 0.92rem; line-height: 1.55;
    color: {COLOR_NEUTRAL_700};
    margin-bottom: 18px;
}}
.trust-grid {{
    display: grid;
    grid-template-columns: 1fr 1.2fr;
    gap: 24px;
    align-items: center;
    margin-bottom: 18px;
}}
@media (max-width: 720px) {{
    .trust-grid {{ grid-template-columns: 1fr; }}
}}
.trust-radar {{
    background: white;
    border: 1px solid {COLOR_NEUTRAL_200};
    border-radius: 12px;
    padding: 12px;
}}
.trust-bars {{
    display: flex; flex-direction: column; gap: 8px;
    padding-left: 4px;
}}
.trust-trait-row {{
    display: flex; align-items: center; gap: 10px;
    font-size: 0.9rem;
}}
.trust-trait-icon {{ flex: 0 0 22px; font-size: 0.95rem; }}
.trust-trait-label {{ flex: 0 0 130px; color: {COLOR_NEUTRAL_700}; }}
.trust-trait-track {{
    flex: 1; height: 6px;
    background: {COLOR_NEUTRAL_200};
    border-radius: 999px; overflow: hidden;
}}
.trust-trait-bar {{
    height: 100%;
    background: linear-gradient(90deg, #6366f1, #06b6d4);
    border-radius: 999px;
}}
.trust-trait-num {{
    flex: 0 0 24px; text-align: right;
    font-weight: 700; color: {COLOR_NEUTRAL_900};
    font-variant-numeric: tabular-nums;
}}
.trust-signals {{
    display: flex; flex-wrap: wrap; gap: 14px;
    padding: 10px 14px;
    background: {COLOR_NEUTRAL_100};
    border-radius: 10px;
    margin-bottom: 14px;
    font-size: 0.84rem;
    color: {COLOR_NEUTRAL_700};
}}
.trust-signal-item {{ display: inline-flex; align-items: center; gap: 4px; }}
.trust-reasoning {{
    background: white;
    border: 1px solid {COLOR_NEUTRAL_200};
    border-radius: 10px;
    padding: 12px 16px;
}}
.trust-reason-item {{
    display: flex; gap: 8px; align-items: flex-start;
    padding: 4px 0;
    font-size: 0.86rem; color: {COLOR_NEUTRAL_700};
    line-height: 1.5;
}}
.trust-reason-icon {{ flex: 0 0 22px; font-size: 0.95rem; margin-top: 1px; }}

</style>
"""


def inject_global_css() -> None:
    """Inject the global stylesheet once per Streamlit page load."""
    st.markdown(_build_css(), unsafe_allow_html=True)
