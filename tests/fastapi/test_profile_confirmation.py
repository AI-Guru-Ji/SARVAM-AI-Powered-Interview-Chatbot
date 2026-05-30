"""
Tests for the voice-confirmation sub-FSM on HIGH_RISK_FIELDS.

The first profile question is "What is your full name?" — `name` is a
HIGH_RISK_FIELD, so after the raw answer the backend should emit a
read-back prompt and wait for yes/no. These tests drive the flow with
mocked STT returning either a substantive name (triggers confirmation)
OR a yes/no token (resolves confirmation).
"""

from __future__ import annotations

import io

from models.schemas import SttResult


def _wav() -> bytes:
    return b"RIFF" + b"\x00" * 8000


def _post(client, sid: str):
    return client.post(
        f"/v1/sessions/{sid}/answer",
        files={"audio": ("a.wav", io.BytesIO(_wav()), "audio/wav")},
    )


def _set_stt(mock_services, text: str):
    mock_services.stt.speech_to_text.return_value = SttResult(
        transcript=text, language_code="hi-IN",
    )


def test_confirmation_yes_path_accepts_extracted_value(client, mock_services):
    """name → readback → 'haan' → stores extracted_value, advances."""
    mock_services.profile_extract.extract.return_value = "Ramesh Kumar"

    r = client.post("/v1/sessions", json={
        "role": "housekeeping", "language": "hi", "candidate_name": "Demo",
    })
    sid = r.json()["session_id"]

    # 1) Answer the name question → backend should switch to read-back
    _set_stt(mock_services, "मेरा नाम रमेश कुमार है")
    r = _post(client, sid)
    body = r.json()
    assert r.status_code == 200
    # Read-back text contains the extracted value
    assert "Ramesh Kumar" in body["current_question"]["text"]

    # 2) Candidate says "haan" → backend accepts, advances to Q2 (mobile)
    _set_stt(mock_services, "haan ji bilkul")
    r = _post(client, sid)
    body = r.json()
    assert r.status_code == 200
    # The next question must NOT contain the previous read-back
    assert "Ramesh Kumar" not in body["current_question"]["text"]
    # Session state should now have a stored extracted_value for name
    state = client.get(f"/v1/sessions/{sid}").json()
    assert state["stage"] == "profile"   # still in profile, Q2 now


def test_confirmation_no_re_asks_question(client, mock_services):
    """name → readback → 'nahi' → re-ask original Q (not advance)."""
    mock_services.profile_extract.extract.return_value = "Ramesh Kumar"

    r = client.post("/v1/sessions", json={
        "role": "housekeeping", "language": "hi", "candidate_name": "Demo",
    })
    sid = r.json()["session_id"]

    # 1) Answer name → goes to confirm. Capture the read-back text so we
    #    can verify the re-ask is NOT the read-back.
    _set_stt(mock_services, "मेरा नाम रमेश कुमार है")
    r = _post(client, sid)
    readback_text = r.json()["current_question"]["text"]
    assert "Ramesh Kumar" in readback_text   # confirms we're in read-back

    # 2) Candidate says "nahi" → re-ask original question
    _set_stt(mock_services, "nahi galat")
    r = _post(client, sid)
    body = r.json()
    assert r.status_code == 200
    # Should be back to the name question (not the read-back).
    assert "Ramesh Kumar" not in body["current_question"]["text"]
    assert "नाम" in body["current_question"]["text"]   # Hindi "name"


def test_confirmation_no_exhausted_auto_accepts(client, mock_services):
    """After MAX_RETRIES 'no's, backend auto-accepts and advances."""
    from constants.app_constants import PROFILE_CONFIRM_MAX_RETRIES
    mock_services.profile_extract.extract.return_value = "Ramesh Kumar"

    r = client.post("/v1/sessions", json={
        "role": "housekeeping", "language": "hi", "candidate_name": "Demo",
    })
    sid = r.json()["session_id"]
    original_q = r.json()["current_question"]["text"]

    # Burn through all the retries
    for _ in range(PROFILE_CONFIRM_MAX_RETRIES):
        _set_stt(mock_services, "मेरा नाम रमेश कुमार है")
        _post(client, sid)
        _set_stt(mock_services, "nahi galat")
        _post(client, sid)

    # One more "name" submission → backend goes to read-back again
    _set_stt(mock_services, "मेरा नाम रमेश कुमार है")
    _post(client, sid)
    # And one more "nahi" — retries exhausted, should auto-accept + advance
    _set_stt(mock_services, "nahi galat")
    r = _post(client, sid)
    body = r.json()
    assert r.status_code == 200
    assert body["current_question"]["text"] != original_q  # advanced
