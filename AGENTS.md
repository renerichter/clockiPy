# AGENTS.md — Context & Instructions for AI Agents

> **Role:** You are a senior Python engineer working on `clockiPy`.
> **Tone:** Calm, helpful, constructive.
> **Environment:** project-local `.venv`

---

## 1. Environment & Setup (CRITICAL)

**Always** use the project-local `.venv` for all shell commands.

- **Bootstrap:** `./scripts/bootstrap_venv.sh`
- **Activation:** `source .venv/bin/activate`
- **Install deps:** `pip install -r requirements.txt` and `pip install -e .`
- **Tests:** Run with `pytest` (preferred). If missing, install it with `pip install pytest`.

**Fallback (if pytest is unavailable):**

```bash
./scripts/bootstrap_venv.sh
source .venv/bin/activate
python -m unittest discover tests/ -v
```

---

## 2. Repo Overview

- **CLI entry:** `clockipy/__main__.py`
- **API client:** `clockipy/api/client.py`
- **Report generation:** `clockipy/reports/report_generator.py`
- **Time entry model:** `clockipy/reports/time_entry.py`
- **Utilities:** `clockipy/utils/*.py`
- **Tests:** `tests/test_*.py`

---

## 3. Planned vs. Measured + Recurring Task Rules

- **Planned time format:** `{pH:MM}` inside task description.
- **Recurring tasks:** If a task name contains `🔁`, deviations are **not** summed across different days.
  - Each day's occurrence is treated independently for plan deviation.
  - Summary tables still show a **single row** per project/tag/subproject, but deviations include per-day over/under values.
  - Multiple entries on the same day with the same description aggregate within that day.
  - If start time is missing, recurring entries with same description group together (graceful fallback).
- **Non-recurring tasks:** Aggregate across all days in the report range.
- **Single-day reports:** Normal aggregation still applies.
- **Tag allocation:** Deviations are allocated proportionally by entry duration within each occurrence.

---

## 4. Development Rules

- **Tests are mandatory:** Any feature change or bug fix must include an updated or new test.
- **Iterate until green:** If tests fail, fix or extend them until they pass.
- **Dependencies:** If you add a runtime dependency, update `requirements.txt`. If it's dev-only, install it into `.venv` and document it here.
- **Environment secrets:** Prefer exported `CLOCKIFY_*` vars (for example from `~/rene.env`); use `clockipy.env` only as a local fallback. Never commit real credentials.

---

## 5. Suggested Workflow

```bash
./scripts/bootstrap_venv.sh
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
pytest tests/ -q
```

---

## 6. Quick Manual Checks

```bash
python -m clockipy --help
python -m clockipy --mode month --start 2025-01-15
```
