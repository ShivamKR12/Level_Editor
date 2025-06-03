#!/usr/bin/env python3
"""
Script to append "# type: ignore" to lines in improved_level_editor.py that reference LEVEL_EDITOR.

Usage:
    python add_type_ignore.py /path/to/improved_level_editor.py

This will modify the file in place, adding "# type: ignore" at the end of any line containing "LEVEL_EDITOR"
that does not already end with a "type: ignore" comment. A backup of the original file will be saved with
a ".bak" extension.
"""

import sys
from pathlib import Path

def add_type_ignore_to_level_editor(file_path: Path):
    if not file_path.is_file():
        print(f"Error: File not found: {file_path}")
        return

    # Read all lines from the file
    original_lines = file_path.read_text(encoding='utf-8').splitlines(keepends=True)

    modified_lines = []
    changed = False

    for line in original_lines:
        stripped = line.rstrip('\n')
        # Check if this line references "LEVEL_EDITOR" and does not already have a "# type: ignore"
        if "LEVEL_EDITOR" in stripped and "# type: ignore" not in stripped:
            # Append "  # type: ignore" before the newline (preserve existing indentation/comments)
            if stripped.endswith((' ', '\t')):
                # If line ends with whitespace, just append the comment
                new_line = stripped + "# type: ignore\n"
            else:
                new_line = stripped + "  # type: ignore\n"
            modified_lines.append(new_line)
            changed = True
        else:
            # Leave the line unchanged
            modified_lines.append(line)

    if not changed:
        print("No lines referencing LEVEL_EDITOR without an existing '# type: ignore' were found.")
        return

    # Backup the original file
    backup_path = file_path.with_suffix(file_path.suffix + ".bak")
    try:
        file_path.replace(backup_path)
        print(f"Backup created at: {backup_path}")
    except Exception as e:
        print(f"Warning: Could not create backup file: {e}")
        return

    # Write the modified lines back to the original file path
    try:
        file_path.write_text("".join(modified_lines), encoding='utf-8')
        print(f"Modified file written to: {file_path}")
    except Exception as e:
        # If writing fails, restore backup
        print(f"Error writing modified file: {e}")
        try:
            backup_path.replace(file_path)
            print("Original file restored from backup.")
        except Exception as restore_err:
            print(f"Error restoring backup: {restore_err}")

def main():
    if len(sys.argv) != 2:
        print("Usage: python add_type_ignore.py /path/to/improved_level_editor.py")
        sys.exit(1)

    file_path = Path(sys.argv[1])
    add_type_ignore_to_level_editor(file_path)

if __name__ == "__main__":
    main()
