from __future__ import annotations

from datetime import date, datetime
import importlib
import re
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


def _load_dashboard_module():
    try:
        return importlib.import_module("perf_tracker.dashboard")
    except ModuleNotFoundError as exc:
        pytest.fail(f"Expected perf_tracker.dashboard to exist, but import failed: {exc}")


def _load_history_module():
    try:
        return importlib.import_module("perf_tracker.history")
    except ModuleNotFoundError as exc:
        pytest.fail(f"Expected perf_tracker.history to exist, but import failed: {exc}")


def _make_row(
    *,
    row_date: date,
    model_name: str,
    target_latency_ms: float,
    vai61_latency_ms: float,
    vart_latency_ms: float | None,
    error: str | None = None,
):
    history = _load_history_module()
    return history.HistoryRow(
        date=row_date,
        model_name=model_name,
        section="CV",
        focus="Latency",
        customer="Internal",
        gops=123.4,
        stamp_tp="t2d1",
        batch_dp="2x8",
        target_latency_ms=target_latency_ms,
        npu_latency_ms=None,
        vai61_latency_ms=vai61_latency_ms,
        vart_latency_ms=vart_latency_ms,
        aie_latency_ms=None,
        perftest_latency_ms=None,
        source_kind="xoah",
        suite_run_name=f"{row_date:%Y%m%d}_004500_VE2_QOR_P0_HW",
        suite_name="VE2_QOR_P0_HW",
        user="perf-bot",
        rel_branch="release/vai_6.2",
        super_suite="VAI_6_2_GEN2_REGRESSION",
        test_name=f"{model_name}-hw-vek385_vaiml",
        error=error,
    )


def test_render_dashboard_html_contains_summary_table_and_model_detail_anchors() -> None:
    dashboard = _load_dashboard_module()
    rows = [
        _make_row(
            row_date=date(2026, 5, 5),
            model_name="asura_int8_subaru_2x8_t2d1",
            target_latency_ms=1.7,
            vai61_latency_ms=1.9,
            vart_latency_ms=1.4,
        ),
        _make_row(
            row_date=date(2026, 5, 7),
            model_name="phoenix_int8_city",
            target_latency_ms=2.2,
            vai61_latency_ms=2.6,
            vart_latency_ms=2.1,
        ),
    ]

    html = dashboard.render_dashboard_html(
        rows,
        snapshot_date=date(2026, 5, 7),
        generated_at=datetime(2026, 5, 7, 23, 59, 59),
    )

    assert '<table class="summary-table">' in html
    assert "Latest VART (ms)" in html
    assert "<th>Customer</th>" in html
    assert "<td>CV</td>" in html
    assert (
        '<a href="#model-asura-int8-subaru-2x8-t2d1">'
        "asura_int8_subaru_2x8_t2d1-hw-vek385_vaiml</a>"
    ) in html
    assert '<a href="#model-phoenix-int8-city">phoenix_int8_city-hw-vek385_vaiml</a>' in html
    assert 'id="model-asura-int8-subaru-2x8-t2d1"' in html
    assert 'id="model-phoenix-int8-city"' in html
    assert "Trend through 2026-05-07" in html


def test_render_dashboard_html_shows_snapshot_date_and_last_updated_time() -> None:
    dashboard = _load_dashboard_module()
    rows = [
        _make_row(
            row_date=date(2026, 5, 7),
            model_name="asura_int8_subaru_2x8_t2d1",
            target_latency_ms=1.7,
            vai61_latency_ms=1.9,
            vart_latency_ms=1.4,
        )
    ]

    html = dashboard.render_dashboard_html(
        rows,
        snapshot_date=date(2026, 5, 7),
        generated_at=datetime(2026, 5, 8, 13, 36, 9),
    )

    assert "Snapshot date: 2026-05-07" in html
    assert "Last updated: 2026-05-08 13:36:09" in html


def test_render_dashboard_html_contains_xoah_history_links() -> None:
    dashboard = _load_dashboard_module()
    rows = [
        _make_row(
            row_date=date(2026, 5, 7),
            model_name="asura_int8_subaru_2x8_t2d1",
            target_latency_ms=2.0,
            vai61_latency_ms=3.0,
            vart_latency_ms=2.8,
        )
    ]

    html = dashboard.render_dashboard_html(
        rows,
        snapshot_date=date(2026, 5, 7),
        generated_at=datetime(2026, 5, 7, 23, 59, 59),
    )

    assert "XOAH History" not in html
    assert (
        "http://xoah/historydata?"
        "user=perf-bot&amp;suiteName=VE2_QOR_P0_HW&amp;suiteRunName=LATEST&amp;"
        "superSuiteName=VAI_6_2_GEN2_REGRESSION&amp;"
        "testName=asura_int8_subaru_2x8_t2d1-hw-vek385_vaiml&amp;"
        "relBranch=release%2Fvai_6.2&amp;platform=LNX64&amp;taskName=board"
    ) in html
    assert '<h3><a href="http://xoah/historydata?' in html


def test_render_dashboard_html_color_codes_summary_rows() -> None:
    dashboard = _load_dashboard_module()
    rows = [
        _make_row(
            row_date=date(2026, 5, 7),
            model_name="meets_target",
            target_latency_ms=2.0,
            vai61_latency_ms=3.0,
            vart_latency_ms=1.9,
        ),
        _make_row(
            row_date=date(2026, 5, 7),
            model_name="between_target_and_vai61",
            target_latency_ms=2.0,
            vai61_latency_ms=3.0,
            vart_latency_ms=2.5,
        ),
        _make_row(
            row_date=date(2026, 5, 7),
            model_name="worse_than_vai61",
            target_latency_ms=2.0,
            vai61_latency_ms=3.0,
            vart_latency_ms=3.5,
        ),
    ]

    html = dashboard.render_dashboard_html(rows, snapshot_date=date(2026, 5, 7))

    assert 'class="summary-good"' in html
    assert 'class="summary-warning"' in html
    assert 'class="summary-bad"' in html


def test_render_dashboard_html_uses_no_data_color_only_when_latest_vart_is_missing() -> None:
    dashboard = _load_dashboard_module()
    rows = [
        _make_row(
            row_date=date(2026, 5, 7),
            model_name="has_vart_missing_target",
            target_latency_ms=None,
            vai61_latency_ms=3.0,
            vart_latency_ms=2.5,
        ),
        _make_row(
            row_date=date(2026, 5, 7),
            model_name="has_vart_missing_baselines",
            target_latency_ms=None,
            vai61_latency_ms=None,
            vart_latency_ms=2.5,
        ),
        _make_row(
            row_date=date(2026, 5, 7),
            model_name="missing_vart",
            target_latency_ms=2.0,
            vai61_latency_ms=3.0,
            vart_latency_ms=None,
        ),
    ]

    html = dashboard.render_dashboard_html(rows, snapshot_date=date(2026, 5, 7))

    assert html.count('class="summary-unknown"') == 1
    assert html.count('class="summary-warning"') == 2


def test_render_dashboard_html_has_summary_filters() -> None:
    dashboard = _load_dashboard_module()
    rows = [
        _make_row(
            row_date=date(2026, 5, 7),
            model_name="filter_model",
            target_latency_ms=2.0,
            vai61_latency_ms=3.0,
            vart_latency_ms=2.5,
        )
    ]

    html = dashboard.render_dashboard_html(rows, snapshot_date=date(2026, 5, 7))

    assert 'id="summary-filter-model"' in html
    assert 'id="summary-filter-customer"' in html
    assert 'id="summary-filter-status"' in html
    assert '<select id="summary-filter-model" data-filter-column="0">' in html
    assert '<select id="summary-filter-customer" data-filter-column="1">' in html
    assert '<option value="filter_model-hw-vek385_vaiml">filter_model-hw-vek385_vaiml</option>' in html
    assert '<option value="CV">CV</option>' in html
    assert 'data-status="summary-warning"' in html
    assert "function applySummaryFilters()" in html


def test_render_dashboard_html_contains_per_model_latency_line_chart() -> None:
    dashboard = _load_dashboard_module()
    rows = [
        _make_row(
            row_date=date(2026, 5, 5),
            model_name="asura_int8_subaru_2x8_t2d1",
            target_latency_ms=2.0,
            vai61_latency_ms=3.0,
            vart_latency_ms=2.8,
        ),
        _make_row(
            row_date=date(2026, 5, 7),
            model_name="asura_int8_subaru_2x8_t2d1",
            target_latency_ms=2.0,
            vai61_latency_ms=3.0,
            vart_latency_ms=1.8,
        ),
    ]

    html = dashboard.render_dashboard_html(rows, snapshot_date=date(2026, 5, 7))

    assert '<section class="chart-card">' in html
    assert '<div class="chart-scroll">' in html
    assert '<svg class="model-trend-chart"' in html
    assert "Current VART" in html
    assert "Daily VART" in html
    assert "Target" in html
    assert "VAI 6.1" in html
    assert 'class="line line-vart"' in html
    assert 'class="line line-target"' not in html
    assert 'class="line line-vai61"' not in html
    assert html.count("<polyline") == 1
    assert 'class="chart-point point-vai61"' not in html
    assert 'class="chart-point point-target"' not in html
    assert 'class="reference-line reference-vai61"' in html
    assert 'class="reference-line reference-target"' in html
    assert 'class="legend-marker point-vart"' in html
    assert 'class="legend-marker point-vai61"' in html
    assert 'class="legend-marker point-target"' in html
    assert "2026-05-05" in html
    assert "2026-05-07" in html
    assert "VAI 6.1: 3.000 ms" in html
    assert "Target: 2.000 ms" in html
    assert '<polyline class="line line-vart" points="70.0,114.0 890.0,189.0">' in html


def test_render_dashboard_html_highlights_latest_vart_and_labels_reference_y_values() -> None:
    dashboard = _load_dashboard_module()
    rows = [
        _make_row(
            row_date=date(2026, 5, 5),
            model_name="asura_int8_subaru_2x8_t2d1",
            target_latency_ms=2.0,
            vai61_latency_ms=3.0,
            vart_latency_ms=2.8,
        ),
        _make_row(
            row_date=date(2026, 5, 7),
            model_name="asura_int8_subaru_2x8_t2d1",
            target_latency_ms=2.0,
            vai61_latency_ms=3.0,
            vart_latency_ms=1.8,
        ),
    ]

    html = dashboard.render_dashboard_html(rows, snapshot_date=date(2026, 5, 7))

    assert "Latest VART point: 2026-05-07, 1.800 ms" in html
    assert 'class="tick-label latest-date-label"' in html
    assert "05-07 (latest)" in html
    assert 'class="reference-line reference-vai61"' in html
    assert "VAI 6.1: 3.000 ms" in html
    assert 'class="reference-line reference-latest-vart"' in html
    assert "Latest VART: 1.800 ms" in html
    assert 'class="reference-line reference-target"' in html
    assert "Target: 2.000 ms" in html
    assert 'class="chart-point point-vai61"' not in html
    assert 'class="chart-point point-target"' not in html


def test_render_dashboard_html_shows_detail_error_without_graph_point() -> None:
    dashboard = _load_dashboard_module()
    rows = [
        _make_row(
            row_date=date(2026, 5, 5),
            model_name="asura_int8_subaru_2x8_t2d1",
            target_latency_ms=2.0,
            vai61_latency_ms=3.0,
            vart_latency_ms=2.8,
        ),
        _make_row(
            row_date=date(2026, 5, 7),
            model_name="asura_int8_subaru_2x8_t2d1",
            target_latency_ms=2.0,
            vai61_latency_ms=3.0,
            vart_latency_ms=None,
            error="FAIL: board crashed",
        ),
    ]

    html = dashboard.render_dashboard_html(rows, snapshot_date=date(2026, 5, 7))

    assert "FAIL: board crashed" in html
    assert "<th>Error</th>" in html
    assert "Current VART: 2.800 ms" in html
    assert "Current VART: NA" not in html


def test_render_dashboard_html_respects_snapshot_date_cutoff() -> None:
    dashboard = _load_dashboard_module()
    rows = [
        _make_row(
            row_date=date(2026, 5, 5),
            model_name="asura_int8_subaru_2x8_t2d1",
            target_latency_ms=1.7,
            vai61_latency_ms=1.9,
            vart_latency_ms=1.4,
        ),
        _make_row(
            row_date=date(2026, 5, 7),
            model_name="asura_int8_subaru_2x8_t2d1",
            target_latency_ms=1.7,
            vai61_latency_ms=1.9,
            vart_latency_ms=1.3,
        ),
        _make_row(
            row_date=date(2026, 5, 8),
            model_name="asura_int8_subaru_2x8_t2d1",
            target_latency_ms=1.7,
            vai61_latency_ms=1.9,
            vart_latency_ms=0.9,
        ),
    ]

    html = dashboard.render_dashboard_html(
        rows,
        snapshot_date=date(2026, 5, 7),
        generated_at=datetime(2026, 5, 7, 23, 59, 59),
    )

    assert "2026-05-08" not in html
    assert ">0.900<" not in html
    assert ">1.300<" in html


def test_render_dashboard_html_uses_collision_proof_model_anchors() -> None:
    dashboard = _load_dashboard_module()
    rows = [
        _make_row(
            row_date=date(2026, 5, 7),
            model_name="resnet-50",
            target_latency_ms=1.7,
            vai61_latency_ms=1.9,
            vart_latency_ms=1.3,
        ),
        _make_row(
            row_date=date(2026, 5, 7),
            model_name="resnet 50",
            target_latency_ms=2.2,
            vai61_latency_ms=2.6,
            vart_latency_ms=2.1,
        ),
    ]

    html = dashboard.render_dashboard_html(rows, snapshot_date=date(2026, 5, 7))

    summary_targets = re.findall(r'<a href="#(model-[^"]+)">', html)
    detail_targets = re.findall(r'<section class="detail-card" id="([^"]+)">', html)

    assert len(summary_targets) == 2
    assert len(set(summary_targets)) == 2
    assert set(detail_targets) == set(summary_targets)


def test_write_dashboard_snapshots_creates_dated_files_and_latest_symlink(
    tmp_path: Path,
) -> None:
    dashboard = _load_dashboard_module()
    rows = [
        _make_row(
            row_date=date(2026, 5, 5),
            model_name="asura_int8_subaru_2x8_t2d1",
            target_latency_ms=1.7,
            vai61_latency_ms=1.9,
            vart_latency_ms=1.4,
        ),
        _make_row(
            row_date=date(2026, 5, 7),
            model_name="asura_int8_subaru_2x8_t2d1",
            target_latency_ms=1.7,
            vai61_latency_ms=1.9,
            vart_latency_ms=1.3,
        ),
        _make_row(
            row_date=date(2026, 5, 7),
            model_name="phoenix_int8_city",
            target_latency_ms=2.2,
            vai61_latency_ms=2.6,
            vart_latency_ms=2.1,
        ),
    ]

    written_paths = dashboard.write_dashboard_snapshots(rows, output_dir=tmp_path)

    assert written_paths == [
        tmp_path / "daily" / "2026-05-05.html",
        tmp_path / "daily" / "2026-05-07.html",
    ]
    assert all(path.exists() for path in written_paths)

    first_snapshot = written_paths[0].read_text(encoding="utf-8")
    second_snapshot = written_paths[1].read_text(encoding="utf-8")
    assert "phoenix_int8_city" not in first_snapshot
    assert "phoenix_int8_city" in second_snapshot

    latest_path = tmp_path / "latest.html"
    assert latest_path.is_symlink()
    assert latest_path.readlink() == Path("daily/2026-05-07.html")
    assert latest_path.resolve() == written_paths[-1]


def test_write_dashboard_snapshots_falls_back_to_copy_when_symlink_creation_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dashboard = _load_dashboard_module()
    rows = [
        _make_row(
            row_date=date(2026, 5, 7),
            model_name="asura_int8_subaru_2x8_t2d1",
            target_latency_ms=1.7,
            vai61_latency_ms=1.9,
            vart_latency_ms=1.3,
        )
    ]

    def _raise_symlink_error(self: Path, target: Path, target_is_directory: bool = False) -> None:
        raise OSError("symlinks unavailable")

    monkeypatch.setattr(Path, "symlink_to", _raise_symlink_error)

    written_paths = dashboard.write_dashboard_snapshots(rows, output_dir=tmp_path)

    latest_path = tmp_path / "latest.html"
    assert written_paths == [tmp_path / "daily" / "2026-05-07.html"]
    assert latest_path.exists()
    assert not latest_path.is_symlink()
    assert latest_path.read_text(encoding="utf-8") == written_paths[-1].read_text(
        encoding="utf-8"
    )


def test_write_dashboard_snapshots_with_no_rows_removes_stale_latest_alias(
    tmp_path: Path,
) -> None:
    dashboard = _load_dashboard_module()
    latest_path = tmp_path / "latest.html"
    latest_path.write_text("stale dashboard", encoding="utf-8")

    written_paths = dashboard.write_dashboard_snapshots([], output_dir=tmp_path)

    assert written_paths == []
    assert not latest_path.exists()
