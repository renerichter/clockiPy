"""Tests for the weekly digest builder."""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from clockipy.digest import (
    build_digest,
    iso_week_bounds,
    render_digest,
)
from clockipy.store import Cache


def _entry(eid: str, day: date, hours: float, *, project="p1", tags=("tag1",)) -> dict:
    secs = int(hours * 3600)
    h, rem = divmod(secs, 3600)
    m, s = divmod(rem, 60)
    duration = "PT"
    if h:
        duration += f"{h}H"
    if m:
        duration += f"{m}M"
    if s or duration == "PT":
        duration += f"{s}S"
    return {
        "id": eid,
        "timeInterval": {
            "start": f"{day.isoformat()}T10:00:00Z",
            "end": f"{day.isoformat()}T11:00:00Z",
            "duration": duration,
        },
        "projectId": project,
        "tagIds": list(tags),
        "description": eid,
    }


def test_iso_week_bounds_returns_monday_through_sunday():
    # 2026-05-20 is a Wednesday.
    start, end = iso_week_bounds(date(2026, 5, 20))
    assert start.weekday() == 0  # Monday
    assert end.weekday() == 6  # Sunday
    assert (end - start).days == 6


@pytest.fixture
def populated_cache(tmp_path):
    """Cache with 4 prior weeks of ~10h/wk on p1 and the current week with 10h."""
    cache = Cache(tmp_path / "cache.db")
    cache.upsert_projects({"p1": "Project One"})
    cache.upsert_tags({"tag1": "Tag One"})

    ref = date(2026, 5, 20)  # Wed
    week_start, _ = iso_week_bounds(ref)

    entries = []
    counter = 0
    # Current week: 10h
    entries.append(_entry(f"e{counter}", week_start, 10.0))
    counter += 1
    # 4 prior weeks: 10h each
    for i in range(1, 5):
        prev = week_start - timedelta(days=7 * i)
        entries.append(_entry(f"e{counter}", prev, 10.0))
        counter += 1
    cache.upsert_entries(entries)
    return cache, ref


def test_digest_with_no_history(tmp_path):
    cache = Cache(tmp_path / "cache.db")
    cache.upsert_projects({"p1": "Project One"})
    cache.upsert_tags({"tag1": "Tag One"})
    week_start, _ = iso_week_bounds(date(2026, 5, 20))
    cache.upsert_entries([_entry("e1", week_start, 5.0)])

    d = build_digest(cache, ref=date(2026, 5, 20))
    assert d.history_weeks_available == 0
    proj_row = next(r for r in d.rows if r.label == "project: Project One")
    assert proj_row.actual_hours == pytest.approx(5.0)
    assert proj_row.median_4w_hours is None
    assert proj_row.is_anomaly is False


def test_digest_no_anomaly_when_actual_matches_median(populated_cache):
    cache, ref = populated_cache
    d = build_digest(cache, ref=ref)
    assert d.history_weeks_available == 4
    proj_row = next(r for r in d.rows if r.label == "project: Project One")
    assert proj_row.actual_hours == pytest.approx(10.0)
    assert proj_row.median_4w_hours == pytest.approx(10.0)
    assert proj_row.delta_pct == pytest.approx(0.0)
    assert proj_row.is_anomaly is False


def test_digest_flags_anomaly_when_actual_far_from_median(tmp_path):
    cache = Cache(tmp_path / "cache.db")
    cache.upsert_projects({"p1": "Project One"})
    cache.upsert_tags({"tag1": "Tag One"})
    week_start, _ = iso_week_bounds(date(2026, 5, 20))

    entries = [_entry("e0", week_start, 20.0)]  # this week: double
    for i in range(1, 5):
        prev = week_start - timedelta(days=7 * i)
        entries.append(_entry(f"e{i}", prev, 10.0))
    cache.upsert_entries(entries)

    d = build_digest(cache, ref=date(2026, 5, 20))
    proj_row = next(r for r in d.rows if r.label == "project: Project One")
    assert proj_row.delta_pct == pytest.approx(100.0)
    assert proj_row.is_anomaly is True
    assert proj_row in d.anomalies


def test_anomaly_requires_min_history(tmp_path):
    cache = Cache(tmp_path / "cache.db")
    cache.upsert_projects({"p1": "Project One"})
    cache.upsert_tags({"tag1": "Tag One"})
    week_start, _ = iso_week_bounds(date(2026, 5, 20))
    # this week 20h, only ONE prior week of 10h → insufficient history.
    cache.upsert_entries([
        _entry("e0", week_start, 20.0),
        _entry("e1", week_start - timedelta(days=7), 10.0),
    ])
    d = build_digest(cache, ref=date(2026, 5, 20))
    assert d.history_weeks_available == 1
    proj_row = next(r for r in d.rows if r.label == "project: Project One")
    assert proj_row.is_anomaly is False  # gated by MIN_HISTORY_FOR_ANOMALY


def test_threshold_below_anomaly(tmp_path):
    cache = Cache(tmp_path / "cache.db")
    cache.upsert_projects({"p1": "Project One"})
    cache.upsert_tags({"tag1": "Tag One"})
    week_start, _ = iso_week_bounds(date(2026, 5, 20))
    # this week 11.5h vs 10h median → +15% (below 25% threshold)
    cache.upsert_entries([_entry("e0", week_start, 11.5)] + [
        _entry(f"e{i}", week_start - timedelta(days=7 * i), 10.0)
        for i in range(1, 5)
    ])
    d = build_digest(cache, ref=date(2026, 5, 20))
    proj_row = next(r for r in d.rows if r.label == "project: Project One")
    assert proj_row.delta_pct == pytest.approx(15.0)
    assert proj_row.is_anomaly is False


def test_render_digest_contains_key_sections(populated_cache):
    cache, ref = populated_cache
    d = build_digest(cache, ref=ref)
    out = render_digest(d)
    assert "# Weekly Digest" in out
    assert "Total tracked:" in out
    assert "project: Project One" in out
    assert "tag: Tag One" in out


def test_render_digest_shows_anomaly_callout(tmp_path):
    cache = Cache(tmp_path / "cache.db")
    cache.upsert_projects({"p1": "Project One"})
    cache.upsert_tags({"tag1": "Tag One"})
    week_start, _ = iso_week_bounds(date(2026, 5, 20))
    entries = [_entry("e0", week_start, 20.0)]
    for i in range(1, 5):
        entries.append(_entry(f"e{i}", week_start - timedelta(days=7 * i), 10.0))
    cache.upsert_entries(entries)
    d = build_digest(cache, ref=date(2026, 5, 20))
    out = render_digest(d)
    assert "## ⚠️  Anomalies" in out
    assert "Project One" in out


def test_render_digest_explains_missing_history(tmp_path):
    cache = Cache(tmp_path / "cache.db")
    cache.upsert_projects({"p1": "Project One"})
    cache.upsert_tags({"tag1": "Tag One"})
    week_start, _ = iso_week_bounds(date(2026, 5, 20))
    cache.upsert_entries([_entry("e0", week_start, 5.0)])
    d = build_digest(cache, ref=date(2026, 5, 20))
    out = render_digest(d)
    assert "Anomaly detection needs" in out
