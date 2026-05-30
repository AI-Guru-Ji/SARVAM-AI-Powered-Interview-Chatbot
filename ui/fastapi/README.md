# ShramSaathi AI — Mobile Backend (FastAPI)

REST + multipart backend that powers the Android candidate app. Reuses
the same UI-agnostic services as the Streamlit recruiter dashboard via
the layering rules in `CLAUDE.md`.

This is the **Week 1 deliverable** of the mobile-app project — a
working backend that drives an entire interview via HTTP. The Android
client (Flutter) consumes these endpoints from `Week 2` onwards.

## Quickstart (local dev)

```bash
# 1. Install deps (one-time)
venv/bin/pip install -r requirements.txt

# 2. Set Sarvam credentials (if not already in .env)
echo 'SARVAM_API_KEY=your-key-here' >> .env

# 3. Run the backend
venv/bin/uvicorn ui.fastapi.app:app --reload --port 8000

# 4. Visit http://127.0.0.1:8000/docs for interactive Swagger UI.
```

By default the server runs in **DEMO_MODE=1** which:
- bypasses Firebase OTP (any 6-digit OTP is accepted; the
  fixed value `123456` is also always valid),
- stubs Resend email notifications (logs the body instead of sending),
- uses local SQLite at `output/sessions.db`.

To toggle off, set `DEMO_MODE=0` and supply real `FIREBASE_*` /
`RESEND_API_KEY` environment variables.

## Environment variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `SARVAM_API_KEY` | Yes (live) | — | Sarvam subscription key (shared with Streamlit) |
| `DEMO_MODE` | No | `1` | Stub OTP + email; safe for demos |
| `SARVAM_BACKEND_DB_URL` | No | `sqlite:///output/sessions.db` | SQLAlchemy URL — use a Postgres DSN in production |
| `SARVAM_BACKEND_API_KEY` | No | empty | When set, all routes require `Authorization: Bearer <key>` |
| `RESEND_API_KEY` | No | empty | Triggers real recruiter emails when present |
| `LOG_LEVEL` | No | `INFO` | Standard Python logging level |

## Endpoint reference (v1)

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/v1/health` | Liveness + Sarvam reachability + DB ping |
| `GET` | `/v1/config` | Supported roles + languages + question counts |
| `POST` | `/v1/auth/otp/request` | Send (or stub) an OTP for a phone number |
| `POST` | `/v1/auth/otp/verify` | Verify the OTP; returns a bearer token |
| `POST` | `/v1/sessions` | Create a new interview session |
| `GET` | `/v1/sessions/{id}` | Current FSM stage + current question + audio URL |
| `DELETE` | `/v1/sessions/{id}` | Abort + delete |
| `POST` | `/v1/sessions/{id}/answer` | Multipart upload of the candidate's WAV; advances the FSM |
| `GET` | `/v1/sessions/{id}/audio` | Stream WAV for the current question (lazy-generated) |
| `GET` | `/v1/sessions/{id}/audio/{filename}` | Stream a specific cached WAV file |
| `POST` | `/v1/sessions/{id}/finalize` | Run BOTH evaluations + write report JSON + email recruiter |
| `GET` | `/v1/sessions/{id}/report` | Recruiter-side JSON scorecard |
| `GET` | `/v1/sessions/{id}/report.pdf` | Recruiter-side dashboard PDF |

OpenAPI / Swagger UI is served at `/docs` with the full schema.

## FSM stages (server-side)

```
profile  →  interview  →  behavioral  →  awaiting_finalize
                                              ↓
                                          evaluating  →  completed
```

The Streamlit-specific "intro" / "outro" / "review" splash stages are
collapsed because they're pure UI screens with no server work — the
mobile client renders those on its own.

## Smoke test with `curl`

```bash
# Reachability
curl -s http://127.0.0.1:8000/v1/health | jq

# Get supported roles + languages
curl -s http://127.0.0.1:8000/v1/config | jq

# Demo-mode OTP flow
curl -s -X POST http://127.0.0.1:8000/v1/auth/otp/request \
     -H 'Content-Type: application/json' \
     -d '{"phone":"9999988887","language":"hi"}' | jq

curl -s -X POST http://127.0.0.1:8000/v1/auth/otp/verify \
     -H 'Content-Type: application/json' \
     -d '{"phone":"9999988887","otp":"123456"}' | jq

# Create a session
SID=$(curl -s -X POST http://127.0.0.1:8000/v1/sessions \
       -H 'Content-Type: application/json' \
       -d '{"role":"electrician","language":"hi","candidate_name":"Demo",
            "candidate_phone":"9999988887",
            "recruiter_email":"recruiter@example.com"}' | jq -r .session_id)
echo "session id = $SID"

# Download the current question's TTS WAV
curl -s "http://127.0.0.1:8000/v1/sessions/$SID/audio" \
     -o /tmp/q.wav && file /tmp/q.wav

# Upload an answer (any WAV will do for STT)
curl -s -X POST "http://127.0.0.1:8000/v1/sessions/$SID/answer" \
     -F 'audio=@/tmp/q.wav' | jq

# … repeat /answer until stage = awaiting_finalize, then …
curl -s -X POST "http://127.0.0.1:8000/v1/sessions/$SID/finalize" | jq

# Recruiter side
curl -s "http://127.0.0.1:8000/v1/sessions/$SID/report" | jq
curl -s "http://127.0.0.1:8000/v1/sessions/$SID/report.pdf" -o /tmp/r.pdf
```

## Tests

```bash
venv/bin/python -m pytest tests/fastapi/ -q
```

12 integration tests, all offline (Sarvam calls mocked). Total runtime
~1 second.

## Architecture (one-screen view)

```
┌─────────────────────────┐
│   ui/fastapi/           │   ← New (this dir). HTTP wiring only.
│     app.py              │     Composition root.
│     deps.py             │     Service container (lru_cached singleton).
│     auth.py             │     OTP stub + bearer-token gate.
│     state_machine.py    │     Server FSM (replicates Streamlit FSM).
│     db.py               │     SQLite session store.
│     notifier.py         │     Resend email (stubbed in demo).
│     schemas.py          │     Wire-format Pydantic models.
│     routes/             │     One module per route group.
└────────────┬────────────┘
             │ depends on (reuses unchanged)
             ▼
┌─────────────────────────┐
│   services/             │   ← UI-agnostic core. No changes.
│   models/               │
│   prompts/              │
│   data/                 │
│   constants/            │
│   config/               │
└─────────────────────────┘
```

Per `CLAUDE.md`: `services/` never imports from `ui/`. The new FastAPI
layer is purely additive — the existing Streamlit app continues to work
unchanged.

## Hosting (free-tier MVP path)

| Resource | Free tier choice | Upgrade after winning the deal |
|---|---|---|
| Compute | Render.com free web service | Google Cloud Run (Mumbai) |
| DB | SQLite (file in `output/`) | Cloud SQL Postgres |
| Auth | Demo stub | Firebase Phone Auth |
| Email | Demo log-only | Resend paid plan |
| Object storage | Local FS on Render | S3-equivalent |

Zero code change between tiers — only environment variables flip.

## Known limitations (Week 1 scope)

These are deferred to Phase 2 of the mobile project, not bugs to file:

- **No voice confirmation** for HIGH_RISK_FIELDS (name / mobile / age /
  location). The Streamlit app does an extract → TTS read-back → yes/no
  STT sub-FSM; the mobile MVP captures raw transcript only. Recruiters
  edit values from the dashboard.
- **No empty-answer retry** at the API level. If STT returns empty
  text, the FSM still advances. The client should let the candidate
  re-record before uploading.
- **No session resume across app restarts** on the client side — the
  backend tolerates it (state is in SQLite), but the Flutter app
  doesn't yet show "you have an interview in progress" on relaunch.
- **No rate limiting / abuse protection**. Add Cloud Armor or
  Cloudflare in production.
