# clang-call-analyzer - Refactoring Plan

## Overview

This plan simplifies clang-call-analyzer by removing YAML config and path filtering, but keeps file simplification and flexible file selection.

---

## User Requirements

### 1. Keep Workflow
```
compile_commands.json -> compile_commands_simple.json -> output.json -> output.html
```

### 2. Preserve Essential Options

**Keep these CLI options:**
- `--input, -i INPUT` - Path to compile_commands.json
- `--output, -o OUTPUT` - Output file path
- `--format, -F {json,html}` - Output format
- `--verbose, -v LEVEL` - Logging level
- `--version` - Show program version
- `--dump-simple-db FILE` - Dump simplified compile_commands.json (for debugging/optimization)
- `--filter-cfg, -f FILE` - Filter.cfg file (INI format) - specify files/paths to analyze

### 3. Remove YAML Config and Path Filtering

**Remove these CLI options and ALL associated code:**
- `--config, -c CONFIG` - YAML configuration file
- `--path, -p PATH` - Filter path to analyze single directory

**Note:** `--filter-cfg` is kept (not removed) for flexible file/selection.

### 4. HTML Generation
- HTML's ONLY input is JSON file
- Use FileGraphGenerator for file-level visualization
- No direct code-to-HTML path

### 5. HTML Visualization
- Each node = FILE
- Lines between nodes = function call relationships
- On lines, display: `"func @ file(start_line-end_line)"`

### 6. Output Behavior
- When `--format html` is specified, output BOTH `output.json` AND `output.html`

---

## Architecture

### File Simplification (compile_commands_simple.json)

The tool automatically generates a simplified version of compile_commands.json:

**Kept flags:**
- All `-D` macro definitions
- Only `-I` include paths (no filtering, keeps all)
- All source files

**Removed flags:**
- All other compiler flags (`-std`, `-O`, `-Wall`, etc.)
- System library `-I` paths (if detected)

This improves parsing performance without filtering.

---

## Files to DELETE

### YAML Config and Path Filtering Files
```
src/filter_config.py
src/compilation_db_filter.py
src/adaptive_flag_parser.py
src/flag_filter_manager.py
src/flag_whitelist.py
```

### Filter-Related Test Files
```
tests/test_filter_config.py
tests/test_filter/  # Entire directory
```

---

## Files to MODIFY

### src/cli.py

**Remove imports:**
```python
# Remove these imports:
from .filter_config import FilterConfigLoader, FilterConfig, FilterMode
from .compilation_db_filter import CompilationDatabaseFilter
from .flag_filter_manager import FlagFilterManager
from .adaptive_flag_parser import AdaptiveFlagParser

# Remove YAML import
try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False
```

**Remove CLI arguments:**
```python
# Remove --config argument
parser.add_argument('--config', '-c', ...)

# Remove --path argument
parser.add_argument('--path', '-p', ...)

# Remove --dump-filtered-db argument
parser.add_argument('--dump-filtered-db', ...)

# Remove --disable-retry argument
parser.add_argument('--disable-retry', ...)
```

**Remove functions:**
```python
# Remove:
def load_config(config_path: Optional[str]) -> dict

# Remove (if exists):
def _apply_aggressive_filter(...)
```

**Add/Update CLI arguments:**
```python
# Keep/update --filter-cfg for flexible file selection
filter_group = parser.add_mutually_exclusive_group()
filter_group.add_argument(
    '--filter-cfg', '-f',
    type=str,
    default=None,
    metavar='FILE',
    help='Filter.cfg file (INI format). '
         'If specified, only files/paths in this file are analyzed. '
         'Supports multiple paths (one per line).'
)

# Keep/update --dump-simple-db for exporting simplified database
parser.add_argument(
    '--dump-simple-db',
    type=str,
    default=None,
    metavar='FILE',
    help='Dump simplified compile_commands.json to specified file. '
         'Contains only -D flags and all -I flags. '
         'Useful for debugging and optimization.'
)
```

**Simplify main() function:**

Remove all filter logic:
- Remove `config = load_config(args.config)`
- Remove `flag_filter_manager` initialization
- Remove path filtering logic
- Keep file simplification (compile_commands_simple.json generation)
- Keep flexible file selection via `--filter-cfg`

**Update main() flow:**

```python
# Generate compile_commands_simple.json (always, for performance)
logging.info("Generating compile_commands_simple.json for performance optimization")

from .compile_commands_simplifier import CompileCommandsSimplifier
simplifier = CompileCommandsSimplifier(logger=logger)
units, simple_db_stats = simplifier.simplify_units(units)

# Log summary
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

# Export simplified DB if requested
if args.dump_simple_db:
    simplifier.dump_to_file(units, args.dump_simple_db)

# Parse with simplified units
units = simplified_units

# Filter files based on --filter-cfg
if args.filter_cfg:
    # Read filter.cfg file
    with open(args.filter_cfg, 'r') as f:
        filter_paths = [line.strip() for line in f if line.strip()]
    
    logging.info(f"Filtering to {len(filter_paths)} paths from --filter-cfg")
    
    # Filter units
    filtered_units = []
    for unit in units:
        # Check if file path matches any filter path
        file_path = unit.file
        if any(file_path.startswith(p) or file_path.startswith(p.rstrip('/'))
               for p in filter_paths):
            filtered_units.append(unit)
        else:
            logging.debug(f"Skipped {file_path} (not in filter paths)")
    
    units = filtered_units
    logging.info(f"Analyzing {len(units)} filtered compilation units")
```

**Update output generation:**

```python
# Generate outputs
json_path = None

# Step 1: Generate JSON first (for html format)
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
        import json as json_lib
        functions_dict = json_lib.load(f)

    # Remove temporary JSON file if it was temporary
    import os
    if 'call_graph_temp.json' in str(json_path):
        os.remove(json_path)
        logging.info(f"Removed temporary JSON file: {json_path}")

    # Generate HTML from JSON using FileGraphGenerator
    from .file_graph_generator import FileGraphGenerator
    file_gen = FileGraphGenerator(
        functions=functions_dict,
        relationships=relationships_to_emit,
        logger=logger
    )
    html_content = file_gen.generate_html()
    write_html_file(html_content, str(output_paths['html']))
    logging.info(f"HTML output: {output_paths.get('html')}")
```

**Add import:**
```python
from .compile_commands_simplifier import CompileCommandsSimplifier
```

**Update `_determine_output_paths()`:**

```python
def _determine_output_paths(args: argparse.Namespace) -> Dict[str, Path]:
    """Determine output file paths based on format and arguments."""
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
```

**Update `_print_output_summary()`:**

```python
def _print_output_summary(format_type: str, output_paths: Dict[str, Path]) -> None:
    """Print summary of generated output files."""
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
```

---

### src/ast_parser.py

**No changes** - Already simplified to remove adaptive retry.

---

### src/function_extractor.py

**No changes** - Already simplified to remove filter_paths parameter.

---

### src/file_graph_generator.py

**Update edge label format to: `"func @ file(start_line-end_line)"**

Already completed - uses `line_range` from function data.

---

### src/compile_commands_simplifier.py

**Restore and verify** - Keep for automatic compile_commands_simple.json generation.

---

### REQUIREMENTS.md

Update to reflect new architecture and remove filter-related requirements.

---

### README.md

Update documentation and examples to match new CLI options.

---

### USAGE.md

Update documentation for new options.

---

## Implementation Steps

### Phase 1: Delete Filter-Related Files

1. Delete source files:
   - `src/filter_config.py`
   - `src/compilation_db_filter.py`
   - `src/adaptive_flag_parser.py`
   - `src/flag_filter_manager.py`
   - `src/flag_whitelist.py`

2. Delete test files:
   - `tests/test_filter_config.py`
   - `tests/test_filter/` (entire directory)

3. Verify no orphaned imports remain (grep for deleted modules)

### Phase 2: Update CLI (src/cli.py)

1. Remove imports for filter modules
2. Add import for `CompileCommandsSimplifier`
3. Remove CLI arguments: `--config`, `--path`, `--dump-filtered-db`, `--disable-retry`
4. Add/keep `--filter-cfg` for flexible file selection
5. Add/keep `--dump-simple-db` for exporting simplified database
6. Remove `load_config()` function
7. Simplify `main()` function:
   - Generate compile_commands_simple.json (always)
   - Filter files based on `--filter-cfg`
   - Remove all other filter logic
8. Update output generation for HTML format (both JSON and HTML)
9. Update `_determine_output_paths()` for both formats
10. Update `_print_output_summary()` to show both outputs

### Phase 3: Verify Core Modules

1. Verify `ast_parser.py` has no adaptive retry
2. Verify `function_extractor.py` has no filter_paths
3. Verify `file_graph_generator.py` has correct edge labels

### Phase 4: Update Documentation

1. Update `REQUIREMENTS.md` - remove filter requirements
2. Update `README.md` - remove filter documentation, add new examples
3. Update `USAGE.md` - remove filter usage, add `--filter-cfg` and `--dump-simple-db`

---

## Simplified Workflow After Refactoring

```
1. Load compile_commands.json
   ↓
2. Generate compile_commands_simple.json (automatically, keeps -D/-I flags)
   ↓
3. Parse with simplified commands (or filter files via --filter-cfg)
   ↓
4. Extract all functions (no filtering)
   ↓
5. Build call relationships
   ↓
6. Generate output.json
   ↓
7. (Optional) Export compile_commands_simple.json via --dump-simple-db
   ↓
8. (Optional) Generate output.html from output.json using FileGraphGenerator
```

---

## Testing

### Unit Tests
- Test file simplification logic
- Test `--filter-cfg` file parsing
- Test FileGraphGenerator edge label format

### Integration Tests
- Test `--format json` output
- Test `--format html` generates both JSON and HTML
- Test `--dump-simple-db` exports simplified database
- Test `--filter-cfg` filters files correctly

### Regression Tests
- Run existing tests (excluding deleted filter tests)
- Verify basic functionality still works

---

## Success Criteria

1. ✅ All filter-related files deleted
2. ✅ YAML config and path filtering removed
3. ✅ `--filter-cfg` kept for flexible file selection
4. ✅ `--dump-simple-db` kept for exporting simplified DB
5. ✅ compile_commands_simple.json generated automatically
6. ✅ HTML generation depends ONLY on JSON
7. ✅ `--format html` outputs both JSON and HTML files
8. ✅ HTML shows file-level nodes
9. ✅ Edge labels display: `"func @ file(start_line-end_line)"`
10. ✅ Tests pass (excluding deleted filter tests)
11. ✅ Documentation updated

---

## Rollback Plan

If issues arise:

1. Restore deleted files from git history
2. Restore CLI arguments and filter logic
3. Revert documentation changes
