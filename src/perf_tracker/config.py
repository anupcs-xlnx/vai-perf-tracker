from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class SuiteConfig:
    name: str
    workbook_sheet: str | None
    history_csv_path: Path
    dashboard_output_dir: Path


@dataclass(frozen=True)
class TrackingConfig:
    config_path: Path
    workbook_path: Path
    workbook_history_year: int
    xoah_summary_url: str
    suite_name: str
    history_csv_path: Path
    dashboard_output_dir: Path
    suites: tuple[SuiteConfig, ...]


def load_tracking_config(path: str | Path) -> TrackingConfig:
    config_path = Path(path).expanduser().resolve()
    data = json.loads(config_path.read_text(encoding="utf-8"))
    base_dir = config_path.parent
    workbook_path = _resolve_path(base_dir, data["workbook_path"], field_name="workbook_path")
    workbook_history_year = int(data["workbook_history_year"])
    xoah_summary_url = _require_text(data, "xoah_summary_url")
    legacy_history_csv_path = _resolve_path(
        base_dir,
        data["history_csv_path"],
        field_name="history_csv_path",
    )
    legacy_dashboard_output_dir = _resolve_path(
        base_dir,
        data["dashboard_output_dir"],
        field_name="dashboard_output_dir",
    )
    suites = _load_suite_configs(
        data,
        base_dir=base_dir,
        default_history_csv_path=legacy_history_csv_path,
        default_dashboard_output_dir=legacy_dashboard_output_dir,
    )
    return TrackingConfig(
        config_path=config_path,
        workbook_path=workbook_path,
        workbook_history_year=workbook_history_year,
        xoah_summary_url=xoah_summary_url,
        suite_name=suites[0].name,
        history_csv_path=legacy_history_csv_path,
        dashboard_output_dir=legacy_dashboard_output_dir,
        suites=suites,
    )


def _load_suite_configs(
    data: dict[str, Any],
    *,
    base_dir: Path,
    default_history_csv_path: Path,
    default_dashboard_output_dir: Path,
) -> tuple[SuiteConfig, ...]:
    raw_suites = data.get("suites")
    if raw_suites is None:
        suite_name = _require_text(data, "suite_name")
        return (
            SuiteConfig(
                name=suite_name,
                workbook_sheet=_optional_text(data.get("workbook_sheet"), field_name="workbook_sheet"),
                history_csv_path=default_history_csv_path,
                dashboard_output_dir=default_dashboard_output_dir,
            ),
        )

    if not isinstance(raw_suites, list) or not raw_suites:
        raise ValueError("Tracking config field 'suites' must be a non-empty list.")

    suites: list[SuiteConfig] = []
    seen_names: set[str] = set()
    for index, raw_suite in enumerate(raw_suites):
        if not isinstance(raw_suite, dict):
            raise ValueError(f"Tracking config suite at index {index} must be an object.")
        name = _require_text(raw_suite, "name")
        if name in seen_names:
            raise ValueError(f"Tracking config suite name {name!r} is duplicated.")
        seen_names.add(name)
        suites.append(
            SuiteConfig(
                name=name,
                workbook_sheet=_optional_text(
                    raw_suite.get("workbook_sheet"),
                    field_name=f"suites[{index}].workbook_sheet",
                ),
                history_csv_path=_resolve_path(
                    base_dir,
                    raw_suite.get("history_csv_path", str(default_history_csv_path)),
                    field_name=f"suites[{index}].history_csv_path",
                ),
                dashboard_output_dir=_resolve_path(
                    base_dir,
                    raw_suite.get("dashboard_output_dir", str(default_dashboard_output_dir)),
                    field_name=f"suites[{index}].dashboard_output_dir",
                ),
            )
        )
    return tuple(suites)


def _resolve_path(base_dir: Path, value: Any, *, field_name: str) -> Path:
    raw_path = Path(_require_text_value(value, field_name=field_name))
    if raw_path.is_absolute():
        return raw_path
    return (base_dir / raw_path).resolve()


def _require_text(data: dict[str, Any], key: str) -> str:
    return _require_text_value(data[key], field_name=key)


def _optional_text(value: Any, *, field_name: str) -> str | None:
    if value is None:
        return None
    return _require_text_value(value, field_name=field_name)


def _require_text_value(value: Any, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"Tracking config field {field_name!r} must be a string.")

    text = value.strip()
    if not text:
        raise ValueError(f"Tracking config field {field_name!r} must be a non-empty string.")
    return text
