"""Date utility functions for clockiPy."""
from datetime import datetime, date, time, timezone, timedelta
import calendar

def iso_datetime(dt: date, is_end: bool = False) -> str:
    """Convert a date to an ISO datetime string.
    
    Args:
        dt: Date to convert
        is_end: Whether this is an end date (uses time.max instead of time.min)
        
    Returns:
        ISO datetime string
    """
    t = time.max if is_end else time.min
    return datetime.combine(dt, t, tzinfo=timezone.utc).isoformat()

def get_week_range(target_date: date, week_start: int = 0) -> (date, date):
    """Get the start and end dates of the week containing the target date.
    
    Args:
        target_date: Date within the week
        week_start: Day of week to start on (0=Monday, 6=Sunday)
        
    Returns:
        Tuple of (start_date, end_date)
    """
    wd = (target_date.weekday() - week_start) % 7
    start = target_date - timedelta(days=wd)
    end = start + timedelta(days=6)
    return start, end

def get_month_range(target_date: date) -> (date, date):
    """Get the start and end dates of the month containing the target date.
    
    Args:
        target_date: Date within the month
        
    Returns:
        Tuple of (start_date, end_date)
    """
    start = target_date.replace(day=1)
    last_day = calendar.monthrange(target_date.year, target_date.month)[1]
    end = target_date.replace(day=last_day)
    return start, end

def get_year_range(target_date: date) -> (date, date):
    """Get the start and end dates of the year containing the target date.
    
    Args:
        target_date: Date within the year
        
    Returns:
        Tuple of (start_date, end_date) - Jan 1 to Dec 31
    """
    start = date(target_date.year, 1, 1)
    end = date(target_date.year, 12, 31)
    return start, end

def day_str(dt: date) -> str:
    """Format a date as a string with day of week.
    
    Args:
        dt: Date to format
        
    Returns:
        Formatted date string
    """
    return f"({['Mo','Tue','Wed','Thu','Fri','Sat','Sun'][dt.weekday()]}){dt}" 