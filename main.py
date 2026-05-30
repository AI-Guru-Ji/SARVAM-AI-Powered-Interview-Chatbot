"""
main.py — Entry point for the Blue Collar Interview Bot.

This file is intentionally thin. It handles argument parsing and
delegates to the appropriate runner. All business logic lives in the
``services/`` package; all UI lives in ``ui/<frontend>/``.

Usage::

    # Web UI (recommended — the actual product):
    streamlit run ui/streamlit/app.py

    # CLI helpers go through this main:
    python main.py --health-check        # Run pre-demo health check + exit
"""

from __future__ import annotations

import argparse
import sys

from config.settings import get_settings
from services.health_check_service import HealthCheckService
from utils.logger import get_logger


logger = get_logger(__name__)


def _run_health_check() -> int:
    """Execute the pre-demo health check from the terminal."""
    settings = get_settings()
    report = HealthCheckService(settings).run()
    print("\n=== Sarvam AI Health Check ===\n")
    for r in report.results:
        icon = "✓" if r.ok else "✗"
        latency = f"({r.latency_s:.1f}s)" if r.latency_s else ""
        print(f"{icon} {r.name:<30} {latency:>8}   {r.detail}")
    print()
    print("All systems responsive." if report.all_ok else "One or more checks failed.")
    return 0 if report.all_ok else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="interview_bot",
        description="Blue Collar Interview Bot — CLI helpers.",
    )
    parser.add_argument(
        "--health-check",
        action="store_true",
        help="Run the Sarvam AI health check and exit.",
    )
    args = parser.parse_args(argv)

    if args.health_check:
        return _run_health_check()

    print(
        "No CLI action requested.\n\n"
        "To launch the web app, run:\n"
        "    streamlit run ui/streamlit/app.py\n\n"
        "Available CLI flags: --health-check"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
