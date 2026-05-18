"""Tests for CLI logging configuration."""
from __future__ import annotations

import logging

import pytest

from clockipy.cli import configure_logging


@pytest.fixture(autouse=True)
def _reset_logging():
    # Snapshot root handlers/level so basicConfig(force=True) doesn't leak.
    root = logging.getLogger()
    saved_handlers = root.handlers[:]
    saved_level = root.level
    yield
    root.handlers = saved_handlers
    root.setLevel(saved_level)


def test_default_level_is_warning():
    configure_logging(verbose=0, quiet=False)
    assert logging.getLogger().level == logging.WARNING


def test_verbose_once_sets_info():
    configure_logging(verbose=1, quiet=False)
    assert logging.getLogger().level == logging.INFO


def test_verbose_twice_sets_debug():
    configure_logging(verbose=2, quiet=False)
    assert logging.getLogger().level == logging.DEBUG


def test_quiet_overrides_verbose():
    configure_logging(verbose=2, quiet=True)
    assert logging.getLogger().level == logging.WARNING


def test_basic_config_is_reapplied_on_reconfigure():
    configure_logging(verbose=0, quiet=False)
    configure_logging(verbose=2, quiet=False)
    assert logging.getLogger().level == logging.DEBUG
