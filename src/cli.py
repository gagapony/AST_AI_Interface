#!/usr/bin/env python3
"""Command-line interface for clang-call-analyzer."""

import argparse
import logging
import sys
from pathlib import Path
from typing import Optional

from .compilation_db import CompilationDatabase
from .ast_parser import ASTParser
from .function_extractor import FunctionExtractor
from .function_registry import FunctionRegistry
from .call_analyzer import CallAnalyzer
from .relationship_builder import RelationshipBuilder
from .json_emitter import JSONEmitter


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


def find_compile_commands(start_dir: Path) -> Optional[Path]:
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

    return None


def main() -> int:
    """Main entry point."""
    args = parse_args()
    setup_logging(args.verbose)

    # Find compile_commands.json
    if args.input:
        db_path = Path(args.input)
    else:
        db_path = find_compile_commands(Path.cwd())

    if not db_path or not db_path.exists():
        logging.error(f"compile_commands.json not found. Specify with --input")
        return 1

    try:
        # Load compilation database
        logging.info(f"Loading compilation database from {db_path}")
        comp_db = CompilationDatabase(str(db_path))
        comp_db.load()

        # Initialize function registry
        registry = FunctionRegistry()

        # Parse each translation unit
        for unit in comp_db.get_units():
            logging.debug(f"Parsing {unit.file}")
            try:
                # Parse AST
                parser = ASTParser(unit.flags)
                tu = parser.parse_file(unit.file)

                if not tu:
                    logging.warning(f"Failed to parse {unit.file}")
                    continue

                # Check for diagnostics
                diags = parser.get_diagnostics()
                if diags:
                    logging.warning(f"Diagnostics for {unit.file}:")
                    for diag in diags:
                        logging.warning(f"  {diag}")

                # Extract functions
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

        # Emit output
        logging.info(f"Generating output to {args.output if args.output else 'stdout'}")
        emitter = JSONEmitter(args.output)
        emitter.emit(registry.get_all(), relationships)

        logging.info("Analysis complete")
        return 0

    except Exception as e:
        logging.error(f"Fatal error: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())
