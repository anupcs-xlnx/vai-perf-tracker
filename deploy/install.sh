#!/usr/bin/env bash
# Deploy perf-tracker to xcoanupcs40x (no sudo required).
# Run this script once from the VDI, inside the project directory.
# Usage:  bash deploy/install.sh

set -euo pipefail

QOR_ROOT="/wrk/xcohdnobkup4/anupcs/vai/vai-6-2/qor"
TRACKER_ROOT="${QOR_ROOT}/perf_tracker"
VENV="${QOR_ROOT}/venv"
DASHBOARD_DIR="${QOR_ROOT}/artifacts/dashboard"
LOG_DIR="${QOR_ROOT}/logs"
SYSTEMD_USER="${HOME}/.config/systemd/user"

# ── 1. Create directory layout ───────────────────────────────────────────────
mkdir -p \
    "${DASHBOARD_DIR}" \
    "${QOR_ROOT}/artifacts/history" \
    "${LOG_DIR}" \
    "${SYSTEMD_USER}"

# ── 2. Python venv ───────────────────────────────────────────────────────────
if [ ! -d "${VENV}" ]; then
    echo "Creating venv at ${VENV} ..."
    python3 -m venv "${VENV}"
fi

"${VENV}/bin/pip" install --upgrade pip --quiet
"${VENV}/bin/pip" install openpyxl --quiet
# Install perf_tracker in editable mode
"${VENV}/bin/pip" install -e "${TRACKER_ROOT}" --quiet

echo "venv ready."

# ── 3. Install systemd user units ────────────────────────────────────────────
for unit in perf-dashboard.service perf-dashboard.timer perf-server.service; do
    src="${TRACKER_ROOT}/deploy/${unit}"
    dst="${SYSTEMD_USER}/${unit}"
    cp "${src}" "${dst}"
    echo "Installed: ${dst}"
done

systemctl --user daemon-reload

# Enable and start the HTTP server
systemctl --user enable --now perf-server.service
echo "perf-server.service started on port 8742."

# Enable the daily refresh timer
systemctl --user enable --now perf-dashboard.timer
echo "perf-dashboard.timer enabled (daily at 12:07)."

# ── 4. Run first dashboard generation ────────────────────────────────────────
echo ""
echo "Running initial dashboard generation (may take a while with XOAH) ..."
"${VENV}/bin/python" "${TRACKER_ROOT}/scripts/run_dashboard.py" \
    "${TRACKER_ROOT}/config/tracking_config_vdi.json"

echo ""
echo "Done!  Dashboard available at:"
echo "  http://$(hostname):8742/"
echo ""
echo "To refresh manually (e.g. after dropping a new workbook or CSV):"
echo "  # From workbook:"
echo "  ${VENV}/bin/python ${TRACKER_ROOT}/scripts/run_dashboard.py \\"
echo "      --from-workbook /path/to/new.xlsx \\"
echo "      ${TRACKER_ROOT}/config/tracking_config_vdi.json"
echo ""
echo "  # From CSV:"
echo "  ${VENV}/bin/python ${TRACKER_ROOT}/scripts/run_dashboard.py \\"
echo "      --from-csv /path/to/history.csv \\"
echo "      ${TRACKER_ROOT}/config/tracking_config_vdi.json"
echo ""
echo "Logs:"
echo "  ${LOG_DIR}/dashboard.log"
echo "  ${LOG_DIR}/server.log"
