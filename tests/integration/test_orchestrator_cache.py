"""Integration tests for orchestrator ↔ cache wiring."""
from __future__ import annotations

import io
from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from clockipy.orchestrator import date_interface
from clockipy.store import Cache


@pytest.fixture
def mock_client():
    c = MagicMock()
    c.workspace_id = "ws"
    c.user_id = "u"
    c.get_time_entries.return_value = [
        {
            "id": "e1",
            "timeInterval": {
                "start": "2026-05-15T08:00:00Z",
                "end": "2026-05-15T09:00:00Z",
                "duration": "PT1H",
            },
            "projectId": "p1",
            "taskId": "t1",
            "tagIds": ["tag1"],
            "description": "task {p1:00}",
        }
    ]
    c.get_project_and_tag_mappings.return_value = (
        {"p1": "Project One"},
        {"tag1": "Tag One"},
        {("p1", "t1"): "SubProj"},
    )
    return c


def test_cache_miss_triggers_api_fetch_and_writes_back(tmp_path, mock_client):
    cache = Cache(tmp_path / "c.db")
    with patch("sys.stdout", new_callable=io.StringIO):
        date_interface(
            start_str="2026-05-15", end_str="2026-05-15", mode="normal",
            client=mock_client, cache=cache,
        )
    assert mock_client.get_time_entries.call_count == 1
    assert mock_client.get_project_and_tag_mappings.call_count == 1
    assert cache.get_entries(date(2026, 5, 15), date(2026, 5, 15))
    assert cache.get_project_map() == {"p1": "Project One"}
    assert cache.is_fresh(date(2026, 5, 15), date(2026, 5, 15))


def test_cache_hit_skips_api(tmp_path, mock_client):
    cache = Cache(tmp_path / "c.db")
    with patch("sys.stdout", new_callable=io.StringIO):
        date_interface(start_str="2026-05-15", end_str="2026-05-15", mode="normal",
                       client=mock_client, cache=cache)
    mock_client.reset_mock()
    with patch("sys.stdout", new_callable=io.StringIO):
        date_interface(start_str="2026-05-15", end_str="2026-05-15", mode="normal",
                       client=mock_client, cache=cache)
    assert mock_client.get_time_entries.call_count == 0
    assert mock_client.get_project_and_tag_mappings.call_count == 0


def test_force_refresh_bypasses_cache(tmp_path, mock_client):
    cache = Cache(tmp_path / "c.db")
    with patch("sys.stdout", new_callable=io.StringIO):
        date_interface(start_str="2026-05-15", end_str="2026-05-15", mode="normal",
                       client=mock_client, cache=cache)
    mock_client.reset_mock()
    with patch("sys.stdout", new_callable=io.StringIO):
        date_interface(start_str="2026-05-15", end_str="2026-05-15", mode="normal",
                       client=mock_client, cache=cache, force_refresh=True)
    assert mock_client.get_time_entries.call_count == 1


def test_no_cache_disables_persistence(tmp_path, mock_client):
    with patch("sys.stdout", new_callable=io.StringIO):
        date_interface(start_str="2026-05-15", end_str="2026-05-15", mode="normal",
                       client=mock_client, use_cache=False)
    # No cache file should exist anywhere in tmp_path.
    assert list(tmp_path.glob("**/*.db")) == []


def test_empty_api_response_records_sync_to_avoid_refetch(tmp_path, mock_client):
    mock_client.get_time_entries.return_value = []
    cache = Cache(tmp_path / "c.db")
    with patch("sys.stdout", new_callable=io.StringIO):
        date_interface(start_str="2026-05-15", end_str="2026-05-15", mode="normal",
                       client=mock_client, cache=cache)
    assert cache.is_fresh(date(2026, 5, 15), date(2026, 5, 15))
