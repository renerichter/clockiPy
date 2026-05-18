"""Unit tests for the SQLite cache."""
from __future__ import annotations

import sqlite3
from datetime import date

from clockipy.store.sqlite import (
    DEFAULT_MAX_AGE_SECONDS,
    SCHEMA_VERSION,
    Cache,
    default_db_path,
)

# ---- path resolution -------------------------------------------------------

def test_default_db_path_uses_xdg_cache_home(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    p = default_db_path("ws-123", "user-456")
    assert p == tmp_path / "clockipy" / "ws_123__user_456.db"


def test_default_db_path_falls_back_to_home_cache(monkeypatch, tmp_path):
    monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    p = default_db_path("ws", "u")
    assert p == tmp_path / ".cache" / "clockipy" / "ws__u.db"


def test_default_db_path_sanitizes_unsafe_characters(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    p = default_db_path("ws/with..slashes", "user@host")
    assert ".." not in p.name
    assert "/" not in p.name
    assert "@" not in p.name


# ---- schema ----------------------------------------------------------------

def test_schema_is_created_on_first_open(tmp_path):
    db = tmp_path / "cache.db"
    Cache(db).close()
    conn = sqlite3.connect(str(db))
    try:
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
    finally:
        conn.close()
    assert {"meta", "sync_state", "time_entries", "projects", "tags", "tasks"} <= tables


def test_schema_version_stored(tmp_path):
    db = tmp_path / "cache.db"
    Cache(db).close()
    conn = sqlite3.connect(str(db))
    try:
        v = conn.execute(
            "SELECT value FROM meta WHERE key='schema_version'"
        ).fetchone()[0]
    finally:
        conn.close()
    assert int(v) == SCHEMA_VERSION


def test_schema_mismatch_triggers_rebuild(tmp_path):
    db = tmp_path / "cache.db"
    c = Cache(db)
    c.upsert_projects({"p1": "Project One"})
    c.close()

    # Corrupt the schema version.
    conn = sqlite3.connect(str(db))
    conn.execute(
        "UPDATE meta SET value=? WHERE key='schema_version'",
        (str(SCHEMA_VERSION + 99),),
    )
    conn.commit()
    conn.close()

    c2 = Cache(db)
    try:
        # Tables exist but data was wiped.
        assert c2.get_project_map() == {}
    finally:
        c2.close()


# ---- entries ---------------------------------------------------------------

def _entry(eid: str, start_iso: str, *, project="p1", task=None) -> dict:
    return {
        "id": eid,
        "timeInterval": {"start": start_iso, "end": start_iso, "duration": "PT1H"},
        "projectId": project,
        "taskId": task,
        "tagIds": [],
        "description": f"entry {eid}",
    }


def test_upsert_and_get_entries_roundtrip(tmp_path):
    c = Cache(tmp_path / "cache.db")
    entries = [
        _entry("e1", "2026-05-15T08:00:00Z"),
        _entry("e2", "2026-05-15T09:00:00Z"),
        _entry("e3", "2026-05-16T10:00:00Z"),
    ]
    assert c.upsert_entries(entries) == 3
    got = c.get_entries(date(2026, 5, 15), date(2026, 5, 15))
    assert [e["id"] for e in got] == ["e1", "e2"]
    got_all = c.get_entries(date(2026, 5, 15), date(2026, 5, 16))
    assert [e["id"] for e in got_all] == ["e1", "e2", "e3"]


def test_upsert_is_idempotent_on_id(tmp_path):
    c = Cache(tmp_path / "cache.db")
    c.upsert_entries([_entry("e1", "2026-05-15T08:00:00Z")])
    updated = _entry("e1", "2026-05-15T08:00:00Z")
    updated["description"] = "updated"
    c.upsert_entries([updated])
    got = c.get_entries(date(2026, 5, 15), date(2026, 5, 15))
    assert len(got) == 1
    assert got[0]["description"] == "updated"


def test_upsert_skips_entries_without_id_or_start(tmp_path):
    c = Cache(tmp_path / "cache.db")
    bad = [
        {"id": "no-interval"},
        {"timeInterval": {"start": "2026-05-15T08:00:00Z"}},  # no id
        _entry("ok", "2026-05-15T08:00:00Z"),
    ]
    assert c.upsert_entries(bad) == 1


# ---- freshness -------------------------------------------------------------

def test_fresh_within_window(tmp_path):
    fake_now = [1000.0]
    c = Cache(tmp_path / "cache.db", now=lambda: fake_now[0])
    c.record_sync(date(2026, 5, 1), date(2026, 5, 31))
    fake_now[0] = 1000.0 + DEFAULT_MAX_AGE_SECONDS - 1
    assert c.is_fresh(date(2026, 5, 10), date(2026, 5, 20))


def test_stale_after_window(tmp_path):
    fake_now = [1000.0]
    c = Cache(tmp_path / "cache.db", now=lambda: fake_now[0])
    c.record_sync(date(2026, 5, 1), date(2026, 5, 31))
    fake_now[0] = 1000.0 + DEFAULT_MAX_AGE_SECONDS + 1
    assert not c.is_fresh(date(2026, 5, 10), date(2026, 5, 20))


def test_stale_when_range_not_covered(tmp_path):
    c = Cache(tmp_path / "cache.db")
    c.record_sync(date(2026, 5, 1), date(2026, 5, 15))
    assert not c.is_fresh(date(2026, 5, 1), date(2026, 5, 31))


def test_fresh_picks_most_recent_covering_sync(tmp_path):
    fake_now = [1000.0]
    c = Cache(tmp_path / "cache.db", now=lambda: fake_now[0])
    c.record_sync(date(2026, 1, 1), date(2026, 12, 31))  # old, but covers
    fake_now[0] = 1000.0 + DEFAULT_MAX_AGE_SECONDS * 10  # way past stale
    fake_now[0] += 1
    c.record_sync(date(2026, 5, 1), date(2026, 5, 31))   # fresh, narrower
    assert c.is_fresh(date(2026, 5, 10), date(2026, 5, 20))


# ---- lookup maps -----------------------------------------------------------

def test_lookup_maps_roundtrip(tmp_path):
    c = Cache(tmp_path / "cache.db")
    c.upsert_projects({"p1": "Project One", "p2": "Project Two"})
    c.upsert_tags({"t1": "Tag One"})
    c.upsert_tasks({("p1", "tk1"): "SubProject A"})
    assert c.get_project_map() == {"p1": "Project One", "p2": "Project Two"}
    assert c.get_tag_map() == {"t1": "Tag One"}
    assert c.get_task_map() == {("p1", "tk1"): "SubProject A"}


def test_lookup_upsert_is_idempotent(tmp_path):
    c = Cache(tmp_path / "cache.db")
    c.upsert_projects({"p1": "Old"})
    c.upsert_projects({"p1": "New"})
    assert c.get_project_map() == {"p1": "New"}
