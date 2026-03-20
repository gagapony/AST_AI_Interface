#!/usr/bin/env python3
"""
Dump compile_commands.json with filtered -I, -D flags and file paths.

This creates a minimal compile_commands.json that only includes:
- -D flags (macro definitions) - all kept
- -I flags (include paths) - only those matching filter.cfg paths
- file paths - only those matching filter.cfg paths
- All other compiler flags are removed.
"""

import json
import os
import sys
from pathlib import Path


def load_filter_paths(filter_cfg_path: str) -> set:
    """
    Load filter paths from filter.cfg file.

    Args:
        filter_cfg_path: Path to filter.cfg file

    Returns:
        Set of normalized filter paths
    """
    filter_paths = set()

    if not os.path.exists(filter_cfg_path):
        print(f"Warning: Filter config not found: {filter_cfg_path}")
        return filter_paths

    with open(filter_cfg_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()

            # Skip empty lines and comments
            if not line or line.startswith('#'):
                continue

            # Normalize path
            filter_paths.add(line.rstrip('/'))

    return filter_paths


def is_allowed_path(path: str, filter_paths: set) -> bool:
    """
    Check if a path is allowed by filter.cfg.

    Args:
        path: File or include path (e.g., '/path/to/file.cpp')
        filter_paths: Set of allowed filter paths

    Returns:
        True if path matches any filter path
    """
    # Normalize path
    path = path.rstrip('/')

    for filter_path in filter_paths:
        # Check if path starts with filter path
        if path == filter_path or path.startswith(filter_path + '/'):
            return True

    return False


def filter_flags(command: str, filter_paths: set) -> tuple[str, dict]:
    """
    Filter compiler command to keep only -D and matching -I flags.

    Args:
        command: Original compiler command string
        filter_paths: Set of allowed filter paths

    Returns:
        Tuple of (filtered_command, stats_dict)
    """
    stats = {
        'original_flags': 0,
        'kept_D_flags': 0,
        'kept_I_flags': 0,
        'removed_I_flags': 0,
        'removed_other_flags': 0
    }

    # Parse command into tokens
    tokens = command.split()

    filtered_tokens = []
    i = 0

    while i < len(tokens):
        token = tokens[i]
        stats['original_flags'] += 1

        # Handle -D flags (keep all)
        if token == '-D' and i + 1 < len(tokens):
            # -D NAME (with space)
            filtered_tokens.append('-D')
            filtered_tokens.append(tokens[i + 1])
            stats['kept_D_flags'] += 1
            i += 2
            continue
        elif token.startswith('-D'):
            # -DNAME (no space)
            filtered_tokens.append(token)
            stats['kept_D_flags'] += 1
            i += 1
            continue

        # Handle -I flags (keep only if matches filter paths)
        if token == '-I' and i + 1 < len(tokens):
            # -I /path (with space)
            path = tokens[i + 1]
            if is_allowed_path(path, filter_paths):
                filtered_tokens.append('-I')
                filtered_tokens.append(path)
                stats['kept_I_flags'] += 1
            else:
                stats['removed_I_flags'] += 1
            i += 2
            continue
        elif token.startswith('-I'):
            # -I/path (no space)
            path = token[2:]  # Remove -I prefix
            if is_allowed_path(path, filter_paths):
                filtered_tokens.append(token)
                stats['kept_I_flags'] += 1
            else:
                stats['removed_I_flags'] += 1
            i += 1
            continue

        # Handle -isystem flags (filter like -I)
        if token == '-isystem' and i + 1 < len(tokens):
            # -isystem /path (with space)
            path = tokens[i + 1]
            if is_allowed_path(path, filter_paths):
                filtered_tokens.append('-isystem')
                filtered_tokens.append(path)
                stats['kept_I_flags'] += 1
            else:
                stats['removed_I_flags'] += 1
            i += 2
            continue
        elif token.startswith('-isystem'):
            # -isystem/path (no space)
            path = token[9:]  # Remove -isystem prefix
            if is_allowed_path(path, filter_paths):
                filtered_tokens.append(token)
                stats['kept_I_flags'] += 1
            else:
                stats['removed_I_flags'] += 1
            i += 1
            continue

        # Remove all other flags
        stats['removed_other_flags'] += 1
        i += 1

    # Reconstruct command
    filtered_command = ' '.join(filtered_tokens)

    return filtered_command, stats


def main():
    """Main entry point."""
    if len(sys.argv) < 4:
        print("Usage: python dump_simple_db.py <input.json> <output.json> <filter.cfg>")
        print("  input.json:   Path to original compile_commands.json")
        print("  output.json:  Path to filtered compile_commands.json")
        print("  filter.cfg:   Path to filter.cfg file")
        print()
        print("Filters applied:")
        print("  - Keep all -D flags (macro definitions)")
        print("  - Keep only -I flags matching filter.cfg paths")
        print("  - Keep only file paths matching filter.cfg paths")
        print("  - Remove all other compiler flags")
        sys.exit(1)

    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])
    filter_cfg_path = Path(sys.argv[3])

    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}")
        sys.exit(1)

    if not filter_cfg_path.exists():
        print(f"Warning: Filter config not found: {filter_cfg_path}")
        print("Will filter NOTHING (will pass through all)")
        sys.exit(1)

    # Load filter paths
    filter_paths = load_filter_paths(filter_cfg_path)

    print("=" * 60)
    print("FILTER CONFIGURATION")
    print("=" * 60)
    print(f"Filter paths ({len(filter_paths)}):")
    for path in sorted(filter_paths):
        print(f"  - {path}")
    print()

    # Load original compile_commands.json
    with open(input_path, 'r', encoding='utf-8') as f:
        compile_commands = json.load(f)

    print("=" * 60)
    print("FILTERING PROCESS")
    print("=" * 60)

    # Filter each compilation unit
    filtered_units = []
    total_stats = {
        'original_units': 0,
        'kept_units': 0,
        'removed_units': 0,
        'original_flags': 0,
        'kept_D_flags': 0,
        'kept_I_flags': 0,
        'removed_I_flags': 0,
        'removed_other_flags': 0
    }

    for unit in compile_commands:
        total_stats['original_units'] += 1

        original_command = unit.get('command', '')
        file_path = unit.get('file', '')

        # Check if file is in filter paths
        if not is_allowed_path(file_path, filter_paths):
            total_stats['removed_units'] += 1
            file_name = Path(file_path).name
            print(f"❌ Removed file: {file_name} (not in filter paths)")
            print(f"   Path: {file_path}")
            continue

        total_stats['kept_units'] += 1

        # Filter flags
        filtered_command, stats = filter_flags(original_command, filter_paths)

        filtered_unit = {
            'directory': unit.get('directory'),
            'command': filtered_command,
            'file': file_path
        }

        filtered_units.append(filtered_unit)

        # Accumulate stats
        for key in ['original_flags', 'kept_D_flags', 'kept_I_flags', 'removed_I_flags', 'removed_other_flags']:
            total_stats[key] += stats[key]

        # Show details for this unit
        file_name = Path(file_path).name
        print(f"✅ Kept file: {file_name}")
        print(f"   Original flags: {stats['original_flags']}")
        print(f"   Kept -D flags: {stats['kept_D_flags']}")
        print(f"   Kept -I flags: {stats['kept_I_flags']}")
        print(f"   Removed -I flags: {stats['removed_I_flags']}")
        print(f"   Removed other flags: {stats['removed_other_flags']}")
        print()

    # Write filtered compile_commands.json
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(filtered_units, f, indent=2)

    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total original units: {total_stats['original_units']}")
    print(f"Total kept units: {total_stats['kept_units']}")
    print(f"Total removed units: {total_stats['removed_units']}")
    print(f"Total original flags: {total_stats['original_flags']}")
    print(f"Total kept -D flags: {total_stats['kept_D_flags']}")
    print(f"Total kept -I flags: {total_stats['kept_I_flags']}")
    print(f"Total removed -I flags: {total_stats['removed_I_flags']}")
    print(f"Total removed other flags: {total_stats['removed_other_flags']}")
    print()
    print(f"✅ Filtered compile_commands.json written to: {output_path}")
    print()
    print("Filters applied:")
    print("  ✅ All -D flags kept")
    print("  ✅ -I flags filtered by filter.cfg paths")
    print("  ✅ File paths filtered by filter.cfg paths")
    print("  ✅ All other compiler flags removed")


if __name__ == '__main__':
    main()
