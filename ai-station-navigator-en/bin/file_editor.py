#!/usr/bin/env python3
"""
File Editor - Previewless File Editing Tool
Replaces Edit tool to avoid terminal flicker
"""

import sys
import os

# Windows UTF-8 Compatibility (P0 - All scripts must include)
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except:
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')


import json
import re
from pathlib import Path
from datetime import datetime

# Add project lib directory to sys.path (green package bundled dependencies)
_lib_dir = Path(__file__).parent.parent / "lib"
if _lib_dir.exists():
    sys.path.insert(0, str(_lib_dir))


def read_file(file_path: str) -> str:
    """Read file content"""
    try:
        return Path(file_path).read_text(encoding='utf-8')
    except FileNotFoundError:
        print(f"[X] Error: File not found: {file_path}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"[X] Error reading file: {e}", file=sys.stderr)
        sys.exit(1)


def write_file(file_path: str, content: str) -> None:
    """Write file content"""
    try:
        Path(file_path).write_text(content, encoding='utf-8')
    except Exception as e:
        print(f"[X] Error writing file: {e}", file=sys.stderr)
        sys.exit(1)


def replace(file_path: str, old: str, new: str) -> None:
    """Exact string replacement

    Args:
        file_path: File path
        old: Old string to replace
        new: New string
    """
    content = read_file(file_path)

    if old not in content:
        print(f"[!] Warning: '{old[:50]}...' not found in file")
        return

    content = content.replace(old, new)
    write_file(file_path, content)
    print(f"[OK] Replaced in {file_path}")


def regex_replace(file_path: str, pattern: str, replacement: str, count: int = 0) -> None:
    """Regex replacement

    Args:
        file_path: File path
        pattern: Regex pattern
        replacement: Replacement string
        count: Number of replacements (0=all)
    """
    content = read_file(file_path)

    try:
        if count > 0:
            content = re.sub(pattern, replacement, content, count=count)
        else:
            content = re.sub(pattern, replacement, content)
    except re.error as e:
        print(f"[X] Regex error: {e}", file=sys.stderr)
        sys.exit(1)

    write_file(file_path, content)
    print(f"[OK] Regex replaced in {file_path}")


def append(file_path: str, content: str, newline: bool = True) -> None:
    """Append content to end of file

    Args:
        file_path: File path
        content: Content to append
        newline: Whether to add newline before content
    """
    try:
        # Read existing content first to check newline
        if newline:
            try:
                existing = read_file(file_path)
                needs_newline = existing and not existing.endswith('\n')
            except (OSError, IOError):
                needs_newline = False

        with open(file_path, 'a', encoding='utf-8') as f:
            if newline and needs_newline:
                f.write('\n')
            f.write(content)
        print(f"[OK] Appended to {file_path}")
    except Exception as e:
        print(f"[X] Error appending to file: {e}", file=sys.stderr)
        sys.exit(1)


def prepend(file_path: str, content: str) -> None:
    """Insert content at beginning of file

    Args:
        file_path: File path
        content: Content to insert
    """
    text = read_file(file_path)
    write_file(file_path, content + '\n' + text)
    print(f"[OK] Prepended to {file_path}")


def insert_after(file_path: str, marker: str, content: str) -> None:
    """Insert content after marker

    Args:
        file_path: File path
        marker: Locator marker string
        content: Content to insert
    """
    text = read_file(file_path)

    if marker not in text:
        print(f"[!] Warning: Marker '{marker[:50]}...' not found")
        return

    text = text.replace(marker, marker + '\n' + content, 1)
    write_file(file_path, text)
    print(f"[OK] Inserted after marker in {file_path}")


def insert_before(file_path: str, marker: str, content: str) -> None:
    """Insert content before marker

    Args:
        file_path: File path
        marker: Locator marker string
        content: Content to insert
    """
    text = read_file(file_path)

    if marker not in text:
        print(f"[!] Warning: Marker '{marker[:50]}...' not found")
        return

    text = text.replace(marker, content + '\n' + marker, 1)
    write_file(file_path, text)
    print(f"[OK] Inserted before marker in {file_path}")


def delete_between(file_path: str, start_marker: str, end_marker: str) -> None:
    """Delete content between two markers (including markers)

    Args:
        file_path: File path
        start_marker: Start marker
        end_marker: End marker
    """
    text = read_file(file_path)

    if start_marker not in text or end_marker not in text:
        print(f"[!] Warning: Markers not found")
        return

    pattern = re.escape(start_marker) + r'.*?' + re.escape(end_marker)
    text = re.sub(pattern, '', text, flags=re.DOTALL)
    write_file(file_path, text)
    print(f"[OK] Deleted between markers in {file_path}")


def update_json_field(file_path: str, field_path: str, value: str) -> None:
    """Update field in JSON file

    Args:
        file_path: JSON file path
        field_path: Field path (e.g., "a.b.c")
        value: New value (auto-detect type)
    """
    try:
        data = json.loads(read_file(file_path))
    except json.JSONDecodeError as e:
        print(f"[X] Invalid JSON: {e}", file=sys.stderr)
        sys.exit(1)

    # Infer value type
    try:
        value = json.loads(value)
    except json.JSONDecodeError:
        # Keep as string
        pass

    # Navigate to target field
    keys = field_path.split('.')
    target = data
    for key in keys[:-1]:
        if key not in target:
            target[key] = {}
        target = target[key]

    # Update value
    target[keys[-1]] = value

    write_file(file_path, json.dumps(data, ensure_ascii=False, indent=2))
    print(f"[OK] Updated JSON field '{field_path}' in {file_path}")


def main():
    if len(sys.argv) < 2:
        print_usage()
        sys.exit(1)

    operation = sys.argv[1].lower()
    args = sys.argv[2:]

    operations = {
        'replace': (3, replace),
        'regex': (3, regex_replace),
        'append': (2, append),
        'prepend': (2, prepend),
        'insert-after': (3, insert_after),
        'insert-before': (3, insert_before),
        'delete-between': (3, delete_between),
        'update-json': (3, update_json_field),
    }

    if operation not in operations:
        print(f"[X] Unknown operation: {operation}", file=sys.stderr)
        print_usage()
        sys.exit(1)

    min_args, func = operations[operation]

    if len(args) < min_args:
        print(f"[X] Not enough arguments for '{operation}'", file=sys.stderr)
        print_usage()
        sys.exit(1)

    try:
        func(*args)
    except TypeError as e:
        print(f"[X] Argument error: {e}", file=sys.stderr)
        print_usage()
        sys.exit(1)


def print_usage():
    """Print usage instructions"""
    usage = """
File Editor - Previewless File Editing Tool

Usage:
  python bin/file_editor.py <operation> [arguments...]

Operations:
  replace <file> <old> <new>
      Exact string replacement

  regex <file> <pattern> <replacement> [count=0]
      Regex replacement (count=0 means replace all)

  append <file> <content>
      Append content to end of file

  prepend <file> <content>
      Insert content at beginning of file

  insert-after <file> <marker> <content>
      Insert content after marker

  insert-before <file> <marker> <content>
      Insert content before marker

  delete-between <file> <start_marker> <end_marker>
      Delete content between two markers

  update-json <file> <field_path> <value>
      Update JSON field (field_path: "a.b.c")

Examples:
  python bin/file_editor.py replace mybox/config.yaml "old" "new"
  python bin/file_editor.py append mybox/log.txt "New entry"
  python bin/file_editor.py regex mybox/data.txt "\\d+" "X"
  python bin/file_editor.py update-json mybox/config.json "version" "1.2.3"
"""
    print(usage)


if __name__ == '__main__':
    main()
