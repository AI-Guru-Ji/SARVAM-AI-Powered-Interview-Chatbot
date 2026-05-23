"""
profile_builder.py — Turn the candidate's onboarding answers into a
structured profile and a 1-page plain-text resume.

Deterministic — no LLM calls. Every onboarding question maps to a known
field (the order is fixed by data/profile_questions.py), so we read the
candidate's actual answers directly into the corresponding slots. The
resume formatter then displays those answers under English section labels.

Why no LLM:
  - Real interviews where the candidate spoke Hindi had the LLM
    extraction step consistently take 60-80 s and return either an
    empty skeleton or a degenerate repetition loop. Reasoning-model
    behaviour on multi-field translation+extraction was unreliable.
  - The candidate's verbatim answers are MORE useful to a blue-collar
    recruiter in India than an LLM-paraphrased "structured" version.
    Recruiters reading these resumes are bilingual.
  - Zero-latency, never fails, never invents.
"""

from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime

from .sarvam_api import chat_completion


# Question-index → profile-field mapping. Matches the order of
# PROFILE_QUESTIONS in data/profile_questions.py. If the questionnaire
# changes, update this list to match.
_QUESTION_FIELD_ORDER = [
    "contact_info",       # Q1 — full name, mobile, email
    "location_and_age",   # Q2 — age + city/town
    "languages",          # Q3 — languages spoken
    "family",             # Q4 — marital status, dependents
    "experience_years",   # Q5 — years of experience in {role}
    "experience",         # Q6 — past employers + duration
    "education",          # Q7 — qualifications (10th, 12th, ITI, …)
    "salary",             # Q8 — expected + last salary
    "availability",       # Q9 — when can start, willing to relocate
]


# Human-readable labels for each field, shown as section headers in the
# resume. Kept in English (HR-readable) regardless of the candidate's
# interview language.
_FIELD_LABELS = {
    "contact_info":     "Contact Information",
    "location_and_age": "Location & Age",
    "languages":        "Languages Spoken",
    "family":           "Family",
    "experience_years": "Years of Experience",
    "experience":       "Work History",
    "education":        "Education",
    "salary":           "Salary Expectations",
    "availability":     "Availability",
}


# ─────────────────────────────────────────────
# 1. STRUCTURED PROFILE (deterministic, no LLM)
# ─────────────────────────────────────────────
def build_profile_json(
    candidate_name: str,
    role: str,
    language: str,
    qa_pairs: list[tuple[str, str]],
) -> dict:
    """Build a structured candidate profile from the onboarding Q&A.

    Args:
        candidate_name : Already known from the setup form.
        role           : Role key (e.g. "housekeeping").
        language       : Short code (en/hi/bn/te/pa/gu).
        qa_pairs       : List of (question_text, transcribed_answer) tuples
                         in the order PROFILE_QUESTIONS were asked.

    Returns a dict with raw answers grouped by topic.
    """
    answers: dict[str, dict] = {}
    for i, (q, a) in enumerate(qa_pairs):
        if i >= len(_QUESTION_FIELD_ORDER):
            break  # extra questions beyond our schema — ignore
        field = _QUESTION_FIELD_ORDER[i]
        clean = (a or "").strip()
        answers[field] = {
            "question": q,
            "answer": clean if clean else None,
        }

    profile = {
        "name": candidate_name,
        "applied_role": role,
        "language": language,
        "answers": answers,
    }

    # Debug snapshot for observability.
    try:
        debug_dir = Path(__file__).resolve().parent.parent / "output" / "debug"
        debug_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        transcript = "\n".join(
            f"Q: {q}\nA: {a if a and a.strip() else '(no answer)'}"
            for q, a in qa_pairs
        )
        with open(debug_dir / f"profile_build_{ts}.txt", "w", encoding="utf-8") as f:
            f.write("=== INPUT TRANSCRIPT ===\n")
            f.write(transcript)
            f.write("\n\n=== DETERMINISTIC PROFILE (no LLM call) ===\n")
            f.write(json.dumps(profile, ensure_ascii=False, indent=2))
    except Exception as e:
        print(f"[profile_builder] (non-fatal) couldn't write debug file: {e}")

    populated = _count_populated_fields(profile)
    print(
        f"[profile_builder] Built profile with {populated}/"
        f"{len(_QUESTION_FIELD_ORDER)} answers (no LLM call)"
    )
    return profile


def _count_populated_fields(profile: dict) -> int:
    """Count how many onboarding answers the candidate actually gave."""
    answers = profile.get("answers") or {}
    return sum(
        1 for slot in answers.values()
        if slot and slot.get("answer") and str(slot["answer"]).strip()
    )


# ─────────────────────────────────────────────
# 2. PROFESSIONAL ATS-FRIENDLY RESUME (LLM-generated)
# ─────────────────────────────────────────────
# The candidate-facing prompt — exact wording requested by the product
# owner. Treat the LLM as a professional resume writer; it produces a
# real printable resume in English from the raw Hindi/Hinglish transcript.
_RESUME_SYSTEM_PROMPT = """You are a professional resume writer specializing in blue-collar workforce documentation in India. You will receive a raw conversation transcript between an AI interviewer and a job candidate of 7 questions. Carefully analyze every statement, implied skill, and experience mentioned even if stated informally or in Hindi/Hinglish. From this conversation alone, generate a clean, professional, ATS-friendly resume in English. The resume must include: Candidate Name & Contact Placeholder, Professional Summary (3 lines), Work Experience (with estimated durations if mentioned), Education & Certifications, Core Skills & Tools, and Languages Known. Format it as a real, printable resume — not a JSON, not bullet dumps. If any detail is missing, infer intelligently from context. Never fabricate facts not mentioned in the conversation."""


def build_resume_text(profile: dict, language: str = "en") -> str:
    """Generate a professional English resume from the onboarding transcript.

    Uses the LLM to rewrite the candidate's Hindi/Hinglish answers into a
    polished, ATS-friendly English resume with the standard sections
    (Professional Summary, Work Experience, Education, Skills, Languages).

    If the LLM call fails or times out, falls back to the deterministic
    formatter so the recruiter still gets a usable document.

    The `language` argument is accepted for API compatibility but ignored
    (the resume is always English regardless of the interview language).
    """
    # Two LLM attempts (reasoning is non-deterministic; a second call often
    # takes a different path and fits in budget). Falls back to the
    # deterministic Python formatter only if BOTH attempts fail, so the
    # candidate always sees a usable resume on stage.
    for attempt in (1, 2):
        try:
            return _llm_resume_text(profile)
        except Exception as e:
            print(f"[profile_builder] LLM resume attempt {attempt}/2 failed ({e})")
            if attempt < 2:
                print("[profile_builder] Retrying resume generation once...")
    print("[profile_builder] Both LLM attempts exhausted — using deterministic fallback")
    return _deterministic_resume_text(profile)


def _extract_phone_and_email(text: str) -> tuple[str | None, str | None]:
    """Pull a phone number and email address out of a free-form answer.

    Used on the contact_info answer (Q1) so the LLM doesn't have to guess
    — we pass these as explicit context. Returns (None, None) if not
    found; the caller substitutes "[To be filled]" placeholders.
    """
    import re as _re
    if not text:
        return None, None

    # Email: standard pattern (covers most real-world cases).
    email_m = _re.search(
        r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+",
        text,
    )
    email = email_m.group(0) if email_m else None

    # Phone: try to find a 10-digit number (Indian mobile) ignoring
    # spaces, dashes and the country prefix. Candidates may speak digits
    # like "9876543210" or "98765 43210" or "+91 98765 43210".
    cleaned = _re.sub(r"[\s\-()]", "", text)
    phone_m = _re.search(r"(?:\+?91)?(\d{10})", cleaned)
    phone = phone_m.group(1) if phone_m else None
    return phone, email


def _llm_resume_text(profile: dict) -> str:
    """Call sarvam-30b with the professional-writer prompt + transcript."""
    name = profile.get("name") or "Candidate"
    role = (profile.get("applied_role") or "").replace("_", " ")
    answers = profile.get("answers") or {}

    # Number the Q&A pairs in the order they were asked — gives the LLM
    # the question context so it can interpret each answer correctly.
    transcript_lines: list[str] = []
    for i, field in enumerate(_QUESTION_FIELD_ORDER, start=1):
        slot = answers.get(field) or {}
        q = slot.get("question") or ""
        a = slot.get("answer") or "(no answer)"
        transcript_lines.append(f"Q{i} ({field}): {q}")
        transcript_lines.append(f"A{i}: {a}")
    transcript = "\n".join(transcript_lines)

    # Q1 asked for phone + email. Extract them deterministically in Python
    # so the LLM doesn't have to parse digits / email out of a free-form
    # spoken answer (it often missed them and fell back to the placeholder).
    contact_answer = (answers.get("contact_info") or {}).get("answer") or ""
    phone, email = _extract_phone_and_email(contact_answer)
    phone_line = f"Phone: {phone}" if phone else "Phone: [To be filled]"
    email_line = f"Email: {email}" if email else "Email: [To be filled]"

    user_message = (
        f"Candidate name: {name}  (use this name VERBATIM as the header — do not change it, translate it, or replace it with another name)\n"
        f"Role applied for: {role}\n\n"
        f"Conversation transcript:\n{transcript}\n\n"
        f"Contact details extracted from Q1 (use these EXACTLY — copy verbatim):\n"
        f"  {phone_line}\n"
        f"  {email_line}\n\n"
        f"IMPORTANT WRITING RULES — follow strictly:\n"
        f"1. Output ENGLISH only. The candidate spoke Hindi, but the resume must be 100% English. Do NOT include any Hindi/Devanagari characters.\n"
        f"2. Use the exact candidate name '{name}' — do NOT invent or substitute a different name.\n"
        f"3. Plain text only — NO markdown. Do not use #, ##, ###, **, __, or asterisk bullets. Use ALL-CAPS section headers and '-' bullets.\n"
        f"4. Under the candidate name, write the two contact lines EXACTLY as shown above ('{phone_line}' and '{email_line}'). Do not invent or replace these values.\n"
        f"5. Translate every Hindi term to English (e.g. होटल → hotel, हाउसकीपिंग → housekeeping, गोरखपुर → Gorakhpur).\n\n"
        f"Now write the resume in English."
    )

    raw = chat_completion(
        messages=[{"role": "user", "content": user_message}],
        system_prompt=_RESUME_SYSTEM_PROMPT,
        temperature=0.4,
    )

    # Save to debug dir so we can see what the LLM produced even if it
    # later looks off in the UI.
    try:
        debug_dir = Path(__file__).resolve().parent.parent / "output" / "debug"
        debug_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        with open(debug_dir / f"resume_llm_{ts}.txt", "w", encoding="utf-8") as f:
            f.write("=== TRANSCRIPT SENT TO LLM ===\n")
            f.write(transcript)
            f.write("\n\n=== RAW LLM RESUME ===\n")
            f.write(raw or "(empty)")
    except Exception:
        pass

    # Strip code fences if the model wraps the resume in them.
    text = (raw or "").strip()
    if text.startswith("```"):
        ls = text.splitlines()[1:]
        if ls and ls[-1].strip().startswith("```"):
            ls = ls[:-1]
        text = "\n".join(ls).strip()
    if not text:
        raise RuntimeError("LLM returned empty resume")
    return text


def _deterministic_resume_text(profile: dict) -> str:
    """Fallback resume — used only when the LLM call fails.

    Section labels are English; candidate answers are shown verbatim
    (no translation, no rewriting). Instant, never fails.
    """
    name = profile.get("name") or "Candidate"
    role = profile.get("applied_role") or "—"
    answers = profile.get("answers") or {}

    lines: list[str] = []
    lines.append(str(name).upper())
    lines.append(f"Applied for: {role.replace('_', ' ').title()}")
    lines.append("")
    lines.append("OBJECTIVE")
    lines.append(f"  Seeking a {role.replace('_', ' ')} role.")
    lines.append("")

    for field in _QUESTION_FIELD_ORDER:
        slot = answers.get(field) or {}
        ans = slot.get("answer")
        if not ans or not str(ans).strip():
            continue
        label = _FIELD_LABELS.get(field, field.replace("_", " ").title())
        lines.append(label.upper())
        for chunk in _wrap_line(str(ans).strip(), width=78):
            lines.append(f"  {chunk}")
        lines.append("")

    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines)


def _wrap_line(text: str, width: int = 78) -> list[str]:
    """Wrap a single line at word boundaries, preserving Unicode words.

    Avoids breaking inside Hindi/Bengali/Telugu words by splitting on
    spaces only. Lines that have no spaces (rare for spoken answers)
    are returned as-is rather than mid-word truncated.
    """
    words = text.split(" ")
    if not words:
        return [text]
    out: list[str] = []
    current = ""
    for w in words:
        if not current:
            current = w
        elif len(current) + 1 + len(w) <= width:
            current += " " + w
        else:
            out.append(current)
            current = w
    if current:
        out.append(current)
    return out


# ─────────────────────────────────────────────
# 3. RESUME → PDF
# ─────────────────────────────────────────────
# Section titles that should be rendered as accent-coloured headers in
# the PDF (matches the UI card colours in streamlit_app.py).
_PDF_SECTION_COLOURS = {
    "professional summary":         (79, 142, 247),    # blue
    "summary":                      (79, 142, 247),
    "work experience":              (46, 204, 113),    # green
    "experience":                   (46, 204, 113),
    "education & certifications":   (155, 89, 182),    # purple
    "education and certifications": (155, 89, 182),
    "education":                    (155, 89, 182),
    "core skills & tools":          (230, 126, 34),    # orange
    "skills & tools":               (230, 126, 34),
    "skills and tools":             (230, 126, 34),
    "core skills":                  (230, 126, 34),
    "skills":                       (230, 126, 34),
    "languages known":              (22, 160, 133),    # teal
    "languages":                    (22, 160, 133),
    "objective":                    (79, 142, 247),
}


def build_resume_pdf(resume_text: str, candidate_name: str = "Candidate") -> bytes:
    """Render the resume text as a PDF and return the raw bytes.

    Section headers (Professional Summary, Work Experience, …) are styled
    in the same accent colours used by the on-screen cards. The header
    band (name + contact placeholders) gets the blue/purple gradient look
    in flat colour form.

    Returns the PDF as bytes so the caller can pass straight to
    st.download_button without touching disk.
    """
    from fpdf import FPDF  # local import: keeps module import cheap

    pdf = FPDF(format="A4", unit="mm")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_margins(left=18, top=15, right=18)

    # ── Header band (name + contact) ─────────────────────────────────────
    lines = resume_text.splitlines()
    header_lines: list[str] = []
    body_start = 0
    for i, raw in enumerate(lines):
        norm = raw.strip().rstrip(":").strip().lower()
        if norm in _PDF_SECTION_COLOURS:
            body_start = i
            break
        if raw.strip():
            header_lines.append(raw.strip())
    else:
        body_start = len(lines)

    if not header_lines:
        header_lines = [candidate_name]
    name = header_lines[0]
    contact = header_lines[1:]

    # Coloured header rectangle
    pdf.set_fill_color(79, 142, 247)
    pdf.rect(x=0, y=0, w=210, h=32, style="F")
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 22)
    pdf.set_xy(18, 9)
    pdf.cell(0, 9, _ascii_safe(name), ln=1)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_xy(18, 19)
    pdf.cell(0, 5, _ascii_safe(" | ".join(contact)) if contact else "", ln=1)
    pdf.set_y(40)
    pdf.set_text_color(0, 0, 0)

    # ── Body sections ────────────────────────────────────────────────────
    # Effective writable width inside the page margins.
    BODY_W = 210 - 18 - 18  # A4 width minus left/right margins (mm)
    current_colour: tuple[int, int, int] | None = None
    for raw in lines[body_start:]:
        stripped = raw.strip()
        norm = stripped.rstrip(":").strip().lower()

        # Reset x to left margin before every body operation so the
        # cursor never drifts past the right edge (which makes fpdf
        # raise "Not enough horizontal space").
        pdf.set_x(18)

        if norm in _PDF_SECTION_COLOURS:
            current_colour = _PDF_SECTION_COLOURS[norm]
            pdf.ln(4)
            pdf.set_x(18)
            pdf.set_font("Helvetica", "B", 12)
            pdf.set_text_color(*current_colour)
            pdf.multi_cell(BODY_W, 7, _ascii_safe(stripped.rstrip(":").upper()))
            # Coloured underline rule
            y = pdf.get_y()
            pdf.set_draw_color(*current_colour)
            pdf.set_line_width(0.6)
            pdf.line(18, y, 192, y)
            pdf.ln(2)
            pdf.set_text_color(0, 0, 0)
            continue

        if not stripped:
            pdf.ln(2)
            continue

        # Body line — bullet or paragraph. Single multi_cell with an
        # explicit width so fpdf can never get confused about remaining
        # space.
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(0, 0, 0)
        if stripped.startswith(("-", "•", "*")):
            text = stripped.lstrip("-•* ").strip()
            pdf.multi_cell(BODY_W, 5, _ascii_safe(f"  - {text}"))
        else:
            pdf.multi_cell(BODY_W, 5, _ascii_safe(stripped))

    raw = pdf.output(dest="S")
    return bytes(raw) if not isinstance(raw, bytes) else raw


def _ascii_safe(text: str) -> str:
    """Helvetica (the built-in PDF font) only supports Latin-1.

    The LLM is asked to write in English, so the resume is mostly safe.
    Any stray non-Latin-1 chars (e.g. an em-dash, fancy quotes, or a
    leftover Devanagari character) get replaced with a Latin-1
    equivalent so fpdf doesn't raise.
    """
    replacements = {
        "—": "-", "–": "-",
        "“": '"', "”": '"', "‘": "'", "’": "'",
        "•": "*", "₹": "INR ", "₨": "INR ",
    }
    for src, dst in replacements.items():
        text = text.replace(src, dst)
    return text.encode("latin-1", errors="replace").decode("latin-1")


# ─────────────────────────────────────────────
# 4. ONE-SHOT WRAPPER (kept for API compatibility)
# ─────────────────────────────────────────────
def build_profile(
    candidate_name: str,
    role: str,
    language: str,
    qa_pairs: list[tuple[str, str]],
) -> tuple[dict, str]:
    """Build BOTH the JSON profile and the resume text in one call.

    Returns (profile_dict, resume_text).
    """
    profile = build_profile_json(candidate_name, role, language, qa_pairs)
    resume = build_resume_text(profile, language=language)
    return profile, resume
