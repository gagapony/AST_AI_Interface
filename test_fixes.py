#!/usr/bin/env python3
"""Simple test to verify the fixes."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from compile_commands_simplifier import CompileCommandsSimplifier
from compilation_db import CompilationUnit

# Test Problem 1: Path filtering
print("=" * 60)
print("TEST 1: Path filtering with relative paths")
print("=" * 60)

# Create a test project root
project_root = "/home/gabriel/projects/smart-drying-module"
filter_paths = ["src/", "include/"]

# Initialize simplifier with project root
simplifier = CompileCommandsSimplifier(
    filter_paths=filter_paths,
    project_root=project_root
)

print(f"Project root: {project_root}")
print(f"Filter paths: {filter_paths}")
print(f"Resolved filter paths: {simplifier.resolved_filter_paths}")
print()

# Test various file paths
test_files = [
    "/home/gabriel/projects/smart-drying-module/src/main.cpp",
    "/home/gabriel/projects/smart-drying-module/include/utils.h",
    "/home/gabriel/projects/smart-drying-module/tests/test_main.cpp",
    "/usr/include/stdio.h",
]

for test_file in test_files:
    is_allowed = simplifier._is_allowed_path(test_file)
    status = "✓ ALLOWED" if is_allowed else "✗ REJECTED"
    print(f"{status}: {test_file}")

print()
print("Expected results:")
print("✓ ALLOWED: src/main.cpp")
print("✓ ALLOWED: include/utils.h")
print("✗ REJECTED: tests/test_main.cpp")
print("✗ REJECTED: /usr/include/stdio.h")
print()

# Test Problem 2: Edge label format
print("=" * 60)
print("TEST 2: Edge label format verification")
print("=" * 60)

# Simulate file_relationships structure
file_relationships = {
    "/home/gabriel/projects/smart-drying-module/src/main.cpp": {
        'outgoing': {
            "/home/gabriel/projects/smart-drying-module/include/utils.h": {
                'functions': ['call_func'],
                'line_ranges': [(10, 20)],  # Source call line ranges
                'function_indices': [5]  # Target function index
            }
        },
        'incoming': {},
        'function_count': 3
    }
}

# Simulate functions data
functions = [
    {
        'index': 5,
        'self': {
            'name': 'target_func',
            'path': '/home/gabriel/projects/smart-drying-module/include/utils.h',
            'line': (30, 40)  # Target function definition line range
        }
    }
]

# Build function index to definition map
func_index_to_def = {func['index']: func for func in functions}

# Simulate edge label generation
for source_file, rels in file_relationships.items():
    for target_file, call_info in rels['outgoing'].items():
        source_name = Path(source_file).name
        target_name = Path(target_file).name

        func_name = call_info['functions'][0]
        child_idx = call_info['function_indices'][0]

        if child_idx in func_index_to_def:
            target_func = func_index_to_def[child_idx]
            target_line_range = target_func['self']['line']
        else:
            target_line_range = call_info['line_ranges'][0]

        label = f"{source_name} ---- @ {func_name} ({target_line_range[0]}, {target_line_range[1]}) --> {target_name}"

        print(f"Source file: {source_name}")
        print(f"Target file: {target_name}")
        print(f"Called function: {func_name}")
        print(f"Target function definition line range: {target_line_range}")
        print(f"Edge label: {label}")
        print()

        # Expected format: "main.cpp ---- @ call_func (30, 40) --> utils.h"
        expected = "main.cpp ---- @ call_func (30, 40) --> utils.h"
        if label == expected:
            print("✓ Edge label format is CORRECT")
        else:
            print(f"✗ Edge label format is INCORRECT")
            print(f"  Expected: {expected}")
            print(f"  Got:      {label}")

print()
print("=" * 60)
print("TEST COMPLETE")
print("=" * 60)
