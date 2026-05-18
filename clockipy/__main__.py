"""Backwards-compatible entry shim.

Real logic lives in :mod:`clockipy.cli`, :mod:`clockipy.env`, and
:mod:`clockipy.orchestrator`. This module re-exports the public names used by
existing tests and consumers so ``python -m clockipy`` and previous import
paths keep working.
"""
from __future__ import annotations

from .cli import build_parser, main, parse_args  # noqa: F401
from .env import (  # noqa: F401
    REQUIRED_ENV_VARS,
    candidate_env_files,
    get_env_var,
    has_required_env,
    load_env_file,
    load_environment,
    resolve_user_id,
)
from .orchestrator import (  # noqa: F401
    date_interface,
    list_user_and_workspaces,
)

if __name__ == "__main__":
    main()
