#!/usr/bin/env python3
"""Run basic code quality checks."""

import ast
import os
import sys
from pathlib import Path


def check_syntax(file_path: str) -> bool:
    """Check if a Python file has valid syntax."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            ast.parse(f.read())
        return True
    except SyntaxError as e:
        print(f"  ✗ Syntax error: {e}")
        return False


def main():
    """Run lint checks on all Python files."""
    src_dir = Path(__file__).parent / 'src'
    test_dir = Path(__file__).parent / 'tests'

    python_files = list(src_dir.glob('*.py')) + list(test_dir.glob('*.py'))

    print(f"Checking {len(python_files)} Python files...")

    all_ok = True
    for file_path in python_files:
        print(f"  {file_path.name}", end='')
        if check_syntax(file_path):
            print(" ✓")
        else:
            all_ok = False

    if all_ok:
        print("\n✓ All files have valid syntax")
        return 0
    else:
        print("\n✗ Some files have syntax errors")
        return 1


if __name__ == '__main__':
    sys.exit(main())
