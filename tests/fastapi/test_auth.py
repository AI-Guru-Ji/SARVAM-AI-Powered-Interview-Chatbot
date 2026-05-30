"""Demo-mode OTP flow tests."""


def test_otp_request_returns_demo_otp(client):
    r = client.post(
        "/v1/auth/otp/request",
        json={"phone": "9999988887", "language": "hi"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert data["demo_otp"] == "123456"


def test_otp_verify_with_demo_otp_returns_token(client):
    client.post(
        "/v1/auth/otp/request",
        json={"phone": "9999988887", "language": "hi"},
    )
    r = client.post(
        "/v1/auth/otp/verify",
        json={"phone": "9999988887", "otp": "123456"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert data["token"]
    assert data["candidate_phone"] == "9999988887"


def test_otp_verify_wrong_otp_returns_401(client):
    client.post(
        "/v1/auth/otp/request",
        json={"phone": "9999988887", "language": "hi"},
    )
    r = client.post(
        "/v1/auth/otp/verify",
        json={"phone": "9999988887", "otp": "000000"},
    )
    assert r.status_code == 401
