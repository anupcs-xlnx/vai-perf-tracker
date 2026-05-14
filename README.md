# VAI Perf Tracker

Automated daily VART latency dashboard for Vitis AI QoR tracking. Pulls nightly test results from
an Elasticsearch test database (XOAH) via YODATools, appends to a history CSV, and generates
dark-themed AMD-styled HTML dashboards served over HTTP.

Inspired by [Praveen Iyer's perf tracker](http://fisweb:8080/proj/vaiml_int/staff/praveeni/perf_tracker).

---

## Navigating the dashboard

### Landing page (`index.html`)

- **Milestone timeline** — key release dates with a days-remaining countdown
- **Suite calendar** — which suite ran on which date, color-coded pass/fail
- **Field Bash models** — focused table of models being demonstrated at the validation event, with RC1 and RC2+ goal comparisons

### Daily snapshot (`<SUITE>/<YYYY-MM-DD>.html`)

Each test suite gets one HTML snapshot per day. The page has two sections:

**Summary table** — one row per model:

| Column | What it shows |
|--------|---------------|
| Model | Human-readable model name; links to the detail card below |
| Customer | Customer or program the model belongs to |
| VAI 6.2 Latency | Measured VART latency for this run (ms) — steel-blue border |
| Suite | Which XOAH suite run produced this result |
| VAI 6.2 Goal | RC2+ target latency (ms) — muted-red border |
| RC1 Goal | RC1 target latency (ms) |
| VAI 6.1 Latency | Baseline from the prior release for reference |
| Trend | Direction vs ~7 days ago (↓ better, ↑ worse, `N/A` = oldest entry, `—` = no current reading) |
| Bash | Whether this model is on the Field Bash demo list |

**Row color coding:**
- Green — at or below goal
- Yellow — within 5% of goal
- Red — more than 5% above goal
- Gray — no goal defined

**RC2+ goal change footnote:** If any model's RC2+ goal changed since initial publication, the
changed cells are marked with a gold `*` and a footnote table below the summary shows the
before/after values and dates.

**Per-model detail cards** — below the summary, each model has a latency trend chart with
milestone markers and a full table of every historical run.

### Latest symlink (`<SUITE>_latest.html`)

Always points to the most recent snapshot. Bookmark this for day-to-day monitoring.

---

## Repository layout

```
perf_tracker/
├── src/perf_tracker/           # Python package
│   ├── config.py               # Config loading
│   ├── dashboard.py            # HTML generation
│   ├── history.py              # History CSV read/write
│   ├── milestones.py           # Milestone dates
│   ├── model_goals.py          # RC1/RC2+ goals; loads live overrides at import
│   ├── pipeline.py             # Orchestration
│   ├── workbook.py             # Excel baseline parsing
│   └── xoah.py                 # XOAH query + board log extraction via YODATools
├── scripts/
│   └── run_dashboard.py        # CLI entry point
├── config/
│   └── tracking_config.json    # Config template — copy and fill in your paths
├── deploy/
│   ├── install.sh                      # One-time setup script
│   ├── gen_index.py                    # Generates index.html landing page
│   ├── sync_rc2_goals.py               # Downloads live RC2+ goals from SharePoint
│   ├── perf-dashboard.service.example  # systemd oneshot template
│   ├── perf-dashboard.timer            # systemd daily timer
│   └── perf-server.service.example     # systemd HTTP server template
└── artifacts/                  # Generated outputs (not committed)
    ├── history/<SUITE>.csv
    └── dashboard/
        ├── index.html
        ├── <SUITE>_latest.html
        └── <SUITE>/YYYY-MM-DD.html
```

---

## Dependencies

- **Python 3.10+**
- **YODATools** — AMD internal library for querying XOAH (Elasticsearch). Not a pip package; must
  be made importable via a `.pth` file in your Python environment (see [Setup](#setup) below).
- **`elasticsearch < 8`** — YODATools uses the v7 API; v8 drops the `host=` kwarg and breaks it.
- **`openpyxl`** — for reading the baseline workbook and live goals spreadsheet
- **`pyyaml`, `pexpect`, `cachetools`, `numpy`, `pandas`, `requests`, `paramiko`** — YODATools runtime dependencies

---

## Setup

### 1. Configure

Copy `config/tracking_config.json` and fill in your paths:

```json
{
  "workbook_path": "/path/to/your/baselines.xlsx",
  "workbook_history_year": 2026,
  "xoah_summary_url": "http://your-xoah-host/summary?...",
  "history_csv_path": "/path/to/artifacts/history/history.csv",
  "dashboard_output_dir": "/path/to/artifacts/dashboard",
  "suites": [
    {
      "name": "YOUR_SUITE_NAME",
      "workbook_sheet": "YourWorkbookSheetName",
      "history_csv_path": "/path/to/artifacts/history/YOUR_SUITE_NAME.csv"
    }
  ]
}
```

Update `src/perf_tracker/model_goals.py` with your model names and RC1/RC2+ targets.
Update `src/perf_tracker/milestones.py` with your milestone dates.

### 2. Create a Python environment

```bash
python3 -m venv venv
venv/bin/pip install --upgrade pip
venv/bin/pip install openpyxl "elasticsearch<8" pyyaml pexpect cachetools numpy pandas requests paramiko
venv/bin/pip install -e .
```

### 3. Wire in YODATools

YODATools is not a pip package. Make it importable by adding a `.pth` file pointing to its parent
directory:

```bash
# Find your Python version
PY_VER=$(venv/bin/python -c "import sys; print(f'python{sys.version_info.major}.{sys.version_info.minor}')")

# Create the .pth file
echo "/path/to/YODATools/parent" > venv/lib/${PY_VER}/site-packages/yodatools.pth

# Verify
venv/bin/python -c "import YODATools; print('OK:', YODATools.__file__)"
```

### 4. Run the first generation

```bash
venv/bin/python scripts/run_dashboard.py config/tracking_config.json
```

On first run this fetches all historical XOAH data for your suites, which may take several minutes.
Subsequent runs only fetch rows not already in the history CSV.

### 5. Serve the dashboard

```bash
venv/bin/python -m http.server --bind 0.0.0.0 <PORT> \
    --directory /path/to/artifacts/dashboard
```

Open `http://<your-host>:<PORT>/` in a browser.

---

## Automating with systemd

For daily automation on a Linux host where you have a persistent user session:

1. Copy the example service files and edit paths and port:
   ```bash
   cp deploy/perf-dashboard.service.example deploy/perf-dashboard.service
   cp deploy/perf-server.service.example    deploy/perf-server.service
   # edit both files — replace all /path/to/... and <PORT>
   ```

2. Install and enable:
   ```bash
   mkdir -p ~/.config/systemd/user
   cp deploy/perf-dashboard.service deploy/perf-dashboard.timer deploy/perf-server.service \
       ~/.config/systemd/user/
   systemctl --user daemon-reload
   systemctl --user enable --now perf-server.service
   systemctl --user enable --now perf-dashboard.timer
   ```

3. Ensure services survive logout (run once, requires sudo):
   ```bash
   sudo loginctl enable-linger $USER
   ```

The timer fires daily at 12:07 by default — edit `deploy/perf-dashboard.timer` to change the time.

### Service execution order

`perf-dashboard.service` runs three steps in sequence:

1. **ExecStartPre** — `sync_rc2_goals.py` fetches the live goals spreadsheet from SharePoint and
   updates `rc2_goals_live.json`. Always exits 0 so a SharePoint outage never blocks the dashboard.
2. **ExecStart** — `run_dashboard.py` fetches XOAH data, updates the history CSV, and writes all
   HTML snapshots.
3. **ExecStartPost** — `gen_index.py` regenerates the landing page.

### Regenerate without fetching new data

```bash
venv/bin/python scripts/run_dashboard.py --no-xoah config/tracking_config.json
venv/bin/python deploy/gen_index.py /path/to/artifacts/dashboard
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

## Live RC2+ goal sync (optional)

If your team maintains a live goals spreadsheet on SharePoint, `deploy/sync_rc2_goals.py` can
download it daily and update the dashboard's RC2+ targets automatically.

Update the `SHEET_TO_TEST` mapping and `SHARE_URL` in `sync_rc2_goals.py` for your spreadsheet.
Authentication uses a Microsoft Graph token stored at `~/.config/microsoft-graph/token.json`
(obtained via the `m365-teams` auth script). The sync script auto-refreshes the access token using
the stored refresh token so the VDI runs independently without a laptop.

When a goal changes, the dashboard marks the affected cell with a gold `*` and renders a footnote
table showing the before/after values and date of change.

---

## Design decisions

**Column borders instead of background highlights.** The latency and goal columns use colored
borders (steel-blue and muted-red) rather than fills, so the green/yellow/red row status colors
remain fully visible without the column highlight overriding them.

**`(ms)` stays lowercase.** CSS `text-transform: uppercase` on table headers would render `(ms)` as
`(MS)`. It is wrapped in `<span style="text-transform:none">` to prevent this.

**History CSV as the long-term cache.** XOAH only retains run data for a limited window. The
pipeline writes every fetched result to CSV immediately and never re-fetches a row already there.
Run the pipeline daily or data that falls out of XOAH's retention window is lost permanently.

**Trend uses a 7-day lookback with fallback.** The trend column compares today's latency to the
nearest reading at least 7 days prior. If no such reading exists, it falls back to the oldest
available reading. If this is the model's first-ever entry, it shows `N/A` rather than `—` (which
means the current reading is missing, not that prior data doesn't exist yet).

**The sync script always exits 0.** A SharePoint outage or expired token must never prevent the
dashboard from regenerating. Failures are logged but the pipeline continues with cached values.

---

## Adapting for your own project

1. Replace `_GOALS` in `model_goals.py` with your models and targets.
2. Update suite names in `config/tracking_config.json` to match your XOAH suite names.
3. Point `workbook_path` at your own baseline Excel workbook and update the sheet names.
4. Adjust milestone dates in `milestones.py`.
5. If using SharePoint goal sync, update `SHEET_TO_TEST` and `SHARE_URL` in `sync_rc2_goals.py`.

The history CSV schema, dashboard layout, and systemd service files are all reusable as-is.
