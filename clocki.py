"""
clockiPy: A CLI tool for fetching and displaying Clockify time entries in a clean table.

- Fetches time entries from the Clockify API
- Summarizes by day, week, month, project, tag, and more
- Exports to CSV and Markdown
- Can be used as a CLI (via `python clocki.py` or `clockipy` if installed as a package)

Environment variables are loaded from `clockipy.env` (see `clockipy.env.example`).
"""
import os
import sys
import argparse
from datetime import datetime, date, time, timezone, timedelta
from collections import defaultdict
from typing import Optional, Dict, Any, List
import requests
from tabulate import tabulate
from dotenv import load_dotenv
import calendar
import csv
import markdown

# --- Environment Setup ---
ENV_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'clockipy.env')
if not os.path.exists(ENV_FILE):
    print(f"Missing environment file: {ENV_FILE}")
    sys.exit(1)
load_dotenv(ENV_FILE)

# --- Helpers ---
def get_env_var(key: str) -> str:
    value = os.getenv(key)
    if not value:
        print(f"Set {key} in your environment or {ENV_FILE}.")
        sys.exit(1)
    return value

def api_get(url: str, api_key: str, params: Optional[dict] = None, paginate: bool = False) -> Any:
    headers = {"X-Api-Key": api_key}
    if not paginate:
        try:
            resp = requests.get(url, headers=headers, params=params)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            print(f"API request failed: {e}")
            sys.exit(1)
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
                print(f"API request failed (page {page}): {e}")
                sys.exit(1)
        return all_results

def parse_clockify_duration(duration: Optional[str]) -> int:
    if not duration:
        return 0
    import re
    match = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", duration)
    if not match:
        return 0
    h, m, s = match.groups(default="0")
    return int(h) * 3600 + int(m) * 60 + int(s)

def format_seconds(seconds: int) -> str:
    h, m = divmod(seconds, 3600)
    m, s = divmod(m, 60)
    return f"{h:02}:{m:02}:{s:02}"

def iso_datetime(dt: date, is_end: bool = False) -> str:
    t = time.max if is_end else time.min
    return datetime.combine(dt, t, tzinfo=timezone.utc).isoformat()

def parse_planned_from_name(name: str) -> int:
    """
    Extract planned duration in seconds from entry name pattern {ph:mm} (e.g., {p1:30}).
    Returns 0 if not found or invalid.
    """
    import re
    match = re.search(r"\{p(\d+):(\d{1,2})\}", name)
    if not match:
        return 0
    hours, minutes = match.groups()
    try:
        return int(hours) * 3600 + int(minutes) * 60
    except Exception:
        return 0

def get_week_range(target_date: date, week_start: int = 0) -> (date, date):
    # week_start: 0=Monday, 6=Sunday
    wd = (target_date.weekday() - week_start) % 7
    start = target_date - timedelta(days=wd)
    end = start + timedelta(days=6)
    return start, end

def get_month_range(target_date: date) -> (date, date):
    start = target_date.replace(day=1)
    last_day = calendar.monthrange(target_date.year, target_date.month)[1]
    end = target_date.replace(day=last_day)
    return start, end

def day_str(dt: date) -> str:
    return f"({['Mo','Tue','Wed','Thu','Fri','Sat','Sun'][dt.weekday()]}){dt}"

def write_csv(filename: str, headers: list, rows: list):
    with open(filename, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)

def write_markdown(md_path, content, start_date, end_date, overwrite=False):
    # File existence feedback
    file_exists = os.path.exists(md_path)
    if file_exists and not overwrite:
        mode = 'a'
        print(f"[INFO] File '{md_path}' exists. Appending output.")
    elif file_exists and overwrite:
        mode = 'w'
        print(f"[INFO] File '{md_path}' exists. Overwriting as requested.")
    else:
        mode = 'w'
        print(f"[INFO] File '{md_path}' does not exist. Creating new file.")
    try:
        with open(md_path, mode, encoding='utf-8') as f:
            if mode == 'w' or (mode == 'a' and os.stat(md_path).st_size == 0):
                f.write(f"# Analysis of {start_date} to {end_date}\n\n")
            f.write(content)
    except Exception as e:
        print(f"[ERROR] Failed to write to '{md_path}': {e}")
        sys.exit(2)
    # Markdown validation
    try:
        with open(md_path, 'r', encoding='utf-8') as f:
            md_text = f.read()
        # Validate by converting to HTML (will raise if invalid)
        markdown.markdown(md_text)
    except Exception as e:
        print(f"[ERROR] Markdown validation failed for '{md_path}': {e}")
        sys.exit(3)

# --- CLI Logic ---
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch and display Clockify time entries in a clean table.",
        epilog="""
Examples:
    # Show entries and summary for a custom date range
  python clocki.py --start 2025-05-15 --end 2024-05-22
    ---
    # Show per-day tables and weekly summary for the week containing 2025-05-15
  python clocki.py --mode week --start 2025-05-15
    ---
    # Show monthly summary, per-week breakdown, and export all tables to CSV files with prefix 'june'  
  python clocki.py --mode month --start 2025-05-15 --breakdown --csv june
      
""",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('-l', '--list', action='store_true', help='List user and workspaces with their IDs')
    parser.add_argument('--start', help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end', help='End date (YYYY-MM-DD)')
    parser.add_argument('--mode', choices=['normal', 'week', 'month'], default='normal', help='Summary mode: normal (default), week (per-day tables), month (monthly summary)')
    parser.add_argument('--weekstart', type=int, choices=range(0,7), default=0, help='Custom week start day: 0=Mon, 6=Sun (default: 0)')
    parser.add_argument('--csv', help='Export main tables to CSV (provide filename prefix)')
    parser.add_argument('--breakdown', action='store_true', help='For month mode: add per-week summary tables')
    parser.add_argument('--test', action='store_true', help='Print a sample of the task mapping for verification')
    parser.add_argument('--md', help='Export output as markdown to the given file path')
    parser.add_argument('--overwrite', action='store_true', help='Explicitly overwrite the markdown file if it exists (DANGEROUS)')
    return parser.parse_args()

def prompt_for_date(prompt: str, default: str) -> str:
    user_input = input(f"{prompt} [{default}]: ").strip()
    return user_input or default

def list_user_and_workspaces() -> None:
    api_key = get_env_var("CLOCKIFY_API_KEY")
    user = api_get("https://api.clockify.me/api/v1/user", api_key)
    print("\nUser Info:")
    print(f"  Name: {user.get('name')}")
    print(f"  Email: {user.get('email')}")
    print(f"  ID: {user.get('id')}")
    workspaces = api_get("https://api.clockify.me/api/v1/workspaces", api_key)
    print("\nWorkspaces:")
    for ws in workspaces:
        print(f"  Name: {ws.get('name')}, ID: {ws.get('id')}")

def date_interface(start_str: Optional[str] = None, end_str: Optional[str] = None, test_mode: bool = False, mode: str = "normal", week_start: int = 0, csv_prefix: Optional[str] = None, breakdown: bool = False, md_path: Optional[str] = None, overwrite: bool = False) -> None:
    today = date.today()
    if mode == "week":
        ref_date = datetime.strptime(start_str, "%Y-%m-%d").date() if start_str else today
        start_date, end_date = get_week_range(ref_date, week_start)
        # DEBUG: Print the week range used for the API call
        print(f"[DEBUG] Week mode: start_date={start_date} ({start_date.strftime('%A')}), end_date={end_date} ({end_date.strftime('%A')})")
    elif mode == "month":
        ref_date = datetime.strptime(start_str, "%Y-%m-%d").date() if start_str else today
        start_date, end_date = get_month_range(ref_date)
    else:
        start_str = start_str or prompt_for_date("Start date (YYYY-MM-DD)", today.isoformat())
        end_str = end_str or prompt_for_date("End date (YYYY-MM-DD)", today.isoformat())
        start_date = datetime.strptime(start_str, "%Y-%m-%d").date()
        end_date = datetime.strptime(end_str, "%Y-%m-%d").date()
    api_key = get_env_var("CLOCKIFY_API_KEY")
    workspace_id = get_env_var("CLOCKIFY_WORKSPACE_ID")
    user_id = get_env_var("CLOCKIFY_USER_ID")
    base_url = f"https://api.clockify.me/api/v1/workspaces/{workspace_id}/user/{user_id}/time-entries"
    params = {
        "start": iso_datetime(start_date),
        "end": iso_datetime(end_date, is_end=True)
    }
    entries = api_get(base_url, api_key, params, paginate=True)
    project_ids = {e.get("projectId") for e in entries if e.get("projectId")}
    project_id_to_name = {}
    if project_ids:
        projects_url = f"https://api.clockify.me/api/v1/workspaces/{workspace_id}/projects"
        projects = api_get(projects_url, api_key)
        for proj in projects:
            pid = proj.get("id")
            pname = proj.get("name", "No project")
            if pid:
                project_id_to_name[pid] = pname
    tags_url = f"https://api.clockify.me/api/v1/workspaces/{workspace_id}/tags"
    tags_data = api_get(tags_url, api_key)
    tag_id_to_name = {tag['id']: tag['name'] for tag in tags_data if 'id' in tag and 'name' in tag}
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
        tasks_url = f"https://api.clockify.me/api/v1/workspaces/{workspace_id}/projects/{pid}/tasks"
        try:
            tasks = api_get(tasks_url, api_key)
            for t in tasks:
                tid = t.get("id")
                tname = t.get("name")
                if tid and tname:
                    task_map[(pid, tid)] = tname
        except Exception:
            continue
    if test_mode:
        print("\nSample of resolved (projectId, taskId) -> taskName mapping:")
        for i, ((pid, tid), tname) in enumerate(task_map.items()):
            print(f"  Project: {project_id_to_name.get(pid, pid)} | TaskId: {tid} -> Task: {tname}")
            if i >= 4:
                break
    def build_table_rows(entries):
        table_rows = []
        project_durations = defaultdict(int)
        tag_durations = defaultdict(int)
        spontaneousity_durations = {"🎲": 0, "🗓️": 0}
        total_duration = 0
        for idx, entry in enumerate(sorted(entries, key=lambda e: e["timeInterval"]["start"])):
            label = idx + 1
            project_id = entry.get("projectId")
            task_id = entry.get("taskId")
            real_task_name = task_map.get((project_id, task_id), "") if project_id and task_id else ""
            subtask_name = entry.get("description") or entry.get("task", {}).get("name") or "No description"
            project = project_id_to_name.get(project_id, "No project")
            start = entry["timeInterval"]["start"]
            end = entry["timeInterval"].get("end", "")
            duration_sec = parse_clockify_duration(entry["timeInterval"].get("duration"))
            planned_sec = parse_planned_from_name(subtask_name)
            total_duration += duration_sec
            project_durations[project] += duration_sec
            tag_ids = entry.get("tagIds") or []
            tag_names = [tag_id_to_name.get(tid, tid) for tid in tag_ids]
            tags_str = ", ".join(tag_names) if tag_names else ""
            for tag in tag_names:
                tag_durations[tag] += duration_sec
            if "🎲" in subtask_name:
                spontaneousity_durations["🎲"] += duration_sec
            elif "🗓️" in subtask_name:
                spontaneousity_durations["🗓️"] += duration_sec
            def to_local_hm(dt_str: str) -> str:
                if not dt_str:
                    return ""
                try:
                    dt_utc = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
                    return dt_utc.astimezone().strftime("%H:%M")
                except Exception:
                    return ""
            start_hm = to_local_hm(start)
            end_hm = to_local_hm(end)
            duration_hm = f"{duration_sec // 3600:02}:{(duration_sec % 3600) // 60:02}"
            planned_hm = f"{planned_sec // 3600:02}:{(planned_sec % 3600) // 60:02}" if planned_sec else ""
            table_rows.append([
                label, subtask_name, real_task_name, project, planned_hm, start_hm, end_hm, duration_hm, "", tags_str, duration_sec
            ])
        return table_rows, project_durations, tag_durations, spontaneousity_durations, total_duration
    def percent(val, total):
        return f"{(val / total * 100):.0f}" if total else "0"
    def print_tables(table_rows, project_durations, tag_durations, spontaneousity_durations, total_duration, total_difference, date_range_str, csv_prefix=None, day_table=False, mode="normal"):
        # Determine the correct percent header
        if day_table:
            percent_header = "%/Day"
        elif mode == "week":
            percent_header = "%/Week"
        elif mode == "month":
            percent_header = "%/Month"
        else:
            percent_header = "%/Day"
        headers = ["#", "Task", "SubProject", "Project", "Planned", "Start", "End", "Duration", "Dur-Plan", "Tags", percent_header]
        # Dur-Plan logic
        task_groups = defaultdict(list)
        for idx, row in enumerate(table_rows):
            task_name = row[1]
            task_groups[task_name].append(idx)
        total_difference = 0
        for task_name, indices in task_groups.items():
            planned_sec = parse_planned_from_name(task_name)
            total_measured = sum(table_rows[i][-1] for i in indices)
            diff_sec = total_measured - planned_sec
            total_difference += diff_sec
            for i in indices[:-1]:
                table_rows[i][-3] = "00:00"
            if planned_sec:
                abs_diff = abs(diff_sec)
                diff_hm = f"{abs_diff // 3600:02}:{(abs_diff % 3600) // 60:02}"
                table_rows[indices[-1]][-3] = ("+" if diff_sec > 0 else "-") + diff_hm if diff_sec != 0 else "00:00"
            else:
                table_rows[indices[-1]][-3] = ""
        table_rows_with_ratio = [row[:-1] + [percent(row[-1], total_duration)] for row in table_rows]
        if day_table:
            print(f"\n### Time Entries {date_range_str}:")
            print(tabulate(table_rows_with_ratio, headers=headers, tablefmt="github"))
        elif day_table is None:
            pass  # skip
        else:
            print(f"\n### Time Entries {date_range_str}:")
            print(tabulate(table_rows_with_ratio, headers=headers, tablefmt="github"))
        if csv_prefix:
            write_csv(f"{csv_prefix}_entries.csv", headers, [row[:-1] + [percent(row[-1], total_duration)] for row in table_rows])
        # SubProject Table (before Project Table)
        subproject_durations = defaultdict(int)
        for row in table_rows:
            subproject, project, duration_sec = row[2], row[3], row[-1]
            key = (subproject, project)
            subproject_durations[key] += duration_sec
        if subproject_durations:
            subproject_table = [
                [subproject, project, percent(secs, total_duration), f"{secs // 3600:02}:{(secs % 3600) // 60:02}"]
                for (subproject, project), secs in subproject_durations.items()
            ]
            # Sort by duration (descending)
            subproject_table.sort(key=lambda x: int(x[3][:2])*60 + int(x[3][3:]), reverse=True)
            print(f"\n### Time by SubProject {date_range_str}:")
            print(tabulate(subproject_table, headers=["SubProject", "Project", "%/Day", "Duration"], tablefmt="github"))
            if csv_prefix:
                write_csv(f"{csv_prefix}_subprojects.csv", ["SubProject", "Project", "%/Day", "Duration"], subproject_table)
        # Project Table
        print_proj_header = percent_header
        proj_table = [
            [proj, percent(secs, total_duration), f"{secs // 3600:02}:{(secs % 3600) // 60:02}"] for proj, secs in sorted(project_durations.items())
        ]
        print(f"\n### Time by Project {date_range_str}:")
        print(tabulate(proj_table, headers=["Project", print_proj_header, "Duration"], tablefmt="github"))
        if csv_prefix:
            write_csv(f"{csv_prefix}_projects.csv", ["Project", print_proj_header, "Duration"], proj_table)
        # Tag Table
        if tag_durations:
            print(f"\n### Time by Tag {date_range_str}:")
            custom_tag_order = ["🚨 & 🍭", "🚨 & 🥵", "🐢 & 🍭", "🐢 & 🥵"]
            def tag_sort_key(item):
                tag = item[0]
                if tag in custom_tag_order:
                    return (custom_tag_order.index(tag), tag)
                return (len(custom_tag_order), tag)
            tag_table = [
                [tag, percent(secs, total_duration), f"{secs // 3600:02}:{(secs % 3600) // 60:02}"] for tag, secs in tag_durations.items()
            ]
            tag_table.sort(key=tag_sort_key)
            print(tabulate(tag_table, headers=["Tag", percent_header, "ΣDuration"], tablefmt="github"))
            if csv_prefix:
                write_csv(f"{csv_prefix}_tags.csv", ["Tag", percent_header, "ΣDuration"], tag_table)
        # Spontaneousity Table
        spont_total = sum(spontaneousity_durations.values())
        if spont_total > 0:
            print(f"\n### Spontaneousity {date_range_str}:")
            spont_order = ["🗓️", "🎲"]
            spont_table = [
                [symbol, percent(secs, spont_total), f"{secs // 3600:02}:{(secs % 3600) // 60:02}"] for symbol, secs in spontaneousity_durations.items() if secs > 0
            ]
            spont_table.sort(key=lambda row: spont_order.index(row[0]) if row[0] in spont_order else len(spont_order))
            print(tabulate(spont_table, headers=["🎲/🗓️", percent_header, "Duration"], tablefmt="github"))
            if csv_prefix:
                write_csv(f"{csv_prefix}_spont.csv", ["🎲/🗓️", percent_header, "Duration"], spont_table)
        # Totals Table (replaces ASCII art)
        print(f"\n### Totals {date_range_str}:")
        # Dur-Plan total: sum of abs differences per task
        abs_total_difference = 0
        for task_name, indices in task_groups.items():
            planned_sec = parse_planned_from_name(task_name)
            total_measured = sum(table_rows[i][-1] for i in indices)
            abs_total_difference += abs(total_measured - planned_sec)
        totals_table = []
        totals_table.append(["ΣDuration", "0%", f"{total_duration // 3600:02}:{(total_duration % 3600) // 60:02}"])
        if abs_total_difference != 0:
            abs_diff = abs_total_difference
            diff_h = abs_diff // 3600
            diff_m = (abs_diff % 3600) // 60
            measured_result_str = f"{diff_h:02}:{diff_m:02}"
            percent_deviation = f"{(abs_total_difference / total_duration * 100):.0f}%" if total_duration else "0%"
        else:
            measured_result_str = "00:00"
            percent_deviation = "0%"
        totals_table.append(["Dur-Plan Total", percent_deviation,measured_result_str])
        print(tabulate(totals_table, headers=["Total", "% Dev", "h:mm"], tablefmt="github"))
        if csv_prefix:
            write_csv(f"{csv_prefix}_totals.csv", ["Total", "% Dev", "h:mm"], totals_table)
        print()  # extra newline
    # --- Mode logic ---
    import io
    md_buffer = io.StringIO() if md_path else None
    def print_tables_md(*args, **kwargs):
        # Capture print output as markdown code block
        import contextlib
        if md_buffer:
            with contextlib.redirect_stdout(md_buffer):
                print_tables(*args, **kwargs)
        else:
            print_tables(*args, **kwargs)
    if mode == "week":
        entries_by_day = defaultdict(list)
        for e in entries:
            day = datetime.fromisoformat(e["timeInterval"]["start"].replace("Z", "+00:00")).date()
            entries_by_day[day].append(e)
        all_table_rows, all_proj, all_tag, all_spont, all_total = [], defaultdict(int), defaultdict(int), {"🎲":0,"🗓️":0}, 0
        if breakdown:
            for i in range(7):
                day = start_date + timedelta(days=i)
                table_rows, project_durations, tag_durations, spontaneousity_durations, total_duration = build_table_rows(entries_by_day[day])
                date_range_str = day_str(day)
                print_tables_md(table_rows, project_durations, tag_durations, spontaneousity_durations, total_duration, 0, date_range_str, csv_prefix, day_table=True, mode=mode)
                for k,v in project_durations.items(): all_proj[k]+=v
                for k,v in tag_durations.items(): all_tag[k]+=v
                for k,v in spontaneousity_durations.items(): all_spont[k]+=v
                all_total += total_duration
                all_table_rows.extend(table_rows)
        else:
            for day in sorted(entries_by_day):
                table_rows, project_durations, tag_durations, spontaneousity_durations, total_duration = build_table_rows(entries_by_day[day])
                for k,v in project_durations.items(): all_proj[k]+=v
                for k,v in tag_durations.items(): all_tag[k]+=v
                for k,v in spontaneousity_durations.items(): all_spont[k]+=v
                all_total += total_duration
                all_table_rows.extend(table_rows)
        # Print summary for the week
        print_tables_md(all_table_rows, all_proj, all_tag, all_spont, all_total, 0, f"{day_str(start_date)} to {day_str(end_date)}", csv_prefix, day_table=None, mode=mode)
    elif mode == "month":
        table_rows, project_durations, tag_durations, spontaneousity_durations, total_duration = build_table_rows(entries)
        print_tables_md(table_rows, project_durations, tag_durations, spontaneousity_durations, total_duration, 0, f"{day_str(start_date)} to {day_str(end_date)}", csv_prefix, day_table=None, mode=mode)
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
                week_entries = [e for e in entries if wstart <= datetime.fromisoformat(e["timeInterval"]["start"].replace("Z", "+00:00")).date() <= wend]
                if not week_entries: continue
                table_rows, project_durations, tag_durations, spontaneousity_durations, total_duration = build_table_rows(week_entries)
                print_tables_md(table_rows, project_durations, tag_durations, spontaneousity_durations, total_duration, 0, f"{day_str(wstart)} to {day_str(wend)}", csv_prefix, day_table=None, mode=mode)
    else:
        table_rows, project_durations, tag_durations, spontaneousity_durations, total_duration = build_table_rows(entries)
        print_tables_md(table_rows, project_durations, tag_durations, spontaneousity_durations, total_duration, 0, f"{day_str(start_date)} to {day_str(end_date)}", csv_prefix, mode=mode)
    # If markdown output requested, write to file
    if md_path:
        md_content = f"\n{md_buffer.getvalue()}\n"
        write_markdown(md_path, md_content, start_date, end_date, overwrite)
        print(f"[SUCCESS] Markdown output written to '{md_path}'")
        sys.exit(0)

def main() -> None:
    args = parse_args()
    if args.list:
        list_user_and_workspaces()
    else:
        date_interface(args.start, args.end, getattr(args, 'test', False), args.mode, args.weekstart, args.csv, args.breakdown, getattr(args, 'md', None), getattr(args, 'overwrite', False))

if __name__ == "__main__":
    main()