#!/usr/bin/env python3
"""Command-line interface for clang-call-analyzer."""

import argparse
import logging
import sys
from pathlib import Path
from typing import Dict, Optional

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

from .compilation_db import CompilationDatabase
from .ast_parser import ASTParser
from .function_extractor import FunctionExtractor, FunctionInfo
from .function_registry import FunctionRegistry
from .call_analyzer import CallAnalyzer
from .relationship_builder import RelationshipBuilder
from .json_emitter import JSONEmitter
from .flag_filter_manager import FlagFilterManager
from .filter_config import FilterConfigLoader, FilterConfig, FilterMode
from .compilation_db_filter import CompilationDatabaseFilter
from .mermaid_generator import MermaidGenerator, write_mermaid_file
from .echarts_generator import EChartsGenerator, write_html_file
from .file_graph_generator import FileGraphGenerator


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
        choices=['json', 'mermaid', 'html', 'both'],
        default='json',
        help='Output format (default: json). '
             'Options: json (JSON output), mermaid (Mermaid diagram), '
             'html (ECharts interactive graph), both (generate both JSON and HTML). '
             'If --format is html or both, --output is used for the HTML file. '
             'When format is both, JSON is written to <output>.json and HTML to <output>.html.'
    )
    parser.add_argument(
        '--mermaid', '-m',
        action='store_true',
        help='Generate Mermaid tree diagram of call relationships. '
             'Equivalent to --format mermaid. '
             'Output file is derived from --output by appending "_mermaid.md". '
             'If --output is not specified, defaults to "call_graph_mermaid.md". '
             '(Deprecated: use --format mermaid instead)'
    )
    parser.add_argument(
        '--html',
        action='store_true',
        help='Generate ECharts interactive HTML graph. '
             'Equivalent to --format html. '
             'Output file is derived from --output by replacing .json with .html. '
             'If --output is not specified, defaults to "call_graph.html". '
             '(Deprecated: use --format html instead)'
    )
    parser.add_argument(
        '--config', '-c',
        type=str,
        default=None,
        help='Path to configuration file (YAML format)'
    )
    # Filter configuration (mutually exclusive)
    filter_group = parser.add_mutually_exclusive_group()
    filter_group.add_argument(
        '--filter-cfg', '-f',
        type=str,
        default=None,
        metavar='FILE',
        help='Path to filter.cfg file (INI format filter paths). '
             'If specified, only files matching these paths are analyzed. '
             'Takes priority over --path.'
    )
    filter_group.add_argument(
        '--path', '-p',
        type=str,
        default=None,
        metavar='PATH',
        help='Filter path to analyze (single directory). '
             'Only files in this path are analyzed. '
             'Ignored if --filter-cfg is specified.'
    )

    parser.add_argument(
        '--dump-filtered-db',
        type=str,
        default=None,
        metavar='FILE',
        help='Dump filtered compile_commands.json to specified file. '
             'Useful for debugging filter configuration.'
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
    parser.add_argument(
        '--file-graph',
        action='store_true',
        help='Generate file-level call graph (file nodes with function call details). '
             'Only works with --format html. '
             'Edges show: function name @ sourceFile:line'
    )
    parser.add_argument(
        '--aggressive-filter',
        action='store_true',
        help='Apply aggressive filtering to compilation database (fast mode). '
             'Keeps: all -D flags, only -I flags matching filter.cfg, only files matching filter.cfg. '
             'Removes: all other compiler flags. '
             'This significantly speeds up parsing for large projects. '
             'Requires --filter-cfg to be specified.'
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

    # Handle backward compatibility for --mermaid and --html flags
    # These flags override --format if specified
    if args.mermaid:
        args.format = 'mermaid'
        logging.warning("--mermaid flag is deprecated, use --format mermaid instead")
    elif args.html:
        args.format = 'html'
        logging.warning("--html flag is deprecated, use --format html instead")

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
        # Load filter configuration with priority logic
        project_root = db_path.parent
        logger = logging.getLogger(__name__)

        filter_loader = FilterConfigLoader(project_root=str(project_root), logger=logger)
        filter_config = filter_loader.load(
            filter_cfg_path=args.filter_cfg,
            single_path=args.path
        )

        # Validate filter paths (warning only)
        filter_loader.validate_paths(filter_config)

        # Log filter configuration
        logging.info(f"Filter mode: {filter_config.mode.name}")
        logging.info(f"Filter scope: {filter_config.get_scope_summary()}")

        # Load compilation database
        logging.info(f"Loading compilation database from {db_path}")
        comp_db = CompilationDatabase(str(db_path))

        # Initialize flag filter manager
        flag_filter_manager = FlagFilterManager.from_config(config, logger)

        # Apply filter configuration
        units = comp_db.get_units()

        if args.aggressive_filter:
            logging.info("Applying aggressive filter mode (keeps -D and filter.cfg -I only)")
            if filter_config.mode == FilterMode.AUTO_DETECT:
                logging.error("--aggressive-filter requires --filter-cfg to be specified")
                return 1
            units = _apply_aggressive_filter(units, filter_config, logger)

        elif filter_config.mode != FilterMode.AUTO_DETECT:
            # Convert CompilationUnit to dict format for filtering
            compile_commands = [
                {
                    'file': unit.file,
                    'command': unit.command,
                    'directory': unit.directory
                }
                for unit in units
            ]

            # Filter compilation database
            db_filter = CompilationDatabaseFilter(
                filter_config=filter_config,
                project_root=str(project_root),
                logger=logger
            )

            filtered_units = db_filter.filter_compilation_db(compile_commands)

            # Dump filtered DB if requested (before converting to CompilationUnit)
            if args.dump_filtered_db:
                db_filter.dump_filtered_db(compile_commands, args.dump_filtered_db)

            # Convert back to CompilationUnit format
            units = [
                comp_db._parse_entry({
                    'file': unit.file,
                    'command': unit.command,
                    'directory': unit.directory
                })
                for unit in filtered_units
            ]

            logging.info(db_filter.get_summary())
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
                        # Filter out specific diagnostic messages to reduce noise
                        # - "unknown warning option" (libclang warning about flags)
                        # - "file not found" (system header warnings)
                        if "unknown warning option" in diag or "file not found" in diag:
                            continue  # Skip these diagnostics
                        logging.debug(f"  {diag}")

                # Prepare filter paths for FunctionExtractor
                filter_paths = None
                if filter_config.mode != FilterMode.AUTO_DETECT:
                    # Convert normalized_paths to List[Path] for FunctionExtractor
                    filter_paths = [Path(p) for p in filter_config.normalized_paths]
                    logger.debug(f"Using filter paths: {filter_paths}")

                # Extract functions
                extractor = FunctionExtractor(tu, filter_paths=filter_paths)
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

        # Filter functions by scope if filter is active (post-processing filter)
        if filter_config.mode != FilterMode.AUTO_DETECT:
            all_functions = registry.get_all()

            # Filter functions: only keep those defined within the filter scope
            filtered_indices = {i for i, f in enumerate(all_functions)
                               if filter_config.is_in_scope(f.path, str(project_root))}

            filtered_count = len(all_functions) - len(filtered_indices)
            logging.info(f"Post-processing filter: kept {len(filtered_indices)}/{len(all_functions)} functions in filter scope")
            logging.info(f"Filtered out {filtered_count} system/external functions")

            # Create index mapping: old_index -> new_index
            old_to_new = {old_idx: new_idx
                           for new_idx, old_idx in enumerate(sorted(filtered_indices))}

            # Filter relationships: only keep edges between filtered functions
            filtered_relationships = {}
            for old_idx in filtered_indices:
                old_parents, old_children = relationships.get(old_idx, ([], []))

                # Filter parents: only keep parents that are also in filtered set
                filtered_parents = sorted([old_to_new[p] for p in old_parents if p in old_to_new])

                # Filter children: only keep children that are also in filtered set
                filtered_children = sorted([old_to_new[c] for c in old_children if c in old_to_new])

                new_idx = old_to_new[old_idx]
                filtered_relationships[new_idx] = (filtered_parents, filtered_children)

            # Filter function list and add index property
            filtered_functions = []
            for new_idx, old_idx in enumerate(sorted(filtered_indices)):
                func = all_functions[old_idx]
                # Create a copy with index property for ECharts
                func_with_index = FunctionInfo(
                    path=func.path,
                    line_range=func.line_range,
                    name=func.name,
                    qualified_name=func.qualified_name,
                    brief=func.brief,
                    raw_cursor=func.raw_cursor,  # Include raw_cursor
                    index=new_idx  # Add index
                )
                filtered_functions.append(func_with_index)

            # Use filtered data
            functions_to_emit = filtered_functions
            relationships_to_emit = filtered_relationships
        else:
            functions_to_emit = registry.get_all()
            relationships_to_emit = relationships

        # Emit output based on format
        logger = logging.getLogger(__name__)

        # Determine output paths based on format
        output_paths = _determine_output_paths(args)

        # Generate outputs
        if args.format == 'json' or args.format == 'both':
            # Generate JSON output
            logging.info(f"Generating JSON output to {output_paths['json']}")
            emitter = JSONEmitter(str(output_paths['json']))
            emitter.emit(functions_to_emit, relationships_to_emit)

        if args.format == 'mermaid' or args.format == 'both':
            # Generate Mermaid diagram
            logging.info("Generating Mermaid diagram...")
            mermaid_gen = MermaidGenerator(
                functions=functions_to_emit,
                relationships=relationships_to_emit
            )
            mermaid_content = mermaid_gen.generate()
            write_mermaid_file(mermaid_content, str(output_paths['mermaid']))

        if args.format == 'html' or args.format == 'both':
            # Generate ECharts HTML
            if args.file_graph:
                # File-level graph
                logging.info("Generating file-level ECharts HTML...")
                from .file_graph_generator import FileGraphGenerator
                from .json_emitter import JSONEmitter

                # First emit JSON to temp file to get proper format
                import json as json_lib
                import os
                temp_json = '/tmp/call_analyzer_temp.json'
                json_emitter = JSONEmitter(temp_json)
                json_emitter.emit(functions_to_emit, relationships_to_emit)

                # Load the JSON to get proper format
                with open(temp_json, 'r', encoding='utf-8') as f:
                    functions_dict = json_lib.load(f)

                # Clean up temp file
                os.remove(temp_json)

                filegraph_gen = FileGraphGenerator(
                    functions=functions_dict,
                    relationships=relationships_to_emit,
                    logger=logger
                )
                html_content = filegraph_gen.generate_html()
                write_html_file(html_content, str(output_paths['html']))
            else:
                # Function-level graph (default)
                logging.info("Generating function-level ECharts HTML...")
                echarts_gen = EChartsGenerator(
                    functions=functions_to_emit,
                    relationships=relationships_to_emit,
                    logger=logger
                )
                html_content = echarts_gen.generate_html()
                write_html_file(html_content, str(output_paths['html']))

        # Print output files summary
        _print_output_summary(args.format, output_paths)

        # Print filtering summary
        flag_filter_manager.print_summary()

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
    elif args.format == 'mermaid':
        # Mermaid output uses _mermaid.md suffix
        if args.output:
            if base_path.suffix in ['.json', '.html']:
                base_name = base_path.stem
            else:
                base_name = base_path.name
            paths['mermaid'] = base_path.parent / f"{base_name}_mermaid.md"
        else:
            paths['mermaid'] = Path("call_graph_mermaid.md")
    elif args.format == 'html':
        paths['html'] = base_path if base_path.suffix == '.html' else base_path.with_suffix('.html')
    elif args.format == 'both':
        # Both format: generate JSON and HTML
        paths['json'] = base_path if base_path.suffix == '.json' else base_path.with_suffix('.json')
        paths['html'] = base_path.with_suffix('.html')
        paths['mermaid'] = None  # Not generated for 'both' format
    else:
        # Default to JSON
        paths['json'] = base_path if base_path.suffix == '.json' else base_path.with_suffix('.json')

    return paths


def _print_output_summary(format_type: str, output_paths: Dict[str, Path]) -> None:
    """
    Print summary of generated output files.

    Args:
        format_type: Output format type
        output_paths: Dictionary of output paths
    """
    print("\n" + "=" * 50)
    print("Output Generation Complete")
    print("=" * 50)

    if format_type == 'json' or format_type == 'both':
        if output_paths.get('json'):
            print(f"  JSON:  {output_paths['json']}")

    if format_type == 'mermaid':
        if output_paths.get('mermaid'):
            print(f"  Mermaid:  {output_paths['mermaid']}")

    if format_type == 'html' or format_type == 'both':
        if output_paths.get('html'):
            print(f"  HTML:  {output_paths['html']}")

    print("=" * 50 + "\n")


def _is_allowed_path(path: str, filter_paths: list) -> bool:
    """
    Check if a path is allowed by filter configuration.

    Args:
        path: File or include path
        filter_paths: List of filter paths from filter.cfg

    Returns:
        True if path matches any filter path
    """
    path = path.rstrip('/')
    for filter_path in filter_paths:
        if path == filter_path or path.startswith(filter_path + '/'):
            return True
    return False


def _apply_aggressive_filter(units, filter_config: FilterConfig, logger) -> list:
    """
    Apply aggressive filtering to compilation units.

    Keeps:
    - All -D flags (macro definitions)
    - Only -I flags matching filter.cfg paths
    - Only files matching filter.cfg paths

    Removes:
    - All -I flags not matching filter.cfg
    - All other compiler flags (-std, -O, -Wall, etc.)

    Args:
        units: List of CompilationUnit objects
        filter_config: FilterConfig instance
        logger: Logger instance

    Returns:
        List of filtered CompilationUnit objects
    """
    from .compilation_db import CompilationUnit

    filter_paths = filter_config.normalized_paths

    filtered_units = []
    stats = {
        'original_units': len(units),
        'kept_units': 0,
        'removed_units': 0,
        'kept_D_flags': 0,
        'kept_I_flags': 0,
        'removed_I_flags': 0,
        'removed_other_flags': 0
    }

    for unit in units:
        # Check if file is in filter paths
        if not _is_allowed_path(unit.file, filter_paths):
            stats['removed_units'] += 1
            logger.debug(f"Aggressive filter: Removed file {unit.file} (not in filter paths)")
            continue

        # Filter flags
        tokens = unit.command.split()
        filtered_tokens = []
        i = 0

        while i < len(tokens):
            token = tokens[i]

            # Keep all -D flags
            if token == '-D' and i + 1 < len(tokens):
                filtered_tokens.append('-D')
                filtered_tokens.append(tokens[i + 1])
                stats['kept_D_flags'] += 1
                i += 2
                continue
            elif token.startswith('-D'):
                filtered_tokens.append(token)
                stats['kept_D_flags'] += 1
                i += 1
                continue

            # Keep -I flags only if they match filter paths
            if token == '-I' and i + 1 < len(tokens):
                path = tokens[i + 1]
                if _is_allowed_path(path, filter_paths):
                    filtered_tokens.append('-I')
                    filtered_tokens.append(path)
                    stats['kept_I_flags'] += 1
                else:
                    stats['removed_I_flags'] += 1
                i += 2
                continue
            elif token.startswith('-I'):
                path = token[2:]
                if _is_allowed_path(path, filter_paths):
                    filtered_tokens.append(token)
                    stats['kept_I_flags'] += 1
                else:
                    stats['removed_I_flags'] += 1
                i += 1
                continue

            # Keep -isystem flags only if they match filter paths
            if token == '-isystem' and i + 1 < len(tokens):
                path = tokens[i + 1]
                if _is_allowed_path(path, filter_paths):
                    filtered_tokens.append('-isystem')
                    filtered_tokens.append(path)
                    stats['kept_I_flags'] += 1
                else:
                    stats['removed_I_flags'] += 1
                i += 2
                continue
            elif token.startswith('-isystem'):
                path = token[9:]
                if _is_allowed_path(path, filter_paths):
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

        # Re-extract flags from filtered command
        import shlex
        filtered_flags = []

        # Use same logic as CompilationDatabase._extract_flags
        tokens = shlex.split(filtered_command)
        i = 0
        while i < len(tokens):
            token = tokens[i]

            # Skip compiler executable
            if token.endswith('++') or token.endswith('gcc') or token.endswith('clang'):
                i += 1
                continue

            # Skip output file option
            if token == '-o':
                if i + 1 < len(tokens):
                    i += 2
                    continue
                else:
                    i += 1
                    continue

            # Collect flags (start with -)
            if token.startswith('-') and not token.startswith('--'):
                filtered_flags.append(token)
                i += 1
            else:
                i += 1

        # Create filtered unit
        from .compilation_db import CompilationUnit
        filtered_unit = CompilationUnit(
            directory=unit.directory,
            command=filtered_command,
            file=unit.file,
            flags=filtered_flags
        )

        filtered_units.append(filtered_unit)
        stats['kept_units'] += 1

    # Log summary
    logger.info("=" * 60)
    logger.info("AGGRESSIVE FILTER SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Original units: {stats['original_units']}")
    logger.info(f"Kept units: {stats['kept_units']}")
    logger.info(f"Removed units: {stats['removed_units']}")
    logger.info(f"Kept -D flags: {stats['kept_D_flags']}")
    logger.info(f"Kept -I flags: {stats['kept_I_flags']}")
    logger.info(f"Removed -I flags: {stats['removed_I_flags']}")
    logger.info(f"Removed other flags: {stats['removed_other_flags']}")
    logger.info("=" * 60)

    return filtered_units


if __name__ == '__main__':
    sys.exit(main())
