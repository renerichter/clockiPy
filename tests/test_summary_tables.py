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


if __name__ == '__main__':
    unittest.main() 