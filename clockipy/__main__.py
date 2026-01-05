"""Main module for the clockiPy package."""
import os
import sys
import argparse
from datetime import datetime, date, timedelta
from typing import Optional
from dotenv import load_dotenv
from collections import defaultdict

from .api.client import ClockifyClient
from .utils.date_utils import iso_datetime, get_week_range, get_month_range, get_year_range, day_str
from .utils.file_utils import write_markdown
from .reports.time_entry import TimeEntry
from .reports.report_generator import ReportGenerator

# --- Environment Setup ---
def load_environment():
    """Load environment variables from the clockipy.env file."""
    env_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'clockipy.env')
    if not os.path.exists(env_file):
        print(f"Missing environment file: {env_file}")
        sys.exit(1)
    load_dotenv(env_file)

def get_env_var(key: str) -> str:
    """Get an environment variable or exit if not found.
    
    Args:
        key: Environment variable name
        
    Returns:
        Environment variable value
        
    Raises:
        SystemExit: If the environment variable is not found
    """
    value = os.getenv(key)
    if not value:
        print(f"Set {key} in your environment or clockipy.env.")
        sys.exit(1)
    return value

# --- CLI Logic ---
def parse_args() -> argparse.Namespace:
    """Parse command line arguments.
    
    Returns:
        Parsed arguments
    """
    parser = argparse.ArgumentParser(
        description="Fetch and display Clockify time entries in a clean table.",
        epilog="""
Examples:
    # Show entries and summary for a custom date range
  clockipy --start 2025-05-15 --end 2024-05-22
    ---
    # Show per-day tables and weekly summary for the week containing 2025-05-15
  clockipy --mode week --start 2025-05-15
    ---
    # Show monthly summary, per-week breakdown, and export all tables to CSV files with prefix 'june'  
  clockipy --mode month --start 2025-05-15 --breakdown --csv june
    ---
    # Show yearly summary for 2025 (Jan 1 to Dec 31)
  clockipy --mode year --start 2025-01-01
    ---
    # Show yearly summary with per-month breakdown
  clockipy --mode year --start 2025-06-15 --breakdown
      
""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        prog="clockipy"
    )
    parser.add_argument('-l', '--list', action='store_true', help='List user and workspaces with their IDs')
    parser.add_argument('--start', help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end', help='End date (YYYY-MM-DD)')
    parser.add_argument('--mode', choices=['normal', 'week', 'month', 'year'], default='normal', help='Summary mode: normal (default), week (per-day tables), month (monthly summary), year (yearly summary)')
    parser.add_argument('--weekstart', type=int, choices=range(0,7), default=0, help='Custom week start day: 0=Mon, 6=Sun (default: 0)')
    parser.add_argument('--csv', help='Export main tables to CSV (provide filename prefix)')
    parser.add_argument('--breakdown', action='store_true', help='For month mode: add per-week summary tables')
    parser.add_argument('--test', action='store_true', help='Print a sample of the task mapping for verification')
    parser.add_argument('--md', help='Export output as markdown to the given file path')
    parser.add_argument('--overwrite', action='store_true', help='Explicitly overwrite the markdown file if it exists (DANGEROUS)')
    return parser.parse_args()

def prompt_for_date(prompt: str, default: str) -> str:
    """Prompt the user for a date.
    
    Args:
        prompt: Prompt message
        default: Default value
        
    Returns:
        User input or default value
    """
    user_input = input(f"{prompt} [{default}]: ").strip()
    return user_input or default

def list_user_and_workspaces() -> None:
    """List user information and workspaces."""
    api_key = get_env_var("CLOCKIFY_API_KEY")
    client = ClockifyClient(api_key, "", "")
    user, workspaces = client.get_user_and_workspaces()
    
    print("\nUser Info:")
    print(f"  Name: {user.get('name')}")
    print(f"  Email: {user.get('email')}")
    print(f"  ID: {user.get('id')}")
    
    print("\nWorkspaces:")
    for ws in workspaces:
        print(f"  Name: {ws.get('name')}, ID: {ws.get('id')}")

def date_interface(start_str: Optional[str] = None, end_str: Optional[str] = None, test_mode: bool = False, mode: str = "normal", week_start: int = 0, csv_prefix: Optional[str] = None, breakdown: bool = False, md_path: Optional[str] = None, overwrite: bool = False) -> None:
    """Main interface for date-based reports.
    
    Args:
        start_str: Start date string (YYYY-MM-DD)
        end_str: End date string (YYYY-MM-DD)
        test_mode: Whether to run in test mode
        mode: Report mode (normal, week, month)
        week_start: Day of week to start on (0=Monday, 6=Sunday)
        csv_prefix: Prefix for CSV files
        breakdown: Whether to include breakdown tables
        md_path: Path to export markdown
        overwrite: Whether to overwrite existing markdown file
    """
    today = date.today()
    
    # Determine date range based on mode
    if mode == "week":
        ref_date = datetime.strptime(start_str, "%Y-%m-%d").date() if start_str else today
        start_date, end_date = get_week_range(ref_date, week_start)
        print(f"📅 Week: {start_date} ({start_date.strftime('%a')}) → {end_date} ({end_date.strftime('%a')})")
    elif mode == "month":
        ref_date = datetime.strptime(start_str, "%Y-%m-%d").date() if start_str else today
        start_date, end_date = get_month_range(ref_date)
        print(f"📅 Month: {start_date} → {end_date}")
    elif mode == "year":
        ref_date = datetime.strptime(start_str, "%Y-%m-%d").date() if start_str else today
        start_date, end_date = get_year_range(ref_date)
        print(f"📅 Year {ref_date.year}: {start_date} → {end_date}")
    else:
        start_str = start_str or prompt_for_date("Start date (YYYY-MM-DD)", today.isoformat())
        end_str = end_str or prompt_for_date("End date (YYYY-MM-DD)", today.isoformat())
        start_date = datetime.strptime(start_str, "%Y-%m-%d").date()
        end_date = datetime.strptime(end_str, "%Y-%m-%d").date()
    
    # Initialize API client
    api_key = get_env_var("CLOCKIFY_API_KEY")
    workspace_id = get_env_var("CLOCKIFY_WORKSPACE_ID")
    user_id = get_env_var("CLOCKIFY_USER_ID")
    client = ClockifyClient(api_key, workspace_id, user_id)
    
    # Get time entries
    entries = client.get_time_entries(start_date, end_date)
    
    if not entries:
        print(f"\n⚠️  No time entries found for {day_str(start_date)} to {day_str(end_date)}")
        return
    
    print(f"📊 Found {len(entries)} time entries")
    
    # Get project, tag, and task mappings
    project_id_to_name, tag_id_to_name, task_map = client.get_project_and_tag_mappings(entries)
    
    # Print task mapping if in test mode
    if test_mode:
        print("\nSample of resolved (projectId, taskId) -> taskName mapping:")
        for i, ((pid, tid), tname) in enumerate(task_map.items()):
            print(f"  Project: {project_id_to_name.get(pid, pid)} | TaskId: {tid} -> Task: {tname}")
            if i >= 4:
                break
    
    def create_time_entry(e, idx):
        """Create a TimeEntry from raw entry data."""
        project_id = e.get("projectId")
        task_id = e.get("taskId")
        project_name = project_id_to_name.get(project_id, "No project")
        task_name = task_map.get((project_id, task_id), "") if project_id and task_id else ""
        tag_ids = e.get("tagIds") or []
        tag_names = [tag_id_to_name.get(tid, tid) for tid in tag_ids]
        return TimeEntry(e, idx, project_name, task_name, tag_names)
    
    def entries_to_time_entries(raw_entries):
        """Convert raw API entries to TimeEntry objects, sorted by start time."""
        sorted_entries = sorted(raw_entries, key=lambda x: x["timeInterval"]["start"])
        return [create_time_entry(e, idx + 1) for idx, e in enumerate(sorted_entries)]
    
    # --- Mode logic ---
    import io
    md_buffer = io.StringIO() if md_path else None
    
    def print_report(report: str):
        """Print a report to stdout and/or the markdown buffer.
        
        Args:
            report: Report text
        """
        if md_buffer:
            md_buffer.write(report)
        else:
            print(report)
    
    if mode == "week":
        # Group entries by day
        entries_by_day = {}
        for e in entries:
            day = datetime.fromisoformat(e["timeInterval"]["start"].replace("Z", "+00:00")).date()
            if day not in entries_by_day:
                entries_by_day[day] = []
            entries_by_day[day].append(e)
        
        # Process each day
        all_time_entries = []
        all_proj = defaultdict(int)
        all_tag = defaultdict(int)
        all_spont = {"🎲": 0, "🗓️": 0}
        all_total = 0
        
        if breakdown:
            for i in range(7):
                day = start_date + timedelta(days=i)
                if day not in entries_by_day:
                    continue
                
                day_entries = entries_to_time_entries(entries_by_day[day])
                all_time_entries.extend(day_entries)
                
                date_range_str = day_str(day)
                report_generator = ReportGenerator(day_entries, date_range_str, mode)
                report = report_generator.generate_report(csv_prefix, day_table=True)
                print_report(report)
                
                for k, v in report_generator.project_durations.items():
                    all_proj[k] += v
                for k, v in report_generator.tag_durations.items():
                    all_tag[k] += v
                for k, v in report_generator.spontaneousity_durations.items():
                    all_spont[k] += v
                all_total += report_generator.total_duration
        else:
            all_time_entries = entries_to_time_entries(entries)
        
        # Print summary for the week
        date_range_str = f"{day_str(start_date)} to {day_str(end_date)}"
        report_generator = ReportGenerator(all_time_entries, date_range_str, mode)
        report = report_generator.generate_report(csv_prefix, day_table=None)
        print_report(report)
    
    elif mode == "month":
        time_entries = entries_to_time_entries(entries)
        
        # Generate report for the month
        date_range_str = f"{day_str(start_date)} to {day_str(end_date)}"
        report_generator = ReportGenerator(time_entries, date_range_str, mode)
        report = report_generator.generate_report(csv_prefix, day_table=None)
        print_report(report)
        
        # Generate breakdown reports if requested
        if breakdown:
            
            first_of_month = start_date
            last_of_month = end_date
            first_week_start, _ = get_week_range(first_of_month, week_start)
            _, last_week_end = get_week_range(last_of_month, week_start)
            
            week_ranges = []
            d = first_week_start
            while d <= last_week_end:
                wstart = d
                wend = d + timedelta(days=6)
                week_ranges.append((max(wstart, first_of_month), min(wend, last_of_month)))
                d += timedelta(days=7)
            
            for wstart, wend in week_ranges:
                week_entries = [e for e in time_entries if wstart <= datetime.fromisoformat(e.start.replace("Z", "+00:00")).date() <= wend]
                if not week_entries:
                    continue
                
                date_range_str = f"{day_str(wstart)} to {day_str(wend)}"
                report_generator = ReportGenerator(week_entries, date_range_str, mode)
                report = report_generator.generate_report(csv_prefix, day_table=None)
                print_report(report)
    
    elif mode == "year":
        time_entries = entries_to_time_entries(entries)
        
        # Generate report for the year
        date_range_str = f"{day_str(start_date)} to {day_str(end_date)}"
        report_generator = ReportGenerator(time_entries, date_range_str, mode)
        report = report_generator.generate_report(csv_prefix, day_table=None)
        print_report(report)
        
        # Generate per-month breakdown reports if requested
        if breakdown:
            import calendar as cal
            year = start_date.year
            
            for month in range(1, 13):
                month_start = date(year, month, 1)
                month_end = date(year, month, cal.monthrange(year, month)[1])
                
                month_entries = [
                    e for e in time_entries 
                    if month_start <= datetime.fromisoformat(e.start.replace("Z", "+00:00")).date() <= month_end
                ]
                if not month_entries:
                    continue
                
                date_range_str = f"{day_str(month_start)} to {day_str(month_end)}"
                report_generator = ReportGenerator(month_entries, date_range_str, "month")
                report = report_generator.generate_report(csv_prefix, day_table=None)
                print_report(report)
    
    else:
        time_entries = entries_to_time_entries(entries)
        
        # Generate report
        date_range_str = f"{day_str(start_date)} to {day_str(end_date)}"
        report_generator = ReportGenerator(time_entries, date_range_str, mode)
        report = report_generator.generate_report(csv_prefix)
        print_report(report)
    
    # If markdown output requested, write to file
    if md_path:
        md_content = f"\n{md_buffer.getvalue()}\n"
        write_markdown(md_path, md_content, start_date, end_date, overwrite)
        print(f"[SUCCESS] Markdown output written to '{md_path}'")
        sys.exit(0)

def main() -> None:
    """Main entry point."""
    # Load environment variables
    load_environment()
    
    # Parse command line arguments
    args = parse_args()
    
    if args.list:
        list_user_and_workspaces()
    else:
        date_interface(
            args.start, args.end, getattr(args, 'test', False),
            args.mode, args.weekstart, args.csv, args.breakdown,
            getattr(args, 'md', None), getattr(args, 'overwrite', False)
        )

if __name__ == "__main__":
    main() 