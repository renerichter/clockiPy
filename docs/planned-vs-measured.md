# Planned vs measured

clockiPy turns every Clockify task into a planned-vs-measured comparison
without any extra UI — the plan is encoded inside the task description.

## The `{pH:MM}` tag

Add `{pH:MM}` anywhere in a task name to declare planned time:

```
Deep work {p2:00}       → 2 h 00 min planned
Review {p0:45}          → 45 min planned
Long block {p10:30}     → 10 h 30 min planned
No tag                  → 0 min planned (untreated as "ad-hoc")
```

Rules:

- `H` is any non-negative integer (no leading-zero requirement).
- `MM` must be two digits, `00`–`59`.
- Malformed tags (`{p1:}`, `{p:30}`, `{px:30}`) parse as **zero** rather
  than failing — the line still renders.

## Deviation columns

Every summary table includes:

| Column     | Meaning                                                    |
| ---------- | ---------------------------------------------------------- |
| `Over %`   | How much measured time overshot the plan, as a %.          |
| `Under %`  | How much measured time undershot the plan, as a %.         |

Exactly one of the two is populated per row (the other is blank).

## Aggregation across rows

When the same task or tag appears in many entries:

- **Measured** time sums across all entries.
- **Planned** time sums across all entries that carry the `{pH:MM}` tag.
- Deviation is computed on the totals.

This means a forgotten `{pH:MM}` tag on one of several entries for the
same activity underweights the plan total. That's an intentional
fail-loud: the planned column drops, the deviation jumps, and you
notice.

## Recurring tasks (🔁)

A task name containing the 🔁 emoji is recurring. clockiPy treats
recurring tasks differently:

- **Each day's occurrence is evaluated independently.** Deviations are
  not summed across different days.
- Summary tables still show a single row per project/tag/subproject —
  but the deviation columns reflect the sum of per-day deviations.
- Multiple entries on the same day with the same recurring description
  aggregate within that day (the normal rule).
- Entries with no start timestamp fall back to grouping by description
  alone.

### Why this matters

A daily 15-minute standup that occasionally runs 30 minutes should not
look like "100 % over plan" on weeks where it ran 5×15 + 1×30. The
per-day rule keeps the deviation column meaningful.

## Tag-level allocation

When an entry has multiple tags, deviation is allocated **proportionally
by duration** across them. A single 2 h entry tagged `deep-work` and
`research` contributes 2 h to both tags' measured totals and splits its
deviation between them according to the same weighting other entries
under each tag carry.

## See it in action

```bash
clockipy --mode week --start 2026-05-18
```

Look for the `Time by Project`, `Time by Tag`, and `Time by SubProject`
sections — every one carries the deviation columns.
