#!/usr/bin/env python3
"""Generate the goal reconciliation page.

Usage:
    python deploy/gen_goal_reconciliation.py [OUTPUT_DIR]

OUTPUT_DIR defaults to artifacts/dashboard.
"""
from __future__ import annotations

import sys
from pathlib import Path

DEFAULT_OUTPUT = Path(__file__).resolve().parents[1] / "artifacts" / "dashboard"

_BG     = "#0d0d0d"
_CARD   = "#161616"
_BORDER = "#2a2a2a"
_TEXT   = "#e0e0e0"
_MUTED  = "#9d9fa2"
_GOLD   = "#c1a968"
_TEAL   = "#00c2de"

_JIRA_BASE = "https://jira.xilinx.com/browse"

# Tuple fields:
#   model_friendly_name,
#   spreadsheet_goal (float | None),
#   dashboard_goal (float | None),
#   epic_goal (str | None),   <- new: human-readable, e.g. "150ms" or "<40ms combined"
#   epic_key (str | None),    <- Jira key for link, e.g. "AIESW-13503"
#   status,
#   default_comment
#
# status: "match" | "mismatch" | "not_in_sheet" | "unresolved" | "check_sumit"

RECONCILIATION_DATA = [
    # ── Matches ──────────────────────────────────────────────────────────────
    # Subaru epic (AIESW-21659) states <40ms total for Asura+Garuda+Route combined.
    # Individual goals (18/12/15ms) come from Sumit's spreadsheet only.
    ("Asura",
     18, 18,
     "<40ms (SA+SG+SR combined)", "AIESW-21659",
     "match", ""),
    ("BEVFormer-tiny ResNet-50",
     20, 20,
     "30 FPS (≈33ms) — full model", "AIESW-23282",
     "match", ""),
    ("BEVFormer-tiny Transformer",
     13, 13,
     "30 FPS (≈33ms) — full model", "AIESW-23282",
     "match", ""),
    ("Garuda",
     12, 12,
     "<40ms (SA+SG+SR combined)", "AIESW-21659",
     "match", ""),
    ("RAFT-Stereo",
     150, 150,
     "150ms", "AIESW-13503",
     "match", ""),
    ("Route",
     15, 15,
     "<40ms (SA+SG+SR combined)", "AIESW-21659",
     "match", ""),
    ("YOLO8m",
     5.6, 5.6,
     None, "AIESW-23286",
     "match", ""),
    # ── Mismatches ───────────────────────────────────────────────────────────
    ("DINO-nano ViT",
     60, 15,
     None, "AIESW-24988",
     "mismatch", ""),
    ("Egolanes",
     33, 29.6,
     None, "AIESW-23104",
     "mismatch", "Epic is analysis-only (insights report); no performance target set"),
    ("Wayve ViT s256 d1024",
     40, 22.8,
     None, "AIESW-29684",
     "mismatch", ""),
    ("Wayve ViT s256 d1536",
     75, 44.2,
     None, "AIESW-29684",
     "mismatch", ""),
    ("Wayve ViT s512 d1536",
     157, 77,
     None, "AIESW-29684",
     "mismatch", ""),
    ("Wayve ViT s1024 d1536",
     360, 174,
     None, "AIESW-29684",
     "mismatch", ""),
    ("Anduril YOLOx-s",
     2.49, 3.2,
     None, "AIESW-23280",
     "mismatch", ""),
    ("Anduril YOLOx-m",
     4.29, 5.4,
     None, "AIESW-23280",
     "mismatch", ""),
    ("Anduril YOLOx-l 640",
     7.87, 9.2,
     None, "AIESW-23280",
     "mismatch", ""),
    ("Anduril YOLOx-l 1280",
     51.81, 36.8,
     None, "AIESW-23280",
     "mismatch", ""),
    # ── Not in spreadsheet ───────────────────────────────────────────────────
    ("DenseNet-161",
     None, 150,
     None, "AIESW-28363",
     "not_in_sheet",
     "Epic says must beat VAI 5.1 baseline of 374ms; no specific ms target given"),
    ("TinyDepth",
     None, 16.67,
     "60 FPS (16.67ms)", "AIESW-6307",
     "not_in_sheet", ""),
    # ── Unresolved mapping ───────────────────────────────────────────────────
    ("PETRv2",
     None, 72,
     None, "AIESW-22153",
     "unresolved",
     "Spreadsheet has petrv2_bbone=100 and petrv2_transformer=50; unclear which maps here"),
    ("PETRv2 BEV Segmentation",
     None, 80,
     None, "AIESW-22153",
     "unresolved",
     "Spreadsheet has petrv2_bbone=100 and petrv2_transformer=50; unclear which maps here"),
    # ── Check with Sumit ─────────────────────────────────────────────────────
    ("YOLO11x",
     None, 60.76,
     None, "AIESW-23284",
     "check_sumit",
     "Assumed = yolov11m in spreadsheet, which has no goal set"),
    ("YOLO12l",
     None, 21.76,
     None, "AIESW-23285",
     "check_sumit",
     "Assumed = yolov12m in spreadsheet, which has no goal set"),
]

_BASH_TARGETS = frozenset({
    "Anduril YOLOx-s", "Anduril YOLOx-m", "Anduril YOLOx-l 640", "Anduril YOLOx-l 1280",
    "Egolanes", "RAFT-Stereo", "DINO-nano ViT", "YOLO8m",
    "Wayve ViT s256 d1024", "Wayve ViT s256 d1536",
    "Wayve ViT s512 d1536", "Wayve ViT s1024 d1536",
})

_STATUS_META = {
    "match":        ("#22543d", "#9ae6b4", "Match"),
    "mismatch":     ("#7b341e", "#fbd38d", "Mismatch"),
    "not_in_sheet": ("#2d3748", "#a0aec0", "Not in Spreadsheet"),
    "unresolved":   ("#6b2737", "#feb2b2", "Unresolved"),
    "check_sumit":  ("#744210", "#fefcbf", "Check with Sumit"),
}


def _fmt(val: object) -> str:
    if val is None:
        return "—"
    f = float(val)
    return f"{f:g}"


def _badge(status: str) -> str:
    bg, fg, label = _STATUS_META[status]
    return (
        f'<span style="background:{bg};color:{fg};padding:2px 8px;border-radius:4px;'
        f'font-size:0.78rem;font-weight:600;white-space:nowrap">{label}</span>'
    )


def _status_select(row_id: str, initial_status: str) -> str:
    options = "\n".join(
        f'<option value="{k}"{"  selected" if k == initial_status else ""}>{v[2]}</option>'
        for k, v in _STATUS_META.items()
    )
    bg, fg, _ = _STATUS_META[initial_status]
    return (
        f'<select class="status-select" data-row="{row_id}" '
        f'style="background:{bg};color:{fg};border:1px solid rgba(255,255,255,0.12);'
        f'border-radius:4px;padding:3px 8px;font-size:0.78rem;font-weight:600;'
        f'cursor:pointer;outline:none;min-width:165px;width:165px">'
        f'{options}</select>'
    )


def _epic_cell(epic_goal: object, epic_key: object) -> str:
    if epic_goal is None:
        txt = '<span style="color:#444">N/A</span>'
    else:
        txt = str(epic_goal)
    if epic_key:
        url = f"{_JIRA_BASE}/{epic_key}"
        link = (
            f' <a href="{url}" target="_blank" rel="noopener" '
            f'style="font-size:0.72rem;color:{_MUTED};white-space:nowrap"'
            f'title="Open {epic_key} in Jira">[{epic_key}]</a>'
        )
    else:
        link = ""
    return txt + link


def _table_rows() -> str:
    rows = []
    for i, row in enumerate(RECONCILIATION_DATA):
        model, sheet_goal, dash_goal, epic_goal, epic_key, status, default_comment = row
        row_id = f"row-{i}"
        comment_id = f"comment-{i}"
        sheet_str = _fmt(sheet_goal)
        dash_str  = _fmt(dash_goal)
        epic_html = _epic_cell(epic_goal, epic_key)

        bash_cell = (
            f'<td style="text-align:center;font-size:1.1rem;color:{_TEAL}">&#x2713;</td>'
            if model in _BASH_TARGETS else
            '<td></td>'
        )
        rows.append(f"""
  <tr id="{row_id}" data-status="{status}">
    <td style="text-align:center;width:36px">
      <input type="checkbox" class="resolve-cb" data-row="{row_id}"
        style="width:16px;height:16px;cursor:pointer;accent-color:{_TEAL}">
    </td>
    <td>{model}</td>
    {bash_cell}
    <td style="text-align:right">{sheet_str}</td>
    <td style="text-align:right;white-space:nowrap">{epic_html}</td>
    <td style="text-align:right">{dash_str}</td>
    <td style="text-align:center;min-width:175px">{_status_select(row_id, status)}</td>
    <td contenteditable="true" class="comment-cell" id="{comment_id}"
        data-comment-id="{comment_id}"
        style="min-width:180px;outline:none;color:{_MUTED}"
        >{default_comment}</td>
  </tr>""")
    return "\n".join(rows)


def generate_reconciliation(output_dir: Path) -> Path:
    out_path = output_dir / "goal_reconciliation.html"

    total        = len(RECONCILIATION_DATA)
    matches      = sum(1 for r in RECONCILIATION_DATA if r[5] == "match")
    mismatches   = sum(1 for r in RECONCILIATION_DATA if r[5] == "mismatch")
    needs_action = total - matches - mismatches

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Goal Reconciliation — VAI 6.2 QoR</title>
  <style>
    :root {{ color-scheme: dark; font-family: Arial, sans-serif; }}
    body {{ margin: 0; background: {_BG}; color: {_TEXT}; }}
    main {{ max-width: 1200px; margin: 0 auto; padding: 32px 24px; }}
    h1 {{ color: {_GOLD}; font-size: 1.6rem; margin: 0 0 4px; }}
    .muted {{ color: {_MUTED}; font-size: 0.88rem; }}
    a {{ color: {_TEAL}; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    .section-label {{
      color: {_GOLD}; font-size: 0.8rem; text-transform: uppercase;
      letter-spacing: 0.06em; border-bottom: 1px solid {_BORDER};
      padding-bottom: 6px; margin: 28px 0 12px;
    }}
    .stat-row {{ display:flex; gap:24px; flex-wrap:wrap; margin:16px 0; }}
    .stat {{
      background:{_CARD}; border:1px solid {_BORDER}; border-radius:8px;
      padding:14px 20px; text-align:center; min-width:100px;
    }}
    .stat-num {{ font-size:1.8rem; font-weight:bold; color:{_GOLD}; }}
    .stat-lbl {{ font-size:0.78rem; color:{_MUTED}; margin-top:2px; }}
    table.recon {{
      width:100%; border-collapse:collapse;
      background:{_CARD}; border:1px solid {_BORDER}; border-radius:8px;
      overflow:hidden; font-size:0.9rem;
    }}
    table.recon th {{
      background:#1e1e1e; color:{_MUTED}; font-size:0.78rem;
      text-transform:uppercase; letter-spacing:0.04em;
      padding:10px 12px; text-align:left; border-bottom:1px solid {_BORDER};
    }}
    table.recon td {{
      padding:9px 12px; border-bottom:1px solid {_BORDER}; vertical-align:middle;
    }}
    table.recon tr:last-child td {{ border-bottom: none; }}
    table.recon tr.resolved td {{
      text-decoration: line-through;
      color: {_MUTED};
      opacity: 0.55;
    }}
    table.recon tr.resolved td span {{ opacity: 0.55; }}
    .comment-cell:empty:before {{
      content: 'Add a comment…';
      color: #444;
      font-style: italic;
    }}
    .comment-cell:focus {{
      background: #1e2a1e;
      outline: 1px solid {_TEAL}44;
      border-radius: 3px;
    }}
    select.status-select option {{ background: #1e1e1e; color: {_TEXT}; }}
    select.status-select:focus {{ outline: 1px solid {_TEAL}55; }}
    .legend {{ display:flex; gap:16px; flex-wrap:wrap; margin:12px 0 20px; font-size:0.82rem; }}
  </style>
</head>
<body>
  <main>
    <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:16px">
      <div>
        <h1>
          <a href="./" title="Back to dashboard"
            style="color:{_MUTED};font-size:1rem;margin-right:10px;vertical-align:middle">&#8592;</a>
          VAI 6.2 Goal Reconciliation
        </h1>
        <p class="muted">
          Comparing goals in <em>vai_6_2_perf_goals.xlsx</em> (tab: impr_6.2, Col E)
          and Marketing Jira Epics against the Perf Tracker Dashboard's "VAI 6.2 Goal" column.
        </p>
      </div>
      <div style="font-size:0.78rem;color:{_MUTED};text-align:right;white-space:nowrap;padding-top:6px">
        Questions or suggestions?<br>
        Contact <a href="mailto:anup.sekhar@amd.com">Anup Sekhar</a>
      </div>
    </div>

    <div class="stat-row">
      <div class="stat"><div class="stat-num">{total}</div><div class="stat-lbl">Models</div></div>
      <div class="stat"><div class="stat-num" style="color:#9ae6b4">{matches}</div><div class="stat-lbl">Match</div></div>
      <div class="stat"><div class="stat-num" style="color:#fbd38d">{mismatches}</div><div class="stat-lbl">Mismatch</div></div>
      <div class="stat"><div class="stat-num" style="color:#feb2b2">{needs_action}</div><div class="stat-lbl">Need Action</div></div>
    </div>

    <div class="legend">
      {"".join(_badge(s) + f'<span style="margin-right:4px">&nbsp;{_STATUS_META[s][2]}</span>' for s in _STATUS_META)}
    </div>

    <p class="section-label">Goal Comparison Table</p>
    <p class="muted" style="margin-bottom:10px">
      Check the box to mark a row as resolved (adds strikethrough). Comments are editable and saved in your browser.
      Epic Goal links open the corresponding Jira Marketing Epic in a new tab.
    </p>

    <table class="recon">
      <thead>
        <tr>
          <th style="width:36px">&#10003;</th>
          <th>Model</th>
          <th style="text-align:center;width:80px" title="Field Bash (May 20) target model">Bash Target</th>
          <th style="text-align:right">Sumit's Spreadsheet Goal <span style="text-transform:none">(ms)</span></th>
          <th style="text-align:right">VAI 6.2 Epic Goal</th>
          <th style="text-align:right">Perf Tracker Dashboard Goal <span style="text-transform:none">(ms)</span></th>
          <th style="text-align:center;min-width:190px">
            <div style="display:flex;flex-direction:column;align-items:center;gap:5px">
              <span>Status</span>
              <select id="status-header-filter"
                style="background:#1e1e1e;color:{_MUTED};
                  border:1px solid {_BORDER};border-radius:4px;padding:2px 8px;
                  font-size:0.72rem;cursor:pointer;width:100%"
                onchange="filterByStatus(this.value)">
                <option value="">All</option>
                {"".join(f'<option value="{k}">{v[2]}</option>' for k, v in _STATUS_META.items())}
              </select>
            </div>
          </th>
          <th>Comments</th>
        </tr>
      </thead>
      <tbody>
{_table_rows()}
      </tbody>
    </table>

    <p class="muted" style="margin-top:16px;font-size:0.78rem">
      <strong>Notes:</strong>
      &ldquo;Unresolved&rdquo; rows have ambiguous model mapping — verify before updating goals.
      &ldquo;Check with Sumit&rdquo; rows have no goal in the spreadsheet; confirm the correct value.
      Epic Goals are sourced from the VAI 6.2 Marketing Jira Epics
      (JQL: <em>project in (APRO, "AIE Software") AND fixVersion = "VAI 6.2" AND issuetype = Epic
      AND status not in (Closed, Withdrawn, Backlog) AND "Requirement Source" = Marketing</em>).
      &ldquo;N/A&rdquo; means the epic exists but contains no specific latency target.
    </p>
  </main>

  <footer style="text-align:center;padding:16px 24px;color:{_MUTED};font-size:0.78rem;
    border-top:1px solid {_BORDER};margin-top:32px;">
    <a href="./">&#8592; Back to Dashboard</a>
  </footer>

  <script>
    const STORAGE_KEY = 'vai62-recon-v1';

    function loadState() {{
      try {{ return JSON.parse(localStorage.getItem(STORAGE_KEY) || '{{}}'); }}
      catch {{ return {{}}; }}
    }}

    function saveState(state) {{
      localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    }}

    const state = loadState();
    document.querySelectorAll('.resolve-cb').forEach(cb => {{
      const rowId = cb.dataset.row;
      if (state[rowId + '-resolved']) {{
        cb.checked = true;
        document.getElementById(rowId).classList.add('resolved');
      }}
      cb.addEventListener('change', () => {{
        const row = document.getElementById(rowId);
        if (cb.checked) {{
          row.classList.add('resolved');
        }} else {{
          row.classList.remove('resolved');
        }}
        state[rowId + '-resolved'] = cb.checked;
        saveState(state);
      }});
    }});

    const STATUS_COLORS = {{
      'match':        ['#22543d', '#9ae6b4'],
      'mismatch':     ['#7b341e', '#fbd38d'],
      'not_in_sheet': ['#2d3748', '#a0aec0'],
      'unresolved':   ['#6b2737', '#feb2b2'],
      'check_sumit':  ['#744210', '#fefcbf'],
    }};
    function styleSelect(sel) {{
      const [bg, fg] = STATUS_COLORS[sel.value] || ['#333', '#ccc'];
      sel.style.background = bg;
      sel.style.color = fg;
    }}
    function filterByStatus(val) {{
      document.querySelectorAll('tbody tr').forEach(row => {{
        row.style.display = (!val || row.dataset.status === val) ? '' : 'none';
      }});
    }}

    document.querySelectorAll('.status-select').forEach(sel => {{
      const rowId = sel.dataset.row;
      const saved = state[rowId + '-status'];
      if (saved && STATUS_COLORS[saved]) sel.value = saved;
      styleSelect(sel);
      sel.addEventListener('change', () => {{
        styleSelect(sel);
        state[rowId + '-status'] = sel.value;
        document.getElementById(rowId).dataset.status = sel.value;
        // Re-apply header filter after row status change
        const hf = document.getElementById('status-header-filter');
        if (hf) filterByStatus(hf.value);
        saveState(state);
      }});
    }});

    document.querySelectorAll('.comment-cell').forEach(cell => {{
      const cid = cell.dataset.commentId;
      if (state[cid]) {{
        cell.textContent = state[cid];
      }}
      cell.addEventListener('input', () => {{
        state[cid] = cell.textContent;
        saveState(state);
      }});
      cell.addEventListener('keydown', e => {{
        if (e.key === 'Enter' && !e.shiftKey) {{
          e.preventDefault();
          cell.blur();
        }}
      }});
    }});
  </script>
</body>
</html>
"""
    out_path.write_text(html, encoding="utf-8")
    return out_path


if __name__ == "__main__":
    output_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUTPUT
    output_dir.mkdir(parents=True, exist_ok=True)
    path = generate_reconciliation(output_dir)
    print(f"Written: {path}")
