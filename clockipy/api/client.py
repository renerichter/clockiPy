"""
ClockifyClient: A client for interacting with the Clockify API.
"""
import requests
from typing import Optional, Dict, Any, List, Set, Tuple
from datetime import date

class ClockifyClient:
    """A client for interacting with the Clockify API."""
    
    def __init__(self, api_key: str, workspace_id: str, user_id: str):
        """Initialize the ClockifyClient.
        
        Args:
            api_key: Clockify API key
            workspace_id: Clockify workspace ID
            user_id: Clockify user ID
        """
        self.api_key = api_key
        self.workspace_id = workspace_id
        self.user_id = user_id
        self.base_url = "https://api.clockify.me/api/v1"
    
    def api_get(self, url: str, params: Optional[dict] = None, paginate: bool = False) -> Any:
        """Make a GET request to the Clockify API.
        
        Args:
            url: API endpoint URL
            params: Query parameters (optional)
            paginate: Whether to paginate the results (optional)
            
        Returns:
            API response as JSON
            
        Raises:
            requests.RequestException: If the API request fails
        """
        headers = {"X-Api-Key": self.api_key}
        if not paginate:
            try:
                resp = requests.get(url, headers=headers, params=params)
                resp.raise_for_status()
                return resp.json()
            except requests.RequestException as e:
                raise requests.RequestException(f"API request failed: {e}")
        else:
            # Pagination logic for endpoints returning lists (e.g., time entries)
            all_results = []
            page = 1
            page_size = 50  # Clockify default/max
            while True:
                paged_params = params.copy() if params else {}
                paged_params["page"] = page
                paged_params["page-size"] = page_size
                try:
                    resp = requests.get(url, headers=headers, params=paged_params)
                    resp.raise_for_status()
                    data = resp.json()
                    if not isinstance(data, list):
                        # Defensive: if not a list, just return
                        return data
                    all_results.extend(data)
                    if len(data) < page_size:
                        break  # Last page
                    page += 1
                except requests.RequestException as e:
                    raise requests.RequestException(f"API request failed (page {page}): {e}")
            return all_results
    
    def get_time_entries(self, start_date: date, end_date: date) -> List[Dict[str, Any]]:
        """Get time entries for the specified date range.
        
        Args:
            start_date: Start date
            end_date: End date
            
        Returns:
            List of time entries
        """
        from ..utils.date_utils import iso_datetime
        
        url = f"{self.base_url}/workspaces/{self.workspace_id}/user/{self.user_id}/time-entries"
        params = {
            "start": iso_datetime(start_date),
            "end": iso_datetime(end_date, is_end=True)
        }
        return self.api_get(url, params, paginate=True)
    
    def get_projects(self) -> List[Dict[str, Any]]:
        """Get all projects in the workspace.
        
        Returns:
            List of projects
        """
        url = f"{self.base_url}/workspaces/{self.workspace_id}/projects"
        return self.api_get(url)
    
    def get_tags(self) -> List[Dict[str, Any]]:
        """Get all tags in the workspace.
        
        Returns:
            List of tags
        """
        url = f"{self.base_url}/workspaces/{self.workspace_id}/tags"
        return self.api_get(url)
    
    def get_tasks(self, project_id: str) -> List[Dict[str, Any]]:
        """Get all tasks for a project.
        
        Args:
            project_id: Project ID
            
        Returns:
            List of tasks
        """
        url = f"{self.base_url}/workspaces/{self.workspace_id}/projects/{project_id}/tasks"
        try:
            return self.api_get(url)
        except requests.RequestException:
            return []
    
    def get_user_and_workspaces(self) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """Get user information and workspaces.
        
        Returns:
            Tuple of (user_info, workspaces)
        """
        user_url = f"{self.base_url}/user"
        user = self.api_get(user_url)
        
        workspaces_url = f"{self.base_url}/workspaces"
        workspaces = self.api_get(workspaces_url)
        
        return user, workspaces
    
    def get_project_and_tag_mappings(self, entries: List[Dict[str, Any]]) -> Tuple[Dict[str, str], Dict[str, str], Dict[Tuple[str, str], str]]:
        """Get mappings for project IDs, tag IDs, and task IDs.
        
        Args:
            entries: List of time entries
            
        Returns:
            Tuple of (project_id_to_name, tag_id_to_name, task_map)
        """
        # Get project mappings
        project_ids = {e.get("projectId") for e in entries if e.get("projectId")}
        project_id_to_name = {}
        if project_ids:
            projects = self.get_projects()
            for proj in projects:
                pid = proj.get("id")
                pname = proj.get("name", "No project")
                if pid:
                    project_id_to_name[pid] = pname
        
        # Get tag mappings
        tags_data = self.get_tags()
        tag_id_to_name = {tag['id']: tag['name'] for tag in tags_data if 'id' in tag and 'name' in tag}
        
        # Get task mappings
        project_task_ids = set()
        for e in entries:
            pid = e.get("projectId")
            tid = e.get("taskId")
            if pid and tid:
                project_task_ids.add((pid, tid))
        
        task_map = {}
        for pid in project_ids:
            if not pid:
                continue
            tasks = self.get_tasks(pid)
            for t in tasks:
                tid = t.get("id")
                tname = t.get("name")
                if tid and tname:
                    task_map[(pid, tid)] = tname
        
        return project_id_to_name, tag_id_to_name, task_map 