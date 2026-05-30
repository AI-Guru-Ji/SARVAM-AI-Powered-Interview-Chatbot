"""
auth.py — OTP-based phone authentication.

For MVP / demo we ship a **stub** OTP flow:

* ``DEMO_MODE=1`` (default) — any call to ``/auth/otp/request`` returns
  the same fixed OTP ``123456``. ``/auth/otp/verify`` accepts that OTP
  (or any 6-digit code starting with ``9999`` for QA scripts).
* When ``DEMO_MODE=0`` we ALSO fall back to the stub unless a Firebase
  Admin SDK is configured — that's where production integration plugs
  in. The interface is identical so flipping the env flag is the only
  change required.

Tokens are opaque random strings stored in an in-memory dict for the
lifetime of the process. For production they'd live in Redis or a
short-TTL Postgres table — but in demo mode the process restart cost
is acceptable.
"""

from __future__ import annotations

import secrets
import time
from typing import Optional

from fastapi import Header, HTTPException, status

from ui.fastapi.deps import api_key, is_demo_mode


# ──────────────────────────────────────────────────────────────────────
# Stub OTP store
# ──────────────────────────────────────────────────────────────────────
_DEMO_OTP_FIXED = "123456"

# phone → (otp, expires_at_unix)
_pending_otps: dict[str, tuple[str, float]] = {}
# token → (phone, issued_at_unix)
_active_tokens: dict[str, tuple[str, float]] = {}

_OTP_TTL_SECONDS = 5 * 60
_TOKEN_TTL_SECONDS = 24 * 3600


# ──────────────────────────────────────────────────────────────────────
# Public API used by routes/auth.py
# ──────────────────────────────────────────────────────────────────────
def issue_otp(phone: str) -> tuple[str, bool]:
    """Generate (or stub) an OTP for the given phone.

    Returns ``(otp_value, is_demo)``. The route handler may surface
    ``otp_value`` to the caller only when ``is_demo`` is True.
    """
    if is_demo_mode():
        otp = _DEMO_OTP_FIXED
        _pending_otps[phone] = (otp, time.time() + _OTP_TTL_SECONDS)
        return otp, True

    # Production stub (Firebase plug-in goes here).
    otp = f"{secrets.randbelow(900000) + 100000}"
    _pending_otps[phone] = (otp, time.time() + _OTP_TTL_SECONDS)
    # TODO: dispatch SMS via Firebase Phone Auth
    return otp, False


def verify_otp(phone: str, otp: str) -> Optional[str]:
    """If ``(phone, otp)`` matches a non-expired entry (or we're in
    demo mode), return a freshly minted bearer token. Otherwise None."""
    if is_demo_mode():
        # Accept the fixed demo OTP or any 6-digit string starting 9999*
        if otp == _DEMO_OTP_FIXED or otp.startswith("9999"):
            return _mint_token(phone)
        # Fall through to the regular check too — for testers that prefer
        # the "real" OTP flow even in demo mode.

    entry = _pending_otps.get(phone)
    if entry is None:
        return None
    expected, expires_at = entry
    if otp != expected or time.time() > expires_at:
        return None
    _pending_otps.pop(phone, None)
    return _mint_token(phone)


def _mint_token(phone: str) -> str:
    token = secrets.token_urlsafe(32)
    _active_tokens[token] = (phone, time.time())
    return token


def phone_for_token(token: str) -> Optional[str]:
    entry = _active_tokens.get(token)
    if entry is None:
        return None
    phone, issued_at = entry
    if time.time() - issued_at > _TOKEN_TTL_SECONDS:
        _active_tokens.pop(token, None)
        return None
    return phone


# ──────────────────────────────────────────────────────────────────────
# FastAPI dependency — call as ``Depends(require_api_key)``
# ──────────────────────────────────────────────────────────────────────
def require_api_key(
    authorization: str | None = Header(default=None),
) -> str:
    """Optional bearer-token gate. When ``SARVAM_BACKEND_API_KEY`` is set
    we enforce it; otherwise this is a no-op so local dev is friction-free.

    Returns the bearer token (or empty string) so downstream handlers
    can correlate to a candidate phone if they need to.
    """
    expected = api_key()
    if not expected:
        # Auth disabled — return whatever bearer was supplied (may be a
        # candidate's OTP token; routes can resolve it via phone_for_token).
        if authorization and authorization.startswith("Bearer "):
            return authorization[7:]
        return ""

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization: Bearer header",
        )
    token = authorization[7:]
    # Accept either the static API key OR a valid OTP-issued token.
    if token != expected and phone_for_token(token) is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid bearer token",
        )
    return token
