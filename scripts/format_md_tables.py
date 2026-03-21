#!/usr/bin/env python3
"""
Markdown Table Formatter
========================
Reads markdown files, finds all tables, and pads cells so columns align.
Usage:
    python3 scripts/format_md_tables.py README.md docs/*.md
"""

import re
import sys
import os
import unicodedata


def visual_len(s: str) -> int:
    """Calculate visual width accounting for wide chars (CJK, emoji)."""
    length = 0
    i = 0
    chars = list(s)
    while i < len(chars):
        c = chars[i]
        # Skip ANSI escape sequences
        if c == '\x1b':
            while i < len(chars) and chars[i] != 'm':
                i += 1
            i += 1
            continue
        cat = unicodedata.category(c)
        eaw = unicodedata.east_asian_width(c)
        if cat == 'So':  # Symbol Other — emoji like ✅ ❌ ⚠️
            length += 2
        elif eaw in ('W', 'F'):  # Wide or Fullwidth
            length += 2
        else:
            length += 1
        i += 1
    return length


def pad_to(s: str, target_width: int) -> str:
    """Pad string with spaces to reach target visual width."""
    current = visual_len(s)
    if current >= target_width:
        return s
    return s + ' ' * (target_width - current)


def is_separator_row(row: str) -> bool:
    """Check if a row is a table separator (e.g., |---|---|---|)."""
    cells = [c.strip() for c in row.strip().strip('|').split('|')]
    return all(re.match(r'^:?-+:?$', c) for c in cells if c)


def format_table(table_lines: list[str]) -> list[str]:
    """Format a markdown table with aligned columns."""
    if len(table_lines) < 2:
        return table_lines

    # Parse all rows into cells
    parsed_rows = []
    separator_indices = []
    for idx, line in enumerate(table_lines):
        raw = line.strip()
        # Remove leading/trailing pipe
        if raw.startswith('|'):
            raw = raw[1:]
        if raw.endswith('|'):
            raw = raw[:-1]
        cells = [c.strip() for c in raw.split('|')]
        parsed_rows.append(cells)
        if is_separator_row(line):
            separator_indices.append(idx)

    if not parsed_rows:
        return table_lines

    # Determine number of columns (max across all rows)
    num_cols = max(len(row) for row in parsed_rows)

    # Normalize all rows to same number of columns
    for row in parsed_rows:
        while len(row) < num_cols:
            row.append('')

    # Calculate max visual width per column
    col_widths = [0] * num_cols
    for idx, row in enumerate(parsed_rows):
        if idx in separator_indices:
            continue
        for col_idx, cell in enumerate(row):
            w = visual_len(cell)
            if w > col_widths[col_idx]:
                col_widths[col_idx] = w

    # Ensure minimum width of 3 for separator dashes
    col_widths = [max(w, 3) for w in col_widths]

    # Build formatted lines
    result = []
    for idx, row in enumerate(parsed_rows):
        if idx in separator_indices:
            # Rebuild separator with correct widths
            sep_cells = []
            for col_idx in range(num_cols):
                sep_cells.append('-' * col_widths[col_idx])
            result.append('| ' + ' | '.join(sep_cells) + ' |')
        else:
            padded_cells = []
            for col_idx, cell in enumerate(row):
                padded_cells.append(pad_to(cell, col_widths[col_idx]))
            result.append('| ' + ' | '.join(padded_cells) + ' |')

    return result


def format_file(filepath: str) -> bool:
    """Format all tables in a markdown file. Returns True if changes were made."""
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # Strip newlines for processing
    lines = [line.rstrip('\n') for line in lines]

    new_lines = []
    i = 0
    changed = False

    while i < len(lines):
        # Detect start of a table (line starts with |)
        if lines[i].strip().startswith('|'):
            # Collect all consecutive table lines
            table_start = i
            table_lines = []
            while i < len(lines) and lines[i].strip().startswith('|'):
                table_lines.append(lines[i])
                i += 1

            # Only format if it looks like a real table (has separator row)
            has_separator = any(is_separator_row(line) for line in table_lines)
            if has_separator and len(table_lines) >= 2:
                formatted = format_table(table_lines)
                if formatted != table_lines:
                    changed = True
                new_lines.extend(formatted)
            else:
                new_lines.extend(table_lines)
        else:
            new_lines.append(lines[i])
            i += 1

    if changed:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write('\n'.join(new_lines) + '\n')
        return True
    return False


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 format_md_tables.py <file1.md> [file2.md ...]")
        sys.exit(1)

    files = sys.argv[1:]
    total_changed = 0

    for filepath in files:
        if not os.path.isfile(filepath):
            print(f"  SKIP  {filepath} (not found)")
            continue
        try:
            changed = format_file(filepath)
            status = "FIXED" if changed else "OK   "
            print(f"  {status} {filepath}")
            if changed:
                total_changed += 1
        except Exception as e:
            print(f"  ERROR {filepath}: {e}")

    print(f"\nDone: {total_changed}/{len(files)} files updated.")


if __name__ == '__main__':
    main()
