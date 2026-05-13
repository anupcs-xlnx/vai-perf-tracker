# perf_tracker — Claude Code Context

## What this project does

Automated daily dashboard tracking VART latency for all P0 and O3 models across the Vitis AI 6.2
release cycle. Pulls nightly test results from XOAH (AMD's internal Elasticsearch test database)
via YODATools, appends to a history CSV, and generates dark-themed AMD-styled HTML dashboards.
Served at **http://xcoanupcs40x:8742/**.

Key milestones tracked: RC1 (2026-05-07), RC2 (2026-05-13), RC2+ (2026-05-18), Field Bash (2026-05-20), RC3 (2026-06-03), Customer Access (2026-06-05).

Public GitHub repo: **https://github.com/anupcs-xlnx/vai-perf-tracker**

---

## Repository layout

```
perf_tracker/
├── src/perf_tracker/           # Python package
│   ├── config.py               # Config loading
│   ├── dashboard.py            # HTML generation (dark AMD theme, off-white summary table)
│   ├── history.py              # History CSV read/write
│   ├── milestones.py           # Milestone dates
│   ├── model_goals.py          # RC1/RC2+ goals per model; loads live overrides from
│   │                           #   rc2_goals_live.json at import time
│   ├── pipeline.py             # Orchestration
│   ├── workbook.py             # Excel parsing
│   └── xoah.py                 # XOAH query + board log extraction via YODATools
│   # Runtime-generated (gitignored):
│   ├── rc2_goals_live.json     # Live RC2+ overrides from Praveen's spreadsheet
│   └── rc2_goal_changes.json   # Persistent changelog of RC2+ goal changes
├── scripts/
│   └── run_dashboard.py        # CLI entry point
├── config/
│   ├── tracking_config.json         # Mac / dev config
│   └── tracking_config_vdi.json     # VDI production config
├── deploy/
│   ├── install.sh               # One-time VDI setup (creates venv only — not xoahenv)
│   ├── vdi.md                   # Step-by-step VDI deploy guide (source of truth)
│   ├── gen_index.py             # Generates index.html landing page
│   ├── gen_goal_reconciliation.py  # Generates goal_reconciliation.html
│   ├── gen_model_ref.py         # Generates model-ref.html (model reference cards)
│   ├── sync_rc2_goals.py        # Downloads Praveen's XLSX from SharePoint, diffs RC2+
│   │                            #   goals, updates rc2_goals_live.json + changelog
│   ├── perf-dashboard.service   # systemd oneshot; ExecStartPre=sync_rc2_goals.py
│   ├── perf-dashboard.timer     # systemd daily timer (12:07 MDT = 11:07 AM PDT)
│   └── perf-server.service      # systemd HTTP server (port 8742)
└── artifacts/                   # Generated outputs (not committed)
    ├── history/
    │   ├── VE2_QOR_P0_HW.csv
    │   └── VE2_QOR_O3_HW.csv
    └── dashboard/
        ├── index.html
        ├── VE2_QOR_P0_HW_latest.html
        ├── VE2_QOR_P0_HW/          # Daily snapshots: 2026-04-18.html … 2026-05-13.html
        ├── goal_reconciliation.html
        └── model-ref.html
```

---

## VDI deployment

- **Host:** xcoanupcs40x (SSH alias configured, accessible directly as `ssh xcoanupcs40x`)
- **VDI base path:** `/wrk/xcohdnobkup4/anupcs/vai/vai-6-2/qor/`
- **VDI shell:** tcsh — bash syntax requires `bash` first
- **Full deploy guide:** `deploy/vdi.md`

### Python environments on VDI

| Environment | Path | Purpose |
|-------------|------|---------|
| `venv` | `/wrk/.../qor/venv/` | Created by install.sh; NOT used for production |
| `xoahenv` | `/wrk/.../qor/xoahenv/` | Production env; has YODATools + all deps |

Always use **xoahenv** for running the dashboard. The venv was an early setup artifact.

### YODATools

YODATools is NOT a pip package. It lives at `/proj/testcases/xtc/tools/PROD/libs/python` on the
shared NFS filesystem. It is made importable in xoahenv via a `.pth` file:

```
/wrk/xcohdnobkup4/anupcs/vai/vai-6-2/qor/xoahenv/lib/python3.10/site-packages/yodatools.pth
```

Contents of that file: `/proj/testcases/xtc/tools/PROD/libs/python`

YODATools dependencies installed in xoahenv:
- `elasticsearch<8` — MUST be v7 API; v8 breaks `TID/core.py` (`host=` kwarg removed)
- `pyyaml`, `pexpect`, `cachetools`, `numpy`, `pandas`, `requests`, `paramiko`

### Systemd services (all user-level, no sudo needed)

| Service | Status | Role |
|---------|--------|------|
| `perf-server.service` | active (running) | HTTP server on port 8742 |
| `perf-dashboard.timer` | active (waiting) | Fires daily at 12:07 MDT (11:07 AM PDT) |
| `perf-dashboard.service` | oneshot | Full pipeline (sync goals → XOAH fetch → dashboard) |

### Service execution order (perf-dashboard.service)

1. **ExecStartPre:** `sync_rc2_goals.py` — fetches Praveen's XLSX from SharePoint, diffs RC2+ goals
2. **ExecStart:** `run_dashboard.py` — XOAH fetch + CSV update + all snapshot HTML generation
3. **ExecStartPost (×3):** `gen_index.py`, `gen_goal_reconciliation.py`, `gen_model_ref.py`

The sync script always exits 0 — a SharePoint outage never blocks the dashboard.

### Microsoft Graph auth (for sync_rc2_goals.py)

Token stored at `~/.config/microsoft-graph/token.json` on both Mac and VDI.
`sync_rc2_goals.py` auto-refreshes the access token using the refresh token (valid ~90 days).
When the refresh token eventually expires, re-auth from Mac:
```bash
python3 ~/.claude/skills/m365-teams/scripts/auth.py
rsync ~/.config/microsoft-graph/token.json xcoanupcs40x:~/.config/microsoft-graph/token.json
```

### Data flow

XOAH (xcoxoahu10:9200) → YODATools → board log files → history CSV → HTML dashboard → HTTP server

SharePoint XLSX → sync_rc2_goals.py → rc2_goals_live.json → model_goals.py (overrides)

---

## Common operations

### Rsync code changes from Mac to VDI

```bash
rsync -av --progress \
  --exclude='__pycache__' --exclude='*.pyc' --exclude='.pytest_cache' \
  --exclude='*.egg-info' --exclude='artifacts/' --exclude='*.bak*' \
  "/Users/anupcs/Library/CloudStorage/OneDrive-AdvancedMicroDevicesInc/Claude-Code/vai/vai 6.2/qor/perf_tracker/" \
  xcoanupcs40x:/wrk/xcohdnobkup4/anupcs/vai/vai-6-2/qor/perf_tracker/
```

After rsync, reinstall the package:
```bash
ssh xcoanupcs40x bash << 'EOF'
/wrk/xcohdnobkup4/anupcs/vai/vai-6-2/qor/xoahenv/bin/pip install -e \
  /wrk/xcohdnobkup4/anupcs/vai/vai-6-2/qor/perf_tracker --quiet
EOF
```

### Regenerate all dashboard pages (no new XOAH data)

```bash
ssh xcoanupcs40x bash << 'EOF'
XOAHENV=/wrk/xcohdnobkup4/anupcs/vai/vai-6-2/qor/xoahenv
TRACKER=/wrk/xcohdnobkup4/anupcs/vai/vai-6-2/qor/perf_tracker
DASH=/wrk/xcohdnobkup4/anupcs/vai/vai-6-2/qor/artifacts/dashboard

$XOAHENV/bin/python $TRACKER/scripts/run_dashboard.py --no-xoah $TRACKER/config/tracking_config_vdi.json
$XOAHENV/bin/python $TRACKER/deploy/gen_index.py $DASH
$XOAHENV/bin/python $TRACKER/deploy/gen_goal_reconciliation.py $DASH
$XOAHENV/bin/python $TRACKER/deploy/gen_model_ref.py $DASH
EOF
```

### Run manual RC2+ goal sync

```bash
ssh xcoanupcs40x bash << 'EOF'
/wrk/xcohdnobkup4/anupcs/vai/vai-6-2/qor/xoahenv/bin/python \
  /wrk/xcohdnobkup4/anupcs/vai/vai-6-2/qor/perf_tracker/deploy/sync_rc2_goals.py
EOF
```

### Check service health

```bash
ssh xcoanupcs40x "systemctl --user status perf-server.service perf-dashboard.timer"
```

### Push code changes to GitHub

```bash
cd "/Users/anupcs/Library/CloudStorage/OneDrive-AdvancedMicroDevicesInc/Claude-Code/vai/vai 6.2/qor/perf_tracker"
git add -p   # stage selectively
git commit -m "..."
git push
```

---

## Dashboard features

### Pages
| URL | File | Description |
|-----|------|-------------|
| `http://xcoanupcs40x:8742/` | `index.html` | Landing page: milestones, suite calendar, Field Bash list |
| `.../VE2_QOR_P0_HW_latest.html` | symlink | Latest daily snapshot |
| `.../VE2_QOR_P0_HW/2026-05-13.html` | snapshot | Per-date dashboard |
| `.../goal_reconciliation.html` | static | Goal reconciliation vs Sumit's spreadsheet + Jira epics |
| `.../model-ref.html` | static | Model reference cards (architecture, use cases, customers) |

### Summary table column highlights
- **VAI 6.2 Latency** (measured): 3px steel-blue border (`#4a8aaa`), light blue header
- **VAI 6.2 Goal** (target): 2px muted-red border (`#a04040`), light rose header

### RC2+ goal live sync
- `model_goals.py` loads `rc2_goals_live.json` at import (overrides hardcoded RC2 values)
- `rc2_goal_changes.json` stores change history: `{test_name: [{date, old, new}]}`
- Dashboard marks changed RC2+ cells with `*` superscript and renders a footnote table
- Source spreadsheet: Praveen Iyer's `flag_convergence_6_1_vs_6_2_0510_onnx_key.xlsx` on SharePoint

### Customer name display mapping (`dashboard.py`)
```python
_CUSTOMER_NAMES = {
    "SICK-NextGen":      "SICK",
    "IntutiveSurgical":  "Intuitive Surgical",  # typo in CSV
    "IntuitiveSurgical": "Intuitive Surgical",
}
```
Applied via `_display_customer_name()` in summary rows, detail cards, and filter dropdown.

### Timezone
All timestamps display in PDT (UTC-7). VDI runs MDT (UTC-6); conversion: `timedelta(hours=-7)`.
Timer fires 12:07 MDT = **11:07 AM PDT**.

---

## Known issues / gotchas

- **tcsh `Suspended (tty output)`:** Background Python jobs in tcsh get suspended. Fix: always
  launch via `bash`, use `nohup ... > log 2>&1 &`, then `exit`.
- **elasticsearch must be `<8`:** TID/core.py uses the v7 API.
- **`--no-xoah` must NOT be in perf-dashboard.service:** The daily timer needs live XOAH data.
- **History CSV location:** VDI config writes CSVs to `/wrk/.../qor/artifacts/history/`, one
  level above `perf_tracker/`. Do not confuse with `perf_tracker/artifacts/history/` on Mac.
- **Graph token expiry:** Access token (~1hr) auto-refreshed by sync script. Refresh token
  (~90 days) requires manual re-auth when expired (see Microsoft Graph auth section above).
- **`(ms)` in headers:** CSS `text-transform: uppercase` converts `(ms)` to `(MS)`. Fixed by
  wrapping in `<span style="text-transform:none">(ms)</span>` in all affected `<th>` elements.

---

## Contact

Dashboard maintained by Anup Sekhar (anup.sekhar@amd.com).
Inspired by Praveen Iyer's perf-tracker (fisweb:8080/proj/vaiml_int/staff/praveeni/perf_tracker).
