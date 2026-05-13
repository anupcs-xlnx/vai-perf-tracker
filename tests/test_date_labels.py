from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


def _load_date_labels_module():
    try:
        return importlib.import_module("perf_tracker.date_labels")
    except ModuleNotFoundError as exc:
        pytest.fail(f"Expected perf_tracker.date_labels to exist, but import failed: {exc}")


def test_impossible_workbook_date_labels_are_rejected_consistently() -> None:
    date_labels = _load_date_labels_module()

    assert date_labels.is_workbook_date_label("31st February") is False
    with pytest.raises(ValueError, match="Unsupported workbook date label"):
        date_labels.parse_workbook_date_label("31st February", year=2026)
