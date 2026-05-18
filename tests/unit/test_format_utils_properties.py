"""Property tests for low-level parsing utilities.

These verify invariants rather than fixed inputs — broad coverage of the
edge space without writing dozens of one-off cases.
"""
from __future__ import annotations

import re

from hypothesis import given
from hypothesis import strategies as st

from clockipy.utils.format_utils import parse_clockify_duration, parse_planned_from_name

# ---- parse_clockify_duration ----------------------------------------------

durations = st.builds(
    lambda h, m, s: (h, m, s, f"PT{h}H{m}M{s}S"),
    st.integers(min_value=0, max_value=999),
    st.integers(min_value=0, max_value=59),
    st.integers(min_value=0, max_value=59),
)


@given(durations)
def test_parse_clockify_duration_round_trip(payload):
    h, m, s, text = payload
    assert parse_clockify_duration(text) == h * 3600 + m * 60 + s


@given(st.text())
def test_parse_clockify_duration_never_raises(text):
    # Must always return int >= 0 — never raise.
    result = parse_clockify_duration(text)
    assert isinstance(result, int)
    assert result >= 0


def test_parse_clockify_duration_handles_none():
    assert parse_clockify_duration(None) == 0


@given(st.integers(min_value=0, max_value=10000))
def test_parse_clockify_duration_hours_only(h):
    assert parse_clockify_duration(f"PT{h}H") == h * 3600


@given(st.integers(min_value=0, max_value=10000))
def test_parse_clockify_duration_seconds_only(s):
    assert parse_clockify_duration(f"PT{s}S") == s


# ---- parse_planned_from_name ----------------------------------------------

@given(
    st.integers(min_value=0, max_value=99),
    st.integers(min_value=0, max_value=59),
    st.text(alphabet=st.characters(blacklist_characters="{}"),
            min_size=0, max_size=30),
)
def test_parse_planned_from_name_extracts_pHMM(hours, minutes, prefix):
    name = f"{prefix} {{p{hours}:{minutes:02d}}}"
    expected = hours * 3600 + minutes * 60
    assert parse_planned_from_name(name) == expected


@given(st.text())
def test_parse_planned_from_name_returns_zero_or_positive(name):
    result = parse_planned_from_name(name)
    assert isinstance(result, int)
    assert result >= 0


@given(st.text(alphabet=st.characters(blacklist_categories=["Cs"])))
def test_parse_planned_from_name_no_pHMM_pattern_returns_zero(name):
    # Strings without the {pH:MM} pattern must parse as 0.
    if re.search(r"\{p\d+:\d{1,2}\}", name):
        return  # Skip names that happen to contain the pattern.
    assert parse_planned_from_name(name) == 0
