#!/usr/bin/env python3
"""Test script for file-level graph generation."""

import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from file_graph_generator import FileGraphGenerator, write_html_file


def main():
    """Test file-level graph generation."""

    # Load function data
    input_file = Path('/home/gabriel/.openclaw/code/clang-call-analyzer/output.json')

    print(f"Loading data from {input_file}...")
    with open(input_file, 'r') as f:
        data = json.load(f)

    print(f"Loaded {len(data)} function records")

    # Extract functions and relationships
    functions = data
    relationships = {}

    for func in data:
        relationships[func['index']] = (func['parents'], func['children'])

    # Generate file-level graph
    print("Generating file-level graph...")
    generator = FileGraphGenerator(functions, relationships)
    html = generator.generate_html()

    # Write output
    output_file = Path('/home/gabriel/.openclaw/code/clang-call-analyzer/filegraph.html')
    write_html_file(html, str(output_file))

    print(f"\nFile-level graph generated: {output_file}")
    print("Open in browser to view")


if __name__ == '__main__':
    main()
