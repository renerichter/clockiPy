# Development

How to hack on clockiPy locally.

## Bootstrap

```bash
./scripts/bootstrap_venv.sh
source .venv/bin/activate
```

The script creates `.venv`, installs runtime + dev extras from
`pyproject.toml`, and registers `clockipy` as an editable install.

## Test suites

clockiPy keeps a three-layer pyramid:

| Layer          | Path                       | What it covers                                 |
| -------------- | -------------------------- | ---------------------------------------------- |
| Unit           | `tests/unit/`              | Pure functions, parsers, TZ logic, goals math. Property tests via `hypothesis`. |
| Integration    | `tests/integration/`       | Mocked HTTP (`responses`), SQLite cache, orchestrator wiring, digest. |
| Smoke          | `tests/smoke/`             | Real `python -m clockipy` subprocess invocations. |
| Legacy         | `tests/test_*.py` (root)   | Behavior-locking tests retained from earlier versions. |

Run them:

```bash
pytest                              # all suites
pytest tests/unit                   # fast unit + property tests
pytest tests/integration            # mocked HTTP + DB
pytest tests/smoke                  # subprocess CLI
pytest --cov=clockipy               # with coverage
pytest --cov=clockipy --cov-fail-under=80   # enforce the gate
```

## Lint

```bash
ruff check clockipy tests           # lint
ruff check clockipy tests --fix     # auto-fix safe issues
```

The ruff config in `pyproject.toml` is deliberately pragmatic:
`E, F, W, I` selected, broader modernization rules (`UP`, `B`, `SIM`)
deferred to avoid a sweeping typing-modernization PR on legacy report
code.

## Continuous integration

`.github/workflows/ci.yml` runs on push and pull request:

- Python 3.10, 3.11, 3.12
- `pip install -e ".[dev]"`
- `ruff check clockipy tests`
- `pytest --cov=clockipy --cov-fail-under=80 --cov-report=xml`
- Coverage XML uploaded as an artifact on 3.12

## Adding a feature

The repo follows a TDD-first rhythm:

1. Write the failing test(s) first — unit + integration as appropriate.
2. Run the target test only; confirm it fails for the right reason.
3. Implement the minimum to pass.
4. Re-run the full suite. Must stay 100 % green.
5. `ruff check` — must stay clean.
6. Update docs (`docs/*.md` and `README.md` if user-visible).

## Dependencies

Authoritative list lives in `pyproject.toml`. `requirements.txt` is a
backwards-compat re-export for `pip install -r`.

| Group   | Packages                                                                 |
| ------- | ------------------------------------------------------------------------ |
| Runtime | `requests`, `tabulate`, `rich`, `pyyaml`                                 |
| Dev     | `pytest`, `pytest-cov`, `pytest-subtests`, `responses`, `hypothesis`, `freezegun`, `ruff`, `mypy` |

## Task state for AI assistants

`docs/agent-memory/current-task.json` and `docs/agent-memory/current-plan.md`
capture the current improvement task. Agents driven by the
`project-improvement` skill in `cursor-config` read these on resume.
