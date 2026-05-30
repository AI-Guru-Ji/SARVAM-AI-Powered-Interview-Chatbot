"""
End-to-end flow test for the FastAPI backend.

Drives a session from creation through profile → interview →
behavioral → finalize → report, mocking every Sarvam call so the
test runs offline in ~1 second.
"""

from __future__ import annotations

import io

from constants.app_constants import BEHAVIORAL_QUESTION_COUNT
from data.interview_questions import QUESTION_BANK
from data.profile_questions import PROFILE_QUESTIONS
from ui.fastapi.state_machine import (
    STAGE_AWAITING_FINALIZE,
    STAGE_BEHAVIORAL,
    STAGE_COMPLETED,
    STAGE_INTERVIEW,
    STAGE_PROFILE,
)


def _dummy_wav() -> bytes:
    # 8KB of zero-padded RIFF header — passes the >6KB STT guard.
    return b"RIFF" + b"\x00" * 8000


def _post_answer(client, session_id: str):
    return client.post(
        f"/v1/sessions/{session_id}/answer",
        files={"audio": ("answer.wav", io.BytesIO(_dummy_wav()), "audio/wav")},
    )


def test_create_session_returns_first_profile_question(client):
    r = client.post(
        "/v1/sessions",
        json={
            "role": "housekeeping",
            "language": "hi",
            "candidate_name": "Rakesh",
            "candidate_phone": "9999988887",
            "recruiter_email": "recruiter@example.com",
        },
    )
    assert r.status_code == 201
    data = r.json()
    assert data["stage"] == STAGE_PROFILE
    assert data["candidate_name"] == "Rakesh"
    assert data["role"] == "housekeeping"
    assert data["current_question"] is not None
    assert data["current_question"]["text"]
    assert "/v1/sessions/" in data["current_question"]["audio_url"]


def test_get_session_returns_same_state(client):
    r = client.post("/v1/sessions", json={
        "role": "plumber", "language": "en", "candidate_name": "Sue",
    })
    sid = r.json()["session_id"]
    r2 = client.get(f"/v1/sessions/{sid}")
    assert r2.status_code == 200
    assert r2.json()["candidate_name"] == "Sue"


def test_create_session_rejects_unknown_role(client):
    r = client.post("/v1/sessions", json={
        "role": "astronaut", "language": "hi", "candidate_name": "X",
    })
    assert r.status_code == 400


def test_full_flow_advances_to_completed(client, mock_services):
    """Walk all the way from /sessions to /report.pdf using fake audio."""
    r = client.post("/v1/sessions", json={
        "role": "housekeeping", "language": "hi", "candidate_name": "Test",
    })
    assert r.status_code == 201
    sid = r.json()["session_id"]

    # 1) Profile loop — N questions
    for _ in range(len(PROFILE_QUESTIONS)):
        r = _post_answer(client, sid)
        assert r.status_code == 200, r.text

    # After the last profile Q we should now be in profile_review.
    # The backend builds the resume on this transition.
    state = client.get(f"/v1/sessions/{sid}").json()
    assert state["stage"] == "profile_review"
    assert state["is_terminal"] is True

    # 1b) /advance moves past the resume review into the interview
    r = client.post(f"/v1/sessions/{sid}/advance")
    assert r.status_code == 200, r.text
    state = client.get(f"/v1/sessions/{sid}").json()
    assert state["stage"] == STAGE_INTERVIEW

    # 2) Technical interview — N questions (decide service returns "next",
    #    so no follow-ups)
    tech_total = len(QUESTION_BANK["housekeeping"]["questions"])
    for _ in range(tech_total):
        r = _post_answer(client, sid)
        assert r.status_code == 200, r.text

    # After last technical Q we hit the BEHAVIORAL_INTRO gate (explicit
    # "Begin personality round" button). Advance past it.
    state = client.get(f"/v1/sessions/{sid}").json()
    assert state["stage"] == "behavioral_intro"
    r = client.post(f"/v1/sessions/{sid}/advance")
    assert r.status_code == 200, r.text

    state = client.get(f"/v1/sessions/{sid}").json()
    assert state["stage"] == STAGE_BEHAVIORAL

    # 3) Behavioral round
    for _ in range(BEHAVIORAL_QUESTION_COUNT):
        r = _post_answer(client, sid)
        assert r.status_code == 200, r.text

    state = client.get(f"/v1/sessions/{sid}").json()
    assert state["stage"] == STAGE_AWAITING_FINALIZE
    assert state["is_terminal"] is True
    assert state["current_question"] is None

    # 4) Finalize → runs both mocked evals + writes report JSON
    r = client.post(f"/v1/sessions/{sid}/finalize")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["stage"] == STAGE_COMPLETED
    assert body["final_report_url"]

    # 5) /report returns the populated scorecard
    r = client.get(f"/v1/sessions/{sid}/report")
    assert r.status_code == 200
    data = r.json()
    assert data["candidate_name"] == "Test"
    assert data["evaluation"]["overall_score"] == 8.0
    assert data["behavioral_eval"]["honesty"] == 8.0
    assert len(data["behavioral_transcripts"]) == BEHAVIORAL_QUESTION_COUNT


def test_finalize_before_done_returns_409(client):
    r = client.post("/v1/sessions", json={
        "role": "housekeeping", "language": "en", "candidate_name": "Test",
    })
    sid = r.json()["session_id"]
    r = client.post(f"/v1/sessions/{sid}/finalize")
    assert r.status_code == 409


def test_abort_deletes_session(client):
    r = client.post("/v1/sessions", json={
        "role": "housekeeping", "language": "en", "candidate_name": "Test",
    })
    sid = r.json()["session_id"]
    r = client.delete(f"/v1/sessions/{sid}")
    assert r.status_code == 204
    r = client.get(f"/v1/sessions/{sid}")
    assert r.status_code == 404


def test_get_audio_lazy_synthesizes(client):
    r = client.post("/v1/sessions", json={
        "role": "housekeeping", "language": "en", "candidate_name": "Test",
    })
    sid = r.json()["session_id"]
    r = client.get(f"/v1/sessions/{sid}/audio")
    assert r.status_code == 200
    assert r.headers["content-type"] == "audio/wav"
    assert r.content.startswith(b"RIFF")
