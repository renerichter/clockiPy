"""Integration tests for ClockifyClient using the `responses` HTTP mocking library.

Validates the contract:
- All GET requests carry the API key in the X-Api-Key header.
- All GET requests have a finite timeout.
- 5xx and 429 responses are retried with backoff.
- 401/403 raise a structured ClockifyAPIError (no silent swallowing).
- Pagination handles dict-wrapped responses gracefully (raises clear error).
- get_tasks re-raises errors instead of swallowing them.
"""
from __future__ import annotations

import pytest
import responses
from responses import matchers

from clockipy.api.client import ClockifyClient
from clockipy.api.errors import ClockifyAPIError


@pytest.fixture
def client():
    return ClockifyClient(api_key="k", workspace_id="ws", user_id="u")


@responses.activate
def test_api_key_header_is_sent(client):
    responses.get(
        "https://api.clockify.me/api/v1/user",
        json={"id": "u"},
        match=[matchers.header_matcher({"X-Api-Key": "k"})],
    )
    assert client.api_get("https://api.clockify.me/api/v1/user") == {"id": "u"}


@responses.activate
def test_request_has_timeout(client):
    """Indirect check: the session must be configured with a timeout default.

    We verify by inspecting the client's `default_timeout` attribute, which
    the implementation must expose for observability and tests.
    """
    assert client.default_timeout is not None
    assert client.default_timeout >= 5


@responses.activate
def test_retries_on_5xx(client):
    url = "https://api.clockify.me/api/v1/user"
    responses.get(url, status=503)
    responses.get(url, status=503)
    responses.get(url, json={"id": "u"})
    result = client.api_get(url)
    assert result == {"id": "u"}
    assert len(responses.calls) == 3


@responses.activate
def test_retries_on_429(client):
    url = "https://api.clockify.me/api/v1/user"
    responses.get(url, status=429)
    responses.get(url, json={"id": "u"})
    assert client.api_get(url) == {"id": "u"}
    assert len(responses.calls) == 2


@responses.activate
def test_raises_structured_error_on_401(client):
    responses.get("https://api.clockify.me/api/v1/user", status=401, json={"message": "bad key"})
    with pytest.raises(ClockifyAPIError) as exc:
        client.api_get("https://api.clockify.me/api/v1/user")
    assert exc.value.status_code == 401


@responses.activate
def test_pagination_collects_all_pages(client):
    url = "https://api.clockify.me/api/v1/workspaces/ws/user/u/time-entries"
    page1 = [{"id": str(i)} for i in range(50)]
    page2 = [{"id": str(i)} for i in range(50, 73)]
    responses.get(url, json=page1)
    responses.get(url, json=page2)
    from datetime import date
    entries = client.get_time_entries(date(2026, 5, 1), date(2026, 5, 31))
    assert len(entries) == 73


@responses.activate
def test_pagination_rejects_dict_payload(client):
    url = "https://api.clockify.me/api/v1/workspaces/ws/user/u/time-entries"
    responses.get(url, json={"error": "boom"})
    from datetime import date
    with pytest.raises(ClockifyAPIError) as exc:
        client.get_time_entries(date(2026, 5, 1), date(2026, 5, 31))
    assert "dict" in str(exc.value).lower() or "list" in str(exc.value).lower()


@responses.activate
def test_get_tasks_propagates_errors(client):
    url = "https://api.clockify.me/api/v1/workspaces/ws/projects/p1/tasks"
    responses.get(url, status=500)
    responses.get(url, status=500)
    responses.get(url, status=500)
    responses.get(url, status=500)
    with pytest.raises(ClockifyAPIError):
        client.get_tasks("p1")


@responses.activate
def test_get_tasks_returns_empty_on_404(client):
    """404 = project legitimately has no tasks endpoint; not an error worth raising."""
    url = "https://api.clockify.me/api/v1/workspaces/ws/projects/p1/tasks"
    responses.get(url, status=404)
    assert client.get_tasks("p1") == []
