# VAI 6.2 QoR Performance Tracker

Automated daily dashboard tracking VART latency for all P0 and O3 models across the Vitis AI 6.2
release cycle. Produces dark-themed AMD-styled HTML dashboards with trend charts, milestone markers,
and per-model detail tables. Served live at `http://xcoanupcs40x:8742/`.

---

## What this does

Each daily run:

1. Reads the baseline workbook (targets, VAI 6.1 latency, model metadata)
2. Queries XOAH via YODATools for all nightly suite runs not yet in the history CSV
3. Reads the board log file for each test run and extracts VART latency
4. Merges new records into the canonical history CSV (CSV is the long-term cache)
5. Writes dated HTML snapshots + `latest.html` for each suite
6. Regenerates the `index.html` landing page

**Key dates tracked:**

| Milestone | Date |
|-----------|------|
| RC2 | May 13, 2026 |
| QoR Checkpoint | May 18, 2026 |
| FV Bash | May 20, 2026 |

---

## Directory layout

```
perf_tracker/
├── src/perf_tracker/       # Python package
│   ├── config.py           # Config loading
│   ├── dashboard.py        # HTML generation (dark AMD theme)
│   ├── history.py          # History CSV read/write
│   ├── milestones.py       # RC2 / QoR checkpoint / FV Bash dates
│   ├── pipeline.py         # Orchestration
│   ├── workbook.py         # Excel parsing
│   └── xoah.py             # XOAH query + board log extraction
├── scripts/
│   └── run_dashboard.py    # CLI entry point
├── config/
│   ├── tracking_config.json         # Mac / dev config
│   └── tracking_config_vdi.json     # VDI production config
├── deploy/
│   ├── install.sh           # One-time VDI setup
│   ├── vdi.md               # Step-by-step VDI deploy instructions
│   ├── gen_index.py         # Generates index.html landing page
│   ├── perf-dashboard.service  # systemd oneshot generator
│   ├── perf-dashboard.timer     # systemd daily timer (12:07)
│   └── perf-server.service      # systemd HTTP server (port 8742)
└── artifacts/               # Generated outputs (not committed)
    ├── history/
    │   ├── VE2_QOR_P0_HW.csv
    │   └── VE2_QOR_O3_HW.csv
    └── dashboard/
        ├── index.html
        ├── VE2_QOR_P0_HW_latest.html
        ├── VE2_QOR_P0_HW/YYYY-MM-DD.html
        ├── VE2_QOR_O3_HW_latest.html
        └── VE2_QOR_O3_HW/YYYY-MM-DD.html
```

---

## Daily operations

### Normal day — automated

The systemd timer fires at **12:07 every day** and runs the full pipeline automatically.
Nothing needs to be done manually on a normal day.

```bash
# Verify the timer will fire
systemctl --user status perf-dashboard.timer

# See when it last ran and what happened
journalctl --user -u perf-dashboard.service --since "24 hours ago"
```

### Trigger a manual refresh

```bash
systemctl --user start perf-dashboard.service

# Watch the log in real time
journalctl --user -u perf-dashboard.service -f
```

### Drop a new workbook (refresh without waiting for XOAH)

When the baseline workbook is updated (targets change, new models added):

```bash
XOAHENV=/wrk/xcohdnobkup4/anupcs/vai/vai-6-2/qor/xoahenv
TRACKER=/wrk/xcohdnobkup4/anupcs/vai/vai-6-2/qor/perf_tracker
CONFIG=$TRACKER/config/tracking_config_vdi.json

# Copy the new workbook to the expected location
cp /path/to/new_baselines.xlsx \
   /wrk/xcohdnobkup4/anupcs/vai/vai-6-2/qor/VAI_6.2_P0_QOR_dashboard_baselines.xlsx

# Regenerate using cached XOAH history + new workbook (fast, no XOAH fetch)
$XOAHENV/bin/python $TRACKER/scripts/run_dashboard.py --from-workbook \
    /wrk/xcohdnobkup4/anupcs/vai/vai-6-2/qor/VAI_6.2_P0_QOR_dashboard_baselines.xlsx \
    $CONFIG
```

### Regenerate from a history CSV

If you have a corrected or externally produced CSV and want to regenerate the dashboard without
touching XOAH or the workbook:

```bash
XOAHENV=/wrk/xcohdnobkup4/anupcs/vai/vai-6-2/qor/xoahenv
TRACKER=/wrk/xcohdnobkup4/anupcs/vai/vai-6-2/qor/perf_tracker

$XOAHENV/bin/python $TRACKER/scripts/run_dashboard.py \
    --from-csv /wrk/xcohdnobkup4/anupcs/vai/vai-6-2/qor/artifacts/history/VE2_QOR_P0_HW.csv \
    $TRACKER/config/tracking_config_vdi.json
```

### Regenerate the index landing page

The landing page is also regenerated automatically after each pipeline run. To regenerate it
standalone:

```bash
/wrk/xcohdnobkup4/anupcs/vai/vai-6-2/qor/xoahenv/bin/python \
    /wrk/xcohdnobkup4/anupcs/vai/vai-6-2/qor/perf_tracker/deploy/gen_index.py \
    /wrk/xcohdnobkup4/anupcs/vai/vai-6-2/qor/artifacts/dashboard
```

---

## Data flow

```
workbook (.xlsx)          XOAH database
     │                        │
     │  model metadata        │  nightly test runs (via YODATools)
     │  (targets, VAI 6.1)    │  → reads board log → VART latency
     └──────────┬─────────────┘
                │
          pipeline.py
                │
          history CSV  ←── long-term cache, survives XOAH retention
                │
          dashboard.py
                │
          HTML snapshots + index.html
                │
          http.server (port 8742)
                │
          browser
```

**Why the history CSV matters:** XOAH only retains run data for a limited time. The CSV is the
permanent record. The pipeline never re-fetches a suite run already in the CSV. Run it daily so
nothing falls out of XOAH's retention window before being captured.

---

## Services

| Service | Role | Command |
|---------|------|---------|
| `perf-server.service` | Serves dashboard on port 8742 | `systemctl --user status perf-server` |
| `perf-dashboard.timer` | Triggers daily pipeline at 12:07 | `systemctl --user status perf-dashboard.timer` |
| `perf-dashboard.service` | Oneshot pipeline run | `systemctl --user start perf-dashboard` |

```bash
# Check all three at once
systemctl --user status perf-server perf-dashboard.timer perf-dashboard

# Restart HTTP server (needed after code sync or if port 8742 goes down)
systemctl --user restart perf-server

# View today's pipeline log
journalctl --user -u perf-dashboard.service --since today
```

Logs also written to:
- `/wrk/xcohdnobkup4/anupcs/vai/vai-6-2/qor/logs/dashboard.log`
- `/wrk/xcohdnobkup4/anupcs/vai/vai-6-2/qor/logs/server.log`

---

## CLI reference

```
python scripts/run_dashboard.py [OPTIONS] [config_path]

Options:
  (none)               Full pipeline: workbook + XOAH fetch + dashboard
  --from-workbook XLSX Load this workbook; use cached CSV; skip XOAH
  --no-xoah            Use workbook from config; use cached CSV; skip XOAH
  --from-csv CSV       Regenerate dashboard from CSV only; skip everything else
  --output-dir DIR     Override dashboard output directory
  --suite NAME         Suite name (used with --from-csv)
```

---

## Updating the code

Code lives on your Mac and is pushed to the VDI via rsync. After any change:

```bash
# From Mac terminal
VDIHOST=xcoanupcs40x
VDI_QOR=/wrk/xcohdnobkup4/anupcs/vai/vai-6-2/qor
MAC_TRACKER="/Users/anupcs/Library/CloudStorage/OneDrive-AdvancedMicroDevicesInc/Claude-Code/vai/vai 6.2/qor/perf_tracker"

rsync -av --progress \
  --exclude='__pycache__' --exclude='*.pyc' --exclude='.pytest_cache' \
  --exclude='*.egg-info' --exclude='artifacts/' --exclude='*.bak*' \
  "$MAC_TRACKER/" $VDIHOST:${VDI_QOR}/perf_tracker/

# Then on the VDI — reinstall the package if src/ changed
/wrk/xcohdnobkup4/anupcs/vai/vai-6-2/qor/xoahenv/bin/pip install -e \
    /wrk/xcohdnobkup4/anupcs/vai/vai-6-2/qor/perf_tracker --quiet

# Restart HTTP server if deploy/ or dashboard assets changed
systemctl --user restart perf-server
```

---

## Troubleshooting

**Dashboard not updating / timer not firing:**
```bash
systemctl --user list-timers --all | grep perf
journalctl --user -u perf-dashboard.service -n 50
```

**HTTP server down (port 8742 not responding):**
```bash
systemctl --user restart perf-server
systemctl --user status perf-server
```

**YODATools import fails:**
```bash
# Check xoahenv has it
/wrk/xcohdnobkup4/anupcs/vai/vai-6-2/qor/xoahenv/bin/python \
    -c "import YODATools; print(YODATools.__file__)"

# If it fails, re-check the .pth file is pointing to the right parent directory
cat /wrk/xcohdnobkup4/anupcs/vai/vai-6-2/qor/xoahenv/lib/python3.*/site-packages/yodatools.pth

# Verify Praveeni's env still works (the source of truth for the path)
/wrk/xcohdnobkup6/praveeni/yoda_env/bin/python \
    -c "import YODATools, os; print(os.path.dirname(os.path.dirname(YODATools.__file__)))"
```

**Board logs not readable (models show 'VART latency not found'):**

This means XOAH returned test rows but the log files on the compute farm aren't accessible.
The board log paths (under `/wrk/...`) must be NFS-mounted on xcoanupcs40x. Check:
```bash
ls /wrk/xcohdnobkup6/    # should list directories, not give a permissions error
```

If the mount is missing, use `--from-workbook` or `--from-csv` as a fallback until resolved.

**Services don't survive logout:**
```bash
sudo loginctl enable-linger $USER
loginctl show-user $USER | grep Linger   # must show Linger=yes
```

---

## First-time VDI setup

See `deploy/vdi.md` for the complete step-by-step setup guide.
