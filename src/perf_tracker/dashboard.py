from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from html import escape
from pathlib import Path
import re
from typing import Sequence
from urllib.parse import urlencode

from perf_tracker.history import HistoryRow
from perf_tracker.milestones import MILESTONES
from perf_tracker.model_goals import is_bash, rc1_goal, rc2_goal, rc2_goal_changes

# ── Friendly model name mapping ──────────────────────────────────────────────
_CUSTOMER_NAMES: dict[str, str] = {
    "SICK-NextGen":      "SICK",
    "IntutiveSurgical":  "Intuitive Surgical",
    "IntuitiveSurgical": "Intuitive Surgical",
}

_MODEL_NAMES: dict[str, str] = {
    "asura_int8_subaru_2x8_t2d1-hw-vek385_vaiml":                                          "Asura",
    "bevformer_tiny_rn50_int8_batch6_t1d6-hw-vek385_vaiml":                                "BEVFormer-tiny (ResNet-50 backbone)",
    "bevformer_tiny_transformer_bf16_cop-hw-vek385_vaiml":                                 "BevFormer-tiny (transformer)",
    "deimv2_dinov3_s_bf16-hw-vek385_vaiml":                                                "DINO-nano ViT",
    "densenet161_int8_fujifilm_aiesw-28363-hw-vek385_vaiml":                               "DenseNet-161 CNN",
    "egolanes-bs1_int8_autoware_aiesw-23104-hw-vek385_vaiml":                              "Egolanes",
    "garuda_int8_subaru_2x8_t2d1-hw-vek385_vaiml":                                        "Garuda",
    "petr-v2-bevseg_int8-bf16_astemo_aiesw-24634_batch12_t1d6-hw-vek385_vaiml":           "PETRv2 BEV Segmentation",
    "petr-v2_int8-bf16_astemo_aiesw-24634_batch12_t1d6-hw-vek385_vaiml":                  "PETRv2",
    "raft-stereo_fp16_sick_aiesw-13503_t4d1-hw-vek385_vaiml":                             "RAFT-Stereo",
    "route_2x8_vart_zerocopy_fp16-int8_subaru_t2d1-hw-vek385_vaiml":                      "Route",
    "tinydepth_batch2_int8_intuitive-surgical_aiesw-6307-hw-vek385_vaiml":                "TinyDepth",
    "vit_encoder_b2_s1024_d1536_m6144_h16_l12_int8_wavye_t4d2-hw-vek385_vaiml":          "Wayve VIT s1024 d1536",
    "vit_encoder_b2_s256_d1024_m4096_h16_l12_int8_wavye_t4d2-hw-vek385_vaiml":           "Wayve VIT s256 d1024",
    "vit_encoder_b2_s256_d1536_m6144_h16_l12_int8_wavye_t4d2-hw-vek385_vaiml":           "Wayve VIT s256 d1536",
    "vit_encoder_b2_s512_d1536_m6144_h16_l12_int8_wavye_t4d2-hw-vek385_vaiml":           "Wayve VIT s512 d1536",
    "yolo11x-seg_1280x1280_int8_focus_aiesw-23284-hw-vek385_vaiml":                       "YOLO11x",
    "yolo12l_int8-bf16_kria2_aiesw-23285-hw-vek385_vaiml":                                "YOLO12l",
    "yolov8m_int8-bf16-hw-vek385_vaiml":                                                  "YOLO8m",
    "yolox-l_int8_anduril-hw-vek385_vaiml":                                               "Anduril YOLOx-l 640",
    "yolox-m_int8_anduril-hw-vek385_vaiml":                                               "Anduril YOLOx-m",
    "yolox-s_int8_anduril-hw-vek385_vaiml":                                               "Anduril YOLOx-s",
    "yolox-x-1280x1280_int8_anduril-hw-vek385_vaiml":                                     "Anduril YOLOx-l 1280",
}

_HOME_ICON = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24" '
    'fill="currentColor" style="vertical-align:middle;margin-bottom:4px">'
    '<path d="M10 20v-6h4v6h5v-8h3L12 3 2 12h3v8z"/>'
    '</svg>'
)

# ── AMD color palette ────────────────────────────────────────────────────────
_BG        = "#0d0d0d"
_CARD_BG   = "#161616"
_BORDER    = "#2a2a2a"
_TEXT      = "#e0e0e0"
_MUTED     = "#9d9fa2"
_GOLD      = "#c1a968"
_TEAL      = "#00c2de"
_ORANGE    = "#f26522"
_RED       = "#ed1c24"
_GREEN     = "#a6ce39"

# Data table: off-white so rows are easy to read on a dark page
_TABLE_BG  = "#f5f4f0"
_TABLE_HDR = "#e2ded4"
_TABLE_BORDER_LIGHT = "#ccc9bf"
_TABLE_TEXT = "#1a1a1a"

# Status row tints — light versions that work on the off-white table
_GOOD_BG   = "#d4edda"   # soft green
_WARN_BG   = "#fff3cd"   # soft amber
_BAD_BG    = "#f8d7da"   # soft red
_GOOD_TEXT = "#155724"
_WARN_TEXT = "#7a5200"
_BAD_TEXT  = "#721c24"


def render_dashboard_html(
    rows: Sequence[HistoryRow],
    *,
    snapshot_date: date,
    generated_at: datetime | None = None,
) -> str:
    generated_at = generated_at or datetime.now().astimezone()
    visible_rows = [row for row in rows if row.date <= snapshot_date]
    rows_by_model = _group_rows_by_model(visible_rows)
    anchor_by_model = _build_anchor_by_model(rows_by_model)
    latest_rows = sorted(
        (model_rows[-1] for model_rows in rows_by_model.values()),
        key=lambda row: row.model_name.lower(),
    )
    detail_sections = "\n".join(
        _render_detail_section(
            model_name,
            model_rows,
            snapshot_date=snapshot_date,
            anchor=anchor_by_model[model_name],
        )
        for model_name, model_rows in sorted(rows_by_model.items())
    )
    changes = rc2_goal_changes()
    summary_rows = "\n".join(
        _render_summary_row(
            row,
            anchor=anchor_by_model[row.model_name],
            all_model_rows=rows_by_model[row.model_name],
            rc2_changes=changes,
        )
        for row in latest_rows
    )
    rc2_footnote = _render_rc2_footnote(changes, latest_rows)
    model_filter_options = _render_filter_options([_friendly_model_name(row) for row in latest_rows])
    customer_filter_options = _render_filter_options([_display_customer_name(row.section) for row in latest_rows])
    milestone_legend = _render_milestone_legend()

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>VAI 6.2 Perf Dashboard – {snapshot_date.isoformat()}</title>
  <style>
    :root {{
      color-scheme: dark;
      font-family: Arial, sans-serif;
    }}
    body {{
      margin: 0;
      background: {_BG};
      color: {_TEXT};
    }}
    main {{
      max-width: 1200px;
      margin: 0 auto;
      padding: 24px;
    }}
    h1 {{
      color: {_GOLD};
      font-size: 1.6rem;
      margin: 0 0 4px;
      letter-spacing: 0.02em;
    }}
    h2 {{
      color: {_GOLD};
      font-size: 1.1rem;
      margin: 32px 0 12px;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      border-bottom: 1px solid {_BORDER};
      padding-bottom: 6px;
    }}
    h3, h4 {{
      color: {_GOLD};
      margin-top: 0;
    }}
    .summary-table,
    .trend-table {{
      width: 100%;
      border-collapse: collapse;
      background: {_TABLE_BG};
      color: {_TABLE_TEXT};
    }}
    .summary-table th,
    .summary-table td,
    .trend-table th,
    .trend-table td {{
      padding: 10px 12px;
      border-bottom: 1px solid {_TABLE_BORDER_LIGHT};
      text-align: left;
      font-size: 0.92rem;
      color: {_TABLE_TEXT};
    }}
    .summary-table th,
    .trend-table th {{
      background: {_TABLE_HDR};
      color: #3a3630;
      font-weight: 700;
      font-size: 0.82rem;
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }}
    .col-latency {{
      border-left: 3px solid #4a8aaa;
      border-right: 3px solid #4a8aaa;
    }}
    .summary-table thead .col-latency {{
      background: #c0d8ea;
      border-top: 3px solid #4a8aaa;
    }}
    .summary-table tbody tr:last-child .col-latency {{
      border-bottom: 3px solid #4a8aaa;
    }}
    .col-goal {{
      border-left: 2px solid #a04040;
      border-right: 2px solid #a04040;
    }}
    .summary-table thead .col-goal {{
      background: #e8c8c8;
      border-top: 2px solid #a04040;
    }}
    .summary-table tbody tr:last-child .col-goal {{
      border-bottom: 2px solid #a04040;
    }}
    .summary-good    {{ background: {_GOOD_BG}; color: {_GOOD_TEXT}; }}
    .summary-good td {{ color: {_GOOD_TEXT}; }}
    .summary-warning    {{ background: {_WARN_BG}; color: {_WARN_TEXT}; }}
    .summary-warning td {{ color: {_WARN_TEXT}; }}
    .summary-bad    {{ background: {_BAD_BG}; color: {_BAD_TEXT}; }}
    .summary-bad td {{ color: {_BAD_TEXT}; }}
    .summary-good a, .summary-warning a, .summary-bad a {{ color: inherit; text-decoration: underline; }}
    .filter-panel {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 12px;
      margin: 12px 0 16px;
      padding: 14px;
      background: {_CARD_BG};
      border: 1px solid {_BORDER};
      border-radius: 8px;
    }}
    .filter-panel label {{
      display: flex;
      flex-direction: column;
      gap: 4px;
      font-size: 0.85rem;
      color: {_MUTED};
    }}
    .filter-panel input,
    .filter-panel select {{
      padding: 7px 10px;
      border: 1px solid {_BORDER};
      border-radius: 5px;
      font: inherit;
      background: #222;
      color: {_TEXT};
    }}
    .detail-card {{
      margin-top: 28px;
      padding: 20px;
      background: {_CARD_BG};
      border: 1px solid {_BORDER};
      border-radius: 8px;
    }}
    .chart-card {{
      margin: 16px 0 20px;
      padding: 18px;
      background: #111111;
      border: 1px solid {_BORDER};
      border-radius: 8px;
    }}
    .model-trend-chart {{
      min-width: 1000px;
      width: 100%;
      height: auto;
      overflow: visible;
    }}
    .chart-scroll {{
      overflow-x: auto;
      padding-bottom: 6px;
    }}
    .axis  {{ stroke: {_BORDER}; stroke-width: 1; }}
    .grid  {{ stroke: #252525; stroke-width: 1; }}
    .line  {{ fill: none; stroke-width: 3; stroke-linejoin: round; stroke-linecap: round; }}
    .line-vart   {{ stroke: {_TEAL}; stroke-width: 3; }}
    .line-target {{ stroke: {_GOLD}; stroke-dasharray: 8 5; stroke-width: 2; }}
    .line-vai61  {{ stroke: #7a7a7a; stroke-dasharray: 6 4; stroke-width: 1.5; }}
    .chart-point      {{ fill: {_BG}; stroke-width: 2.5; }}
    .point-vart       {{ stroke: {_TEAL}; }}
    .latest-vart-point {{ fill: {_TEAL}; }}
    .reference-line   {{ stroke-width: 1.5; stroke-dasharray: 6 4; }}
    .reference-vai61  {{ stroke: #7a7a7a; }}
    .reference-vart   {{ stroke: {_TEAL}; }}
    .reference-target {{ stroke: {_GOLD}; }}
    .reference-label  {{ font-size: 11px; font-weight: 700; }}
    .milestone-line   {{ stroke-width: 1.5; stroke-dasharray: 6 3; opacity: 0.85; }}
    .tick-label       {{ fill: {_MUTED}; font-size: 10px; }}
    .milestone-label  {{ font-size: 10px; font-weight: 700; text-anchor: middle; }}
    .legend {{
      display: flex;
      gap: 18px;
      flex-wrap: wrap;
      margin-top: 14px;
      font-size: 0.88rem;
      color: {_MUTED};
    }}
    .legend-line {{
      display: inline-block;
      width: 22px;
      height: 0;
      margin-right: 5px;
      vertical-align: middle;
      border-top: 3px solid currentColor;
    }}
    .legend-dashed {{ border-top-style: dashed; }}
    .legend-dot {{
      display: inline-block;
      width: 9px;
      height: 9px;
      border-radius: 50%;
      margin-right: 5px;
      vertical-align: middle;
    }}
    .muted {{ color: {_MUTED}; font-size: 0.88rem; }}
    a {{ color: {_TEAL}; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    .milestone-legend {{
      display: flex;
      gap: 16px;
      flex-wrap: wrap;
      margin-bottom: 10px;
      font-size: 0.82rem;
      color: {_MUTED};
    }}
    .milestone-badge {{
      display: inline-block;
      width: 10px;
      height: 10px;
      margin-right: 5px;
      vertical-align: middle;
      border-left: 2.5px dashed {_GOLD};
    }}
    details.detail-card > summary {{ user-select: none; }}
    details.detail-card[open] > summary .detail-arrow {{
      transform: rotate(90deg);
    }}
  </style>
</head>
<body>
  <main>
    <header style="display:flex;justify-content:space-between;align-items:flex-start;gap:16px">
      <div>
        <h1><a href="../" title="Home" style="color:#f26522;text-decoration:none;margin-right:16px">{_HOME_ICON}</a>VAI 6.2 Performance Dashboard</h1>
        <hr style="border:none;border-top:1px solid {_BORDER};margin:6px 0 16px">
        <p style="color:{_TEXT};font-size:1.1rem;font-weight:600;margin:0 0 4px">XOAH Results on {snapshot_date.strftime("%B %-d")}</p>
        <p class="muted">Last Generated: {_format_generated_at(generated_at)}</p>
        {milestone_legend}
      </div>
      <div style="font-size:0.78rem;color:{_MUTED};text-align:right;white-space:nowrap;padding-top:6px">
        Questions or suggestions?<br>Contact <a href="mailto:anup.sekhar@amd.com">Anup Sekhar</a>
      </div>
    </header>
    <section>
      <h2>Summary</h2>
      <div class="filter-panel" aria-label="Summary table filters">
        <label>Model
          <select id="summary-filter-model" data-filter-column="2">
            <option value="">All</option>
            {model_filter_options}
          </select>
        </label>
        <label>Bash Models
          <select id="summary-filter-bash">
            <option value="">All</option>
            <option value="bash">Bash Models only</option>
          </select>
        </label>
        <label>Customer
          <select id="summary-filter-customer" data-filter-column="3">
            <option value="">All</option>
            {customer_filter_options}
          </select>
        </label>
        <label>Status
          <select id="summary-filter-status">
            <option value="">Any</option>
            <option value="summary-good">&#x2713; Target met</option>
            <option value="summary-warning">&#x26A0; Between target and VAI 6.1</option>
            <option value="summary-bad">&#x2717; Worse than VAI 6.1</option>
            <option value="summary-unknown">No data</option>
          </select>
        </label>
      </div>
      <table class="summary-table">
        <thead>
          <tr>
            <th title="Targeted for Field Bash (May 20)">Bash</th>
            <th style="min-width:110px">Suite</th>
            <th>Model</th>
            <th>Customer</th>
            <th class="col-latency">VAI 6.2 Latency <span style="text-transform:none">(ms)</span></th>
            <th>RC1 Goal <span style="text-transform:none">(ms)</span></th>
            <th>RC2+ Goal <span style="text-transform:none">(ms)</span></th>
            <th class="col-goal">VAI 6.2 Goal <span style="text-transform:none">(ms)</span></th>
            <th>VAI 6.1 Latency <span style="text-transform:none">(ms)</span></th>
            <th>Today's Gap to Goal <span style="text-transform:none">(ms)</span></th>
            <th>Delta vs. VAI 6.1</th>
            <th title="Trend vs. nearest prior-day reading. Falls back to oldest available if no day-prior data. N/A for the oldest entry.">Day Trend</th>
            <th title="Trend vs. nearest reading ≥7 days ago. Falls back to oldest available if no week-prior data. N/A for the oldest entry.">Week Trend</th>
          </tr>
        </thead>
        <tbody>
          {summary_rows}
        </tbody>
      </table>
      {rc2_footnote}
    </section>
    <section>
      <h2 style="display:flex;justify-content:space-between;align-items:center">
        <span>Details</span>
        <span style="display:flex;gap:8px">
          <button onclick="document.querySelectorAll('.detail-card').forEach(e=>e.open=true)"
            style="font-size:0.78rem;padding:4px 10px;background:#2a2a2a;color:{_TEXT};border:1px solid {_BORDER};border-radius:4px;cursor:pointer">Expand All</button>
          <button onclick="document.querySelectorAll('.detail-card').forEach(e=>e.open=false)"
            style="font-size:0.78rem;padding:4px 10px;background:#2a2a2a;color:{_TEXT};border:1px solid {_BORDER};border-radius:4px;cursor:pointer">Collapse All</button>
        </span>
      </h2>
      {detail_sections}
    </section>
  </main>
  <footer style="text-align:center;padding:16px 24px;color:{_MUTED};font-size:0.78rem;border-top:1px solid {_BORDER};margin-top:32px;">
    Inspired by <a href="http://fisweb:8080/proj/vaiml_int/staff/praveeni/perf_tracker/artifacts/dashboard/VE2_QOR_P0_HW_latest.html" target="_blank" rel="noopener">Praveen Iyer's perf-tracker</a>, whose work served as the seed for this dashboard.
  </footer>
  <script>
    function applySummaryFilters() {{
      const table = document.querySelector(".summary-table");
      if (!table) return;
      const columnFilters = Array.from(document.querySelectorAll("[data-filter-column]"));
      const statusFilter = document.getElementById("summary-filter-status");
      const bashFilter   = document.getElementById("summary-filter-bash");
      const wantedStatus = statusFilter ? statusFilter.value : "";
      const wantedBash   = bashFilter   ? bashFilter.value   : "";
      for (const row of table.querySelectorAll("tbody tr")) {{
        let visible = true;
        for (const filter of columnFilters) {{
          const needle = filter.value.trim().toLowerCase();
          if (!needle) continue;
          const ci = Number(filter.dataset.filterColumn);
          if ((row.cells[ci]?.textContent || "").toLowerCase() !== needle) {{
            visible = false;
            break;
          }}
        }}
        if (visible && wantedStatus && row.dataset.status !== wantedStatus) visible = false;
        if (visible && wantedBash === "bash" && row.dataset.bash !== "1") visible = false;
        row.style.display = visible ? "" : "none";
      }}
    }}
    for (const el of document.querySelectorAll("[data-filter-column], #summary-filter-status, #summary-filter-bash")) {{
      el.addEventListener("change", applySummaryFilters);
    }}
  </script>
</body>
</html>
"""


def write_dashboard_snapshot(
    rows: Sequence[HistoryRow],
    output_dir: str | Path,
    *,
    snapshot_date: date,
    generated_at: datetime | None = None,
) -> Path:
    generated_at = generated_at or datetime.now().astimezone()
    output_root = Path(output_dir)
    daily_dir = output_root / "daily"
    daily_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = daily_dir / f"{snapshot_date.isoformat()}.html"
    snapshot_path.write_text(
        render_dashboard_html(rows, snapshot_date=snapshot_date, generated_at=generated_at),
        encoding="utf-8",
    )
    _refresh_latest_alias(snapshot_path, output_root / "latest.html")
    return snapshot_path


def write_dashboard_snapshots(rows: Sequence[HistoryRow], output_dir: str | Path) -> list[Path]:
    output_root = Path(output_dir)
    snapshot_dates = _snapshot_dates(rows)
    if not snapshot_dates:
        _remove_existing_path(output_root / "latest.html")
        return []
    generated_at = datetime.now().astimezone()
    return [
        write_dashboard_snapshot(
            rows, output_root, snapshot_date=sd, generated_at=generated_at
        )
        for sd in snapshot_dates
    ]


def write_flat_dashboard_snapshots(
    rows: Sequence[HistoryRow],
    output_dir: str | Path,
    *,
    suite_name: str,
) -> list[Path]:
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    suite_dir = output_root / suite_name
    suite_dir.mkdir(parents=True, exist_ok=True)
    latest_path = output_root / f"{suite_name}_latest.html"
    _remove_stale_flat_suite_snapshots(output_root, suite_name=suite_name)
    snapshot_dates = _snapshot_dates(rows)
    if not snapshot_dates:
        _remove_existing_path(latest_path)
        return []
    generated_at = datetime.now().astimezone()
    snapshot_paths: list[Path] = []
    for sd in snapshot_dates:
        p = suite_dir / f"{sd.isoformat()}.html"
        p.write_text(
            render_dashboard_html(rows, snapshot_date=sd, generated_at=generated_at),
            encoding="utf-8",
        )
        snapshot_paths.append(p)
    _refresh_flat_latest_alias(snapshot_paths[-1], latest_path, output_root=output_root)
    return snapshot_paths


# ── Internal helpers ─────────────────────────────────────────────────────────

def _group_rows_by_model(rows: Sequence[HistoryRow]) -> dict[str, list[HistoryRow]]:
    grouped: dict[str, list[HistoryRow]] = defaultdict(list)
    for row in sorted(rows, key=lambda r: (r.model_name.lower(), r.date)):
        grouped[row.model_name].append(row)
    return grouped


def _build_anchor_by_model(rows_by_model: dict[str, list[HistoryRow]]) -> dict[str, str]:
    anchors: dict[str, str] = {}
    counts: dict[str, int] = defaultdict(int)
    for model_name in sorted(rows_by_model, key=str.lower):
        base = _slugify(model_name) or "item"
        counts[base] += 1
        suffix = "" if counts[base] == 1 else f"-{counts[base]}"
        anchors[model_name] = f"model-{base}{suffix}"
    return anchors


def _render_summary_row(
    row: HistoryRow,
    *,
    anchor: str,
    all_model_rows: list[HistoryRow],
    rc2_changes: dict[str, list[dict]] | None = None,
) -> str:
    status_class = _summary_status_class(row)
    prev_1d = _prev_vart_latency(all_model_rows, row, min_days=1)
    prev_7d = _prev_vart_latency(all_model_rows, row, min_days=7)
    suite_name = escape(_display_model_name(row))
    friendly = escape(_friendly_model_name(row))
    key   = row.test_name or row.model_name
    bash  = is_bash(key)
    bash_cell = (
        '<td style="text-align:center;font-size:1rem" title="Targeted for Field Bash">&#x2713;</td>'
        if bash else
        '<td></td>'
    )
    bash_attr = ' data-bash="1"' if bash else ''
    r1 = rc1_goal(key)
    r2 = rc2_goal(key)
    r2_changed = bool(rc2_changes and key in rc2_changes)
    r2_str = _format_number(r2)
    if r2_changed and r2_str != "NA":
        r2_str = (
            f'{r2_str}<sup style="color:{_GOLD};font-size:0.7em;margin-left:2px" '
            f'title="RC2+ goal updated from Praveen\'s spreadsheet">*</sup>'
        )
    return (
        f'<tr class="{status_class}" data-status="{status_class}"{bash_attr}>'
        f"{bash_cell}"
        f'<td><a href="#{anchor}" style="font-size:0.78rem;word-break:break-all">{suite_name}</a></td>'
        f"<td>{friendly}</td>"
        f"<td>{escape(_display_customer_name(row.section))}</td>"
        f'<td class="col-latency">{_format_number(row.vart_latency_ms)}</td>'
        f"<td>{_format_number(r1)}</td>"
        f"<td>{r2_str}</td>"
        f'<td class="col-goal">{_format_number(row.target_latency_ms)}</td>'
        f"<td>{_format_number(row.vai61_latency_ms)}</td>"
        f"<td>{_format_delta(row.vart_latency_ms, row.target_latency_ms)}</td>"
        f"<td>{_format_delta(row.vart_latency_ms, row.vai61_latency_ms)}</td>"
        f"{_trend_cell(row.vart_latency_ms, prev_1d)}"
        f"{_trend_cell(row.vart_latency_ms, prev_7d)}"
        "</tr>"
    )


def _render_rc2_footnote(
    changes: dict[str, list[dict]],
    latest_rows: list[HistoryRow],
) -> str:
    if not changes:
        return ""
    # Build {test_name: friendly_name} for models in this dashboard
    name_map = {
        (row.test_name or row.model_name): _friendly_model_name(row)
        for row in latest_rows
    }
    # Only include models that appear in this dashboard
    relevant = {k: v for k, v in changes.items() if k in name_map}
    if not relevant:
        return ""

    rows_html = ""
    for test_name, entries in sorted(relevant.items(), key=lambda kv: name_map[kv[0]].lower()):
        for entry in entries:
            old_s = f"{entry['old']:.3f}" if entry["old"] is not None else "—"
            new_s = f"{entry['new']:.3f}"
            rows_html += (
                f"<tr>"
                f"<td>{escape(name_map[test_name])}</td>"
                f"<td style='text-align:center'>{entry['date']}</td>"
                f"<td style='text-align:right'>{old_s}</td>"
                f"<td style='text-align:right'>{new_s}</td>"
                f"</tr>"
            )

    return f"""
<div style="margin-top:12px;font-size:0.82rem">
  <p style="color:{_GOLD};font-size:0.78rem;text-transform:uppercase;
     letter-spacing:0.05em;margin:0 0 6px">
    <sup style="font-size:0.85em">*</sup> RC2+ Goal Change History
    <span style="color:{_MUTED};font-size:0.72rem;text-transform:none;
      letter-spacing:0">— sourced from Praveen's spreadsheet (flag_convergence…xlsx)</span>
  </p>
  <table style="border-collapse:collapse;background:{_TABLE_BG};color:{_TABLE_TEXT};
      font-size:0.82rem;width:auto">
    <thead>
      <tr style="background:{_TABLE_HDR}">
        <th style="padding:6px 12px;text-align:left">Model</th>
        <th style="padding:6px 12px;text-align:center">Date Changed</th>
        <th style="padding:6px 12px;text-align:right">Previous (ms)</th>
        <th style="padding:6px 12px;text-align:right">Updated (ms)</th>
      </tr>
    </thead>
    <tbody>{rows_html}</tbody>
  </table>
</div>"""


def _render_filter_options(values: Sequence[str]) -> str:
    return "\n".join(
        f'<option value="{escape(v)}">{escape(v)}</option>'
        for v in sorted({v for v in values if v}, key=str.lower)
    )


def _render_milestone_legend() -> str:
    today = date.today()
    items = []
    for d, label in MILESTONES:
        passed = today > d
        if passed:
            span_style  = ' style="color:#4caf50"'
            badge_style = ' style="border-left:2.5px dashed #4caf50"'
        else:
            span_style = badge_style = ""
        items.append(
            f'<span{span_style}>'
            f'<span class="milestone-badge"{badge_style}></span>'
            f'{escape(label)} ({d.strftime("%m/%d")})'
            f'</span>'
        )
    return f'<div class="milestone-legend">{"".join(items)}</div>'


def _render_model_trend_chart(rows: Sequence[HistoryRow]) -> str:
    if not rows:
        return '<div class="chart-card"><p class="muted">No data available.</p></div>'

    vart_rows = [row for row in rows if row.vart_latency_ms is not None]
    target_latency = _latest_non_none([row.target_latency_ms for row in rows])
    vai61_latency  = _latest_non_none([row.vai61_latency_ms for row in rows])

    # Collect all values for Y range
    values = [
        v for row in rows
        for v in (row.vart_latency_ms, row.target_latency_ms, row.vai61_latency_ms)
        if v is not None
    ]
    if not values:
        return '<div class="chart-card"><p class="muted">No latency values available.</p></div>'

    # X-axis date range: span data + future milestones
    data_dates = [row.date for row in vart_rows]
    milestone_dates = [d for d, _label in MILESTONES]
    all_x_dates = data_dates + milestone_dates
    min_date = min(all_x_dates) if all_x_dates else date.today()
    max_date = max(all_x_dates) if all_x_dates else date.today()
    if min_date == max_date:
        max_date = min_date + timedelta(days=1)
    date_range_days = (max_date - min_date).days

    # Chart geometry
    width      = max(1000, 160 + date_range_days * 25)
    height     = 380
    left       = 75
    right      = 130
    top        = 40
    bottom     = 90
    plot_width = width - left - right
    plot_height= height - top - bottom

    latest_vart_row = _latest_row_with_vart(rows)
    latest_vart = latest_vart_row.vart_latency_ms if latest_vart_row is not None else None

    padding = max((max(values) - min(values)) * 0.10, 2.0)
    y_min = max(0.0, min(values) - padding)
    y_max = max(values) + padding

    def x_for_date(d: date) -> float:
        return left + (d - min_date).days / date_range_days * plot_width

    def y_for(value: float) -> float:
        return top + (y_max - value) / (y_max - y_min) * plot_height

    parts: list[str] = [
        '<div class="chart-card">',
        '<h4>Latency Trend</h4>',
        '<p class="muted">Daily VART latency vs target and VAI 6.1 baseline. '
        'Gold dashed verticals = upcoming milestones.</p>',
        '<div class="chart-scroll">',
        f'<svg class="model-trend-chart" viewBox="0 0 {width} {height}" role="img" '
        'aria-label="Latency trend chart">',
    ]

    # Y grid lines
    for frac in (0.0, 0.25, 0.5, 0.75, 1.0):
        val = y_max - (y_max - y_min) * frac
        y   = top + plot_height * frac
        parts.append(
            f'<line class="grid" x1="{left:.1f}" y1="{y:.1f}" '
            f'x2="{width - right:.1f}" y2="{y:.1f}"/>'
        )
        parts.append(
            f'<text class="tick-label" x="{left - 8:.1f}" y="{y + 4:.1f}" '
            f'text-anchor="end">{_format_number(val)}</text>'
        )

    # Axes
    parts.append(
        f'<line class="axis" x1="{left:.1f}" y1="{top + plot_height:.1f}" '
        f'x2="{width - right:.1f}" y2="{top + plot_height:.1f}"/>'
    )
    parts.append(
        f'<line class="axis" x1="{left:.1f}" y1="{top:.1f}" '
        f'x2="{left:.1f}" y2="{top + plot_height:.1f}"/>'
    )

    # Milestone vertical lines
    for ms_date, ms_label in MILESTONES:
        x = x_for_date(ms_date)
        parts.append(
            f'<line class="milestone-line" x1="{x:.1f}" y1="{top:.1f}" '
            f'x2="{x:.1f}" y2="{top + plot_height:.1f}" stroke="{_GOLD}"/>'
        )
        parts.append(
            f'<text class="milestone-label" x="{x:.1f}" y="{top - 6:.1f}" '
            f'fill="{_GOLD}">{escape(ms_label)} ({ms_date.strftime("%m/%d")})</text>'
        )

    # Horizontal reference lines
    reference_markers = [
        ("VAI 6.1", vai61_latency, "reference-vai61"),
        ("Latest VART", latest_vart, "reference-vart"),
        ("Target", target_latency, "reference-target"),
    ]
    for label, val, css in reference_markers:
        if val is None:
            continue
        y = y_for(val)
        parts.append(
            f'<line class="reference-line {css}" x1="{left:.1f}" y1="{y:.1f}" '
            f'x2="{width - right:.1f}" y2="{y:.1f}">'
            f'<title>{escape(label)}: {_format_number(val)} ms</title></line>'
        )
        parts.append(
            f'<text class="reference-label {css}" x="{width - right + 8:.1f}" y="{y + 4:.1f}" '
            f'fill="{_ref_color(css)}">{escape(label)}: {_format_number(val)} ms</text>'
        )

    # VART polyline
    if len(vart_rows) >= 2:
        pts = " ".join(
            f"{x_for_date(r.date):.1f},{y_for(r.vart_latency_ms):.1f}"  # type: ignore[arg-type]
            for r in vart_rows
        )
        parts.append(
            f'<polyline class="line line-vart" points="{pts}">'
            "<title>Daily VART latency</title></polyline>"
        )

    # VART data points
    for row in vart_rows:
        if row.vart_latency_ms is None:
            continue
        x = x_for_date(row.date)
        y = y_for(row.vart_latency_ms)
        is_latest = row is latest_vart_row
        extra = " latest-vart-point" if is_latest else ""
        label = f'{row.date.strftime("%m/%d")}: {_format_number(row.vart_latency_ms)} ms'
        parts.append(
            f'<circle class="chart-point point-vart{extra}" cx="{x:.1f}" cy="{y:.1f}" r="4">'
            f'<title>{escape(label)}</title></circle>'
        )

    # X-axis date ticks (label every nth data point to avoid crowding)
    step = max(1, len(vart_rows) // 8)
    for i, row in enumerate(vart_rows):
        if i % step != 0 and row is not latest_vart_row:
            continue
        x = x_for_date(row.date)
        label = row.date.strftime("%m-%d")
        if row is latest_vart_row:
            label += " ★"
        parts.append(
            f'<text class="tick-label" x="{x:.1f}" y="{height - 6:.1f}" '
            f'text-anchor="middle">{escape(label)}</text>'
        )

    parts.append("</svg></div>")

    # Legend
    parts.append(
        f'<div class="legend">'
        f'<span><span class="legend-line" style="color:{_TEAL}"></span>'
        f'<span class="legend-dot" style="border:2px solid {_TEAL};background:{_BG}"></span>'
        f'Daily VART</span>'
        f'<span><span class="legend-line legend-dashed" style="color:{_GOLD}"></span>'
        f'Target</span>'
        f'<span><span class="legend-line legend-dashed" style="color:#7a7a7a"></span>'
        f'VAI 6.1</span>'
        f'<span><span class="legend-line legend-dashed" style="color:{_GOLD};opacity:0.7"></span>'
        f'Milestone</span>'
        f'</div>'
    )
    parts.append("</div>")
    return "\n".join(parts)


def _ref_color(css: str) -> str:
    return {"reference-vai61": "#7a7a7a", "reference-vart": _TEAL, "reference-target": _GOLD}.get(css, _TEXT)


def _render_detail_section(
    model_name: str,
    rows: Sequence[HistoryRow],
    *,
    snapshot_date: date,
    anchor: str,
) -> str:
    trend_chart = _render_model_trend_chart(rows)
    trend_rows_html = "\n".join(
        (
            "<tr>"
            f"<td>{row.date.isoformat()}</td>"
            f"<td>{_format_number(row.vart_latency_ms)}</td>"
            f"<td>{_format_number(row.target_latency_ms)}</td>"
            f"<td>{_format_number(row.vai61_latency_ms)}</td>"
            f"<td>{escape(row.error or '')}</td>"
            "</tr>"
        )
        for row in rows
    )
    return f"""
<details class="detail-card" id="{anchor}">
  <summary style="cursor:pointer;list-style:none;display:flex;align-items:center;gap:8px">
    <span class="detail-arrow" style="color:{_GOLD};font-size:0.9rem;display:inline-block;transition:transform 0.15s">&#9654;</span>
    <h3 style="margin:0;display:inline">{_render_model_heading(model_name, rows)}</h3>
    <span class="muted" style="font-size:0.82rem;font-weight:normal">
      &nbsp;|&nbsp; Customer: {escape(_display_customer_name(rows[-1].section) or 'NA')}
      &nbsp;|&nbsp; Through {snapshot_date.isoformat()}
    </span>
  </summary>
  {trend_chart}
  <table class="trend-table">
    <thead>
      <tr><th>Date</th><th>VART 6.2 Latency (ms)</th><th>VAI 6.2 Goal (ms)</th><th>VAI 6.1 Latency (ms)</th><th>Error</th></tr>
    </thead>
    <tbody>
      {trend_rows_html}
    </tbody>
  </table>
</details>
""".strip()


def _render_model_heading(model_name: str, rows: Sequence[HistoryRow]) -> str:
    display_name = _display_model_name(rows[-1])
    url = _xoah_history_url(rows[-1])
    if url is None:
        return escape(display_name)
    return f'<a href="{escape(url)}" target="_blank" rel="noopener">{escape(display_name)}</a>'


def _display_customer_name(section: str | None) -> str:
    if not section:
        return ""
    return _CUSTOMER_NAMES.get(section, section)


def _display_model_name(row: HistoryRow) -> str:
    return row.test_name or row.model_name


def _friendly_model_name(row: HistoryRow) -> str:
    test_name = row.test_name or row.model_name
    return _MODEL_NAMES.get(test_name, test_name)


def _prev_vart_latency(
    rows: list[HistoryRow], latest_row: HistoryRow, *, min_days: int
) -> float | None:
    cutoff = latest_row.date - timedelta(days=min_days)
    for row in reversed(rows):
        if row.date <= cutoff and row.vart_latency_ms is not None:
            return row.vart_latency_ms
    # Fallback: return oldest available reading that predates this row
    for row in rows:
        if row.date < latest_row.date and row.vart_latency_ms is not None:
            return row.vart_latency_ms
    return None  # This IS the oldest entry → caller renders N/A


def _trend_cell(current: float | None, prev: float | None) -> str:
    if current is None:
        return '<td style="text-align:center;color:#888">—</td>'
    if prev is None:
        return '<td style="text-align:center;color:#666;font-size:0.82rem">N/A</td>'
    diff = current - prev
    threshold = max(0.1, abs(prev) * 0.001)
    if abs(diff) <= threshold:
        return '<td style="text-align:center;color:#888;font-size:1.1em">→</td>'
    if diff < 0:
        return '<td style="text-align:center;color:#22a050;font-weight:bold;font-size:1.1em">▲</td>'
    return '<td style="text-align:center;color:#c03030;font-weight:bold;font-size:1.1em">▼</td>'


def _xoah_history_url(row: HistoryRow) -> str | None:
    if not all((row.user, row.suite_name, row.super_suite, row.test_name)):
        return None
    return "http://xoah/historydata?" + urlencode(
        {
            "user": row.user,
            "suiteName": row.suite_name,
            "suiteRunName": "LATEST",
            "superSuiteName": row.super_suite,
            "testName": row.test_name,
            "relBranch": row.rel_branch,
            "platform": "LNX64",
            "taskName": "board",
        }
    )


def _slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def _format_number(value: float | None) -> str:
    if value is None:
        return "NA"
    return f"{value:.3f}"


def _format_delta(lhs: float | None, rhs: float | None) -> str:
    if lhs is None or rhs is None:
        return "NA"
    return f"{lhs - rhs:+.3f}"


def _summary_status_class(row: HistoryRow) -> str:
    if row.vart_latency_ms is None:
        return "summary-unknown"
    if row.target_latency_ms is not None and row.vart_latency_ms <= row.target_latency_ms:
        return "summary-good"
    if row.vai61_latency_ms is not None and row.vart_latency_ms > row.vai61_latency_ms:
        return "summary-bad"
    return "summary-warning"


def _latest_non_none(values: Sequence[float | None]) -> float | None:
    for v in reversed(values):
        if v is not None:
            return v
    return None


def _latest_row_with_vart(rows: Sequence[HistoryRow]) -> HistoryRow | None:
    for row in reversed(rows):
        if row.vart_latency_ms is not None:
            return row
    return None


_PDT = timezone(timedelta(hours=-7))

def _format_generated_at(generated_at: datetime) -> str:
    if generated_at.tzinfo is not None and generated_at.utcoffset() is not None:
        generated_at = generated_at.astimezone(_PDT)
    return generated_at.strftime("%Y-%m-%d %-I:%M %p PDT")


def _snapshot_dates(rows: Sequence[HistoryRow]) -> list[date]:
    return sorted({row.date for row in rows})


def _refresh_latest_alias(snapshot_path: Path, latest_path: Path) -> None:
    _remove_existing_path(latest_path)
    try:
        latest_path.symlink_to(Path("daily") / snapshot_path.name)
    except (NotImplementedError, OSError):
        latest_path.write_text(snapshot_path.read_text(encoding="utf-8"), encoding="utf-8")


def _refresh_flat_latest_alias(
    snapshot_path: Path, latest_path: Path, *, output_root: Path
) -> None:
    _remove_existing_path(latest_path)
    relative_path = snapshot_path.relative_to(output_root)
    try:
        latest_path.symlink_to(relative_path)
    except (NotImplementedError, OSError):
        latest_path.write_text(snapshot_path.read_text(encoding="utf-8"), encoding="utf-8")


def _remove_existing_path(path: Path) -> None:
    if path.exists() or path.is_symlink():
        path.unlink()


def _remove_stale_flat_suite_snapshots(output_root: Path, *, suite_name: str) -> None:
    for stale in output_root.glob(f"{suite_name}_20*.html"):
        _remove_existing_path(stale)
