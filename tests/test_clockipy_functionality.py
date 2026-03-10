import sys
import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock, mock_open
from datetime import datetime, date, timedelta
from io import StringIO
import json

# Add the parent directory to sys.path to import the clockipy package
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from clockipy.__main__ import date_interface, load_env_file, load_environment, main, resolve_user_id
from clockipy.utils.format_utils import parse_clockify_duration, parse_planned_from_name

class TestClockipyFunctionality(unittest.TestCase):
    """Test the complete functionality of the clockipy package."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Mock environment variables
        self.env_patcher = patch.dict('os.environ', {
            'CLOCKIFY_API_KEY': 'test_api_key',
            'CLOCKIFY_WORKSPACE_ID': 'test_workspace_id',
            'CLOCKIFY_USER_ID': 'test_user_id'
        })
        self.env_patcher.start()
        
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
        
        # Mock API responses
        self.mock_projects = [
            {"id": "project1", "name": "Project One"},
            {"id": "project2", "name": "Project Two"}
        ]
        
        self.mock_tags = [
            {"id": "tag1", "name": "Tag One"},
            {"id": "tag2", "name": "Tag Two"},
            {"id": "tag3", "name": "Tag Three"}
        ]
        
        self.mock_tasks = {
            "project1": [
                {"id": "task1", "name": "SubProject One"}
            ],
            "project2": [
                {"id": "task2", "name": "SubProject Two"}
            ]
        }
    
    def tearDown(self):
        """Tear down test fixtures."""
        self.env_patcher.stop()
    
    def test_parse_planned_from_name(self):
        """Test parsing planned duration from task names."""
        test_cases = [
            ("Task with 1 hour planned {p1:00}", 3600),
            ("Task with 1.5 hours planned {p1:30}", 5400),
            ("Task with 2 hours planned {p2:00}", 7200),
            ("Task with 45 minutes planned {p0:45}", 2700),
            ("Task with no planned time", 0),
            ("Task with invalid format {p1:}", 0),
            ("Task with invalid format {p:30}", 0),
            ("Task with invalid format {px:30}", 0)
        ]
        
        for task_name, expected in test_cases:
            with self.subTest(task_name=task_name):
                result = parse_planned_from_name(task_name)
                self.assertEqual(result, expected)
    
    def test_parse_clockify_duration(self):
        """Test parsing Clockify duration strings."""
        test_cases = [
            ("PT1H", 3600),
            ("PT30M", 1800),
            ("PT1H30M", 5400),
            ("PT1H30M15S", 5415),
            ("PT15S", 15),
            (None, 0),
            ("", 0),
            ("invalid", 0)
        ]
        
        for duration_str, expected in test_cases:
            with self.subTest(duration_str=duration_str):
                result = parse_clockify_duration(duration_str)
                self.assertEqual(result, expected)
    
    def _mock_get_env_var(self, key):
        """Mock implementation of get_env_var function."""
        env_vars = {
            'CLOCKIFY_API_KEY': 'test_api_key',
            'CLOCKIFY_WORKSPACE_ID': 'test_workspace_id',
            'CLOCKIFY_USER_ID': 'test_user_id'
        }
        return env_vars.get(key, '')

    @patch('clockipy.__main__.load_env_file')
    def test_load_environment_prefers_existing_environment(self, mock_load_env_file):
        """Existing process env should win over file loading."""
        load_environment()
        mock_load_env_file.assert_not_called()

    @patch.dict('os.environ', {}, clear=True)
    @patch('clockipy.__main__.candidate_env_files', return_value=['/tmp/rene.env', '/tmp/clockipy.env'])
    @patch('clockipy.__main__.os.path.exists')
    @patch('clockipy.__main__.load_env_file')
    def test_load_environment_uses_rene_env_fallback(self, mock_load_env_file, mock_exists, mock_candidate_files):
        """~/rene.env should be sufficient when the shell environment is empty."""
        mock_exists.side_effect = lambda path: path == '/tmp/rene.env'

        def fake_load_env_file(path):
            self.assertEqual(path, '/tmp/rene.env')
            os.environ['CLOCKIFY_API_KEY'] = 'test_api_key'
            os.environ['CLOCKIFY_WORKSPACE_ID'] = 'test_workspace_id'
            os.environ['CLOCKIFY_USER_ID'] = 'test_user_id'

        mock_load_env_file.side_effect = fake_load_env_file

        load_environment()

        mock_candidate_files.assert_called_once()
        mock_load_env_file.assert_called_once_with('/tmp/rene.env')

    @patch.dict('os.environ', {}, clear=True)
    def test_load_env_file_supports_export_prefix(self):
        """The loader should support both export-prefixed and plain env lines."""
        with tempfile.NamedTemporaryFile('w', delete=False) as handle:
            handle.write('export CLOCKIFY_API_KEY="test_api_key"\n')
            handle.write('CLOCKIFY_WORKSPACE_ID=test_workspace_id\n')
            handle.write('export CLOCKIFY_USER_ID="test_user_id"\n')
            temp_path = handle.name

        try:
            load_env_file(temp_path)
        finally:
            os.unlink(temp_path)

        self.assertEqual(os.environ['CLOCKIFY_API_KEY'], 'test_api_key')
        self.assertEqual(os.environ['CLOCKIFY_WORKSPACE_ID'], 'test_workspace_id')
        self.assertEqual(os.environ['CLOCKIFY_USER_ID'], 'test_user_id')

    @patch.dict('os.environ', {'CLOCKIFY_API_KEY': 'test_api_key', 'CLOCKIFY_WORKSPACE_ID': 'test_workspace_id'}, clear=True)
    @patch('clockipy.__main__.ClockifyClient.get_user_and_workspaces', return_value=({'id': 'derived_user_id'}, []))
    def test_resolve_user_id_from_api_when_missing(self, mock_get_user_and_workspaces):
        """CLOCKIFY_USER_ID should be derived from Clockify when omitted."""
        user_id = resolve_user_id('test_api_key', 'test_workspace_id')
        self.assertEqual(user_id, 'derived_user_id')
        mock_get_user_and_workspaces.assert_called_once()

    @patch.dict('os.environ', {}, clear=True)
    @patch('clockipy.__main__.candidate_env_files', return_value=['/tmp/rene.env', '/tmp/clockipy.env'])
    @patch('clockipy.__main__.os.path.exists', return_value=False)
    @patch('sys.stdout', new_callable=StringIO)
    def test_load_environment_exits_without_any_credentials(self, mock_stdout, mock_exists, mock_candidate_files):
        """A clear error should be raised when no env source is available."""
        with self.assertRaises(SystemExit):
            load_environment()

        output = mock_stdout.getvalue()
        self.assertIn('Missing Clockify credentials.', output)
        self.assertIn('Checked current environment, ~/rene.env, and clockipy.env.', output)
    
    @patch('clockipy.api.client.ClockifyClient.get_time_entries')
    @patch('clockipy.api.client.ClockifyClient.get_project_and_tag_mappings')
    @patch('clockipy.__main__.get_env_var')
    @patch('clockipy.__main__.load_environment')
    @patch('os.path.exists', return_value=True)
    @patch('sys.stdout', new_callable=StringIO)
    def test_date_interface_normal_mode(self, mock_stdout, mock_exists, mock_load_env, mock_get_env_var, 
                                       mock_get_mappings, mock_get_entries):
        """Test the date_interface function in normal mode."""
        # Set up mock functions
        mock_get_env_var.side_effect = self._mock_get_env_var
        mock_get_entries.return_value = self.mock_entries
        mock_get_mappings.return_value = (self.project_id_to_name, self.tag_id_to_name, self.task_map)
        
        # Call date_interface with test parameters
        with patch('clockipy.__main__.prompt_for_date', return_value='2023-01-01'):
            date_interface(
                start_str="2023-01-01",
                end_str="2023-01-01",
                test_mode=False,
                mode="normal"
            )
        
        # Check output
        output = mock_stdout.getvalue()
        
        # Check that all tables are present
        self.assertIn("### Time Entries", output)
        self.assertIn("### Time by Project", output)
        
        # Check that new columns are present
        self.assertIn("Meas>Plan%", output)
        self.assertIn("Meas<Plan%", output)
    
    @patch('clockipy.api.client.ClockifyClient.get_time_entries')
    @patch('clockipy.api.client.ClockifyClient.get_project_and_tag_mappings')
    @patch('clockipy.__main__.get_env_var')
    @patch('clockipy.__main__.load_environment')
    @patch('os.path.exists', return_value=True)
    @patch('sys.stdout', new_callable=StringIO)
    def test_date_interface_week_mode(self, mock_stdout, mock_exists, mock_load_env, mock_get_env_var, 
                                     mock_get_mappings, mock_get_entries):
        """Test the date_interface function in week mode."""
        # Set up mock functions
        mock_get_env_var.side_effect = self._mock_get_env_var
        mock_get_entries.return_value = self.mock_entries
        mock_get_mappings.return_value = (self.project_id_to_name, self.tag_id_to_name, self.task_map)
        
        # Call date_interface with test parameters
        date_interface(
            start_str="2023-01-01",
            end_str=None,
            test_mode=False,
            mode="week"
        )
        
        # Check output
        output = mock_stdout.getvalue()
        
        # Check that week mode text is present
        self.assertIn("📅 Week:", output)
        
        # Check that all tables are present
        self.assertIn("### Time by Project", output)
        
        # Check that new columns are present
        self.assertIn("Meas>Plan%", output)
        self.assertIn("Meas<Plan%", output)
    
    @patch('clockipy.api.client.ClockifyClient.get_time_entries')
    @patch('clockipy.api.client.ClockifyClient.get_project_and_tag_mappings')
    @patch('clockipy.__main__.get_env_var')
    @patch('clockipy.__main__.load_environment')
    @patch('os.path.exists', return_value=True)
    @patch('sys.stdout', new_callable=StringIO)
    def test_date_interface_month_mode(self, mock_stdout, mock_exists, mock_load_env, mock_get_env_var, 
                                      mock_get_mappings, mock_get_entries):
        """Test the date_interface function in month mode."""
        # Set up mock functions
        mock_get_env_var.side_effect = self._mock_get_env_var
        mock_get_entries.return_value = self.mock_entries
        mock_get_mappings.return_value = (self.project_id_to_name, self.tag_id_to_name, self.task_map)
        
        # Call date_interface with test parameters
        date_interface(
            start_str="2023-01-01",
            end_str=None,
            test_mode=False,
            mode="month"
        )
        
        # Check output
        output = mock_stdout.getvalue()
        
        # Check that all tables are present
        self.assertIn("### Time by Project", output)
        
        # Check that new columns are present
        self.assertIn("Meas>Plan%", output)
        self.assertIn("Meas<Plan%", output)
    
    @patch('clockipy.api.client.ClockifyClient.get_time_entries')
    @patch('clockipy.api.client.ClockifyClient.get_project_and_tag_mappings')
    @patch('clockipy.__main__.get_env_var')
    @patch('clockipy.__main__.load_environment')
    @patch('os.path.exists', return_value=True)
    @patch('sys.stdout', new_callable=StringIO)
    def test_date_interface_with_breakdown(self, mock_stdout, mock_exists, mock_load_env, mock_get_env_var, 
                                          mock_get_mappings, mock_get_entries):
        """Test the date_interface function with breakdown option."""
        # Set up mock functions
        mock_get_env_var.side_effect = self._mock_get_env_var
        mock_get_entries.return_value = self.mock_entries
        mock_get_mappings.return_value = (self.project_id_to_name, self.tag_id_to_name, self.task_map)
        
        # Call date_interface with test parameters
        date_interface(
            start_str="2023-01-01",
            end_str=None,
            test_mode=False,
            mode="month",
            breakdown=True
        )
        
        # Check output
        output = mock_stdout.getvalue()
        
        # Check that all tables are present
        self.assertIn("### Time by Project", output)
        
        # Check that new columns are present
        self.assertIn("Meas>Plan%", output)
        self.assertIn("Meas<Plan%", output)
    
    @patch('clockipy.api.client.ClockifyClient.get_time_entries')
    @patch('clockipy.api.client.ClockifyClient.get_project_and_tag_mappings')
    @patch('clockipy.__main__.get_env_var')
    @patch('clockipy.__main__.load_environment')
    @patch('os.path.exists', return_value=True)
    @patch('sys.stdout', new_callable=StringIO)
    def test_csv_export(self, mock_stdout, mock_exists, mock_load_env, mock_get_env_var, 
                       mock_get_mappings, mock_get_entries):
        """Test CSV export functionality."""
        # Set up mock functions
        mock_get_env_var.side_effect = self._mock_get_env_var
        mock_get_entries.return_value = self.mock_entries
        mock_get_mappings.return_value = (self.project_id_to_name, self.tag_id_to_name, self.task_map)
        
        # Call date_interface with test parameters
        with patch('clockipy.utils.file_utils.write_csv') as mock_write_csv:
            date_interface(
                start_str="2023-01-01",
                end_str="2023-01-01",
                test_mode=False,
                mode="normal",
                csv_prefix="test_export"
            )
            
            # Check that write_csv was called for each table
            self.assertGreaterEqual(mock_write_csv.call_count, 1)

if __name__ == '__main__':
    unittest.main() 
