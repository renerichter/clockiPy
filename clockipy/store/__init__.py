"""Persistence layer for clockiPy (SQLite cache).

This package provides a local cache so the CLI doesn't hammer the Clockify
API on every invocation. The cache lives under ``$XDG_CACHE_HOME`` (default
``~/.cache``) and is scoped per ``(workspace_id, user_id)`` to avoid
cross-account pollution.
"""

from .sqlite import Cache, default_db_path

__all__ = ["Cache", "default_db_path"]
