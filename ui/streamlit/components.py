"""
components.py — Reusable Streamlit widgets used across multiple views.

Includes:
  * avatars, top status bar, "your turn" banner
  * the colour-coded resume card renderer
  * tiny wrappers around the TTS / STT services so views don't import them directly
"""

from __future__ import annotations

import html as _html
from pathlib import Path
from typing import Optional

import streamlit as st

from constants.app_constants import (
    APP_LOGO_FILENAME,
    APP_LOGO_WIDTH_PX,
    APP_NAME,
    APP_TAGLINE,
    AVATAR_BG_COLOURS,
    BOT_AVATAR_URL,
    COLOR_PRIMARY,
    SECTION_COLOURS_HEX,
    TEMP_AUDIO_SUBDIR,
)
from data.profile_questions import PROFILE_QUESTIONS
from data.interview_questions import QUESTION_BANK
from services.sarvam_stt_service import SarvamSttService
from services.sarvam_tts_service import SarvamTtsService
from utils.exceptions import (
    SarvamApiError,
    SttAudioTooShortError,
)
from utils.logger import get_logger


logger = get_logger(__name__)


# ──────────────────────────────────────────────────────────────────────
# Brand header — logo (or text fallback) + tagline.
# Rendered ONCE per page load from ui/streamlit/app.py so every view
# inherits the same branding without duplicating the markup.
# ──────────────────────────────────────────────────────────────────────
def _project_root() -> Path:
    """Project root (one level up from `ui/`)."""
    return Path(__file__).resolve().parent.parent.parent


def _encode_logo_as_data_uri() -> str | None:
    """Read the logo file from disk and return a base64 data URI.

    Returns ``None`` if the file doesn't exist (graceful fallback to the
    text header). Using a data URI means we can embed the image directly
    in HTML so it stays on the same row as the tagline.
    """
    import base64
    import mimetypes

    logo_path = _project_root() / APP_LOGO_FILENAME
    if not logo_path.exists():
        return None
    mime, _ = mimetypes.guess_type(logo_path.name)
    mime = mime or "image/png"
    data = base64.b64encode(logo_path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{data}"


def render_brand_header() -> None:
    """Render the brand panel at the top of every page.

    The new logo image is a complete brand panel — it already contains
    the wordmark, the tagline, and the five feature icons — so the
    cleanest layout is a single centered image inside a soft white
    card. A text tagline below the image acts as a fallback for cases
    where the PNG fails to load.
    """
    logo_uri = _encode_logo_as_data_uri()

    if logo_uri:
        inner = (
            f'<img src="{logo_uri}" '
            f'alt="{APP_NAME} — {APP_TAGLINE}" '
            f'style="width:{APP_LOGO_WIDTH_PX}px; max-width:95%; '
            f'height:auto; display:block; margin: 0 auto;" />'
        )
    else:
        # Text fallback when the PNG is missing.
        inner = (
            f'<div style="text-align:center;">'
            f'<div style="font-size:2rem; font-weight:700; '
            f'letter-spacing:0.3px; color:#1a1a2e;">🎙 {APP_NAME}</div>'
            f'<div style="margin-top:6px; font-size:1.15rem; font-style:italic; '
            f'color:#4f46e5;">{APP_TAGLINE}</div>'
            f'</div>'
        )

    st.markdown(
        f"""
        <div style="
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 14px 22px;
            margin: -8px 0 18px 0;
            background: #ffffff;
            border-radius: 12px;
            border: 1px solid #e5e7eb;
            box-shadow: 0 2px 10px rgba(79, 70, 229, 0.08);
        ">
            {inner}
        </div>
        """,
        unsafe_allow_html=True,
    )


# ──────────────────────────────────────────────────────────────────────
# Avatars
# ──────────────────────────────────────────────────────────────────────
def _initials(name: str) -> str:
    """Pick 1–2 letters from a name for the avatar circle.

    Uses the first letter of the first and last whitespace-separated
    tokens, both upper-cased. Falls back to '?' for empty input.
    """
    name = (name or "").strip()
    if not name:
        return "?"
    parts = [p for p in name.split() if p]
    if len(parts) == 1:
        return parts[0][0].upper()
    return (parts[0][0] + parts[-1][0]).upper()


def _stable_colour(name: str) -> str:
    """Deterministic colour pick — same person always gets the same bg."""
    import hashlib
    h = int(hashlib.md5((name or "").encode("utf-8")).hexdigest(), 16)
    return AVATAR_BG_COLOURS[h % len(AVATAR_BG_COLOURS)]


def candidate_avatar_url(name: str) -> str:
    """Return an inline SVG initial-letter avatar as a base64 data URI.

    Cleaner than the external Dicebear cartoon avatars — instant load,
    no network, on-brand colours, and reads as "professional" rather
    than "demo prototype". Each candidate gets a stable background
    colour derived from a hash of their name.
    """
    import base64
    initials = _initials(name)
    bg = _stable_colour(name)
    # Two-character initials need a slightly smaller font to fit cleanly.
    font_size = 44 if len(initials) == 1 else 36
    svg = f"""<?xml version='1.0' encoding='UTF-8'?>
<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100' width='100' height='100'>
  <defs>
    <linearGradient id='g' x1='0%' y1='0%' x2='100%' y2='100%'>
      <stop offset='0%' stop-color='{bg}' stop-opacity='1'/>
      <stop offset='100%' stop-color='{bg}' stop-opacity='0.75'/>
    </linearGradient>
  </defs>
  <circle cx='50' cy='50' r='50' fill='url(#g)'/>
  <text x='50' y='50' font-family='Plus Jakarta Sans, Inter, sans-serif'
        font-size='{font_size}' font-weight='700' fill='white'
        text-anchor='middle' dominant-baseline='central'
        letter-spacing='0.5'>{initials}</text>
</svg>"""
    encoded = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return f"data:image/svg+xml;base64,{encoded}"


def bot_avatar_url() -> str:
    """Branded inline SVG avatar for the AI interviewer."""
    import base64
    svg = f"""<?xml version='1.0' encoding='UTF-8'?>
<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100' width='100' height='100'>
  <circle cx='50' cy='50' r='50' fill='{COLOR_PRIMARY}'/>
  <!-- microphone glyph -->
  <rect x='42' y='28' width='16' height='30' rx='8' fill='white'/>
  <path d='M30 50 Q30 70 50 70 Q70 70 70 50' stroke='white' stroke-width='4' fill='none' stroke-linecap='round'/>
  <line x1='50' y1='70' x2='50' y2='80' stroke='white' stroke-width='4' stroke-linecap='round'/>
</svg>"""
    encoded = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return f"data:image/svg+xml;base64,{encoded}"


# ──────────────────────────────────────────────────────────────────────
# TTS / STT helpers
#
# Why functions and not direct service calls in views: keeps a single
# place to swap audio backends if we ever move off Sarvam, and lets us
# add UI-side concerns (toasts, file paths) without polluting services.
# ──────────────────────────────────────────────────────────────────────
def generate_tts(text: str, tts_service: SarvamTtsService) -> Optional[bytes]:
    """Synthesize speech and return WAV bytes (or None on failure)."""
    from config.settings import get_settings  # local import → no UI in core
    settings = get_settings()
    try:
        path = (
            settings.output_dir / TEMP_AUDIO_SUBDIR
            / f"tts_{abs(hash(text)) % 10**8}.wav"
        )
        result = tts_service.text_to_speech(
            text=text,
            output_path=str(path),
            language_code=st.session_state.lang_code,
        )
        return result.audio_bytes
    except SarvamApiError as e:
        st.warning(f"TTS failed: {e}")
        return None
    except Exception as e:
        st.warning(f"TTS unexpected error: {e}")
        return None


def transcribe(
    audio_bytes: bytes,
    stt_service: SarvamSttService,
    *,
    file_prefix: str = "answer",
) -> Optional[str]:
    """Save the recording, run STT, return transcript or None on hard failure.

    Returns:
        - str  → transcript (possibly empty if candidate stayed silent)
        - None → hard failure; caller should NOT advance the stage.
    """
    from config.settings import get_settings
    settings = get_settings()
    wav_path = (
        settings.output_dir / TEMP_AUDIO_SUBDIR
        / f"{file_prefix}_{st.session_state.question_idx}_{st.session_state.follow_up_count}.wav"
    )
    wav_path.parent.mkdir(parents=True, exist_ok=True)
    with open(wav_path, "wb") as f:
        f.write(audio_bytes)
    try:
        result = stt_service.speech_to_text(
            str(wav_path),
            language_code=st.session_state.lang_code,
        )
        return result.transcript
    except SttAudioTooShortError:
        st.error(
            "🎙 The microphone didn't capture any sound. "
            "Check that your browser has mic permission "
            "(look for the 🎙 icon in the address bar), then click the mic and try again."
        )
        return None
    except SarvamApiError as e:
        st.error(f"STT failed: {e}")
        return None


# ──────────────────────────────────────────────────────────────────────
# Profile prompt resolver
# ──────────────────────────────────────────────────────────────────────
def profile_prompt(idx: int) -> str:
    """Return the localized profile question at ``idx`` with `{role}`
    substituted with the candidate's applied role.

    Always use this — never index PROFILE_QUESTIONS directly in views.
    """
    role_title = QUESTION_BANK[st.session_state.role]["title"]
    raw = PROFILE_QUESTIONS[idx]["prompts"][st.session_state.lang]
    try:
        return raw.format(role=role_title)
    except (KeyError, IndexError):
        return raw


# ──────────────────────────────────────────────────────────────────────
# Top status bar
# ──────────────────────────────────────────────────────────────────────
def render_top_bar(progress: float, *, badge_text: str, badge_colour: Optional[str] = None) -> None:
    """The role/avatar/progress bar that appears on most views."""
    role_title = QUESTION_BANK[st.session_state.role]["title"]
    col_l, col_m, col_r = st.columns([2, 3, 2])
    with col_l:
        st.image(candidate_avatar_url(st.session_state.candidate_name), width=44)
        st.markdown(f"**{st.session_state.candidate_name}**")
        st.caption(role_title)
    with col_m:
        st.progress(progress, text=badge_text)
    with col_r:
        colour = badge_colour or ""
        colour_css = f" color:{colour};" if colour else ""
        dot = (
            "<span class='pulse-dot'></span>"
            if not colour else ""
        )
        st.markdown(
            f"<div style='text-align:right; font-weight:600;{colour_css}'>"
            f"{dot}{badge_text}"
            f"</div>",
            unsafe_allow_html=True,
        )
    st.divider()


def voice_waveform_html(speaker: str = "bot") -> str:
    """Return a CSS-animated waveform as raw HTML.

    Use this when you want to inline the waveform inside other HTML
    (e.g. alongside an "AI is speaking" label). For a standalone
    waveform call ``render_voice_waveform()`` instead.

    Args:
        speaker: ``"bot"`` (default, indigo bars) or ``"user"``
                 (emerald bars — visual marker for "we're listening").

    The animation is CSS-only and not synced to actual audio levels.
    The intent is to make voice moments *feel* alive — a static audio
    bar reads as a recording; the waveform reads as a conversation.
    """
    klass = "voice-waveform" + (" is-user" if speaker == "user" else "")
    bars = "".join('<div class="bar"></div>' for _ in range(7))
    return f'<div class="{klass}">{bars}</div>'


def render_voice_waveform(speaker: str = "bot") -> None:
    """Standalone waveform widget — wraps voice_waveform_html in st.markdown."""
    st.markdown(voice_waveform_html(speaker), unsafe_allow_html=True)


def render_your_turn_banner(pause_seconds: float) -> None:
    st.markdown(
        f"<div class='your-turn-banner'>"
        f"🎙 YOUR TURN — click the mic, then speak. "
        f"Recording auto-stops after {pause_seconds:.1f}s of silence."
        f"</div>",
        unsafe_allow_html=True,
    )


# ──────────────────────────────────────────────────────────────────────
# Colourful resume card renderer (used on the profile review screen)
# ──────────────────────────────────────────────────────────────────────
def parse_resume_sections(
    resume_text: str,
) -> tuple[list[str], list[tuple[str, str, str, list[str]]]]:
    """Split the resume into (header_lines, sections) where each section
    is (title, icon, colour, body_lines)."""
    lines = resume_text.splitlines()
    header: list[str] = []
    sections: list[tuple[str, str, str, list[str]]] = []
    current: Optional[tuple[str, str, str, list[str]]] = None

    def _normalize(s: str) -> str:
        return s.strip().rstrip(":").strip().lower()

    for raw in lines:
        norm = _normalize(raw)
        if norm and norm in SECTION_COLOURS_HEX:
            if current is not None:
                sections.append(current)
            icon, colour = SECTION_COLOURS_HEX[norm]
            current = (raw.strip().rstrip(":"), icon, colour, [])
        elif current is None:
            if raw.strip():
                header.append(raw.strip())
        else:
            current[3].append(raw)

    if current is not None:
        sections.append(current)
    return header, sections


def render_pretty_resume(resume_text: str) -> None:
    """Render the resume as colour-accented Streamlit cards."""
    header, sections = parse_resume_sections(resume_text)

    # Header card (name + contact placeholders)
    name = header[0] if header else "Candidate"
    contact_lines = header[1:] if len(header) > 1 else []
    contact_html = "<br>".join(_html.escape(l) for l in contact_lines) or "&nbsp;"
    st.markdown(
        f"""
        <div style="
            background: linear-gradient(135deg, #4f8ef7 0%, #6a5acd 100%);
            color: white; padding: 26px 28px; border-radius: 12px;
            box-shadow: 0 4px 12px rgba(79,142,247,0.25);
            margin-bottom: 16px;
        ">
            <div style="font-size: 2.1rem; font-weight: 700; letter-spacing: 0.5px;">
                {_html.escape(name)}
            </div>
            <div style="opacity: 0.95; margin-top: 8px; font-size: 1.15rem;">
                {contact_html}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if not sections:
        st.code(resume_text, language="text")
        return

    for title, icon, colour, body in sections:
        body_clean = list(body)
        while body_clean and not body_clean[0].strip():
            body_clean.pop(0)
        while body_clean and not body_clean[-1].strip():
            body_clean.pop()

        body_html_parts: list[str] = []
        for ln in body_clean:
            if not ln.strip():
                body_html_parts.append("<div style='height:6px;'></div>")
                continue
            escaped = _html.escape(ln.rstrip())
            if ln.lstrip().startswith(("-", "•", "*")):
                body_html_parts.append(
                    f"<div style='margin-left:14px; padding:2px 0; color:#333;'>"
                    f"<span style='color:{colour}; margin-right:6px;'>•</span>"
                    f"{escaped.lstrip()[1:].lstrip()}</div>"
                )
            else:
                body_html_parts.append(
                    f"<div style='padding:2px 0; color:#333;'>{escaped}</div>"
                )

        body_html = "\n".join(body_html_parts)
        st.markdown(
            f"""
            <div style="
                background: white;
                border-left: 5px solid {colour};
                border-radius: 8px;
                padding: 16px 20px;
                margin-bottom: 12px;
                box-shadow: 0 2px 6px rgba(0,0,0,0.06);
                transition: box-shadow 0.2s ease, transform 0.2s ease;
            "
            onmouseover="this.style.boxShadow='0 4px 14px rgba(0,0,0,0.12)';this.style.transform='translateY(-1px)';"
            onmouseout="this.style.boxShadow='0 2px 6px rgba(0,0,0,0.06)';this.style.transform='translateY(0)';"
            >
                <div style="
                    font-size: 1.3rem; font-weight: 700; color: {colour};
                    margin-bottom: 10px; text-transform: uppercase; letter-spacing: 0.5px;
                ">
                    <span style="margin-right:6px;">{icon}</span>{_html.escape(title)}
                </div>
                <div style="font-size: 1.15rem; line-height: 1.65;">
                    {body_html}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
