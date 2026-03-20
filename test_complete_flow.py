#!/usr/bin/env python3
"""Complete integration test for ECharts generator."""

import json
import sys
sys.path.insert(0, 'src')

# Import without relative import
from src.echarts_generator import EChartsGenerator, write_html_file


# Mock FunctionInfo class
class MockFunctionInfo:
    """Mock function info for testing."""
    def __init__(self, index, name, path, line_range, brief='', parents=None, children=None):
        self.index = index
        self.name = name
        self.path = path
        self.line_range = line_range
        self.brief = brief
        self.parents = parents or []
        self.children = children or []


def create_test_data():
    """Create test function data."""
    functions = [
        MockFunctionInfo(
            0, 'main', '/src/main.cpp', (1, 10),
            'Main entry point', [], [1, 2]
        ),
        MockFunctionInfo(
            1, 'init', '/src/init.cpp', (1, 20),
            'Initialize system', [0], []
        ),
        MockFunctionInfo(
            2, 'process', '/src/process.cpp', (1, 30),
            'Process data', [0], []
        ),
    ]

    relationships = {
        0: ([], [1, 2]),
        1: ([0], []),
        2: ([0], []),
    }

    return functions, relationships


def test_complete_flow():
    """Test the complete ECharts generation flow."""
    print("="*60)
    print("COMPLETE INTEGRATION TEST")
    print("="*60)

    # Create test data
    print("\n1. Creating test data...")
    functions, relationships = create_test_data()
    print(f"   Created {len(functions)} functions")

    # Generate HTML
    print("\n2. Generating ECharts HTML...")
    generator = EChartsGenerator(functions, relationships)
    html = generator.generate_html()
    print(f"   Generated {len(html)} bytes of HTML")

    # Validate HTML
    print("\n3. Validating HTML...")

    issues = []

    # Check structure
    if '<!DOCTYPE html>' in html:
        print("   ✅ HTML5 doctype")
    else:
        issues.append("Missing HTML5 doctype")

    if '</html>' in html:
        print("   ✅ HTML closing tag")
    else:
        issues.append("Missing HTML closing tag")

    # Check embedded data
    if 'const GRAPH_DATA' in html:
        print("   ✅ Graph data embedded")
    else:
        issues.append("Graph data not embedded")

    if '"nodes"' in html and '"edges"' in html:
        print("   ✅ Nodes and edges in data")
    else:
        issues.append("Nodes or edges missing from data")

    # Check JavaScript code
    if 'let chart;' in html:
        print("   ✅ Chart variable defined")
    else:
        issues.append("Chart variable not defined")

    if 'function initGraph()' in html:
        print("   ✅ initGraph function present")
    else:
        issues.append("initGraph function missing")

    if 'echarts.init' in html:
        print("   ✅ ECharts initialization")
    else:
        issues.append("ECharts initialization missing")

    # Check for template placeholders that weren't replaced
    if '{app_script}' in html or '$app_script' in html:
        issues.append("Unreplaced placeholder found")
    else:
        print("   ✅ No unreplaced placeholders")

    # Check for malformed JavaScript
    if '{{{' in html:
        issues.append(f"Found triple braces - will break JavaScript")
    else:
        print("   ✅ No triple braces")

    if '{{{{' in html:
        issues.append(f"Found quad braces - will break JavaScript")
    else:
        print("   ✅ No quad braces")

    # Check that JavaScript functions have correct syntax
    if 'function initGraph() {' in html:
        print("   ✅ Function syntax correct")
    else:
        issues.append("Function syntax incorrect")

    # Check for ES6 template strings
    if '${data.name}' in html:
        print("   ✅ ES6 template strings preserved")
    else:
        print("   ⚠️  Warning: ES6 template strings not found")

    # Write output
    print("\n4. Writing output file...")
    output_file = 'test_complete_output.html'
    write_html_file(html, output_file)
    print(f"   ✅ Written to {output_file}")

    # Summary
    print("\n" + "="*60)
    if issues:
        print("❌ TEST FAILED")
        print("="*60)
        print("\nIssues found:")
        for issue in issues:
            print(f"   - {issue}")
        return False
    else:
        print("✅ ALL TESTS PASSED!")
        print("="*60)
        print("\nThe ECharts generator is working correctly.")
        print(f"Open {output_file} in your browser to view the graph.")
        return True


if __name__ == '__main__':
    success = test_complete_flow()
    sys.exit(0 if success else 1)
