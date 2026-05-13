from __future__ import annotations

import argparse
from datetime import date
import sys
from pathlib import Path
from typing import Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from perf_tracker.config import load_tracking_config
from perf_tracker.dashboard import write_flat_dashboard_snapshots
from perf_tracker.history import HistoryRow, read_history_csv
from perf_tracker.pipeline import run_pipeline
from perf_tracker.workbook import ParsedWorkbook, parse_workbook

DEFAULT_CONFIG_PATH = REPO_ROOT / "config" / "tracking_config.json"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Regenerate perf history and dashboard snapshots.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Modes:
  (default)            Full pipeline: workbook + XOAH fetch + dashboard.
  --from-workbook PATH Load workbook; use cached history CSV; skip XOAH.
  --from-csv PATH      Regenerate dashboard directly from a history CSV file.
  --no-xoah            Use config workbook path; skip XOAH (for VDIs without YODATools).
""",
    )
    parser.add_argument(
        "config_path",
        nargs="?",
        default=str(DEFAULT_CONFIG_PATH),
        help="Path to the tracking JSON config (default: config/tracking_config.json).",
    )
    parser.add_argument(
        "--from-workbook",
        metavar="XLSX",
        help="Override workbook path and regenerate dashboards using cached history CSV "
             "(no XOAH fetch).",
    )
    parser.add_argument(
        "--from-csv",
        metavar="CSV",
        help="Regenerate dashboard directly from a history CSV file, "
             "bypassing workbook and XOAH entirely.",
    )
    parser.add_argument(
        "--suite",
        metavar="NAME",
        help="Suite name used with --from-csv (defaults to first suite in config).",
    )
    parser.add_argument(
        "--output-dir",
        metavar="DIR",
        help="Override dashboard output directory (used with --from-csv or --from-workbook).",
    )
    parser.add_argument(
        "--no-xoah",
        action="store_true",
        help="Skip XOAH fetch; use workbook path from config and cached history CSV. "
             "Use this on machines where YODATools is not installed.",
    )
    return parser


def _no_xoah_extractor(
    parsed_workbook: ParsedWorkbook,
    source: object,
    *,
    suite_name: str,
    cached_suite_run_names: set[str],
) -> Sequence[object]:
    return []


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    config = load_tracking_config(args.config_path)

    if args.from_csv:
        return _run_from_csv(args, config)

    if args.from_workbook:
        return _run_from_workbook(args, config)

    if args.no_xoah:
        print("--no-xoah: skipping XOAH fetch, using cached history CSV.")
        result = run_pipeline(config, nightly_extractor=_no_xoah_extractor)
        _print_pipeline_result(result)
        return 0

    # Default: full pipeline with XOAH
    result = run_pipeline(config)
    _print_pipeline_result(result)
    return 0


def _run_from_csv(args: argparse.Namespace, config: object) -> int:
    csv_path = Path(args.from_csv)
    if not csv_path.exists():
        print(f"ERROR: CSV file not found: {csv_path}", file=sys.stderr)
        return 1

    print(f"Loading history from CSV: {csv_path}")
    rows = read_history_csv(csv_path)
    print(f"Loaded {len(rows)} rows.")

    suite_name = args.suite or getattr(config, "suites", [None])[0]
    if hasattr(suite_name, "name"):
        suite_name = suite_name.name
    suite_name = suite_name or "dashboard"

    output_dir = Path(args.output_dir) if args.output_dir else _first_suite_output_dir(config)
    print(f"Writing dashboard to: {output_dir}")
    snapshot_paths = write_flat_dashboard_snapshots(rows, output_dir, suite_name=suite_name)
    print(f"Snapshots written: {len(snapshot_paths)}")
    if snapshot_paths:
        print(f"Latest: {output_dir}/{suite_name}_latest.html")
    return 0


def _run_from_workbook(args: argparse.Namespace, config: object) -> int:
    from perf_tracker.pipeline import _run_suite_pipeline  # type: ignore[attr-defined]

    wb_path = Path(args.from_workbook)
    if not wb_path.exists():
        print(f"ERROR: Workbook not found: {wb_path}", file=sys.stderr)
        return 1

    print(f"Loading workbook: {wb_path}")
    # Patch workbook_path in config
    import dataclasses
    patched = dataclasses.replace(config, workbook_path=wb_path)

    result = run_pipeline(patched, nightly_extractor=_no_xoah_extractor)
    _print_pipeline_result(result)
    return 0


def _first_suite_output_dir(config: object) -> Path:
    suites = getattr(config, "suites", ())
    if suites:
        return suites[0].dashboard_output_dir
    return getattr(config, "dashboard_output_dir", Path("."))


def _print_pipeline_result(result: object) -> None:
    print(f"History CSV:       {getattr(result, 'history_csv_path', 'N/A')}")
    print(f"Dashboard output:  {getattr(result, 'dashboard_output_dir', 'N/A')}")
    print(f"Latest dashboard:  {getattr(result, 'latest_dashboard_path', 'N/A')}")
    print(f"Snapshots written: {len(getattr(result, 'snapshot_paths', []))}")
    print(f"Workbook rows:     {getattr(result, 'workbook_seeded_row_count', 0)}")
    print(f"Prior XOAH rows:   {getattr(result, 'prior_xoah_row_count', 0)}")
    print(f"New XOAH rows:     {getattr(result, 'current_xoah_row_count', 0)}")
    print(f"Canonical rows:    {getattr(result, 'canonical_row_count', 0)}")
    for suite in getattr(result, "suite_results", []):
        print(f"  Suite: {suite.suite_name}")
        print(f"    Latest: {suite.latest_dashboard_path}")
        print(f"    Snapshots: {len(suite.snapshot_paths)}")
        print(f"    XOAH rows (new): {suite.current_xoah_row_count}")


if __name__ == "__main__":
    raise SystemExit(main())
