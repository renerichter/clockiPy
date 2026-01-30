"""Formatting utility functions for clockiPy."""
import re

def format_seconds(seconds: int) -> str:
    """Format seconds as HH:MM:SS.
    
    Args:
        seconds: Number of seconds
        
    Returns:
        Formatted time string
    """
    h, m = divmod(seconds, 3600)
    m, s = divmod(m, 60)
    return f"{h:02}:{m:02}:{s:02}"

def format_hm(seconds: int) -> str:
    """Format seconds as HH:MM.
    
    Args:
        seconds: Number of seconds (can be negative)
        
    Returns:
        Formatted time string (with leading '-' if negative)
    """
    if seconds < 0:
        abs_seconds = abs(seconds)
        return f"-{abs_seconds // 3600:02}:{(abs_seconds % 3600) // 60:02}"
    return f"{seconds // 3600:02}:{(seconds % 3600) // 60:02}"

def parse_clockify_duration(duration: str) -> int:
    """Parse a Clockify duration string into seconds.
    
    Args:
        duration: Clockify duration string (e.g., "PT1H30M")
        
    Returns:
        Duration in seconds
    """
    if not duration:
        return 0
    
    match = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", duration)
    if not match:
        return 0
    
    h, m, s = match.groups(default="0")
    return int(h) * 3600 + int(m) * 60 + int(s)

def parse_planned_from_name(name: str) -> int:
    """Extract planned duration in seconds from entry name pattern {ph:mm}.
    
    Args:
        name: Entry name (e.g., "Task {p1:30}")
        
    Returns:
        Planned duration in seconds, or 0 if not found or invalid
    """
    match = re.search(r"\{p(\d+):(\d{1,2})\}", name)
    if not match:
        return 0
    
    hours, minutes = match.groups()
    try:
        return int(hours) * 3600 + int(minutes) * 60
    except Exception:
        return 0

def percent(val: int, total: int) -> str:
    """Calculate percentage and format as string.
    
    Args:
        val: Value
        total: Total
        
    Returns:
        Formatted percentage string
    """
    return f"{(val / total * 100):.0f}" if total else "0" 