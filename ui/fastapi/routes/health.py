"""Health endpoint — quick liveness + Sarvam reachability probe."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from ui.fastapi.db import get_engine
from ui.fastapi.deps import ServiceContainer, get_services, is_demo_mode
from ui.fastapi.schemas import HealthResponse


router = APIRouter(prefix="/v1", tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health(services: ServiceContainer = Depends(get_services)) -> HealthResponse:
    db_ok = True
    try:
        get_engine().connect().close()
    except Exception:  # noqa: BLE001
        db_ok = False

    # Reuse the existing pre-demo health check service.
    sarvam_ok = True
    try:
        report = services.health.run()
        sarvam_ok = bool(getattr(report, "all_ok", True))
    except Exception:  # noqa: BLE001
        sarvam_ok = False

    return HealthResponse(
        ok=(db_ok and sarvam_ok),
        sarvam_ok=sarvam_ok,
        db_ok=db_ok,
        demo_mode=is_demo_mode(),
    )
