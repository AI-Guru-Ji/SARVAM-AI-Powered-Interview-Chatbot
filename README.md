# श्रमसाथी AI

> Voice-first hiring for India's blue-collar workforce.
> Built on Sarvam AI · 6 Indian languages · ATS-ready output.

---

## What it does

A web app that runs an end-to-end voice interview for blue-collar roles
(housekeeping, electrician, plumber, security guard). Candidates speak in
their own language. Recruiters get a structured English scorecard.

Three steps:

1. **Onboarding** — 9 voice questions in the candidate's language capture
   contact, age, education, experience, salary, availability.
2. **Resume** — an ATS-ready English PDF is auto-generated from the conversation.
3. **Interview** — 5 role-specific voice questions with dynamic follow-ups,
   ending in a scored recruiter report.

**Languages:** English · Hindi · Bengali · Telugu · Punjabi · Gujarati
**Roles:** Housekeeping · Electrician · Plumber · Security Guard

---

## Why it exists

Most blue-collar candidates in India have limited literacy and don't speak
English. Most HR / ATS systems expect typed English input. श्रमसाथी AI
bridges the gap — candidates speak naturally in their own language, and
the recruiter receives clean structured data they can act on.

---

## Run it

### 1. Setup

```bash
cd interview_bot
python -m venv venv && source venv/bin/activate     # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                 # paste your Sarvam key
```

Get a Sarvam key at <https://dashboard.sarvam.ai>.

### 2. One-time: bake the welcome audio

```bash
python tools/regenerate_welcome.py
```
Re-run only when you change `SETUP_WELCOME_TEXT` in
[data/interview_questions.py](data/interview_questions.py).

### 3. Launch

```bash
streamlit run ui/streamlit/app.py
```

Opens at <http://localhost:8501>.

### 4. (Optional) Pre-demo health check

```bash
python main.py --health-check
```

Probes Sarvam TTS + LLM with tiny payloads.

---

## Configuration

| Variable | Required | Default | Notes |
|---|---|---|---|
| `SARVAM_API_KEY` | ✅ | — | Sarvam subscription key |
| `SARVAM_BASE_URL` |  | `https://api.sarvam.ai` | Sandbox override |
| `LOG_LEVEL` |  | `INFO` | `DEBUG` / `INFO` / `WARNING` / `ERROR` |
| `OUTPUT_DIR` |  | `<project>/output` | Where resumes, reports, debug snapshots go |

---

## Architecture

A **UI-agnostic core** + a **swappable presentation layer**. Drop in
`ui/<your-stack>/` to replace Streamlit; the rest never changes.

```
interview_bot/
├── main.py                       # CLI entry (--health-check)
├── config/settings.py            # pydantic-settings, .env-driven
├── constants/app_constants.py    # all URLs, model names, magic numbers, colours
├── data/                         # translated questions & messages
├── models/schemas.py             # Pydantic v2 I/O types
├── prompts/                      # every LLM prompt extracted
├── services/                     # ★ UI-agnostic business logic
│   ├── sarvam_{stt,tts,llm}_service.py
│   ├── profile_service.py        # deterministic profile builder (no LLM)
│   ├── resume_service.py         # LLM resume + PDF, deterministic fallback
│   ├── evaluation_service.py     # scorecard, with retry + JSON recovery
│   ├── decide_next_turn_service.py
│   └── health_check_service.py
├── utils/                        # logger, exceptions, helpers, pdf_renderer
├── ui/streamlit/                 # ★ presentation layer (replaceable)
│   ├── app.py                    # FSM dispatcher
│   ├── state.py, styles.py, components.py
│   └── views/                    # one file per stage
├── tests/                        # mocked unit tests
├── assets/                       # logo, welcome.wav
├── tools/                        # one-shot regeneration scripts
└── output/                       # generated artefacts (gitignored)
```

**Layer rules** (enforced by import discipline):

- `services/` never imports from `ui/`.
- `ui/streamlit/` imports services, models, data — but no other UI.
- A new `ui/fastapi/` or `ui/cli/` slots in without touching business logic.

**Stage machine** (Streamlit FSM):

```
setup → profile_intro → profile → profile_building → profile_review
      → greeting → interview → closing → evaluating → report
```

### Reliability features (battle-scars)

- **Auto-retry on LLM token-budget failures** — evaluation retries in
  English (~3× more token-efficient) when Hindi/Devanagari output busts
  the 4096-token cap.
- **Partial-JSON regex recovery** — scores + summary survive when the
  LLM truncates mid-JSON.
- **Deterministic profile builder** — zero LLM calls; profile is built
  from a fixed question → field mapping.
- **Pre-baked welcome audio** — `assets/welcome.wav` ships with the
  repo; demo opens with zero Sarvam latency.
- **Click-to-begin overlay** — satisfies browser autoplay policy so
  voice always plays on the first interaction.
- **Two-bucket state model** — `reset_interview()` clears one
  candidate's data without wiping the welcome-unlock flag or TTS cache,
  so back-to-back interviews don't replay the intro or leak history.
- **Graceful retry UI** — failed evaluations show a "Retry Evaluation"
  screen, never a Python traceback.

---

## Tests

```bash
pytest                # all unit tests, mocked, no API key needed
pytest -k recovery    # filter by name
pytest -v             # verbose
```

47 tests · ~0.4s · `tests/conftest.py` mocks Sarvam via `unittest.mock`.

---

## Extending

| Want to… | Where to change it |
|---|---|
| Add a role | `data/interview_questions.py` → `QUESTION_BANK` (one entry × 6 languages) |
| Add a language | `data/interview_questions.py` (`LANGUAGES`, plus every translated dict) |
| Change an LLM prompt | `prompts/<feature>_prompt.py` — never inline in services |
| Tune a constant (URL, timeout, model name, colour) | `constants/app_constants.py` |
| Change the welcome text | Edit `SETUP_WELCOME_TEXT`, then re-run `python tools/regenerate_welcome.py` |
| Add an LLM service | `services/<feature>_service.py` — accept `Settings` in `__init__`, raise custom exceptions from `utils/exceptions.py` |
| Swap Streamlit for FastAPI / React | Add `ui/<your-stack>/`. Call the same services. Done. |

---

## Tech stack

| Layer | Tech |
|---|---|
| Web UI | Streamlit + `audio_recorder_streamlit` |
| STT | Sarvam **Saaras v3** |
| TTS | Sarvam **Bulbul v3** |
| LLM | Sarvam **sarvam-30b** (reasoning, `effort=low`) |
| PDF | `fpdf2` (pure Python) |
| Config | `pydantic-settings` |
| Tests | `pytest` + `unittest.mock` |

---

## License

Built on top of Sarvam AI's Indic-language voice + LLM stack. Designed
for Indian blue-collar hiring: spoken interviews in native languages,
candidates with limited literacy, HR systems that expect English ATS
output.
# shramsaathi-ai
