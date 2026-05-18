# Local cache

clockiPy keeps a SQLite cache of fetched entries so repeat queries are
instant and the Clockify API is hit only when needed.

## Location

```
${XDG_CACHE_HOME:-~/.cache}/clockipy/<workspace_id>__<user_id>.db
```

One DB per `(workspace_id, user_id)` pair. Switching workspaces never
poisons another workspace's cache.

## Refresh policy

clockiPy fetches from the Clockify API when **any** of these are true:

- No cache exists yet for this workspace/user.
- The cached sync that covers the requested range is older than **1 hour**.
- No cached sync covers the requested range.
- You passed `--refresh` (force).
- You passed `--no-cache` (cache disabled entirely).

Otherwise it serves the request entirely from the cache.

## Schema

| Table         | Purpose                                                        |
| ------------- | -------------------------------------------------------------- |
| `meta`        | `schema_version` (currently `1`).                              |
| `sync_state`  | One row per successful sync: `range_start`, `range_end`, `fetched_at`. |
| `time_entries`| Raw API JSON keyed by entry id, indexed by `start_iso`.        |
| `projects`    | `id → name`.                                                   |
| `tags`        | `id → name`.                                                   |
| `tasks`       | `(project_id, task_id) → name`.                                |

## Schema versioning

The `meta.schema_version` value is checked on every connection. On
mismatch the database is **dropped and rebuilt** from the next API call.
This is intentional: for a personal tool, refetching is cheap and
maintaining ALTER migrations is not.

## Manual operations

```bash
# Force a refresh for the next call
clockipy --mode week --refresh

# Bypass the cache for one call (don't read, don't write)
clockipy --mode week --no-cache

# Nuke everything for one workspace
rm "${XDG_CACHE_HOME:-$HOME/.cache}/clockipy/<ws>__<user>.db"
```

## Why the cache also powers `--digest`

The weekly digest needs the current ISO week plus the prior 4 weeks of
data to compute medians. Asking the API for 5 weeks every time would be
slow and noisy. The cache lets `clockipy --digest` run in milliseconds
and stay fully offline.
