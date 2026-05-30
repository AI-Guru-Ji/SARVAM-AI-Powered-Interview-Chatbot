"""
app.py — FastAPI composition root for the mobile-app backend.

Run locally::

    cd <repo root>
    uvicorn ui.fastapi.app:app --reload --port 8000

This module is purely "wiring" — it instantiates the FastAPI app,
attaches middleware (CORS for the mobile client + a permissive logger),
and registers every router. Business logic lives in the service layer
and is reached through :mod:`ui.fastapi.deps`.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# When running ``uvicorn ui.fastapi.app:app`` the project root is not
# automatically on sys.path. Mirror the workaround that
# ui/streamlit/app.py uses.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from ui.fastapi.db import get_engine                       # noqa: E402
from ui.fastapi.routes import (                            # noqa: E402
    admin,
    answers,
    audio,
    auth,
    finalize,
    health,
    meta,
    reports,
    resume,
    sessions,
)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)


app = FastAPI(
    title="ShramSaathi AI — Mobile Backend",
    version="0.1.0",
    description=(
        "REST + multipart backend for the ShramSaathi AI Android app. "
        "Reuses the same services as the Streamlit recruiter dashboard "
        "via the UI-agnostic core."
    ),
)

# CORS is permissive in dev / demo; tighten before production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=False,
)


# ──────────────────────────────────────────────────────────────────────
# Routers
# ──────────────────────────────────────────────────────────────────────
app.include_router(health.router)
app.include_router(meta.router)
app.include_router(auth.router)
app.include_router(sessions.router)
app.include_router(answers.router)
app.include_router(audio.router)
app.include_router(resume.router)
app.include_router(finalize.router)
app.include_router(reports.router)
app.include_router(admin.router)


@app.on_event("startup")
def _startup() -> None:
    """Lazy DB init so we fail fast if the SQLite file is unwritable."""
    get_engine()


@app.get("/")
def root() -> dict:
    return {
        "service": "ShramSaathi AI mobile backend",
        "docs": "/docs",
        "health": "/v1/health",
        "config": "/v1/config",
    }
