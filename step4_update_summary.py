#!/usr/bin/env python3
"""Step 4: Update _print_output_summary() function."""

import sys

# Read file
with open('src/cli.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find and replace the _print_output_summary function
# We need to replace the mermaid section with all support

start_line = None
end_line = None

for i, line in enumerate(lines):
    if "def _print_output_summary" in line:
        start_line = i
    if start_line is not None and "def _is_allowed_path" in line:
        end_line = i
        break

if start_line is None or end_line is None:
    print("❌ Could not find _print_output_summary function")
    sys.exit(1)

print(f"Found _print_output_summary: lines {start_line+1} to {end_line}")

# Create new function
new_function = '''def _print_output_summary(format_type: str, output_paths: Dict[str, Path]) -> None:
    """
    Print summary of generated output files.

    Args:
        format_type: Output format type (json, html, all)
        output_paths: Dictionary of output paths
    """
    print("\n" + "=" * 50)
    print("Output Generation Complete")
    print("=" * 50)

    if format_type == 'json' or format_type == 'all':
        if output_paths.get('json'):
            print(f"  JSON:  {output_paths['json']}")

    if format_type == 'html' or format_type == 'all':
        if output_paths.get('html'):
            print(f"  HTML:  {output_paths['html']}")

    if format_type == 'all':
        print()
        print("Serial structure: compile_commands.json → call_graph.json → callgraph.html")

    print("=" * 50 + "\\n")
'''

# Replace old function
new_lines = lines[:start_line]
new_lines.append(new_function)
new_lines.extend(lines[end_line:])

# Write back
with open('src/cli.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print("✅ Step 4 complete: Updated _print_output_summary()")
print(f"   Replaced lines {start_line+1} to {end_line}")
print("   New support: json, html, all formats")
