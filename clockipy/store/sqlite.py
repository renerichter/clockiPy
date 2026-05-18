"""SQLite-backed cache for Clockify time entries and lookup maps.

Design:
- One DB file per ``(workspace_id, user_id)`` (no cross-account mixing).
- Schema is versioned via a ``meta`` table; on version mismatch the cache is
  dropped and rebuilt from the API (acceptable for a personal tool).
- Freshness is decided per requested ``(start, end)`` range: a sync record
  must overlap the request and be younger than ``max_age_seconds``.
- Time-entry rows store the raw JSON payload so consumers see exactly what
  Clockify returned — no lossy projection.
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import time
from collections.abc import Iterable
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)

SCHEMA_VERSION = 1
DEFAULT_MAX_AGE_SECONDS = 3600  # 1 hour


def _xdg_cache_home() -> Path:
    raw = os.environ.get("XDG_CACHE_HOME")
    if raw:
        return Path(raw)
    return Path.home() / ".cache"


def default_db_path(workspace_id: str, user_id: str) -> Path:
    """Return the canonical cache path for a (workspace_id, user_id) pair."""
    safe_ws = "".join(c if c.isalnum() else "_" for c in workspace_id) or "ws"
    safe_user = "".join(c if c.isalnum() else "_" for c in user_id) or "user"
    return _xdg_cache_home() / "clockipy" / f"{safe_ws}__{safe_user}.db"


class Cache:
    """SQLite cache for one (workspace_id, user_id) pair."""

    def __init__(self, db_path: Path | str, *, now: Optional[callable] = None) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._now = now or time.time
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._ensure_schema()

    # ---- lifecycle ---------------------------------------------------------

    def close(self) -> None:
        try:
            self._conn.close()
        except sqlite3.Error:
            pass

    def __enter__(self) -> Cache:
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    @contextmanager
    def _tx(self):
        try:
            yield self._conn
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise

    # ---- schema ------------------------------------------------------------

    def _ensure_schema(self) -> None:
        cur = self._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='meta'"
        )
        if cur.fetchone() is None:
            self._create_schema()
            return

        version = self._read_version()
        if version != SCHEMA_VERSION:
            log.warning(
                "Cache schema version mismatch (have=%s, want=%s); rebuilding.",
                version, SCHEMA_VERSION,
            )
            self._drop_all()
            self._create_schema()

    def _read_version(self) -> Optional[int]:
        row = self._conn.execute(
            "SELECT value FROM meta WHERE key='schema_version'"
        ).fetchone()
        if row is None:
            return None
        try:
            return int(row["value"])
        except (TypeError, ValueError):
            return None

    def _drop_all(self) -> None:
        with self._tx() as conn:
            for table in ("time_entries", "projects", "tags", "tasks",
                          "sync_state", "meta"):
                conn.execute(f"DROP TABLE IF EXISTS {table}")

    def _create_schema(self) -> None:
        with self._tx() as conn:
            conn.executescript(
                """
                CREATE TABLE meta (
                    key   TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE TABLE sync_state (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    range_start  TEXT NOT NULL,
                    range_end    TEXT NOT NULL,
                    fetched_at   REAL NOT NULL
                );
                CREATE INDEX idx_sync_range
                    ON sync_state(range_start, range_end);

                CREATE TABLE time_entries (
                    id          TEXT PRIMARY KEY,
                    start_iso   TEXT NOT NULL,
                    end_iso     TEXT,
                    project_id  TEXT,
                    task_id     TEXT,
                    raw_json    TEXT NOT NULL
                );
                CREATE INDEX idx_entries_start ON time_entries(start_iso);

                CREATE TABLE projects (
                    id   TEXT PRIMARY KEY,
                    name TEXT NOT NULL
                );

                CREATE TABLE tags (
                    id   TEXT PRIMARY KEY,
                    name TEXT NOT NULL
                );

                CREATE TABLE tasks (
                    project_id TEXT NOT NULL,
                    task_id    TEXT NOT NULL,
                    name       TEXT NOT NULL,
                    PRIMARY KEY (project_id, task_id)
                );
                """
            )
            conn.execute(
                "INSERT INTO meta(key, value) VALUES('schema_version', ?)",
                (str(SCHEMA_VERSION),),
            )

    # ---- freshness ---------------------------------------------------------

    def is_fresh(
        self,
        start: date,
        end: date,
        max_age_seconds: int = DEFAULT_MAX_AGE_SECONDS,
    ) -> bool:
        """True iff a sync exists that fully covers (start, end) and is younger than max_age."""
        row = self._conn.execute(
            """
            SELECT fetched_at FROM sync_state
            WHERE range_start <= ? AND range_end >= ?
            ORDER BY fetched_at DESC LIMIT 1
            """,
            (start.isoformat(), end.isoformat()),
        ).fetchone()
        if row is None:
            return False
        age = self._now() - float(row["fetched_at"])
        return age <= max_age_seconds

    def record_sync(self, start: date, end: date) -> None:
        with self._tx() as conn:
            conn.execute(
                "INSERT INTO sync_state(range_start, range_end, fetched_at) "
                "VALUES(?, ?, ?)",
                (start.isoformat(), end.isoformat(), float(self._now())),
            )

    # ---- entries -----------------------------------------------------------

    def upsert_entries(self, entries: Iterable[Dict[str, Any]]) -> int:
        rows = []
        for e in entries:
            eid = e.get("id")
            interval = e.get("timeInterval") or {}
            start_iso = interval.get("start")
            if not eid or not start_iso:
                continue
            rows.append((
                eid,
                start_iso,
                interval.get("end"),
                e.get("projectId"),
                e.get("taskId"),
                json.dumps(e, separators=(",", ":")),
            ))
        if not rows:
            return 0
        with self._tx() as conn:
            conn.executemany(
                "INSERT OR REPLACE INTO time_entries"
                "(id, start_iso, end_iso, project_id, task_id, raw_json) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                rows,
            )
        return len(rows)

    def get_entries(self, start: date, end: date) -> List[Dict[str, Any]]:
        """Return cached entries whose start_iso date (UTC) falls in [start, end]."""
        # Inclusive bounds on the calendar-day boundary in UTC.
        start_bound = f"{start.isoformat()}T00:00:00Z"
        end_bound = f"{end.isoformat()}T23:59:59Z"
        rows = self._conn.execute(
            "SELECT raw_json FROM time_entries "
            "WHERE start_iso >= ? AND start_iso <= ? "
            "ORDER BY start_iso",
            (start_bound, end_bound),
        ).fetchall()
        return [json.loads(r["raw_json"]) for r in rows]

    # ---- lookup maps -------------------------------------------------------

    def upsert_projects(self, mapping: Dict[str, str]) -> None:
        if not mapping:
            return
        with self._tx() as conn:
            conn.executemany(
                "INSERT OR REPLACE INTO projects(id, name) VALUES(?, ?)",
                list(mapping.items()),
            )

    def upsert_tags(self, mapping: Dict[str, str]) -> None:
        if not mapping:
            return
        with self._tx() as conn:
            conn.executemany(
                "INSERT OR REPLACE INTO tags(id, name) VALUES(?, ?)",
                list(mapping.items()),
            )

    def upsert_tasks(self, mapping: Dict[Tuple[str, str], str]) -> None:
        if not mapping:
            return
        with self._tx() as conn:
            conn.executemany(
                "INSERT OR REPLACE INTO tasks(project_id, task_id, name) "
                "VALUES(?, ?, ?)",
                [(pid, tid, name) for (pid, tid), name in mapping.items()],
            )

    def get_project_map(self) -> Dict[str, str]:
        return {r["id"]: r["name"]
                for r in self._conn.execute("SELECT id, name FROM projects")}

    def get_tag_map(self) -> Dict[str, str]:
        return {r["id"]: r["name"]
                for r in self._conn.execute("SELECT id, name FROM tags")}

    def get_task_map(self) -> Dict[Tuple[str, str], str]:
        return {
            (r["project_id"], r["task_id"]): r["name"]
            for r in self._conn.execute(
                "SELECT project_id, task_id, name FROM tasks"
            )
        }
