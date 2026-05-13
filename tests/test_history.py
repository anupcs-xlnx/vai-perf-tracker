from __future__ import annotations

from datetime import date
import importlib
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


def _load_module(module_name: str):
    try:
        return importlib.import_module(module_name)
    except ModuleNotFoundError as exc:
        pytest.fail(f"Expected {module_name} to exist, but import failed: {exc}")


def _load_history_module():
    return _load_module("perf_tracker.history")


def _load_workbook_module():
    return _load_module("perf_tracker.workbook")


def _load_xoah_module():
    return _load_module("perf_tracker.xoah")


def test_parse_workbook_date_label_uses_explicit_year() -> None:
    history = _load_history_module()

    assert history.parse_workbook_date_label("7th May", year=2026) == date(2026, 5, 7)


def test_parse_workbook_date_label_supports_common_spreadsheet_month_names() -> None:
    history = _load_history_module()

    assert history.parse_workbook_date_label("7th March", year=2026) == date(2026, 3, 7)
    assert history.parse_workbook_date_label("7th Sep", year=2026) == date(2026, 9, 7)
    assert history.parse_workbook_date_label("7th Sept", year=2026) == date(2026, 9, 7)


def test_seed_history_rows_from_workbook_measurements() -> None:
    history = _load_history_module()
    workbook = _load_workbook_module()
    parsed_workbook = workbook.ParsedWorkbook(
        models=[
            workbook.ModelRecord(
                model_name="asura_int8_subaru_2x8_t2d1",
                section="CV",
                focus="Latency",
                gops=123.4,
                customer="Subaru",
                stamp_tp="t2d1",
                batch_dp="2x8",
                vai_6_2_goal=1.7,
                npu=1.5,
                npu_6_1=1.9,
                vart_latency=2.1,
            )
        ],
        measurements=[
            workbook.MeasurementRecord(
                model_name="asura_int8_subaru_2x8_t2d1",
                date_label="7th May",
                aie=1.1,
                vart=1.3,
                perftest=None,
            )
        ],
        model_to_test_name={},
    )

    assert history.seed_workbook_history_rows(parsed_workbook, year=2026) == [
        history.HistoryRow(
            date=date(2026, 5, 7),
            model_name="asura_int8_subaru_2x8_t2d1",
            section="CV",
            focus="Latency",
            customer="Subaru",
            gops=123.4,
            stamp_tp="t2d1",
            batch_dp="2x8",
            target_latency_ms=1.7,
            npu_latency_ms=1.5,
            vai61_latency_ms=1.9,
            vart_latency_ms=1.3,
            aie_latency_ms=1.1,
            perftest_latency_ms=None,
            source_kind="workbook",
            suite_run_name=None,
            suite_name=None,
            user=None,
            rel_branch=None,
            super_suite=None,
            test_name=None,
        )
    ]


def test_merge_history_rows_fieldwise_merges_same_day_collision() -> None:
    history = _load_history_module()
    workbook = _load_workbook_module()
    xoah = _load_xoah_module()
    parsed_workbook = workbook.ParsedWorkbook(
        models=[
            workbook.ModelRecord(
                model_name="asura_int8_subaru_2x8_t2d1",
                section="CV",
                focus="Latency",
                gops=123.4,
                customer="Subaru",
                stamp_tp="t2d1",
                batch_dp="2x8",
                vai_6_2_goal=1.7,
                npu=1.5,
                npu_6_1=1.9,
                vart_latency=2.1,
            )
        ],
        measurements=[
            workbook.MeasurementRecord(
                model_name="asura_int8_subaru_2x8_t2d1",
                date_label="7th May",
                aie=1.1,
                vart=1.3,
                perftest=1.4,
            )
        ],
        model_to_test_name={
            "asura_int8_subaru_2x8_t2d1": "asura_int8_subaru_2x8_t2d1-hw-vek385_vaiml"
        },
    )

    workbook_rows = history.seed_workbook_history_rows(parsed_workbook, year=2026)
    nightly_rows = history.nightly_records_to_history_rows(
        parsed_workbook,
        [
            xoah.NightlyRecord(
                model_name="asura_int8_subaru_2x8_t2d1",
                test_name="asura_int8_subaru_2x8_t2d1-hw-vek385_vaiml",
                suite_name="VE2_QOR_P0_HW",
                suite_run_name="20260507_004500_VE2_QOR_P0_HW",
                user="perf-bot",
                rel_branch="release/vai_6.2",
                super_suite="VAI_6_2_GEN2_REGRESSION",
                vart_latency_ms=0.9,
            )
        ],
    )

    assert history.merge_history_rows(workbook_rows, nightly_rows) == [
        history.HistoryRow(
            date=date(2026, 5, 7),
            model_name="asura_int8_subaru_2x8_t2d1",
            section="CV",
            focus="Latency",
            customer="Subaru",
            gops=123.4,
            stamp_tp="t2d1",
            batch_dp="2x8",
            target_latency_ms=1.7,
            npu_latency_ms=1.5,
            vai61_latency_ms=1.9,
            vart_latency_ms=0.9,
            aie_latency_ms=1.1,
            perftest_latency_ms=1.4,
            source_kind="xoah",
            suite_run_name="20260507_004500_VE2_QOR_P0_HW",
            suite_name="VE2_QOR_P0_HW",
            user="perf-bot",
            rel_branch="release/vai_6.2",
            super_suite="VAI_6_2_GEN2_REGRESSION",
            test_name="asura_int8_subaru_2x8_t2d1-hw-vek385_vaiml",
        )
    ]


def test_merge_history_rows_is_idempotent_for_repeated_nightly_inputs() -> None:
    history = _load_history_module()
    workbook = _load_workbook_module()
    xoah = _load_xoah_module()
    parsed_workbook = workbook.ParsedWorkbook(
        models=[
            workbook.ModelRecord(
                model_name="phoenix_int8_city",
                section="NLP",
                focus=None,
                gops=88.0,
                customer=None,
                stamp_tp="batch1",
                batch_dp="1x1",
                vai_6_2_goal=2.2,
                npu=2.0,
                npu_6_1=2.6,
                vart_latency=2.8,
            )
        ],
        measurements=[
            workbook.MeasurementRecord(
                model_name="phoenix_int8_city",
                date_label="7th May",
                aie=2.1,
                vart=2.3,
                perftest=2.4,
            )
        ],
        model_to_test_name={"phoenix_int8_city": "phoenix_int8_city-hw-vek385_vaiml"},
    )

    workbook_rows = history.seed_workbook_history_rows(parsed_workbook, year=2026)
    nightly_rows = history.nightly_records_to_history_rows(
        parsed_workbook,
        [
            xoah.NightlyRecord(
                model_name="phoenix_int8_city",
                test_name="phoenix_int8_city-hw-vek385_vaiml",
                suite_name="VE2_QOR_P0_HW",
                suite_run_name="20260507_004500_VE2_QOR_P0_HW",
                user="perf-bot",
                rel_branch="release/vai_6.2",
                super_suite="VAI_6_2_GEN2_REGRESSION",
                vart_latency_ms=2.05,
            )
        ],
    )

    merged_once = history.merge_history_rows(workbook_rows, nightly_rows)
    merged_twice = history.merge_history_rows(merged_once, nightly_rows)

    assert merged_twice == merged_once


def test_nightly_records_to_history_rows_skips_records_missing_workbook_metadata() -> None:
    history = _load_history_module()
    workbook = _load_workbook_module()
    xoah = _load_xoah_module()
    parsed_workbook = workbook.ParsedWorkbook(
        models=[],
        measurements=[],
        model_to_test_name={"missing_model": "missing_model-hw-vek385_vaiml"},
    )

    rows = history.nightly_records_to_history_rows(
        parsed_workbook,
        [
            xoah.NightlyRecord(
                model_name="missing_model",
                test_name="missing_model-hw-vek385_vaiml",
                suite_name="VE2_QOR_P0_HW",
                suite_run_name="20260507_004500_VE2_QOR_P0_HW",
                user="perf-bot",
                rel_branch="release/vai_6.2",
                super_suite="VAI_6_2_GEN2_REGRESSION",
                vart_latency_ms=1.0,
            )
        ],
    )

    assert rows == [
        history.HistoryRow(
            date=date(2026, 5, 7),
            model_name="missing_model",
            section=None,
            focus=None,
            customer=None,
            gops=None,
            stamp_tp=None,
            batch_dp=None,
            target_latency_ms=None,
            npu_latency_ms=None,
            vai61_latency_ms=None,
            vart_latency_ms=1.0,
            aie_latency_ms=None,
            perftest_latency_ms=None,
            source_kind="xoah",
            suite_run_name="20260507_004500_VE2_QOR_P0_HW",
            suite_name="VE2_QOR_P0_HW",
            user="perf-bot",
            rel_branch="release/vai_6.2",
            super_suite="VAI_6_2_GEN2_REGRESSION",
            test_name="missing_model-hw-vek385_vaiml",
        )
    ]


def test_merge_history_rows_keeps_workbook_metadata_authoritative_on_same_day_xoah_collision() -> None:
    history = _load_history_module()

    workbook_row = history.HistoryRow(
        date=date(2026, 5, 7),
        model_name="asura_int8_subaru_2x8_t2d1",
        section="Updated Section",
        focus="Updated Focus",
        customer="Updated Customer",
        gops=222.0,
        stamp_tp="t4d2",
        batch_dp="4x2",
        target_latency_ms=1.1,
        npu_latency_ms=0.8,
        vai61_latency_ms=1.2,
        vart_latency_ms=1.6,
        aie_latency_ms=1.5,
        perftest_latency_ms=1.7,
        source_kind="workbook",
        suite_run_name=None,
        suite_name=None,
        user=None,
        rel_branch=None,
        super_suite=None,
        test_name=None,
    )
    preserved_xoah_row = history.HistoryRow(
        date=date(2026, 5, 7),
        model_name="asura_int8_subaru_2x8_t2d1",
        section="Old Section",
        focus="Old Focus",
        customer="Old Customer",
        gops=10.0,
        stamp_tp="legacy-stamp",
        batch_dp="legacy-batch",
        target_latency_ms=9.9,
        npu_latency_ms=8.8,
        vai61_latency_ms=7.7,
        vart_latency_ms=0.9,
        aie_latency_ms=None,
        perftest_latency_ms=None,
        source_kind="xoah",
        suite_run_name="20260507_004500_VE2_QOR_P0_HW",
        suite_name="VE2_QOR_P0_HW",
        user="z1aiebuild",
        rel_branch="RAI_1.8",
        super_suite="VAI_6_2_GEN2_REGRESSION",
        test_name="asura_int8_subaru_2x8_t2d1-hw-vek385_vaiml",
    )

    assert history.merge_history_rows([workbook_row], [preserved_xoah_row]) == [
        history.HistoryRow(
            date=date(2026, 5, 7),
            model_name="asura_int8_subaru_2x8_t2d1",
            section="Updated Section",
            focus="Updated Focus",
            customer="Updated Customer",
            gops=222.0,
            stamp_tp="t4d2",
            batch_dp="4x2",
            target_latency_ms=1.1,
            npu_latency_ms=0.8,
            vai61_latency_ms=1.2,
            vart_latency_ms=0.9,
            aie_latency_ms=1.5,
            perftest_latency_ms=1.7,
            source_kind="xoah",
            suite_run_name="20260507_004500_VE2_QOR_P0_HW",
            suite_name="VE2_QOR_P0_HW",
            user="z1aiebuild",
            rel_branch="RAI_1.8",
            super_suite="VAI_6_2_GEN2_REGRESSION",
            test_name="asura_int8_subaru_2x8_t2d1-hw-vek385_vaiml",
        )
    ]


def test_history_csv_roundtrip(tmp_path: Path) -> None:
    history = _load_history_module()
    rows = [
        history.HistoryRow(
            date=date(2026, 5, 7),
            model_name="phoenix_int8_city",
            section="NLP",
            focus=None,
            customer=None,
            gops=88.0,
            stamp_tp="batch1",
            batch_dp="1x1",
            target_latency_ms=2.2,
            npu_latency_ms=2.0,
            vai61_latency_ms=2.6,
            vart_latency_ms=2.05,
            aie_latency_ms=None,
            perftest_latency_ms=None,
            source_kind="xoah",
            suite_run_name="20260507_004500_VE2_QOR_P0_HW",
            suite_name="VE2_QOR_P0_HW",
            user="perf-bot",
            rel_branch="release/vai_6.2",
            super_suite="VAI_6_2_GEN2_REGRESSION",
            test_name="phoenix_int8_city-hw-vek385_vaiml",
        )
    ]
    csv_path = tmp_path / "history.csv"

    history.write_history_csv(csv_path, rows)

    assert history.read_history_csv(csv_path) == rows
