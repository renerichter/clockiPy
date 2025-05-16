# clockiPy

A CLI tool for fetching and displaying [Clockify](https://clockify.me/) time entries in a clean table, with CSV and Markdown export, project/task breakdowns, and more.

## Features
- Fetch time entries from Clockify API
- Display entries in a clean, tabulated format
- Summaries by day, week, month, project, tag, and more
- Export to CSV and Markdown
- Customizable date ranges and breakdowns

## Installation

Clone the repository and install as a package:

```bash
cd clockiPy
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

Or run directly:

```bash
python clocki.py --start 2024-05-15 --end 2024-05-22
```

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

## Environment Setup

Copy the example environment file and fill in your Clockify credentials:

```bash
cp clockipy.env.example clockipy.env
```

Edit `clockipy.env` and set:

- `CLOCKIFY_API_KEY` — Your Clockify API key
- `CLOCKIFY_WORKSPACE_ID` — Your workspace ID
- `CLOCKIFY_USER_ID` — Your user ID

**Do not commit your filled `clockipy.env` to version control!**

## Requirements
- Python 3.7+
- See `requirements.txt` for dependencies

## Development
- Main CLI logic is in `clocki.py`
- VSCode debug config is provided in `.vscode/launch.json`

## License
MIT 