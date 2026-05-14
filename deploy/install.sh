#!/usr/bin/env bash
# One-time setup: creates a Python venv, installs dependencies, and wires up
# systemd user services for daily automation.
#
# Run from the repo root:  bash deploy/install.sh
#
# Prerequisites:
#   - Python 3.10+
#   - systemd (user session)
#   - YODATools accessible on your filesystem (see README.md)
#   - Copy deploy/perf-dashboard.service.example → deploy/perf-dashboard.service
#     and deploy/perf-server.service.example → deploy/perf-server.service,
#     then edit both with your actual paths before running this script.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="${REPO_ROOT}/venv"
ARTIFACTS="${REPO_ROOT}/artifacts"
SYSTEMD_USER="${HOME}/.config/systemd/user"

# ── 1. Directory layout ───────────────────────────────────────────────────────
mkdir -p \
    "${ARTIFACTS}/dashboard" \
    "${ARTIFACTS}/history" \
    "${ARTIFACTS}/logs" \
    "${SYSTEMD_USER}"

# ── 2. Python venv ────────────────────────────────────────────────────────────
if [ ! -d "${VENV}" ]; then
    echo "Creating venv at ${VENV} ..."
    python3 -m venv "${VENV}"
fi

"${VENV}/bin/pip" install --upgrade pip --quiet
"${VENV}/bin/pip" install openpyxl --quiet
"${VENV}/bin/pip" install -e "${REPO_ROOT}" --quiet

# YODATools runtime dependencies
"${VENV}/bin/pip" install \
    "elasticsearch<8" \
    pyyaml pexpect cachetools numpy pandas requests paramiko \
    --quiet

echo "venv ready at ${VENV}"

# ── 3. Wire in YODATools via .pth file ───────────────────────────────────────
# Edit YODA_PATH below to point to your YODATools parent directory.
YODA_PATH="/path/to/YODATools/parent"
PY_VER=$("${VENV}/bin/python" -c "import sys; print(f'python{sys.version_info.major}.{sys.version_info.minor}')")
echo "${YODA_PATH}" > "${VENV}/lib/${PY_VER}/site-packages/yodatools.pth"
echo "YODATools .pth written → ${YODA_PATH}"

# ── 4. Install systemd user units ─────────────────────────────────────────────
for unit in perf-dashboard.service perf-dashboard.timer perf-server.service; do
    src="${REPO_ROOT}/deploy/${unit}"
    if [ ! -f "${src}" ]; then
        echo "WARNING: ${src} not found — copy the .example file and edit paths first"
        continue
    fi
    cp "${src}" "${SYSTEMD_USER}/${unit}"
    echo "Installed: ${SYSTEMD_USER}/${unit}"
done

systemctl --user daemon-reload

systemctl --user enable --now perf-server.service
echo "perf-server.service started"

systemctl --user enable --now perf-dashboard.timer
echo "perf-dashboard.timer enabled"

echo ""
echo "Done. Run the first dashboard generation:"
echo "  ${VENV}/bin/python ${REPO_ROOT}/scripts/run_dashboard.py ${REPO_ROOT}/config/tracking_config.json"
