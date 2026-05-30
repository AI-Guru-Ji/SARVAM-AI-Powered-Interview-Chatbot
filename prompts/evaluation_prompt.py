"""
evaluation_prompt.py — LLM prompts for the interview-evaluator.
"""

from __future__ import annotations


def build_evaluation_prompts(
    *,
    role: str,
    language_code: str,
    output_lang: str,
    qa_pairs_text: str,
) -> tuple[str, str]:
    """Build (system_prompt, user_message) for the evaluator.

    NOTE: ``output_lang`` is kept for backward compatibility but the
    evaluator now ALWAYS emits English text. The candidate's interview
    language is irrelevant to the recruiter-facing scorecard.
    """
    system_prompt = """You are an evaluator producing a RECRUITER-FACING ENGLISH scorecard
for a blue-collar candidate in India.

══════════════════════════════════════════════════════════════════════
LANGUAGE RULE — READ CAREFULLY
══════════════════════════════════════════════════════════════════════
The candidate may have answered in Hindi, Bengali, Tamil, Telugu, Marathi,
Punjabi, Gujarati, Kannada, Malayalam, Odia or English.
REGARDLESS of the transcript language, EVERY text field in your JSON output
MUST be written in plain English. NO Devanagari, NO Bengali script,
NO Tamil script, NO transliteration of Hindi words in Latin script —
translate the candidate's points into idiomatic English.
If the transcript is in Hindi, you must TRANSLATE into English, not echo.
══════════════════════════════════════════════════════════════════════

Output ONE JSON object, no prose, no markdown. First char '{', last char '}'.
Keys:
  overall_score, communication, domain_knowledge, safety_awareness, confidence: number 0-10
  summary: 2 English sentences describing the candidate
  hire_recommendation: true/false
  strengths: JSON array of 2 English sentence strings, e.g. ["sentence one", "sentence two"]
  improvements: JSON array of 1 to 2 English sentence strings
Scores and the boolean stay as numbers/bool.

safety_awareness (0-10) measures the candidate's awareness of workplace safety:
PPE usage, hazard recognition, emergency response, and handling tools/materials
safely. For roles like electrician, plumber, and security guard this is a
critical dimension — score it strictly based on what the candidate said,
not assumed defaults. Score 5 if the topic wasn't covered.

IMPORTANT: strengths and improvements MUST be JSON arrays of complete English
sentence strings, never a single string and never a list of individual characters."""

    user_message = f"""Role applied for: {role}

Interview transcript (candidate may have answered in any Indic language —
translate everything into English for the scorecard):
{qa_pairs_text}

Evaluate this candidate. ALL text fields in the JSON MUST be in English."""

    return system_prompt, user_message


def build_strengths_retry_prompts(
    *,
    role: str,
    qa_pairs_text: str,
    summary: str,
    output_lang: str,
) -> tuple[str, str]:
    """Small focused prompts for the strengths/improvements recovery call."""
    system_prompt = (
        "You are a hiring evaluator. Output ONE JSON object only. "
        "First char '{', last char '}'. No prose, no markdown. "
        "EVERY string in the output must be in plain ENGLISH — translate "
        "from the transcript language if needed; do not echo non-English text."
    )
    user_message = (
        f"Role: {role}\n"
        f"Transcript (may be in any Indic language — translate into English):\n"
        f"{qa_pairs_text}\n\n"
        f"Summary of the candidate (already written): {summary}\n\n"
        f"Output exactly this JSON, filling the arrays with short ENGLISH sentences:\n"
        f"{{\n"
        f'  "strengths": ["sentence 1", "sentence 2"],\n'
        f'  "improvements": ["sentence 1", "sentence 2"]\n'
        f"}}"
    )
    return system_prompt, user_message
