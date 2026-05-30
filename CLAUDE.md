# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

श्रमसाथी AI — a voice-first interview bot for India's blue-collar workforce. Candidates speak in 6 Indian languages (en/hi/bn/te/pa/gu) for 4 roles (housekeeping, electrician, plumber, security guard); recruiters get an English ATS scorecard PDF. Built entirely on Sarvam AI's Indic stack (Saaras v3 STT, Bulbul v3 TTS, sarvam-30b LLM).

The actual product is the Streamlit web app. `main.py` only exists for CLI helpers like `--health-check`.

## Commands

```bash
# Launch the app (this is the product)
streamlit run ui/streamlit/app.py

# Pre-demo Sarvam connectivity probe (TTS + LLM, tiny payloads)
python main.py --health-check

# Tests — all mocked, no API key needed, ~0.4s
pytest
pytest -k recovery          # filter by name
pytest tests/test_evaluation_service.py::test_xyz   # one test

# One-time: re-bake assets/welcome.wav after editing SETUP_WELCOME_TEXT
python tools/regenerate_welcome.py
```

Requires `SARVAM_API_KEY` in `.env` (see `.env.example`). Tests do not.

## Architecture

The repo is structured as **UI-agnostic core + swappable presentation**. A new `ui/fastapi/` or `ui/cli/` could be added without touching `services/`.

**Layer rules (enforced by import discipline — do not violate):**
- `services/` never imports from `ui/`.
- `ui/streamlit/` imports `services/`, `models/`, `data/` — but no other UI package.
- LLM prompts live in `prompts/<feature>_prompt.py`, never inlined in service code.
- All hardcoded values (URLs, model IDs, timeouts, magic numbers) live in `constants/app_constants.py`. Translation strings live in `data/` because they're long-form content, not constants.

**Service composition:** `ui/streamlit/app.py::_build_services()` is the single composition root — it constructs each service once (via `@st.cache_resource`) and injects them into views. Services take `Settings` (or another service) in `__init__`. To add a service, follow this pattern and raise typed exceptions from `utils/exceptions.py`.

**Streamlit FSM** (in `ui/streamlit/app.py`, one view file per stage):
```
setup → profile_intro → profile → profile_building → profile_review
      → greeting → interview → closing → evaluating → report
```

**Two-bucket session state** (`ui/streamlit/state.py`): `_INTERVIEW_DEFAULTS` is wiped by `reset_interview()` between candidates; `_SESSION_DEFAULTS` (`welcome_unlocked`, `setup_welcome_played`, `_tts_cache`) is preserved across consecutive interviews so the welcome doesn't replay and TTS cache stays warm. Per-stage transient keys with dynamic suffixes (`played_*`, `processed_*_*`, `retry_*`, etc.) are listed as prefixes in `_STAGE_KEY_PREFIXES` and swept on reset. Defaults are deep-copied on assignment — without that, every interview would share the same list objects.

## Non-obvious constraints to respect

- **LLM `max_tokens` ceiling is 4096** on the starter Sarvam tier (`LLM_DEFAULT_MAX_TOKENS`). Don't raise it without upgrading the subscription. Devanagari/Hindi tokens consume ~3× the budget of English — `evaluation_service` deliberately retries in English when the first pass truncates.
- **Evaluation has partial-JSON regex recovery**: if the LLM truncates mid-JSON, scores + summary are still extracted. Preserve this behaviour when editing `evaluation_service.py`.
- **Profile building is deterministic, not LLM-driven** — `profile_service.py` uses the fixed `QUESTION_FIELD_ORDER` mapping in `constants/app_constants.py`. Q1 always maps to `contact_info`, Q2 to `location_and_age`, etc. Reordering profile questions in `data/interview_questions.py` will silently misalign fields unless `QUESTION_FIELD_ORDER` is updated in lockstep.
- **`MIN_REAL_AUDIO_BYTES = 6000`** — the browser mic widget can emit ~44-byte WAV stubs; anything < 6 KB is silence and would 400 from Sarvam STT. Guard before STT calls.
- **`MAX_FOLLOW_UPS_PER_QUESTION = 1`** — `decide_next_turn_service` enforces this; the interview loop assumes it.
- **`assets/welcome.wav` is pre-baked and committed.** It's not regenerated at runtime. If you change `SETUP_WELCOME_TEXT`, you must run `tools/regenerate_welcome.py` and commit the new WAV — otherwise the demo opens with stale audio.
- **Streamlit autoplay overlay**: `welcome_unlocked` gates the first audio play to satisfy browser autoplay policy. Don't bypass it.
- **`streamlit run ui/streamlit/app.py`** invokes the file directly, so `app.py` manually inserts the project root onto `sys.path`. Don't remove that block.

## Where to change things

| Change | File |
|---|---|
| Add a role | `data/interview_questions.py` → `QUESTION_BANK` (entry × 6 languages) |
| Add a language | `data/interview_questions.py` (`LANGUAGES` + every translated dict) |
| Tweak an LLM prompt | `prompts/<feature>_prompt.py` |
| Change a URL, model ID, timeout, threshold | `constants/app_constants.py` |
| Change welcome wording | `SETUP_WELCOME_TEXT` in `data/interview_questions.py` + re-bake `welcome.wav` |
| Add a profile question | `data/interview_questions.py` AND `QUESTION_FIELD_ORDER` in constants |

## Testing notes

`tests/conftest.py` builds a `Settings` with a fake key and `tmp_path` output dir; `mock_llm` fixture is a `MagicMock(spec=SarvamLlmService)` — script responses via `mock_llm.chat_completion.return_value = LlmCompletion(...)`. Tests never hit Sarvam.
# Project codebase structure

  Top-level layout (excluding venv/, __pycache__/, .git/, .pytest_cache/, generated output/):

  interview_bot/
  ├── main.py                          # CLI entry — only does --health-check
  ├── README.md                        # User-facing project doc
  ├── CLAUDE.md                        # Guidance for Claude Code
  ├── requirements.txt
  ├── .env.example                     # SARVAM_API_KEY, base URL, log level, output dir
  ├── .gitignore
  │
  ├── config/
  │   └── settings.py                  # pydantic-settings singleton; .env-driven
  │
  ├── constants/
  │   └── app_constants.py             # All URLs, model IDs, timeouts, magic numbers
  │
  ├── data/                            # Long-form translated content (not constants)
  │   ├── interview_questions.py       # QUESTION_BANK × 4 roles × 6 languages; SETUP_WELCOME_TEXT
  │   └── profile_questions.py         # The 9 onboarding questions (× 6 languages)
  │
  ├── models/
  │   └── schemas.py                   # Pydantic v2 I/O types
  │
  ├── prompts/                         # Every LLM prompt extracted from services
  │   ├── decide_next_turn_prompt.py
  │   ├── evaluation_prompt.py
  │   └── resume_prompt.py
  │
  ├── services/                        # ★ UI-agnostic business logic
  │   ├── sarvam_stt_service.py        # Saaras v3 STT
  │   ├── sarvam_tts_service.py        # Bulbul v3 TTS
  │   ├── sarvam_llm_service.py        # sarvam-30b chat completions
  │   ├── profile_service.py           # Deterministic Q→field profile builder (no LLM)
  │   ├── resume_service.py            # LLM resume + PDF, deterministic fallback
  │   ├── evaluation_service.py        # Scorecard; English retry + partial-JSON recovery
  │   ├── decide_next_turn_service.py  # Picks next question / follow-up
  │   └── health_check_service.py      # Pre-demo TTS + LLM probe
  │
  ├── utils/
  │   ├── logger.py                    # Centralised logging
  │   ├── exceptions.py                # Typed errors raised by services
  │   ├── helpers.py                   # Small shared helpers
  │   ├── gender_detector.py           # Pronoun selection for resume text
  │   └── pdf_renderer.py              # fpdf2 renderer for resumes + reports
  │
  ├── ui/                              # ★ Presentation layer — swappable
  │   └── streamlit/
  │       ├── app.py                   # Entry: page setup, service composition, FSM dispatch
  │       ├── state.py                 # Two-bucket session state (interview / session)
  │       ├── styles.py                # Global CSS injection
  │       ├── components.py            # Brand header + shared widgets
  │       └── views/                   # One file per FSM stage
  │           ├── setup_view.py
  │           ├── profile_intro_view.py
  │           ├── profile_view.py
  │           ├── profile_building_view.py
  │           ├── profile_review_view.py
  │           ├── greeting_view.py
  │           ├── interview_view.py
  │           ├── closing_view.py
  │           ├── evaluating_view.py
  │           └── report_view.py
  │
  ├── tests/                           # pytest, all Sarvam calls mocked
  │   ├── conftest.py                  # `settings` + `mock_llm` fixtures
  │   ├── test_evaluation_service.py
  │   ├── test_health_check_service.py
  │   ├── test_profile_service.py
  │   ├── test_resume_service.py
  │   ├── test_helpers.py
  │   └── integration/                 # (placeholder)
  │
  ├── tools/                           # One-shot scripts (not part of runtime)
  │   ├── regenerate_welcome.py        # Re-bakes assets/welcome.wav
  │   ├── generate_architecture_diagram.py
  │   └── generate_technical_ppt.py
  │
  ├── assets/
│   ├── logo.png
│   └── welcome.wav                  # Pre-baked TTS — committed to repo
│
└── output/                          # Gitignored generated artefacts
    ├── profile_<name>_<ts>.json     # Structured onboarding data
    ├── report_<name>_<ts>.json      # Scorecard JSON
    ├── resume_<name>_<ts>.pdf       # ATS resume
    ├── debug/                       # Raw LLM responses (LOG_LEVEL=DEBUG)
    └── temp/                        # Transient TTS/STT WAVs
The architectural shape

## Read it as three concentric rings:

1. config/ + constants/ + data/ + models/ + prompts/ — pure values. No I/O, no logic. Anything you'd want to change in one place lives here.
2. services/ — business logic, UI-agnostic. Each service takes Settings (or another service) in __init__, raises typed exceptions from utils/exceptions.py. The three sarvam_*_service.py files are the only modules that talk to the Sarvam REST API.
3. ui/streamlit/ — presentation. app.py composes services once (@st.cache_resource), then dispatches by st.session_state.stage to one views/<stage>_view.py per FSM stage.

Hard rule: services/ never imports from ui/. A new frontend slots in as ui/fastapi/ or ui/cli/ without touching the rest. main.py is just a thin CLI shim — the actual product is streamlit run ui/streamlit/app.py.
