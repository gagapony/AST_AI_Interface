#!/usr/bin/env python3
"""Replace old output generation code with new serial structure."""

import sys

# Read the backup file
with open('src/cli.py.backup', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find the range to replace (lines 402-545, which are indices 401-544)
# Replace with new code

output_lines = lines[:401]  # Lines 1-401 (keep)
output_lines.append('        # Generate outputs\n')  # Add replacement
output_lines.append('        # True serial structure: compile_commands.json → call_graph.json → callgraph.html\n')
output_lines.append('\n')
output_lines.append('        json_path = None\n')
output_lines.append('\n')
output_lines.append('        # Step 1: Always generate JSON if format is html or all\n')
output_lines.append("        if args.format == 'html' or args.format == 'all':\n")
output_lines.append('            # Generate JSON file first (HTML will be generated from JSON)\n')
output_lines.append("            json_path = Path(str(output_paths.get('json', '/tmp/call_graph_temp.json')))\n")
output_lines.append('            logging.info(f"Generating JSON output to {json_path}")\n')
output_lines.append('            emitter = JSONEmitter(str(json_path))\n')
output_lines.append('            emitter.emit(functions_to_emit, relationships_to_emit)\n')
output_lines.append("            logging.info(f'JSON generated at {json_path}')\n")
output_lines.append('\n')
output_lines.append("        # Step 2: Generate other formats\n")
output_lines.append("        if args.format == 'json' or args.format == 'all':\n")
output_lines.append('            # If format is "all", we already generated JSON, nothing more to do\n')
output_lines.append("            if args.format == 'json':\n")
output_lines.append("                logging.info(f'Generating JSON output to {output_paths[\"json\"]}')\n")
output_lines.append("                if not output_paths.get('json'):\n")
output_lines.append('                    emitter = JSONEmitter(str(output_paths[\'json\']))\n')
output_lines.append('                    emitter.emit(functions_to_emit, relationships_to_emit)\n')
output_lines.append("                logging.info(f'JSON output: {output_paths.get(\"json\")}')\n")
output_lines.append('\n')
output_lines.append("        if args.format == 'html' or args.format == 'all':\n")
output_lines.append('            # Generate ECharts HTML (always from JSON file)\n')
output_lines.append('            logging.info("Generating ECharts HTML from JSON...")\n')
output_lines.append('            if not json_path:\n')
output_lines.append('                logging.error("JSON path not available for HTML generation")\n')
output_lines.append('                return 1\n')
output_lines.append('\n')
output_lines.append('            # Load JSON to get proper format\n')
output_lines.append('            with open(json_path, \'r\', encoding=\'utf-8\') as f:\n')
output_lines.append('                import json as json_lib\n')
output_lines.append('                functions_dict = json_lib.load(f)\n')
output_lines.append('\n')
output_lines.append('            # Remove temp JSON file\n')
output_lines.append('            import os\n')
output_lines.append("            if 'call_graph_temp.json' in str(json_path):\n")
output_lines.append('                os.remove(json_path)\n')
output_lines.append("                logging.info(f'Removed temporary JSON file: {json_path}')\n")
output_lines.append('\n')
output_lines.append('            # Generate HTML from JSON\n')
output_lines.append('            echarts_gen = EChartsGenerator(\n')
output_lines.append('                functions=functions_dict,\n')
output_lines.append('                relationships=relationships_to_emit,\n')
output_lines.append('                logger=logger\n')
output_lines.append('            )\n')
output_lines.append('            html_content = echarts_gen.generate_html()\n')
output_lines.append("            write_html_file(html_content, str(output_paths['html']))\n")
output_lines.append("            logging.info(f'HTML output: {output_paths.get(\"html\")}')\n")

# Add remaining lines from line 546 onwards
output_lines.extend(lines[545:])

# Write to new file
with open('src/cli.py', 'w', encoding='utf-8') as f:
    f.writelines(output_lines)

print("✅ Output generation code replaced")
print("   Old code: lines 402-545 (144 lines)")
print("   New code: True serial structure (JSON → HTML)")
