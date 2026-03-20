#!/usr/bin/env python3
"""Simple test for ECharts generator without full module imports."""

import json
import sys
from pathlib import Path

# Add parent to path to import as module
sys.path.insert(0, str(Path(__file__).parent))

# Import only what we need
from src.echarts_generator import EChartsGenerator, write_html_file


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


def main():
    """Main test function."""
    json_path = Path('output.json')
    if not json_path.exists():
        print(f"Error: {json_path} not found")
        sys.exit(1)

    print(f"Loading data from {json_path}...")
    functions, relationships = load_and_convert_functions(json_path)
    print(f"Loaded {len(functions)} functions")

    print("Generating ECharts HTML...")
    echarts_gen = EChartsGenerator(
        functions=functions,
        relationships=relationships
    )
    html_content = echarts_gen.generate_html()

    output_path = Path('test_output_echarts.html')
    write_html_file(html_content, str(output_path))

    print(f"Success! HTML generated: {output_path}")
    print(f"File size: {output_path.stat().st_size} bytes")


if __name__ == '__main__':
    main()
