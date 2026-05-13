"""Per-model RC1/RC2 latency goals and Bash-with-FAEs targeting flag.

Source: vai_6_2_perf_goals.xlsx  tab=impr_6.2
  Col C → VAI 6.2 RC1 goal (ms)
  Col D → VAI 6.2 RC2 goal (ms)  (kept live via sync_rc2_goals.py)
  Col J → 'X' = targeted for Bash with FAEs (May 20)

Keys are the exact test_name strings used in the history CSV / _MODEL_NAMES dict.

Live RC2 overrides are written by deploy/sync_rc2_goals.py into
rc2_goals_live.json (same directory). If that file exists its values
supersede the hardcoded RC2 entries below.
"""
from __future__ import annotations

import json
from pathlib import Path

# (rc1_goal_ms, rc2_goal_ms, is_bash)
_GOALS: dict[str, tuple[float | None, float | None, bool]] = {
    "yolox-s_int8_anduril-hw-vek385_vaiml":
        (4.5,    3.81,   True),
    "yolox-m_int8_anduril-hw-vek385_vaiml":
        (6.2,    5.91,   True),
    "yolox-x-1280x1280_int8_anduril-hw-vek385_vaiml":
        (44.3,   39.82,  True),
    "egolanes-bs1_int8_autoware_aiesw-23104-hw-vek385_vaiml":
        (29.6,   29.6,   True),
    "raft-stereo_fp16_sick_aiesw-13503_t4d1-hw-vek385_vaiml":
        (200.0,  187.6,  True),
    "vit_encoder_b2_s256_d1024_m4096_h16_l12_int8_wavye_t4d2-hw-vek385_vaiml":
        (22.8,   22.8,   True),
    "vit_encoder_b2_s256_d1536_m6144_h16_l12_int8_wavye_t4d2-hw-vek385_vaiml":
        (44.2,   44.2,   True),
    "vit_encoder_b2_s512_d1536_m6144_h16_l12_int8_wavye_t4d2-hw-vek385_vaiml":
        (77.0,   77.0,   True),
    "vit_encoder_b2_s1024_d1536_m6144_h16_l12_int8_wavye_t4d2-hw-vek385_vaiml":
        (174.0,  174.0,  True),
    "deimv2_dinov3_s_bf16-hw-vek385_vaiml":
        (16.0,   14.9,   True),
    "yolox-l_int8_anduril-hw-vek385_vaiml":
        (17.1,   15.52,  True),
    "yolov8m_int8-bf16-hw-vek385_vaiml":
        (15.0,   9.92,   True),
    # ── Non-Bash models with RC1/RC2 goals ──────────────────────────────────
    "bevformer_tiny_rn50_int8_batch6_t1d6-hw-vek385_vaiml":
        (26.0,   24.2,   False),
    "asura_int8_subaru_2x8_t2d1-hw-vek385_vaiml":
        (25.0,   22.9,   False),
    "garuda_int8_subaru_2x8_t2d1-hw-vek385_vaiml":
        (18.5,   17.2,   False),
    "route_2x8_vart_zerocopy_fp16-int8_subaru_t2d1-hw-vek385_vaiml":
        (15.9,   15.7,   False),
    "bevformer_tiny_transformer_bf16_cop-hw-vek385_vaiml":
        (106.0,  13.0,   False),
    # ── Models not in the goals spreadsheet ─────────────────────────────────
    "tinydepth_batch2_int8_intuitive-surgical_aiesw-6307-hw-vek385_vaiml":
        (None,   None,   False),
    "densenet161_int8_fujifilm_aiesw-28363-hw-vek385_vaiml":
        (None,   None,   False),
    "petr-v2_int8-bf16_astemo_aiesw-24634_batch12_t1d6-hw-vek385_vaiml":
        (None,   None,   False),
    "petr-v2-bevseg_int8-bf16_astemo_aiesw-24634_batch12_t1d6-hw-vek385_vaiml":
        (None,   None,   False),
    "yolo11x-seg_1280x1280_int8_focus_aiesw-23284-hw-vek385_vaiml":
        (None,   None,   False),
    "yolo12l_int8-bf16_kria2_aiesw-23285-hw-vek385_vaiml":
        (None,   None,   False),
}

BASH_MODELS: frozenset[str] = frozenset(k for k, v in _GOALS.items() if v[2])

# ── Live RC2 overrides from Praveen's spreadsheet ────────────────────────────
_HERE             = Path(__file__).parent
_LIVE_PATH        = _HERE / "rc2_goals_live.json"
_CHANGELOG_PATH   = _HERE / "rc2_goal_changes.json"

if _LIVE_PATH.exists():
    with open(_LIVE_PATH) as _f:
        for _k, _v in json.load(_f).items():
            if _k in _GOALS:
                _r1, _, _bash = _GOALS[_k]
                _GOALS[_k] = (_r1, float(_v), _bash)

# Friendly names for the landing-page Bash section (display order)
BASH_FRIENDLY_NAMES: list[str] = [
    "Anduril YOLOx-s",
    "Anduril YOLOx-m",
    "Anduril YOLOx-l 640",
    "Anduril YOLOx-l 1280",
    "DINO-nano ViT",
    "Egolanes",
    "RAFT-Stereo",
    "YOLO8m",
    "Wayve ViT s256 d1024",
    "Wayve ViT s256 d1536",
    "Wayve ViT s512 d1536",
    "Wayve ViT s1024 d1536",
]


def rc1_goal(test_name: str) -> float | None:
    return _GOALS.get(test_name, (None, None, False))[0]


def rc2_goal(test_name: str) -> float | None:
    return _GOALS.get(test_name, (None, None, False))[1]


def is_bash(test_name: str) -> bool:
    return _GOALS.get(test_name, (None, None, False))[2]


def rc2_goal_changes() -> dict[str, list[dict]]:
    """Return {test_name: [{date, old, new}, ...]} for models whose RC2 goal changed."""
    if not _CHANGELOG_PATH.exists():
        return {}
    with open(_CHANGELOG_PATH) as f:
        return json.load(f)
