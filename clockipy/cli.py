"""CLI entry point for clockiPy."""
from __future__ import annotations

import argparse
import logging

from .env import get_env_var, load_environment, resolve_user_id
from .orchestrator import date_interface, list_user_and_workspaces

EPILOG = """
Examples:
  clockipy --start 2026-05-15 --end 2026-05-22
  clockipy --mode week --start 2026-05-15
  clockipy --mode month --start 2026-05-15 --breakdown --csv june
  clockipy --mode year --start 2026-01-01
  clockipy --goals                # show goals + this-week burn-down
  clockipy --digest               # weekly digest (uses cache only)
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fetch and display Clockify time entries in a clean table.",
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        prog="clockipy",
    )
    parser.add_argument("-l", "--list", action="store_true",
                        help="List user and workspaces with their IDs")
    parser.add_argument("--start", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", help="End date (YYYY-MM-DD)")
    parser.add_argument("--mode", choices=["normal", "week", "month", "year"],
                        default="normal",
                        help="Summary mode (default: normal)")
    parser.add_argument("--weekstart", type=int, choices=range(0, 7), default=0,
                        help="Week start day: 0=Mon, 6=Sun (default: 0)")
    parser.add_argument("--csv", help="Export main tables to CSV (filename prefix)")
    parser.add_argument("--breakdown", action="store_true",
                        help="Add per-week breakdown (month) or per-month (year)")
    parser.add_argument("--test", action="store_true",
                        help="Print sample of task mapping for verification")
    parser.add_argument("--md", help="Export output as markdown to the given file path")
    parser.add_argument("--overwrite", action="store_true",
                        help="Overwrite the markdown file if it exists (DANGEROUS)")
    parser.add_argument("-v", "--verbose", action="count", default=0,
                        help="Increase log verbosity (-v INFO, -vv DEBUG)")
    parser.add_argument("-q", "--quiet", action="store_true",
                        help="Only emit warnings and errors")
    parser.add_argument("--refresh", action="store_true",
                        help="Bypass the cache and refetch from the Clockify API")
    parser.add_argument("--no-cache", action="store_true",
                        help="Disable the SQLite cache entirely for this run")
    parser.add_argument("--goals", action="store_true",
                        help="Print configured goals and this-week burn-down")
    parser.add_argument("--digest", action="store_true",
                        help="Print a weekly digest with anomaly callouts (from cache)")
    return parser


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    return build_parser().parse_args(argv)


def configure_logging(verbose: int, quiet: bool) -> None:
    if quiet:
        level = logging.WARNING
    elif verbose >= 2:
        level = logging.DEBUG
    elif verbose >= 1:
        level = logging.INFO
    else:
        level = logging.WARNING
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        force=True,
    )


def _open_cache():
    """Open the cache for this user/workspace (CLI helper)."""
    from .store import Cache, default_db_path

    api_key = get_env_var("CLOCKIFY_API_KEY")
    workspace_id = get_env_var("CLOCKIFY_WORKSPACE_ID")
    user_id = resolve_user_id(api_key, workspace_id)
    return Cache(default_db_path(workspace_id, user_id))


def run_goals() -> None:
    """Print configured goals and this-week burn-down."""
    from datetime import date

    from tabulate import tabulate

    from .digest import (
        _sum_hours_by_dim,  # internal helper, intentional
        iso_week_bounds,
    )
    from .goals import Goals, compute_burn_down

    goals = Goals.load()
    cache = _open_cache()
    week_start, week_end = iso_week_bounds(date.today())
    entries = cache.get_entries(week_start, week_end)
    proj_hours, tag_hours, total = _sum_hours_by_dim(
        entries, cache.get_project_map(), cache.get_tag_map(),
    )
    items = compute_burn_down(goals, proj_hours, tag_hours, total)

    print(f"# Goals — week of {week_start} → {week_end}")
    if not items:
        print("\n_No goals configured. Create ~/.config/clockipy/goals.yml._")
        return
    rows = [
        [i.label, f"{i.target_hours:.1f}", f"{i.actual_hours:.2f}",
         f"{i.remaining_hours:+.2f}", f"{i.percent_complete:.0f}%", i.status]
        for i in items
    ]
    print(tabulate(
        rows,
        headers=["Dimension", "Target (h)", "Actual (h)", "Remaining", "%", "Status"],
        tablefmt="github",
    ))


def run_digest() -> None:
    """Print the weekly digest from cached data only."""
    from .digest import build_digest, render_digest

    cache = _open_cache()
    print(render_digest(build_digest(cache)))


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    configure_logging(args.verbose, args.quiet)
    load_environment()

    if args.list:
        list_user_and_workspaces()
        return

    if args.goals:
        run_goals()
        return

    if args.digest:
        run_digest()
        return

    date_interface(
        args.start, args.end, args.test,
        args.mode, args.weekstart, args.csv, args.breakdown,
        args.md, args.overwrite,
        use_cache=not args.no_cache,
        force_refresh=args.refresh,
    )


if __name__ == "__main__":  # pragma: no cover
    main()
