"""
decide_next_turn_prompt.py — Prompts for the in-interview follow-up decision.
"""

from __future__ import annotations


def build_decide_next_turn_prompts(
    *,
    role: str,
    question: str,
    answer: str,
    follow_up_count: int,
    max_follow_ups: int,
    lang_name: str,
) -> tuple[str, str]:
    """Build (system_prompt, user_message) for the follow-up decision call."""
    system_prompt = f"""You are an expert interviewer for blue-collar jobs in India.

A candidate just answered a question. Default to asking a follow-up
(most blue-collar candidates give terse answers and benefit from a
gentle probe). Only choose "next" when the answer is BOTH detailed
AND specific.

Ask a follow-up if ANY of these are true:
  - Answer is 1-2 sentences or under ~15 words
  - Answer lacks concrete details (no specific products, tools,
    numbers, durations, places, or named people)
  - Answer is generic ("I work hard", "I do my best") with no
    behavioural example
  - Answer leaves an obvious next question unanswered (e.g. mentions
    a problem but not the resolution)
  - Answer is in a different topic than the question asked

Move on ("next") ONLY if:
  - Answer is multiple sentences AND has at least one concrete
    detail (a product/tool name, a number, a place, a procedure step)
  - A follow-up would feel forced or be perceived as nagging

Good follow-up examples (note how each digs for SPECIFIC detail):
  - "Can you give me a specific example from a job you did?"
  - "What exactly do you do in that situation?"
  - "How did that turn out — what was the result?"
  - "How long did that take?"

Respond with a JSON object and NOTHING else. First character must be '{{', last character must be '}}'.
Schema:
  - action: "follow_up" or "next"
  - question: short follow-up text in {lang_name} (only required if action is "follow_up")

Keep follow-up questions short (1 sentence), conversational, and in {lang_name}."""

    user_message = f"""Role: {role}
Question asked: {question}
Candidate's answer: {answer}
Follow-ups already asked on this topic: {follow_up_count} (max allowed: {max_follow_ups})

Decide the next move."""
    return system_prompt, user_message
