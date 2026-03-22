#!/usr/bin/env python3
"""Command-line interface for clang-call-analyzer."""

import argparse
import json as json_lib
import logging
import os
import sys
from pathlib import Path
from typing import Dict

from .compilation_db import CompilationDatabase
from .ast_parser import ASTParser
from .function_extractor import FunctionExtractor
from .function_registry import FunctionRegistry
from .call_analyzer import CallAnalyzer
from .relationship_builder import RelationshipBuilder
from .json_emitter import JSONEmitter
from .file_graph_generator import FileGraphGenerator, write_html_file
from .compile_commands_simplifier import CompileCommandsSimplifier


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description='Analyze C/C++ code and extract function call relationships',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        '--input', '-i',
        type=str,
        default=None,
        help='Path to compile_commands.json (default: auto-detect)'
    )
    parser.add_argument(
        '--output', '-o',
        type=str,
        default=None,
        help='Output file path (default: stdout)'
    )
    parser.add_argument(
        '--format', '-F',
        type=str,
        choices=['json', 'html'],
        default='json',
        help='Output format (default: json). '
             'Options: json (JSON output), html (HTML from JSON). '
             'HTML is always generated from JSON file.'
    )
    parser.add_argument(
        '--verbose', '-v',
        type=str,
        choices=['error', 'warning', 'info', 'debug'],
        default='warning',
        help='Logging level (default: warning)'
    )
    parser.add_argument(
        '--version',
        action='version',
        version='clang-call-analyzer 1.0.0'
    )
    # Add --filter-cfg option for flexible file selection
    parser.add_argument(
        '--filter-cfg', '-f',
        type=str,
        default=None,
        metavar='FILE',
        help='Filter.cfg file (INI format). '
             'If specified, only files/paths in this file are analyzed. '
             'Supports multiple paths (one per line).'
    )
    # Add --simple-db-path option for customizing simplified database path
    parser.add_argument(
        '--simple-db-path',
        type=str,
        default=None,
        metavar='FILE',
        help='Custom path for compile_commands_simple.json. '
             'Default: compile_commands_simple.json in the current directory. '
             'This file contains only -D flags and all -I flags.'
    )

    return parser.parse_args()


def setup_logging(level: str) -> None:
    """Configure logging based on verbosity level."""
    level_map = {
        'error': logging.ERROR,
        'warning': logging.WARNING,
        'info': logging.INFO,
        'debug': logging.DEBUG
    }

    logging.basicConfig(
        level=level_map[level],
        format='%(levelname)s: %(message)s'
    )


def find_compile_commands(start_dir: Path) -> Path:
    """Search for compile_commands.json in parent directories."""
    current = start_dir.absolute()

    while current != current.parent:
        compile_db = current / 'build' / 'compile_commands.json'
        if compile_db.exists():
            logging.info(f"Found compile_commands.json at {compile_db}")
            return compile_db

        compile_db = current / 'compile_commands.json'
        if compile_db.exists():
            logging.info(f"Found compile_commands.json at {compile_db}")
            return compile_db

        current = current.parent

    # Not found
    raise FileNotFoundError(
        f"compile_commands.json not found in {start_dir} or any parent directory"
    )


def read_filter_cfg(cfg_path: str) -> list:
    """
    Read filter.cfg file and return list of paths.

    Args:
        cfg_path: Path to filter.cfg file

    Returns:
        List of paths (one per line, stripped)
    """
    paths = []
    with open(cfg_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):  # Skip comments
                paths.append(line)
    return paths


def main() -> int:
    """Main entry point."""
    args = parse_args()
    setup_logging(args.verbose)

    # Find compile_commands.json
    if args.input:
        db_path = Path(args.input)
    else:
        try:
            db_path = find_compile_commands(Path.cwd())
        except FileNotFoundError as e:
            logging.error(str(e))
            return 1

    if not db_path.exists():
        logging.error(f"compile_commands.json not found at {db_path}")
        return 1

    try:
        # Load compilation database
        logging.info(f"Loading compilation database from {db_path}")
        comp_db = CompilationDatabase(str(db_path))

        # Get compilation units
        units = comp_db.get_units()
        logging.info(f"Analyzing {len(units)} compilation units")

        # Initialize function registry
        registry = FunctionRegistry()

        # Generate compile_commands_simple.json (always, for performance)
        logger = logging.getLogger(__name__)
        logging.info("Generating compile_commands_simple.json for performance optimization")
        
        # Read filter paths if --filter-cfg is specified
        filter_paths = []
        if args.filter_cfg:
            filter_paths = read_filter_cfg(args.filter_cfg)
            logging.info(f"Filtering to {len(filter_paths)} paths from --filter-cfg")
        
        # Get project root (directory containing compile_commands.json)
        project_root = str(db_path.parent)
        logging.info(f"Project root: {project_root}")

        # Simplify compilation units
        simplifier = CompileCommandsSimplifier(
            filter_paths=filter_paths,
            project_root=project_root,
            logger=logger
        )
        simplified_units, simple_db_stats = simplifier.simplify_units(units)
        
        # Log simplification summary
        logging.info("=" * 60)
        logging.info("SIMPLIFIED COMPILE COMMANDS SUMMARY")
        logging.info("=" * 60)
        logging.info(f"Original units: {simple_db_stats['original_units']}")
        logging.info(f"Kept units: {simple_db_stats['kept_units']}")
        logging.info(f"Removed units: {simple_db_stats['removed_units']}")
        logging.info(f"Kept -D flags: {simple_db_stats['kept_D_flags']}")
        logging.info(f"Kept -I flags: {simple_db_stats['kept_I_flags']}")
        logging.info(f"Removed -I flags: {simple_db_stats['removed_I_flags']}")
        logging.info(f"Removed other flags: {simple_db_stats['removed_other_flags']}")
        logging.info("=" * 60)

        # Always export simplified DB to compile_commands_simple.json
        # Use custom path if provided via --simple-db-path
        simple_db_path = args.simple_db_path if args.simple_db_path else 'compile_commands_simple.json'
        logging.info(f"Writing compile_commands_simple.json to {simple_db_path}")
        simplifier.dump_to_file(simplified_units, simple_db_path)

        # Parse with simplified units
        units_to_parse = simplified_units
        logging.info(f"Parsing {len(units_to_parse)} simplified compilation units")

        for unit in units_to_parse:
            logging.info(f"Parsing {unit.file}")
            try:
                # Parse AST (no adaptive filtering, use all flags)
                parser = ASTParser(unit.flags)
                tu = parser.parse_file(unit.file)

                if not tu:
                    logging.warning(f"Failed to parse {unit.file}")
                    continue

                # Check for diagnostics
                diags = parser.get_diagnostics()
                if diags:
                    for diag in diags:
                        # Filter out specific diagnostic messages to reduce noise
                        if "unknown warning option" in diag or "file not found" in diag:
                            continue  # Skip these diagnostics
                        logging.debug(f"  {diag}")

                # Extract functions (no filter paths)
                extractor = FunctionExtractor(tu)
                functions = extractor.extract()

                for func in functions:
                    registry.add_function(func)

                logging.debug(f"  Found {len(functions)} functions")

            except Exception as e:
                logging.error(f"Error processing {unit.file}: {e}")
                continue

        logging.info(f"Total functions found: {registry.count()}")

        # Build call relationships
        logging.info("Building call relationships")
        call_analyzer = CallAnalyzer(registry)
        relationship_builder = RelationshipBuilder(registry, call_analyzer)
        relationships = relationship_builder.build()

        # Get functions to emit
        functions_to_emit = registry.get_all()
        relationships_to_emit = relationships

        # Determine output paths
        output_paths = _determine_output_paths(args)

        # Generate outputs
        logger = logging.getLogger(__name__)

        # Step 1: Generate JSON first (required for html format)
        json_path = None
        if args.format == 'html':
            json_path = Path(str(output_paths.get('json', '/tmp/call_graph_temp.json')))
            logging.info(f"Generating JSON output to {json_path}")
            emitter = JSONEmitter(str(json_path))
            emitter.emit(functions_to_emit, relationships_to_emit)
            logging.info(f"JSON generated at {json_path}")

        # Step 2: Generate JSON output for json format
        if args.format == 'json':
            logging.info(f"Generating JSON output to {output_paths['json']}")
            emitter = JSONEmitter(str(output_paths['json']))
            emitter.emit(functions_to_emit, relationships_to_emit)
            logging.info(f"JSON output: {output_paths.get('json')}")

        # Step 3: Generate HTML (always from JSON file)
        if args.format == 'html':
            logging.info("Generating file-level HTML graph from JSON...")
            if not json_path:
                logging.error("JSON path not available for HTML generation")
                return 1

            # Load JSON
            with open(json_path, 'r', encoding='utf-8') as f:
                functions_dict = json_lib.load(f)

            # Remove temporary JSON file if it was temporary
            if 'call_graph_temp.json' in str(json_path):
                os.remove(json_path)
                logging.info(f"Removed temporary JSON file: {json_path}")

            # Generate HTML from JSON using FileGraphGenerator
            # Only pass functions_dict - FileGraphGenerator rebuilds relationships from it
            file_gen = FileGraphGenerator(
                functions=functions_dict,
                logger=logger
            )
            html_content = file_gen.generate_html()
            write_html_file(html_content, str(output_paths['html']))
            logging.info(f"HTML output: {output_paths.get('html')}")

        # Print output files summary
        _print_output_summary(args.format, output_paths)

        logging.info("Analysis complete")
        return 0

    except Exception as e:
        logging.error(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
        return 1


def _determine_output_paths(args: argparse.Namespace) -> Dict[str, Path]:
    """
    Determine output file paths based on format and arguments.

    Args:
        args: Parsed command-line arguments

    Returns:
        Dictionary mapping format names to output paths
    """
    paths = {}

    # Determine base output path
    if args.output:
        base_path = Path(args.output)
    else:
        base_path = Path("output")

    # Set paths based on format
    if args.format == 'json':
        paths['json'] = base_path if base_path.suffix == '.json' else base_path.with_suffix('.json')
    elif args.format == 'html':
        paths['json'] = base_path.with_suffix('.json')  # Always generate JSON first
        paths['html'] = base_path if base_path.suffix == '.html' else base_path.with_suffix('.html')
    else:
        # Default to JSON
        paths['json'] = base_path if base_path.suffix == '.json' else base_path.with_suffix('.json')

    return paths


def _print_output_summary(format_type: str, output_paths: Dict[str, Path]) -> None:
    """
    Print summary of generated output files.

    Args:
        format_type: Output format type (json, html)
        output_paths: Dictionary of output paths
    """
    print("\n" + "=" * 50)
    print("Output Generation Complete")
    print("=" * 50)

    if format_type == 'json':
        if output_paths.get('json'):
            print(f"  JSON:  {output_paths['json']}")

    if format_type == 'html':
        if output_paths.get('html'):
            print(f"  JSON:  {output_paths.get('json')}")
            print(f"  HTML:  {output_paths.get('html')}")

    print("=" * 50 + "\n")


if __name__ == '__main__':
    sys.exit(main())
