"""Tests for HealthCheckService — uses requests mocking, no real API calls."""

from __future__ import annotations

from unittest.mock import patch, MagicMock

from services.health_check_service import HealthCheckService


def _mock_ok_response(json_body: dict, status_code: int = 200):
    r = MagicMock()
    r.ok = status_code < 400
    r.status_code = status_code
    r.text = "OK"
    r.json.return_value = json_body
    return r


@patch("services.health_check_service.requests.post")
def test_all_green_when_apis_respond(mock_post, settings):
    mock_post.side_effect = [
        _mock_ok_response({"audios": ["..."]}),
        _mock_ok_response({
            "choices": [
                {"message": {"content": "ok"}, "finish_reason": "stop"}
            ]
        }),
    ]
    report = HealthCheckService(settings).run()
    assert report.all_ok
    assert len(report.results) == 3
    assert all(r.ok for r in report.results)


@patch("services.health_check_service.requests.post")
def test_llm_returns_no_content_flags_failure(mock_post, settings):
    mock_post.side_effect = [
        _mock_ok_response({"audios": ["..."]}),
        _mock_ok_response({
            "choices": [
                {"message": {"content": None}, "finish_reason": "length"}
            ]
        }),
    ]
    report = HealthCheckService(settings).run()
    assert not report.all_ok
    llm_result = next(r for r in report.results if "LLM" in r.name)
    assert llm_result.ok is False
    assert "no content" in llm_result.detail


def test_missing_api_key_is_flagged(tmp_path):
    from config.settings import Settings
    no_key = Settings(
        sarvam_api_key="",
        output_dir=tmp_path,
    )
    no_key.ensure_dirs()
    # Don't bother mocking the network — the API-key probe is a local check.
    with patch("services.health_check_service.requests.post") as mock_post:
        mock_post.return_value = _mock_ok_response({}, status_code=200)
        report = HealthCheckService(no_key).run()
    key_result = next(r for r in report.results if "API key" in r.name)
    assert key_result.ok is False
