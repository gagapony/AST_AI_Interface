#!/usr/bin/env python3
"""Step 3 final: Replace output generation with true serial structure."""

import sys

# Read file
with open('src/cli.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find the output generation section
# Look for "output_paths = _determine_output_paths(args)"
start_line = None
for i, line in enumerate(lines):
    if "output_paths = _determine_output_paths(args)" in line:
        start_line = i
        break

if start_line is None:
    print("❌ Could not find output generation section")
    sys.exit(1)

print(f"Found output generation section at line {start_line + 1}")

# Skip until the end of output generation
# Find the line with "# Print output files summary"
end_line = None
for i in range(start_line, len(lines)):
    if "# Print output files summary" in lines[i]:
        end_line = i
        break

if end_line is None:
    print("❌ Could not find end of output generation")
    sys.exit(1)

print(f"Found end of output generation at line {end_line + 1}")
print(f"Will replace lines {start_line + 1} to {end_line} ({end_line - start_line} lines)")

# Read the new output generation code
with open('output_gen_new.py', 'r', encoding='utf-8') as f:
    new_code_lines = f.readlines()

# Build the new file
new_lines = lines[:start_line]
new_lines.append('\n')
new_lines.extend(new_code_lines)
new_lines.extend(lines[end_line:])

# Write back
with open('src/cli.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print("✅ Step 3 complete: Replaced output generation code")
print(f"   Old code: lines {start_line + 1} to {end_line} ({end_line - start_line} lines)")
print("   New code: True serial structure (JSON → HTML)")
