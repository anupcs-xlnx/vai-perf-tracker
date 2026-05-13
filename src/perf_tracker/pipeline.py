from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from perf_tracker.config import SuiteConfig, TrackingConfig
from perf_tracker.dashboard import (
    write_dashboard_snapshots,
    write_flat_dashboard_snapshots,
)
from perf_tracker.history import (
    HistoryRow,
    merge_history_rows,
    nightly_records_to_history_rows,
    read_history_csv,
    refresh_xoah_history_rows,
    write_history_csv,
)
from perf_tracker.workbook import ParsedWorkbook, parse_workbook
from perf_tracker.xoah import NightlyRecord, XOAHSource, extract_available_nightly_records


class NightlyExtractor(Protocol):
    def __call__(
        self,
        parsed_workbook: ParsedWorkbook,
        source: XOAHSource,
        *,
        suite_name: str,
        cached_suite_run_names: set[str],
    ) -> Sequence[NightlyRecord]: ...


@dataclass(frozen=True)
class SuitePipelineResult:
    suite_name: str
    history_csv_path: Path
    dashboard_output_dir: Path
    latest_dashboard_path: Path
    snapshot_paths: list[Path]
    workbook_seeded_row_count: int
    prior_xoah_row_count: int
    current_xoah_row_count: int
    canonical_row_count: int


@dataclass(frozen=True)
class PipelineResult:
    history_csv_path: Path
    dashboard_output_dir: Path
    latest_dashboard_path: Path
    snapshot_paths: list[Path]
    workbook_seeded_row_count: int
    prior_xoah_row_count: int
    current_xoah_row_count: int
    canonical_row_count: int
    suite_results: list[SuitePipelineResult]


def run_pipeline(
    config: TrackingConfig,
    *,
    nightly_extractor: NightlyExtractor = extract_available_nightly_records,
) -> PipelineResult:
    source = XOAHSource.from_summary_url(config.xoah_summary_url)
    suite_results = [
        _run_suite_pipeline(
            config,
            suite,
            source=source,
            nightly_extractor=nightly_extractor,
            use_legacy_dashboard_layout=_uses_legacy_single_suite_layout(config, suite),
        )
        for suite in config.suites
    ]

    if len(suite_results) > 1:
        _remove_existing_path(config.dashboard_output_dir / "latest.html")

    first_result = suite_results[0]
    return PipelineResult(
        history_csv_path=first_result.history_csv_path,
        dashboard_output_dir=first_result.dashboard_output_dir,
        latest_dashboard_path=first_result.latest_dashboard_path,
        snapshot_paths=first_result.snapshot_paths,
        workbook_seeded_row_count=sum(result.workbook_seeded_row_count for result in suite_results),
        prior_xoah_row_count=sum(result.prior_xoah_row_count for result in suite_results),
        current_xoah_row_count=sum(result.current_xoah_row_count for result in suite_results),
        canonical_row_count=sum(result.canonical_row_count for result in suite_results),
        suite_results=suite_results,
    )


def _run_suite_pipeline(
    config: TrackingConfig,
    suite: SuiteConfig,
    *,
    source: XOAHSource,
    nightly_extractor: NightlyExtractor,
    use_legacy_dashboard_layout: bool,
) -> SuitePipelineResult:
    parsed_workbook = parse_workbook(config.workbook_path, sheet_name=suite.workbook_sheet)
    # Workbook daily columns are not treated as measured history. The workbook is
    # the baseline source for target/VAI 6.1/model metadata; XOAH is the time-series source.
    workbook_rows: list[HistoryRow] = []
    prior_xoah_rows = refresh_xoah_history_rows(
        parsed_workbook,
        _read_prior_xoah_rows_for_suite(config, suite),
    )
    cached_suite_run_names = {
        row.suite_run_name for row in prior_xoah_rows if row.suite_run_name is not None
    }
    current_xoah_rows = nightly_records_to_history_rows(
        parsed_workbook,
        nightly_extractor(
            parsed_workbook,
            source,
            suite_name=suite.name,
            cached_suite_run_names=cached_suite_run_names,
        ),
    )
    canonical_rows = merge_history_rows(workbook_rows, [*prior_xoah_rows, *current_xoah_rows])

    suite.history_csv_path.parent.mkdir(parents=True, exist_ok=True)
    write_history_csv(suite.history_csv_path, canonical_rows)
    display_rows = _display_rows(canonical_rows, parsed_workbook)
    if use_legacy_dashboard_layout:
        snapshot_paths = write_dashboard_snapshots(display_rows, suite.dashboard_output_dir)
        latest_dashboard_path = suite.dashboard_output_dir / "latest.html"
    else:
        snapshot_paths = write_flat_dashboard_snapshots(
            display_rows,
            suite.dashboard_output_dir,
            suite_name=suite.name,
        )
        latest_dashboard_path = suite.dashboard_output_dir / f"{suite.name}_latest.html"

    return SuitePipelineResult(
        suite_name=suite.name,
        history_csv_path=suite.history_csv_path,
        dashboard_output_dir=suite.dashboard_output_dir,
        latest_dashboard_path=latest_dashboard_path,
        snapshot_paths=snapshot_paths,
        workbook_seeded_row_count=0,
        prior_xoah_row_count=len(prior_xoah_rows),
        current_xoah_row_count=len(current_xoah_rows),
        canonical_row_count=len(canonical_rows),
    )


def _uses_legacy_single_suite_layout(config: TrackingConfig, suite: SuiteConfig) -> bool:
    return (
        len(config.suites) == 1
        and suite.history_csv_path == config.history_csv_path
        and suite.dashboard_output_dir == config.dashboard_output_dir
        and suite.workbook_sheet is None
    )


def _read_prior_xoah_rows_for_suite(config: TrackingConfig, suite: SuiteConfig) -> list[HistoryRow]:
    rows = _read_prior_xoah_rows(suite.history_csv_path, suite_name=suite.name)
    if rows or suite.history_csv_path == config.history_csv_path:
        return rows
    # First multi-suite run: migrate the legacy P0 cache into its suite-specific CSV.
    return _read_prior_xoah_rows(config.history_csv_path, suite_name=suite.name)


def _read_prior_xoah_rows(path: Path, *, suite_name: str | None = None) -> list[HistoryRow]:
    if not path.is_file():
        return []
    rows = [row for row in read_history_csv(path) if row.source_kind == "xoah"]
    if suite_name is None:
        return rows
    return [row for row in rows if row.suite_name in (None, suite_name)]


def _remove_existing_path(path: Path) -> None:
    if path.exists() or path.is_symlink():
        path.unlink()


def _display_rows(rows: Sequence[HistoryRow], parsed_workbook: ParsedWorkbook) -> list[HistoryRow]:
    display_model_names = {model.model_name for model in parsed_workbook.models}
    display_rows = [row for row in rows if row.model_name in display_model_names]
    if not rows:
        return display_rows

    latest_date = max(row.date for row in rows)
    present_model_names = {row.model_name for row in display_rows}
    for model in parsed_workbook.models:
        if model.model_name in present_model_names:
            continue
        display_rows.append(
            HistoryRow(
                date=latest_date,
                model_name=model.model_name,
                section=model.section,
                focus=model.focus,
                customer=model.customer,
                gops=model.gops,
                stamp_tp=model.stamp_tp,
                batch_dp=model.batch_dp,
                target_latency_ms=model.vai_6_2_goal,
                npu_latency_ms=model.npu,
                vai61_latency_ms=model.npu_6_1,
                vart_latency_ms=None,
                aie_latency_ms=None,
                perftest_latency_ms=None,
                source_kind="workbook",
                suite_run_name=None,
                suite_name=None,
                user=None,
                rel_branch=None,
                super_suite=None,
                test_name=None,
                error="No cached XOAH data for this model",
            )
        )
    return display_rows
