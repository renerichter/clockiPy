"""File I/O utility functions for clockiPy."""
from __future__ import annotations

import csv
import logging
import os
import sys
from datetime import date

logger = logging.getLogger(__name__)


def write_csv(filename: str, headers: list, rows: list) -> None:
    """Write data to a CSV file."""
    with open(filename, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)


def _validate_markdown(text: str) -> None:
    """Lightweight sanity-check for generated markdown.

    Replaces the previous ``markdown.markdown`` round-trip (which only
    rendered HTML and could not actually fail on malformed markdown) with
    explicit structural checks: non-empty content and balanced fenced
    code blocks. This removes the ``markdown`` runtime dependency.
    """
    if not text.strip():
        raise ValueError("Markdown content is empty.")
    if text.count("```") % 2 != 0:
        raise ValueError("Unbalanced fenced code block (```) in markdown output.")


def write_markdown(
    md_path: str,
    content: str,
    start_date: date,
    end_date: date,
    overwrite: bool = False,
) -> None:
    """Write content to a Markdown file with structural validation."""
    file_exists = os.path.exists(md_path)
    if file_exists and not overwrite:
        mode = 'a'
        logger.info("File '%s' exists. Appending output.", md_path)
    elif file_exists and overwrite:
        mode = 'w'
        logger.info("File '%s' exists. Overwriting as requested.", md_path)
    else:
        mode = 'w'
        logger.info("File '%s' does not exist. Creating new file.", md_path)

    try:
        with open(md_path, mode, encoding='utf-8') as f:
            if mode == 'w' or (mode == 'a' and os.stat(md_path).st_size == 0):
                f.write(f"# Analysis of {start_date} to {end_date}\n\n")
            f.write(content)
    except OSError as e:
        logger.error("Failed to write to '%s': %s", md_path, e)
        sys.exit(2)

    try:
        with open(md_path, encoding='utf-8') as f:
            _validate_markdown(f.read())
    except ValueError as e:
        logger.error("Markdown validation failed for '%s': %s", md_path, e)
        sys.exit(3)
