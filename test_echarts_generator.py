#!/usr/bin/env python3
"""Test script for ECharts generator."""

import json
import logging
from pathlib import Path

from src.echarts_generator import EChartsGenerator, write_html_file
from src.function_extractor import FunctionInfo


def load_json_data(json_path: str):
    """Load JSON data from file."""
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Parse functions
    functions = []
    for func_data in data['functions']:
        func = FunctionInfo(
            index=func_data['index'],
            name=func_data['self']['name'],
            path=func_data['self']['path'],
            line_range=tuple(func_data['self']['line_range']),
            brief=func_data['self'].get('brief', ''),
            parents=func_data.get('parents', []),
            children=func_data.get('children', [])
        )
        functions.append(func)

    # Parse relationships
    relationships = {}
    for func_data in data['functions']:
        idx = func_data['index']
        parents = func_data.get('parents', [])
        children = func_data.get('children', [])
        relationships[idx] = (parents, children)

    return functions, relationships


def test_echarts_generator():
    """Test ECharts generator."""
    logging.basicConfig(level=logging.INFO)

    # Load data
    json_path = Path('output.json')
    if not json_path.exists():
        print(f"Error: {json_path} not found")
        return

    print(f"Loading data from {json_path}...")
    functions, relationships = load_json_data(str(json_path))
    print(f"Loaded {len(functions)} functions")

    # Generate HTML
    print("Generating ECharts HTML...")
    echarts_gen = EChartsGenerator(
        functions=functions,
        relationships=relationships
    )
    html_content = echarts_gen.generate_html()

    # Write to file
    output_path = Path('test_output_echarts.html')
    write_html_file(html_content, str(output_path))

    print(f"Test complete! Open {output_path} in your browser.")


if __name__ == '__main__':
    test_echarts_generator()
