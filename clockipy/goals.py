"""Goals configuration & weekly burn-down/digest support.

Schema (``~/.config/clockipy/goals.yml``)::

    weekly_hours: 35       # optional total target
    projects:              # optional mapping of project name -> weekly hours
      "Project One": 10
      "Project Two": 5
    tags:                  # optional mapping of tag name -> weekly hours
      "deep-work": 12

All keys are optional; absent goals simply emit no recommendation.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

log = logging.getLogger(__name__)


def _xdg_config_home() -> Path:
    raw = os.environ.get("XDG_CONFIG_HOME")
    if raw:
        return Path(raw)
    return Path.home() / ".config"


def default_goals_path() -> Path:
    return _xdg_config_home() / "clockipy" / "goals.yml"


@dataclass
class Goals:
    """Parsed goals configuration."""

    weekly_hours: Optional[float] = None
    projects: Dict[str, float] = field(default_factory=dict)
    tags: Dict[str, float] = field(default_factory=dict)

    @classmethod
    def empty(cls) -> Goals:
        return cls()

    @classmethod
    def load(cls, path: Optional[Path] = None) -> Goals:
        """Load goals from ``path`` (default: XDG config). Missing file → empty goals."""
        p = Path(path) if path else default_goals_path()
        if not p.exists():
            return cls.empty()
        try:
            with open(p, encoding="utf-8") as f:
                raw = yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in goals file '{p}': {e}") from e
        return cls.from_dict(raw)

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> Goals:
        if not isinstance(raw, dict):
            raise ValueError(
                f"goals.yml must be a mapping at the top level, got {type(raw).__name__}"
            )
        weekly_hours = raw.get("weekly_hours")
        if weekly_hours is not None and not isinstance(weekly_hours, (int, float)):
            raise ValueError("weekly_hours must be a number")
        projects = _coerce_str_to_number(raw.get("projects") or {}, "projects")
        tags = _coerce_str_to_number(raw.get("tags") or {}, "tags")
        return cls(
            weekly_hours=float(weekly_hours) if weekly_hours is not None else None,
            projects=projects,
            tags=tags,
        )


def _coerce_str_to_number(mapping: Any, label: str) -> Dict[str, float]:
    if not isinstance(mapping, dict):
        raise ValueError(f"{label} must be a mapping of name -> hours")
    out: Dict[str, float] = {}
    for k, v in mapping.items():
        if not isinstance(k, str):
            raise ValueError(f"{label} keys must be strings (got {type(k).__name__})")
        if not isinstance(v, (int, float)):
            raise ValueError(f"{label}[{k!r}] must be a number, got {type(v).__name__}")
        out[k] = float(v)
    return out


# ---- burn-down math --------------------------------------------------------

@dataclass
class BurnDownItem:
    label: str
    target_hours: float
    actual_hours: float

    @property
    def remaining_hours(self) -> float:
        return self.target_hours - self.actual_hours

    @property
    def percent_complete(self) -> float:
        if self.target_hours <= 0:
            return 0.0
        return min(100.0, (self.actual_hours / self.target_hours) * 100.0)

    @property
    def status(self) -> str:
        if self.target_hours <= 0:
            return "—"
        pct = self.percent_complete
        if pct >= 100:
            return "✅ complete"
        if pct >= 75:
            return "🟢 on track"
        if pct >= 50:
            return "🟡 behind"
        return "🔴 at risk"


def compute_burn_down(
    goals: Goals,
    actual_by_project: Dict[str, float],
    actual_by_tag: Dict[str, float],
    actual_total_hours: float,
) -> list[BurnDownItem]:
    """Return ordered burn-down items: total first, then projects, then tags."""
    items: list[BurnDownItem] = []
    if goals.weekly_hours is not None:
        items.append(BurnDownItem("TOTAL", goals.weekly_hours, actual_total_hours))
    for name, target in sorted(goals.projects.items()):
        items.append(BurnDownItem(
            f"project: {name}", target, actual_by_project.get(name, 0.0),
        ))
    for name, target in sorted(goals.tags.items()):
        items.append(BurnDownItem(
            f"tag: {name}", target, actual_by_tag.get(name, 0.0),
        ))
    return items
