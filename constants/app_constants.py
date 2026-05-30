"""
app_constants.py — All hardcoded values used across the codebase.

Anything that is shared between two or more modules, or that you would
want to change in one place (URLs, model names, magic numbers, timeouts,
file-name patterns) lives here. Translation strings stay in `data/`
because they are long-form content, not constants.
"""

from __future__ import annotations

# ──────────────────────────────────────────────────────────────────────
# Sarvam API endpoints (paths joined with settings.sarvam_base_url)
# ──────────────────────────────────────────────────────────────────────
STT_PATH = "/speech-to-text"
TTS_PATH = "/text-to-speech"
LLM_PATH = "/v1/chat/completions"

# ──────────────────────────────────────────────────────────────────────
# Sarvam model identifiers (subject to subscription-tier limits)
# ──────────────────────────────────────────────────────────────────────
STT_MODEL = "saaras:v3"
TTS_MODEL = "bulbul:v3"
LLM_MODEL = "sarvam-30b"

# ──────────────────────────────────────────────────────────────────────
# TTS defaults — Bulbul v3
# ──────────────────────────────────────────────────────────────────────
TTS_DEFAULT_SPEAKER = "shubh"
TTS_SAMPLE_RATE = 48000   # supported: 24000, 32000, 44100, 48000

# ──────────────────────────────────────────────────────────────────────
# LLM defaults — sarvam-30b
# Starter-tier max_tokens cap is 4096. Do not exceed without upgrading.
# ──────────────────────────────────────────────────────────────────────
LLM_DEFAULT_MAX_TOKENS = 4096
LLM_DEFAULT_TEMPERATURE = 0.5
LLM_REASONING_EFFORT = "low"
LLM_EVAL_TEMPERATURE = 0.3
LLM_EXTRACTION_TEMPERATURE = 0.2
LLM_RESUME_TEMPERATURE = 0.4
LLM_HEALTH_CHECK_MAX_TOKENS = 1500

# ──────────────────────────────────────────────────────────────────────
# HTTP timeouts (seconds)
# ──────────────────────────────────────────────────────────────────────
HTTP_TIMEOUT_TTS = 30
HTTP_TIMEOUT_STT = 60
HTTP_TIMEOUT_LLM = 120
HTTP_TIMEOUT_HEALTH_CHECK_TTS = 15
HTTP_TIMEOUT_HEALTH_CHECK_LLM = 30

# ──────────────────────────────────────────────────────────────────────
# Audio guards (browser mic widget can emit ~44-byte WAV stubs)
# ──────────────────────────────────────────────────────────────────────
# 16 kHz mono PCM ≈ 32 KB/sec; anything under ~6 KB is < 200 ms of real
# audio and almost always silence-only that Sarvam STT will reject 400.
MIN_REAL_AUDIO_BYTES = 6_000
AUDIO_SAMPLE_RATE = 16_000
SILENCE_PAUSE_SECONDS = 3.0

# ──────────────────────────────────────────────────────────────────────
# Interview / onboarding limits
# ──────────────────────────────────────────────────────────────────────
MAX_FOLLOW_UPS_PER_QUESTION = 1
PROFILE_SPARSE_FIELD_THRESHOLD = 3   # warn if fewer than this many fields populated

# ──────────────────────────────────────────────────────────────────────
# Profile-question → field mapping (matches order in data/profile_questions.py)
# ──────────────────────────────────────────────────────────────────────
QUESTION_FIELD_ORDER: tuple[str, ...] = (
    # Contact (email removed — too error-prone over voice for low-literacy
    # candidates; collected via WhatsApp/SMS after the call instead)
    "name",               # Q1  — full name              [confirm]
    "mobile",             # Q2  — mobile number          [confirm]
    # Age + location (was "location_and_age"; now 2 Qs)
    "age",                # Q3  — age in years           [confirm]
    "location",           # Q4  — city / town            [confirm]
    "documents",          # Q5  — Aadhaar / PAN / Driving Licence
    "languages",          # Q6  — languages spoken
    # Family (was "family"; now split into 2 Qs)
    "marital_status",     # Q7  — married?
    "dependents",         # Q8  — anyone depending on candidate
    "experience_years",   # Q9  — years of experience in {role}
    "experience",         # Q10 — past employers + duration
    "education",          # Q11 — qualifications
    "salary",             # Q12 — expected + last salary
    "availability",       # Q13 — start date + relocation
)

# Fields that trigger voice confirmation (LLM extract → TTS read-back →
# STT yes/no). Source of truth for both profile_view.py and the
# profile_questions.py requires_confirmation flag.
HIGH_RISK_FIELDS: frozenset[str] = frozenset({
    "name", "mobile", "age", "location",
})

# Max number of times a candidate can say "no" on a confirmation
# before we auto-accept the extracted value (recruiter can fix from
# the review screen).
PROFILE_CONFIRM_MAX_RETRIES = 2

# Human-readable section headers for the deterministic resume fallback.
RESUME_FIELD_LABELS: dict[str, str] = {
    "name":             "Full Name",
    "mobile":           "Mobile Number",
    "age":              "Age",
    "location":         "Location",
    "documents":        "Identity Documents",
    "languages":        "Languages Spoken",
    "marital_status":   "Marital Status",
    "dependents":       "Dependents",
    "experience_years": "Years of Experience",
    "experience":       "Work History",
    "education":        "Education",
    "salary":           "Salary Expectations",
    "availability":     "Availability",
}

# Keyword sets per language for parsing the candidate's spoken
# yes/no on confirmation. Lowercased substring matching — order doesn't
# matter, but YES_KEYWORDS is checked before NO_KEYWORDS so an
# ambiguous "yes no" is treated as yes (rare in practice).
YES_KEYWORDS: dict[str, tuple[str, ...]] = {
    "en": ("yes", "yeah", "yep", "correct", "right", "ok", "okay", "confirm", "true"),
    "hi": ("haan", "ha", "ji", "sahi", "theek", "bilkul", "हाँ", "हां", "जी", "सही", "ठीक"),
    "bn": ("ha", "hyan", "thik", "shothik", "হ্যাঁ", "হ্যা", "ঠিক", "সঠিক"),
    "te": ("avunu", "sari", "ౌను", "అవును", "సరి", "సరైనది"),
    "pa": ("haan", "ji", "sahi", "thik", "ਹਾਂ", "ਜੀ", "ਸਹੀ", "ਠੀਕ"),
    "gu": ("ha", "haa", "saachu", "barabar", "હા", "સાચું", "બરાબર"),
    "kn": ("howdu", "sari", "haudu", "ಹೌದು", "ಸರಿ", "ಸರಿಯಾಗಿದೆ"),
    "ml": ("athe", "ate", "sheri", "ശരി", "അതെ", "ശരിയാണ്"),
    "mr": ("hoy", "ho", "bareobar", "barobar", "होय", "हो", "बरोबर", "बरोबर आहे"),
    "od": ("haan", "thik", "saha", "ହଁ", "ଠିକ୍", "ସଠିକ୍"),
    "ta": ("aamaa", "amam", "ama", "sari", "sari thaan", "ஆம்", "ஆமாம்", "சரி", "சரிதான்"),
}

NO_KEYWORDS: dict[str, tuple[str, ...]] = {
    "en": ("no", "nope", "wrong", "incorrect", "not right", "false", "nah"),
    "hi": ("nahi", "nahin", "galat", "gadbad", "नहीं", "नही", "गलत"),
    "bn": ("na", "nei", "vul", "bhul", "না", "নেই", "ভুল"),
    "te": ("kadu", "tappu", "kaadu", "కాదు", "తప్పు"),
    "pa": ("nahi", "nahin", "galat", "ਨਹੀਂ", "ਗਲਤ"),
    "gu": ("na", "nahi", "khotu", "ના", "નહીં", "ખોટું"),
    "kn": ("illa", "tappu", "ಇಲ್ಲ", "ತಪ್ಪು"),
    "ml": ("alla", "illa", "thettu", "അല്ല", "ഇല്ല", "തെറ്റ്"),
    "mr": ("nahi", "chukla", "नाही", "चुकीचे", "चूक"),
    "od": ("nahi", "nuhe", "bhul", "ନୁହେଁ", "ନାହିଁ", "ଭୁଲ୍"),
    "ta": ("illai", "illa", "thavaru", "இல்லை", "தவறு"),
}

# Map of language code → human name used in LLM prompts.
LANGUAGE_NAMES: dict[str, str] = {
    "en": "English",
    "hi": "Hindi",
    "bn": "Bengali",
    "te": "Telugu",
    "pa": "Punjabi",
    "gu": "Gujarati",
    "kn": "Kannada",
    "ml": "Malayalam",
    "mr": "Marathi",
    "od": "Odia",
    "ta": "Tamil",
}

# Map of language code → native script name. Used by the resume prompt
# to explicitly forbid the wrong script when forcing an English output
# (e.g. "Do NOT include any Gurmukhi characters" for a Punjabi
# candidate). Hindi and Marathi share Devanagari.
SCRIPT_NAMES: dict[str, str] = {
    "en": "Latin",
    "hi": "Devanagari",
    "bn": "Bengali",
    "te": "Telugu",
    "pa": "Gurmukhi",
    "gu": "Gujarati",
    "kn": "Kannada",
    "ml": "Malayalam",
    "mr": "Devanagari",
    "od": "Odia",
    "ta": "Tamil",
}

# Few-shot translation examples per language used in the resume prompt
# to anchor the model on the right transliteration style for place
# names and common blue-collar trade terms.
TRANSLATION_EXAMPLES: dict[str, str] = {
    "en": "",
    "hi": "For example: होटल → hotel, गोरखपुर → Gorakhpur, हाउसकीपिंग → housekeeping.",
    "pa": "For example: ਹੋਟਲ → hotel, ਅੰਮ੍ਰਿਤਸਰ → Amritsar, ਘਰ ਦਾ ਕੰਮ → housekeeping.",
    "bn": "For example: হোটেল → hotel, কলকাতা → Kolkata, পরিষ্কার → cleaning.",
    "te": "For example: హోటల్ → hotel, హైదరాబాద్ → Hyderabad, విద్యుత్ → electrical.",
    "gu": "For example: હોટેલ → hotel, અમદાવાદ → Ahmedabad, સફાઈ → cleaning.",
    "kn": "For example: ಹೋಟೆಲ್ → hotel, ಬೆಂಗಳೂರು → Bengaluru, ಶುಚಿಗೊಳಿಸುವಿಕೆ → cleaning.",
    "ml": "For example: ഹോട്ടൽ → hotel, കൊച്ചി → Kochi, വൃത്തിയാക്കൽ → cleaning.",
    "mr": "For example: हॉटेल → hotel, मुंबई → Mumbai, स्वच्छता → cleaning.",
    "od": "For example: ହୋଟେଲ → hotel, ଭୁବନେଶ୍ୱର → Bhubaneswar, ସଫାଇ → cleaning.",
    "ta": "For example: ஓட்டல் → hotel, சென்னை → Chennai, துப்புரவு → cleaning.",
}

# Substrings used to detect "no answer" placeholders during evaluation.
EVALUATION_SKIP_SUBSTRINGS: tuple[str, ...] = (
    "no answer provided",
    "कोई उत्तर",
)

# ──────────────────────────────────────────────────────────────────────
# Filename patterns for persisted artefacts
# ──────────────────────────────────────────────────────────────────────
TEMP_AUDIO_SUBDIR = "temp"
DEBUG_SUBDIR = "debug"

PROFILE_JSON_FILENAME_TEMPLATE = "profile_{safe_name}_{ts}.json"
RESUME_PDF_FILENAME_TEMPLATE = "resume_{safe_name}_{ts}.pdf"
REPORT_JSON_FILENAME_TEMPLATE = "report_{safe_name}_{ts}.json"

# ──────────────────────────────────────────────────────────────────────
# Streamlit UI literals
# ──────────────────────────────────────────────────────────────────────
# ──────────────────────────────────────────────────────────────────────
# Design system — colours, typography, spacing, motion
# ──────────────────────────────────────────────────────────────────────
# A small, opinionated palette beats an unrestricted one. Used by both
# the Streamlit CSS (styles.py) and the PDF/avatar generators so the
# brand is consistent across every surface.
COLOR_PRIMARY = "#4F46E5"        # indigo-600 — CTA, brand, focus
COLOR_PRIMARY_DARK = "#4338CA"   # indigo-700 — hover/active
COLOR_PRIMARY_SOFT = "#EEF2FF"   # indigo-50  — selected backgrounds
COLOR_ACCENT = "#06B6D4"         # cyan-500   — secondary highlights
COLOR_SUCCESS = "#10B981"        # emerald-500
COLOR_WARN = "#F59E0B"           # amber-500
COLOR_DANGER = "#EF4444"         # red-500

COLOR_NEUTRAL_50 = "#FAFAFA"     # page background
COLOR_NEUTRAL_100 = "#F4F4F5"    # card background
COLOR_NEUTRAL_200 = "#E4E4E7"    # borders
COLOR_NEUTRAL_400 = "#A1A1AA"    # muted icons
COLOR_NEUTRAL_500 = "#71717A"    # secondary text
COLOR_NEUTRAL_700 = "#3F3F46"    # body text
COLOR_NEUTRAL_900 = "#18181B"    # headings

# Curated background colours assigned deterministically to candidate
# avatars based on a hash of their name → same person, same colour.
AVATAR_BG_COLOURS: tuple[str, ...] = (
    "#4F46E5",  # indigo
    "#06B6D4",  # cyan
    "#10B981",  # emerald
    "#F59E0B",  # amber
    "#EF4444",  # red
    "#8B5CF6",  # violet
    "#EC4899",  # pink
    "#0EA5E9",  # sky
)

APP_NAME = "श्रमसाथी AI"
APP_TAGLINE = "हर भाषा में, हर भारतीय श्रमिक के साथ"
APP_PAGE_TITLE = APP_NAME
APP_PAGE_ICON = "🎙"

# Logo file (relative to project root). The brand header renders this
# image if it exists; otherwise it falls back to APP_NAME text.
APP_LOGO_FILENAME = "assets/logo.png"

# Logo display size — 480 px. The new logo is a rich brand panel
# (illustration + brand mark + tagline + 5 feature icons), so it needs
# more breathing room than a plain wordmark. 480 px keeps the small
# feature-icon labels (Hindi text) legible while leaving enough room
# for the side tagline on a typical 880 px content container.
APP_LOGO_WIDTH_PX = 480

# Bot avatar is now generated as an inline SVG data URI in
# ui/streamlit/components.bot_avatar_url(). This constant is kept only
# so the codebase keeps importing without breakage if anything external
# still references it; nothing inside the project uses it anymore.
BOT_AVATAR_URL = "🤖"

# Gender-aware candidate avatars. The default avataaars style picks hair
# randomly from the seed (often long / feminine), which looks wrong for
# male candidates during demos. We constrain `top` (hair) and
# `facialHair` to gendered subsets so a male name always renders a
# masculine avatar and vice versa. The `unknown` URL keeps the original
# random behaviour for names we can't classify.
_AVATAAARS_BASE = "https://api.dicebear.com/7.x/avataaars/svg?seed={seed}"

CANDIDATE_AVATAR_MALE = (
    _AVATAAARS_BASE
    + "&top=shortFlat,shortRound,shortWaved,shortCurly,theCaesar,"
      "theCaesarAndSidePart,shaggy,shaggyMullet,sides,fro,froBand,"
      "shortDreads01,shortDreads02"
    + "&topProbability=100"
    + "&facialHair=blank,beardLight,beardMedium,moustacheMagnum,moustacheFancy"
    + "&facialHairProbability=55"
    + "&backgroundColor=b6e3f4,c0aede,d1d4f9"
)

CANDIDATE_AVATAR_FEMALE = (
    _AVATAAARS_BASE
    + "&top=longButNotTooLong,miaWallace,straight01,straight02,"
      "straightAndStrand,bigHair,bob,bun,curly,curvy,frida,frizzle"
    + "&topProbability=100"
    + "&facialHair=blank"
    + "&facialHairProbability=0"
    + "&backgroundColor=ffd5dc,ffdfbf,c0aede"
)

CANDIDATE_AVATAR_NEUTRAL = (
    _AVATAAARS_BASE
    + "&backgroundColor=b6e3f4,c0aede,d1d4f9,ffd5dc,ffdfbf"
)

# Kept for backwards compatibility with anything still referencing the
# original name. Points at the neutral variant.
CANDIDATE_AVATAR_BASE = CANDIDATE_AVATAR_NEUTRAL

# Stage names (single source of truth for the streamlit FSM)
STAGE_SETUP = "setup"
STAGE_PROFILE_INTRO = "profile_intro"
STAGE_PROFILE = "profile"
STAGE_PROFILE_BUILDING = "profile_building"
STAGE_PROFILE_REVIEW = "profile_review"
STAGE_GREETING = "greeting"
STAGE_INTERVIEW = "interview"
STAGE_CLOSING = "closing"
# Behavioral round runs RIGHT AFTER the technical interview, BEFORE the
# evaluation. Flow:
#   closing → behavioral_intro → behavioral_qs → behavioral_done
#           → evaluating (runs BOTH technical + behavioral) → report
STAGE_BEHAVIORAL_INTRO = "behavioral_intro"
STAGE_BEHAVIORAL_QS = "behavioral_qs"
STAGE_BEHAVIORAL_DONE = "behavioral_done"   # short "ready for results" screen
STAGE_EVALUATING = "evaluating"              # combined eval (technical + behavioral)
STAGE_REPORT = "report"

# How many behavioral questions get asked. Used as the loop bound.
BEHAVIORAL_QUESTION_COUNT = 5

# The 5 personality traits we score. Single source of truth — used by
# the prompt, the service, and the dashboard renderer (radar chart axes).
BEHAVIORAL_TRAITS: tuple[tuple[str, str, str], ...] = (
    # (field_key,             display_label,        icon)
    ("honesty",               "Honesty",            "🛡"),
    ("reliability",           "Reliability",        "📅"),
    ("stress_tolerance",      "Stress Tolerance",   "🔥"),
    ("customer_orientation",  "Customer Focus",     "💼"),
    ("earning_attitude",      "Earning Attitude",   "📈"),
)

# Section accent colours (RGB tuples for the PDF, hex strings for the UI)
SECTION_COLOURS_HEX: dict[str, tuple[str, str]] = {
    # (icon, hex colour)
    "professional summary":         ("📋", "#4f8ef7"),
    "summary":                      ("📋", "#4f8ef7"),
    "work experience":              ("💼", "#2ecc71"),
    "experience":                   ("💼", "#2ecc71"),
    "education & certifications":   ("🎓", "#9b59b6"),
    "education and certifications": ("🎓", "#9b59b6"),
    "education":                    ("🎓", "#9b59b6"),
    "core skills & tools":          ("🔧", "#e67e22"),
    "skills & tools":               ("🔧", "#e67e22"),
    "skills and tools":             ("🔧", "#e67e22"),
    "core skills":                  ("🔧", "#e67e22"),
    "skills":                       ("🔧", "#e67e22"),
    "languages known":              ("🗣", "#16a085"),
    "languages":                    ("🗣", "#16a085"),
    "objective":                    ("🎯", "#4f8ef7"),
}

SECTION_COLOURS_RGB: dict[str, tuple[int, int, int]] = {
    "professional summary":         (79, 142, 247),
    "summary":                      (79, 142, 247),
    "work experience":              (46, 204, 113),
    "experience":                   (46, 204, 113),
    "education & certifications":   (155, 89, 182),
    "education and certifications": (155, 89, 182),
    "education":                    (155, 89, 182),
    "core skills & tools":          (230, 126, 34),
    "skills & tools":               (230, 126, 34),
    "skills and tools":             (230, 126, 34),
    "core skills":                  (230, 126, 34),
    "skills":                       (230, 126, 34),
    "languages known":              (22, 160, 133),
    "languages":                    (22, 160, 133),
    "objective":                    (79, 142, 247),
}
