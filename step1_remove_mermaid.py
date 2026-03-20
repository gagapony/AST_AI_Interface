#!/usr/bin/env python3
"""Step 1: Remove mermaid generation code."""

import sys

# Read file
with open('src/cli.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Skip the mermaid section (lines 408-419 are indices 407-418)
new_lines = lines[:407]  # Keep lines 1-408
new_lines.extend(lines[419:])  # Skip lines 409-420, add rest

# Write back
with open('src/cli.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print("✅ Removed mermaid generation code (lines 408-419)")
print(f"   Removed 12 lines")
