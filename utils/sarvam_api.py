"""
sarvam_api.py — Wrapper for all Sarvam AI API calls.

APIs used:
  STT  : POST https://api.sarvam.ai/speech-to-text
  TTS  : POST https://api.sarvam.ai/text-to-speech
  LLM  : POST https://api.sarvam.ai/v1/chat/completions
"""

import os
import re
import base64
import requests
import json
from dotenv import load_dotenv

load_dotenv()

SARVAM_API_KEY = os.getenv("SARVAM_API_KEY")
BASE_URL = "https://api.sarvam.ai"

HEADERS = {
    "api-subscription-key": SARVAM_API_KEY,
    "Content-Type": "application/json"
}


# ─────────────────────────────────────────────
# 1. SPEECH TO TEXT (Saaras v3)
# ─────────────────────────────────────────────
def speech_to_text(audio_file_path: str, language_code: str = "hi-IN") -> str:
    """
    Convert recorded audio file to text using Sarvam Saaras v3.

    Args:
        audio_file_path : Path to a .wav audio file (max 30s for REST API)
        language_code   : BCP-47 code. Use "hi-IN" for Hindi, "en-IN" for English.
                          Pass "unknown" to let Sarvam auto-detect.

    Returns:
        Transcribed text string.
    """
    url = f"{BASE_URL}/speech-to-text"

    with open(audio_file_path, "rb") as f:
        audio_bytes = f.read()

    # Guard: a WAV with just a header (~44 bytes) or only a fraction of a second
    # of silence will make Sarvam return 400. 16 kHz mono PCM ≈ 32 KB/sec, so
    # anything under ~6 KB is well under 200 ms of real audio.
    if len(audio_bytes) < 6_000:
        raise RuntimeError(
            f"Audio too short ({len(audio_bytes)} bytes). "
            "Please click the mic and speak for at least 1 second."
        )

    # Sarvam STT REST API expects multipart/form-data
    files = {
        "file": (os.path.basename(audio_file_path), audio_bytes, "audio/wav"),
    }
    data = {
        "model": "saaras:v3",
        "language_code": language_code,
    }

    # Use a separate header without Content-Type for multipart
    headers = {"api-subscription-key": SARVAM_API_KEY}

    response = requests.post(url, headers=headers, files=files, data=data)
    if not response.ok:
        # Surface the actual server message instead of the generic HTTPError
        raise RuntimeError(
            f"Sarvam STT {response.status_code}: {response.text[:500]}"
        )

    result = response.json()
    transcript = result.get("transcript", "")
    print(f"[STT] Transcribed: {transcript}")
    return transcript

#stt=sarvam.STT(language="unknown", model="saaras:v3", mode="transcribe"),  # Auto-detects language
#tts=sarvam.TTS(target_language_code="en-IN", model="bulbul:v3", speaker="anand")
# ─────────────────────────────────────────────
# 2. TEXT TO SPEECH (Bulbul v3)
# ─────────────────────────────────────────────
def text_to_speech(text: str, output_path: str, language_code: str = "hi-IN") -> str:
    """
    Convert text to speech using Sarvam Bulbul v3.

    Args:
        text          : Text to convert (keep under 500 chars per call)
        output_path   : Where to save the resulting .wav file
        language_code : "hi-IN" for Hindi, "en-IN" for Indian English

    Returns:
        Path to the saved audio file.
    """
    url = f"{BASE_URL}/text-to-speech"

    payload = {
        "text": text,
        "target_language_code": language_code,
        "speaker": "shubh",        # v3 speakers (lowercase): anushka, vidya, arya, abhilash, manisha, shubh, ...
        "speech_sample_rate": 48000, # v3 REST also supports 24000, 32000, 44100, 48000
        "model": "bulbul:v3"
    }

    response = requests.post(url, headers=HEADERS, json=payload)
    if not response.ok:
        print(f"[TTS] Server said: {response.status_code} — {response.text}")
    response.raise_for_status()

    result = response.json()
    audio_data = result.get("audios", [None])[0]

    if not audio_data:
        raise ValueError("No audio returned from TTS API")

    # Audio is base64-encoded WAV
    audio_bytes = base64.b64decode(audio_data)
    with open(output_path, "wb") as f:
        f.write(audio_bytes)

    print(f"[TTS] Audio saved to {output_path}")
    return output_path


# ─────────────────────────────────────────────
# 3. CHAT / LLM (sarvam-105b)
# ─────────────────────────────────────────────
def chat_completion(
    messages: list,
    system_prompt: str = "",
    max_tokens: int = 4096,
    temperature: float = 0.5
) -> str:
    """
    Send a chat request to Sarvam LLM.

    Args:
        messages      : List of {"role": "user"/"assistant", "content": "..."} dicts
        system_prompt : Optional system instruction
        max_tokens    : Cap on response length. Starter tier max for
                        sarvam-30b is 4096 — do not exceed.
        temperature   : Sampling temperature

    Returns:
        Model's response text.

    Note: sarvam-30b is a reasoning model whose chain-of-thought is billed
    against max_tokens. We hardcode reasoning_effort="low" in the payload
    below so enough output budget is left for the actual answer.
    """
    url = f"{BASE_URL}/v1/chat/completions"

    full_messages = []
    if system_prompt:
        full_messages.append({"role": "system", "content": system_prompt})
    full_messages.extend(messages)

    payload = {
        "model": "sarvam-30b",
        "messages": full_messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "reasoning_effort": "low",
    }

    response = requests.post(url, headers=HEADERS, json=payload)
    print(f"[LLM] HTTP {response.status_code} — raw body (first 800 chars): {response.text[:800]}")
    response.raise_for_status()

    result = response.json()
    try:
        choice = result["choices"][0]
        reply = choice["message"]["content"]
    except (KeyError, IndexError, TypeError) as e:
        raise RuntimeError(f"Unexpected LLM response shape ({e}): {result}") from e

    if reply is None:
        finish = choice.get("finish_reason")
        # Some Sarvam models emit reasoning tokens that don't appear in `content`.
        # Surface anything we can find (reasoning_content / partial text) so the
        # caller can see what the model produced before it ran out of tokens.
        partial = (
            choice.get("message", {}).get("reasoning_content")
            or choice.get("delta", {}).get("content")
            or ""
        )
        raise RuntimeError(
            f"LLM returned content=None (finish_reason={finish!r}, "
            f"max_tokens={max_tokens}). "
            f"If finish_reason is 'length', increase max_tokens. "
            f"Partial output: {str(partial)[:300]}"
        )

    print(f"[LLM] Reply: {reply[:80]}...")
    return reply


# ─────────────────────────────────────────────
# 4. DECIDE NEXT TURN (follow-up or move on)
# ─────────────────────────────────────────────
def decide_next_turn(
    role: str,
    question: str,
    answer: str,
    follow_up_count: int,
    language: str = "en",
    max_follow_ups: int = 1,
) -> dict:
    """
    After a candidate answers, decide whether to ask a follow-up or move to
    the next prepared question.

    Returns:
        {"action": "follow_up", "question": "..."}  — ask the follow-up
        {"action": "next"}                          — move to the next main question
    """
    # Hard cap — never exceed max follow-ups per topic
    if follow_up_count >= max_follow_ups:
        return {"action": "next"}

    # Skip follow-up entirely if there's no answer to probe
    if not answer or not answer.strip() or answer.strip().lower().startswith("no answer"):
        return {"action": "next"}

    lang_name = "Hindi" if language == "hi" else "English"

    system_prompt = f"""You are an expert interviewer for blue-collar jobs in India.

A candidate just answered a question. Decide whether to:
  (a) ask ONE short follow-up to clarify or dig deeper, OR
  (b) move on to the next prepared question.

Ask a follow-up ONLY if:
  - The answer was vague, very short, or off-topic
  - There's a clear gap worth probing (e.g. "How did you handle that?", "Can you give an example?")
  - You can learn meaningfully more about the candidate

Move on if:
  - The answer was already clear and complete
  - A follow-up would feel forced or repetitive

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

    try:
        response = chat_completion(
            messages=[{"role": "user", "content": user_message}],
            system_prompt=system_prompt,
        )
    except Exception as e:
        print(f"[decide_next_turn] LLM error ({e}) — defaulting to 'next'")
        return {"action": "next"}

    # Parse JSON (same robust strategy as evaluate_candidate)
    try:
        clean = response.strip()
        if clean.startswith("```"):
            clean = clean.split("\n", 1)[1] if "\n" in clean else clean[3:]
            if clean.endswith("```"):
                clean = clean[:-3]
            clean = clean.strip()
        if not clean.startswith("{"):
            start = clean.find("{")
            end = clean.rfind("}")
            if start != -1 and end != -1:
                clean = clean[start:end + 1]
        decision = json.loads(clean)
    except json.JSONDecodeError:
        print(f"[decide_next_turn] Could not parse JSON — defaulting to 'next'")
        return {"action": "next"}

    if decision.get("action") == "follow_up" and decision.get("question"):
        return {"action": "follow_up", "question": str(decision["question"]).strip()}
    return {"action": "next"}


# ─────────────────────────────────────────────
# 5. EVALUATE CANDIDATE (LLM-based scoring)
# ─────────────────────────────────────────────
def evaluate_candidate(
    role: str,
    questions: list,
    answers: list,
    language: str = "en"
) -> dict:
    """
    Use the LLM to score the candidate's interview answers.

    Returns a dict with:
      - overall_score (0–10)
      - communication (0–10)
      - domain_knowledge (0–10)
      - confidence (0–10)
      - summary (str)
      - hire_recommendation (bool)
    """
    # If the candidate never produced a real answer to a question, including
    # the "No answer provided." placeholder just makes the reasoning model
    # burn tokens deliberating about empty rows. Drop them — but if NOTHING
    # was answered, keep one so the model has something to evaluate.
    SKIP_SUBSTRINGS = ("no answer provided", "कोई उत्तर")

    def _is_empty(a: str) -> bool:
        if not a or not a.strip():
            return True
        lo = a.strip().lower()
        return any(tok in lo for tok in SKIP_SUBSTRINGS)

    filtered = [(q, a) for q, a in zip(questions, answers) if not _is_empty(a)]
    if not filtered:
        # Candidate said nothing useful — short-circuit with a deterministic
        # report instead of asking the LLM to evaluate empty input.
        return {
            "overall_score": 0,
            "communication": 0,
            "domain_knowledge": 0,
            "confidence": 0,
            "summary": "Candidate did not provide answers to the interview questions.",
            "hire_recommendation": False,
            "strengths": [],
            "improvements": ["Provide spoken answers to each question."],
        }
    qa_pairs = "\n".join(f"Q{i+1}: {q}\nA{i+1}: {a}" for i, (q, a) in enumerate(filtered))

    # Map short language code → full language name for the LLM prompt
    LANG_NAMES = {
        "en": "English",
        "hi": "Hindi",
        "bn": "Bengali",
        "te": "Telugu",
        "pa": "Punjabi",
        "gu": "Gujarati",
    }
    lang_name = LANG_NAMES.get(language, "English")

    def _make_eval_prompts(output_lang: str) -> tuple[str, str]:
        """Build (system_prompt, user_message) asking for evaluation text in
        ``output_lang``. We use this twice: first call uses the candidate's
        language, retry uses English (~3× more token-efficient than
        Devanagari/Telugu/Bengali, so much less likely to bust the budget)."""
        sp = f"""You evaluate blue-collar job candidates in India.

Output ONE JSON object, no prose, no markdown. First char '{{', last char '}}'.
Keys:
  overall_score, communication, domain_knowledge, confidence: number 0-10
  summary: 2 sentences in {output_lang}
  hire_recommendation: true/false
  strengths: JSON array of 2 separate sentence strings in {output_lang}, e.g. ["sentence one", "sentence two"]
  improvements: JSON array of 1 to 2 separate sentence strings in {output_lang}
Scores and the boolean stay as numbers/bool. Text fields in {output_lang} only.
IMPORTANT: strengths and improvements MUST be JSON arrays of complete sentence strings, never a single string and never a list of individual characters."""
        um = f"""Role applied for: {role}
Language used: {language}

Interview transcript:
{qa_pairs}

Evaluate this candidate."""
        return sp, um

    # Attempt 1: native language (matches candidate's interview language).
    # Attempt 2 (retry): English — uses far fewer output tokens than
    # Devanagari/Telugu/Bengali, so it almost always fits in the 4096-token
    # budget even after the model's reasoning preamble. Better an English
    # summary on a recovered report than a hard failure for the demo.
    attempts: list[tuple[str, str]] = [
        (lang_name, "candidate's language"),
        ("English", "English (more token-efficient — recovery attempt)"),
    ]
    response = None
    last_error: Exception | None = None
    for attempt_no, (output_lang, why) in enumerate(attempts, start=1):
        sp, um = _make_eval_prompts(output_lang)
        try:
            response = chat_completion(
                messages=[{"role": "user", "content": um}],
                system_prompt=sp,
                temperature=0.3,
            )
            if attempt_no > 1:
                print(f"[evaluate] Recovered on attempt {attempt_no} using {why}")
            break
        except RuntimeError as e:
            last_error = e
            print(f"[evaluate] Attempt {attempt_no}/{len(attempts)} ({why}) failed: {e}")
            if attempt_no < len(attempts):
                print(f"[evaluate] Retrying with {attempts[attempt_no][1]}...")

    if response is None:
        # Both attempts failed — return a graceful fallback flagged so the
        # UI shows a "Retry Evaluation" button instead of a stack trace.
        print(f"[evaluate] Both attempts exhausted. Last error: {last_error}")
        return {
            "overall_score": None,
            "communication": None,
            "domain_knowledge": None,
            "confidence": None,
            "summary": (
                "Automatic evaluation could not be generated this time. "
                "Please click 'Retry Evaluation' below to try again."
            ),
            "hire_recommendation": None,
            "strengths": [],
            "improvements": [],
            "_generation_failed": True,
        }

    # Parse JSON from LLM response — with partial-recovery for the common
    # case where sarvam-30b ran out of output budget mid-JSON (it tends to
    # finish scores + summary but get truncated before strengths/improvements).
    evaluation = _parse_or_recover_evaluation(response)

    # If the LLM produced scores + summary but truncated before
    # strengths/improvements, run a small focused retry call to fill in
    # just those two fields. Much smaller request → fits in budget.
    needs_retry = (
        not evaluation.get("strengths")
        or not evaluation.get("improvements")
    ) and evaluation.get("summary") and "overall_score" in evaluation
    if needs_retry:
        try:
            extras = _retry_strengths_and_improvements(
                role=role,
                qa_pairs=qa_pairs,
                summary=evaluation.get("summary", ""),
                lang_name=lang_name,
            )
            if not evaluation.get("strengths"):
                evaluation["strengths"] = extras.get("strengths", [])
            if not evaluation.get("improvements"):
                evaluation["improvements"] = extras.get("improvements", [])
        except Exception as e:
            print(f"[evaluate] strengths/improvements retry failed ({e}) — leaving empty")

    return evaluation


def _parse_or_recover_evaluation(raw: str) -> dict:
    """Parse the evaluator's JSON output, recovering from common failures.

    Strategy:
      1. Try standard JSON parse (after stripping ``` fences if present).
      2. If that fails, regex-extract each known field from whatever the
         model managed to emit before truncation. This recovers scores
         and the summary even when the trailing fields got cut off.

    Never raises. Returns a dict shaped like the evaluator schema with
    safe defaults for anything that couldn't be recovered.
    """
    # Standard parse path
    clean = (raw or "").strip()
    if clean.startswith("```"):
        clean = clean.split("\n", 1)[1] if "\n" in clean else clean[3:]
        if clean.endswith("```"):
            clean = clean[:-3]
        clean = clean.strip()
    if clean.startswith("{") and clean.endswith("}"):
        try:
            return _normalize_evaluation(json.loads(clean))
        except json.JSONDecodeError:
            pass
    # Try grabbing the outermost {...} block from a response with prose
    start = clean.find("{")
    end = clean.rfind("}")
    if start != -1 and end > start:
        try:
            return _normalize_evaluation(json.loads(clean[start:end + 1]))
        except json.JSONDecodeError:
            pass

    # Recovery: regex-extract each field. This handles the typical
    # truncation case where the model wrote {..."summary":"...","hire_recommendation":
    # and then ran out of tokens.
    print("[evaluate] JSON parse failed — attempting regex recovery on truncated response")

    def _num(pattern: str):
        m = re.search(pattern, clean)
        if not m:
            return None
        try:
            v = m.group(1)
            return int(v) if "." not in v else float(v)
        except (ValueError, IndexError):
            return None

    def _str(pattern: str):
        m = re.search(pattern, clean, re.DOTALL)
        if not m:
            return None
        # Unescape standard JSON escapes
        s = m.group(1)
        try:
            return json.loads(f'"{s}"')
        except json.JSONDecodeError:
            return s.strip()

    def _bool(pattern: str):
        m = re.search(pattern, clean)
        return m.group(1).lower() == "true" if m else None

    def _list(pattern: str):
        m = re.search(pattern, clean, re.DOTALL)
        if not m:
            return None
        return [s for s in re.findall(r'"((?:[^"\\]|\\.)*)"', m.group(1)) if s.strip()]

    overall = _num(r'"overall_score"\s*:\s*(\d+(?:\.\d+)?)')
    communication = _num(r'"communication"\s*:\s*(\d+(?:\.\d+)?)')
    domain = _num(r'"domain_knowledge"\s*:\s*(\d+(?:\.\d+)?)')
    confidence = _num(r'"confidence"\s*:\s*(\d+(?:\.\d+)?)')
    summary = _str(r'"summary"\s*:\s*"((?:[^"\\]|\\.)*?)"')
    hire = _bool(r'"hire_recommendation"\s*:\s*(true|false)')
    strengths = _list(r'"strengths"\s*:\s*\[(.*?)\]') or []
    improvements = _list(r'"improvements"\s*:\s*\[(.*?)\]') or []

    return _normalize_evaluation({
        "overall_score": overall if overall is not None else 0,
        "communication": communication if communication is not None else 0,
        "domain_knowledge": domain if domain is not None else 0,
        "confidence": confidence if confidence is not None else 0,
        "summary": summary or "Evaluation could not be fully generated. Please retry.",
        "hire_recommendation": bool(hire) if hire is not None else False,
        "strengths": strengths,
        "improvements": improvements,
    })


def _normalize_evaluation(d: dict) -> dict:
    """Coerce evaluator output to the expected shape (especially list fields
    that the model sometimes returns as a single string)."""
    def _as_list(v):
        if v is None or v == "":
            return []
        if isinstance(v, list):
            return [str(x).strip() for x in v if str(x).strip()]
        if isinstance(v, str):
            # If the model returned one string with multiple sentences, split on common separators.
            for sep in ("\n", ";"):
                if sep in v:
                    parts = [p.strip() for p in v.split(sep) if p.strip()]
                    if len(parts) > 1:
                        return parts
            return [v.strip()]
        return [str(v)]

    return {
        "overall_score": d.get("overall_score") or 0,
        "communication": d.get("communication") or 0,
        "domain_knowledge": d.get("domain_knowledge") or 0,
        "confidence": d.get("confidence") or 0,
        "summary": str(d.get("summary") or "").strip() or "—",
        "hire_recommendation": bool(d.get("hire_recommendation")),
        "strengths": _as_list(d.get("strengths")),
        "improvements": _as_list(d.get("improvements")),
    }


def _retry_strengths_and_improvements(
    role: str,
    qa_pairs: str,
    summary: str,
    lang_name: str,
) -> dict:
    """Small focused LLM call for just strengths + improvements.

    Used when the main evaluation call truncated before reaching these
    fields. Much smaller prompt → fits comfortably in the output budget.
    """
    system_prompt = (
        f"You are a hiring evaluator. Output ONE JSON object only. "
        f"First char '{{', last char '}}'. No prose, no markdown."
    )
    user_message = (
        f"Role: {role}\n"
        f"Transcript:\n{qa_pairs}\n\n"
        f"Summary of the candidate (already written): {summary}\n\n"
        f"Output exactly this JSON, filling the arrays with short sentences in {lang_name}:\n"
        f'{{\n'
        f'  "strengths": ["sentence 1", "sentence 2"],\n'
        f'  "improvements": ["sentence 1", "sentence 2"]\n'
        f'}}'
    )
    raw = chat_completion(
        messages=[{"role": "user", "content": user_message}],
        system_prompt=system_prompt,
        temperature=0.3,
    )
    # Parse with the same robust helper
    parsed = _parse_or_recover_evaluation(raw)
    return {
        "strengths": parsed.get("strengths") or [],
        "improvements": parsed.get("improvements") or [],
    }


# ─────────────────────────────────────────────
# 6. SYSTEM HEALTH CHECK (for demo prep)
# ─────────────────────────────────────────────
def run_health_check() -> list[dict]:
    """Probe each Sarvam endpoint with a tiny payload and return a status list.

    Designed for pre-demo verification: catches API outages, expired keys,
    or rate-limit issues *before* the interview starts in front of a customer.

    STT shares the API key + auth scheme with TTS, so TTS-passing implies
    STT's auth/connectivity is also fine. We don't probe STT directly to
    avoid having to ship a sample WAV.

    Returns a list of dicts:
        {"name": str, "ok": bool, "latency_s": float, "detail": str}
    """
    import time as _time
    results: list[dict] = []

    # ── 1. TTS — Bulbul v3 ──────────────────────────────────────────────
    t0 = _time.time()
    try:
        url = f"{BASE_URL}/text-to-speech"
        payload = {
            "text": "ok",
            "target_language_code": "en-IN",
            "speaker": "shubh",
            "speech_sample_rate": 24000,
            "model": "bulbul:v3",
        }
        r = requests.post(url, headers=HEADERS, json=payload, timeout=15)
        elapsed = _time.time() - t0
        if r.ok:
            results.append({
                "name": "TTS — Bulbul v3",
                "ok": True,
                "latency_s": elapsed,
                "detail": "Voice synthesis is responding.",
            })
        else:
            results.append({
                "name": "TTS — Bulbul v3",
                "ok": False,
                "latency_s": elapsed,
                "detail": f"HTTP {r.status_code}: {r.text[:200]}",
            })
    except Exception as e:
        results.append({
            "name": "TTS — Bulbul v3",
            "ok": False,
            "latency_s": _time.time() - t0,
            "detail": f"Exception: {e}",
        })

    # ── 2. LLM — Chat completions (sarvam-30b) ──────────────────────────
    t0 = _time.time()
    try:
        # Tiny prompt + small max_tokens — won't trigger heavy reasoning,
        # so this completes in 1-3 seconds when the API is healthy.
        url = f"{BASE_URL}/v1/chat/completions"
        payload = {
            "model": "sarvam-30b",
            "messages": [{"role": "user", "content": "Reply with the single word: ok"}],
            # sarvam-30b reasons even on trivial prompts (~500 tokens of
            # chain-of-thought). Setting max_tokens too low gives false
            # negatives — the model is fine, it just needs more headroom.
            "max_tokens": 1500,
            "temperature": 0.0,
            "reasoning_effort": "low",
        }
        r = requests.post(url, headers=HEADERS, json=payload, timeout=30)
        elapsed = _time.time() - t0
        if r.ok:
            d = r.json()
            ch = d.get("choices", [{}])[0]
            content = (ch.get("message") or {}).get("content")
            if content:
                results.append({
                    "name": "LLM — sarvam-30b",
                    "ok": True,
                    "latency_s": elapsed,
                    "detail": "Chat completions are responding.",
                })
            else:
                # Got 200 but no content — model is reasoning past the
                # limit even on a trivial prompt. Demo will likely be slow.
                results.append({
                    "name": "LLM — sarvam-30b",
                    "ok": False,
                    "latency_s": elapsed,
                    "detail": (
                        f"Model returned no content (finish_reason="
                        f"{ch.get('finish_reason')!r}). API is up but the "
                        f"model is currently slow — expect retries during demo."
                    ),
                })
        else:
            results.append({
                "name": "LLM — sarvam-30b",
                "ok": False,
                "latency_s": elapsed,
                "detail": f"HTTP {r.status_code}: {r.text[:200]}",
            })
    except Exception as e:
        results.append({
            "name": "LLM — sarvam-30b",
            "ok": False,
            "latency_s": _time.time() - t0,
            "detail": f"Exception: {e}",
        })

    # ── 3. API key sanity ───────────────────────────────────────────────
    key_status = "set" if SARVAM_API_KEY else "MISSING"
    results.append({
        "name": "API key (SARVAM_API_KEY)",
        "ok": bool(SARVAM_API_KEY),
        "latency_s": 0.0,
        "detail": (
            f"Key {key_status}"
            + (f" — STT uses the same key, so its auth is OK if TTS passed."
               if SARVAM_API_KEY else " — set it in .env to enable interviews.")
        ),
    })

    return results
