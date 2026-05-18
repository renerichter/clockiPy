# Goals & weekly digest

Two opt-in features that turn clockiPy from a reporter into a coach.

## Goals: `~/.config/clockipy/goals.yml`

A YAML file declaring weekly time targets. All keys optional:

```yaml
weekly_hours: 35            # total weekly target
projects:                   # per-project weekly targets
  "Project One": 10
  "Project Two": 5.5
tags:                       # per-tag weekly targets
  "deep-work": 12
  "meetings": 6
```

Location follows XDG: `${XDG_CONFIG_HOME:-~/.config}/clockipy/goals.yml`.

### `clockipy --goals`

Prints the current week's burn-down using **cached** data only:

```
# Goals — week of 2026-05-18 → 2026-05-24
| Dimension              | Target | Actual | Remaining | %    | Status      |
| TOTAL                  | 35.0   | 22.50  | +12.50    | 64%  | 🟡 behind   |
| project: Project One   | 10.0   |  8.00  |  +2.00    | 80%  | 🟢 on track |
| project: Project Two   |  5.5   |  6.00  |  -0.50    | 100% | ✅ complete |
| tag: deep-work         | 12.0   |  4.50  |  +7.50    | 38%  | 🔴 at risk  |
```

Status thresholds (% of target):

| % complete | Status        |
| ---------- | ------------- |
| ≥ 100      | ✅ complete   |
| ≥ 75       | 🟢 on track   |
| ≥ 50       | 🟡 behind     |
| < 50       | 🔴 at risk    |

### Validation

The YAML is validated on load:

- Top level must be a mapping.
- `weekly_hours` must be a number.
- Every value under `projects:` and `tags:` must be a number.
- Invalid YAML or wrong types produce a clear error — clockiPy never
  silently ignores a goal.

## Weekly digest: `clockipy --digest`

A compact summary of the current ISO week (Monday → Sunday) plus
anomaly callouts against the rolling 4-week median.

For each project and tag seen this week or in the prior 4 weeks:

- `actual_hours` — sum for this week
- `4w median` — median of the same dimension across cached prior weeks
- `Δh` and `Δ%` vs that median
- `⚠️ anomaly` flag when `|Δ%| > 25%` **and** at least 2 prior weeks are
  in the cache

### Why the anomaly gate exists

One prior week is a sample size of one — not signal. Flagging "anomalies"
off a single comparison point would generate noise on every new project
or tag. The minimum of 2 prior weeks keeps callouts trustworthy.

### Example output

```
# Weekly Digest — 2026-05-18 → 2026-05-24

**Total tracked:** 22.50 h
**History available:** 4 prior week(s)

| Dimension              | This wk (h) | 4w median | Δ h    | Δ %    |    |
| project: Project One   | 20.00       | 10.00     | +10.00 | +100%  | ⚠️ |
| project: Project Two   |  2.50       |  3.00     |  -0.50 |  -16%  |    |
| tag: deep-work         |  4.50       |  6.00     |  -1.50 |  -25%  |    |

## ⚠️  Anomalies
- **project: Project One**: 20.00h is 100.0% above the 4-week median (10.00h).
```

When fewer than 2 prior weeks are cached:

```
_Anomaly detection needs at least 2 prior weeks of cached data._
```

Fix: run a couple of weekly reports so the cache builds up history.

## Combining the two

`--goals` shows where you stand against your declared plan;
`--digest` shows where you've drifted from your own typical week.
They answer different questions — keep both around.
