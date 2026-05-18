# CLI reference

Every flag, what it does, when to reach for it.

## Synopsis

```
clockipy [-l] [--start DATE] [--end DATE] [--mode MODE]
         [--weekstart N] [--breakdown] [--csv PREFIX]
         [--md FILE] [--overwrite] [--test]
         [--refresh] [--no-cache]
         [--goals] [--digest]
         [-v | -vv | -q]
```

## Modes

| Flag                | What you get                                          |
| ------------------- | ----------------------------------------------------- |
| `--mode normal`     | Free-form range — requires `--start` (and `--end`).   |
| `--mode week`       | Mon–Sun week containing `--start` (or today).         |
| `--mode month`      | Calendar month containing `--start` (or today).       |
| `--mode year`       | Calendar year containing `--start` (or today).        |
| `--goals`           | Bypass reports; print this week's burn-down.          |
| `--digest`          | Bypass reports; print this week's anomaly digest.     |

## Date selection

| Flag            | Notes                                                        |
| --------------- | ------------------------------------------------------------ |
| `--start DATE`  | `YYYY-MM-DD`. Required for `normal`; reference date for the other modes. |
| `--end DATE`    | `YYYY-MM-DD`. Optional in `normal`; ignored in week/month/year. |
| `--weekstart N` | `0=Mon` (default) through `6=Sun`. Affects week boundaries.  |

## Breakdowns & exports

| Flag             | Notes                                                       |
| ---------------- | ----------------------------------------------------------- |
| `--breakdown`    | Add per-week (in `month`) or per-month (in `year`) tables.  |
| `--csv PREFIX`   | Write CSV files alongside stdout. Filenames start with `PREFIX_`. |
| `--md FILE`      | Write a single Markdown report to `FILE`.                   |
| `--overwrite`    | Allow `--md` to overwrite an existing file (default: append). |

## Cache

| Flag           | Notes                                                         |
| -------------- | ------------------------------------------------------------- |
| `--refresh`    | Force a refetch; still writes back to the cache.              |
| `--no-cache`   | Don't read **or** write the cache for this run.               |

See [cache.md](cache.md) for the freshness rule.

## Diagnostics

| Flag         | Notes                                                            |
| ------------ | ---------------------------------------------------------------- |
| `-l, --list` | Print your user info + every workspace and exit.                 |
| `--test`     | Print a sample of resolved `(projectId, taskId) → taskName`.     |
| `-v`         | Set log level to `INFO`.                                         |
| `-vv`        | Set log level to `DEBUG` (also enables `urllib3` retry traces).  |
| `-q`         | Set log level to `WARNING` regardless of `-v`.                   |

## Exit codes

| Code | When                                                                  |
| ---- | --------------------------------------------------------------------- |
| 0    | Success.                                                              |
| 2    | Missing credentials, or filesystem error writing CSV/Markdown.        |
| 3    | Markdown structural validation failed (unbalanced fences, empty).     |
| ≠0   | Any unhandled exception bubbles up through `argparse` / `sys.exit`.   |

## Recipes

```bash
# This week, nothing fancy
clockipy --mode week

# Last full month with per-week tables + CSVs
clockipy --mode month --start 2026-04-01 --breakdown --csv april

# Full year archive to Markdown
clockipy --mode year --start 2026-01-01 --breakdown \
         --md reports/2026-full-year.md --overwrite

# Just the digest, fully offline
clockipy --digest

# Force a fresh pull because Clockify just got new data
clockipy --mode week --refresh
```
