# Troubleshooting

Quick fixes for the most common failure modes.

## "Missing Clockify credentials"

clockiPy exits with code 2 and prints which sources it checked. Fix one
of:

```bash
export CLOCKIFY_API_KEY=ck_...
export CLOCKIFY_WORKSPACE_ID=...
# or put them in ~/rene.env
# or put them in ./clockipy.env (project-local)
```

See [credentials.md](credentials.md) for the full precedence rules.

## `clockipy --list` works but reports show no entries

Two likely causes:

1. **Wrong workspace.** `clockipy --list` shows every workspace you can
   access. Re-export `CLOCKIFY_WORKSPACE_ID` with the right id.
2. **Wrong user.** Unset `CLOCKIFY_USER_ID` and let clockiPy auto-resolve
   it from the API.

## "Anomaly detection needs at least 2 prior weeks of cached data"

The digest has fewer than 2 weeks of history in the cache. Build it up:

```bash
clockipy --mode week --start 2026-05-04   # 2 weeks back
clockipy --mode week --start 2026-05-11   # 1 week back
clockipy --digest                          # now has 2+ weeks of history
```

Or wait — running `--mode week` (no args, on the current week) every
week naturally accumulates history.

## Stale data even after the source system was updated

The cache treats data as fresh for 1 hour. Force a refresh:

```bash
clockipy --mode week --refresh
```

Or bypass the cache entirely for one run:

```bash
clockipy --mode week --no-cache
```

## `429 Too Many Requests` or transient `5xx` errors

The client retries automatically (3 retries, exponential backoff). If
you see the error after retries are exhausted, wait a minute and retry,
or run with `-vv` to see the retry trace:

```bash
clockipy --mode week -vv
```

## Markdown export refuses to write

Two structural validations apply:

- Output must be non-empty.
- Fenced code blocks must be balanced.

A failure here usually means an upstream renderer bug — open an issue
with the offending range.

## Tests fail right after a refactor

Many older tests in `tests/test_clockipy_functionality.py` patch by
canonical module path (e.g. `clockipy.env.candidate_env_files`). If you
moved a symbol, update the patch target — the backwards-compat shim in
`clockipy.__main__` re-exports symbols at runtime but **does not**
proxy `unittest.mock.patch` targets.

Prefer dependency injection (`date_interface(client=...)`) over patching
when adding new tests.

## Cache file got into a weird state

It's safe to delete:

```bash
rm "${XDG_CACHE_HOME:-$HOME/.cache}/clockipy/<workspace>__<user>.db"
```

The next run rebuilds it.
