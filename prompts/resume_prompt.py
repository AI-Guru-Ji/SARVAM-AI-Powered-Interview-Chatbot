"""
resume_prompt.py — LLM prompts for the resume-writer.

The resume is ALWAYS generated in English (ATS-friendly), regardless of
the language the candidate spoke during onboarding. The prompts are
language-aware so the model gets accurate guidance about which script
to forbid and what kind of vocabulary to translate.

Design notes:
- The system prompt gives the model a literal TEMPLATE to fill in, not
  a numbered enumeration of sections. Numbered enumerations were
  causing sarvam-30b to either (a) print the enumeration as text in the
  output, or (b) duplicate the whole resume body — both observed bugs.
- The system prompt ends with an explicit "STOP" instruction to prevent
  the model from writing the resume twice.
- Email is intentionally NOT shown in the output — we no longer collect
  email during the voice interview (recruiters capture it via WhatsApp/
  SMS after the call).
"""

from __future__ import annotations

from constants.app_constants import (
    LANGUAGE_NAMES,
    SCRIPT_NAMES,
    TRANSLATION_EXAMPLES,
)


# Plain-text template — gives the model a literal shape to fill in.
# Each `<<...>>` placeholder is something the model should replace with
# real content. The model should output this same shape, with the
# placeholders replaced — and NOTHING ELSE before or after.
_RESUME_TEMPLATE = """\
<<NAME>>
<<PHONE_LINE>>

PROFESSIONAL SUMMARY
<<3 short lines summarising the candidate's background and goal>>

WORK EXPERIENCE
<<one entry per past job, in the form: EMPLOYER NAME, City | duration>>
<<one line of detail per job if relevant>>

EDUCATION & CERTIFICATIONS
<<each qualification on its own line: 'Qualification, Institution'>>

CORE SKILLS & TOOLS
- <<skill 1>>
- <<skill 2>>
- <<skill 3>>
- <<more skills as relevant>>

LANGUAGES KNOWN
<<comma-separated list, e.g. 'Hindi, English'>>
"""


RESUME_SYSTEM_PROMPT = (
    "You are a professional resume writer for blue-collar workforce in "
    "India. You will receive a voice-interview transcript (the candidate "
    "may have spoken in any Indian language) and you must produce a "
    "clean, professional, ATS-friendly resume in ENGLISH.\n\n"
    "OUTPUT FORMAT — fill in this template exactly once, with NO "
    "explanatory text before or after, and NO duplication of sections. "
    "After you finish the LANGUAGES KNOWN section, STOP. Do not repeat, "
    "do not re-list, do not add a second copy.\n\n"
    "TEMPLATE TO FILL IN:\n"
    f"```\n{_RESUME_TEMPLATE}```\n\n"
    "RULES:\n"
    "- First line is ONLY the candidate's name — no header above it.\n"
    "- Second line is the phone contact line — copy verbatim.\n"
    "- Use ALL-CAPS exactly for the section headers shown in the "
    "template (PROFESSIONAL SUMMARY, WORK EXPERIENCE, "
    "EDUCATION & CERTIFICATIONS, CORE SKILLS & TOOLS, LANGUAGES KNOWN).\n"
    "- NEVER include the words 'placeholder', 'header', 'section', or "
    "phrases like 'CANDIDATE NAME' or 'CONTACT INFORMATION'.\n"
    "- NEVER print an email address. Email is collected out-of-band.\n"
    "- Plain text only — NO markdown (#, **, *, ##, etc.). Bullets use "
    "the hyphen '-' character.\n"
    "- If a detail is missing, infer reasonably from context (e.g. for "
    "a candidate applying as Electrician, common tools they didn't "
    "explicitly name can still appear in CORE SKILLS & TOOLS). Never "
    "fabricate employers, dates, or qualifications.\n"
    "- After 'LANGUAGES KNOWN' content, STOP. The resume ends there."
)


def build_resume_user_message(
    *,
    name: str,
    role: str,
    language: str,
    transcript: str,
    phone_line: str,
) -> str:
    """Build the user-side message for the resume generation call.

    Args:
        name:        Candidate's full name. Used verbatim as the resume header.
        role:        Human-readable role (e.g. "Housekeeping").
        language:    Short code of the language the candidate spoke
                     (en / hi / bn / te / pa / gu / kn / ml / mr / od / ta).
        transcript:  Numbered Q&A pairs from the onboarding chat.
        phone_line:  "Phone: 9876543210" or "Phone: [To be filled]".

    Returns:
        The fully composed user message to pass into chat_completion.
    """
    lang_name = LANGUAGE_NAMES.get(language, "an Indian language")
    script_name = SCRIPT_NAMES.get(language, "the native script")
    examples = TRANSLATION_EXAMPLES.get(language, "")
    examples_clause = f"  {examples}\n" if examples else ""

    return (
        f"Candidate name (use VERBATIM as the very first line): {name}\n"
        f"Phone line (use VERBATIM as the second line): {phone_line}\n"
        f"Role applied for: {role}\n"
        f"Language spoken during onboarding: {lang_name}\n\n"
        f"Transcript of the onboarding conversation:\n{transcript}\n\n"
        f"LANGUAGE RULES:\n"
        f"  Output 100% English. Do NOT include any {lang_name} or "
        f"{script_name}-script characters anywhere in the resume. "
        f"Translate every {lang_name} term to clean English.\n"
        f"{examples_clause}"
        f"For Indic place names, use the standard English spelling "
        f"(e.g. 'Lucknow', 'Chennai', 'Bengaluru').\n\n"
        f"Now produce the resume by filling in the TEMPLATE shown in the "
        f"system prompt. Write each section exactly ONCE. Stop after "
        f"LANGUAGES KNOWN."
    )
