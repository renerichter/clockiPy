"""Tests for write_markdown structural validation (no `markdown` dep)."""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from clockipy.utils.file_utils import _validate_markdown, write_markdown


def test_validate_accepts_basic_markdown():
    _validate_markdown("# Title\n\nSome text.\n")


def test_validate_rejects_empty():
    with pytest.raises(ValueError, match="empty"):
        _validate_markdown("   \n  ")


def test_validate_rejects_unbalanced_fences():
    with pytest.raises(ValueError, match="Unbalanced"):
        _validate_markdown("# Title\n```python\nprint('x')\n")


def test_validate_accepts_balanced_fences():
    _validate_markdown("# Title\n```python\nprint('x')\n```\n")


def test_write_markdown_creates_file_with_header(tmp_path: Path):
    target = tmp_path / "report.md"
    write_markdown(str(target), "## Section\nbody\n",
                   date(2026, 1, 1), date(2026, 1, 7), overwrite=False)
    text = target.read_text(encoding="utf-8")
    assert text.startswith("# Analysis of 2026-01-01 to 2026-01-07")
    assert "## Section" in text


def test_write_markdown_appends_when_exists(tmp_path: Path):
    target = tmp_path / "report.md"
    target.write_text("# Pre-existing\n", encoding="utf-8")
    write_markdown(str(target), "## Appended\n",
                   date(2026, 1, 1), date(2026, 1, 7), overwrite=False)
    text = target.read_text(encoding="utf-8")
    assert text.startswith("# Pre-existing")
    assert "## Appended" in text


def test_write_markdown_overwrites_when_requested(tmp_path: Path):
    target = tmp_path / "report.md"
    target.write_text("# Old content\n", encoding="utf-8")
    write_markdown(str(target), "## Fresh\n",
                   date(2026, 1, 1), date(2026, 1, 7), overwrite=True)
    text = target.read_text(encoding="utf-8")
    assert "Old content" not in text
    assert text.startswith("# Analysis of 2026-01-01 to 2026-01-07")
    assert "## Fresh" in text


def test_write_markdown_exits_on_unbalanced_fences(tmp_path: Path):
    target = tmp_path / "bad.md"
    with pytest.raises(SystemExit) as exc:
        write_markdown(str(target), "```python\nno close\n",
                       date(2026, 1, 1), date(2026, 1, 1), overwrite=True)
    assert exc.value.code == 3
