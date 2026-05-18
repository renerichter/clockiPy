"""Tests for goals.yml loading and burn-down math."""
from __future__ import annotations

import pytest

from clockipy.goals import (
    BurnDownItem,
    Goals,
    compute_burn_down,
    default_goals_path,
)


def test_default_goals_path_honors_xdg(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert default_goals_path() == tmp_path / "clockipy" / "goals.yml"


def test_default_goals_path_falls_back_to_home_config(monkeypatch, tmp_path):
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    assert default_goals_path() == tmp_path / ".config" / "clockipy" / "goals.yml"


def test_missing_file_returns_empty_goals(tmp_path):
    g = Goals.load(tmp_path / "nope.yml")
    assert g.weekly_hours is None
    assert g.projects == {}
    assert g.tags == {}


def test_loads_full_goals_file(tmp_path):
    p = tmp_path / "goals.yml"
    p.write_text(
        "weekly_hours: 35\n"
        "projects:\n"
        "  Project One: 10\n"
        "  Project Two: 5.5\n"
        "tags:\n"
        "  deep-work: 12\n",
        encoding="utf-8",
    )
    g = Goals.load(p)
    assert g.weekly_hours == 35.0
    assert g.projects == {"Project One": 10.0, "Project Two": 5.5}
    assert g.tags == {"deep-work": 12.0}


def test_rejects_non_mapping_top_level(tmp_path):
    p = tmp_path / "goals.yml"
    p.write_text("- not a mapping\n", encoding="utf-8")
    with pytest.raises(ValueError, match="mapping"):
        Goals.load(p)


def test_rejects_non_numeric_weekly_hours(tmp_path):
    p = tmp_path / "goals.yml"
    p.write_text("weekly_hours: forty\n", encoding="utf-8")
    with pytest.raises(ValueError, match="weekly_hours"):
        Goals.load(p)


def test_rejects_non_numeric_project_target(tmp_path):
    p = tmp_path / "goals.yml"
    p.write_text("projects:\n  Foo: 'lots'\n", encoding="utf-8")
    with pytest.raises(ValueError, match="projects"):
        Goals.load(p)


def test_rejects_invalid_yaml(tmp_path):
    p = tmp_path / "goals.yml"
    p.write_text("weekly_hours: [unclosed\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid YAML"):
        Goals.load(p)


# ---- burn-down -------------------------------------------------------------

def test_burn_down_status_buckets():
    assert BurnDownItem("x", 10, 10).status.startswith("✅")
    assert BurnDownItem("x", 10, 8).status.startswith("🟢")
    assert BurnDownItem("x", 10, 5).status.startswith("🟡")
    assert BurnDownItem("x", 10, 2).status.startswith("🔴")


def test_burn_down_no_target_marks_status_dash():
    assert BurnDownItem("x", 0, 5).status == "—"
    assert BurnDownItem("x", 0, 5).percent_complete == 0.0


def test_burn_down_percent_complete_caps_at_100():
    item = BurnDownItem("x", 10, 25)
    assert item.percent_complete == 100.0
    assert item.remaining_hours == -15


def test_compute_burn_down_orders_total_projects_tags():
    g = Goals(
        weekly_hours=35,
        projects={"B Project": 10, "A Project": 5},
        tags={"deep": 12},
    )
    items = compute_burn_down(
        g,
        actual_by_project={"A Project": 3, "B Project": 8},
        actual_by_tag={"deep": 10},
        actual_total_hours=22,
    )
    labels = [i.label for i in items]
    assert labels == ["TOTAL", "project: A Project", "project: B Project", "tag: deep"]
    assert items[0].actual_hours == 22
    assert items[1].actual_hours == 3
    assert items[2].actual_hours == 8
    assert items[3].actual_hours == 10


def test_compute_burn_down_handles_missing_actual():
    g = Goals(projects={"Ghost": 5})
    items = compute_burn_down(g, {}, {}, 0)
    assert items[0].actual_hours == 0
    assert items[0].status.startswith("🔴")
