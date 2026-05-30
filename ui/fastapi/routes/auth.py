"""OTP-based phone authentication endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from ui.fastapi.auth import issue_otp, verify_otp
from ui.fastapi.deps import is_demo_mode
from ui.fastapi.schemas import (
    OtpRequest,
    OtpRequestResponse,
    OtpVerify,
    OtpVerifyResponse,
)


router = APIRouter(prefix="/v1/auth", tags=["auth"])


@router.post("/otp/request", response_model=OtpRequestResponse)
def request_otp(payload: OtpRequest) -> OtpRequestResponse:
    otp, is_demo = issue_otp(payload.phone)
    return OtpRequestResponse(
        ok=True,
        message=(
            "Demo mode: use 123456 (or any 9999xx)" if is_demo
            else "OTP sent via SMS"
        ),
        demo_otp=otp if is_demo else None,
    )


@router.post("/otp/verify", response_model=OtpVerifyResponse)
def verify(payload: OtpVerify) -> OtpVerifyResponse:
    token = verify_otp(payload.phone, payload.otp)
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired OTP",
        )
    return OtpVerifyResponse(ok=True, token=token, candidate_phone=payload.phone)
