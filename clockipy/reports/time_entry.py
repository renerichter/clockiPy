"""TimeEntry class for representing and manipulating Clockify time entries."""
from datetime import datetime, date
from typing import Optional, Dict, Any, List
from ..utils.format_utils import parse_clockify_duration, parse_planned_from_name, format_hm

class TimeEntry:
    """Class representing a Clockify time entry."""
    
    def __init__(self, entry_data: Dict[str, Any], index: int, project_name: str = "No project", 
                 task_name: str = "", tag_names: List[str] = None):
        """Initialize a TimeEntry.
        
        Args:
            entry_data: Raw entry data from the Clockify API
            index: Index of this entry in the list
            project_name: Project name (optional)
            task_name: Task name (optional)
            tag_names: List of tag names (optional)
        """
        self.raw_data = entry_data
        self.index = index
        self.description = entry_data.get("description") or entry_data.get("task", {}).get("name") or "No description"
        self.project_id = entry_data.get("projectId")
        self.task_id = entry_data.get("taskId")
        self.project_name = project_name
        self.task_name = task_name
        self.tag_names = tag_names or []
        
        # Time information
        self.start = entry_data["timeInterval"]["start"]
        self.end = entry_data["timeInterval"].get("end", "")
        self.duration_sec = parse_clockify_duration(entry_data["timeInterval"].get("duration"))
        self.planned_sec = parse_planned_from_name(self.description)
        
        # Spontaneity
        self.is_spontaneous = "🎲" in self.description
        self.is_scheduled = "🗓️" in self.description
        self.is_recurring = "🔁" in self.description
    
    @property
    def tags_str(self) -> str:
        """Get tags as a comma-separated string.
        
        Returns:
            Comma-separated tag string
        """
        return ", ".join(self.tag_names) if self.tag_names else ""
    
    @property
    def start_hm(self) -> str:
        """Get formatted start time.
        
        Returns:
            Formatted start time (HH:MM)
        """
        return self._format_time(self.start)

    @property
    def start_date(self) -> Optional[date]:
        """Get the start date in UTC.

        Returns:
            Date portion of the start time, or None if unavailable
        """
        if not self.start:
            return None
        try:
            dt_utc = datetime.fromisoformat(self.start.replace("Z", "+00:00"))
            return dt_utc.date()
        except Exception:
            return None
    
    @property
    def end_hm(self) -> str:
        """Get formatted end time.
        
        Returns:
            Formatted end time (HH:MM)
        """
        return self._format_time(self.end)
    
    @property
    def duration_hm(self) -> str:
        """Get formatted duration.
        
        Returns:
            Formatted duration (HH:MM)
        """
        return format_hm(self.duration_sec)
    
    @property
    def planned_hm(self) -> str:
        """Get formatted planned duration.
        
        Returns:
            Formatted planned duration (HH:MM), or empty string if none
        """
        return format_hm(self.planned_sec) if self.planned_sec else ""
    
    @property
    def difference_sec(self) -> int:
        """Get the difference between actual and planned duration.
        
        Returns:
            Difference in seconds (positive if actual > planned), or 0 if no planned time
        """
        if not self.planned_sec:
            return 0
        return self.duration_sec - self.planned_sec
    
    @property
    def difference_hm(self) -> str:
        """Get formatted difference between actual and planned duration.
        
        Returns:
            Formatted difference (±HH:MM), or empty string if no planned duration
        """
        if not self.planned_sec:
            return ""
        
        diff_sec = self.difference_sec
        if diff_sec == 0:
            return "00:00"
        
        abs_diff = abs(diff_sec)
        diff_hm = format_hm(abs_diff)
        return ("+" if diff_sec > 0 else "-") + diff_hm
    
    def _format_time(self, dt_str: str) -> str:
        """Format a datetime string as HH:MM in local time.
        
        Args:
            dt_str: ISO datetime string
            
        Returns:
            Formatted time string (HH:MM)
        """
        if not dt_str:
            return ""
        
        try:
            dt_utc = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
            return dt_utc.astimezone().strftime("%H:%M")
        except Exception:
            return ""
    
    def to_row(self, total_duration: int) -> List[Any]:
        """Convert to a table row.
        
        Args:
            total_duration: Total duration of all entries (for percentage calculation)
            
        Returns:
            Table row as a list
        """
        from ..utils.format_utils import percent
        
        return [
            self.index,
            self.description,
            self.task_name,
            self.project_name,
            self.planned_hm,
            self.start_hm,
            self.end_hm,
            self.duration_hm,
            self.difference_hm,
            self.tags_str,
            self.duration_sec
        ] 
