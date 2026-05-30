"""
profile_view.py — Stage 3: 13-question voice onboarding with voice
confirmation on high-risk fields.

Two phases per high-risk question:
  ASKING     → bot speaks the question, candidate records an answer
  CONFIRMING → bot speaks the LLM-extracted value back, candidate says
               yes/no, bot advances or re-asks

For free-form fields (languages, dependents, education, …) only the
ASKING phase runs — the raw transcript is saved as-is.
"""

from __future__ import annotations

import streamlit as st
from audio_recorder_streamlit import audio_recorder

from constants.app_constants import (
    AUDIO_SAMPLE_RATE,
    HIGH_RISK_FIELDS,
    MIN_REAL_AUDIO_BYTES,
    NO_KEYWORDS,
    PROFILE_CONFIRM_MAX_RETRIES,
    SILENCE_PAUSE_SECONDS,
    STAGE_PROFILE_BUILDING,
    YES_KEYWORDS,
)
from data.profile_questions import (
    CONFIRMATION_PROMPTS,
    PROFILE_QUESTIONS,
    RETRY_PROMPT,
)
from services.profile_extract_service import ProfileExtractService
from services.sarvam_stt_service import SarvamSttService
from services.sarvam_tts_service import SarvamTtsService
from ui.streamlit.components import (
    bot_avatar_url,
    candidate_avatar_url,
    generate_tts,
    profile_prompt,
    render_top_bar,
    render_your_turn_banner,
    transcribe,
    voice_waveform_html,
)
from ui.streamlit.state import reset_interview


# ──────────────────────────────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────────────────────────────
def _format_value_for_speech(field: str, value: str) -> str:
    """Format an extracted value for TTS read-back.

    - mobile: "9876543210"   → "9, 8, 7, 6, 5, 4, 3, 2, 1, 0"
    - email:  "raj@gmail.com" → "r, a, j, at the rate, g, m, a, i, l, dot, c, o, m"
    - others: returned as-is
    """
    if field == "mobile":
        digits = [c for c in value if c.isdigit()]
        return ", ".join(digits) if digits else value
    if field == "email":
        out: list[str] = []
        for c in value:
            if c == "@":
                out.append("at the rate")
            elif c == ".":
                out.append("dot")
            elif c == "-":
                out.append("dash")
            elif c == "_":
                out.append("underscore")
            elif c.isspace():
                continue
            else:
                out.append(c)
        return ", ".join(out) if out else value
    return value


def _classify_yes_no(transcript: str, language: str) -> str | None:
    """Classify the candidate's confirmation utterance.

    Returns "yes", "no", or None (ambiguous). Uses simple lowercased
    substring matching against per-language keyword sets — fast, free,
    and tolerant of STT noise. YES is checked first so a phrase like
    "haan nahi" is treated as yes (rare in practice).
    """
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


def _build_confirmation_script(field: str, value: str, language: str) -> str:
    """Compose the bot's read-back sentence for one field."""
    template = CONFIRMATION_PROMPTS.get(field, {}).get(language) \
        or CONFIRMATION_PROMPTS.get(field, {}).get("en", "You said {value}. Is that correct?")
    speakable = _format_value_for_speech(field, value)
    return template.format(value=speakable)


def _advance_to_next_question(*, accepted_raw: str, accepted_value: str | None,
                              question_text: str, field: str,
                              total: int, tts_service: SarvamTtsService) -> None:
    """Save the answer for the current question and move to the next.

    `accepted_value` is the LLM-extracted clean value (None for
    free-form fields).
    """
    idx = st.session_state.profile_q_idx
    st.session_state.profile_transcripts.append({
        "field": field,
        "question": question_text,
        "answer": accepted_raw,
        "extracted_value": accepted_value,
    })

    # Reset the confirmation sub-FSM
    st.session_state.profile_phase = "asking"
    st.session_state.profile_pending_field = None
    st.session_state.profile_pending_question = ""
    st.session_state.profile_pending_raw = ""
    st.session_state.profile_pending_value = ""
    st.session_state.profile_confirm_audio = None
    st.session_state.profile_confirm_retries = 0

    if idx + 1 >= total:
        st.session_state.stage = STAGE_PROFILE_BUILDING
        return

    st.session_state.profile_q_idx = idx + 1
    next_q_text = profile_prompt(idx + 1)
    with st.spinner("🔊 Preparing next question…"):
        st.session_state.profile_current_audio = generate_tts(next_q_text, tts_service)


def _restart_current_question(tts_service: SarvamTtsService) -> None:
    """Re-ask the current question (on confirmation "no" with retries left)."""
    idx = st.session_state.profile_q_idx

    # Wipe processed-audio hash so the user can record again
    st.session_state.pop(f"profile_processed_{idx}", None)
    st.session_state.pop(f"profile_played_{idx}", None)

    # Clear pending confirmation values
    st.session_state.profile_phase = "asking"
    st.session_state.profile_pending_field = None
    st.session_state.profile_pending_raw = ""
    st.session_state.profile_pending_value = ""
    st.session_state.profile_confirm_audio = None
    # Keep retries counter — it tracks total nos for this question.

    # Re-generate the question's TTS so it autoplays again
    q_text = profile_prompt(idx)
    with st.spinner("🔊 Asking again…"):
        st.session_state.profile_current_audio = generate_tts(q_text, tts_service)


# ──────────────────────────────────────────────────────────────────────
# MAIN VIEW
# ──────────────────────────────────────────────────────────────────────
def render(
    *,
    tts_service: SarvamTtsService,
    stt_service: SarvamSttService,
    extract_service: ProfileExtractService,
) -> None:
    questions = PROFILE_QUESTIONS
    total = len(questions)
    idx = st.session_state.profile_q_idx
    lang = st.session_state.lang

    render_top_bar(
        progress=idx / total,
        badge_text=f"About you — {idx + 1} of {total}",
    )

    # Past Q&A history
    for turn in st.session_state.profile_transcripts:
        with st.chat_message("assistant", avatar=bot_avatar_url()):
            st.markdown(turn["question"])
        with st.chat_message(
            "user",
            avatar=candidate_avatar_url(st.session_state.candidate_name),
        ):
            # Prefer the clean extracted value when present
            shown = turn.get("extracted_value") or turn["answer"] or "_(skipped)_"
            st.markdown(shown)

    # Current question bubble
    current_q_text = profile_prompt(idx)
    current_field = questions[idx]["field"]
    needs_confirmation = current_field in HIGH_RISK_FIELDS
    phase = st.session_state.profile_phase

    with st.chat_message("assistant", avatar=bot_avatar_url()):
        st.markdown(
            "<div style='display:flex; align-items:center; gap:10px;'>"
            "<span class='bot-speaking'>AI Assistant is asking</span>"
            f"{voice_waveform_html('bot')}"
            "</div>",
            unsafe_allow_html=True,
        )
        st.markdown(f"**{current_q_text}**")
        if st.session_state.profile_current_audio:
            play_flag = f"profile_played_{idx}"
            should_autoplay = not st.session_state.get(play_flag, False)
            st.audio(
                st.session_state.profile_current_audio,
                format="audio/wav",
                autoplay=should_autoplay,
            )
            st.session_state[play_flag] = True

    # ── BRANCH: ASKING vs CONFIRMING ────────────────────────────────
    if phase == "asking":
        _render_asking(
            idx=idx,
            total=total,
            current_q_text=current_q_text,
            current_field=current_field,
            needs_confirmation=needs_confirmation,
            lang=lang,
            tts_service=tts_service,
            stt_service=stt_service,
            extract_service=extract_service,
        )
    else:  # phase == "confirming"
        _render_confirming(
            idx=idx,
            total=total,
            lang=lang,
            tts_service=tts_service,
            stt_service=stt_service,
        )

    # Sidebar
    _render_sidebar(idx=idx, total=total)


# ──────────────────────────────────────────────────────────────────────
# PHASE: ASKING — record + (if high-risk) extract + switch to confirming
# ──────────────────────────────────────────────────────────────────────
def _render_asking(
    *,
    idx: int,
    total: int,
    current_q_text: str,
    current_field: str,
    needs_confirmation: bool,
    lang: str,
    tts_service: SarvamTtsService,
    stt_service: SarvamSttService,
    extract_service: ProfileExtractService,
) -> None:
    render_your_turn_banner(SILENCE_PAUSE_SECONDS)

    with st.chat_message(
        "user",
        avatar=candidate_avatar_url(st.session_state.candidate_name),
    ):
        c1, c2, c3 = st.columns([1, 2, 1])
        with c2:
            audio_bytes = audio_recorder(
                text="",
                energy_threshold=(0.01, 0.05),
                pause_threshold=SILENCE_PAUSE_SECONDS,
                sample_rate=AUDIO_SAMPLE_RATE,
                neutral_color="#4f8ef7",
                recording_color="#e74c3c",
                icon_name="microphone",
                icon_size="3x",
                key=f"profile_recorder_{idx}",
            )

        if audio_bytes and len(audio_bytes) >= MIN_REAL_AUDIO_BYTES:
            audio_hash = hash(audio_bytes)
            processed_key = f"profile_processed_{idx}"

            if st.session_state.get(processed_key) != audio_hash:
                st.session_state[processed_key] = audio_hash

                with st.spinner("📝 Transcribing…"):
                    answer = transcribe(audio_bytes, stt_service, file_prefix="profile")
                if answer is None:
                    st.stop()

                clean = (answer or "").strip()
                if not clean:
                    st.session_state[f"profile_empty_{idx}"] = True
                    st.rerun()

                if not needs_confirmation:
                    # Free-form field → save and advance immediately
                    _advance_to_next_question(
                        accepted_raw=clean,
                        accepted_value=None,
                        question_text=current_q_text,
                        field=current_field,
                        total=total,
                        tts_service=tts_service,
                    )
                    st.rerun()

                # High-risk field → extract value, generate confirmation
                # TTS, switch to confirming phase
                with st.spinner("🤔 Understanding your answer…"):
                    extracted = extract_service.extract(
                        field=current_field,
                        raw_answer=clean,
                        language=lang,
                    )

                confirm_script = _build_confirmation_script(
                    current_field, extracted, lang,
                )
                with st.spinner("🔊 Reading it back…"):
                    confirm_audio = generate_tts(confirm_script, tts_service)

                st.session_state.profile_phase = "confirming"
                st.session_state.profile_pending_field = current_field
                st.session_state.profile_pending_question = current_q_text
                st.session_state.profile_pending_raw = clean
                st.session_state.profile_pending_value = extracted
                st.session_state.profile_confirm_audio = confirm_audio
                st.rerun()

    # Empty-capture retry / skip controls
    if st.session_state.get(f"profile_empty_{idx}"):
        st.warning(
            "🎙 I couldn't hear an answer. Please click the mic and speak "
            "clearly, or skip this question if you'd rather not answer."
        )
        col_retry, col_skip = st.columns(2)
        with col_retry:
            if st.button(
                "🔁 Try again",
                use_container_width=True,
                key=f"retry_{idx}",
            ):
                st.session_state.pop(f"profile_empty_{idx}", None)
                st.session_state.pop(f"profile_processed_{idx}", None)
                st.rerun()
        with col_skip:
            if st.button(
                "⏭ Skip this question",
                use_container_width=True,
                key=f"skip_{idx}",
            ):
                st.session_state.pop(f"profile_empty_{idx}", None)
                _advance_to_next_question(
                    accepted_raw="",
                    accepted_value=None,
                    question_text=current_q_text,
                    field=current_field,
                    total=total,
                    tts_service=tts_service,
                )
                st.rerun()


# ──────────────────────────────────────────────────────────────────────
# PHASE: CONFIRMING — bot reads back, candidate says yes/no
# ──────────────────────────────────────────────────────────────────────
def _render_confirming(
    *,
    idx: int,
    total: int,
    lang: str,
    tts_service: SarvamTtsService,
    stt_service: SarvamSttService,
) -> None:
    field = st.session_state.profile_pending_field
    value = st.session_state.profile_pending_value
    question_text = st.session_state.profile_pending_question
    raw = st.session_state.profile_pending_raw
    retries = st.session_state.profile_confirm_retries

    # Bot's confirmation bubble (read-back) — appears below the question
    with st.chat_message("assistant", avatar=bot_avatar_url()):
        st.markdown(
            "<div style='display:flex; align-items:center; gap:10px;'>"
            "<span class='bot-speaking'>Confirming your answer</span>"
            f"{voice_waveform_html('bot')}"
            "</div>",
            unsafe_allow_html=True,
        )
        confirm_script = _build_confirmation_script(field, value, lang)
        st.markdown(f"**{confirm_script}**")
        if st.session_state.profile_confirm_audio:
            play_flag = f"profile_confirm_played_{idx}_{retries}"
            should_autoplay = not st.session_state.get(play_flag, False)
            st.audio(
                st.session_state.profile_confirm_audio,
                format="audio/wav",
                autoplay=should_autoplay,
            )
            st.session_state[play_flag] = True

    render_your_turn_banner(SILENCE_PAUSE_SECONDS)

    # Mic for the yes/no confirmation reply
    with st.chat_message(
        "user",
        avatar=candidate_avatar_url(st.session_state.candidate_name),
    ):
        c1, c2, c3 = st.columns([1, 2, 1])
        with c2:
            audio_bytes = audio_recorder(
                text="",
                energy_threshold=(0.01, 0.05),
                pause_threshold=SILENCE_PAUSE_SECONDS,
                sample_rate=AUDIO_SAMPLE_RATE,
                neutral_color="#10b981",       # green tint to distinguish from main mic
                recording_color="#e74c3c",
                icon_name="microphone",
                icon_size="3x",
                key=f"profile_confirm_recorder_{idx}_{retries}",
            )

        if audio_bytes and len(audio_bytes) >= MIN_REAL_AUDIO_BYTES:
            audio_hash = hash(audio_bytes)
            processed_key = f"profile_confirm_processed_{idx}_{retries}"

            if st.session_state.get(processed_key) != audio_hash:
                st.session_state[processed_key] = audio_hash

                with st.spinner("🤔 Listening…"):
                    yn_transcript = transcribe(
                        audio_bytes, stt_service, file_prefix="profile_confirm",
                    )
                if yn_transcript is None:
                    st.stop()

                decision = _classify_yes_no(yn_transcript, lang)

                if decision == "yes":
                    # Accept — save extracted value and advance.
                    _advance_to_next_question(
                        accepted_raw=raw,
                        accepted_value=value,
                        question_text=question_text,
                        field=field,
                        total=total,
                        tts_service=tts_service,
                    )
                    st.rerun()
                elif decision == "no":
                    if retries + 1 >= PROFILE_CONFIRM_MAX_RETRIES:
                        # Out of retries — accept what we have, recruiter
                        # can fix from the review screen.
                        st.toast(
                            "⚠️ Saving the best we have — you can edit later "
                            "from the review screen.",
                            icon="ℹ️",
                        )
                        _advance_to_next_question(
                            accepted_raw=raw,
                            accepted_value=value,
                            question_text=question_text,
                            field=field,
                            total=total,
                            tts_service=tts_service,
                        )
                        st.rerun()
                    # Retry: play "no problem, let me ask again" then
                    # restart the question.
                    st.session_state.profile_confirm_retries = retries + 1
                    retry_text = RETRY_PROMPT.get(lang, RETRY_PROMPT["en"])
                    with st.spinner("🔊 Let me ask again…"):
                        # Speak the apology + the original question back
                        full_retry = retry_text + " " + question_text
                        st.session_state.profile_current_audio = generate_tts(
                            full_retry, tts_service,
                        )
                    # Reset the question audio play-flag so it autoplays
                    st.session_state.pop(f"profile_played_{idx}", None)
                    st.session_state.pop(f"profile_processed_{idx}", None)
                    st.session_state.profile_phase = "asking"
                    st.session_state.profile_confirm_audio = None
                    st.rerun()
                else:
                    # Ambiguous — gentle prompt + retry button
                    st.warning(
                        "🤔 I couldn't tell if that was yes or no. "
                        "Please click the mic again and clearly say "
                        "‘yes’ or ‘no’ (or ‘haan’ / ‘nahi’)."
                    )
                    st.session_state.pop(processed_key, None)


# ──────────────────────────────────────────────────────────────────────
# SIDEBAR
# ──────────────────────────────────────────────────────────────────────
def _render_sidebar(*, idx: int, total: int) -> None:
    from data.interview_questions import QUESTION_BANK
    role_title = QUESTION_BANK[st.session_state.role]["title"]
    with st.sidebar:
        st.markdown("### 👋 Onboarding")
        st.caption(f"Candidate: **{st.session_state.candidate_name}**")
        st.caption(f"Role: **{role_title}**")
        st.caption(f"Language: **{st.session_state.lang_code}**")
        st.divider()
        st.markdown("**Progress**")
        st.caption(f"Question {idx + 1} / {total}")
        if st.session_state.profile_phase == "confirming":
            st.caption("🎯 Confirming your answer…")
        st.divider()
        if st.button("❌ Abort", use_container_width=True):
            reset_interview()
            st.rerun()
