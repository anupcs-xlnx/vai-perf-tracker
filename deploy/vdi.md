# Deploying perf-tracker to xcoanupcs40x

Target directory on VDI: `/wrk/xcohdnobkup4/anupcs/vai/vai-6-2/qor/`

> **VDI shell is tcsh.** All bash-specific syntax (`VAR=val`, `2>&1`, `$()`) requires running `bash`
> first. Commands below are labeled with which shell to use.

---

## Step 1 — rsync the code to the VDI

Run from your **Mac terminal**. History CSVs are included so already-fetched XOAH data is preserved.

```bash
VDIHOST=xcoanupcs40x
VDI_QOR=/wrk/xcohdnobkup4/anupcs/vai/vai-6-2/qor
MAC_TRACKER="/Users/anupcs/Library/CloudStorage/OneDrive-AdvancedMicroDevicesInc/Claude-Code/vai/vai 6.2/qor/perf_tracker"

# Create target directories on VDI
ssh $VDIHOST "mkdir -p ${VDI_QOR}/perf_tracker ${VDI_QOR}/artifacts/history ${VDI_QOR}/logs"

# Sync source code, scripts, config, deploy files, and history cache
rsync -av --progress \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  --exclude='.pytest_cache' \
  --exclude='*.egg-info' \
  --exclude='artifacts/logs' \
  --exclude='artifacts/reports' \
  --exclude='artifacts/dashboard' \
  --exclude='*.bak*' \
  --exclude='VAI_6.2_P0_QOR_copy.xlsx' \
  --exclude='VAI_6.2_P0_QOR.xlsx' \
  "$MAC_TRACKER/" \
  $VDIHOST:${VDI_QOR}/perf_tracker/
```

## Step 2 — copy the workbook

The VDI config expects the workbook one level above `perf_tracker/`, directly under `qor/`.

```bash
VDIHOST=xcoanupcs40x
VDI_QOR=/wrk/xcohdnobkup4/anupcs/vai/vai-6-2/qor
MAC_WB="/Users/anupcs/Library/CloudStorage/OneDrive-AdvancedMicroDevicesInc/Claude-Code/vai/vai 6.2/qor/perf_tracker/VAI_6.2_P0_QOR_dashboard_baselines.xlsx"

scp "$MAC_WB" $VDIHOST:${VDI_QOR}/VAI_6.2_P0_QOR_dashboard_baselines.xlsx
```

## Step 3 — enable linger (services survive logout)

SSH to the VDI and run once (requires sudo):

```bash
ssh xcoanupcs40x

sudo loginctl enable-linger $USER

# Verify
loginctl show-user $USER | grep Linger   # should print: Linger=yes
```

## Step 4 — create xoahenv with YODATools access

**Do not use the venv created by `install.sh` for XOAH queries.** YODATools is not a pip package —
it lives at `/proj/testcases/xtc/tools/PROD/libs/python` on the shared filesystem. We create a
separate environment (`xoahenv`) and wire YODATools in via a `.pth` file.

> Run `bash` first to get a bash shell (VDI default is tcsh).

```bash
bash   # switch from tcsh to bash

XOAHENV=/wrk/xcohdnobkup4/anupcs/vai/vai-6-2/qor/xoahenv
TRACKER=/wrk/xcohdnobkup4/anupcs/vai/vai-6-2/qor/perf_tracker

# Create the environment
python3 -m venv $XOAHENV

# Install pip dependencies
$XOAHENV/bin/pip install --upgrade pip --quiet
$XOAHENV/bin/pip install openpyxl --quiet
$XOAHENV/bin/pip install -e $TRACKER --quiet

# Install YODATools runtime dependencies (discovered by scanning its imports)
$XOAHENV/bin/pip install \
    "elasticsearch<8" \
    pyyaml \
    pexpect \
    cachetools \
    numpy \
    pandas \
    requests \
    paramiko \
    --quiet

# Wire in YODATools via .pth file
# Find the exact Python version directory first:
ls $XOAHENV/lib/   # e.g. shows python3.10

# Then create the .pth file using the exact version (replace python3.10 if different):
echo "/proj/testcases/xtc/tools/PROD/libs/python" \
    > $XOAHENV/lib/python3.10/site-packages/yodatools.pth

# Verify
$XOAHENV/bin/python -c "import YODATools; print('YODATools OK:', YODATools.__file__)"
```

Expected output: `YODATools OK: /proj/testcases/xtc/tools/PROD/libs/python/YODATools/__init__.py`

### Why `elasticsearch<8`?

TID/core.py calls `Elasticsearch(host=..., port=...)` — the v7 API. The v8 client dropped those
kwargs. Pinning `<8` avoids a `TypeError` at runtime.

## Step 5 — run the first dashboard generation

The VDI shell is tcsh, but background jobs (`&`) in tcsh are suspended if they write to the
terminal (`Suspended (tty output)`). Work around this by switching to bash to launch the job with
`nohup`, then immediately exit back to tcsh. The nohup process outlives the bash session.

```tcsh
# From tcsh — switch to bash, launch, exit back
bash
```

```bash
# Inside bash:
XOAHENV=/wrk/xcohdnobkup4/anupcs/vai/vai-6-2/qor/xoahenv
TRACKER=/wrk/xcohdnobkup4/anupcs/vai/vai-6-2/qor/perf_tracker
LOG=/wrk/xcohdnobkup4/anupcs/vai/vai-6-2/qor/logs/dashboard.log

nohup $XOAHENV/bin/python $TRACKER/scripts/run_dashboard.py \
    $TRACKER/config/tracking_config_vdi.json \
    > $LOG 2>&1 &

echo "PID: $!"
exit   # return to tcsh
```

Monitor progress from tcsh:

```tcsh
tail -f /wrk/xcohdnobkup4/anupcs/vai/vai-6-2/qor/logs/dashboard.log
```

The run is complete when you see:
```
New XOAH rows:    N
Canonical rows:   N
  Suite: VE2_QOR_P0_HW
    Latest: /wrk/.../artifacts/dashboard/VE2_QOR_P0_HW_latest.html
    Snapshots: N
  Suite: VE2_QOR_O3_HW
    ...
```

> **First run takes several minutes** — it fetches every suite run since January. Subsequent runs
> only fetch runs not yet in the history CSV and complete in under a minute.

## Step 6 — generate index.html and start the HTTP server

```tcsh
set XOAHENV=/wrk/xcohdnobkup4/anupcs/vai/vai-6-2/qor/xoahenv
set TRACKER=/wrk/xcohdnobkup4/anupcs/vai/vai-6-2/qor/perf_tracker

# Generate the landing page
$XOAHENV/bin/python $TRACKER/deploy/gen_index.py \
    /wrk/xcohdnobkup4/anupcs/vai/vai-6-2/qor/artifacts/dashboard

# Start the HTTP server (temporary — for testing; Step 7 makes it permanent)
$XOAHENV/bin/python -m http.server 8742 \
    --directory /wrk/xcohdnobkup4/anupcs/vai/vai-6-2/qor/artifacts/dashboard &
```

Open **http://xcoanupcs40x:8742/** in a browser to verify the dashboard is live.

## Step 7 — wire up systemd for daily automation

This makes the daily timer and HTTP server survive logout.

```tcsh
# Update the installed systemd service files to use xoahenv
sed -i 's|/qor/venv/bin/python|/qor/xoahenv/bin/python|g' \
    ~/.config/systemd/user/perf-dashboard.service
sed -i 's|/qor/venv/bin/python|/qor/xoahenv/bin/python|g' \
    ~/.config/systemd/user/perf-server.service

# Reload systemd and start services
systemctl --user daemon-reload
systemctl --user start perf-server.service
systemctl --user enable perf-dashboard.timer
systemctl --user start perf-dashboard.timer

# Verify
systemctl --user status perf-server.service     # should be active/running
systemctl --user status perf-dashboard.timer    # should be active/waiting
```

Also update the source service files so future re-syncs stay consistent:

```bash
bash   # switch to bash for sed syntax
sed -i 's|/qor/venv/bin/python|/qor/xoahenv/bin/python|g' \
    /wrk/xcohdnobkup4/anupcs/vai/vai-6-2/qor/perf_tracker/deploy/perf-dashboard.service \
    /wrk/xcohdnobkup4/anupcs/vai/vai-6-2/qor/perf_tracker/deploy/perf-server.service
exit
```

---

## Day-to-day operations

**Trigger a manual refresh (full XOAH fetch + dashboard):**
```tcsh
# From bash (needed to avoid tcsh tostop suspension)
bash
XOAHENV=/wrk/xcohdnobkup4/anupcs/vai/vai-6-2/qor/xoahenv
TRACKER=/wrk/xcohdnobkup4/anupcs/vai/vai-6-2/qor/perf_tracker
LOG=/wrk/xcohdnobkup4/anupcs/vai/vai-6-2/qor/logs/dashboard.log

nohup $XOAHENV/bin/python $TRACKER/scripts/run_dashboard.py \
    $TRACKER/config/tracking_config_vdi.json > $LOG 2>&1 &
exit
```

Or use the systemd oneshot service:
```tcsh
systemctl --user start perf-dashboard.service
journalctl --user -u perf-dashboard.service -f
```

**Drop a new workbook and regenerate (skips XOAH fetch):**
```tcsh
set XOAHENV=/wrk/xcohdnobkup4/anupcs/vai/vai-6-2/qor/xoahenv
set TRACKER=/wrk/xcohdnobkup4/anupcs/vai/vai-6-2/qor/perf_tracker

cp /path/to/new_baselines.xlsx \
   /wrk/xcohdnobkup4/anupcs/vai/vai-6-2/qor/VAI_6.2_P0_QOR_dashboard_baselines.xlsx

$XOAHENV/bin/python $TRACKER/scripts/run_dashboard.py \
    --no-xoah $TRACKER/config/tracking_config_vdi.json
```

**Regenerate from a history CSV only:**
```tcsh
set XOAHENV=/wrk/xcohdnobkup4/anupcs/vai/vai-6-2/qor/xoahenv
set TRACKER=/wrk/xcohdnobkup4/anupcs/vai/vai-6-2/qor/perf_tracker

$XOAHENV/bin/python $TRACKER/scripts/run_dashboard.py \
    --from-csv /wrk/xcohdnobkup4/anupcs/vai/vai-6-2/qor/artifacts/history/VE2_QOR_P0_HW.csv \
    $TRACKER/config/tracking_config_vdi.json
```

**Check service status:**
```tcsh
systemctl --user status perf-server.service
systemctl --user status perf-dashboard.timer
```

**Logs:**
```
/wrk/xcohdnobkup4/anupcs/vai/vai-6-2/qor/logs/dashboard.log
/wrk/xcohdnobkup4/anupcs/vai/vai-6-2/qor/logs/server.log
```

---

## Re-syncing after code changes on Mac

Any time you update code on your Mac, re-run the rsync from Step 1, then:

```tcsh
set XOAHENV=/wrk/xcohdnobkup4/anupcs/vai/vai-6-2/qor/xoahenv
set TRACKER=/wrk/xcohdnobkup4/anupcs/vai/vai-6-2/qor/perf_tracker

# Reinstall the package if src/ changed
$XOAHENV/bin/pip install -e $TRACKER --quiet

# Restart the HTTP server to serve updated static files
systemctl --user restart perf-server.service
```

---

## Troubleshooting

**YODATools import fails:**
```tcsh
# Check the .pth file
cat /wrk/xcohdnobkup4/anupcs/vai/vai-6-2/qor/xoahenv/lib/python3.10/site-packages/yodatools.pth
# Should print: /proj/testcases/xtc/tools/PROD/libs/python

# Test import
/wrk/xcohdnobkup4/anupcs/vai/vai-6-2/qor/xoahenv/bin/python \
    -c "import YODATools; print(YODATools.__file__)"
```

**Background job suspended in tcsh (`Suspended (tty output)`):**
Always launch background Python jobs from bash, not tcsh:
```tcsh
bash
nohup /path/to/python /path/to/script ... > log 2>&1 &
exit
```

**`TypeError: Elasticsearch.__init__() got an unexpected keyword argument 'host'`:**
The elasticsearch v8 client breaks TID/core.py. Downgrade:
```bash
$XOAHENV/bin/pip install "elasticsearch<8"
```

**HTTP server down (port 8742 not responding):**
```tcsh
systemctl --user restart perf-server.service
systemctl --user status perf-server.service
```

**Dashboard not updating / timer not firing:**
```tcsh
systemctl --user list-timers --all | grep perf
journalctl --user -u perf-dashboard.service -n 50
```

**Services don't survive logout:**
```bash
sudo loginctl enable-linger $USER
loginctl show-user $USER | grep Linger   # must show Linger=yes
```

**Board logs not readable (models show 'VART latency not found'):**
```tcsh
ls /wrk/xcohdnobkup6/    # NFS must be mounted; missing mount = no board logs
```
