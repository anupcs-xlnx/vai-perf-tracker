from __future__ import annotations

import importlib
import sys
from pathlib import Path
import types
from typing import Any

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

EXPECTED_DEFAULT_USER_METRICS = [
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
]


def _load_module(module_name: str):
    try:
        return importlib.import_module(module_name)
    except ModuleNotFoundError as exc:
        pytest.fail(f"Expected {module_name} to exist, but import failed: {exc}")


def _load_xoah_module():
    return _load_module("perf_tracker.xoah")


def _build_parsed_workbook():
    workbook_module = _load_module("perf_tracker.workbook")
    return workbook_module.ParsedWorkbook(
        models=[],
        measurements=[],
        model_to_test_name={
            "asura_int8_subaru_2x8_t2d1": "asura_int8_subaru_2x8_t2d1-hw-vek385_vaiml",
            "phoenix_int8_city": "phoenix_int8_city-hw-vek385_vaiml",
        },
    )


class FakeXOAHClient:
    def __init__(self, responses: dict[str, list[dict[str, Any]]]) -> None:
        self._responses = responses
        self.queries: list[str] = []

    def query_test_rows(self, query: str) -> list[dict[str, Any]]:
        self.queries.append(query)
        return list(self._responses[query])


class FakeYODAToolsDelegate:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows
        self.calls: list[tuple[str, list[str]]] = []

    def getTestAndTaskData(self, query: str, user_metrics: list[str]) -> list[dict[str, Any]]:
        self.calls.append((query, list(user_metrics)))
        return list(self.rows)


class QueryAwareYODAToolsDelegate:
    def __init__(self, responses: dict[str, list[dict[str, Any]]]) -> None:
        self._responses = responses
        self.calls: list[tuple[str, list[str]]] = []

    def getTestAndTaskData(self, query: str, user_metrics: list[str]) -> list[dict[str, Any]]:
        self.calls.append((query, list(user_metrics)))
        return list(self._responses[query])


def test_xoah_source_parses_summary_url_and_builds_queries() -> None:
    xoah = _load_xoah_module()

    source = xoah.XOAHSource.from_summary_url(
        "https://xoah.example/query?"
        "superSuiteName=VAI_6_2_GEN2_REGRESSION&"
        "user=perf-bot&"
        "relBranch=release%2Fvai_6.2"
    )

    assert source.super_suite == "VAI_6_2_GEN2_REGRESSION"
    assert source.user == "perf-bot"
    assert source.rel_branch == "release/vai_6.2"
    assert source.build_suite_query(xoah.TARGET_SUITE) == (
        "USER:(perf-bot) AND REL_BRANCH:(release/vai_6.2) AND "
        "SUPER_SUITE_NAME:(VAI_6_2_GEN2_REGRESSION) AND SUITE_NAME:(VE2_QOR_P0_HW)"
    )
    assert source.build_suite_run_query(
        xoah.TARGET_SUITE,
        "20260507_004500_VE2_QOR_P0_HW",
    ) == (
        "USER:(perf-bot) AND REL_BRANCH:(release/vai_6.2) AND "
        "SUPER_SUITE_NAME:(VAI_6_2_GEN2_REGRESSION) AND SUITE_NAME:(VE2_QOR_P0_HW) AND "
        "SUITE_RUN_NAME:(20260507_004500_VE2_QOR_P0_HW)"
    )


def test_select_latest_suite_run_name_uses_sortable_run_strings() -> None:
    xoah = _load_xoah_module()

    latest = xoah.select_latest_suite_run_name(
        [
            {"SUITE_RUN_NAME": "20260505_235959_VE2_QOR_P0_HW"},
            {"SUITE_RUN_NAME": "20260507_000001_VE2_QOR_P0_HW"},
            {"SUITE_RUN_NAME": "20260506_120000_VE2_QOR_P0_HW"},
            {"OTHER_FIELD": "ignored"},
        ]
    )

    assert latest == "20260507_000001_VE2_QOR_P0_HW"


def test_extract_available_nightly_records_backfills_uncached_suite_runs() -> None:
    xoah = _load_xoah_module()
    parsed_workbook = _build_parsed_workbook()
    source = xoah.XOAHSource(
        super_suite="VAI_6_2_GEN2_REGRESSION",
        user="perf-bot",
        rel_branch="release/vai_6.2",
    )
    cached_suite_run = "20260506_004500_VE2_QOR_P0_HW"
    first_new_suite_run = "20260505_004500_VE2_QOR_P0_HW"
    second_new_suite_run = "20260507_004500_VE2_QOR_P0_HW"
    list_query = source.build_suite_query(xoah.TARGET_SUITE)
    first_run_query = source.build_suite_run_query(xoah.TARGET_SUITE, first_new_suite_run)
    second_run_query = source.build_suite_run_query(xoah.TARGET_SUITE, second_new_suite_run)
    client = FakeXOAHClient(
        {
            list_query: [
                {"SUITE_RUN_NAME": second_new_suite_run},
                {"SUITE_RUN_NAME": cached_suite_run},
                {"SUITE_RUN_NAME": first_new_suite_run},
                {"SUITE_RUN_NAME": first_new_suite_run},
            ],
            first_run_query: [
                {
                    "TEST_NAME": "asura_int8_subaru_2x8_t2d1-hw-vek385_vaiml",
                    "SUITE_RUN_NAME": first_new_suite_run,
                }
            ],
            second_run_query: [
                {
                    "TEST_NAME": "asura_int8_subaru_2x8_t2d1-hw-vek385_vaiml",
                    "SUITE_RUN_NAME": second_new_suite_run,
                }
            ],
        }
    )
    board_logs = {
        first_new_suite_run: "INFO: Average Inference latency : 12 ms/batch",
        second_new_suite_run: "INFO: Average Inference latency : 10 ms/batch",
    }

    records = xoah.extract_available_nightly_records(
        parsed_workbook,
        source,
        client=client,
        cached_suite_run_names={cached_suite_run},
        log_reader=lambda _client, row: board_logs[row["SUITE_RUN_NAME"]],
    )

    assert client.queries == [list_query, first_run_query, second_run_query]
    assert [(record.suite_run_name, record.vart_latency_ms) for record in records] == [
        (first_new_suite_run, 12.0),
        (second_new_suite_run, 10.0),
    ]


def test_extract_available_nightly_records_skips_rows_with_deleted_result_artifacts(
    tmp_path: Path,
) -> None:
    xoah = _load_xoah_module()
    parsed_workbook = _build_parsed_workbook()
    source = xoah.XOAHSource(
        super_suite="VAI_6_2_GEN2_REGRESSION",
        user="perf-bot",
        rel_branch="release/vai_6.2",
    )
    suite_run_name = "20260507_004500_VE2_QOR_P0_HW"
    list_query = source.build_suite_query(xoah.TARGET_SUITE)
    run_query = source.build_suite_run_query(xoah.TARGET_SUITE, suite_run_name)
    existing_work_dir = tmp_path / "existing-work-dir"
    existing_work_dir.mkdir()
    client = FakeXOAHClient(
        {
            list_query: [{"SUITE_RUN_NAME": suite_run_name}],
            run_query: [
                {
                    "TEST_NAME": "asura_int8_subaru_2x8_t2d1-hw-vek385_vaiml",
                    "SUITE_RUN_NAME": suite_run_name,
                    "TEST_WORK_DIR": str(tmp_path / "deleted-work-dir"),
                },
                {
                    "TEST_NAME": "phoenix_int8_city-hw-vek385_vaiml",
                    "SUITE_RUN_NAME": suite_run_name,
                    "TEST_WORK_DIR": str(existing_work_dir),
                },
            ],
        }
    )

    records = xoah.extract_available_nightly_records(
        parsed_workbook,
        source,
        client=client,
        cached_suite_run_names=set(),
        log_reader=lambda _client, row: (
            "INFO: Average Inference latency : 1 ms/batch"
            if row["TEST_NAME"].startswith("asura")
            else "INFO: Average Inference latency : 2 ms/batch"
        ),
    )

    assert [(record.model_name, record.vart_latency_ms) for record in records] == [
        ("phoenix_int8_city", 2.0)
    ]


def test_extract_nightly_records_joins_models_and_parses_vart_latency() -> None:
    xoah = _load_xoah_module()
    parsed_workbook = _build_parsed_workbook()
    source = xoah.XOAHSource(
        super_suite="VAI_6_2_GEN2_REGRESSION",
        user="perf-bot",
        rel_branch="release/vai_6.2",
    )
    latest_suite_run = "20260507_004500_VE2_QOR_P0_HW"
    list_query = source.build_suite_query(xoah.TARGET_SUITE)
    run_query = source.build_suite_run_query(xoah.TARGET_SUITE, latest_suite_run)
    client = FakeXOAHClient(
        {
            list_query: [
                {"SUITE_RUN_NAME": "20260505_235959_VE2_QOR_P0_HW"},
                {"SUITE_RUN_NAME": latest_suite_run},
                {"SUITE_RUN_NAME": "20260506_120000_VE2_QOR_P0_HW"},
            ],
            run_query: [
                {
                    "TEST_NAME": "asura_int8_subaru_2x8_t2d1-hw-vek385_vaiml",
                    "SUITE_RUN_NAME": latest_suite_run,
                },
                {
                    "TEST_NAME": "phoenix_int8_city-hw-vek385_vaiml",
                    "SUITE_RUN_NAME": latest_suite_run,
                },
                {
                    "TEST_NAME": "unmapped_test-hw-vek385_vaiml",
                    "SUITE_RUN_NAME": latest_suite_run,
                },
            ],
        }
    )

    board_logs = {
        "asura_int8_subaru_2x8_t2d1-hw-vek385_vaiml": (
            "hello\nINFO: Average Inference latency : 10.5 ms/batch\nbye"
        ),
        "phoenix_int8_city-hw-vek385_vaiml": (
            "INFO: Average Inference latency : 2 ms/batch"
        ),
        "unmapped_test-hw-vek385_vaiml": (
            "INFO: Average Inference latency : 7 ms/batch"
        ),
    }

    records = xoah.extract_nightly_records(
        parsed_workbook,
        source,
        client=client,
        log_reader=lambda _client, row: board_logs.get(row["TEST_NAME"]),
    )

    assert client.queries == [list_query, run_query]
    assert {record.model_name for record in records} == {
        "asura_int8_subaru_2x8_t2d1",
        "phoenix_int8_city",
        "unmapped_test",
    }

    by_model = {record.model_name: record for record in records}
    assert by_model["asura_int8_subaru_2x8_t2d1"].test_name == (
        "asura_int8_subaru_2x8_t2d1-hw-vek385_vaiml"
    )
    assert by_model["asura_int8_subaru_2x8_t2d1"].vart_latency_ms == pytest.approx(10.5)
    assert by_model["phoenix_int8_city"].vart_latency_ms == pytest.approx(2.0)
    assert by_model["unmapped_test"].test_name == "unmapped_test-hw-vek385_vaiml"
    assert by_model["unmapped_test"].vart_latency_ms == pytest.approx(7.0)

    for record in records:
        assert record.suite_name == xoah.TARGET_SUITE
        assert record.suite_run_name == latest_suite_run
        assert record.user == "perf-bot"
        assert record.rel_branch == "release/vai_6.2"
        assert record.super_suite == "VAI_6_2_GEN2_REGRESSION"


def test_extract_nightly_records_populates_errors_for_missing_or_malformed_board_logs() -> None:
    xoah = _load_xoah_module()
    parsed_workbook = _build_parsed_workbook()
    source = xoah.XOAHSource(
        super_suite="VAI_6_2_GEN2_REGRESSION",
        user="perf-bot",
        rel_branch="release/vai_6.2",
    )
    latest_suite_run = "20260507_004500_VE2_QOR_P0_HW"
    list_query = source.build_suite_query(xoah.TARGET_SUITE)
    run_query = source.build_suite_run_query(xoah.TARGET_SUITE, latest_suite_run)
    client = FakeXOAHClient(
        {
            list_query: [{"SUITE_RUN_NAME": latest_suite_run}],
            run_query: [
                {
                    "TEST_NAME": "asura_int8_subaru_2x8_t2d1-hw-vek385_vaiml",
                    "SUITE_RUN_NAME": latest_suite_run,
                },
                {
                    "TEST_NAME": "phoenix_int8_city-hw-vek385_vaiml",
                    "SUITE_RUN_NAME": latest_suite_run,
                },
            ],
        }
    )

    board_logs = {
        "asura_int8_subaru_2x8_t2d1-hw-vek385_vaiml": None,
        "phoenix_int8_city-hw-vek385_vaiml": "latency not present here",
    }

    records = xoah.extract_nightly_records(
        parsed_workbook,
        source,
        client=client,
        log_reader=lambda _client, row: board_logs[row["TEST_NAME"]],
    )

    assert {record.model_name: record.error for record in records} == {
        "asura_int8_subaru_2x8_t2d1": "VART latency not found in board log",
        "phoenix_int8_city": "VART latency not found in board log",
    }
    assert all(record.vart_latency_ms is None for record in records)


def test_extract_nightly_records_keeps_vart_latency_when_summary_fails_after_board_pass() -> None:
    xoah = _load_xoah_module()
    parsed_workbook = _build_parsed_workbook()
    source = xoah.XOAHSource(
        super_suite="VAI_6_2_GEN2_REGRESSION",
        user="perf-bot",
        rel_branch="release/vai_6.2",
    )
    latest_suite_run = "20260507_004500_VE2_QOR_P0_HW"
    list_query = source.build_suite_query(xoah.TARGET_SUITE)
    run_query = source.build_suite_run_query(xoah.TARGET_SUITE, latest_suite_run)
    client = FakeXOAHClient(
        {
            list_query: [{"SUITE_RUN_NAME": latest_suite_run}],
            run_query: [
                {
                    "TEST_NAME": "asura_int8_subaru_2x8_t2d1-hw-vek385_vaiml",
                    "SUITE_RUN_NAME": latest_suite_run,
                    "TASK_STATUS": "PASS",
                },
                {
                    "TEST_NAME": "phoenix_int8_city-hw-vek385_vaiml",
                    "SUITE_RUN_NAME": latest_suite_run,
                    "board": {
                        "TASK_NAME": "board",
                        "TASK_STATUS": "PASS",
                    },
                    "summary": {
                        "TASK_NAME": "summary",
                        "TASK_STATUS": "FAIL",
                        "TASK_FIRST_ERROR_STRING": "OFM Mismatch",
                    },
                },
            ],
        }
    )

    board_logs = {
        "asura_int8_subaru_2x8_t2d1-hw-vek385_vaiml": (
            "INFO: Average Inference latency : 10.5 ms/batch"
        ),
        "phoenix_int8_city-hw-vek385_vaiml": (
            "INFO: Average Inference latency : 2 ms/batch"
        ),
    }

    records = xoah.extract_nightly_records(
        parsed_workbook,
        source,
        client=client,
        log_reader=lambda _client, row: board_logs[row["TEST_NAME"]],
    )

    by_model = {record.model_name: record for record in records}
    assert by_model["asura_int8_subaru_2x8_t2d1"].vart_latency_ms == pytest.approx(10.5)
    assert by_model["asura_int8_subaru_2x8_t2d1"].error is None
    assert by_model["phoenix_int8_city"].vart_latency_ms == pytest.approx(2.0)
    assert by_model["phoenix_int8_city"].error == "summary FAIL: OFM Mismatch"


def test_extract_nightly_records_populates_error_for_failed_board_without_latency() -> None:
    xoah = _load_xoah_module()
    parsed_workbook = _build_parsed_workbook()
    source = xoah.XOAHSource(
        super_suite="VAI_6_2_GEN2_REGRESSION",
        user="perf-bot",
        rel_branch="release/vai_6.2",
    )
    latest_suite_run = "20260507_004500_VE2_QOR_P0_HW"
    list_query = source.build_suite_query(xoah.TARGET_SUITE)
    run_query = source.build_suite_run_query(xoah.TARGET_SUITE, latest_suite_run)
    client = FakeXOAHClient(
        {
            list_query: [{"SUITE_RUN_NAME": latest_suite_run}],
            run_query: [
                {
                    "TEST_NAME": "phoenix_int8_city-hw-vek385_vaiml",
                    "SUITE_RUN_NAME": latest_suite_run,
                    "board": {
                        "TASK_NAME": "board",
                        "TASK_STATUS": "FAIL",
                        "TASK_FIRST_ERROR_STRING": "\x1b[91mboard crashed\x1b[0m",
                    },
                },
            ],
        }
    )

    records = xoah.extract_nightly_records(
        parsed_workbook,
        source,
        client=client,
        log_reader=lambda _client, _row: "latency not present here",
    )

    assert len(records) == 1
    assert records[0].vart_latency_ms is None
    assert records[0].error == "board FAIL: board crashed"


def test_extract_nightly_records_uses_default_client_and_board_log_reader(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    xoah = _load_xoah_module()
    parsed_workbook = _build_parsed_workbook()
    source = xoah.XOAHSource(
        super_suite="VAI_6_2_GEN2_REGRESSION",
        user="perf-bot",
        rel_branch="release/vai_6.2",
    )
    latest_suite_run = "20260507_004500_VE2_QOR_P0_HW"
    list_query = source.build_suite_query(xoah.TARGET_SUITE)
    run_query = source.build_suite_run_query(xoah.TARGET_SUITE, latest_suite_run)
    board_log_path = tmp_path / "logs" / "job_output.log"
    board_log_path.parent.mkdir()
    board_log_path.write_text(
        "hello\nINFO: Average Inference latency : 6.75 ms/batch\nbye\n",
        encoding="utf-8",
    )
    delegate = QueryAwareYODAToolsDelegate(
        {
            list_query: [{"SUITE_RUN_NAME": latest_suite_run}],
            run_query: [
                {
                    "TEST_NAME": "asura_int8_subaru_2x8_t2d1-hw-vek385_vaiml",
                    "SUITE_RUN_NAME": latest_suite_run,
                    "board": {"JOB_OUTPUT_FILE": str(board_log_path.relative_to(tmp_path))},
                    "TEST_WORK_DIR": str(tmp_path),
                }
            ],
        }
    )

    def fake_import_module(module_name: str):
        assert module_name == "YODATools.YODATools"
        return types.SimpleNamespace(YODATools=lambda: delegate)

    monkeypatch.setattr(xoah.importlib, "import_module", fake_import_module)

    records = xoah.extract_nightly_records(parsed_workbook, source)

    assert len(records) == 1
    assert records[0].model_name == "asura_int8_subaru_2x8_t2d1"
    assert records[0].test_name == "asura_int8_subaru_2x8_t2d1-hw-vek385_vaiml"
    assert records[0].suite_run_name == latest_suite_run
    assert records[0].vart_latency_ms == pytest.approx(6.75)
    assert delegate.calls == [
        (list_query, EXPECTED_DEFAULT_USER_METRICS),
        (run_query, EXPECTED_DEFAULT_USER_METRICS),
    ]


def test_create_yodatools_client_wraps_explicit_real_import(monkeypatch: pytest.MonkeyPatch) -> None:
    xoah = _load_xoah_module()
    delegate = FakeYODAToolsDelegate(rows=[{"TEST_NAME": "demo"}])

    def fake_import_module(module_name: str):
        assert module_name == "YODATools.YODATools"
        return types.SimpleNamespace(YODATools=lambda: delegate)

    monkeypatch.setattr(xoah.importlib, "import_module", fake_import_module)

    client = xoah.create_yodatools_client(user_metrics=["board.JOB_OUTPUT_FILE"])

    assert client.query_test_rows("USER:(perf-bot)") == [{"TEST_NAME": "demo"}]
    assert delegate.calls == [("USER:(perf-bot)", ["board.JOB_OUTPUT_FILE"])]


def test_create_yodatools_client_requests_board_output_file_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    xoah = _load_xoah_module()
    delegate = FakeYODAToolsDelegate(rows=[{"TEST_NAME": "demo"}])

    def fake_import_module(module_name: str):
        assert module_name == "YODATools.YODATools"
        return types.SimpleNamespace(YODATools=lambda: delegate)

    monkeypatch.setattr(xoah.importlib, "import_module", fake_import_module)

    client = xoah.create_yodatools_client()
    client.query_test_rows("USER:(perf-bot)")

    assert delegate.calls == [("USER:(perf-bot)", EXPECTED_DEFAULT_USER_METRICS)]


def test_default_user_metrics_match_proven_old_script_shape() -> None:
    xoah = _load_xoah_module()

    assert list(xoah.DEFAULT_USER_METRICS) == EXPECTED_DEFAULT_USER_METRICS


def test_read_board_log_reads_nested_board_job_output_file(tmp_path: Path) -> None:
    xoah = _load_xoah_module()
    board_log_path = tmp_path / "job_output.log"
    board_log_path.write_text(
        "INFO: Average Inference latency : 7.25 ms/batch\n",
        encoding="utf-8",
    )

    board_log = xoah.read_board_log(
        client=FakeXOAHClient({}),
        row={
            "board": {"JOB_OUTPUT_FILE": str(board_log_path)},
            "TEST_WORK_DIR": str(tmp_path),
        },
    )

    assert board_log == "INFO: Average Inference latency : 7.25 ms/batch\n"


def test_read_board_log_prefers_inline_text_and_returns_none_for_unreadable_file(
    tmp_path: Path,
) -> None:
    xoah = _load_xoah_module()
    missing_path = tmp_path / "missing.log"

    inline_log = xoah.read_board_log(
        client=FakeXOAHClient({}),
        row={
            "BOARD_LOG": "INFO: Average Inference latency : 3 ms/batch",
            "board": {"JOB_OUTPUT_FILE": str(missing_path)},
        },
    )
    unreadable_log = xoah.read_board_log(
        client=FakeXOAHClient({}),
        row={
            "board": {"JOB_OUTPUT_FILE": str(missing_path)},
            "TEST_WORK_DIR": str(tmp_path),
        },
    )

    assert inline_log == "INFO: Average Inference latency : 3 ms/batch"
    assert unreadable_log is None
