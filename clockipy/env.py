"""Environment & credential loading for clockiPy.

Precedence (first source with all required vars wins):
1. Process environment
2. ``~/rene.env``
3. ``<repo>/clockipy.env``

A missing optional ``CLOCKIFY_USER_ID`` is auto-resolved against the Clockify
``/user`` endpoint and cached back into ``os.environ`` for the run.
"""
from __future__ import annotations

import logging
import os
import shlex
import sys
from collections.abc import Iterable
from typing import List

from .api.client import ClockifyClient
from .api.errors import ClockifyAPIError

log = logging.getLogger(__name__)

REQUIRED_ENV_VARS = (
    "CLOCKIFY_API_KEY",
    "CLOCKIFY_WORKSPACE_ID",
)


def has_required_env() -> bool:
    return all(os.getenv(key) for key in REQUIRED_ENV_VARS)


def candidate_env_files() -> List[str]:
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return [
        os.path.join(os.path.expanduser("~"), "rene.env"),
        os.path.join(repo_root, "clockipy.env"),
    ]


def load_env_file(env_file: str) -> None:
    """Load ``KEY=value`` pairs from a file without overriding existing vars."""
    with open(env_file, encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[len("export "):].lstrip()
            if "=" not in line:
                continue
            key, raw_value = line.split("=", 1)
            key = key.strip()
            if not key or key in os.environ:
                continue
            raw_value = raw_value.strip()
            if raw_value:
                try:
                    parts = shlex.split(raw_value, posix=True)
                except ValueError:
                    parts = [raw_value.strip("'\"")]
                value = parts[0] if len(parts) == 1 else " ".join(parts)
            else:
                value = ""
            os.environ[key] = value


def load_environment(candidates: Iterable[str] | None = None) -> None:
    """Load Clockify credentials, exiting with a helpful message on failure."""
    if has_required_env():
        return
    for env_file in candidates if candidates is not None else candidate_env_files():
        if not os.path.exists(env_file):
            continue
        load_env_file(env_file)
        if has_required_env():
            return
    print("Missing Clockify credentials.", file=sys.stderr)
    print("Set CLOCKIFY_API_KEY and CLOCKIFY_WORKSPACE_ID in your environment.", file=sys.stderr)
    print("CLOCKIFY_USER_ID is optional and will be auto-detected when missing.", file=sys.stderr)
    print("Checked current environment, ~/rene.env, and clockipy.env.", file=sys.stderr)
    sys.exit(1)


def get_env_var(key: str) -> str:
    value = os.getenv(key)
    if not value:
        print(f"Set {key} in your environment, ~/rene.env, or clockipy.env.", file=sys.stderr)
        sys.exit(1)
    return value


def resolve_user_id(api_key: str, workspace_id: str) -> str:
    user_id = os.getenv("CLOCKIFY_USER_ID")
    if user_id:
        return user_id
    client = ClockifyClient(api_key, workspace_id, "")
    try:
        user, _ = client.get_user_and_workspaces()
    except ClockifyAPIError as e:
        print(f"Unable to query Clockify for user id: {e}", file=sys.stderr)
        sys.exit(1)
    user_id = user.get("id")
    if not user_id:
        print("Unable to determine CLOCKIFY_USER_ID from the Clockify API.", file=sys.stderr)
        sys.exit(1)
    return user_id
