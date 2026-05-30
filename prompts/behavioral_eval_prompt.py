"""
behavioral_eval_prompt.py — LLM prompts for the behavioral / personality
scorecard (the "Trust Profile" feature).

Scores 5 traits 0-10 from the candidate's transcript of 5 scenario
questions. Always outputs English regardless of interview language —
the dashboard is recruiter-facing.

Prompt design rule learned the hard way: Sarvam-30b loves to "think
out loud" before producing JSON. If the rubric is verbose and comes
before the output schema, the model writes a long markdown analysis
that exhausts ``max_tokens`` before any JSON is emitted, and the
regex recovery has nothing to extract. This file therefore:
  1. Puts "OUTPUT JSON ONLY, NO PROSE" as the FIRST line.
  2. Shows the JSON template with <placeholders> the model fills in.
  3. Keeps the rubric to a single concise line per trait.
  4. Repeats the "no prose" rule at the END of the user message.
"""

from __future__ import annotations


def build_behavioral_eval_prompts(
    *,
    role: str,
    candidate_lang_name: str,
    qa_pairs_text: str,
) -> tuple[str, str]:
    """Build (system_prompt, user_message) for the behavioral eval call.

    Args:
        role:                Human-readable role (e.g. "Security Guard").
        candidate_lang_name: Language the candidate spoke ("Hindi", etc.).
        qa_pairs_text:       Numbered Q&A pairs from the 5 behavioral Qs.
    """
    system_prompt = (
        "Output ONE JSON object ONLY. NO prose, NO analysis, NO markdown, "
        "NO 'thinking', NO commentary. Your entire response must start "
        "with '{' and end with '}'. Anything else breaks downstream parsing.\n\n"
        "TASK: Score a blue-collar candidate on 5 personality traits (0-10 each) "
        f"from their 5 scenario answers (transcript may be in {candidate_lang_name}).\n\n"
        "FILL THIS JSON TEMPLATE — replace each <...> placeholder:\n"
        "{\n"
        '  "honesty": <integer 0-10>,\n'
        '  "reliability": <integer 0-10>,\n'
        '  "stress_tolerance": <integer 0-10>,\n'
        '  "customer_orientation": <integer 0-10>,\n'
        '  "earning_attitude": <integer 0-10>,\n'
        '  "overall_summary": "<2 English sentences about the candidate>",\n'
        '  "per_trait_reasoning": {\n'
        '    "honesty": "<1 short English sentence quoting evidence from Q1>",\n'
        '    "reliability": "<1 sentence from Q2>",\n'
        '    "stress_tolerance": "<1 sentence from Q3>",\n'
        '    "customer_orientation": "<1 sentence from Q4>",\n'
        '    "earning_attitude": "<1 sentence from Q5>"\n'
        "  },\n"
        '  "answer_specificity": <integer 0-10>,\n'
        '  "cross_question_consistency": "<high|medium|low>"\n'
        "}\n\n"
        "SCORING GUIDE (one line per trait — apply strictly):\n"
        "- honesty: returns found money / admits faults. 0=keeps it, 5=hedges, 10=immediate return.\n"
        "- reliability: stays loyal vs jumps for small raise. 0=jumps immediately, 5=wavers, 10=stays thoughtfully.\n"
        "- stress_tolerance: clear story of handling adversity. 0=blames, 5=vague, 10=owned + learned.\n"
        "- customer_orientation: de-escalates angry customers. 0=argues back, 5=defends self, 10=listens + empathises.\n"
        "- earning_attitude: balance of money + growth. 0=money-only, 5=one-sided, 10=articulates both.\n"
        "- answer_specificity: overall concreteness. 0=vague generics, 10=specific names/numbers/steps.\n"
        "- cross_question_consistency: do the 5 answers paint a coherent character? high/medium/low.\n\n"
        "RULES:\n"
        "1. ALL output text in ENGLISH. Translate Hindi/Indic transcript as you read.\n"
        "2. Evidence-based — quote one concrete thing the candidate said in each reasoning line.\n"
        "3. NO preamble. NO 'Here is the JSON:'. NO ```json fences. Just the raw JSON object.\n"
        "4. Your first character must be '{'."
    )

    user_message = (
        f"Role applied for: {role}\n"
        f"Transcript language: {candidate_lang_name}\n\n"
        f"Behavioral interview transcript:\n{qa_pairs_text}\n\n"
        "Now output the JSON scorecard. Remember: start with '{', no explanation, "
        "no markdown, no analysis before the JSON — produce ONLY the filled "
        "template above."
    )

    return system_prompt, user_message
