"""
helpers.py — Pure, reusable helper functions.

Nothing here imports streamlit, requests, or any heavy dependency. These
are small text-manipulation / JSON-parsing / regex utilities that the
services and views compose.
"""

from __future__ import annotations

import json
import re
from typing import Any, Optional


# ──────────────────────────────────────────────────────────────────────
# Phone & email extraction (resume contact info from spoken transcripts)
#
# The candidate SPEAKS their phone and email, so STT often produces:
#   * "rajesh at gmail dot com"            (no @, no .)
#   * "rajesh at the rate gmail dot com"   (Indian English idiom)
#   * "nine eight seven six five four ..." (digit words instead of digits)
#   * "नौ आठ सात छह..."                  (Hindi digit words)
#   * "98765 43210"                        (separators between digits)
#
# We normalise all of these into digit/email form before regex-matching.
# ──────────────────────────────────────────────────────────────────────
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_PHONE_RE = re.compile(r"(\d{10})")

# Word → digit mappings. Lower-case English + Hindi (Devanagari).
_DIGIT_WORDS_EN: dict[str, str] = {
    "zero": "0", "oh": "0", "o": "0",
    "one": "1", "two": "2", "three": "3", "four": "4", "five": "5",
    "six": "6", "seven": "7", "eight": "8", "nine": "9",
    # Common Indian-English variants
    "doh": "2", "tree": "3", "for": "4", "tu": "2",
}

_DIGIT_WORDS_HI: dict[str, str] = {
    "शून्य": "0", "जीरो": "0",
    "एक": "1", "दो": "2", "तीन": "3", "चार": "4", "पांच": "5",
    "पाँच": "5", "छह": "6", "छः": "6", "सात": "7", "आठ": "8", "नौ": "9",
}

_DIGIT_WORDS = {**_DIGIT_WORDS_EN, **_DIGIT_WORDS_HI}

# Phrases that mean "@" when an email is spoken
_AT_PATTERNS = re.compile(
    r"\b(?:at\s+the\s+rate(?:\s+of)?|at\s+the\s+rate|at\s+rate|at|ऐट|एट)\b",
    re.IGNORECASE,
)
# Phrases that mean "." inside an email
_DOT_PATTERNS = re.compile(
    r"\b(?:dot|डॉट|डाट)\b",
    re.IGNORECASE,
)


def _spoken_digits_to_numeric(text: str) -> str:
    """Replace spoken digit words with their digits, in place.

    Example:
        "my number is nine eight seven six five four three two one zero"
        → "my number is 9 8 7 6 5 4 3 2 1 0"
    """
    if not text:
        return text

    def _replace(match: re.Match) -> str:
        word = match.group(0).lower()
        return _DIGIT_WORDS.get(word, match.group(0))

    # English digit words — word-boundary based
    pattern_en = r"\b(?:" + "|".join(re.escape(w) for w in _DIGIT_WORDS_EN) + r")\b"
    text = re.sub(pattern_en, _replace, text, flags=re.IGNORECASE)

    # Hindi digit words — Devanagari isn't covered by \b in Python's re.
    # Use a non-word boundary that allows them to be flanked by spaces or
    # punctuation but not other Devanagari letters.
    for hi_word, digit in _DIGIT_WORDS_HI.items():
        text = re.sub(
            rf"(?<![ऀ-ॿ]){re.escape(hi_word)}(?![ऀ-ॿ])",
            digit,
            text,
        )
    return text


def _reconstruct_email(text: str) -> Optional[str]:
    """Try to rebuild an email from "X at Y dot Z" spoken form.

    Returns a valid-looking email string or ``None``.
    """
    if not text:
        return None
    # Replace spoken-form separators with @ / .
    candidate = _AT_PATTERNS.sub("@", text)
    candidate = _DOT_PATTERNS.sub(".", candidate)
    # Tighten: collapse "X @ Y" → "X@Y" and "Y . com" → "Y.com" so the
    # email regex catches them.
    candidate = re.sub(r"\s*@\s*", "@", candidate)
    candidate = re.sub(r"\s*\.\s*", ".", candidate)
    m = _EMAIL_RE.search(candidate)
    return m.group(0) if m else None


def extract_phone_and_email(text: str) -> tuple[Optional[str], Optional[str]]:
    """Pull a 10-digit phone number and an email address from free-form text.

    Handles:
      * digits with separators ("98765 43210", "98765-43210")
      * digit words in English ("nine eight seven …")
      * digit words in Hindi ("नौ आठ सात …")
      * +91 country prefix
      * spoken emails ("rajesh at gmail dot com",
        "rajesh at the rate gmail dot com")

    Returns:
        ``(phone, email)`` — either or both may be ``None``.
    """
    if not text:
        return None, None

    # ── Email ────────────────────────────────────────────────────────
    # First try a direct match (covers cases where the candidate typed,
    # or where STT happened to render '@' and '.' correctly).
    email_m = _EMAIL_RE.search(text)
    email = email_m.group(0) if email_m else None
    # Fallback: reconstruct from spoken "at"/"dot" patterns.
    if not email:
        email = _reconstruct_email(text)

    # ── Phone ────────────────────────────────────────────────────────
    # First normalise spoken digit words into digit characters.
    normalised = _spoken_digits_to_numeric(text)
    # Pull out every digit, in order. Indian mobile numbers are 10 digits;
    # 91/+91 country code adds 2 more; a leading 0 trunk prefix adds 1.
    digits = re.sub(r"\D", "", normalised)
    phone: Optional[str] = None
    if len(digits) == 10:
        phone = digits
    elif len(digits) == 12 and digits.startswith("91"):
        phone = digits[2:]
    elif len(digits) == 11 and digits.startswith("0"):
        phone = digits[1:]
    elif len(digits) > 10:
        # Take the LAST 10 digits — most other digits in the answer are
        # noise (e.g. "I am 35 years old, mobile 9876543210").
        phone = digits[-10:]
    return phone, email


def extract_contact_from_transcripts(
    transcripts: list[str | None],
) -> tuple[Optional[str], Optional[str]]:
    """Scan every onboarding answer for phone and email.

    Candidates sometimes give contact details in answers other than Q1
    (e.g. when re-stating in another question). This widens the safety
    net so we don't blank the resume header just because Q1's transcript
    came through fuzzy.
    """
    phone, email = None, None
    for answer in transcripts:
        if not answer:
            continue
        p, e = extract_phone_and_email(answer)
        if p and not phone:
            phone = p
        if e and not email:
            email = e
        if phone and email:
            break
    return phone, email


# ──────────────────────────────────────────────────────────────────────
# JSON parsing with recovery for LLM responses
# ──────────────────────────────────────────────────────────────────────
def strip_code_fences(text: str) -> str:
    """Remove ``` fences the model occasionally wraps output in."""
    text = (text or "").strip()
    if text.startswith("```"):
        # Drop the opening ``` (and any language tag on the same line).
        lines = text.splitlines()
        lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


def parse_json_lenient(raw: str) -> Optional[dict]:
    """Try multiple strategies to parse a possibly-messy JSON string.

    Order of attempts:
      1. ``json.loads`` after stripping ``` fences
      2. Grab the outermost ``{...}`` block from a string with prose around it

    Returns the parsed dict on success or ``None`` if every strategy
    fails. Never raises.
    """
    clean = strip_code_fences(raw)
    if clean.startswith("{") and clean.endswith("}"):
        try:
            return json.loads(clean)
        except json.JSONDecodeError:
            pass
    start = clean.find("{")
    end = clean.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(clean[start:end + 1])
        except json.JSONDecodeError:
            pass
    return None


def coerce_str_list(value: Any) -> list[str]:
    """Normalise an LLM 'list of strings' field that may have been
    returned as a single string, a list, ``None``, or unrelated junk.

    Handles the bug where iterating a Hindi string yielded one bullet
    per character (the LLM returned a single string instead of a list).
    """
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]
    if isinstance(value, str):
        for sep in ("\n", ";"):
            if sep in value:
                parts = [p.strip() for p in value.split(sep) if p.strip()]
                if len(parts) > 1:
                    return parts
        return [value.strip()]
    return [str(value)]


# ──────────────────────────────────────────────────────────────────────
# PDF text safety
# ──────────────────────────────────────────────────────────────────────
_LATIN1_REPLACEMENTS = {
    "—": "-", "–": "-",
    "“": '"', "”": '"', "‘": "'", "’": "'",
    "•": "*", "₹": "INR ", "₨": "INR ",
}


def ascii_safe(text: str) -> str:
    """Convert text to a Latin-1-safe form for fpdf's built-in Helvetica.

    Replaces common Unicode punctuation with ASCII equivalents and drops
    any stray non-Latin-1 characters (e.g. leftover Devanagari) so PDF
    rendering never crashes mid-page.
    """
    for src, dst in _LATIN1_REPLACEMENTS.items():
        text = text.replace(src, dst)
    return text.encode("latin-1", errors="replace").decode("latin-1")


# ──────────────────────────────────────────────────────────────────────
# Indic digit-word → ASCII digit normalisation
# ──────────────────────────────────────────────────────────────────────
# Used by ProfileExtractService to fix cases where the LLM returns the
# candidate's spoken digits in their native language instead of ASCII
# digits (e.g. "आठ सात नौ पाँच" → "8795"). Works for all 11 supported
# languages.

# Native-script digits (e.g. Devanagari ०१२३ → 0123)
_NATIVE_SCRIPT_DIGITS: dict[str, str] = {
    # Devanagari (Hindi, Marathi)
    "०": "0", "१": "1", "२": "2", "३": "3", "४": "4",
    "५": "5", "६": "6", "७": "7", "८": "8", "९": "9",
    # Bengali
    "০": "0", "১": "1", "২": "2", "৩": "3", "৪": "4",
    "৫": "5", "৬": "6", "৭": "7", "৮": "8", "৯": "9",
    # Gurmukhi (Punjabi)
    "੦": "0", "੧": "1", "੨": "2", "੩": "3", "੪": "4",
    "੫": "5", "੬": "6", "੭": "7", "੮": "8", "੯": "9",
    # Gujarati
    "૦": "0", "૧": "1", "૨": "2", "૩": "3", "૪": "4",
    "૫": "5", "૬": "6", "૭": "7", "૮": "8", "૯": "9",
    # Telugu
    "౦": "0", "౧": "1", "౨": "2", "౩": "3", "౪": "4",
    "౫": "5", "౬": "6", "౭": "7", "౮": "8", "౯": "9",
    # Kannada
    "೦": "0", "೧": "1", "೨": "2", "೩": "3", "೪": "4",
    "೫": "5", "೬": "6", "೭": "7", "೮": "8", "೯": "9",
    # Malayalam
    "൦": "0", "൧": "1", "൨": "2", "൩": "3", "൪": "4",
    "൫": "5", "൬": "6", "൭": "7", "൮": "8", "൯": "9",
    # Tamil
    "௦": "0", "௧": "1", "௨": "2", "௩": "3", "௪": "4",
    "௫": "5", "௬": "6", "௭": "7", "௮": "8", "௯": "9",
    # Odia
    "୦": "0", "୧": "1", "୨": "2", "୩": "3", "୪": "4",
    "୫": "5", "୬": "6", "୭": "7", "୮": "8", "୯": "9",
}

# Spoken digit words per language (lowercased). Includes both the actual
# native digit words AND the common English-pronunciation transliterations
# (Indian English speakers often say digits in English even while speaking
# Hindi/Marathi/etc., and Sarvam STT writes those phonetically — e.g.
# "एट" = "eight", "नाइन" = "nine", "थ्री" = "three").
_DIGIT_WORDS_BY_LANG: dict[str, dict[str, str]] = {
    "hi": {
        # native Hindi
        "शून्य": "0", "जीरो": "0", "ज़ीरो": "0",
        "एक": "1",
        "दो": "2",
        "तीन": "3",
        "चार": "4",
        "पाँच": "5", "पांच": "5",
        "छह": "6", "छः": "6", "छे": "6",
        "सात": "7",
        "आठ": "8",
        "नौ": "9", "नो": "9",
        # English-pronounced digits transliterated into Devanagari
        # (common in Indian English code-mixing — Sarvam STT writes them
        # this way when the candidate said them in English)
        "ज़ीरो": "0", "ओ": "0",
        "वन": "1",
        "टू": "2",
        "थ्री": "3",
        "फोर": "4", "फॉर": "4",
        "फाइव": "5", "फ़ाइव": "5",
        "सिक्स": "6",
        "सेवन": "7",
        "एट": "8", "ऐट": "8",
        "नाइन": "9",
    },
    "mr": {  # Marathi shares Devanagari with Hindi
        "शून्य": "0",
        "एक": "1",
        "दोन": "2", "दो": "2",
        "तीन": "3",
        "चार": "4",
        "पाच": "5", "पाँच": "5",
        "सहा": "6", "छह": "6",
        "सात": "7",
        "आठ": "8",
        "नऊ": "9", "नौ": "9",
        # English-pronounced digits transliterated into Devanagari
        "ज़ीरो": "0", "जीरो": "0",
        "वन": "1", "टू": "2", "थ्री": "3",
        "फोर": "4", "फॉर": "4", "फाइव": "5",
        "सिक्स": "6", "सेवन": "7",
        "एट": "8", "ऐट": "8", "नाइन": "9",
    },
    "bn": {
        "শূন্য": "0",
        "এক": "1",
        "দুই": "2",
        "তিন": "3",
        "চার": "4",
        "পাঁচ": "5",
        "ছয়": "6",
        "সাত": "7",
        "আট": "8",
        "নয়": "9",
    },
    "gu": {
        "શૂન્ય": "0",
        "એક": "1",
        "બે": "2",
        "ત્રણ": "3",
        "ચાર": "4",
        "પાંચ": "5",
        "છ": "6",
        "સાત": "7",
        "આઠ": "8",
        "નવ": "9",
    },
    "pa": {
        "ਜ਼ੀਰੋ": "0", "ਸਿਫ਼ਰ": "0",
        "ਇੱਕ": "1", "ਇਕ": "1",
        "ਦੋ": "2",
        "ਤਿੰਨ": "3",
        "ਚਾਰ": "4",
        "ਪੰਜ": "5",
        "ਛੇ": "6",
        "ਸੱਤ": "7",
        "ਅੱਠ": "8",
        "ਨੌਂ": "9", "ਨੌ": "9",
    },
    "te": {
        "సున్నా": "0", "శూన్యం": "0",
        "ఒకటి": "1", "ఒక": "1",
        "రెండు": "2",
        "మూడు": "3",
        "నాలుగు": "4",
        "ఐదు": "5",
        "ఆరు": "6",
        "ఏడు": "7",
        "ఎనిమిది": "8",
        "తొమ్మిది": "9",
    },
    "kn": {
        "ಸೊನ್ನೆ": "0", "ಶೂನ್ಯ": "0",
        "ಒಂದು": "1",
        "ಎರಡು": "2",
        "ಮೂರು": "3",
        "ನಾಲ್ಕು": "4",
        "ಐದು": "5",
        "ಆರು": "6",
        "ಏಳು": "7",
        "ಎಂಟು": "8",
        "ಒಂಬತ್ತು": "9",
    },
    "ml": {
        "പൂജ്യം": "0", "സീറോ": "0",
        "ഒന്ന്": "1", "ഒന്നു": "1",
        "രണ്ട്": "2", "രണ്ടു": "2",
        "മൂന്ന്": "3", "മൂന്നു": "3",
        "നാല്": "4", "നാലു": "4",
        "അഞ്ച്": "5",
        "ആറ്": "6", "ആറു": "6",
        "ഏഴ്": "7", "ഏഴു": "7",
        "എട്ട്": "8", "എട്ടു": "8",
        "ഒൻപത്": "9", "ഒമ്പത്": "9",
    },
    "ta": {
        "பூஜ்யம்": "0", "சைபர்": "0",
        "ஒன்று": "1",
        "இரண்டு": "2",
        "மூன்று": "3",
        "நான்கு": "4",
        "ஐந்து": "5",
        "ஆறு": "6",
        "ஏழு": "7",
        "எட்டு": "8",
        "ஒன்பது": "9",
    },
    "od": {
        "ଶୂନ୍ୟ": "0",
        "ଗୋଟିଏ": "1", "ଏକ": "1",
        "ଦୁଇ": "2",
        "ତିନି": "3",
        "ଚାରି": "4",
        "ପାଞ୍ଚ": "5",
        "ଛଅ": "6",
        "ସାତ": "7",
        "ଆଠ": "8",
        "ନଅ": "9",
    },
    "en": {
        "zero": "0", "oh": "0", "o": "0", "naught": "0",
        "one": "1",
        "two": "2", "too": "2", "to": "2",
        "three": "3",
        "four": "4", "for": "4",
        "five": "5",
        "six": "6",
        "seven": "7",
        "eight": "8", "ate": "8",
        "nine": "9",
    },
}


def normalise_digits(text: str, language: str = "en") -> str:
    """Convert any digit-words / native-script digits in `text` to ASCII digits.

    Examples:
        ``"आठ सात नौ पाँच"`` (language="hi")          →  ``"8795"``
        ``"एट सेवन नाइन फाइव डबल एट"`` (language="hi") →  ``"879588"``
        ``"೯೮೭೬"`` (any language)                      →  ``"9876"``
        ``"my number is 9 8 7 6 5"``                   →  ``"my number is 98765"``
        ``"eight seven double four nine"`` (lang="en") →  ``"87449"``

    Strategy:
        1. Replace native-script digit glyphs (०, ౦, ೦, ...) with ASCII.
        2. Replace word-forms ("आठ", "ஏழு", "eight") with their digit.
        3. Expand "double X" / "डबल X" → "XX" and "triple X" → "XXX".
        4. Strip whitespace BETWEEN consecutive digits so "9 8 7" → "987".
        5. Leave anything that didn't match alone.

    Note: this is a best-effort post-processor for mobile-number extraction.
    It does NOT remove non-digit text — callers should run a final
    ``re.sub(r'\\D', '', result)`` if they want digits-only output.
    """
    if not text:
        return text

    # 1. Native-script digit glyphs → ASCII (does not need spaces around them)
    out = "".join(_NATIVE_SCRIPT_DIGITS.get(ch, ch) for ch in text)

    # 2. Word-form replacement. Longest-match-first to avoid partials
    #    (e.g. "एक" inside a longer word).
    words = _DIGIT_WORDS_BY_LANG.get(language, {})
    if words:
        for src in sorted(words.keys(), key=len, reverse=True):
            out = out.replace(src, " " + words[src] + " ")
            if src.isascii():
                out = out.replace(src.capitalize(), " " + words[src] + " ")
                out = out.replace(src.upper(), " " + words[src] + " ")

    # 3. Expand 'double X' / 'triple X' patterns in any language we know.
    #    Each language has its own word for double/triple — gather them all.
    import re as _re
    _DOUBLE_WORDS = (
        "double", "Double", "DOUBLE",
        "डबल", "ਡਬਲ", "ডবল", "ડબલ",
        "ಡಬಲ್", "ഡബിൾ", "డబుల్", "டபுள்",
    )
    _TRIPLE_WORDS = (
        "triple", "Triple", "TRIPLE",
        "ट्रिपल", "ਟ੍ਰਿਪਲ", "ট্রিপল", "ટ્રિપલ",
        "ಟ್ರಿಪಲ್", "ട്രിപ്പിൾ", "ట్రిపుల్", "டிரிபிள்",
    )
    for word in _DOUBLE_WORDS:
        out = _re.sub(rf"{_re.escape(word)}\s+(\d)", r"\1\1", out)
    for word in _TRIPLE_WORDS:
        out = _re.sub(rf"{_re.escape(word)}\s+(\d)", r"\1\1\1", out)

    # 4. Collapse whitespace between consecutive digits ("9 8 7" → "987")
    out = _re.sub(r"(?<=\d)\s+(?=\d)", "", out)
    return out


def extract_phone_digits(text: str, language: str = "en") -> str:
    """Strict mobile-number extractor: returns just the 10-digit number, or ''.

    Pipeline:
        1. ``normalise_digits`` — handle Indic words + native script.
        2. Strip everything that isn't 0-9.
        3. Strip leading 91 / +91 country code if present.
        4. Return only if 10 digits remain.

    Examples:
        ``"मेरा नंबर आठ सात नौ पाँच ८ ८ ४ १ १ २ है"``  →  ``"8795884112"``
        ``"+91 98765 43210"``                          →  ``"9876543210"``
    """
    import re as _re
    normalised = normalise_digits(text or "", language=language)
    digits = _re.sub(r"\D", "", normalised)
    if not digits:
        return ""
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    if len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    return digits if len(digits) == 10 else ""
