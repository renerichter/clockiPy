"""Weekly digest: actuals + Δ vs 4-week rolling median, anomaly callouts.

A "digest" is a compact summary of the user's most recent ISO week. It
reuses cached entries to compute, for each project and tag:

- ``actual_hours`` — sum of duration this week
- ``median_4w_hours`` — median of the same metric across the prior 4 ISO weeks
- ``delta_hours`` and ``delta_pct`` vs that median
- ``is_anomaly`` — |delta_pct| > 25% AND we have at least 2 prior weeks

The digest never calls the API; it operates entirely on a ``Cache``.
"""
from __future__ import annotations

import logging
import statistics
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

from .store import Cache
from .utils.format_utils import parse_clockify_duration

log = logging.getLogger(__name__)

ANOMALY_THRESHOLD_PCT = 25.0
LOOKBACK_WEEKS = 4
MIN_HISTORY_FOR_ANOMALY = 2


@dataclass
class DigestRow:
    label: str            # "project: Foo" or "tag: bar"
    actual_hours: float
    median_4w_hours: Optional[float]
    delta_hours: Optional[float]
    delta_pct: Optional[float]
    is_anomaly: bool


@dataclass
class Digest:
    week_start: date
    week_end: date
    total_hours: float
    rows: List[DigestRow]
    history_weeks_available: int

    @property
    def anomalies(self) -> List[DigestRow]:
        return [r for r in self.rows if r.is_anomaly]


def iso_week_bounds(ref: date) -> tuple[date, date]:
    """Return Monday..Sunday bounds for the ISO week containing ``ref``."""
    monday = ref - timedelta(days=ref.weekday())
    return monday, monday + timedelta(days=6)


def _entry_local_date(entry: dict) -> date:
    iso = entry["timeInterval"]["start"]
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone().date()


def _sum_hours_by_dim(
    entries: Iterable[dict],
    project_map: Dict[str, str],
    tag_map: Dict[str, str],
) -> tuple[Dict[str, float], Dict[str, float], float]:
    """Return (project_hours, tag_hours, total_hours) for the entries."""
    by_project: Dict[str, float] = defaultdict(float)
    by_tag: Dict[str, float] = defaultdict(float)
    total_seconds = 0
    for e in entries:
        seconds = parse_clockify_duration(e.get("timeInterval", {}).get("duration"))
        total_seconds += seconds
        pid = e.get("projectId")
        if pid:
            name = project_map.get(pid, pid)
            by_project[name] += seconds / 3600.0
        for tid in e.get("tagIds") or []:
            tname = tag_map.get(tid, tid)
            by_tag[tname] += seconds / 3600.0
    return dict(by_project), dict(by_tag), total_seconds / 3600.0


def _delta_pct(actual: float, median: float) -> Optional[float]:
    if median <= 0:
        return None
    return ((actual - median) / median) * 100.0


def build_digest(
    cache: Cache,
    ref: Optional[date] = None,
    lookback_weeks: int = LOOKBACK_WEEKS,
    anomaly_threshold_pct: float = ANOMALY_THRESHOLD_PCT,
) -> Digest:
    """Build the weekly digest using only data already in ``cache``."""
    ref = ref or date.today()
    week_start, week_end = iso_week_bounds(ref)

    project_map = cache.get_project_map()
    tag_map = cache.get_tag_map()

    this_entries = cache.get_entries(week_start, week_end)
    by_proj_now, by_tag_now, total_now = _sum_hours_by_dim(
        this_entries, project_map, tag_map,
    )

    history_proj: Dict[str, List[float]] = defaultdict(list)
    history_tag: Dict[str, List[float]] = defaultdict(list)
    history_count = 0
    for i in range(1, lookback_weeks + 1):
        hist_start = week_start - timedelta(days=7 * i)
        hist_end = hist_start + timedelta(days=6)
        hist_entries = cache.get_entries(hist_start, hist_end)
        if not hist_entries:
            continue
        history_count += 1
        proj_h, tag_h, _ = _sum_hours_by_dim(hist_entries, project_map, tag_map)
        for name, hours in proj_h.items():
            history_proj[name].append(hours)
        for name, hours in tag_h.items():
            history_tag[name].append(hours)

    def row(label_prefix: str, name: str, actual: float,
            history: Dict[str, List[float]]) -> DigestRow:
        hist = history.get(name, [])
        if not hist:
            return DigestRow(f"{label_prefix}: {name}", actual, None, None, None, False)
        median = statistics.median(hist)
        delta = actual - median
        pct = _delta_pct(actual, median)
        is_anomaly = (
            history_count >= MIN_HISTORY_FOR_ANOMALY
            and pct is not None
            and abs(pct) > anomaly_threshold_pct
        )
        return DigestRow(
            f"{label_prefix}: {name}", actual, median, delta, pct, is_anomaly,
        )

    # Union of names seen this week or in history.
    proj_names = sorted(set(by_proj_now) | set(history_proj))
    tag_names = sorted(set(by_tag_now) | set(history_tag))

    rows: List[DigestRow] = []
    for name in proj_names:
        rows.append(row("project", name, by_proj_now.get(name, 0.0), history_proj))
    for name in tag_names:
        rows.append(row("tag", name, by_tag_now.get(name, 0.0), history_tag))

    return Digest(
        week_start=week_start,
        week_end=week_end,
        total_hours=total_now,
        rows=rows,
        history_weeks_available=history_count,
    )


def render_digest(digest: Digest) -> str:
    """Render the digest as a markdown-friendly string."""
    from tabulate import tabulate

    lines: list[str] = []
    lines.append(f"# Weekly Digest — {digest.week_start} → {digest.week_end}")
    lines.append("")
    lines.append(f"**Total tracked:** {digest.total_hours:.2f} h")
    lines.append(f"**History available:** {digest.history_weeks_available} prior week(s)")
    lines.append("")

    if not digest.rows:
        lines.append("_No entries this week and no historical context._")
        return "\n".join(lines)

    table = []
    for r in digest.rows:
        median = "—" if r.median_4w_hours is None else f"{r.median_4w_hours:.2f}"
        delta = "—" if r.delta_hours is None else f"{r.delta_hours:+.2f}"
        pct = "—" if r.delta_pct is None else f"{r.delta_pct:+.1f}%"
        flag = "⚠️" if r.is_anomaly else ""
        table.append([r.label, f"{r.actual_hours:.2f}", median, delta, pct, flag])
    lines.append(tabulate(
        table,
        headers=["Dimension", "This wk (h)", "4w median", "Δ h", "Δ %", ""],
        tablefmt="github",
    ))

    if digest.anomalies:
        lines.append("")
        lines.append("## ⚠️  Anomalies")
        for r in digest.anomalies:
            direction = "above" if (r.delta_pct or 0) > 0 else "below"
            lines.append(
                f"- **{r.label}**: {r.actual_hours:.2f}h is "
                f"{abs(r.delta_pct or 0):.1f}% {direction} the 4-week median "
                f"({r.median_4w_hours:.2f}h)."
            )
    elif digest.history_weeks_available < MIN_HISTORY_FOR_ANOMALY:
        lines.append("")
        lines.append(
            "_Anomaly detection needs at least "
            f"{MIN_HISTORY_FOR_ANOMALY} prior weeks of cached data._"
        )

    return "\n".join(lines)
