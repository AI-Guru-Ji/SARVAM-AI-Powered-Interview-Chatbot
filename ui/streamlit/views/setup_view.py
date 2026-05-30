"""
setup_view.py — Stage 1: split-pane setup screen.

When the page loads, a warm Hindi welcome plays automatically so the
demo opens with voice immediately — the audio bar is hidden by global
CSS so it just sounds like the product is talking to the user.

Left pane: a friendly 3-step "how it works" explainer.
Right pane: role / language / candidate-name form + health check.
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from config.settings import get_settings
from constants.app_constants import (
    COLOR_ACCENT,
    COLOR_NEUTRAL_500,
    COLOR_NEUTRAL_900,
    COLOR_PRIMARY,
    COLOR_PRIMARY_SOFT,
    COLOR_SUCCESS,
    STAGE_PROFILE_INTRO,
    TEMP_AUDIO_SUBDIR,
)
from data.interview_questions import (
    LANGUAGES,
    OPENING_MESSAGE,
    QUESTION_BANK,
    SETUP_WELCOME_LANG_CODE,
    SETUP_WELCOME_TEXT,
)
from data.profile_questions import PROFILE_INTRO
from services.health_check_service import HealthCheckService
from services.sarvam_tts_service import SarvamTtsService
from ui.streamlit.components import generate_tts


# ──────────────────────────────────────────────────────────────────────
# "How it works" steps shown on the left pane
# ──────────────────────────────────────────────────────────────────────
_STEPS = [
    {
        "icon": "🗣",
        "title": "Onboarding chat",
        "body": "A 9-question voice conversation in the candidate's own language — captures contact, experience, education, salary expectations.",
        "tint": COLOR_PRIMARY,
    },
    {
        "icon": "📄",
        "title": "Auto-generated resume",
        "body": "An ATS-ready English PDF resume is created from the conversation. Candidate reviews and downloads.",
        "tint": COLOR_ACCENT,
    },
    {
        "icon": "📊",
        "title": "Scored interview",
        "body": "5 role-specific questions with dynamic follow-ups. Recruiter gets a structured scorecard with hire recommendation.",
        "tint": COLOR_SUCCESS,
    },
]


_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_WELCOME_WAV = _PROJECT_ROOT / "assets" / "welcome.wav"


def _load_welcome_audio(tts_service: SarvamTtsService) -> bytes | None:
    """Return the welcome WAV bytes.

    Fast path: read the pre-generated ``assets/welcome.wav`` (instant,
    zero API call). This is the only path used in production demos —
    run ``python tools/regenerate_welcome.py`` once to populate the file.

    Fallback: live Sarvam TTS — only kicks in if the static file is
    missing (first-run before the script has been executed), or has
    been deleted. Logs a warning so the developer notices.
    """
    settings = get_settings()
    cache = st.session_state.setdefault("_tts_cache", {})

    # Fast path — disk read
    if _WELCOME_WAV.exists():
        if "setup_welcome" not in cache:
            cache["setup_welcome"] = _WELCOME_WAV.read_bytes()
        return cache["setup_welcome"]

    # Fallback — live TTS
    audio = cache.get("setup_welcome")
    if audio is not None:
        return audio
    try:
        path = settings.output_dir / TEMP_AUDIO_SUBDIR / "tts_setup_welcome.wav"
        result = tts_service.text_to_speech(
            text=SETUP_WELCOME_TEXT,
            output_path=str(path),
            language_code=SETUP_WELCOME_LANG_CODE,
        )
        cache["setup_welcome"] = result.audio_bytes
        # Tell the developer to run the regeneration script so the next
        # demo isn't subject to this 2-4 s API latency.
        st.info(
            "Welcome audio was generated on the fly. For instant playback "
            "on future page loads, run: `python tools/regenerate_welcome.py`",
            icon="💡",
        )
        return result.audio_bytes
    except Exception as e:
        st.warning(f"Welcome audio unavailable right now: {e}")
        cache["setup_welcome"] = None
        return None


def _render_speaking_chip() -> None:
    """Floating top-right chip confirming voice is playing.

    Pure CSS — fades in, stays for ~8 s, fades out. Auto-dismisses
    without taking up any layout space (position: fixed).
    """
    st.markdown(
        '<div class="speaking-chip">🔊 श्रमसाथी AI is speaking…</div>',
        unsafe_allow_html=True,
    )


def _render_unlock_overlay() -> bool:
    """Hero card shown on the very first visit of a session.

    The card includes a big primary CTA button. Clicking it satisfies
    the browser's "user interaction required before autoplay" policy,
    so the welcome audio (and every subsequent st.audio in the app)
    plays automatically from that point on.

    Returns ``True`` if the user has already unlocked the session and
    the caller should proceed to render the normal setup view.
    """
    if st.session_state.get("welcome_unlocked"):
        return True

    # Centered hero card.
    _, mid, _ = st.columns([1, 3, 1])
    with mid:
        st.markdown(
            """
            <div class="welcome-unlock-card">
                <div class="welcome-unlock-eyebrow">श्रमसाथी AI</div>
                <div class="welcome-unlock-title">
                    Ready to meet your candidate?
                </div>
                <div class="welcome-unlock-sub">
                    Click below to begin — श्रमसाथी AI will introduce itself
                    in Hindi, then we'll set up the interview.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        clicked = st.button(
            "🎙   Click here to begin   →",
            type="primary",
            use_container_width=True,
            key="welcome_unlock_btn",
        )
        if clicked:
            st.session_state.welcome_unlocked = True
            st.rerun()
    return False


def _play_welcome_greeting(tts_service: SarvamTtsService) -> None:
    """Auto-play the welcome audio + show the speaking chip on first load.

    Plays only after the unlock overlay has been clicked (so browser
    autoplay policy is satisfied) and only on the FIRST setup-view
    render of that unlocked state. The audio element itself is hidden
    by global CSS so the recruiter just hears the voice; the chip is
    the visible confirmation.
    """
    audio = _load_welcome_audio(tts_service)
    if not audio:
        return
    already_played = st.session_state.get("setup_welcome_played", False)
    st.audio(audio, format="audio/wav", autoplay=not already_played)
    if not already_played:
        _render_speaking_chip()
    st.session_state.setup_welcome_played = True


def _render_left_pane() -> None:
    """The "how it works in 3 steps" panel — tightened so it doesn't dominate the page."""
    st.markdown(
        f"""
        <div style="
            padding: 16px 16px;
            background: white;
            border-radius: 14px;
            border: 1px solid #E4E4E7;
            box-shadow: 0 1px 3px rgba(24,24,27,0.04);
            height: 100%;
        ">
            <div style="font-size: 0.72rem; font-weight: 600; color: {COLOR_PRIMARY};
                        text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 6px;">
                How it works
            </div>
            <h3 style="margin: 0 0 14px 0; font-size: 1.05rem; color: {COLOR_NEUTRAL_900}; line-height: 1.3;">
                A complete interview, end to end.
            </h3>
        """,
        unsafe_allow_html=True,
    )

    for i, step in enumerate(_STEPS, start=1):
        st.markdown(
            f"""
            <div style="display:flex; gap:10px; margin-bottom: 12px; align-items: flex-start;">
                <div style="
                    width: 32px; height: 32px; border-radius: 9px; flex-shrink: 0;
                    background: {step['tint']}15; color: {step['tint']};
                    display:flex; align-items:center; justify-content:center;
                    font-size: 1.0rem;
                ">{step['icon']}</div>
                <div>
                    <div style="font-weight: 600; color: {COLOR_NEUTRAL_900}; font-size: 0.85rem;">
                        Step {i} — {step['title']}
                    </div>
                    <div style="color: {COLOR_NEUTRAL_500}; font-size: 0.78rem; line-height: 1.4; margin-top: 2px;">
                        {step['body']}
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown(
        f"""
            <div style="
                margin-top: 8px; padding: 10px 12px;
                background: {COLOR_PRIMARY_SOFT}; border-radius: 9px;
                color: {COLOR_NEUTRAL_900}; font-size: 0.78rem; line-height: 1.45;
            ">
                <strong>11 languages</strong> · English, Hindi, Bengali,
                Telugu, Punjabi, Gujarati, Marathi, Tamil, Kannada,
                Malayalam, Odia. Designed for blue-collar candidates
                from villages and small towns.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_right_pane(
    *,
    tts_service: SarvamTtsService,
    health_check_service: HealthCheckService,
) -> None:
    """The form + health-check panel."""
    st.markdown(
        f"""
        <div style="padding: 4px 0 8px 0;">
            <h2 style="margin: 0; font-size: 1.5rem; color: {COLOR_NEUTRAL_900};">
                Start a new interview
            </h2>
            <p style="color: {COLOR_NEUTRAL_500}; margin: 4px 0 0 0; font-size: 0.95rem;">
                Pick a role and language, then enter the candidate's name.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.form("setup_form"):
        role_keys = list(QUESTION_BANK.keys())
        role_titles = [QUESTION_BANK[r]["title"] for r in role_keys]
        role_pick = st.selectbox("Role", role_titles)
        role = role_keys[role_titles.index(role_pick)]

        lang_pick = st.selectbox("Language", list(LANGUAGES.keys()))
        lang, lang_code = LANGUAGES[lang_pick]

        candidate_name = st.text_input(
            "Candidate name",
            placeholder="e.g. Ramesh Babu",
        )

        submitted = st.form_submit_button(
            "Start Profile Building →",
            use_container_width=True,
            type="primary",
        )

    # Pre-demo health check — collapsible so it doesn't dominate.
    with st.expander("System Health Check"):
        st.caption(
            "Probes Sarvam TTS + LLM with tiny payloads to confirm "
            "everything is responsive. Recommended before any live demo."
        )
        if st.button("Run health check", key="run_health_check_btn"):
            with st.spinner("Probing Sarvam APIs…"):
                report = health_check_service.run()
            if report.all_ok:
                st.success("All systems responsive — ready for demo.")
            else:
                st.error("One or more checks failed. See details below.")
            for r in report.results:
                icon = "✅" if r.ok else "❌"
                latency = f"  ({r.latency_s:.1f}s)" if r.latency_s else ""
                st.markdown(
                    f"**{icon}  {r.name}**{latency}  \n"
                    f"<span style='color:#666;'>{r.detail}</span>",
                    unsafe_allow_html=True,
                )

    if submitted:
        if not candidate_name.strip():
            st.error("Please enter the candidate's name.")
            return

        st.session_state.role = role
        st.session_state.lang = lang
        st.session_state.lang_code = lang_code
        st.session_state.candidate_name = candidate_name.strip()
        st.session_state.stage = STAGE_PROFILE_INTRO

        intro_text = PROFILE_INTRO[lang].format(name=candidate_name.strip())
        st.session_state.profile_intro_text = intro_text
        with st.spinner("🔊 Preparing your warm welcome…"):
            st.session_state.profile_intro_audio = generate_tts(intro_text, tts_service)

        greeting_text = OPENING_MESSAGE[lang].format(
            role=QUESTION_BANK[role]["title"]
        )
        st.session_state.greeting_text = greeting_text
        with st.spinner("🔊 Preparing interview greeting…"):
            st.session_state.greeting_audio = generate_tts(greeting_text, tts_service)
        st.rerun()


def render(
    *,
    tts_service: SarvamTtsService,
    health_check_service: HealthCheckService,
) -> None:
    """Two-column setup screen — explainer on the left, form on the right.

    Gated behind a one-click unlock overlay on the very first visit:
    that click satisfies the browser's autoplay policy so the welcome
    audio (hidden bar; only the speaking chip is visible) plays on the
    very next rerun.
    """
    # First-visit gate. Returns False until the recruiter clicks; on
    # that click we rerun and unlock the rest of the setup view.
    if not _render_unlock_overlay():
        return

    _play_welcome_greeting(tts_service)

    # Narrower left pane (was [5, 4] = 55%/45%; now ~37%/63%) so the
    # explainer doesn't dominate the page and the form gets prominence.
    col_left, col_right = st.columns([3, 5], gap="large")
    with col_left:
        _render_left_pane()
    with col_right:
        _render_right_pane(
            tts_service=tts_service,
            health_check_service=health_check_service,
        )
