import sys
import os
import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, date, timedelta
from io import StringIO
import json

# Add the parent directory to sys.path to import the clockipy package
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from clockipy.reports.time_entry import TimeEntry
from clockipy.reports.report_generator import ReportGenerator

class TestSummaryTables(unittest.TestCase):
    """Test the summary tables functionality with the new columns."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Mock time entries with planned durations
        self.mock_entries = [
            {
                "description": "Task 1 {p1:30}",  # 1h30m planned
                "timeInterval": {
                    "start": "2023-01-01T10:00:00Z",
                    "end": "2023-01-01T12:00:00Z",  # 2h actual (more than planned)
                    "duration": "PT2H"
                },
                "projectId": "project1",
                "tagIds": ["tag1", "tag2"]
            },
            {
                "description": "Task 2 {p2:00}",  # 2h planned
                "timeInterval": {
                    "start": "2023-01-01T13:00:00Z",
                    "end": "2023-01-01T14:30:00Z",  # 1h30m actual (less than planned)
                    "duration": "PT1H30M"
                },
                "projectId": "project1",
                "taskId": "task1",
                "tagIds": ["tag1"]
            },
            {
                "description": "Task 3 🎲",  # No planned time, spontaneous
                "timeInterval": {
                    "start": "2023-01-01T15:00:00Z",
                    "end": "2023-01-01T16:00:00Z",  # 1h actual
                    "duration": "PT1H"
                },
                "projectId": "project2",
                "tagIds": ["tag2"]
            },
            {
                "description": "Task 4 🗓️ {p0:45}",  # 45m planned, scheduled
                "timeInterval": {
                    "start": "2023-01-01T16:30:00Z",
                    "end": "2023-01-01T17:00:00Z",  # 30m actual (less than planned)
                    "duration": "PT30M"
                },
                "projectId": "project2",
                "taskId": "task2",
                "tagIds": ["tag3"]
            }
        ]
        
        # Mock project and tag data
        self.project_id_to_name = {
            "project1": "Project One",
            "project2": "Project Two"
        }
        
        self.tag_id_to_name = {
            "tag1": "Tag One",
            "tag2": "Tag Two",
            "tag3": "Tag Three"
        }
        
        self.task_map = {
            ("project1", "task1"): "SubProject One",
            ("project2", "task2"): "SubProject Two"
        }
        
        # Create TimeEntry objects
        self.time_entries = []
        for idx, entry in enumerate(self.mock_entries):
            project_id = entry.get("projectId")
            task_id = entry.get("taskId")
            project_name = self.project_id_to_name.get(project_id, "No project")
            task_name = self.task_map.get((project_id, task_id), "") if project_id and task_id else ""
            tag_ids = entry.get("tagIds") or []
            tag_names = [self.tag_id_to_name.get(tid, tid) for tid in tag_ids]
            
            time_entry = TimeEntry(entry, idx + 1, project_name, task_name, tag_names)
            self.time_entries.append(time_entry)
    
    @patch('sys.stdout', new_callable=StringIO)
    def test_subproject_table_has_plan_columns(self, mock_stdout):
        """Test that the SubProject table includes Meas<Plan and Meas>Plan columns."""
        # Create report generator
        report_generator = ReportGenerator(self.time_entries, "2023-01-01", "normal")
        
        # Generate report
        report = report_generator.generate_report(None, False)
        
        # Print report
        print(report)
        
        # Check if the output contains the new columns in the SubProject table
        output = mock_stdout.getvalue()
        self.assertIn("### Time by SubProject", output)
        self.assertIn("Meas<Plan%", output)
        self.assertIn("Meas>Plan%", output)
    
    @patch('sys.stdout', new_callable=StringIO)
    def test_project_table_has_plan_columns(self, mock_stdout):
        """Test that the Project table includes Meas<Plan and Meas>Plan columns."""
        # Create report generator
        report_generator = ReportGenerator(self.time_entries, "2023-01-01", "normal")
        
        # Generate report
        report = report_generator.generate_report(None, False)
        
        # Print report
        print(report)
        
        # Check if the output contains the new columns in the Project table
        output = mock_stdout.getvalue()
        self.assertIn("### Time by Project", output)
        self.assertIn("Meas<Plan%", output)
        self.assertIn("Meas>Plan%", output)
    
    @patch('sys.stdout', new_callable=StringIO)
    def test_tag_table_has_plan_columns(self, mock_stdout):
        """Test that the Tag table includes Meas<Plan and Meas>Plan columns."""
        # Create report generator
        report_generator = ReportGenerator(self.time_entries, "2023-01-01", "normal")
        
        # Generate report
        report = report_generator.generate_report(None, False)
        
        # Print report
        print(report)
        
        # Check if the output contains the new columns in the Tag table
        output = mock_stdout.getvalue()
        self.assertIn("### Time by Tag", output)
        self.assertIn("Meas<Plan%", output)
        self.assertIn("Meas>Plan%", output)
    
    @patch('sys.stdout', new_callable=StringIO)
    def test_spontaneousity_table_has_plan_columns(self, mock_stdout):
        """Test that the Spontaneousity table includes Meas<Plan and Meas>Plan columns."""
        # Create report generator
        report_generator = ReportGenerator(self.time_entries, "2023-01-01", "normal")
        
        # Generate report
        report = report_generator.generate_report(None, False)
        
        # Print report
        print(report)
        
        # Check if the output contains the new columns in the Spontaneousity table
        output = mock_stdout.getvalue()
        self.assertIn("### Spontaneousity", output)
        self.assertIn("Meas<Plan%", output)
        self.assertIn("Meas>Plan%", output)

class TestTimeDifferenceCalculations(unittest.TestCase):
    """Test the time difference calculation logic (Meas>Plan, Meas<Plan, Abs)."""
    
    def _create_entry(self, description, duration_str, project_id="p1"):
        """Helper to create a mock entry dict."""
        return {
            "description": description,
            "timeInterval": {
                "start": "2023-01-01T10:00:00Z",
                "end": "2023-01-01T11:00:00Z",
                "duration": duration_str
            },
            "projectId": project_id,
            "tagIds": []
        }
    
    def _create_time_entry(self, entry_dict, idx=1):
        """Helper to create TimeEntry from dict."""
        return TimeEntry(entry_dict, idx, "Test Project", "", [])
    
    def test_measured_equals_planned(self):
        """When measured == planned, all diff totals should be zero."""
        entry = self._create_entry("Task {p1:00}", "PT1H")
        time_entry = self._create_time_entry(entry)
        
        report_gen = ReportGenerator([time_entry], "2023-01-01", "normal")
        
        data = report_gen.task_planned_measured["Task {p1:00}"]
        self.assertEqual(data["planned"], 3600)
        self.assertEqual(data["measured"], 3600)
    
    def test_measured_greater_than_planned(self):
        """When measured > planned, should contribute to Meas>Plan."""
        entry = self._create_entry("Task {p0:30}", "PT1H")
        time_entry = self._create_time_entry(entry)
        
        report_gen = ReportGenerator([time_entry], "2023-01-01", "normal")
        
        data = report_gen.task_planned_measured["Task {p0:30}"]
        self.assertEqual(data["planned"], 1800)
        self.assertEqual(data["measured"], 3600)
        diff = data["measured"] - data["planned"]
        self.assertEqual(diff, 1800)
    
    def test_measured_less_than_planned(self):
        """When measured < planned, should contribute to Meas<Plan."""
        entry = self._create_entry("Task {p2:00}", "PT1H")
        time_entry = self._create_time_entry(entry)
        
        report_gen = ReportGenerator([time_entry], "2023-01-01", "normal")
        
        data = report_gen.task_planned_measured["Task {p2:00}"]
        self.assertEqual(data["planned"], 7200)
        self.assertEqual(data["measured"], 3600)
        diff = data["measured"] - data["planned"]
        self.assertEqual(diff, -3600)
    
    def test_no_planned_time_excluded_from_diff(self):
        """Entries with no planned time should not affect diff totals."""
        entries = [
            self._create_entry("Task no plan", "PT1H"),
            self._create_entry("Task {p0:30}", "PT1H"),
        ]
        time_entries = [self._create_time_entry(e, i+1) for i, e in enumerate(entries)]
        
        report_gen = ReportGenerator(time_entries, "2023-01-01", "normal")
        
        no_plan_data = report_gen.task_planned_measured["Task no plan"]
        self.assertEqual(no_plan_data["planned"], 0)
        self.assertEqual(no_plan_data["measured"], 3600)
        
        with_plan_data = report_gen.task_planned_measured["Task {p0:30}"]
        self.assertEqual(with_plan_data["planned"], 1800)
    
    def test_mixed_signs_totals(self):
        """Test multiple entries with mixed over/under plan."""
        entries = [
            self._create_entry("Over {p0:30}", "PT1H"),
            self._create_entry("Under {p2:00}", "PT1H"),
            self._create_entry("Exact {p1:00}", "PT1H"),
            self._create_entry("No plan", "PT1H"),
        ]
        time_entries = [self._create_time_entry(e, i+1) for i, e in enumerate(entries)]
        
        report_gen = ReportGenerator(time_entries, "2023-01-01", "normal")
        
        over_data = report_gen.task_planned_measured["Over {p0:30}"]
        self.assertEqual(over_data["measured"] - over_data["planned"], 1800)
        
        under_data = report_gen.task_planned_measured["Under {p2:00}"]
        self.assertEqual(under_data["measured"] - under_data["planned"], -3600)
        
        exact_data = report_gen.task_planned_measured["Exact {p1:00}"]
        self.assertEqual(exact_data["measured"] - exact_data["planned"], 0)
    
    def test_zero_duration_entry(self):
        """Test entry with zero actual duration."""
        entry = self._create_entry("Zero dur {p1:00}", "PT0S")
        time_entry = self._create_time_entry(entry)
        
        report_gen = ReportGenerator([time_entry], "2023-01-01", "normal")
        
        data = report_gen.task_planned_measured["Zero dur {p1:00}"]
        self.assertEqual(data["measured"], 0)
        self.assertEqual(data["planned"], 3600)


class TestYearMode(unittest.TestCase):
    """Test the year mode functionality."""
    
    def test_year_mode_report_generation(self):
        """Test that year mode generates reports correctly."""
        entry = {
            "description": "Year task {p1:00}",
            "timeInterval": {
                "start": "2023-06-15T10:00:00Z",
                "end": "2023-06-15T12:00:00Z",
                "duration": "PT2H"
            },
            "projectId": "p1",
            "tagIds": []
        }
        time_entry = TimeEntry(entry, 1, "Test Project", "", [])
        
        report_gen = ReportGenerator([time_entry], "2023-01-01 to 2023-12-31", "year")
        report = report_gen.generate_report(None, day_table=None)
        
        self.assertIn("%/Year", report)
        self.assertIn("### Totals", report)


class TestRecurringTaskHandling(unittest.TestCase):
    """Test handling of recurring tasks across multiple days."""

    def _create_entry(self, description, start, duration_str, project_id="p1", tag_ids=None):
        return {
            "description": description,
            "timeInterval": {
                "start": start,
                "end": start,
                "duration": duration_str
            },
            "projectId": project_id,
            "tagIds": tag_ids or []
        }

    def _create_time_entries(self, entries, tag_map=None):
        tag_map = tag_map or {}
        result = []
        for idx, entry in enumerate(entries):
            tag_ids = entry.get("tagIds") or []
            tag_names = [tag_map.get(tid, tid) for tid in tag_ids]
            result.append(TimeEntry(entry, idx + 1, "Test Project", "", tag_names))
        return result

    def test_recurring_tasks_split_by_day_for_deviations(self):
        entries = [
            self._create_entry("Daily Task 🔁 {p1:00}", "2023-01-01T10:00:00Z", "PT1H30M"),
            self._create_entry("Daily Task 🔁 {p1:00}", "2023-01-02T10:00:00Z", "PT30M"),
        ]
        time_entries = self._create_time_entries(entries)

        report_gen = ReportGenerator(time_entries, "2023-01-01 to 2023-01-02", "week")

        self.assertEqual(report_gen.plan_deviation_totals["over"], 1800)
        self.assertEqual(report_gen.plan_deviation_totals["under"], 1800)
        self.assertEqual(report_gen.plan_deviation_totals["abs"], 3600)

    def test_non_recurring_tasks_aggregate_across_days(self):
        entries = [
            self._create_entry("Task {p1:00}", "2023-01-01T10:00:00Z", "PT1H30M"),
            self._create_entry("Task {p1:00}", "2023-01-02T10:00:00Z", "PT30M"),
        ]
        time_entries = self._create_time_entries(entries)

        report_gen = ReportGenerator(time_entries, "2023-01-01 to 2023-01-02", "week")

        self.assertEqual(report_gen.plan_deviation_totals["over"], 0)
        self.assertEqual(report_gen.plan_deviation_totals["under"], 0)
        self.assertEqual(report_gen.plan_deviation_totals["abs"], 0)

    def test_recurring_multiple_entries_same_day_aggregate_within_day(self):
        """Multiple recurring entries on the same day should aggregate within that day."""
        entries = [
            self._create_entry("Daily 🔁 {p0:30}", "2023-01-01T10:00:00Z", "PT45M"),
            self._create_entry("Daily 🔁 {p0:30}", "2023-01-01T14:00:00Z", "PT45M"),
        ]
        time_entries = self._create_time_entries(entries)

        report_gen = ReportGenerator(time_entries, "2023-01-01", "normal")

        self.assertEqual(len(report_gen.occurrences), 1)
        self.assertEqual(report_gen.plan_deviation_totals["over"], 1800)
        self.assertEqual(report_gen.plan_deviation_totals["under"], 0)

    def test_recurring_task_missing_start_time_groups_together(self):
        """Recurring tasks with missing start time should gracefully degrade."""
        entries = [
            self._create_entry("Task 🔁 {p1:00}", "", "PT1H30M"),
            self._create_entry("Task 🔁 {p1:00}", "", "PT30M"),
        ]
        time_entries = self._create_time_entries(entries)

        report_gen = ReportGenerator(time_entries, "unknown", "week")

        self.assertEqual(len(report_gen.occurrences), 1)
        occ = report_gen.occurrences[0]
        self.assertIsNone(occ["date"])
        self.assertEqual(occ["planned"], 7200)
        self.assertEqual(occ["measured"], 7200)

    def test_mixed_recurring_and_non_recurring_tasks(self):
        """Non-recurring and recurring tasks should be handled independently."""
        entries = [
            self._create_entry("Non-recurring {p1:00}", "2023-01-01T10:00:00Z", "PT1H30M"),
            self._create_entry("Non-recurring {p1:00}", "2023-01-02T10:00:00Z", "PT30M"),
            self._create_entry("Recurring 🔁 {p1:00}", "2023-01-01T10:00:00Z", "PT1H30M"),
            self._create_entry("Recurring 🔁 {p1:00}", "2023-01-02T10:00:00Z", "PT30M"),
        ]
        time_entries = self._create_time_entries(entries)

        report_gen = ReportGenerator(time_entries, "2023-01-01 to 2023-01-02", "week")

        self.assertEqual(len(report_gen.occurrences), 3)
        self.assertEqual(report_gen.plan_deviation_totals["over"], 1800)
        self.assertEqual(report_gen.plan_deviation_totals["under"], 1800)


class TestMultiTagProportionalAllocation(unittest.TestCase):
    """Test that tag deviations are allocated proportionally by entry duration."""

    def _create_entry(self, description, start, duration_str, project_id="p1", tag_ids=None):
        return {
            "description": description,
            "timeInterval": {
                "start": start,
                "end": start,
                "duration": duration_str
            },
            "projectId": project_id,
            "tagIds": tag_ids or []
        }

    def test_tag_deviation_proportional_allocation(self):
        """Tag deviations should be allocated proportionally by entry duration within occurrence."""
        entries = [
            self._create_entry("Task {p1:00}", "2023-01-01T10:00:00Z", "PT2H30M", tag_ids=["tagA"]),
            self._create_entry("Task {p1:00}", "2023-01-01T14:00:00Z", "PT30M", tag_ids=["tagB"]),
        ]
        tag_map = {"tagA": "Tag A", "tagB": "Tag B"}
        time_entries = []
        for idx, entry in enumerate(entries):
            tag_ids = entry.get("tagIds") or []
            tag_names = [tag_map.get(tid, tid) for tid in tag_ids]
            time_entries.append(TimeEntry(entry, idx + 1, "Test Project", "", tag_names))

        report_gen = ReportGenerator(time_entries, "2023-01-01", "normal")

        self.assertEqual(report_gen.plan_deviation_totals["over"], 3600)

    def test_entry_with_no_tags_excluded_from_tag_allocation(self):
        """Entries with no tags should not affect tag table."""
        entry = {
            "description": "NoTag {p0:30}",
            "timeInterval": {
                "start": "2023-01-01T10:00:00Z",
                "end": "2023-01-01T11:00:00Z",
                "duration": "PT1H"
            },
            "projectId": "p1",
            "tagIds": []
        }
        time_entry = TimeEntry(entry, 1, "Test Project", "", [])

        report_gen = ReportGenerator([time_entry], "2023-01-01", "normal")

        self.assertEqual(len(report_gen.tag_durations), 0)
        self.assertEqual(report_gen.plan_deviation_totals["over"], 1800)


class TestOccurrenceGrouping(unittest.TestCase):
    """Test that occurrences are correctly grouped."""

    def _create_entry(self, description, start, duration_str, project="Proj", task=""):
        return {
            "description": description,
            "timeInterval": {
                "start": start,
                "end": start,
                "duration": duration_str
            },
            "projectId": "p1",
            "taskId": "t1" if task else None,
            "tagIds": []
        }

    def _create_time_entry(self, entry_dict, idx=1, project_name="Test Project", task_name=""):
        return TimeEntry(entry_dict, idx, project_name, task_name, [])

    def test_occurrences_count_matches_expected(self):
        """Verify occurrence count for mixed recurring and non-recurring."""
        entries = [
            self._create_entry("A 🔁 {p1:00}", "2023-01-01T10:00:00Z", "PT1H"),
            self._create_entry("A 🔁 {p1:00}", "2023-01-02T10:00:00Z", "PT1H"),
            self._create_entry("A 🔁 {p1:00}", "2023-01-03T10:00:00Z", "PT1H"),
            self._create_entry("B {p1:00}", "2023-01-01T10:00:00Z", "PT1H"),
            self._create_entry("B {p1:00}", "2023-01-02T10:00:00Z", "PT1H"),
        ]
        time_entries = [self._create_time_entry(e, i+1) for i, e in enumerate(entries)]

        report_gen = ReportGenerator(time_entries, "2023-01-01 to 2023-01-03", "week")

        self.assertEqual(len(report_gen.occurrences), 4)

    def test_project_table_uses_occurrences_for_deviations(self):
        """Project table deviations should come from occurrences, not entries."""
        entries = [
            self._create_entry("Task 🔁 {p1:00}", "2023-01-01T10:00:00Z", "PT1H30M"),
            self._create_entry("Task 🔁 {p1:00}", "2023-01-02T10:00:00Z", "PT30M"),
        ]
        time_entries = [self._create_time_entry(e, i+1) for i, e in enumerate(entries)]

        report_gen = ReportGenerator(time_entries, "2023-01-01 to 2023-01-02", "week")
        report = report_gen.generate_report(None, False)

        self.assertIn("Test Project", report)
        self.assertIn("Meas>Plan%", report)
        self.assertIn("Meas<Plan%", report)


if __name__ == '__main__':
    unittest.main()
