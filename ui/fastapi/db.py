"""
db.py — Tiny SQLite session store for the FastAPI backend.

One table — ``sessions`` — that holds an entire interview's state as a
JSON blob. This is intentionally the simplest persistence we can ship:
no migrations, no joins, no ORM relationships, just key-value rows.

The schema is identical between SQLite (MVP / demo) and Postgres
(production). To migrate, set ``SARVAM_BACKEND_DB_URL`` to a Postgres
DSN and the same SQLAlchemy code Just Works.

The state JSON shape is owned by :mod:`ui.fastapi.state_machine` — this
module knows nothing about the FSM. We persist `dict[str, Any]` and let
the FSM be the single source of truth for its shape.
"""

from __future__ import annotations

import json
import os
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Optional

from sqlalchemy import (
    Column,
    DateTime,
    String,
    Text,
    create_engine,
    select,
)
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


# ──────────────────────────────────────────────────────────────────────
# Engine / session factory (lazy)
# ──────────────────────────────────────────────────────────────────────
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def _resolve_db_url() -> str:
    """Resolve the database URL.

    Priority:
      1. ``SARVAM_BACKEND_DB_URL`` env var (production / Postgres).
      2. ``output/sessions.db`` SQLite file (demo / MVP).
    """
    explicit = os.getenv("SARVAM_BACKEND_DB_URL", "").strip()
    if explicit:
        return explicit
    db_path = _PROJECT_ROOT / "output" / "sessions.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{db_path}"


_engine = None
_SessionFactory: Optional[sessionmaker] = None


def get_engine():
    """Return (and lazily create) the SQLAlchemy engine."""
    global _engine, _SessionFactory
    if _engine is None:
        url = _resolve_db_url()
        connect_args = (
            {"check_same_thread": False} if url.startswith("sqlite") else {}
        )
        _engine = create_engine(url, connect_args=connect_args, future=True)
        _SessionFactory = sessionmaker(
            bind=_engine, expire_on_commit=False, future=True,
        )
        Base.metadata.create_all(_engine)
    return _engine


# ──────────────────────────────────────────────────────────────────────
# Schema
# ──────────────────────────────────────────────────────────────────────
class Base(DeclarativeBase):
    pass


class SessionRow(Base):
    __tablename__ = "sessions"

    id: str = Column(String(36), primary_key=True)
    candidate_phone: str = Column(String(20), nullable=False, default="")
    recruiter_email: str = Column(String(255), nullable=False, default="")
    state_json: str = Column(Text, nullable=False)
    created_at: datetime = Column(DateTime(timezone=True), nullable=False)
    updated_at: datetime = Column(DateTime(timezone=True), nullable=False)


# ──────────────────────────────────────────────────────────────────────
# CRUD helpers — call these from routes / state_machine
# ──────────────────────────────────────────────────────────────────────
@contextmanager
def _open_session() -> Iterator[Session]:
    get_engine()
    assert _SessionFactory is not None
    with _SessionFactory() as s:
        yield s


def create_session(
    *,
    state: dict,
    candidate_phone: str = "",
    recruiter_email: str = "",
) -> str:
    """Insert a new session row and return its UUID."""
    sid = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    with _open_session() as s:
        s.add(SessionRow(
            id=sid,
            candidate_phone=candidate_phone,
            recruiter_email=recruiter_email,
            state_json=json.dumps(state, ensure_ascii=False),
            created_at=now,
            updated_at=now,
        ))
        s.commit()
    return sid


def load_session(session_id: str) -> Optional[tuple[dict, str, str]]:
    """Load (state, candidate_phone, recruiter_email) by id, or None."""
    with _open_session() as s:
        row = s.get(SessionRow, session_id)
        if row is None:
            return None
        return (
            json.loads(row.state_json),
            row.candidate_phone or "",
            row.recruiter_email or "",
        )


def save_state(session_id: str, state: dict) -> None:
    """Overwrite the state JSON for an existing session."""
    with _open_session() as s:
        row = s.get(SessionRow, session_id)
        if row is None:
            raise KeyError(f"session {session_id!r} not found")
        row.state_json = json.dumps(state, ensure_ascii=False)
        row.updated_at = datetime.now(timezone.utc)
        s.commit()


def delete_session(session_id: str) -> bool:
    """Hard-delete a session row. Returns True if a row was removed."""
    with _open_session() as s:
        row = s.get(SessionRow, session_id)
        if row is None:
            return False
        s.delete(row)
        s.commit()
        return True


def list_sessions(limit: int = 50) -> list[dict]:
    """Return recent sessions ordered by updated_at desc. For admin/debug."""
    with _open_session() as s:
        stmt = (
            select(SessionRow)
            .order_by(SessionRow.updated_at.desc())
            .limit(limit)
        )
        return [
            {
                "id": r.id,
                "candidate_phone": r.candidate_phone,
                "recruiter_email": r.recruiter_email,
                "created_at": r.created_at.isoformat(),
                "updated_at": r.updated_at.isoformat(),
                "stage": json.loads(r.state_json).get("stage"),
            }
            for r in s.scalars(stmt).all()
        ]
