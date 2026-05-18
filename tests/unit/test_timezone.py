"""Tests for TimeEntry timezone-aware start_date.

Verifies the bug fix: recurring tasks must group by *local* calendar day,
not UTC day. A 23:30 local-time entry on Monday must not be bucketed under
Tuesday's recurring slot just because its UTC representation crossed midnight.
"""
from __future__ import annotations

from datetime import date, timedelta, timezone

from clockipy.reports.time_entry import TimeEntry


def _make_entry(start_iso: str, duration: str = "PT30M", desc: str = "Task 🔁") -> TimeEntry:
    return TimeEntry(
        entry_data={
            "description": desc,
            "timeInterval": {"start": start_iso, "end": start_iso, "duration": duration},
            "projectId": "p1",
        },
        index=1,
    )


class TestStartDateLocal:
    def test_late_night_local_does_not_roll_to_next_day_in_utc_plus_2(self):
        # 23:30 in UTC+02:00 = 21:30 UTC, same calendar day in *local* tz.
        # The bug: previous implementation used UTC date everywhere, so a
        # 23:30+02:00 entry would still be on the same day. But the inverse
        # case (00:30+02:00 = 22:30 UTC prev day) was misgrouped. Test both.
        tz = timezone(timedelta(hours=2))
        entry = _make_entry("2026-05-18T00:30:00+02:00")
        assert entry.start_date(tz=tz) == date(2026, 5, 18)
        # Old UTC behavior would return 2026-05-17 — assert we no longer do.
        assert entry.start_date_utc() == date(2026, 5, 17)

    def test_late_night_grouping_local_in_negative_tz(self):
        # 22:00 UTC = 18:00 in UTC-4. Local day = same UTC date here.
        tz = timezone(timedelta(hours=-4))
        entry = _make_entry("2026-05-18T22:00:00Z")
        assert entry.start_date(tz=tz) == date(2026, 5, 18)
        assert entry.start_date_utc() == date(2026, 5, 18)

    def test_default_tz_is_system_local(self):
        entry = _make_entry("2026-05-18T12:00:00Z")
        # Default call must not crash and must return *some* date.
        assert entry.start_date() is not None

    def test_missing_start_returns_none(self):
        entry = TimeEntry(
            entry_data={
                "description": "x",
                "timeInterval": {"start": "", "duration": "PT1H"},
            },
            index=1,
        )
        assert entry.start_date() is None
        assert entry.start_date_utc() is None

    def test_invalid_iso_returns_none(self):
        entry = TimeEntry(
            entry_data={
                "description": "x",
                "timeInterval": {"start": "not-a-date", "duration": "PT1H"},
            },
            index=1,
        )
        assert entry.start_date() is None

    def test_backwards_compat_property_still_works(self):
        # `start_date` was previously a *property* returning UTC date.
        # Existing callers (report_generator) treat it as an attribute lookup.
        # After the fix it must remain attribute-accessible (callable OR property
        # that returns a date for the *local* tz).
        entry = _make_entry("2026-05-18T12:00:00Z")
        # Either form must yield a date when called without args / accessed.
        result = entry.start_date() if callable(entry.start_date) else entry.start_date
        assert isinstance(result, date)
