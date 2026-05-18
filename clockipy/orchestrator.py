"""Report orchestration: turn raw API data into per-mode report output.

This module is the seam between the CLI layer and the API/report layers.
Each public function is independently testable with a mocked
:class:`ClockifyClient`.
"""
from __future__ import annotations

import calendar as cal
import io
import logging
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Callable, Dict, List, Optional

from .api.client import ClockifyClient
from .env import get_env_var, resolve_user_id
from .reports.report_generator import ReportGenerator
from .reports.time_entry import TimeEntry
from .store import Cache, default_db_path
from .utils.date_utils import day_str, get_month_range, get_week_range, get_year_range
from .utils.file_utils import write_markdown

log = logging.getLogger(__name__)


# ---- date-range resolution -------------------------------------------------

def resolve_date_range(
    mode: str,
    start_str: Optional[str],
    end_str: Optional[str],
    week_start: int,
    prompt: Optional[Callable[[str, str], str]] = None,
) -> tuple[date, date]:
    """Resolve the date range for ``mode``.

    ``prompt`` is injected to keep this function side-effect-free in tests.
    """
    today = date.today()
    if mode == "week":
        ref = datetime.strptime(start_str, "%Y-%m-%d").date() if start_str else today
        return get_week_range(ref, week_start)
    if mode == "month":
        ref = datetime.strptime(start_str, "%Y-%m-%d").date() if start_str else today
        return get_month_range(ref)
    if mode == "year":
        ref = datetime.strptime(start_str, "%Y-%m-%d").date() if start_str else today
        return get_year_range(ref)
    # normal mode
    if not start_str:
        if prompt is None:
            print("--start is required in normal mode.", file=sys.stderr)
            sys.exit(2)
        start_str = prompt("Start date (YYYY-MM-DD)", today.isoformat())
    if not end_str:
        end_str = prompt("End date (YYYY-MM-DD)", today.isoformat()) if prompt else start_str
    return (
        datetime.strptime(start_str, "%Y-%m-%d").date(),
        datetime.strptime(end_str, "%Y-%m-%d").date(),
    )


# ---- entry construction ----------------------------------------------------

def build_time_entries(
    raw_entries: List[Dict],
    project_id_to_name: Dict[str, str],
    tag_id_to_name: Dict[str, str],
    task_map: Dict[tuple, str],
) -> List[TimeEntry]:
    """Convert raw API entries into ``TimeEntry`` objects, sorted by start."""
    sorted_entries = sorted(raw_entries, key=lambda x: x["timeInterval"]["start"])
    out: List[TimeEntry] = []
    for idx, e in enumerate(sorted_entries, start=1):
        project_id = e.get("projectId")
        task_id = e.get("taskId")
        project_name = project_id_to_name.get(project_id, "No project")
        task_name = (
            task_map.get((project_id, task_id), "")
            if project_id and task_id
            else ""
        )
        tag_ids = e.get("tagIds") or []
        tag_names = [tag_id_to_name.get(tid, tid) for tid in tag_ids]
        out.append(TimeEntry(e, idx, project_name, task_name, tag_names))
    return out


# ---- entry-day grouping (local timezone) -----------------------------------

def _entry_local_date(raw: dict) -> date:
    iso = raw["timeInterval"]["start"]
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone().date()


# ---- public entrypoints ----------------------------------------------------

def list_user_and_workspaces() -> None:
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


def _load_or_fetch(
    client: ClockifyClient,
    start_date: date,
    end_date: date,
    cache: Optional[Cache],
    force_refresh: bool,
) -> tuple[list, Dict[str, str], Dict[str, str], Dict[tuple, str]]:
    """Return (entries, projects, tags, tasks) using cache when fresh.

    Refresh policy: if a cache is provided AND (force_refresh is False) AND
    the cache is fresh for the requested range, serve everything from cache.
    Otherwise fetch from the API and update the cache.
    """
    if cache is not None and not force_refresh and cache.is_fresh(start_date, end_date):
        log.info("Cache hit for %s..%s", start_date, end_date)
        entries = cache.get_entries(start_date, end_date)
        if entries:
            return (
                entries,
                cache.get_project_map(),
                cache.get_tag_map(),
                cache.get_task_map(),
            )
        log.info("Cache marked fresh but contained no entries; refetching.")

    log.info("Fetching entries from Clockify API (%s..%s)", start_date, end_date)
    entries = client.get_time_entries(start_date, end_date)
    if not entries:
        if cache is not None:
            cache.record_sync(start_date, end_date)
        return [], {}, {}, {}

    project_map, tag_map, task_map = client.get_project_and_tag_mappings(entries)
    if cache is not None:
        cache.upsert_entries(entries)
        cache.upsert_projects(project_map)
        cache.upsert_tags(tag_map)
        cache.upsert_tasks(task_map)
        cache.record_sync(start_date, end_date)
    return entries, project_map, tag_map, task_map


def date_interface(
    start_str: Optional[str] = None,
    end_str: Optional[str] = None,
    test_mode: bool = False,
    mode: str = "normal",
    week_start: int = 0,
    csv_prefix: Optional[str] = None,
    breakdown: bool = False,
    md_path: Optional[str] = None,
    overwrite: bool = False,
    *,
    client: Optional[ClockifyClient] = None,
    prompt: Optional[Callable[[str, str], str]] = None,
    cache: Optional[Cache] = None,
    use_cache: bool = True,
    force_refresh: bool = False,
) -> None:
    """Main interface for date-based reports.

    Injection points: ``client``, ``prompt``, and ``cache`` keep this fully
    testable. ``use_cache=False`` disables caching entirely; ``force_refresh``
    bypasses the freshness check but still writes back.
    """
    start_date, end_date = resolve_date_range(mode, start_str, end_str, week_start, prompt)

    if mode == "week":
        print(f"📅 Week: {day_str(start_date)} to {day_str(end_date)}")
    elif mode == "month":
        print(f"📅 Month: {day_str(start_date)} to {day_str(end_date)}")
    elif mode == "year":
        print(f"📅 Year {start_date.year}: {day_str(start_date)} to {day_str(end_date)}")

    if client is None:
        api_key = get_env_var("CLOCKIFY_API_KEY")
        workspace_id = get_env_var("CLOCKIFY_WORKSPACE_ID")
        user_id = resolve_user_id(api_key, workspace_id)
        client = ClockifyClient(api_key, workspace_id, user_id)
        if cache is None and use_cache:
            cache = Cache(default_db_path(workspace_id, user_id))
            cache_owned_here = True
        else:
            cache_owned_here = False
    elif cache is None and use_cache and getattr(client, "workspace_id", None) and getattr(client, "user_id", None):
        cache = Cache(default_db_path(client.workspace_id, client.user_id))
        cache_owned_here = True
    else:
        cache_owned_here = False

    try:
        _date_interface_body(
            client, cache, force_refresh,
            start_date, end_date, mode, week_start, breakdown,
            csv_prefix, md_path, overwrite, test_mode,
        )
    finally:
        if cache_owned_here and cache is not None:
            cache.close()


def _date_interface_body(
    client, cache, force_refresh,
    start_date, end_date, mode, week_start, breakdown,
    csv_prefix, md_path, overwrite, test_mode,
):
    entries, project_id_to_name, tag_id_to_name, task_map = _load_or_fetch(
        client, start_date, end_date, cache, force_refresh,
    )
    if not entries:
        print(f"\n⚠️  No time entries found for {day_str(start_date)} to {day_str(end_date)}")
        return

    print(f"📊 Found {len(entries)} time entries")

    if test_mode:
        print("\nSample of resolved (projectId, taskId) -> taskName mapping:")
        for i, ((pid, tid), tname) in enumerate(task_map.items()):
            print(f"  Project: {project_id_to_name.get(pid, pid)} | TaskId: {tid} -> Task: {tname}")
            if i >= 4:
                break

    md_buffer = io.StringIO() if md_path else None

    def emit(report: str) -> None:
        if md_buffer is not None:
            md_buffer.write(report)
        else:
            print(report)

    if mode == "week":
        _render_week(
            entries, start_date, end_date, week_start, breakdown,
            project_id_to_name, tag_id_to_name, task_map,
            csv_prefix, emit, mode,
        )
    elif mode == "month":
        _render_month(
            entries, start_date, end_date, week_start, breakdown,
            project_id_to_name, tag_id_to_name, task_map,
            csv_prefix, emit, mode,
        )
    elif mode == "year":
        _render_year(
            entries, start_date, end_date, breakdown,
            project_id_to_name, tag_id_to_name, task_map,
            csv_prefix, emit, mode,
        )
    else:
        time_entries = build_time_entries(entries, project_id_to_name, tag_id_to_name, task_map)
        date_range_str = f"{day_str(start_date)} to {day_str(end_date)}"
        rg = ReportGenerator(time_entries, date_range_str, mode)
        emit(rg.generate_report(csv_prefix))

    if md_path:
        assert md_buffer is not None
        md_content = f"\n{md_buffer.getvalue()}\n"
        write_markdown(md_path, md_content, start_date, end_date, overwrite)
        print(f"[SUCCESS] Markdown output written to '{md_path}'")
        sys.exit(0)


# ---- mode renderers --------------------------------------------------------

def _render_week(entries, start_date, end_date, week_start, breakdown,
                 project_id_to_name, tag_id_to_name, task_map,
                 csv_prefix, emit, mode):
    entries_by_day: Dict[date, list] = defaultdict(list)
    for e in entries:
        entries_by_day[_entry_local_date(e)].append(e)

    all_time_entries: List[TimeEntry] = []
    if breakdown:
        for i in range(7):
            day = start_date + timedelta(days=i)
            if day not in entries_by_day:
                continue
            day_entries = build_time_entries(
                entries_by_day[day], project_id_to_name, tag_id_to_name, task_map
            )
            all_time_entries.extend(day_entries)
            rg = ReportGenerator(day_entries, day_str(day), mode)
            emit(rg.generate_report(csv_prefix, day_table=True))
    else:
        all_time_entries = build_time_entries(
            entries, project_id_to_name, tag_id_to_name, task_map
        )

    date_range_str = f"{day_str(start_date)} to {day_str(end_date)}"
    rg = ReportGenerator(all_time_entries, date_range_str, mode)
    emit(rg.generate_report(csv_prefix, day_table=None))


def _render_month(entries, start_date, end_date, week_start, breakdown,
                  project_id_to_name, tag_id_to_name, task_map,
                  csv_prefix, emit, mode):
    time_entries = build_time_entries(entries, project_id_to_name, tag_id_to_name, task_map)
    date_range_str = f"{day_str(start_date)} to {day_str(end_date)}"
    rg = ReportGenerator(time_entries, date_range_str, mode)
    emit(rg.generate_report(csv_prefix, day_table=None))

    if not breakdown:
        return

    first_week_start, _ = get_week_range(start_date, week_start)
    _, last_week_end = get_week_range(end_date, week_start)
    week_ranges = []
    d = first_week_start
    while d <= last_week_end:
        wstart = d
        wend = d + timedelta(days=6)
        week_ranges.append((max(wstart, start_date), min(wend, end_date)))
        d += timedelta(days=7)

    for wstart, wend in week_ranges:
        week_entries = [
            te for te in time_entries
            if wstart <= _entry_local_date(te.raw_data) <= wend
        ]
        if not week_entries:
            continue
        date_range_str = f"{day_str(wstart)} to {day_str(wend)}"
        rg = ReportGenerator(week_entries, date_range_str, mode)
        emit(rg.generate_report(csv_prefix, day_table=None))


def _render_year(entries, start_date, end_date, breakdown,
                 project_id_to_name, tag_id_to_name, task_map,
                 csv_prefix, emit, mode):
    time_entries = build_time_entries(entries, project_id_to_name, tag_id_to_name, task_map)
    date_range_str = f"{day_str(start_date)} to {day_str(end_date)}"
    rg = ReportGenerator(time_entries, date_range_str, mode)
    emit(rg.generate_report(csv_prefix, day_table=None))

    if not breakdown:
        return

    year = start_date.year
    for month in range(1, 13):
        month_start = date(year, month, 1)
        month_end = date(year, month, cal.monthrange(year, month)[1])
        month_entries = [
            te for te in time_entries
            if month_start <= _entry_local_date(te.raw_data) <= month_end
        ]
        if not month_entries:
            continue
        date_range_str = f"{day_str(month_start)} to {day_str(month_end)}"
        rg = ReportGenerator(month_entries, date_range_str, "month")
        emit(rg.generate_report(csv_prefix, day_table=None))
