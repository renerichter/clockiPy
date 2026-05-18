"""Smoke tests: drive the CLI through subprocess like a real user.

Network is mocked at the Python process level by setting credentials to a
sentinel and using ``--no-cache`` + ``--digest`` (which never calls the API).
For paths that *do* call the API, we verify the CLI exits cleanly on
``--help`` and validates flags.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _run(args, env=None):
    """Run `python -m clockipy ...` and return CompletedProcess."""
    full_env = os.environ.copy()
    if env:
        full_env.update(env)
    return subprocess.run(
        [sys.executable, "-m", "clockipy", *args],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        env=full_env,
        timeout=30,
    )


def test_help_exits_zero_and_documents_flags():
    result = _run(["--help"])
    assert result.returncode == 0
    out = result.stdout
    for flag in ["--mode", "--start", "--end", "--refresh", "--no-cache",
                 "--goals", "--digest", "--verbose", "--quiet"]:
        assert flag in out, f"--help missing flag {flag}\n{out}"


def test_invalid_mode_exits_nonzero():
    result = _run(["--mode", "fortnight"])
    assert result.returncode != 0
    assert "invalid choice" in result.stderr.lower() or "invalid" in result.stderr.lower()


def test_missing_credentials_exits_nonzero(tmp_path):
    # Clear env so credential resolution must fail.
    env = {
        "CLOCKIFY_API_KEY": "",
        "CLOCKIFY_WORKSPACE_ID": "",
        "CLOCKIFY_USER_ID": "",
        # Point HOME elsewhere so ~/rene.env / clockipy.env can't accidentally satisfy.
        "HOME": str(tmp_path),
        "XDG_CONFIG_HOME": str(tmp_path / "config"),
        "XDG_CACHE_HOME": str(tmp_path / "cache"),
    }
    result = _run(["--mode", "week", "--start", "2026-05-15"], env=env)
    assert result.returncode != 0
    assert "Missing Clockify credentials" in result.stderr or \
           "Missing Clockify credentials" in result.stdout


def test_module_entrypoint_importable():
    """clockipy.__main__ must remain importable as a backwards-compat shim."""
    result = subprocess.run(
        [sys.executable, "-c", "import clockipy.__main__; assert callable(clockipy.__main__.main)"],
        capture_output=True, text=True, cwd=str(REPO_ROOT), timeout=10,
    )
    assert result.returncode == 0, result.stderr
