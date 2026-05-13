from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
import importlib
from pathlib import Path
import re
from typing import Any, Protocol, TypeAlias, cast
from urllib.parse import parse_qs, urlparse

from perf_tracker.workbook import ParsedWorkbook, normalize_test_name

TARGET_SUITE = "VE2_QOR_P0_HW"
# Mirror the proven old script metric shape so XOAH rows include
# suite provenance plus the fields needed to resolve board logs.
DEFAULT_USER_METRICS = (
    "SUITE_RUN_NAME",
    "SUITE_NAME",
    "TEST_WORK_DIR",
    "TEST_CASE_NAME",
    "TEST_NAME",
    "TASK_STATUS",
    "JOB_OUTPUT_FILE",
    "TASK_UNIQUE_ERROR",
    "TASK_FIRST_ERROR_STRING",
    "TEST_PATH",
)
VART_LATENCY_RE = re.compile(
    r"INFO:\s*Average Inference latency\s*:\s*(\d+\.?\d*)\s*ms/batch"
)
ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*m")

XOAHRow: TypeAlias = Mapping[str, Any]


class XOAHClient(Protocol):
    def query_test_rows(self, query: str) -> Sequence[XOAHRow]: ...


LogReader: TypeAlias = Callable[[XOAHClient, XOAHRow], str | None]


@dataclass(frozen=True)
class XOAHSource:
    super_suite: str
    user: str
    rel_branch: str

    @classmethod
    def from_summary_url(cls, summary_url: str) -> XOAHSource:
        params = parse_qs(urlparse(summary_url).query)
        return cls(
            super_suite=_required_query_param(params, "superSuiteName"),
            user=_required_query_param(params, "user"),
            rel_branch=_required_query_param(params, "relBranch"),
        )

    def build_suite_query(self, suite_name: str) -> str:
        return (
            f"USER:({self.user}) AND REL_BRANCH:({self.rel_branch}) AND "
            f"SUPER_SUITE_NAME:({self.super_suite}) AND SUITE_NAME:({suite_name})"
        )

    def build_suite_run_query(self, suite_name: str, suite_run_name: str) -> str:
        return (
            f"{self.build_suite_query(suite_name)} AND "
            f"SUITE_RUN_NAME:({suite_run_name})"
        )


@dataclass(frozen=True)
class NightlyRecord:
    model_name: str
    test_name: str
    suite_name: str
    suite_run_name: str
    user: str
    rel_branch: str
    super_suite: str
    vart_latency_ms: float | None
    error: str | None = None


@dataclass(frozen=True)
class YODAToolsClient:
    delegate: Any
    user_metrics: tuple[str, ...] = DEFAULT_USER_METRICS

    def query_test_rows(self, query: str) -> Sequence[XOAHRow]:
        return list(
            cast(
                Sequence[XOAHRow],
                self.delegate.getTestAndTaskData(query, list(self.user_metrics)),
            )
        )


def select_latest_suite_run_name(rows: Sequence[XOAHRow]) -> str:
    suite_run_names = [
        suite_run_name
        for row in rows
        if (suite_run_name := _coerce_string(row.get("SUITE_RUN_NAME"))) is not None
    ]
    if not suite_run_names:
        raise ValueError("Could not determine SUITE_RUN_NAME from XOAH rows.")
    return max(suite_run_names)


def list_suite_run_names(rows: Sequence[XOAHRow]) -> list[str]:
    return sorted(
        {
            suite_run_name
            for row in rows
            if (suite_run_name := _coerce_string(row.get("SUITE_RUN_NAME"))) is not None
        }
    )


def extract_vart_latency_ms(board_log: str | None) -> float | None:
    if board_log is None:
        return None
    match = VART_LATENCY_RE.search(board_log)
    if match is None:
        return None
    return float(match.group(1))


def extract_nightly_records(
    parsed_workbook: ParsedWorkbook,
    source: XOAHSource,
    *,
    client: XOAHClient | None = None,
    suite_name: str = TARGET_SUITE,
    log_reader: LogReader | None = None,
) -> list[NightlyRecord]:
    active_client = client or create_yodatools_client()
    active_log_reader = log_reader or read_board_log
    suite_query = source.build_suite_query(suite_name)
    latest_suite_run = select_latest_suite_run_name(active_client.query_test_rows(suite_query))
    suite_run_query = source.build_suite_run_query(suite_name, latest_suite_run)
    test_rows = active_client.query_test_rows(suite_run_query)

    return _extract_nightly_records_from_rows(
        parsed_workbook,
        source,
        suite_name=suite_name,
        suite_run_name=latest_suite_run,
        test_rows=test_rows,
        client=active_client,
        log_reader=active_log_reader,
    )


def _extract_nightly_records_from_rows(
    parsed_workbook: ParsedWorkbook,
    source: XOAHSource,
    *,
    suite_name: str,
    suite_run_name: str,
    test_rows: Sequence[XOAHRow],
    client: XOAHClient,
    log_reader: LogReader,
) -> list[NightlyRecord]:
    exact_test_name_to_model = {
        test_name: model_name for model_name, test_name in parsed_workbook.model_to_test_name.items()
    }

    records: list[NightlyRecord] = []
    for row in test_rows:
        if not _has_result_artifact(row):
            continue

        test_name = _coerce_string(row.get("TEST_NAME"))
        if test_name is None:
            continue

        model_name = exact_test_name_to_model.get(test_name)
        if model_name is None:
            normalized_test_name = normalize_test_name(test_name)
            if normalized_test_name is None:
                continue
            model_name = normalized_test_name

        error = _row_error(row)
        board_log = log_reader(client, row)
        vart_latency_ms = extract_vart_latency_ms(board_log)
        if error is None and vart_latency_ms is None:
            error = "VART latency not found in board log"

        records.append(
            NightlyRecord(
                model_name=model_name,
                test_name=test_name,
                suite_name=suite_name,
                suite_run_name=suite_run_name,
                user=source.user,
                rel_branch=source.rel_branch,
                super_suite=source.super_suite,
                vart_latency_ms=vart_latency_ms,
                error=error,
            )
        )

    return records


def extract_available_nightly_records(
    parsed_workbook: ParsedWorkbook,
    source: XOAHSource,
    *,
    client: XOAHClient | None = None,
    suite_name: str = TARGET_SUITE,
    cached_suite_run_names: set[str] | None = None,
    log_reader: LogReader | None = None,
) -> list[NightlyRecord]:
    active_client = client or create_yodatools_client()
    cached = cached_suite_run_names or set()
    suite_query = source.build_suite_query(suite_name)
    suite_run_names = [
        suite_run_name
        for suite_run_name in list_suite_run_names(active_client.query_test_rows(suite_query))
        if suite_run_name not in cached
    ]

    records: list[NightlyRecord] = []
    for suite_run_name in suite_run_names:
        suite_run_query = source.build_suite_run_query(suite_name, suite_run_name)
        records.extend(
            _extract_nightly_records_from_rows(
                parsed_workbook,
                source,
                suite_name=suite_name,
                suite_run_name=suite_run_name,
                test_rows=active_client.query_test_rows(suite_run_query),
                client=active_client,
                log_reader=log_reader or read_board_log,
            )
        )
    return records


def create_yodatools_client(
    user_metrics: Sequence[str] = DEFAULT_USER_METRICS,
) -> XOAHClient:
    module = importlib.import_module("YODATools.YODATools")
    yodatools_class = getattr(module, "YODATools", None)
    if not callable(yodatools_class):
        raise RuntimeError("YODATools.YODATools.YODATools is not available.")
    return YODAToolsClient(delegate=yodatools_class(), user_metrics=tuple(user_metrics))


def read_board_log(client: XOAHClient, row: XOAHRow) -> str | None:
    for key in ("BOARD_LOG", "board_log", "BOARD_LOG_TEXT", "board_log_text"):
        board_log = _coerce_string(row.get(key))
        if board_log is not None:
            return board_log

    job_output_file = _nested_board_job_output_file(row)
    if job_output_file is not None:
        return _read_text_file(job_output_file, work_dir=_coerce_string(row.get("TEST_WORK_DIR")))

    top_level_job_output_file = _top_level_job_output_file(row)
    if top_level_job_output_file is not None:
        return _read_text_file(
            top_level_job_output_file,
            work_dir=_coerce_string(row.get("TEST_WORK_DIR")),
        )

    return None


def _required_query_param(params: Mapping[str, list[str]], key: str) -> str:
    values = params.get(key)
    if not values or not values[0].strip():
        raise ValueError(f"XOAH summary URL is missing required query parameter: {key}")
    return values[0].strip()


def _coerce_string(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    if not normalized:
        return None
    return normalized


def _row_error(row: XOAHRow) -> str | None:
    for task_row in _task_error_candidates(row):
        task_status = _coerce_string(task_row.get("TASK_STATUS"))
        if task_status is not None and task_status.upper() != "PASS":
            detail = _clean_error_text(
                _coerce_string(task_row.get("TASK_FIRST_ERROR_STRING"))
                or _coerce_string(task_row.get("TASK_UNIQUE_ERROR"))
            )
            task_name = _coerce_string(task_row.get("TASK_NAME"))
            status_prefix = f"{task_name} {task_status}" if task_name else task_status
            return _clean_error_text(f"{status_prefix}: {detail}" if detail else status_prefix)
    return None


def _task_error_candidates(row: XOAHRow) -> list[XOAHRow]:
    candidates: list[XOAHRow] = []
    for key in ("board", "vaiml", "summary"):
        nested = row.get(key)
        if isinstance(nested, Mapping):
            candidates.append(nested)
    candidates.append(row)
    return candidates


def _clean_error_text(value: str | None) -> str | None:
    if value is None:
        return None
    return ANSI_ESCAPE_RE.sub("", value)


def _has_result_artifact(row: XOAHRow) -> bool:
    saw_artifact_reference = False
    work_dir = _coerce_string(row.get("TEST_WORK_DIR"))
    if work_dir is not None:
        saw_artifact_reference = True
        if Path(work_dir).exists():
            return True
    for task_row in _task_error_candidates(row):
        job_output_file = _coerce_string(task_row.get("JOB_OUTPUT_FILE"))
        if job_output_file is not None:
            saw_artifact_reference = True
            if Path(job_output_file).exists():
                return True
    return not saw_artifact_reference


def _nested_board_job_output_file(row: XOAHRow) -> str | None:
    board = row.get("board")
    if not isinstance(board, Mapping):
        return None
    return _coerce_string(board.get("JOB_OUTPUT_FILE"))


def _top_level_job_output_file(row: XOAHRow) -> str | None:
    if _nested_board_job_output_file(row) is not None:
        return None
    return _coerce_string(row.get("JOB_OUTPUT_FILE"))


def _read_text_file(path_value: str, *, work_dir: str | None) -> str | None:
    path = Path(path_value)
    if not path.is_absolute():
        if work_dir is None:
            return None
        path = Path(work_dir) / path

    try:
        if not path.is_file():
            return None
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
