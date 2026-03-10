# clockiPy

A CLI tool for fetching and displaying [Clockify](https://clockify.me/) time entries in a clean table, with CSV and Markdown export, project/task breakdowns, and more.

## Features

- Fetch time entries from Clockify API
- Display entries in a clean, tabulated format
- Summaries by day, week, month, year, project, tag, and more
- Compare planned vs. measured time with percentage difference columns
- Export to CSV and Markdown
- Customizable date ranges and breakdowns

## Python Environment Setup

This project uses a project-local virtual environment in `.venv`.

### Bootstrap (recommended)

```bash
./scripts/bootstrap_venv.sh
source .venv/bin/activate
```

### Manual setup

```bash
python3 -m venv .venv
source .venv/bin/activate   # macOS/Linux
# .venv\Scripts\activate    # Windows
pip install -r requirements.txt
pip install -e .
```

## Installation

After activating your environment (see above), install as a package:

```bash
pip install .
```

Or install in editable mode for development:

```bash
pip install -e .
```

## Usage

After installation, use the CLI command:

```bash
clockipy --start 2024-05-15 --end 2024-05-22
```

Or run the module directly:

```bash
python -m clockipy --start 2024-05-15 --end 2024-05-22
```

Prefer the `clockipy` command once the package is installed. `python -m clockipy` assumes `python` resolves to the active environment's interpreter.

### Example commands

- Show entries and summary for a custom date range:

  ```bash
  clockipy --start 2024-05-15 --end 2024-05-22
  ```

- Show per-day tables and weekly summary:

  ```bash
  clockipy --mode week --start 2024-05-15
  ```

- Show monthly summary, per-week breakdown, and export all tables to CSV:

  ```bash
  clockipy --mode month --start 2024-05-15 --breakdown --csv june
  ```

- Show yearly summary (Jan 1 to Dec 31):

  ```bash
  clockipy --mode year --start 2024-06-15
  ```

- Show yearly summary with per-month breakdown:

  ```bash
  clockipy --mode year --start 2024-01-01 --breakdown
  ```

## Environment Setup

Preferred setup: export these values in your shell environment, for example from `~/rene.env` if you use the dotfiles repo:

- `CLOCKIFY_API_KEY` — Your Clockify API key
- `CLOCKIFY_WORKSPACE_ID` — Your workspace ID
- `CLOCKIFY_USER_ID` — Optional; `clockipy` can derive it from the Clockify API if omitted

`clockipy` checks credentials in this order:

1. Existing process environment
2. `~/rene.env`
3. Repo-local `clockipy.env`

Optional fallback if you do not use shell exports:

```bash
cp clockipy.env.example clockipy.env
```

**Do not commit your filled `clockipy.env` to version control.**

## Planned vs. Measured Time

clockiPy can compare planned time with actual measured time. To use this feature:

1. Include planned time in your task names using the format `{ph:mm}` (e.g., `{p1:30}` for 1 hour and 30 minutes)
2. The summary tables will show:
   - `Meas>Plan%`: Percentage of time where measured time exceeded planned time (over-worked)
   - `Meas<Plan%`: Percentage of time where measured time was less than planned time (under-worked)
3. The Totals table shows:
   - `Meas>Plan Total`: Sum of all over-plan time (worked more than estimated)
   - `Meas<Plan Total`: Sum of all under-plan time (worked less than estimated)
   - `Abs(Dur-Plan) Total`: Total absolute deviation from plan

**Note:** Tasks without planned time (`{p...}` notation) are excluded from deviation calculations.

This helps you track how accurately you estimate task durations.

## Requirements

- Python 3.7+
- See `requirements.txt` for dependencies

## Project Structure

- `clockipy/` - Main package
  - `api/` - Clockify API client
  - `utils/` - Utility functions
  - `reports/` - Report generation
- `tests/` - Test suite

## Development

### Project Structure

```
clockipy/
├── __main__.py          # CLI entry point and mode logic
├── api/
│   └── client.py        # Clockify API client
├── reports/
│   ├── report_generator.py  # Report/table generation
│   └── time_entry.py        # TimeEntry data class
└── utils/
    ├── date_utils.py    # Date range helpers (week, month, year)
    ├── format_utils.py  # Duration formatting, parsing
    └── file_utils.py    # CSV/Markdown export
```

### Running Tests

Tests use Python's built-in `unittest` framework.

```bash
./scripts/bootstrap_venv.sh
source .venv/bin/activate
python -m unittest discover tests/ -v
```

**Run specific test file:**

```bash
python -m unittest tests/test_summary_tables.py -v
```

**Run specific test class:**

```bash
python -m unittest tests.test_summary_tables.TestTimeDifferenceCalculations -v
```

### Test Coverage

The test suite includes:

- `test_clockipy_functionality.py` - Integration tests for CLI modes
- `test_summary_tables.py` - Unit tests for report generation and time diff calculations

Key test cases:

- Duration parsing (`PT1H30M` format)
- Planned time extraction (`{p1:30}` format)
- Time difference calculations (Meas>Plan, Meas<Plan)
- All CLI modes (normal, week, month, year)

### Adding New Tests

1. Create test file in `tests/` directory
2. Import from `clockipy` package
3. Use `unittest.TestCase` base class
4. Run with `python -m unittest discover tests/ -v`

## CLI Reference

| Flag | Description |
|------|-------------|
| `--mode {normal,week,month,year}` | Summary mode |
| `--start YYYY-MM-DD` | Start/reference date |
| `--end YYYY-MM-DD` | End date (normal mode only) |
| `--breakdown` | Add sub-period breakdown (week→day, month→week, year→month) |
| `--csv PREFIX` | Export tables to CSV files |
| `--md PATH` | Export to Markdown file |
| `--weekstart {0-6}` | Week start day (0=Mon, 6=Sun) |
| `-l, --list` | List user and workspaces |

## License

MIT

---

## Agent Quick Reference

> This section provides quick context for AI coding assistants.

### Environment Priority

1. `./scripts/bootstrap_venv.sh`
2. `source .venv/bin/activate`

### Key Files

| Purpose | File |
|---------|------|
| CLI entry | `clockipy/__main__.py` |
| API client | `clockipy/api/client.py` |
| Reports | `clockipy/reports/report_generator.py` |
| Date utils | `clockipy/utils/date_utils.py` |
| Tests | `tests/test_*.py` |

### Run Commands

```bash
# Tests
python -m unittest discover tests/ -v

# CLI help
python -m clockipy --help

# Example run
python -m clockipy --mode month --start 2025-01-15
```

### Dependencies

`requests`, `tabulate`, `markdown` (see `requirements.txt`)
