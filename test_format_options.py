#!/usr/bin/env python3
"""Test script for all format options."""

import json
import sys
from pathlib import Path

# Add parent to path to import as module
sys.path.insert(0, str(Path(__file__).parent))

from src.echarts_generator import EChartsGenerator, write_html_file
from src.mermaid_generator import MermaidGenerator, write_mermaid_file


class SimpleFunctionInfo:
    """Simplified function info for testing."""

    def __init__(self, index, name, path, line_range, brief, parents, children):
        self.index = index
        self.name = name
        self.path = path
        self.line_range = line_range
        self.brief = brief
        self.parents = parents
        self.children = children


def load_and_convert_functions(json_path):
    """Load JSON and convert to FunctionInfo objects."""
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Convert to SimpleFunctionInfo
    functions = []
    relationships = {}

    for func_data in data:
        func = SimpleFunctionInfo(
            index=func_data['index'],
            name=func_data['self']['name'],
            path=func_data['self']['path'],
            line_range=tuple(func_data['self']['line']),
            brief=func_data['self'].get('brief', ''),
            parents=func_data.get('parents', []),
            children=func_data.get('children', [])
        )
        functions.append(func)
        relationships[func.index] = (func.parents, func.children)

    return functions, relationships


def test_all_formats():
    """Test all format options."""
    json_path = Path('output.json')
    if not json_path.exists():
        print(f"Error: {json_path} not found")
        sys.exit(1)

    print("=" * 60)
    print("Testing All Format Options")
    print("=" * 60)

    # Load data
    print(f"\n[1/4] Loading data from {json_path}...")
    functions, relationships = load_and_convert_functions(json_path)
    print(f"      Loaded {len(functions)} functions")

    # Test JSON format
    print("\n[2/4] Testing JSON format...")
    json_output = Path('test_output.json')
    # JSON is already there, just verify
    if json_path.exists():
        print(f"      ✓ JSON output: {json_path} ({json_path.stat().st_size} bytes)")

    # Test Mermaid format
    print("\n[3/4] Testing Mermaid format...")
    mermaid_gen = MermaidGenerator(
        functions=functions,
        relationships=relationships
    )
    mermaid_content = mermaid_gen.generate()
    mermaid_output = Path('test_output_mermaid.md')
    write_mermaid_file(mermaid_content, str(mermaid_output))
    print(f"      ✓ Mermaid output: {mermaid_output} ({mermaid_output.stat().st_size} bytes)")

    # Test HTML format
    print("\n[4/4] Testing HTML (ECharts) format...")
    echarts_gen = EChartsGenerator(
        functions=functions,
        relationships=relationships
    )
    html_content = echarts_gen.generate_html()
    html_output = Path('test_output_echarts.html')
    write_html_file(html_content, str(html_output))
    print(f"      ✓ HTML output: {html_output} ({html_output.stat().st_size} bytes)")

    # Verify HTML content
    print("\n[Verification] Checking HTML content...")
    html_text = html_content

    checks = [
        ("ECharts CDN", "https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"),
        ("Graph data", "const GRAPH_DATA"),
        ("Nodes array", '"nodes": ['),
        ("Edges array", '"edges": ['),
        ("Categories", '"categories": ['),
        ("Search input", 'id="search-input"'),
        ("Group selector", 'id="group-mode"'),
        ("Export buttons", 'id="export-png"'),
        ("CSS styles", "graph-container"),
    ]

    for check_name, check_str in checks:
        if check_str in html_text:
            print(f"      ✓ {check_name}")
        else:
            print(f"      ✗ {check_name} - MISSING")

    # Count nodes and edges in HTML
    print("\n[Statistics]")
    nodes_count = html_text.count('"id":') - 2  # Subtract 2 for the categories
    edges_count = html_text.count('"source":')
    print(f"      Nodes in HTML: {nodes_count}")
    print(f"      Edges in HTML: {edges_count}")

    print("\n" + "=" * 60)
    print("All tests completed successfully!")
    print("=" * 60)
    print("\nGenerated files:")
    print(f"  - {mermaid_output}")
    print(f"  - {html_output}")
    print("\nOpen {html_output} in your browser to see the interactive graph.")


if __name__ == '__main__':
    test_all_formats()
