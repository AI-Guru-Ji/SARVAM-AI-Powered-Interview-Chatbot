"""Smoke tests for /v1/health and /v1/config."""


def test_health_returns_ok(client):
    r = client.get("/v1/health")
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert data["demo_mode"] is True
    assert data["db_ok"] is True


def test_config_lists_roles_and_languages(client):
    r = client.get("/v1/config")
    assert r.status_code == 200
    data = r.json()
    assert data["behavioral_question_count"] == 5
    # All 4 known roles should appear
    role_keys = {r["key"] for r in data["roles"]}
    assert {"housekeeping", "electrician", "plumber", "security_guard"} <= role_keys
    # All 11 supported languages should appear
    lang_codes = {l["code"] for l in data["languages"]}
    assert {"en", "hi", "bn", "te", "pa", "gu", "kn", "ml", "mr", "od", "ta"} <= lang_codes
