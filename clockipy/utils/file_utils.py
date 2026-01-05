"""File I/O utility functions for clockiPy."""
import os
import csv
import sys
import markdown
from datetime import date
from typing import List

def write_csv(filename: str, headers: list, rows: list):
    """Write data to a CSV file.
    
    Args:
        filename: Output file name
        headers: Column headers
        rows: Data rows
    """
    with open(filename, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)

def write_markdown(md_path: str, content: str, start_date: date, end_date: date, overwrite: bool = False):
    """Write content to a Markdown file.
    
    Args:
        md_path: Output file path
        content: Markdown content
        start_date: Start date for the title
        end_date: End date for the title
        overwrite: Whether to overwrite the file if it exists
    """
    # File existence feedback
    file_exists = os.path.exists(md_path)
    if file_exists and not overwrite:
        mode = 'a'
        print(f"[INFO] File '{md_path}' exists. Appending output.")
    elif file_exists and overwrite:
        mode = 'w'
        print(f"[INFO] File '{md_path}' exists. Overwriting as requested.")
    else:
        mode = 'w'
        print(f"[INFO] File '{md_path}' does not exist. Creating new file.")
    
    try:
        with open(md_path, mode, encoding='utf-8') as f:
            if mode == 'w' or (mode == 'a' and os.stat(md_path).st_size == 0):
                f.write(f"# Analysis of {start_date} to {end_date}\n\n")
            f.write(content)
    except Exception as e:
        print(f"[ERROR] Failed to write to '{md_path}': {e}")
        sys.exit(2)
    
    # Markdown validation
    try:
        with open(md_path, 'r', encoding='utf-8') as f:
            md_text = f.read()
        # Validate by converting to HTML (will raise if invalid)
        markdown.markdown(md_text)
    except Exception as e:
        print(f"[ERROR] Markdown validation failed for '{md_path}': {e}")
        sys.exit(3) 