"""
notifier.py — Recruiter email notifications.

Uses Resend's HTTP API directly (no SDK) so the dependency footprint
stays small. ``RESEND_API_KEY`` set → live; absent → logs the message
and short-circuits, so the demo never has to ship credentials.

Email body intentionally includes:
  * Candidate name + role
  * Overall technical score + hire recommendation
  * Behavioral round summary (1-line if available)
  * Link to the full report
"""

from __future__ import annotations

import logging
from typing import Optional

import requests

from ui.fastapi.deps import resend_api_key


logger = logging.getLogger(__name__)


_RESEND_URL = "https://api.resend.com/emails"
_FROM_DEFAULT = "ShramSaathi <onboarding@resend.dev>"   # free testing sender


def notify_recruiter(
    *,
    recruiter_email: str,
    candidate_name: str,
    role: str,
    overall_score: Optional[float],
    hire_recommendation: Optional[bool],
    behavioral_summary: str,
    report_url: str,
) -> bool:
    """Send the post-interview notification. Returns True on real send,
    False when stubbed or on failure (never raises)."""
    if not recruiter_email:
        logger.info("notify_recruiter: no recruiter_email — skipping")
        return False

    key = resend_api_key()
    subject = (
        f"[Interview submitted] {candidate_name} · {role.title().replace('_', ' ')}"
    )
    body_html = _build_body_html(
        candidate_name=candidate_name,
        role=role,
        overall_score=overall_score,
        hire_recommendation=hire_recommendation,
        behavioral_summary=behavioral_summary,
        report_url=report_url,
    )

    if not key:
        # Demo path — log a structured representation of the email
        # so the demo audience can SEE what would have been sent.
        logger.info(
            "[DEMO EMAIL] to=%s subject=%s body_html=%s",
            recruiter_email, subject, body_html,
        )
        return False

    try:
        r = requests.post(
            _RESEND_URL,
            headers={"Authorization": f"Bearer {key}"},
            json={
                "from": _FROM_DEFAULT,
                "to": [recruiter_email],
                "subject": subject,
                "html": body_html,
            },
            timeout=15,
        )
        r.raise_for_status()
        logger.info("Recruiter email sent to %s", recruiter_email)
        return True
    except Exception as e:  # noqa: BLE001
        logger.warning("notify_recruiter failed: %s", e)
        return False


def _build_body_html(
    *,
    candidate_name: str,
    role: str,
    overall_score: Optional[float],
    hire_recommendation: Optional[bool],
    behavioral_summary: str,
    report_url: str,
) -> str:
    score_str = f"{overall_score:.1f} / 10" if overall_score is not None else "—"
    if hire_recommendation is True:
        verdict = '<span style="color:#10b981;font-weight:700">✓ Recommended</span>'
    elif hire_recommendation is False:
        verdict = '<span style="color:#ef4444;font-weight:700">✕ Not recommended</span>'
    else:
        verdict = '<span style="color:#71717a">No verdict</span>'

    return f"""\
<div style="font-family:'Inter',Helvetica,Arial,sans-serif;max-width:520px;
            line-height:1.5;color:#27272a">
  <h2 style="margin:0 0 12px">Interview submitted</h2>
  <p style="margin:0 0 16px;color:#71717a">A new candidate has finished
     their ShramSaathi AI interview. Quick summary below.</p>

  <table style="border-collapse:collapse;width:100%;font-size:14px">
    <tr><td style="padding:4px 0;color:#71717a">Candidate</td>
        <td style="padding:4px 0;font-weight:600">{candidate_name}</td></tr>
    <tr><td style="padding:4px 0;color:#71717a">Role</td>
        <td style="padding:4px 0">{role.replace('_', ' ').title()}</td></tr>
    <tr><td style="padding:4px 0;color:#71717a">Overall score</td>
        <td style="padding:4px 0;font-weight:700;font-size:18px">{score_str}</td></tr>
    <tr><td style="padding:4px 0;color:#71717a">Verdict</td>
        <td style="padding:4px 0">{verdict}</td></tr>
  </table>

  {('<p style="margin:16px 0;padding:10px 12px;background:#f4f4f5;'
    f'border-radius:8px"><strong>Trust profile:</strong> {behavioral_summary}</p>')
    if behavioral_summary else ''}

  <p style="margin:24px 0">
    <a href="{report_url}" style="display:inline-block;padding:10px 18px;
       background:#6366f1;color:white;text-decoration:none;border-radius:8px;
       font-weight:600">View full scorecard →</a>
  </p>

  <p style="margin:24px 0 0;color:#a1a1aa;font-size:12px">
    This email was sent by ShramSaathi AI on behalf of your interview workflow.
  </p>
</div>
"""
