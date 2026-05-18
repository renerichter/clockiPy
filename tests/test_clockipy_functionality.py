"""Functional tests for clockiPy public surface.

After the P2 refactor, env/credential helpers live in ``clockipy.env`` and
the orchestrator lives in ``clockipy.orchestrator``. The backwards-compat
shim in ``clockipy.__main__`` re-exports the public names but tests that
need to *patch* internals must target the canonical module path.
"""
import os
import sys
import tempfile
import unittest
from io import StringIO
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from clockipy.env import (
    load_env_file,
    load_environment,
    resolve_user_id,
)
from clockipy.orchestrator import date_interface
from clockipy.utils.format_utils import parse_clockify_duration, parse_planned_from_name


class TestClockipyFunctionality(unittest.TestCase):
    def setUp(self):
        self.env_patcher = patch.dict('os.environ', {
            'CLOCKIFY_API_KEY': 'test_api_key',
            'CLOCKIFY_WORKSPACE_ID': 'test_workspace_id',
            'CLOCKIFY_USER_ID': 'test_user_id',
        })
        self.env_patcher.start()

        self.mock_entries = [
            {
                "description": "Task 1 {p1:30}",
                "timeInterval": {"start": "2023-01-01T10:00:00Z",
                                 "end": "2023-01-01T12:00:00Z", "duration": "PT2H"},
                "projectId": "project1", "tagIds": ["tag1", "tag2"],
            },
            {
                "description": "Task 2 {p2:00}",
                "timeInterval": {"start": "2023-01-01T13:00:00Z",
                                 "end": "2023-01-01T14:30:00Z", "duration": "PT1H30M"},
                "projectId": "project1", "taskId": "task1", "tagIds": ["tag1"],
            },
            {
                "description": "Task 3 🎲",
                "timeInterval": {"start": "2023-01-01T15:00:00Z",
                                 "end": "2023-01-01T16:00:00Z", "duration": "PT1H"},
                "projectId": "project2", "tagIds": ["tag2"],
            },
            {
                "description": "Task 4 🗓️ {p0:45}",
                "timeInterval": {"start": "2023-01-01T16:30:00Z",
                                 "end": "2023-01-01T17:00:00Z", "duration": "PT30M"},
                "projectId": "project2", "taskId": "task2", "tagIds": ["tag3"],
            },
        ]
        self.project_id_to_name = {"project1": "Project One", "project2": "Project Two"}
        self.tag_id_to_name = {"tag1": "Tag One", "tag2": "Tag Two", "tag3": "Tag Three"}
        self.task_map = {("project1", "task1"): "SubProject One",
                         ("project2", "task2"): "SubProject Two"}

    def tearDown(self):
        self.env_patcher.stop()

    # ---- parsing -----------------------------------------------------------

    def test_parse_planned_from_name(self):
        for task_name, expected in [
            ("Task with 1 hour planned {p1:00}", 3600),
            ("Task with 1.5 hours planned {p1:30}", 5400),
            ("Task with 2 hours planned {p2:00}", 7200),
            ("Task with 45 minutes planned {p0:45}", 2700),
            ("Task with no planned time", 0),
            ("Task with invalid format {p1:}", 0),
            ("Task with invalid format {p:30}", 0),
            ("Task with invalid format {px:30}", 0),
        ]:
            with self.subTest(task_name=task_name):
                self.assertEqual(parse_planned_from_name(task_name), expected)

    def test_parse_clockify_duration(self):
        for duration_str, expected in [
            ("PT1H", 3600), ("PT30M", 1800), ("PT1H30M", 5400),
            ("PT1H30M15S", 5415), ("PT15S", 15),
            (None, 0), ("", 0), ("invalid", 0),
        ]:
            with self.subTest(duration_str=duration_str):
                self.assertEqual(parse_clockify_duration(duration_str), expected)

    # ---- environment loading ----------------------------------------------

    @patch('clockipy.env.load_env_file')
    def test_load_environment_prefers_existing_environment(self, mock_load_env_file):
        load_environment()
        mock_load_env_file.assert_not_called()

    @patch.dict('os.environ', {}, clear=True)
    @patch('clockipy.env.candidate_env_files',
           return_value=['/tmp/rene.env', '/tmp/clockipy.env'])
    @patch('clockipy.env.os.path.exists')
    @patch('clockipy.env.load_env_file')
    def test_load_environment_uses_rene_env_fallback(
        self, mock_load_env_file, mock_exists, mock_candidate_files,
    ):
        mock_exists.side_effect = lambda p: p == '/tmp/rene.env'

        def fake(path):
            self.assertEqual(path, '/tmp/rene.env')
            os.environ['CLOCKIFY_API_KEY'] = 'test_api_key'
            os.environ['CLOCKIFY_WORKSPACE_ID'] = 'test_workspace_id'
            os.environ['CLOCKIFY_USER_ID'] = 'test_user_id'

        mock_load_env_file.side_effect = fake
        load_environment()
        mock_candidate_files.assert_called_once()
        mock_load_env_file.assert_called_once_with('/tmp/rene.env')

    @patch.dict('os.environ', {}, clear=True)
    def test_load_env_file_supports_export_prefix(self):
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

    @patch.dict('os.environ',
                {'CLOCKIFY_API_KEY': 'test_api_key',
                 'CLOCKIFY_WORKSPACE_ID': 'test_workspace_id'}, clear=True)
    @patch('clockipy.env.ClockifyClient.get_user_and_workspaces',
           return_value=({'id': 'derived_user_id'}, []))
    def test_resolve_user_id_from_api_when_missing(self, mock_get):
        self.assertEqual(resolve_user_id('test_api_key', 'test_workspace_id'),
                         'derived_user_id')
        mock_get.assert_called_once()

    @patch.dict('os.environ', {}, clear=True)
    @patch('clockipy.env.candidate_env_files',
           return_value=['/tmp/rene.env', '/tmp/clockipy.env'])
    @patch('clockipy.env.os.path.exists', return_value=False)
    @patch('sys.stderr', new_callable=StringIO)
    def test_load_environment_exits_without_any_credentials(
        self, mock_stderr, mock_exists, mock_candidate_files,
    ):
        with self.assertRaises(SystemExit):
            load_environment()
        out = mock_stderr.getvalue()
        self.assertIn('Missing Clockify credentials.', out)
        self.assertIn('Checked current environment, ~/rene.env, and clockipy.env.', out)

    # ---- date_interface (via injected client) -----------------------------

    def _make_client(self):
        c = MagicMock()
        c.get_time_entries.return_value = self.mock_entries
        c.get_project_and_tag_mappings.return_value = (
            self.project_id_to_name, self.tag_id_to_name, self.task_map,
        )
        return c

    @patch('sys.stdout', new_callable=StringIO)
    def test_date_interface_normal_mode(self, mock_stdout):
        date_interface(start_str="2023-01-01", end_str="2023-01-01",
                       mode="normal", client=self._make_client())
        out = mock_stdout.getvalue()
        self.assertIn("### Time Entries", out)
        self.assertIn("### Time by Project", out)
        self.assertIn("Over %", out)
        self.assertIn("Under %", out)

    @patch('sys.stdout', new_callable=StringIO)
    def test_date_interface_week_mode(self, mock_stdout):
        date_interface(start_str="2023-01-01", mode="week", client=self._make_client())
        out = mock_stdout.getvalue()
        self.assertIn("📅 Week:", out)
        self.assertIn("### Time by Project", out)

    @patch('sys.stdout', new_callable=StringIO)
    def test_date_interface_month_mode(self, mock_stdout):
        date_interface(start_str="2023-01-01", mode="month", client=self._make_client())
        out = mock_stdout.getvalue()
        self.assertIn("### Time by Project", out)
        self.assertIn("Over %", out)

    @patch('sys.stdout', new_callable=StringIO)
    def test_date_interface_with_breakdown(self, mock_stdout):
        date_interface(start_str="2023-01-01", mode="month", breakdown=True,
                       client=self._make_client())
        out = mock_stdout.getvalue()
        self.assertIn("### Time by Project", out)

    @patch('sys.stdout', new_callable=StringIO)
    def test_csv_export(self, mock_stdout):
        with patch('clockipy.utils.file_utils.write_csv') as mock_write_csv:
            date_interface(start_str="2023-01-01", end_str="2023-01-01",
                           mode="normal", csv_prefix="test_export",
                           client=self._make_client())
            self.assertGreaterEqual(mock_write_csv.call_count, 1)


if __name__ == '__main__':
    unittest.main()
