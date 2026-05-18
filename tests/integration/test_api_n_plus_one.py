"""P4 verification: only-referenced-projects task fetching (N+1 elimination)."""
from __future__ import annotations

import responses

from clockipy.api.client import ClockifyClient


@responses.activate
def test_only_fetches_tasks_for_projects_with_entries():
    """Workspace has 3 projects, but entries only reference one with a taskId.

    Expect exactly ONE /tasks request — not 3 (would be N+1).
    """
    client = ClockifyClient(api_key="k", workspace_id="ws", user_id="u")

    responses.get(
        "https://api.clockify.me/api/v1/workspaces/ws/projects",
        json=[
            {"id": "p1", "name": "P1"},
            {"id": "p2", "name": "P2"},
            {"id": "p3", "name": "P3"},
        ],
    )
    responses.get("https://api.clockify.me/api/v1/workspaces/ws/tags", json=[])
    responses.get(
        "https://api.clockify.me/api/v1/workspaces/ws/projects/p1/tasks",
        json=[{"id": "t1", "name": "Task 1"}],
    )
    # NOTE: deliberately NOT registering p2/p3 task endpoints — they must not be called.

    entries = [{"projectId": "p1", "taskId": "t1"}]
    proj_map, tag_map, task_map = client.get_project_and_tag_mappings(entries)

    task_calls = [
        c for c in responses.calls
        if "/projects/" in c.request.url and c.request.url.endswith("/tasks")
    ]
    assert len(task_calls) == 1
    assert task_calls[0].request.url.endswith("/p1/tasks")
    assert proj_map == {"p1": "P1"}
    assert task_map == {("p1", "t1"): "Task 1"}


@responses.activate
def test_no_task_fetch_when_no_entries_have_taskid():
    client = ClockifyClient(api_key="k", workspace_id="ws", user_id="u")
    responses.get(
        "https://api.clockify.me/api/v1/workspaces/ws/projects",
        json=[{"id": "p1", "name": "P1"}],
    )
    responses.get("https://api.clockify.me/api/v1/workspaces/ws/tags", json=[])

    entries = [{"projectId": "p1"}]  # no taskId
    _, _, task_map = client.get_project_and_tag_mappings(entries)

    task_calls = [c for c in responses.calls if c.request.url.endswith("/tasks")]
    assert task_calls == []
    assert task_map == {}


@responses.activate
def test_parallel_task_fetches_across_projects():
    """Multiple projects with taskIds → each /tasks endpoint hit exactly once."""
    client = ClockifyClient(api_key="k", workspace_id="ws", user_id="u")
    responses.get(
        "https://api.clockify.me/api/v1/workspaces/ws/projects",
        json=[{"id": f"p{i}", "name": f"P{i}"} for i in range(1, 4)],
    )
    responses.get("https://api.clockify.me/api/v1/workspaces/ws/tags", json=[])
    for i in range(1, 4):
        responses.get(
            f"https://api.clockify.me/api/v1/workspaces/ws/projects/p{i}/tasks",
            json=[{"id": f"t{i}", "name": f"Task{i}"}],
        )

    entries = [{"projectId": f"p{i}", "taskId": f"t{i}"} for i in range(1, 4)]
    _, _, task_map = client.get_project_and_tag_mappings(entries)

    task_calls = [c for c in responses.calls if c.request.url.endswith("/tasks")]
    assert len(task_calls) == 3
    assert task_map == {("p1", "t1"): "Task1", ("p2", "t2"): "Task2", ("p3", "t3"): "Task3"}
