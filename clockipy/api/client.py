"""ClockifyClient: a resilient client for the Clockify v1 REST API.

Hardened over the original implementation:
- Single `requests.Session` with connection pooling.
- Retry-with-backoff on 429/5xx (urllib3 Retry adapter).
- Default HTTP timeout on every call.
- Structured ClockifyAPIError on 4xx (no silent swallowing).
- Pagination tolerates only list payloads; dict payloads raise explicitly.
- `get_tasks` re-raises real errors; only returns [] for 404.
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .errors import ClockifyAPIError

log = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30  # seconds
DEFAULT_PAGE_SIZE = 50
RETRY_STATUSES = (429, 500, 502, 503, 504)


def _build_session(api_key: str, retries: int = 3, backoff: float = 0.5) -> requests.Session:
    session = requests.Session()
    session.headers.update({"X-Api-Key": api_key, "Accept": "application/json"})
    retry = Retry(
        total=retries,
        backoff_factor=backoff,
        status_forcelist=RETRY_STATUSES,
        allowed_methods=frozenset(["GET", "HEAD"]),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=10, pool_maxsize=10)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


class ClockifyClient:
    """A resilient client for the Clockify API."""

    base_url = "https://api.clockify.me/api/v1"
    default_timeout = DEFAULT_TIMEOUT

    def __init__(
        self,
        api_key: str,
        workspace_id: str,
        user_id: str,
        *,
        timeout: Optional[float] = None,
        session: Optional[requests.Session] = None,
    ) -> None:
        self.api_key = api_key
        self.workspace_id = workspace_id
        self.user_id = user_id
        self.default_timeout = timeout or DEFAULT_TIMEOUT
        self._session = session or _build_session(api_key)

    # ---- low-level ----------------------------------------------------------

    def api_get(
        self,
        url: str,
        params: Optional[dict] = None,
        paginate: bool = False,
    ) -> Any:
        """GET ``url`` with retry/backoff, timeout, and structured error handling."""
        if not paginate:
            return self._get_single(url, params)
        return self._get_paginated(url, params)

    def _get_single(self, url: str, params: Optional[dict]) -> Any:
        try:
            resp = self._session.get(url, params=params, timeout=self.default_timeout)
        except requests.RequestException as e:
            raise ClockifyAPIError(f"Network error: {e}", url=url) from e
        self._raise_for_status(resp)
        return resp.json()

    def _get_paginated(self, url: str, params: Optional[dict]) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        page = 1
        while True:
            paged = dict(params or {})
            paged["page"] = page
            paged["page-size"] = DEFAULT_PAGE_SIZE
            try:
                resp = self._session.get(url, params=paged, timeout=self.default_timeout)
            except requests.RequestException as e:
                raise ClockifyAPIError(
                    f"Network error on page {page}: {e}", url=url
                ) from e
            self._raise_for_status(resp)
            data = resp.json()
            if not isinstance(data, list):
                raise ClockifyAPIError(
                    f"Expected list payload for paginated endpoint, got "
                    f"{type(data).__name__}",
                    url=url,
                    status_code=resp.status_code,
                    body=str(data),
                )
            results.extend(data)
            if len(data) < DEFAULT_PAGE_SIZE:
                break
            page += 1
        return results

    @staticmethod
    def _raise_for_status(resp: requests.Response) -> None:
        if resp.ok:
            return
        body = resp.text if resp.text else None
        raise ClockifyAPIError(
            f"Clockify API returned {resp.status_code} for {resp.request.url}",
            status_code=resp.status_code,
            url=resp.request.url,
            body=body,
        )

    # ---- high-level domain calls -------------------------------------------

    def get_time_entries(self, start_date: date, end_date: date) -> List[Dict[str, Any]]:
        from ..utils.date_utils import iso_datetime
        url = f"{self.base_url}/workspaces/{self.workspace_id}/user/{self.user_id}/time-entries"
        params = {
            "start": iso_datetime(start_date),
            "end": iso_datetime(end_date, is_end=True),
        }
        return self.api_get(url, params, paginate=True)

    def get_projects(self) -> List[Dict[str, Any]]:
        return self.api_get(f"{self.base_url}/workspaces/{self.workspace_id}/projects")

    def get_tags(self) -> List[Dict[str, Any]]:
        return self.api_get(f"{self.base_url}/workspaces/{self.workspace_id}/tags")

    def get_tasks(self, project_id: str) -> List[Dict[str, Any]]:
        """Get tasks for a project.

        Returns ``[]`` only on 404 (project has no tasks resource). All other
        errors propagate as ClockifyAPIError.
        """
        url = f"{self.base_url}/workspaces/{self.workspace_id}/projects/{project_id}/tasks"
        try:
            return self.api_get(url)
        except ClockifyAPIError as e:
            if e.status_code == 404:
                return []
            raise

    def get_user_and_workspaces(self) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        user = self.api_get(f"{self.base_url}/user")
        workspaces = self.api_get(f"{self.base_url}/workspaces")
        return user, workspaces

    # ---- mapping helpers ---------------------------------------------------

    def get_project_and_tag_mappings(
        self, entries: List[Dict[str, Any]]
    ) -> Tuple[Dict[str, str], Dict[str, str], Dict[Tuple[str, str], str]]:
        """Build (project_id->name, tag_id->name, (project_id, task_id)->task_name).

        Performance: only fetches tasks for projects actually referenced by
        entries (was N+1 over all workspace projects before). Parallelises the
        per-project task fetches with a small thread pool.
        """
        from concurrent.futures import ThreadPoolExecutor

        referenced_project_ids = {e.get("projectId") for e in entries if e.get("projectId")}

        project_id_to_name: Dict[str, str] = {}
        if referenced_project_ids:
            for proj in self.get_projects():
                pid = proj.get("id")
                if pid and pid in referenced_project_ids:
                    project_id_to_name[pid] = proj.get("name", "No project")

        tag_id_to_name: Dict[str, str] = {
            t["id"]: t["name"]
            for t in self.get_tags()
            if "id" in t and "name" in t
        }

        # Only fetch tasks for projects that actually had entries with taskIds.
        projects_with_tasks = {
            e["projectId"]
            for e in entries
            if e.get("projectId") and e.get("taskId")
        }

        task_map: Dict[Tuple[str, str], str] = {}
        if projects_with_tasks:
            with ThreadPoolExecutor(max_workers=8) as pool:
                results = pool.map(self.get_tasks, projects_with_tasks)
            for pid, tasks in zip(projects_with_tasks, results):
                for t in tasks:
                    tid = t.get("id")
                    tname = t.get("name")
                    if tid and tname:
                        task_map[(pid, tid)] = tname

        return project_id_to_name, tag_id_to_name, task_map
