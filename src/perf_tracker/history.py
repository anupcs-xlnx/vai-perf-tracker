from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
from datetime import datetime
from pathlib import Path
from typing import Literal, Sequence, TypeVar

from perf_tracker.date_labels import parse_workbook_date_label
from perf_tracker.workbook import ModelRecord, ParsedWorkbook
from perf_tracker.xoah import NightlyRecord

SourceKind = Literal["workbook", "xoah"]
HISTORY_CSV_FIELDS = (
    "date",
    "model_name",
    "section",
    "focus",
    "customer",
    "gops",
    "stamp_tp",
    "batch_dp",
    "target_latency_ms",
    "npu_latency_ms",
    "vai61_latency_ms",
    "vart_latency_ms",
    "aie_latency_ms",
    "perftest_latency_ms",
    "source_kind",
    "suite_run_name",
    "suite_name",
    "user",
    "rel_branch",
    "super_suite",
    "test_name",
    "error",
)


@dataclass(frozen=True)
class HistoryRow:
    date: date
    model_name: str
    section: str | None
    focus: str | None
    customer: str | None
    gops: float | None
    stamp_tp: str | None
    batch_dp: str | None
    target_latency_ms: float | None
    npu_latency_ms: float | None
    vai61_latency_ms: float | None
    vart_latency_ms: float | None
    aie_latency_ms: float | None
    perftest_latency_ms: float | None
    source_kind: SourceKind
    suite_run_name: str | None
    suite_name: str | None
    user: str | None
    rel_branch: str | None
    super_suite: str | None
    test_name: str | None
    error: str | None = None


def seed_workbook_history_rows(parsed_workbook: ParsedWorkbook, *, year: int) -> list[HistoryRow]:
    model_by_name = {model.model_name: model for model in parsed_workbook.models}
    rows: list[HistoryRow] = []
    for measurement in parsed_workbook.measurements:
        model = model_by_name.get(measurement.model_name)
        if model is None:
            raise ValueError(f"Missing workbook metadata for model: {measurement.model_name}")
        rows.append(
            _build_workbook_history_row(
                model=model,
                row_date=parse_workbook_date_label(measurement.date_label, year=year),
                vart_latency_ms=measurement.vart,
                aie_latency_ms=measurement.aie,
                perftest_latency_ms=measurement.perftest,
            )
        )
    return rows


def nightly_records_to_history_rows(
    parsed_workbook: ParsedWorkbook,
    nightly_records: Sequence[NightlyRecord],
) -> list[HistoryRow]:
    model_by_name = {model.model_name: model for model in parsed_workbook.models}
    rows: list[HistoryRow] = []
    for record in nightly_records:
        model = model_by_name.get(record.model_name)
        rows.append(
            HistoryRow(
                date=parse_suite_run_date(record.suite_run_name),
                model_name=record.model_name,
                section=model.section if model is not None else None,
                focus=model.focus if model is not None else None,
                customer=model.customer if model is not None else None,
                gops=model.gops if model is not None else None,
                stamp_tp=model.stamp_tp if model is not None else None,
                batch_dp=model.batch_dp if model is not None else None,
                target_latency_ms=model.vai_6_2_goal if model is not None else None,
                npu_latency_ms=model.npu if model is not None else None,
                vai61_latency_ms=model.npu_6_1 if model is not None else None,
                vart_latency_ms=record.vart_latency_ms,
                aie_latency_ms=None,
                perftest_latency_ms=None,
                source_kind="xoah",
                suite_run_name=record.suite_run_name,
                suite_name=record.suite_name,
                user=record.user,
                rel_branch=record.rel_branch,
                super_suite=record.super_suite,
                test_name=record.test_name,
                error=record.error,
            )
        )
    return rows


def refresh_xoah_history_rows(
    parsed_workbook: ParsedWorkbook,
    rows: Sequence[HistoryRow],
) -> list[HistoryRow]:
    model_by_name = {model.model_name: model for model in parsed_workbook.models}
    refreshed_rows: list[HistoryRow] = []
    for row in rows:
        model = model_by_name.get(row.model_name)
        refreshed_rows.append(
            HistoryRow(
                date=row.date,
                model_name=row.model_name,
                section=model.section if model is not None else row.section,
                focus=model.focus if model is not None else row.focus,
                customer=model.customer if model is not None else row.customer,
                gops=model.gops if model is not None else row.gops,
                stamp_tp=model.stamp_tp if model is not None else row.stamp_tp,
                batch_dp=model.batch_dp if model is not None else row.batch_dp,
                target_latency_ms=model.vai_6_2_goal if model is not None else row.target_latency_ms,
                npu_latency_ms=model.npu if model is not None else row.npu_latency_ms,
                vai61_latency_ms=model.npu_6_1 if model is not None else row.vai61_latency_ms,
                vart_latency_ms=row.vart_latency_ms,
                aie_latency_ms=row.aie_latency_ms,
                perftest_latency_ms=row.perftest_latency_ms,
                source_kind=row.source_kind,
                suite_run_name=row.suite_run_name,
                suite_name=row.suite_name,
                user=row.user,
                rel_branch=row.rel_branch,
                super_suite=row.super_suite,
                test_name=row.test_name,
                error=row.error,
            )
        )
    return refreshed_rows


def merge_history_rows(
    workbook_rows: Sequence[HistoryRow],
    nightly_rows: Sequence[HistoryRow],
) -> list[HistoryRow]:
    """Return one canonical row per `(date, model_name)`.

    Same-key collisions are merged field-wise instead of replaced wholesale:
    incoming nightly non-`None` values win, while workbook-only values like
    `aie_latency_ms` or `perftest_latency_ms` are preserved when the nightly row
    does not provide them. The merged row keeps `source_kind="xoah"` whenever
    any nightly data contributes to that canonical row.
    """

    merged: dict[tuple[date, str], HistoryRow] = {
        (row.date, row.model_name): row for row in workbook_rows
    }
    for row in nightly_rows:
        key = (row.date, row.model_name)
        existing = merged.get(key)
        merged[key] = row if existing is None else _merge_history_row_pair(existing, row)
    return sorted(merged.values(), key=lambda row: (row.date, row.model_name))


def parse_suite_run_date(suite_run_name: str) -> date:
    return datetime.strptime(suite_run_name[:8], "%Y%m%d").date()


def write_history_csv(path: str | Path, rows: Sequence[HistoryRow]) -> None:
    output_path = Path(path)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=HISTORY_CSV_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow(_row_to_csv_dict(row))


def read_history_csv(path: str | Path) -> list[HistoryRow]:
    input_path = Path(path)
    with input_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return [_row_from_csv_dict(row) for row in reader]


def _build_workbook_history_row(
    *,
    model: ModelRecord,
    row_date: date,
    vart_latency_ms: float | None,
    aie_latency_ms: float | None,
    perftest_latency_ms: float | None,
) -> HistoryRow:
    return HistoryRow(
        date=row_date,
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
        vart_latency_ms=vart_latency_ms,
        aie_latency_ms=aie_latency_ms,
        perftest_latency_ms=perftest_latency_ms,
        source_kind="workbook",
        suite_run_name=None,
        suite_name=None,
        user=None,
        rel_branch=None,
        super_suite=None,
        test_name=None,
    )


T = TypeVar("T")


def _merge_history_row_pair(existing: HistoryRow, incoming: HistoryRow) -> HistoryRow:
    if (existing.date, existing.model_name) != (incoming.date, incoming.model_name):
        raise ValueError("Cannot merge history rows with different keys.")

    metadata_authority = _metadata_authority_row(existing, incoming)

    return HistoryRow(
        date=existing.date,
        model_name=existing.model_name,
        section=metadata_authority.section,
        focus=metadata_authority.focus,
        customer=metadata_authority.customer,
        gops=metadata_authority.gops,
        stamp_tp=metadata_authority.stamp_tp,
        batch_dp=metadata_authority.batch_dp,
        target_latency_ms=metadata_authority.target_latency_ms,
        npu_latency_ms=metadata_authority.npu_latency_ms,
        vai61_latency_ms=metadata_authority.vai61_latency_ms,
        vart_latency_ms=_prefer_incoming(incoming.vart_latency_ms, existing.vart_latency_ms),
        aie_latency_ms=_prefer_incoming(incoming.aie_latency_ms, existing.aie_latency_ms),
        perftest_latency_ms=_prefer_incoming(
            incoming.perftest_latency_ms, existing.perftest_latency_ms
        ),
        source_kind="xoah"
        if "xoah" in (existing.source_kind, incoming.source_kind)
        else "workbook",
        suite_run_name=_prefer_incoming(incoming.suite_run_name, existing.suite_run_name),
        suite_name=_prefer_incoming(incoming.suite_name, existing.suite_name),
        user=_prefer_incoming(incoming.user, existing.user),
        rel_branch=_prefer_incoming(incoming.rel_branch, existing.rel_branch),
        super_suite=_prefer_incoming(incoming.super_suite, existing.super_suite),
        test_name=_prefer_incoming(incoming.test_name, existing.test_name),
        error=_prefer_incoming(incoming.error, existing.error),
    )


def _prefer_incoming(incoming: T | None, existing: T | None) -> T | None:
    return existing if incoming is None else incoming


def _metadata_authority_row(existing: HistoryRow, incoming: HistoryRow) -> HistoryRow:
    if incoming.source_kind == "workbook":
        return incoming
    if existing.source_kind == "workbook":
        return existing
    return incoming


def _row_to_csv_dict(row: HistoryRow) -> dict[str, str]:
    return {
        "date": row.date.isoformat(),
        "model_name": row.model_name,
        "section": _serialize_text(row.section),
        "focus": _serialize_text(row.focus),
        "customer": _serialize_text(row.customer),
        "gops": _serialize_float(row.gops),
        "stamp_tp": _serialize_text(row.stamp_tp),
        "batch_dp": _serialize_text(row.batch_dp),
        "target_latency_ms": _serialize_float(row.target_latency_ms),
        "npu_latency_ms": _serialize_float(row.npu_latency_ms),
        "vai61_latency_ms": _serialize_float(row.vai61_latency_ms),
        "vart_latency_ms": _serialize_float(row.vart_latency_ms),
        "aie_latency_ms": _serialize_float(row.aie_latency_ms),
        "perftest_latency_ms": _serialize_float(row.perftest_latency_ms),
        "source_kind": row.source_kind,
        "suite_run_name": _serialize_text(row.suite_run_name),
        "suite_name": _serialize_text(row.suite_name),
        "user": _serialize_text(row.user),
        "rel_branch": _serialize_text(row.rel_branch),
        "super_suite": _serialize_text(row.super_suite),
        "test_name": _serialize_text(row.test_name),
        "error": _serialize_text(row.error),
    }


def _row_from_csv_dict(row: dict[str, str]) -> HistoryRow:
    return HistoryRow(
        date=date.fromisoformat(row["date"]),
        model_name=row["model_name"],
        section=_deserialize_text(row["section"]),
        focus=_deserialize_text(row["focus"]),
        customer=_deserialize_text(row["customer"]),
        gops=_deserialize_float(row["gops"]),
        stamp_tp=_deserialize_text(row["stamp_tp"]),
        batch_dp=_deserialize_text(row["batch_dp"]),
        target_latency_ms=_deserialize_float(row["target_latency_ms"]),
        npu_latency_ms=_deserialize_float(row["npu_latency_ms"]),
        vai61_latency_ms=_deserialize_float(row["vai61_latency_ms"]),
        vart_latency_ms=_deserialize_float(row["vart_latency_ms"]),
        aie_latency_ms=_deserialize_float(row["aie_latency_ms"]),
        perftest_latency_ms=_deserialize_float(row["perftest_latency_ms"]),
        source_kind=row["source_kind"],
        suite_run_name=_deserialize_text(row["suite_run_name"]),
        suite_name=_deserialize_text(row["suite_name"]),
        user=_deserialize_text(row["user"]),
        rel_branch=_deserialize_text(row["rel_branch"]),
        super_suite=_deserialize_text(row["super_suite"]),
        test_name=_deserialize_text(row["test_name"]),
        error=_deserialize_text(row.get("error", "")),
    )


def _serialize_text(value: str | None) -> str:
    return "" if value is None else value


def _serialize_float(value: float | None) -> str:
    return "" if value is None else str(value)


def _deserialize_text(value: str) -> str | None:
    return value or None


def _deserialize_float(value: str) -> float | None:
    return None if value == "" else float(value)
