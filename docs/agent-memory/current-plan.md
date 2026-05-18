# clockiPy improvement plan (vertical-slice execution)

Inherits `.agents/core-invariants.md`. TDD-first per `implement-change` skill.

## P0 — Foundation
- Remove legacy `setup.py`, write `pyproject.toml` (PEP 621), add dev/test extras (pytest, responses, hypothesis, ruff, mypy, pytest-cov).
- Add `[tool.ruff]`, `[tool.pytest.ini_options]`, `[tool.coverage.run]`.
- Update `requirements.txt` -> derived from pyproject (or remove and reference pyproject).
- Update `scripts/bootstrap_venv.sh` to `pip install -e ".[dev]"`.

## P1 — Critical bug fixes (TDD)
- Write failing tests in `tests/unit/test_timezone.py` for: late-night entry grouped under local day, not UTC day.
- Fix `TimeEntry.start_date` to local timezone; accept optional `tz` param; keep UTC retrievable via `start_date_utc`.
- Write failing tests in `tests/integration/test_api_client.py` (using `responses`) for: timeout passed, retry on 5xx/429, pagination dict-vs-list, `get_tasks` re-raises auth errors, default headers.
- Implement `requests.Session` + retry adapter + `timeout=30` + structured `ClockifyAPIError`.

## P2 — Refactor
- Create `clockipy/cli.py` (argparse + dispatch).
- Create `clockipy/env.py` (credential loading).
- Create `clockipy/orchestrator.py` (date_interface logic, mode dispatch).
- Create `clockipy/modes/{normal,week,month,year}.py` (mode-specific assembly).
- Thin `__main__.py` -> `from clockipy.cli import main; main()`.
- `ReportGenerator.compute()` pure method called explicitly from `__init__` or factory.

## P3 — UX
- `logging` everywhere; `--verbose/--quiet` flags; default INFO.
- `rich.console.Console` for stdout tables; keep `tabulate` only for CSV/MD export.
- Drop `markdown` dep; simple existence + non-empty check.

## P4 — Performance
- `get_project_and_tag_mappings`: only fetch tasks for project_ids referenced by entries.
- `concurrent.futures.ThreadPoolExecutor(max_workers=8)` for parallel task fetches.
- In-memory per-run cache keyed by `(workspace_id, project_id)`.

## P5 — Persistence
- `clockipy/store/sqlite.py` schema: entries, projects, tags, sync_state.
- `--refresh` to invalidate; auto-refresh if cache older than 1h or range not covered.

## P6 — Coach
- `~/.config/clockipy/goals.yml`: budgets per project/tag (weekly/monthly).
- `clockipy goals` subcommand (show/lint config + current burn-down).
- `clockipy digest --week [--mail|--md]`: Monday recap with anomalies (`Δ vs 4-week median`, `consistently under-planned tasks`).
- Anomaly callouts in normal report when significant drift detected.

## P7 — Tests
- `tests/unit/` — utils, time_entry, format_utils, env.
- `tests/integration/` — api_client (responses), orchestrator (mocked client), store (tmp sqlite).
- `tests/smoke/` — subprocess invocation of `clockipy --start ... --end ...` with patched env + mocked HTTP via `pytest-httpserver`.
- `hypothesis` for parse_clockify_duration and parse_planned_from_name.
- `.github/workflows/ci.yml` — pytest + ruff + mypy; coverage gate ≥80%.

## P8 — Docs
- README rewrite: install via pipx, examples, configuration.
- AGENTS.md kept aligned.

## P9 — cursor-config deliverable
- `.cursor/commands/improve-project.md`.
- `.agents/skills/project-improvement/SKILL.md`.
- Inherits `.agents/core-invariants.md`, composes `repo-scout` + `deep-qa` + `make-plan` + `implement-change` + `verify-diff`.

## P10 — Prompt reflection
- Section in skill for prompt-gap learnings.

## Done definition
- `pytest -q` green; coverage ≥80% on touched modules.
- `ruff check .` clean.
- `clockipy --mode week --start <date>` runs end-to-end with cache + rich output.
- New cursor-config command wires through real workflow.
