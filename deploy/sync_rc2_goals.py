#!/usr/bin/env python3
"""Sync RC2+ latency goals from Praveen's live SharePoint spreadsheet.

Reads the impr_6.2 tab, column D (VAI 6.2 RC2) from:
  flag_convergence_6_1_vs_6_2_0510_onnx_key.xlsx

Compares with current values in model_goals.py. If any changed:
  - Updates src/perf_tracker/rc2_goals_live.json  (overrides for model_goals.py)
  - Appends to src/perf_tracker/rc2_goal_changes.json  (persistent changelog)

Designed to be called as ExecStartPre in perf-dashboard.service.
Always exits 0 so a SharePoint outage does not block dashboard generation.
"""
from __future__ import annotations

import base64
import io
import json
import os
import sys
import time
import traceback
import urllib.request
import urllib.parse
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT  = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

TOKEN_FILE   = Path.home() / ".config" / "microsoft-graph" / "token.json"
LIVE_PATH    = SRC_ROOT / "perf_tracker" / "rc2_goals_live.json"
CHANGES_PATH = SRC_ROOT / "perf_tracker" / "rc2_goal_changes.json"

SHARE_URL = (
    "https://amdcloud-my.sharepoint.com/:x:/r/personal/praveeni_amd_com"
    "/Documents/flag_convergence_6_1_vs_6_2_0510_onnx_key.xlsx"
    "?d=wb4cdeda81bb243ef8888d10050f3d2b4&csf=1&web=1&e=fmrlZf"
)

# ── Mapping: spreadsheet onnx_basename → tracker test_name ───────────────────
SHEET_TO_TEST: dict[str, str] = {
    "Anduril_yolox_s-640x640":
        "yolox-s_int8_anduril-hw-vek385_vaiml",
    "Anduril_yolox_m-640x640":
        "yolox-m_int8_anduril-hw-vek385_vaiml",
    "Anduril_yolox_l-1280x1280_full_quant.onnx":
        "yolox-x-1280x1280_int8_anduril-hw-vek385_vaiml",
    "egolanes_bs1_aiesw_23104-int8-no_calib.onnx":
        "egolanes-bs1_int8_autoware_aiesw-23104-hw-vek385_vaiml",
    "raft_v5.onnx":
        "raft-stereo_fp16_sick_aiesw-13503_t4d1-hw-vek385_vaiml",
    "Wavye_vit_encoder_b1_s256_d1024_m4096":
        "vit_encoder_b2_s256_d1024_m4096_h16_l12_int8_wavye_t4d2-hw-vek385_vaiml",
    "Wavye_vit_encoder_b1_s256_d1536_m6144":
        "vit_encoder_b2_s256_d1536_m6144_h16_l12_int8_wavye_t4d2-hw-vek385_vaiml",
    "Wavye_vit_encoder_b1_s512_d1536_m6144":
        "vit_encoder_b2_s512_d1536_m6144_h16_l12_int8_wavye_t4d2-hw-vek385_vaiml",
    "Wavye_vit_encoder_b1_s1024_d1536_m6144":
        "vit_encoder_b2_s1024_d1536_m6144_h16_l12_int8_wavye_t4d2-hw-vek385_vaiml",
    "bevformer_tiny_rn50_int8_batch6_t1d6":
        "bevformer_tiny_rn50_int8_batch6_t1d6-hw-vek385_vaiml",
    "dino-nano_bf16_sick_aiesw-24988":
        "deimv2_dinov3_s_bf16-hw-vek385_vaiml",
    "Anduril_yolox_l-1x3x640x640_full_quant.onnx":
        "yolox-l_int8_anduril-hw-vek385_vaiml",
    "asura_int8_subaru_2x8_t2d1":
        "asura_int8_subaru_2x8_t2d1-hw-vek385_vaiml",
    "garuda_int8_subaru_2x8_t2d1":
        "garuda_int8_subaru_2x8_t2d1-hw-vek385_vaiml",
    "route_2x8_vart_zerocopy_fp16-int8_subaru_t2d1":
        "route_2x8_vart_zerocopy_fp16-int8_subaru_t2d1-hw-vek385_vaiml",
    "bevformer_tiny_transformer_bf16_cop":
        "bevformer_tiny_transformer_bf16_cop-hw-vek385_vaiml",
    "yolov8m-1x3x640x640_tail_non_quant.onnx":
        "yolov8m_int8-bf16-hw-vek385_vaiml",
}


def _get_access_token() -> str:
    """Return a valid access token, refreshing it first if it has expired."""
    with open(TOKEN_FILE) as f:
        token_data = json.load(f)

    expires_at = token_data.get("expires_at", 0)
    if time.time() < expires_at - 60:
        return token_data["access_token"]

    # Access token expired — use refresh token to get a new one
    refresh_token = token_data["refresh_token"]
    client_id     = token_data["client_id"]
    tenant_id     = token_data["tenant_id"]

    url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
    body = urllib.parse.urlencode({
        "grant_type":    "refresh_token",
        "client_id":     client_id,
        "refresh_token": refresh_token,
        "scope":         "https://graph.microsoft.com/.default offline_access",
    }).encode()
    req = urllib.request.Request(url, data=body, method="POST")
    with urllib.request.urlopen(req, timeout=30) as r:
        new_token = json.loads(r.read())

    # Persist refreshed token back to disk for next run
    token_data["access_token"]  = new_token["access_token"]
    token_data["expires_at"]    = time.time() + new_token.get("expires_in", 3600)
    if "refresh_token" in new_token:
        token_data["refresh_token"] = new_token["refresh_token"]
    with open(TOKEN_FILE, "w") as f:
        json.dump(token_data, f, indent=2)
    print("Access token refreshed and saved.")

    return token_data["access_token"]


def _download_xlsx(access_token: str) -> bytes:
    encoded  = base64.urlsafe_b64encode(SHARE_URL.encode()).rstrip(b"=").decode()
    share_id = f"u!{encoded}"
    meta_url = f"https://graph.microsoft.com/v1.0/shares/{share_id}/driveItem"
    req = urllib.request.Request(
        meta_url, headers={"Authorization": f"Bearer {access_token}"}
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        meta = json.loads(r.read())
    dl_url = meta["@microsoft.graph.downloadUrl"]
    with urllib.request.urlopen(dl_url, timeout=60) as r:
        return r.read()


def _read_col_d(xlsx_bytes: bytes) -> dict[str, float]:
    """Return {onnx_basename: rc2_goal_ms} for valid numeric rows."""
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(xlsx_bytes), read_only=True, data_only=True)
    ws = wb["impr_6.2"]
    result: dict[str, float] = {}
    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i == 0:
            continue  # header
        name, _, _, col_d = row[0], row[1], row[2], row[3]
        if not isinstance(name, str):
            continue
        if not isinstance(col_d, (int, float)):
            continue  # skip #DIV/0!, None, etc.
        result[name.strip()] = float(col_d)
    return result


def _load_json(path: Path) -> dict:
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {}


def _save_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def sync() -> None:
    from perf_tracker.model_goals import rc2_goal as current_rc2

    token      = _get_access_token()
    xlsx_bytes = _download_xlsx(token)
    live_sheet = _read_col_d(xlsx_bytes)

    # Build {test_name: new_value} for models we track
    new_live: dict[str, float] = {}
    for sheet_name, test_name in SHEET_TO_TEST.items():
        if sheet_name in live_sheet:
            new_live[test_name] = live_sheet[sheet_name]

    # Load existing live overrides and changelog
    prev_live = _load_json(LIVE_PATH)   # {test_name: float}
    changelog  = _load_json(CHANGES_PATH)  # {test_name: [{date,old,new}]}

    today_str = date.today().isoformat()
    changed: list[tuple[str, float | None, float]] = []

    for test_name, new_val in new_live.items():
        # Current authoritative value: live override > hardcoded
        if test_name in prev_live:
            old_val: float | None = prev_live[test_name]
        else:
            old_val = current_rc2(test_name)

        if old_val is None or abs(new_val - old_val) > 0.001:
            changed.append((test_name, old_val, new_val))
            entry = {"date": today_str, "old": old_val, "new": new_val}
            changelog.setdefault(test_name, []).append(entry)

    if changed:
        for test_name, old_val, new_val in changed:
            old_str = f"{old_val:.3f}" if old_val is not None else "None"
            print(f"  RC2+ changed: {test_name}")
            print(f"    {old_str} → {new_val:.3f}")
        _save_json(LIVE_PATH, new_live)
        _save_json(CHANGES_PATH, changelog)
        print(f"Updated {LIVE_PATH.name} and {CHANGES_PATH.name} ({len(changed)} change(s))")
    else:
        # Always write live values to keep them fresh (in case file was missing)
        _save_json(LIVE_PATH, new_live)
        print("No RC2+ goal changes detected.")


def main() -> None:
    try:
        sync()
    except Exception:
        print("WARNING: sync_rc2_goals failed (dashboard will use cached values):")
        traceback.print_exc()
        sys.exit(0)  # never block the dashboard


if __name__ == "__main__":
    main()
