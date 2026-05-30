"""
admin.py — Read-only admin endpoints.

  GET  /v1/admin/sessions        JSON list of all interview sessions
                                 (most recent first), with summary
                                 scores when a finalize has completed.
  GET  /admin                    Simple HTML dashboard rendering the
                                 same data — bookmark this URL to
                                 watch stakeholder testing live.
"""

from __future__ import annotations

import html as _html
import json
from typing import Optional

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from ui.fastapi import db
from ui.fastapi.auth import require_api_key


router = APIRouter(tags=["admin"])


# ──────────────────────────────────────────────────────────────────────
# JSON endpoint — consumed by the HTML page and by anything else
# (Postman, curl, an internal monitoring script).
# ──────────────────────────────────────────────────────────────────────
@router.get("/v1/admin/sessions")
def list_sessions(_token: str = Depends(require_api_key)) -> list[dict]:
    out: list[dict] = []
    for row in db.list_sessions(limit=200):
        full = db.load_session(row["id"])
        if full is None:
            out.append(row)
            continue
        state, _, _ = full
        ev = state.get("evaluation") or {}
        be = state.get("behavioral_eval") or {}
        out.append({
            **row,
            "candidate_name": state.get("candidate_name", ""),
            "role": state.get("role", ""),
            "language": state.get("language", ""),
            "overall_score": ev.get("overall_score"),
            "hire_recommendation": ev.get("hire_recommendation"),
            "behavioral_honesty": be.get("honesty"),
            "behavioral_reliability": be.get("reliability"),
            "summary": (ev.get("summary") or "")[:200],
        })
    return out


# ──────────────────────────────────────────────────────────────────────
# HTML dashboard — minimal, dependency-free, single page.
# ──────────────────────────────────────────────────────────────────────
@router.get("/admin", response_class=HTMLResponse, name="admin_dashboard")
def admin_dashboard(request: Request) -> HTMLResponse:
    rows_html: list[str] = []
    for row in db.list_sessions(limit=200):
        full = db.load_session(row["id"])
        if full is None:
            continue
        state, _, _ = full
        ev = state.get("evaluation") or {}
        score = ev.get("overall_score")
        score_html = (
            f"<span class='score'>{score:.1f}</span>"
            if isinstance(score, (int, float)) else
            "<span class='score muted'>—</span>"
        )
        hire = ev.get("hire_recommendation")
        if hire is True:
            chip = "<span class='chip yes'>✓ Recommended</span>"
        elif hire is False:
            chip = "<span class='chip no'>✕ Not recommended</span>"
        else:
            chip = "<span class='chip pending'>Pending</span>"
        sid = row["id"]
        stage = state.get("stage", row.get("stage", ""))
        report_url = str(request.url_for("get_report", session_id=sid))
        pdf_url = str(request.url_for("get_report_pdf", session_id=sid))
        rows_html.append(f"""
        <tr>
          <td>
            <div class='name'>{_html.escape(state.get('candidate_name') or '—')}</div>
            <div class='sub'>{_html.escape(state.get('role','—'))} · {_html.escape(state.get('language','—'))}</div>
          </td>
          <td>{score_html}</td>
          <td>{chip}</td>
          <td><code>{_html.escape(stage)}</code></td>
          <td class='sub'>{_html.escape(row.get('updated_at','')[:19])}</td>
          <td>
            <a href='{pdf_url}' target='_blank' class='btn'>📄 PDF</a>
            <a href='{report_url}' target='_blank' class='btn btn-ghost'>JSON</a>
          </td>
        </tr>
        """)
    table = "\n".join(rows_html) or "<tr><td colspan='6' class='empty'>No interviews yet. Stakeholders' results will appear here as they submit.</td></tr>"
    page = f"""<!doctype html>
<html><head>
<meta charset='utf-8'>
<title>ShramSaathi AI · Admin</title>
<meta name='viewport' content='width=device-width, initial-scale=1'>
<style>
  body {{
    margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    background: #FAFAFA; color: #18181B; min-height: 100vh;
  }}
  .hero {{
    background: linear-gradient(135deg, #6366F1, #06B6D4);
    color: white; padding: 28px 32px;
  }}
  .hero h1 {{ margin: 0 0 4px; font-size: 22px; font-weight: 800; }}
  .hero p  {{ margin: 0; opacity: 0.85; font-size: 13px; }}
  .container {{ max-width: 1100px; margin: -20px auto 24px; padding: 0 24px; }}
  .card {{
    background: white; border-radius: 14px; box-shadow: 0 4px 18px rgba(0,0,0,0.06);
    overflow: hidden;
  }}
  table {{ width: 100%; border-collapse: collapse; }}
  th, td {{ padding: 14px 16px; text-align: left; border-bottom: 1px solid #F4F4F5; }}
  th {{ font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; color: #71717A; background: #FAFAFA; }}
  td.empty {{ color: #71717A; text-align: center; padding: 40px; }}
  .name {{ font-weight: 600; }}
  .sub  {{ color: #71717A; font-size: 12px; }}
  .score {{ font-size: 22px; font-weight: 800; color: #10B981; }}
  .score.muted {{ color: #D4D4D8; }}
  .chip {{ display: inline-block; padding: 4px 10px; border-radius: 20px; font-size: 11px; font-weight: 700; }}
  .chip.yes     {{ background: #D1FAE5; color: #047857; }}
  .chip.no      {{ background: #FEE2E2; color: #B91C1C; }}
  .chip.pending {{ background: #F4F4F5; color: #71717A; }}
  .btn {{
    display: inline-block; padding: 6px 11px; border-radius: 6px;
    background: #6366F1; color: white; text-decoration: none; font-size: 12px;
    font-weight: 600; margin-right: 4px;
  }}
  .btn-ghost {{ background: transparent; color: #6366F1; border: 1px solid #E4E4E7; }}
  code {{ background: #F4F4F5; padding: 2px 6px; border-radius: 4px; font-size: 11px; color: #52525B; }}
  .refresh {{ margin: 0 0 12px; text-align: right; font-size: 12px; color: #71717A; }}
</style>
</head><body>
<div class='hero'>
  <h1>📊  ShramSaathi AI · Admin</h1>
  <p>Live view of every interview submitted from any device.</p>
</div>
<div class='container'>
  <div class='refresh'>Auto-refreshes every 20 seconds · <a href='/admin'>Refresh now</a></div>
  <div class='card'>
    <table>
      <thead>
        <tr>
          <th>Candidate</th>
          <th>Score</th>
          <th>Verdict</th>
          <th>Stage</th>
          <th>Updated</th>
          <th>Report</th>
        </tr>
      </thead>
      <tbody>
        {table}
      </tbody>
    </table>
  </div>
</div>
<script>setTimeout(() => location.reload(), 20000);</script>
</body></html>"""
    return HTMLResponse(content=page)
