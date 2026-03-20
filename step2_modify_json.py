#!/usr/bin/env python3
"""Step 2: Modify JSON generation code."""

import sys

# Read file
with open('src/cli.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find and replace the JSON generation section
# Old: if args.format == 'json' or args.format == 'both':
# New: if args.format == 'json' or args.format == 'all':
for i, line in enumerate(lines):
    if "if args.format == 'json' or args.format == 'both':" in line:
        lines[i] = "        if args.format == 'json' or args.format == 'all':\n"
        print(f"Modified line {i+1}: Changed 'both' to 'all'")
        break

# Write back
with open('src/cli.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print("✅ Step 2 complete: Modified JSON generation code")
print("   Changed: 'both' → 'all'")
