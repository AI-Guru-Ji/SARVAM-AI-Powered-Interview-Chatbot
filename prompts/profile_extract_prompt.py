"""
profile_extract_prompt.py — Prompt for extracting a single normalized
field value from a free-form STT transcript.

Used during profile-building voice confirmation. The candidate's raw
speech ("mera naam Rajesh Kumar hai aur main Mumbai se hoon") is
transcribed by Saaras v3 and then this prompt asks sarvam-30b to pull
out exactly one field (e.g. just "Rajesh Kumar").
"""

from __future__ import annotations


# ──────────────────────────────────────────────────────────────────────
# Per-field extraction instructions. Keep these short and uncompromising
# — the model should output the VALUE ONLY, no preamble, no JSON, no
# explanation.
# ──────────────────────────────────────────────────────────────────────
_FIELD_RULES: dict[str, str] = {
    "name": (
        "Extract the candidate's FULL NAME from their answer.\n"
        "- Output only the name in clean Title Case (e.g. 'Rajesh Kumar').\n"
        "- Do NOT include 'Mera naam', 'My name is', or any verb.\n"
        "- If the answer contains multiple names, return the candidate's own name."
    ),
    "mobile": (
        "Extract the 10-digit mobile number from the answer.\n"
        "- Output ONLY the digits 0-9, with NO spaces, NO dashes, NO '+91'.\n"
        "- Convert spoken digit-words to digits in ANY language:\n"
        "    Hindi:    'आठ सात नौ पाँच' → '8795', 'एक' → '1'\n"
        "    Tamil:    'ஒன்று இரண்டு' → '12'\n"
        "    Bengali:  'এক দুই তিন' → '123'\n"
        "    English:  'eight seven nine' → '879'\n"
        "- If you find a 12-digit '91xxxxxxxxxx' number, drop the leading '91'.\n"
        "- If you cannot find 10 clean digits, output a single hyphen '-' so the system can use its fallback."
    ),
    "age": (
        "Extract the candidate's AGE in years as a single integer (10 to 99).\n"
        "- Output ONLY the number as a digit (e.g. '25'). No 'years', no extra text.\n"
        "- Convert spoken numbers to digits in any language:\n"
        "    'twenty five' → '25', 'pacchees' → '25', 'पैंतालीस' → '45'."
    ),
    "location": (
        "Extract the city or town the candidate currently lives in.\n"
        "- Output ONLY the place name, transliterated to its standard "
        "English/Roman spelling (e.g. 'Lucknow', 'Chennai', 'Bengaluru', "
        "'Bhubaneswar', 'New Delhi').\n"
        "- STRICTLY do NOT output a full sentence. Do NOT include verbs like "
        "'I live in', 'main rehta hoon', 'में रहता हूँ', 'ൽ താമസിക്കുന്നു'.\n"
        "- Examples of correct output:\n"
        "    Input: 'मैं लखनऊ में रहता हूँ' → Output: 'Lucknow'\n"
        "    Input: 'நான் சென்னையில் இருக்கிறேன்' → Output: 'Chennai'\n"
        "    Input: 'I am from Hyderabad' → Output: 'Hyderabad'\n"
        "- If the candidate names a state/area alongside, include it: "
        "'Lucknow, Uttar Pradesh'. Keep it short (under 35 characters)."
    ),
}


def build_profile_extract_prompts(
    *,
    field: str,
    raw_answer: str,
    lang_name: str,
) -> tuple[str, str]:
    """Build (system_prompt, user_message) for one field-extraction call.

    Args:
        field:      One of HIGH_RISK_FIELDS — name / mobile / email / age / location.
        raw_answer: The verbatim STT transcript in the candidate's language.
        lang_name:  Human-readable language name ("Hindi", "Bengali", …) —
                    used only to help the model parse code-mixed input.

    Returns:
        A (system, user) pair the LLM service expects.
    """
    rule = _FIELD_RULES.get(field, "Extract the value the candidate provided.")

    system_prompt = (
        "You are a precise data extractor. Your only job is to pull one "
        f"specific value from a candidate's spoken answer (transcribed from {lang_name}).\n\n"
        f"{rule}\n\n"
        "Output the value and NOTHING ELSE — no quotation marks, no preamble, "
        "no 'The name is', no JSON, no markdown. If you cannot find the value, "
        "respond with a single hyphen '-'."
    )

    user_message = f"Candidate's answer:\n{raw_answer}\n\nExtract the {field}:"

    return system_prompt, user_message
