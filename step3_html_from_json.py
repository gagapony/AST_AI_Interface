#!/usr/bin/env python3
"""Step 3: Implement HTML from JSON generation."""

import sys

# Read file
with open('src/cli.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find the HTML generation section
# We need to replace the entire if args.format == 'html' or args.format == 'both' block
# with new code that always generates HTML from JSON

start_line = None
end_line = None

for i, line in enumerate(lines):
    if "if args.format == 'html' or args.format == 'both':" in line:
        start_line = i
    if start_line is not None and "        # Print output files summary" in line:
        end_line = i
        break

if start_line is None or end_line is None:
    print("❌ Could not find HTML generation section")
    sys.exit(1)

print(f"Found HTML generation section: lines {start_line+1} to {end_line}")

# Create new HTML generation code
new_code = """        if args.format == 'html' or args.format == 'all':
            # Generate ECharts HTML (always from JSON file)
            logging.info("Generating ECharts HTML from JSON...")
            if not json_path:
                logging.error("JSON path not available for HTML generation")
                return 1

            # Load JSON to get proper format
            with open(json_path, 'r', encoding='utf-8') as f:
                import json as json_lib
                functions_dict = json_lib.load(f)

            # Remove temp JSON file
            import os
            if 'call_graph_temp.json' in str(json_path):
                os.remove(json_path)
                logging.info(f"Removed temporary JSON file: {json_path}")

            # Generate HTML from JSON
            echarts_gen = EChartsGenerator(
                functions=functions_dict,
                relationships=relationships_to_emit,
                logger=logger
            )
            html_content = echarts_gen.generate_html()
            write_html_file(html_content, str(output_paths['html']))
            logging.info(f"HTML output: {output_paths.get('html')}")

"""

# Replace old code with new code
new_lines = lines[:start_line]
new_lines.append(new_code)
new_lines.extend(lines[end_line:])

# Write back
with open('src/cli.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print("✅ Step 3 complete: Implemented HTML from JSON generation")
print(f"   Replaced lines {start_line+1} to {end_line}")
