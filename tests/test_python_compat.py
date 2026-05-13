from __future__ import annotations

import ast
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_xoah_module_parses_with_python_310_grammar() -> None:
    xoah_source = (PROJECT_ROOT / "src" / "perf_tracker" / "xoah.py").read_text(
        encoding="utf-8"
    )

    try:
        ast.parse(
            xoah_source,
            filename="src/perf_tracker/xoah.py",
            feature_version=(3, 10),
        )
    except SyntaxError as exc:
        pytest.fail(f"Expected xoah.py to parse under Python 3.10 grammar, but got: {exc}")


def test_pyproject_declares_python_310_support() -> None:
    pyproject_text = (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert 'requires-python = ">=3.10"' in pyproject_text
