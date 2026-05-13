from __future__ import annotations

import calendar
from datetime import date
import re

DATE_LABEL_RE = re.compile(r"^(?P<day>\d{1,2})(?:st|nd|rd|th)\s+(?P<month>[A-Za-z]+)$")

def _month_aliases(month_number: int) -> tuple[str, ...]:
    full_name = calendar.month_name[month_number].lower()
    abbreviation = calendar.month_abbr[month_number].lower()
    if full_name == "september":
        return full_name, abbreviation, "sept"
    return full_name, abbreviation


MONTH_NAME_TO_NUMBER = {
    alias: month_number
    for month_number in range(1, 13)
    for alias in _month_aliases(month_number)
}


def is_workbook_date_label(value: str) -> bool:
    return _parse_date_label_parts(value) is not None


def parse_workbook_date_label(date_label: str, *, year: int) -> date:
    parsed_parts = _parse_date_label_parts(date_label)
    if parsed_parts is None:
        raise ValueError(f"Unsupported workbook date label: {date_label!r}")
    day, month = parsed_parts
    return date(year, month, day)


def _parse_date_label_parts(date_label: str) -> tuple[int, int] | None:
    match = DATE_LABEL_RE.fullmatch(date_label.strip())
    if match is None:
        return None

    day = int(match.group("day"))
    month = MONTH_NAME_TO_NUMBER.get(match.group("month").lower())
    if month is None:
        return None

    try:
        # Validate month/day combinations independently of workbook year.
        date(2000, month, day)
    except ValueError:
        return None

    return day, month
