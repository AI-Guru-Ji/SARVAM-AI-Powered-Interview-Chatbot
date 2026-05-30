"""
profile_enrich_prompt.py — Prompt for structured-extraction of skills +
work-history + English summary labels from the profile-building transcript.

Used at the profile_building stage. The candidate's free-form answers
(in any of the 11 supported languages) are parsed into:
  - `skills` array (short English noun phrases for chip rendering)
  - `work_history` array (structured past-job cards)
  - `education_en`, `salary_en`, `availability_en`, `marital_status_en`,
    `dependents_en` — short English labels for the recruiter dashboard

Always outputs ENGLISH regardless of the candidate's language, because
the dashboard is recruiter-facing and ATS-friendly.
"""

from __future__ import annotations


# Per-role skill seed lists. Helps the model produce non-empty chips
# even when the transcript is sparse — these are common blue-collar
# skills the model should consider inferring from context. NOT meant
# to be copy-pasted verbatim — only as guidance.
_ROLE_SKILL_SEEDS: dict[str, str] = {
    "electrician": (
        "AC/DC wiring, MCB & fuse box, circuit breakers, conduit fitting, "
        "earthing & bonding, multimeter use, panel board work, inverter "
        "installation, CCTV wiring, switchgear, cable laying, voltage "
        "testing, safety PPE, live-wire safety procedures"
    ),
    "plumber": (
        "PVC / CPVC / GI pipe fitting, leak detection, drain cleaning, "
        "valves & faucets, sewage blockage clearing, water pressure "
        "diagnostics, threading, soldering & brazing, fixture installation, "
        "pipe insulation, plumbing tools (wrench, plunger, snake, etc.)"
    ),
    "housekeeping": (
        "deep cleaning, hotel-floor cleaning, bathroom sanitization, "
        "vacuuming, mopping, dusting, laundry handling, bed-making, "
        "chemical safety (bleach / detergents / disinfectants), waste "
        "disposal, guest-room standards, hospitality protocols"
    ),
    "security_guard": (
        "patrolling, access control, CCTV monitoring, visitor management, "
        "incident reporting, emergency response, fire-safety awareness, "
        "first aid, night-shift alertness, two-way radio use, crowd control, "
        "report writing"
    ),
}


def build_profile_enrich_prompts(
    *,
    role: str,
    role_key: str,
    transcript: str,
    candidate_lang_name: str,
) -> tuple[str, str]:
    """Build (system_prompt, user_message) for the profile enrichment call.

    Args:
        role:                Human-readable role (e.g. "Electrician").
        role_key:            Internal role key — "electrician", "plumber",
                             "housekeeping", "security_guard". Used to look
                             up the seed-skill list.
        transcript:          Numbered Q&A pairs from the profile-building chat.
        candidate_lang_name: e.g. "Hindi", "Punjabi", "Tamil" — used so the
                             LLM knows what language the transcript is in.

    Returns:
        (system, user) pair the LLM service expects.
    """
    seed = _ROLE_SKILL_SEEDS.get(role_key, "")
    seed_clause = (
        f"\n\nFor a {role} role, common relevant skills include: "
        f"{seed}. Consider these when extracting — but ONLY include a "
        f"skill in the output if the transcript actually mentions or "
        f"clearly implies it. Never invent skills not in the transcript."
    ) if seed else ""

    system_prompt = (
        "You are a precise structured-data extractor for blue-collar job "
        "candidates in India. From a voice-interview transcript (which may "
        f"be in {candidate_lang_name} or a mix of languages), extract the "
        "following into JSON:\n"
        "  - a list of skills/tools\n"
        "  - a list of past jobs\n"
        "  - short English summary labels for education, salary, "
        "availability, marital status, and dependents\n\n"
        "OUTPUT RULES:\n"
        "- Output ONE JSON object, nothing else. First char '{', last char '}'.\n"
        "- All output text is in ENGLISH only — translate from the "
        "candidate's language as needed.\n"
        "- Use empty string '' or empty list [] when a field can't be filled.\n"
        "- Do NOT invent facts that aren't in the transcript.\n\n"
        "FIELD GUIDANCE:\n"
        "- skills: short noun phrases recruiters scan. Tools, materials, "
        "machinery, techniques, safety knowledge. 5-10 chips ideal. Never "
        "duplicate. Order by relevance to the role."
        f"{seed_clause}\n"
        "- work_history: only include jobs the candidate clearly mentioned. "
        "Empty list is fine if they have no prior work. For each job: "
        '{"title": "...", "employer": "...", "dates": "...", "duration": "..."}\n'
        "    - 'duration' is a short label like '3 yrs' or '6 months'.\n"
        "    - 'dates' is like 'Jan 2021 - Present' or empty string.\n"
        "- education_en: ONE compact English label, e.g. '12th Pass · ITI "
        "Electrician', '10th Pass', 'B.A. · Lucknow University'. Strip "
        "verbose phrasing.\n"
        "- salary_en: ONE compact label with the ₹ symbol if applicable, "
        "e.g. '₹15,000 / month expected (last: ₹12,000)' or "
        "'₹40,000 expected'. Use 'Not stated' if missing.\n"
        "- availability_en: ONE compact label, e.g. 'Available immediately "
        "· Full time' or 'Available next month · Open to relocation'.\n"
        "- marital_status_en: exactly one of 'Married', 'Single', or "
        "'Prefer not to say'.\n"
        "- dependents_en: short English phrase, e.g. '2 children · supports "
        "parents' or 'No dependents'. Use empty string if not mentioned.\n\n"
        "SCHEMA (output exactly this shape):\n"
        "{\n"
        '  "skills": ["string", ...],\n'
        '  "work_history": [\n'
        '    {"title": "...", "employer": "...", "dates": "...", "duration": "..."}\n'
        "  ],\n"
        '  "education_en": "...",\n'
        '  "salary_en": "...",\n'
        '  "availability_en": "...",\n'
        '  "marital_status_en": "...",\n'
        '  "dependents_en": "..."\n'
        "}"
    )

    user_message = (
        f"Role applied for: {role}\n\n"
        f"Profile-building transcript:\n{transcript}\n\n"
        f"Extract skills, work history, and the English summary labels "
        f"into the JSON object above."
    )

    return system_prompt, user_message
