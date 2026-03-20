#!/usr/bin/env python3
"""Generate file-level call graph from compile_commands.json."""

import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.cli import main

# Monkey-patch to use file graph generator
import src.cli as cli_module

# Store original output generation
original_generate = None


def generate_file_level_graph(args, functions_to_emit, relationships_to_emit, output_paths, logger):
    """Generate file-level graph instead of function-level."""
    from src.file_graph_generator import FileGraphGenerator, write_html_file

    # Convert FunctionInfo to dict format for FileGraphGenerator
    functions_dict = []
    for func in functions_to_emit:
        functions_dict.append({
            'index': func.index,
            'path': func.path,
            'line_range': list(func.line_range),
            'name': func.name,
            'qualified_name': func.qualified_name,
            'brief': func.brief
        })

    # Generate file-level graph
    logging.info("Generating file-level ECharts HTML...")
    filegraph_gen = FileGraphGenerator(
        functions=functions_dict,
        relationships=relationships_to_emit,
        logger=logger
    )
    html_content = filegraph_gen.generate_html()
    write_html_file(html_content, str(output_paths['html']))


# Run with monkey-patch
if __name__ == '__main__':
    # Parse args first
    args = cli_module.parse_args()

    # Override output format to force HTML
    if args.format not in ['html', 'both']:
        args.format = 'html'

    # Run main
    sys.exit(cli_module.main())
