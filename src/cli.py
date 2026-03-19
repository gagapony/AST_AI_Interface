#!/usr/bin/env python3
"""Command-line interface for clang-call-analyzer."""

import argparse
import logging
import sys
from pathlib import Path
from typing import Optional

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

from .compilation_db import CompilationDatabase
from .ast_parser import ASTParser
from .function_extractor import FunctionExtractor
from .function_registry import FunctionRegistry
from .call_analyzer import CallAnalyzer
from .relationship_builder import RelationshipBuilder
from .json_emitter import JSONEmitter
from .flag_filter_manager import FlagFilterManager


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
        '--config', '-c',
        type=str,
        default=None,
        help='Path to configuration file (YAML format)'
    )
    parser.add_argument(
        '--path', '-p',
        type=str,
        default=None,
        help='Filter: only analyze files in this path (recursive)'
    )
    parser.add_argument(
        '--verbose', '-v',
        type=str,
        choices=['error', 'warning', 'info', 'debug'],
        default='warning',
        help='Logging level (default: warning)'
    )
    parser.add_argument(
        '--disable-retry',
        action='store_true',
        help='Disable adaptive retry (parse with whitelisted flags only)'
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


def load_config(config_path: Optional[str]) -> dict:
    """
    Load configuration from YAML file.

    Args:
        config_path: Path to config file, or None for default config

    Returns:
        Configuration dictionary
    """
    if not config_path:
        # Return default empty config
        return {}

    if not YAML_AVAILABLE:
        logging.warning("PyYAML not available, ignoring config file")
        return {}

    config_file = Path(config_path)
    if not config_file.exists():
        logging.error(f"Config file not found: {config_path}")
        return {}

    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f) or {}
        logging.info(f"Loaded configuration from {config_path}")
        return config
    except Exception as e:
        logging.error(f"Failed to load config: {e}")
        return {}


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

    # Load configuration
    config = load_config(args.config)

    # Override retry setting from command line
    if args.disable_retry:
        config['flag_filter'] = config.get('flag_filter', {})
        config['flag_filter']['enable_retry'] = False

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

        # Initialize flag filter manager
        flag_filter_manager = FlagFilterManager.from_config(config, logging.getLogger(__name__))

        # Apply path filter if specified
        units = comp_db.get_units()
        if args.path:
            filter_path = Path(args.path).resolve()
            original_count = len(units)
            units = [u for u in units if Path(u.file).is_relative_to(filter_path)]
            filtered_count = original_count - len(units)
            logging.info(f"Path filter: {filter_path}")
            logging.info(f"Filtered {filtered_count}/{original_count} compilation units")
            logging.info(f"Analyzing {len(units)} units in specified path")
        else:
            logging.info(f"Analyzing all {len(units)} compilation units")

        # Initialize function registry
        registry = FunctionRegistry()

        # Parse each translation unit
        for unit in units:
            logging.info(f"Parsing {unit.file}")
            try:
                # Parse AST with adaptive flag filtering
                parser = ASTParser(unit.flags, flag_filter_manager)
                tu = parser.parse_file(unit.file)

                if not tu:
                    logging.warning(f"Failed to parse {unit.file}")
                    continue

                # Check for diagnostics
                diags = parser.get_diagnostics()
                if diags:
                    for diag in diags:
                        logging.debug(f"  {diag}")

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

        # Print filtering summary
        flag_filter_manager.print_summary()

        logging.info("Analysis complete")
        return 0

    except Exception as e:
        logging.error(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
