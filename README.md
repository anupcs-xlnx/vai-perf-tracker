# VAI Perf Tracker

Automated daily latency dashboard for AMD Vitis AI QoR tracking. Pulls nightly VART test results
from an Elasticsearch test database (XOAH) via YODATools, appends to a history CSV, and generates
dark-themed AMD-styled HTML dashboards served over HTTP.

Inspired by [Praveen Iyer's perf tracker](http://fisweb:8080/proj/vaiml_int/staff/praveeni/perf_tracker).

---

## Dashboard pages

### Landing page (`index.html`)

The landing page shows:
- **Milestone timeline** — key release dates (RC1, RC2, RC2+, Field Bash, etc.) with a "days remaining" countdown
- **Suite calendar** — which suite ran on which date, color-coded pass/fail
- **Field Bash models** — a focused table of the subset of models being demonstrated at the Field Validation event, with RC1 and RC2+ goal comparisons

### Daily snapshot (`<SUITE>/<YYYY-MM-DD>.html`)

Each suite gets one HTML file per day. The page has two main sections:

**Summary table** (top)

One row per model. Columns:

| Column | What it shows |
|--------|---------------|
| Model | Human-readable model name (links to the detail card below) |
| Customer | Customer or program the model belongs to |
| VAI 6.2 Latency | Measured VART latency for this run, in ms. Steel-blue border. |
| Suite | Which XOAH suite run produced this result |
| VAI 6.2 Goal | RC2+ target latency in ms. Muted-red border. |
| RC1 Goal | RC1 target latency in ms |
| VAI 6.1 Latency | Baseline from the prior release for reference |
| Trend | Direction vs ~7 days ago (↑ worse, ↓ better, — no prior data) |
| Bash | Whether this model is on the Field Bash demo list |

**Row color coding:**
- Green — at or below goal
- Yellow — within 5% of goal
- Red — more than 5% above goal
- Gray — no goal defined for this model

**RC2+ goal change footnote:** If any model's RC2+ goal changed since initial publication (tracked from a live spreadsheet), the changed cells are marked with a gold `*` and a footnote table below the summary lists the before/after values and dates.

**Per-model detail cards** (below summary)

Clicking a model name in the summary table scrolls to its detail card. Each card shows:
- A latency trend chart with milestone markers
- A full table of every historical run with date, latency, and the suite that produced it

### Latest symlink (`<SUITE>_latest.html`)

Always points to the most recent snapshot. Bookmark this for day-to-day monitoring.

---

## Dashboard design decisions

**Dark AMD theme.** Black background (`#000000`), white text (`#ffffff`), AMD corporate colors for
accents. Off-white background for the summary table to make it easy to read at a glance.

**Column border highlights instead of background colors.** The latency and goal columns use colored
borders (steel-blue and muted-red respectively) rather than background color fills. This preserves
the green/yellow/red row status colors so you can see at a glance which models are on track without
the column highlight masking the row status.

**`(ms)` in lowercase.** CSS `text-transform: uppercase` is applied to table headers for visual
consistency. The `(ms)` unit is wrapped in `<span style="text-transform:none">` to prevent it from
being rendered as `(MS)`.

**History CSV as the long-term cache.** XOAH only retains run data for a limited time. The pipeline
writes every fetched result to a CSV immediately. On subsequent runs, already-fetched rows are
skipped. Run the pipeline daily or you will lose data that falls out of XOAH's retention window.

**Trend indicator uses a 7-day lookback with fallback.** The trend column compares today's latency
to the closest reading at least 7 days prior. If no reading exists that far back, it falls back to
the oldest available reading. If this is the very first entry for a model, it shows `N/A` (no prior
data exists yet, not a missing reading).

**Live RC2+ goal sync.** The RC2+ goal values in `model_goals.py` are hardcoded as a safe fallback.
A separate daily script (`deploy/sync_rc2_goals.py`) downloads the live goals spreadsheet from
SharePoint via the Microsoft Graph API, diffs column D of the `impr_6.2` tab against the current
values, and writes any changes to `src/perf_tracker/rc2_goals_live.json`. This file is loaded at
import time by `model_goals.py` to override the hardcoded values. A persistent changelog
(`rc2_goal_changes.json`) records every change with date, old value, and new value — this powers
the `*` asterisk footnote in the dashboard.

**Token auto-refresh for SharePoint access.** The Microsoft Graph access token expires in ~1 hour.
The sync script checks the `expires_at` field in `~/.config/microsoft-graph/token.json` and
refreshes it automatically using the refresh token (valid ~90 days) before downloading the
spreadsheet. The refreshed token is written back to disk. No manual action is needed unless the
refresh token itself expires.

**PDT timezone display.** All timestamps are shown in PDT (UTC-7). The VDI runs MDT (UTC-6); the
pipeline applies a `-1h` offset before rendering timestamps. The systemd timer fires at
12:07 MDT = **11:07 AM PDT**.

---

## Repository layout

```
perf_tracker/
├── src/perf_tracker/           # Python package
│   ├── config.py               # Config loading
│   ├── dashboard.py            # HTML generation
│   ├── history.py              # History CSV read/write
│   ├── milestones.py           # Milestone dates
│   ├── model_goals.py          # RC1/RC2+ goals per model; loads live overrides at import
│   ├── pipeline.py             # Orchestration
│   ├── workbook.py             # Excel baseline parsing
│   └── xoah.py                 # XOAH query + board log extraction via YODATools
├── scripts/
│   └── run_dashboard.py        # CLI entry point
├── config/
│   ├── tracking_config.json         # Dev config (Mac paths)
│   └── tracking_config_vdi.json     # Production config (VDI paths)
├── deploy/
│   ├── install.sh               # One-time VDI venv setup
│   ├── vdi.md                   # Step-by-step VDI deploy guide
│   ├── gen_index.py             # Generates index.html landing page
│   ├── sync_rc2_goals.py        # Downloads live RC2+ goals from SharePoint
│   ├── perf-dashboard.service   # systemd oneshot (sync goals → dashboard → index)
│   ├── perf-dashboard.timer     # systemd daily timer
│   └── perf-server.service      # systemd HTTP server (port 8742)
└── artifacts/                   # Generated outputs (not committed)
    ├── history/
    │   └── <SUITE>.csv
    └── dashboard/
        ├── index.html
        ├── <SUITE>_latest.html
        └── <SUITE>/YYYY-MM-DD.html
```

---

## Dependencies

- **Python 3.10+**
- **YODATools** — AMD internal library for querying XOAH (Elasticsearch test database). Not a pip package; lives on the shared NFS filesystem at `/proj/testcases/xtc/tools/PROD/libs/python`. Made importable via a `.pth` file in the Python environment.
- **elasticsearch < 8** — YODATools uses the v7 API; v8 removes the `host=` kwarg and breaks it.
- **openpyxl** — for reading the baseline workbook and the live goals spreadsheet
- **pyyaml**, **pexpect**, **cachetools**, **numpy**, **pandas**, **requests**, **paramiko** — YODATools dependencies

---

## Data flow

```
XOAH (Elasticsearch)
    └── YODATools → board log files → VART latency
           │
       pipeline.py
           │
       history CSV  ←── permanent record; survives XOAH retention window
           │
       dashboard.py → dated HTML snapshots + latest.html
           │
       gen_index.py → index.html landing page
           │
       http.server (port 8742)

SharePoint XLSX
    └── sync_rc2_goals.py → rc2_goals_live.json → model_goals.py (overrides)
```

---

## Deployment (VDI)

See `deploy/vdi.md` for the full step-by-step guide. The short version:

1. Create a Python virtual environment and install dependencies (run `deploy/install.sh`)
2. Add a `.pth` file for YODATools into the venv's `site-packages`
3. Copy `deploy/*.service` and `deploy/*.timer` to `~/.config/systemd/user/`
4. `systemctl --user daemon-reload && systemctl --user enable --now perf-server perf-dashboard.timer`

### Pushing code changes from Mac to VDI

```bash
rsync -av --progress \
  --exclude='__pycache__' --exclude='*.pyc' --exclude='.pytest_cache' \
  --exclude='*.egg-info' --exclude='artifacts/' --exclude='*.bak*' \
  /path/to/perf_tracker/ <vdi-host>:/path/to/perf_tracker/

# Reinstall the package after src/ changes
ssh <vdi-host> "xoahenv/bin/pip install -e /path/to/perf_tracker --quiet"
```

### Service execution order

The `perf-dashboard.service` one-shot runs:

1. `ExecStartPre` — `sync_rc2_goals.py` fetches the live goals spreadsheet and updates `rc2_goals_live.json`. Always exits 0 so a SharePoint outage never blocks the dashboard.
2. `ExecStart` — `run_dashboard.py` fetches XOAH data, updates the history CSV, and writes all dated HTML snapshots.
3. `ExecStartPost` — `gen_index.py` regenerates the landing page.

### Regenerate all pages without new XOAH data

```bash
python scripts/run_dashboard.py --no-xoah config/tracking_config_vdi.json
python deploy/gen_index.py /path/to/artifacts/dashboard
```

---

## CLI reference

```
python scripts/run_dashboard.py [OPTIONS] [config_path]

  (none)          Full pipeline: workbook + XOAH fetch + HTML
  --no-xoah       Skip XOAH fetch; regenerate HTML from existing CSV
  --suite NAME    Process only this suite
  --output-dir D  Override dashboard output directory
```

---

## Forking this for your own project

The tracker is intentionally generic. To adapt it:

1. Replace the `_GOALS` dict in `model_goals.py` with your models and targets.
2. Update the `SUITE_NAMES` in `config.py` to match your XOAH suite names.
3. Update `tracking_config.json` with your workbook path, XOAH URL, and output directories.
4. If you use a different spreadsheet for live goal sync, update `SHEET_TO_TEST` in `sync_rc2_goals.py` and point `SHARE_URL` at your file.
5. Adjust milestone dates in `milestones.py`.

The history CSV schema, dashboard layout, and systemd service files are all reusable as-is.
