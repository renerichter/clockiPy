"""Unit tests for report output formatting and semantic correctness.

Covers: day_str format, column headers, totals table net deviation,
spontaneity denominator, and section heading format.
"""
from __future__ import annotations

import unittest
from datetime import date

from clockipy.reports.report_generator import ReportGenerator
from clockipy.reports.time_entry import TimeEntry
from clockipy.utils.date_utils import day_str

# ---- day_str ---------------------------------------------------------------


class TestDayStr(unittest.TestCase):
    """Verify day_str output format: (Xxx) YYYY-MM-DD."""

    def test_format_has_space_between_paren_and_date(self):
        d = date(2026, 4, 27)  # Monday
        result = day_str(d)
        self.assertIn(") ", result, "Missing space after closing paren")

    def test_abbreviation_is_three_chars(self):
        # Check every weekday
        for offset in range(7):
            d = date(2026, 4, 27) + __import__("datetime").timedelta(days=offset)
            result = day_str(d)
            abbr = result.split(")")[0][1:]  # extract between ( and )
            self.assertEqual(len(abbr), 3, f"Expected 3-char abbr, got '{abbr}' for {d}")

    def test_monday(self):
        self.assertEqual(day_str(date(2026, 4, 27)), "(Mon) 2026-04-27")

    def test_tuesday(self):
        self.assertEqual(day_str(date(2026, 4, 28)), "(Tue) 2026-04-28")

    def test_wednesday(self):
        self.assertEqual(day_str(date(2026, 4, 29)), "(Wed) 2026-04-29")

    def test_thursday(self):
        self.assertEqual(day_str(date(2026, 4, 30)), "(Thu) 2026-04-30")

    def test_friday(self):
        self.assertEqual(day_str(date(2026, 5, 1)), "(Fri) 2026-05-01")

    def test_saturday(self):
        self.assertEqual(day_str(date(2026, 5, 2)), "(Sat) 2026-05-02")

    def test_sunday(self):
        self.assertEqual(day_str(date(2026, 5, 3)), "(Sun) 2026-05-03")


# ---- Helpers ---------------------------------------------------------------


def _make_entry(description, duration_str, project_id="p1", tag_ids=None, start="2023-01-01T10:00:00Z"):
    return {
        "description": description,
        "timeInterval": {
            "start": start,
            "end": start,
            "duration": duration_str,
        },
        "projectId": project_id,
        "tagIds": tag_ids or [],
    }


def _make_time_entry(raw, idx=1, project_name="Proj", task_name="", tag_names=None):
    return TimeEntry(raw, idx, project_name, task_name, tag_names or [])


# ---- Column headers --------------------------------------------------------


class TestColumnHeaders(unittest.TestCase):
    """Verify renamed column headers appear in reports."""

    def setUp(self):
        raw = _make_entry("Work {p1:00}", "PT1H30M")
        self.te = _make_time_entry(raw)
        self.rg = ReportGenerator([self.te], "2023-01-01 to 2023-01-07", "week")
        self.report = self.rg.generate_report(None, day_table=None)

    def test_over_percent_header(self):
        self.assertIn("Over %", self.report)

    def test_under_percent_header(self):
        self.assertIn("Under %", self.report)

    def test_old_headers_absent(self):
        self.assertNotIn("Meas>Plan%", self.report)
        self.assertNotIn("Meas<Plan%", self.report)


# ---- Section headings have no trailing colon -------------------------------


class TestHeadingFormat(unittest.TestCase):
    """Section headings must NOT end with a colon."""

    def setUp(self):
        raw = _make_entry("Work {p1:00}", "PT2H", tag_ids=["t1"])
        te = _make_time_entry(raw, tag_names=["Tag A"])
        self.report = ReportGenerator([te], "2023-01-01", "normal").generate_report(None, False)

    def test_no_trailing_colon_on_project_heading(self):
        for line in self.report.splitlines():
            if line.startswith("### "):
                self.assertFalse(
                    line.rstrip().endswith(":"),
                    f"Heading has trailing colon: {line!r}",
                )


# ---- Spontaneity heading spelling ------------------------------------------


class TestSpontaneitySpelling(unittest.TestCase):
    """Verify correct spelling of 'Spontaneity' in output."""

    def setUp(self):
        raw1 = _make_entry("Planned 🗓️ {p1:00}", "PT1H")
        raw2 = _make_entry("Ad-hoc 🎲", "PT0H30M")
        te1 = _make_time_entry(raw1)
        te2 = _make_time_entry(raw2)
        self.report = ReportGenerator([te1, te2], "2023-01-01", "normal").generate_report(None, False)

    def test_correct_spelling(self):
        self.assertIn("### Spontaneity", self.report)

    def test_old_misspelling_absent(self):
        self.assertNotIn("Spontaneousity", self.report)


# ---- Spontaneity uses total_duration as denominator ------------------------


class TestSpontaneityDenominator(unittest.TestCase):
    """Spontaneity %/Week must use total_duration, not spont_total."""

    def test_percent_relative_to_total(self):
        # 1h scheduled + 1h spontaneous + 1h unclassified (no 🗓️/🎲)
        raw_sched = _make_entry("Sched 🗓️ {p1:00}", "PT1H")
        raw_spont = _make_entry("Spont 🎲", "PT1H", start="2023-01-01T11:00:00Z")
        raw_other = _make_entry("Other work", "PT1H", start="2023-01-01T12:00:00Z")

        entries = [
            _make_time_entry(raw_sched, 1),
            _make_time_entry(raw_spont, 2),
            _make_time_entry(raw_other, 3),
        ]
        rg = ReportGenerator(entries, "2023-01-01", "normal")
        report = rg.generate_report(None, False)

        # With total_duration as denominator (3h), each 1h = 33%
        # With spont_total (2h), each 1h = 50%
        # If we see "33" it's using total_duration (correct).
        self.assertIn("33", report)


# ---- Totals table ----------------------------------------------------------


class TestTotalsTable(unittest.TestCase):
    """Verify totals table semantics: ΣPlanned row, net deviation, renamed rows."""

    def test_sigma_planned_row_present(self):
        """ΣPlanned row should appear when entries have planned time."""
        raw = _make_entry("Task {p2:00}", "PT1H30M")
        te = _make_time_entry(raw)
        rg = ReportGenerator([te], "2023-01-01", "normal")
        report = rg.generate_report(None, False)
        self.assertIn("ΣPlanned", report)

    def test_sigma_planned_absent_when_no_plan(self):
        """ΣPlanned row should NOT appear when no entries have planned time."""
        raw = _make_entry("No plan task", "PT1H")
        te = _make_time_entry(raw)
        rg = ReportGenerator([te], "2023-01-01", "normal")
        report = rg.generate_report(None, False)
        self.assertNotIn("ΣPlanned", report)

    def test_net_deviation_positive_when_over(self):
        """ΣDuration shows positive net % when over plan."""
        raw = _make_entry("Over {p0:30}", "PT1H")
        te = _make_time_entry(raw)
        rg = ReportGenerator([te], "2023-01-01", "normal")
        report = rg.generate_report(None, False)
        # 1h measured - 0.5h planned = +0.5h. Net % = +30min/60min = +50%
        self.assertIn("+50%", report)

    def test_net_deviation_negative_when_under(self):
        """ΣDuration shows negative net % when under plan."""
        raw = _make_entry("Under {p2:00}", "PT1H")
        te = _make_time_entry(raw)
        rg = ReportGenerator([te], "2023-01-01", "normal")
        report = rg.generate_report(None, False)
        # 1h measured - 2h planned = -1h. Net % = -3600/3600 = -100%
        # But the code computes (over - under)/total_duration:
        #   over = 0, under = 3600 → net = -3600. -3600/3600 = -100%
        self.assertIn("-100%", report)

    def test_net_deviation_zero_when_exact(self):
        """ΣDuration shows +0% when plan matches measured exactly."""
        raw = _make_entry("Exact {p1:00}", "PT1H")
        te = _make_time_entry(raw)
        rg = ReportGenerator([te], "2023-01-01", "normal")
        report = rg.generate_report(None, False)
        self.assertIn("+0%", report)

    def test_over_plan_total_row_renamed(self):
        raw = _make_entry("Over {p0:30}", "PT1H")
        te = _make_time_entry(raw)
        report = ReportGenerator([te], "2023-01-01", "normal").generate_report(None, False)
        self.assertIn("Over Plan Total", report)
        self.assertNotIn("Meas>Plan Total", report)

    def test_under_plan_total_row_renamed(self):
        raw = _make_entry("Under {p2:00}", "PT1H")
        te = _make_time_entry(raw)
        report = ReportGenerator([te], "2023-01-01", "normal").generate_report(None, False)
        self.assertIn("Under Plan Total", report)
        self.assertNotIn("Meas<Plan Total", report)

    def test_abs_delta_row_renamed(self):
        raw = _make_entry("Over {p0:30}", "PT1H")
        te = _make_time_entry(raw)
        report = ReportGenerator([te], "2023-01-01", "normal").generate_report(None, False)
        self.assertIn("Abs(Δ) Total", report)
        self.assertNotIn("Abs(Dur-Plan) Total", report)

    def test_hardcoded_zero_percent_absent(self):
        """The old hardcoded '0%' on ΣDuration must not appear."""
        # Use an entry that definitely has non-zero deviation
        raw = _make_entry("Over {p0:30}", "PT1H")
        te = _make_time_entry(raw)
        rg = ReportGenerator([te], "2023-01-01", "normal")
        report = rg.generate_report(None, False)
        # ΣDuration row should show +50%, not 0%
        lines = [line for line in report.splitlines() if "ΣDuration" in line]
        self.assertTrue(len(lines) >= 1)
        self.assertNotIn("| 0%", lines[0])

    def test_total_planned_tracks_sum(self):
        """total_planned attribute should sum all planned_sec from entries."""
        raw1 = _make_entry("A {p1:00}", "PT1H")
        raw2 = _make_entry("B {p0:30}", "PT0H45M", start="2023-01-01T12:00:00Z")
        raw3 = _make_entry("C no plan", "PT2H", start="2023-01-01T14:00:00Z")
        entries = [
            _make_time_entry(raw1, 1),
            _make_time_entry(raw2, 2),
            _make_time_entry(raw3, 3),
        ]
        rg = ReportGenerator(entries, "2023-01-01", "normal")
        # A: 3600s + B: 1800s + C: 0s = 5400s
        self.assertEqual(rg.total_planned, 5400)


# ---- Percent header for normal mode ----------------------------------------


class TestPercentHeaderNormalMode(unittest.TestCase):
    """Normal mode should use %/Total (not %/Day) regardless of range."""

    def test_normal_mode_uses_percent_total(self):
        raw = _make_entry("Work {p1:00}", "PT2H")
        te = _make_time_entry(raw)
        rg = ReportGenerator([te], "2023-01-01 to 2023-01-05", "normal")
        report = rg.generate_report(None, False)
        self.assertIn("%/Total", report)
        self.assertNotIn("%/Day", report)

    def test_week_mode_uses_percent_week(self):
        raw = _make_entry("Work {p1:00}", "PT2H")
        te = _make_time_entry(raw)
        rg = ReportGenerator([te], "range", "week")
        report = rg.generate_report(None, day_table=None)
        self.assertIn("%/Week", report)


# ---- Display description stripping -----------------------------------------


class TestDisplayDescription(unittest.TestCase):
    """Task column should strip {pH:MM} and {P:xxx} metadata."""

    def test_strips_planned_marker(self):
        raw = _make_entry("Fix bug {p1:30} in prod", "PT1H")
        te = _make_time_entry(raw)
        self.assertEqual(te.display_description, "Fix bug in prod")

    def test_strips_project_tag(self):
        raw = _make_entry("⭐️--🗓️{p0:45}{P:EnC} REBO-30071: push", "PT1H")
        te = _make_time_entry(raw)
        self.assertNotIn("{P:EnC}", te.display_description)
        self.assertNotIn("{p0:45}", te.display_description)
        self.assertIn("REBO-30071: push", te.display_description)

    def test_strips_meeting_tag(self):
        raw = _make_entry("--🗓️{p0:15}{M:Cai} TechUp: planning", "PT1H")
        te = _make_time_entry(raw)
        self.assertNotIn("{M:Cai}", te.display_description)
        self.assertNotIn("{p0:15}", te.display_description)
        self.assertIn("TechUp: planning", te.display_description)

    def test_strips_bare_category_tag(self):
        raw = _make_entry("-🔁-🗓️{p1:15}{Sport} back training", "PT1H")
        te = _make_time_entry(raw)
        self.assertNotIn("{Sport}", te.display_description)
        self.assertIn("back training", te.display_description)

    def test_preserves_emoji_markers(self):
        raw = _make_entry("⭐️--🗓️{p0:45}{P:EnC} task desc", "PT1H")
        te = _make_time_entry(raw)
        self.assertIn("⭐️", te.display_description)
        self.assertIn("🗓️", te.display_description)

    def test_no_double_spaces_after_strip(self):
        raw = _make_entry("prefix {p1:00}{P:Foo} suffix", "PT1H")
        te = _make_time_entry(raw)
        self.assertNotIn("  ", te.display_description)

    def test_to_row_uses_display_description(self):
        raw = _make_entry("Task {p1:00}{P:X} actual name", "PT1H")
        te = _make_time_entry(raw)
        row = te.to_row(3600)
        # row[1] is the task/description column
        self.assertNotIn("{p1:00}", row[1])
        self.assertNotIn("{P:X}", row[1])
        self.assertIn("actual name", row[1])


# ---- Working days + avg/day in Totals -------------------------------------


class TestWorkingDaysInTotals(unittest.TestCase):
    """Multi-day reports should show Working Days and Avg/Day."""

    def test_multi_day_shows_working_days(self):
        raw1 = _make_entry("A", "PT4H", start="2023-01-01T10:00:00Z")
        raw2 = _make_entry("B", "PT4H", start="2023-01-02T10:00:00Z")
        raw3 = _make_entry("C", "PT4H", start="2023-01-03T10:00:00Z")
        entries = [
            _make_time_entry(raw1, 1),
            _make_time_entry(raw2, 2),
            _make_time_entry(raw3, 3),
        ]
        rg = ReportGenerator(entries, "2023-01-01 to 2023-01-03", "normal")
        report = rg.generate_report(None, False)
        self.assertIn("Working Days", report)
        self.assertIn("3", report)  # 3 distinct days
        self.assertIn("Avg/Day", report)
        self.assertIn("04:00", report)  # 12h / 3 days = 4h

    def test_single_day_no_working_days_row(self):
        raw = _make_entry("A", "PT8H", start="2023-01-01T10:00:00Z")
        te = _make_time_entry(raw)
        rg = ReportGenerator([te], "2023-01-01", "normal")
        report = rg.generate_report(None, False)
        self.assertNotIn("Working Days", report)
        self.assertNotIn("Avg/Day", report)


if __name__ == "__main__":
    unittest.main()
