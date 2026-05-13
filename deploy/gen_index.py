#!/usr/bin/env python3
"""Generate a unified index.html linking all suite dashboards.

Usage:
    python deploy/gen_index.py [OUTPUT_DIR]

OUTPUT_DIR defaults to artifacts/dashboard.
"""
from __future__ import annotations

import calendar as _cal
import sys
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from perf_tracker.model_goals import BASH_FRIENDLY_NAMES  # noqa: E402

DEFAULT_OUTPUT = REPO_ROOT / "artifacts" / "dashboard"

_BG     = "#0d0d0d"
_CARD   = "#161616"
_BORDER = "#2a2a2a"
_TEXT   = "#e0e0e0"
_MUTED  = "#9d9fa2"
_GOLD   = "#c1a968"
_TEAL   = "#00c2de"

MILESTONES = [
    (date(2026, 5,  7), "RC1"),
    (date(2026, 5, 13), "RC2"),
    (date(2026, 5, 18), "RC2+"),
    (date(2026, 5, 20), "Bash"),
    (date(2026, 6,  3), "RC3"),
    (date(2026, 6,  5), "Customer Access"),
]

_MILESTONE_MAP: dict[date, str] = {d: label for d, label in MILESTONES}
_SHADE_AFTER = date(2026, 6, 5)   # June 6+ is shaded


_GREEN = "#4caf50"

def _milestone_rows() -> str:
    today = date.today()
    rows = []
    for d, label in MILESTONES:
        delta = (d - today).days
        if delta < 0:
            status    = f'<span style="color:{_GREEN}">Delivered</span>'
            row_style = f' style="color:{_GREEN}"'
        elif delta == 0:
            status    = f'<span style="color:{_GOLD};font-weight:bold">TODAY</span>'
            row_style = ""
        else:
            status    = f'<span style="color:{_TEAL}">{delta}d away</span>'
            row_style = ""
        date_str = d.strftime("%b %-d")
        rows.append(
            f"<tr>"
            f"<td{row_style}><strong>{label}</strong></td>"
            f"<td{row_style}>{date_str}</td>"
            f"<td>{status}</td>"
            f"</tr>"
        )
    return "\n".join(rows)


def _calendar_grid(year: int, month: int, suite_name: str, snapshots: set[str]) -> str:
    month_label = date(year, month, 1).strftime("%B %Y")
    days_in_month = _cal.monthrange(year, month)[1]
    first_dow = date(year, month, 1).weekday()   # 0=Mon … 6=Sun
    sunday_offset = (first_dow + 1) % 7           # cells before day 1 in Sun-first grid
    today = date.today()

    cells: list[str] = ["<td></td>"] * sunday_offset

    for day in range(1, days_in_month + 1):
        d = date(year, month, day)
        date_str = d.strftime("%Y-%m-%d")
        is_snap      = date_str in snapshots
        is_milestone = d in _MILESTONE_MAP
        is_today     = d == today
        is_shaded    = d > _SHADE_AFTER

        base = "text-align:center;padding:3px 1px;font-size:0.82rem;vertical-align:top;"
        ms_label = _MILESTONE_MAP.get(d, "")
        ms_html  = (
            f'<div style="font-size:0.58rem;color:{_GOLD};line-height:1.1;margin-top:1px">'
            f'{ms_label}</div>'
        ) if ms_label else ""

        if is_shaded:
            day_html = f'<span style="color:#444">{day}</span>'
            cells.append(f'<td style="{base}opacity:0.4">{day_html}{ms_html}</td>')

        elif is_today and is_snap:
            day_html = (
                f'<a href="./{suite_name}/{date_str}.html" class="snap-link" '
                f'style="color:{_GOLD};background:{_GOLD}44;border:1px solid {_GOLD}bb">{day}</a>'
            )
            cells.append(
                f'<td style="{base}background:{_GOLD}11;border-radius:6px;'
                f'outline:2px solid {_GOLD}66">{day_html}{ms_html}</td>'
            )

        elif is_today:
            cells.append(
                f'<td style="{base}background:{_GOLD}22;border-radius:4px;'
                f'outline:2px solid {_GOLD}66">'
                f'<span style="color:{_GOLD};font-weight:bold">{day}</span>{ms_html}</td>'
            )

        elif is_snap and is_milestone:
            day_html = (
                f'<a href="./{suite_name}/{date_str}.html" class="snap-link" '
                f'style="color:{_TEAL};background:{_TEAL}30;border:1px solid {_GOLD}99">{day}</a>'
            )
            cells.append(
                f'<td style="{base}">{day_html}{ms_html}</td>'
            )

        elif is_snap:
            day_html = (
                f'<a href="./{suite_name}/{date_str}.html" class="snap-link" '
                f'style="color:{_TEAL};background:{_TEAL}28;border:1px solid {_TEAL}77">{day}</a>'
            )
            cells.append(
                f'<td style="{base}">{day_html}{ms_html}</td>'
            )

        elif is_milestone:
            cells.append(
                f'<td style="{base}outline:1px solid {_GOLD}66;border-radius:4px">'
                f'<span style="color:{_TEXT}">{day}</span>{ms_html}</td>'
            )

        else:
            cells.append(
                f'<td style="{base}">'
                f'<span style="color:{_MUTED}">{day}</span>{ms_html}</td>'
            )

    # Pad to full last week
    while len(cells) % 7 != 0:
        cells.append("<td></td>")

    hdr = "".join(
        f'<th style="text-align:center;padding:3px;font-size:0.72rem;color:{_MUTED};'
        f'font-weight:600">{h}</th>'
        for h in ["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"]
    )
    body_rows = ""
    for i in range(0, len(cells), 7):
        body_rows += "<tr>" + "".join(cells[i:i+7]) + "</tr>\n"

    return (
        f'<div style="flex:1;min-width:200px">'
        f'<div style="text-align:center;font-weight:bold;color:{_GOLD};'
        f'margin-bottom:6px;font-size:0.88rem">{month_label}</div>'
        f'<table style="border-collapse:collapse;width:100%">'
        f"<thead><tr>{hdr}</tr></thead>"
        f"<tbody>{body_rows}</tbody>"
        f"</table></div>"
    )


def _suite_card(output_dir: Path) -> str:
    suite_name  = "VE2_QOR_P0_HW"
    suite_title = "P0 Models (Priority-0 QoR)"
    link        = f"./{suite_name}_latest.html"
    daily_dir   = output_dir / suite_name
    snapshots   = {s.stem for s in daily_dir.glob("20*.html")} if daily_dir.exists() else set()

    # O3 suite intentionally omitted until data is meaningful
    # ("VE2_QOR_O3_HW", "O3 Models (Optimized QoR)")

    may_cal = _calendar_grid(2026, 5, suite_name, snapshots)
    jun_cal = _calendar_grid(2026, 6, suite_name, snapshots)

    return (
        f'<div class="card">'
        f'<h2><a href="{link}">{suite_title}</a></h2>'
        f'<p class="muted">Suite: {suite_name}</p>'
        f'<div style="display:flex;gap:24px;margin-top:12px;flex-wrap:wrap">'
        f"{may_cal}{jun_cal}"
        f"</div></div>"
    )


def _bash_section() -> str:
    items = "".join(
        f'<li style="padding:4px 0;color:{_TEXT};font-size:0.92rem">'
        f'<span style="color:{_TEAL};margin-right:8px">&#x2713;</span>{name}</li>'
        for name in BASH_FRIENDLY_NAMES
    )
    return (
        f'<div class="card">'
        f'<h2 style="margin-top:0">Field Bash — May 20, 2026</h2>'
        f'<p class="muted" style="margin-bottom:12px">'
        f'Models targeted for the Field Bash event. '
        f'Use the <strong>Field Bash</strong> filter on each daily dashboard to focus on these models.'
        f'</p>'
        f'<ul style="margin:0;padding-left:4px;list-style:none;'
        f'column-count:2;column-gap:32px">{items}</ul>'
        f'</div>'
    )


def generate_index(output_dir: Path) -> Path:
    index_path = output_dir / "index.html"
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>VAI 6.2 QoR Dashboard</title>
  <style>
    :root {{ color-scheme: dark; font-family: Arial, sans-serif; }}
    body {{ margin: 0; background: {_BG}; color: {_TEXT}; }}
    main {{ max-width: 1060px; margin: 0 auto; padding: 32px 24px; }}
    h1 {{ color: {_GOLD}; font-size: 1.7rem; margin: 0 0 4px; }}
    h2 {{ color: {_GOLD}; font-size: 1.1rem; margin: 0 0 8px; }}
    .muted {{ color: {_MUTED}; font-size: 0.88rem; }}
    .card {{
      background: {_CARD}; border: 1px solid {_BORDER}; border-radius: 8px;
      padding: 20px; margin: 20px 0;
    }}
    .milestone-table {{
      width: 100%; border-collapse: collapse;
      background: {_CARD}; margin: 12px 0;
    }}
    .milestone-table th, .milestone-table td {{
      padding: 9px 12px; border-bottom: 1px solid {_BORDER};
      text-align: left; font-size: 0.9rem;
    }}
    .milestone-table th {{
      background: #1e1e1e; color: {_MUTED}; font-size: 0.8rem;
      text-transform: uppercase; letter-spacing: 0.04em;
    }}
    a {{ color: {_TEAL}; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    .snap-link {{
      display: inline-block; font-weight: bold; text-decoration: none;
      border-radius: 4px; padding: 1px 5px; min-width: 16px; text-align: center;
      transition: transform 0.1s ease, box-shadow 0.1s ease, filter 0.1s ease;
    }}
    .snap-link:hover {{
      transform: translateY(-4px);
      box-shadow: 0 6px 14px rgba(0,0,0,0.7);
      filter: brightness(1.6);
      text-decoration: none;
    }}
    .section-label {{
      color: {_GOLD}; font-size: 0.8rem; text-transform: uppercase;
      letter-spacing: 0.06em; border-bottom: 1px solid {_BORDER};
      padding-bottom: 6px; margin: 28px 0 12px;
    }}
  </style>
</head>
<body>
  <main>
    <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:16px">
      <div>
        <h1>VAI 6.2 QoR Performance Dashboard</h1>
        <p class="muted">Refreshes daily at 11:07 AM PDT</p>
      </div>
      <div style="font-size:0.78rem;color:{_MUTED};text-align:right;white-space:nowrap;padding-top:6px">
        Questions or suggestions?<br>Contact <a href="mailto:anup.sekhar@amd.com">Anup Sekhar</a>
      </div>
    </div>

    <p class="section-label">Milestones</p>
    <table class="milestone-table">
      <thead><tr><th>Milestone</th><th>Date</th><th>Status</th></tr></thead>
      <tbody>{_milestone_rows()}</tbody>
    </table>

    <p class="section-label">Suite Dashboards</p>
    {_suite_card(output_dir)}

    <p class="section-label">Field Bash</p>
    {_bash_section()}

    <p class="section-label">Tools</p>
    <div class="card" style="padding:16px 20px">
      <a href="./goal_reconciliation.html"
        style="font-size:1rem;font-weight:600;color:{_GOLD}">
        &#x2714; Goal Reconciliation
      </a>
      <p class="muted" style="margin:4px 0 0">
        Compare VAI 6.2 latency goals in Sumit's spreadsheet against the
        Perf Tracker dashboard. Track resolved items and add comments inline.
      </p>
    </div>
  </main>
  <footer style="text-align:center;padding:16px 24px;color:{_MUTED};font-size:0.78rem;
    border-top:1px solid {_BORDER};margin-top:32px;">
    Inspired by <a href="http://fisweb:8080/proj/vaiml_int/staff/praveeni/perf_tracker/artifacts/dashboard/VE2_QOR_P0_HW_latest.html"
      target="_blank" rel="noopener">Praveen Iyer's perf-tracker</a>,
    whose work served as the seed for this dashboard.
  </footer>
</body>
</html>
"""
    index_path.write_text(html, encoding="utf-8")
    return index_path


if __name__ == "__main__":
    output_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUTPUT
    output_dir.mkdir(parents=True, exist_ok=True)
    path = generate_index(output_dir)
    print(f"Written: {path}")
