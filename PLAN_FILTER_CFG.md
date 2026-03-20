# PLAN_FILTER_CFG.md - Filter Configuration Implementation

## Overview

**Version:** 1.0
**Status:** Technical Design
**Goal:** Add flexible filter configuration via `filter.cfg` (INI format) to dramatically improve preprocessing efficiency by limiting analysis scope.

### Problem Statement

Current implementation analyzes all compilation units from `compile_commands.json`, leading to:
- **Massive parse overhead:** ESP32 project parses 15,828 functions when only ~95-200 are needed
- **Long runtime:** 60-90 seconds for large embedded projects
- **High memory usage:** All translation units loaded into AST

### Solution: Filter Configuration System

1. **filter.cfg INI format:** Simple, human-readable filter path configuration
2. **Compile database filtering:** Pre-filter compilation units before AST parsing
3. **AST traversal optimization:** Skip files outside filter scope during traversal
4. **CLI extensions:** New parameters (`--filter-cfg`, `--dump-filtered-db`) with backward compatibility
5. **Priority-based filtering:** Config file → `--path` → auto-detect (all files)

### Expected Impact

- **Parse time:** Reduced by 80-90% (from 60-90s to 6-10s for ESP32)
- **Memory usage:** Reduced by 80-90%
- **Function count:** From 15,828 to ~95-200 (only project code)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    clang-call-analyzer                       │
│                                                               │
│  ┌──────────────┐                                            │
│  │  CLI Entry   │                                            │
│  │  (with new   │                                            │
│  │   options)   │                                            │
│  └──────┬───────┘                                            │
│         │                                                     │
│         ▼                                                     │
│  ┌──────────────────────┐                                    │
│  │  ConfigLoader       │◄─────────────────────────────────┐  │
│  │  (extended for      │                                  │  │
│  │   filter.cfg)       │                                  │  │
│  └──────┬───────────────┘                                  │  │
│         │                                                  │  │
│         ├─→ Load filter.cfg (if --filter-cfg)              │  │
│         │   - Parse INI format                           │  │
│         │   - Extract filter paths                       │  │
│         │                                                  │  │
│         ├─→ Load --path (if specified)                   │  │
│         │   - Single path filter                          │  │
│         │                                                  │  │
│         └─→ Merge with priority                           │  │
│           --filter-cfg > --path > auto-detect             │  │
│         │                                                  │  │
│         ▼                                                  │  │
│  ┌──────────────────────┐                                │  │
│  │  FilterConfig        │◄───────────────────────────────┘  │
│  │  (filter paths +    │                                   │
│  │   priority logic)   │                                   │
│  └──────┬───────────────┘                                   │
│         │                                                   │
│         ▼                                                   │
│  ┌──────────────────────────────┐                          │
│  │  CompilationDatabaseFilter    │                          │
│  │  (pre-filter units)          │                          │
│  └──────┬───────────────────────┘                          │
│         │                                                   │
│         ├─→ Read compile_commands.json                     │
│         │                                                   │
│         ├─→ Filter compilation units                       │
│         │   - Check if file path in filter scope           │
│         │   - Only process matching units                  │
│         │                                                   │
│         ├─→ Dump compile_commands_simple.json              │
│         │   (if --dump-filtered-db)                        │
│         │                                                   │
│         └─→ Pass filtered units to ASTParser              │
│                                                             │
│  ┌──────────────────────────────┐                          │
│  │  FunctionExtractor           │                          │
│  │  (with scope check)          │                          │
│  └──────┬───────────────────────┘                          │
│         │                                                   │
│         ├─→ During AST traversal:                          │
│         │   - Check if cursor location in filter scope     │
│         │   - Skip nodes from outside scope                │
│         │   - Only extract functions in scope              │
│         │                                                   │
│         └─→ No external_calls field in output             │
│                                                             │
│  ┌──────────────────────────────┐                          │
│  │  JSONEmitter                 │                          │
│  │  (output without             │                          │
│  │   external_calls)            │                          │
│  └──────────────────────────────┘                          │
└─────────────────────────────────────────────────────────────┘
```

---

## Module Design

### Module 1: `filter_config.py` - Filter Configuration Manager

**Responsibilities:**
- Parse `filter.cfg` INI format file
- Manage filter paths (multiple paths supported)
- Handle priority logic (--filter-cfg > --path > auto-detect)
- Resolve relative/absolute paths
- Track which filter mode is active

**Key Classes/Functions:**

```python
from dataclasses import dataclass, field
from typing import List, Optional, Set
from enum import Enum
import os
from pathlib import Path

class FilterMode(Enum):
    """Filter configuration mode priority."""
    FILTER_CFG = 1      # Highest: --filter-cfg specified
    SINGLE_PATH = 2     # Medium: --path specified
    AUTO_DETECT = 3     # Lowest: analyze all (no filter)

@dataclass
class FilterConfig:
    """Filter configuration with paths and mode."""
    mode: FilterMode
    paths: List[str]
    config_file: Optional[str] = None  # Path to filter.cfg if mode=FILTER_CFG
    normalized_paths: List[str] = field(default_factory=list)

    def __post_init__(self):
        """Normalize all filter paths to absolute paths."""
        self.normalized_paths = self._normalize_paths(self.paths)

    def _normalize_paths(self, paths: List[str]) -> List[str]:
        """
        Normalize filter paths to absolute paths.

        Args:
            paths: List of filter paths (relative or absolute)

        Returns:
            List of normalized absolute paths
        """
        normalized = []
        for p in paths:
            if os.path.isabs(p):
                # Already absolute
                norm = os.path.normpath(p)
            else:
                # Relative to current directory (or project root if available)
                # For now, use current directory
                norm = os.path.abspath(os.path.normpath(p))

            normalized.append(norm)
        return normalized

    def is_in_scope(self, file_path: str, project_root: str = None) -> bool:
        """
        Check if a file path is within filter scope.

        Args:
            file_path: Path to check
            project_root: Optional project root for relative path calculation

        Returns:
            True if file is in filter scope, False otherwise
        """
        # If no filter active (auto-detect mode), analyze everything
        if self.mode == FilterMode.AUTO_DETECT:
            return True

        # Normalize file path
        if project_root:
            # If file_path is absolute, try to make it relative to project root
            try:
                rel_path = os.path.relpath(file_path, project_root)
                file_path = rel_path
            except ValueError:
                # File on different drive (Windows) - keep absolute
                pass

        # Normalize for comparison
        file_path = os.path.normpath(file_path)

        # Check each filter path
        for filter_path in self.normalized_paths:
            norm_filter = os.path.normpath(filter_path)

            # Check if file_path starts with filter_path
            if file_path.startswith(norm_filter):
                return True

            # Check if file_path relative path starts with filter_path
            if not os.path.isabs(file_path):
                # Compare relative paths
                if file_path.startswith(norm_filter):
                    return True

        return False

    def get_scope_summary(self) -> str:
        """Get human-readable summary of filter scope."""
        if self.mode == FilterMode.AUTO_DETECT:
            return "All files (no filter)"
        elif self.mode == FilterMode.SINGLE_PATH:
            return f"Single path: {self.paths[0]}"
        elif self.mode == FilterMode.FILTER_CFG:
            return f"Filter config: {self.config_file} ({len(self.paths)} paths)"
        else:
            return "Unknown mode"

class FilterConfigLoader:
    """Load and parse filter configuration."""

    def __init__(self, project_root: str = None):
        """
        Initialize filter config loader.

        Args:
            project_root: Optional project root directory for relative path resolution
        """
        self.project_root = project_root or os.getcwd()
        self.logger = None  # Will be set by CLI

    def load(self,
             filter_cfg_path: Optional[str] = None,
             single_path: Optional[str] = None) -> FilterConfig:
        """
        Load filter configuration with priority logic.

        Priority: filter_cfg > single_path > auto-detect

        Args:
            filter_cfg_path: Path to filter.cfg file (from --filter-cfg)
            single_path: Single filter path (from --path)

        Returns:
            FilterConfig instance
        """
        # Priority 1: --filter-cfg
        if filter_cfg_path:
            return self._load_from_cfg(filter_cfg_path)

        # Priority 2: --path
        if single_path:
            return FilterConfig(
                mode=FilterMode.SINGLE_PATH,
                paths=[single_path],
                config_file=None
            )

        # Priority 3: Auto-detect (no filter)
        return FilterConfig(
            mode=FilterMode.AUTO_DETECT,
            paths=[],
            config_file=None
        )

    def _load_from_cfg(self, cfg_path: str) -> FilterConfig:
        """
        Load filter configuration from INI file.

        Args:
            cfg_path: Path to filter.cfg file

        Returns:
            FilterConfig instance

        Raises:
            FileNotFoundError: If config file doesn't exist
            ValueError: If config file is invalid
        """
        if not os.path.exists(cfg_path):
            raise FileNotFoundError(f"Filter config file not found: {cfg_path}")

        # Parse INI format (simple line-based parser, no sections)
        paths = []
        with open(cfg_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()

                # Skip empty lines
                if not line:
                    continue

                # Skip comments (lines starting with #)
                if line.startswith('#'):
                    continue

                # Treat as filter path
                paths.append(line)

        if not paths:
            self.logger.warning(f"Filter config file '{cfg_path}' contains no paths")

        return FilterConfig(
            mode=FilterMode.FILTER_CFG,
            paths=paths,
            config_file=cfg_path
        )

    def validate_paths(self, config: FilterConfig) -> bool:
        """
        Validate that filter paths exist (warning only, not error).

        Args:
            config: FilterConfig instance

        Returns:
            True (always, validation is warning-only)
        """
        if config.mode == FilterMode.AUTO_DETECT:
            return True

        for path in config.normalized_paths:
            if not os.path.exists(path):
                self.logger.warning(f"Filter path does not exist: {path}")
            elif not os.path.isdir(path):
                self.logger.warning(f"Filter path is not a directory: {path}")

        return True
```

**filter.cfg Format (INI-style):**

```ini
# Filter Configuration
# Each line is a filter path (relative or absolute)
# Lines starting with # are comments

# Relative paths (relative to working directory)
src/
include/
lib/
components/

# Absolute paths
/home/user/project/vendor/mylib/

# Empty lines are ignored

# More comments
# This is another comment
tests/
```

**Parsing Rules:**
1. One filter path per line
2. Lines starting with `#` are comments (ignored)
3. Empty lines are ignored
4. Both relative and absolute paths supported
5. Trailing slashes optional (`src/` == `src`)
6. Paths normalized to absolute for comparison

---

### Module 2: `compilation_db_filter.py` - Compilation Database Filtering

**Responsibilities:**
- Pre-filter `compile_commands.json` entries before AST parsing
- Match compilation units to filter scope
- Generate `compile_commands_simple.json` for debugging
- Track statistics (filtered vs. kept units)

**Key Classes/Functions:**

```python
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
import json
import os

from filter_config import FilterConfig

@dataclass
class FilterStats:
    """Statistics about database filtering."""
    total_units: int = 0
    filtered_units: int = 0
    kept_units: int = 0

@dataclass
class FilteredCompilationUnit:
    """Compilation unit after filtering."""
    directory: str
    command: str
    file: str
    original_index: int  # Index in original compile_commands.json

class CompilationDatabaseFilter:
    """
    Filter compilation database entries based on filter configuration.

    This reduces the number of files parsed by libclang, improving performance.
    """

    def __init__(self,
                 filter_config: FilterConfig,
                 project_root: str = None,
                 logger: Optional[Any] = None):
        """
        Initialize compilation database filter.

        Args:
            filter_config: FilterConfig instance
            project_root: Project root directory for path resolution
            logger: Optional logger
        """
        self.filter_config = filter_config
        self.project_root = project_root or os.getcwd()
        self.logger = logger
        self.stats = FilterStats()

    def filter_compilation_db(self,
                               compile_commands: List[Dict[str, Any]]) -> List[FilteredCompilationUnit]:
        """
        Filter compilation units based on filter configuration.

        Args:
            compile_commands: List of compilation units from compile_commands.json

        Returns:
            List of filtered compilation units (kept units only)
        """
        self.stats = FilterStats(total_units=len(compile_commands))
        filtered_units = []

        for idx, unit in enumerate(compile_commands):
            self.stats.total_units += 1

            file_path = unit['file']
            directory = unit.get('directory', '')

            # Resolve absolute file path
            if not os.path.isabs(file_path):
                abs_file_path = os.path.join(directory, file_path)
            else:
                abs_file_path = file_path

            # Check if in filter scope
            if self.filter_config.is_in_scope(abs_file_path, self.project_root):
                # Keep this unit
                filtered_units.append(FilteredCompilationUnit(
                    directory=directory,
                    command=unit['command'],
                    file=file_path,
                    original_index=idx
                ))
                self.stats.kept_units += 1
            else:
                # Filter out this unit
                self.stats.filtered_units += 1
                if self.logger and self.filter_config.mode != FilterMode.AUTO_DETECT:
                    self.logger.debug(f"Filtered compilation unit: {file_path}")

        return filtered_units

    def dump_filtered_db(self,
                         compile_commands: List[Dict[str, Any]],
                         output_path: str) -> None:
        """
        Dump filtered compilation database to JSON file.

        Args:
            compile_commands: Original compilation commands
            output_path: Path to output JSON file
        """
        # Get filtered units
        filtered_units = self.filter_compilation_db(compile_commands)

        # Convert to dict format for JSON output
        output_units = []
        for unit in filtered_units:
            output_units.append({
                'directory': unit.directory,
                'command': unit.command,
                'file': unit.file
            })

        # Write to file
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output_units, f, indent=2)

        if self.logger:
            self.logger.info(
                f"Dumped {len(output_units)} compilation units to {output_path}"
            )

    def get_stats(self) -> FilterStats:
        """Get filtering statistics."""
        return self.stats

    def get_summary(self) -> str:
        """Get human-readable summary of filtering."""
        if self.stats.total_units == 0:
            return "No compilation units to filter"

        if self.filter_config.mode == FilterMode.AUTO_DETECT:
            return f"All {self.stats.total_units} compilation units (no filter)"

        kept_pct = (self.stats.kept_units / self.stats.total_units) * 100
        return (
            f"Filtered {self.stats.total_units} compilation units: "
            f"{self.stats.kept_units} kept ({kept_pct:.1f}%), "
            f"{self.stats.filtered_units} filtered"
        )
```

**Integration with Existing `compilation_db.py`:**

```python
# In compilation_db.py (existing module, extended)
class CompilationDatabase:
    """Extended with filter support."""

    def __init__(self,
                 db_path: str,
                 filter_config: Optional[FilterConfig] = None,
                 project_root: str = None):
        """
        Initialize compilation database.

        Args:
            db_path: Path to compile_commands.json
            filter_config: Optional FilterConfig for pre-filtering
            project_root: Project root directory
        """
        self.db_path = db_path
        self.filter_config = filter_config
        self.project_root = project_root
        self.raw_units = []
        self.filtered_units = []
        self._filter: Optional[CompilationDatabaseFilter] = None

    def load(self) -> None:
        """Load compilation database from file."""
        with open(self.db_path, 'r') as f:
            self.raw_units = json.load(f)

        # Apply filter if configured
        if self.filter_config:
            self._filter = CompilationDatabaseFilter(
                filter_config=self.filter_config,
                project_root=self.project_root
            )
            self.filtered_units = self._filter.filter_compilation_db(self.raw_units)

    def get_units(self) -> List[Dict[str, Any]]:
        """
        Get compilation units to process.

        Returns:
            Filtered units if filter_config is set, otherwise all units
        """
        if self._filter and self.filtered_units:
            # Convert FilteredCompilationUnit back to dict format
            return [
                {
                    'directory': unit.directory,
                    'command': unit.command,
                    'file': unit.file
                }
                for unit in self.filtered_units
            ]
        return self.raw_units

    def dump_filtered_db(self, output_path: str) -> None:
        """Dump filtered compilation database to file."""
        if self._filter:
            self._filter.dump_filtered_db(self.raw_units, output_path)
        else:
            raise ValueError("No filter configured, cannot dump filtered DB")

    def get_filter_summary(self) -> str:
        """Get filter summary."""
        if self._filter:
            return self._filter.get_summary()
        return "No filter applied"
```

---

### Module 3: `function_extractor.py` - Extended with Scope Check

**Responsibilities:**
- During AST traversal, check if cursor is in filter scope
- Skip function definitions from outside filter scope
- Only extract functions from within filter scope
- Track skipped functions for debugging

**Key Modifications to Existing Module:**

```python
# In function_extractor.py (existing module, extended)
class FunctionExtractor:
    """Extended with filter scope checking."""

    def __init__(self,
                 tu: 'clang.cindex.TranslationUnit',
                 file_filter: 'FileFilter',
                 filter_config: Optional[FilterConfig] = None,
                 project_root: str = None):
        """
        Initialize function extractor.

        Args:
            tu: Translation unit from libclang
            file_filter: FileFilter instance (existing)
            filter_config: Optional FilterConfig for scope checking
            project_root: Project root directory
        """
        self.tu = tu
        self.file_filter = file_filter
        self.filter_config = filter_config
        self.project_root = project_root

    def extract(self) -> List[FunctionInfo]:
        """
        Extract function definitions from AST.

        Modified to skip functions outside filter scope.
        """
        functions = []
        skipped_count = 0

        for cursor in self.tu.cursor.walk_preorder():
            if self._is_function_definition(cursor):
                # Get file path
                file_path = str(cursor.location.file) if cursor.location.file else None

                if not file_path:
                    continue

                # Check filter scope
                if not self._should_extract_from_file(file_path):
                    skipped_count += 1
                    continue

                # Extract function info
                info = self._extract_info(cursor)
                functions.append(info)

        if self.filter_config and self.filter_config.mode != FilterMode.AUTO_DETECT:
            self.logger.debug(
                f"Extracted {len(functions)} functions, "
                f"skipped {skipped_count} (outside filter scope)"
            )

        return functions

    def _should_extract_from_file(self, file_path: str) -> bool:
        """
        Check if functions should be extracted from this file.

        Combines existing file_filter with new filter_config scope check.

        Args:
            file_path: Absolute file path

        Returns:
            True if functions should be extracted, False otherwise
        """
        # Existing file_filter check (system paths, whitelist/blacklist)
        result = self.file_filter.should_analyze(file_path)
        if not result.should_analyze:
            if self.config.show_skipped:
                rel_path = self.file_filter.path_filter._to_relative_path(file_path)
                self.logger.info(f"Skipping {rel_path}: {result.reason}")
            return False

        # New filter_config scope check
        if self.filter_config:
            if not self.filter_config.is_in_scope(file_path, self.project_root):
                if self.config.show_skipped:
                    rel_path = os.path.relpath(file_path, self.project_root)
                    self.logger.info(
                        f"Skipping {rel_path}: outside filter scope "
                        f"({self.filter_config.get_scope_summary()})"
                    )
                return False

        return True
```

**Scope Checking Logic:**

The filter scope check is a **second-level filter** that works alongside the existing `file_filter`:

```
File Analysis Flow:
┌─────────────────────────────────────┐
│  File: /project/src/main.cpp       │
└──────────┬──────────────────────────┘
           │
           ├─→ FileFilter.should_analyze()
           │   ├─→ Check system paths (from -isystem)
           │   ├─→ Check whitelist
           │   └─→ Check blacklist
           │
           ├─→ PASS? → Continue
           │
           ├─→ FAIL → Skip (log reason)
           │
           └─→ FilterConfig.is_in_scope()
               ├─→ Is file in filter paths?
               │
               ├─→ YES → Extract functions
               │
               └─→ NO  → Skip (outside scope)
```

---

### Module 4: `cli.py` - Extended with New Parameters

**Responsibilities:**
- Add new CLI parameters (`--filter-cfg`, `--dump-filtered-db`)
- Preserve backward compatibility with `--path`
- Implement priority logic for filter selection
- Update help text

**Key Changes:**

```python
# In cli.py (existing module, extended)
def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description='Extract function call relationships from C/C++ codebase'
    )

    # Existing parameters
    parser.add_argument(
        '--input', '-i',
        type=str,
        default='compile_commands.json',
        help='Path to compile_commands.json (default: compile_commands.json)'
    )

    parser.add_argument(
        '--output', '-o',
        type=str,
        default=None,
        help='Output file path (default: stdout)'
    )

    parser.add_argument(
        '--verbose', '-v',
        choices=['error', 'warning', 'info', 'debug'],
        default='info',
        help='Logging level (default: info)'
    )

    parser.add_argument(
        '--config', '-c',
        type=str,
        default='clang-call-analyzer.yml',
        help='Path to config file (default: clang-call-analyzer.yml)'
    )

    # NEW: Filter configuration
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

    # NEW: Dump filtered database
    parser.add_argument(
        '--dump-filtered-db',
        type=str,
        default=None,
        metavar='FILE',
        help='Dump filtered compile_commands.json to specified file. '
             'Useful for debugging filter configuration.'
    )

    # Other existing parameters
    parser.add_argument(
        '--whitelist',
        type=str,
        help='Paths to analyze (comma-separated, overrides config)'
    )

    parser.add_argument(
        '--blacklist',
        type=str,
        help='Paths to exclude (comma-separated, overrides config)'
    )

    parser.add_argument(
        '--no-whitelist',
        action='store_true',
        help='Disable default whitelist (analyze everything not blacklisted)'
    )

    parser.add_argument(
        '--no-auto-detect',
        action='store_true',
        help='Disable auto-detection of system paths'
    )

    parser.add_argument(
        '--show-skipped',
        action='store_true',
        help='Show skipped files and reasons'
    )

    parser.add_argument(
        '--version',
        action='version',
        version='%(prog)s 2.0'
    )

    return parser.parse_args()
```

**Parameter Priority Logic (in main flow):**

```python
# In main workflow
def main():
    args = parse_args()

    # Load filter configuration with priority
    project_root = os.getcwd()  # Or detect from compile_commands.json
    filter_loader = FilterConfigLoader(project_root=project_root)
    filter_config = filter_loader.load(
        filter_cfg_path=args.filter_cfg,
        single_path=args.path
    )

    # Validate filter paths (warning only)
    filter_loader.validate_paths(filter_config)

    # Log filter configuration
    logging.info(f"Filter mode: {filter_config.mode.name}")
    logging.info(f"Filter scope: {filter_config.get_scope_summary()}")

    # Load compilation database with filter
    db = CompilationDatabase(
        db_path=args.input,
        filter_config=filter_config,
        project_root=project_root
    )
    db.load()

    # Log filtering summary
    logging.info(db.get_filter_summary())

    # Dump filtered DB if requested
    if args.dump_filtered_db:
        db.dump_filtered_db(args.dump_filtered_db)

    # Continue with AST parsing...
```

---

### Module 5: `json_emitter.py` - Modified Output Format

**Responsibilities:**
- Remove `external_calls` field from output
- Ensure backward compatibility with other fields
- Document the change

**Key Changes:**

```python
# In json_emitter.py (existing module, modified)
def emit(self,
         functions: List[FunctionInfo],
         relationships: Dict[int, Tuple[List[int], List[int]]]) -> None:
    """
    Emit JSON output.

    Modified: Removed external_calls field.
    """
    output = []

    for idx, func in enumerate(functions):
        parents, children = relationships[idx]

        # Format function entry (NO external_calls field)
        entry = {
            'index': idx,
            'self': {
                'path': func.path,
                'line_range': [func.line_range[0], func.line_range[1]],
                'name': func.name,
                'qualified_name': func.qualified_name,
                'brief': func.brief
            },
            'parents': parents,
            'children': children
            # external_calls field REMOVED
        }

        output.append(entry)

    # Write to file or stdout
    if self.output_file:
        with open(self.output_file, 'w') as f:
            json.dump(output, f, indent=2)
    else:
        print(json.dumps(output, indent=2))
```

**Output Format Change:**

**Before:**
```json
{
  "index": 0,
  "self": { ... },
  "parents": [],
  "children": [1, 2],
  "external_calls": [
    {"name": "printf", "location": "stdio.h:123"}
  ]
}
```

**After:**
```json
{
  "index": 0,
  "self": { ... },
  "parents": [],
  "children": [1, 2]
  // external_calls field removed
}
```

---

## Data Flow

```
┌─────────────────────────────────────────────────────────────┐
│  CLI: clang-call-analyzer --filter-cfg filter.cfg          │
└──────────┬──────────────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────┐
│  FilterConfigLoader.load()         │
│  - Reads filter.cfg                │
│  - Parses INI format               │
│  - Returns FilterConfig            │
│    mode=FILTER_CFG                 │
│    paths=["src/", "include/"]      │
└──────────┬──────────────────────────┘
           │
           ▼
┌─────────────────────────────────────┐
│  CompilationDatabase.load()        │
│  - Reads compile_commands.json     │
│  - Has FilterConfig attached       │
└──────────┬──────────────────────────┘
           │
           ▼
┌─────────────────────────────────────┐
│  CompilationDatabaseFilter.filter()│
│  - Iterates 1000 compilation units │
│  - Checks file path against filter│
│  - Keeps ~50 units in scope        │
│  - Skips ~950 units                │
│  - Stats: 50 kept, 950 filtered    │
└──────────┬──────────────────────────┘
           │
           ├──→ If --dump-filtered-db:
           │    └─→ Dump 50 units to JSON
           │
           ▼
┌─────────────────────────────────────┐
│  ASTParser.parse()                  │
│  - Only parse 50 kept units         │
│  - Skip 950 filtered units          │
└──────────┬──────────────────────────┘
           │
           ▼
┌─────────────────────────────────────┐
│  FunctionExtractor.extract()       │
│  - For each function in AST:        │
│    ├─→ Check file_filter            │
│    │    (system paths, whitelist)   │
│    ├─→ Check filter_config.is_in_scope│
│    │    (filter.cfg paths)          │
│    └─→ Extract if both pass         │
│  - Result: ~95-200 functions        │
└──────────┬──────────────────────────┘
           │
           ▼
┌─────────────────────────────────────┐
│  CallAnalyzer.analyze_calls()      │
│  - Resolve calls to analyzed funcs │
│  - NO external_calls tracking       │
└──────────┬──────────────────────────┘
           │
           ▼
┌─────────────────────────────────────┐
│  JSONEmitter.emit()                 │
│  - Output without external_calls    │
│  - ~95-200 function entries         │
└─────────────────────────────────────┘
```

**Performance Impact:**

| Stage | Without Filter | With Filter | Improvement |
|-------|----------------|-------------|-------------|
| Compilation units to parse | 1,000 | 50 | 95% reduction |
| AST parsing time | 60-90s | 6-10s | 80-90% faster |
| Functions extracted | 15,828 | 95-200 | 99% reduction |
| Memory usage | High | Low | 80-90% reduction |

---

## Implementation Details

### filter.cfg Parsing Algorithm

**Line-by-line parser:**

```python
def _load_from_cfg(self, cfg_path: str) -> FilterConfig:
    """Parse filter.cfg file (simple INI format)."""
    paths = []

    with open(cfg_path, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            # Strip whitespace
            line = line.strip()

            # Rule 1: Skip empty lines
            if not line:
                continue

            # Rule 2: Skip comments (lines starting with #)
            if line.startswith('#'):
                continue

            # Rule 3: Treat as filter path
            paths.append(line)

    return FilterConfig(
        mode=FilterMode.FILTER_CFG,
        paths=paths,
        config_file=cfg_path
    )
```

**Error handling:**
- `FileNotFoundError`: Config file doesn't exist → Fatal error
- Empty config: Warning logged, but continues (no filter applied)
- Invalid paths: Warning logged, but kept in config

### Scope Matching Algorithm

**Path normalization and matching:**

```python
def is_in_scope(self, file_path: str, project_root: str = None) -> bool:
    """Check if file is within filter scope."""

    # Normalize file path
    if project_root and not os.path.isabs(file_path):
        # Try to make relative to project root
        try:
            rel_path = os.path.relpath(file_path, project_root)
            file_path = rel_path
        except ValueError:
            # Different drive, keep absolute
            pass

    file_path = os.path.normpath(file_path)

    # Check each filter path
    for filter_path in self.normalized_paths:
        norm_filter = os.path.normpath(filter_path)

        # Absolute match
        if file_path.startswith(norm_filter):
            return True

        # Relative match (if file_path is relative)
        if not os.path.isabs(file_path):
            if file_path.startswith(norm_filter):
                return True

    return False
```

**Matching examples:**

| Filter Path | File Path | In Scope? | Reason |
|-------------|-----------|-----------|--------|
| `src/` | `src/main.cpp` | ✅ Yes | Starts with `src/` |
| `src/` | `src/include/helper.h` | ✅ Yes | Starts with `src/` |
| `src/` | `lib/util.c` | ❌ No | Doesn't start with `src/` |
| `include/` | `/project/include/api.h` | ✅ Yes | Relative path matches |
| `/home/user/lib/` | `/home/user/lib/helper.c` | ✅ Yes | Absolute path matches |

### CLI Parameter Priority Logic

**Decision tree:**

```
┌─────────────────────────────────────┐
│  CLI Arguments Received              │
└──────────┬──────────────────────────┘
           │
           ├─→ --filter-cfg specified?
           │   ├─→ YES → Use filter.cfg
           │   │   (mode=FILTER_CFG, paths from file)
           │   │
           │   └─→ NO  → Check next
           │
           ├─→ --path specified?
           │   ├─→ YES → Use single path
           │   │   (mode=SINGLE_PATH, paths=[--path])
           │   │
           │   └─→ NO  → Use auto-detect
           │
           └─→ Auto-detect
               (mode=AUTO_DETECT, analyze all)
```

**Priority rules:**
1. `--filter-cfg` takes **absolute priority** over `--path`
2. `--filter-cfg` and `--path` are **mutually exclusive** (can't use both)
3. If neither specified, analyze **all files** (no filter)
4. This is enforced by `argparse` `mutually_exclusive_group`

**Usage examples:**

```bash
# Priority 1: Use filter.cfg
clang-call-analyzer --filter-cfg filter.cfg
# Analyzes: src/, include/, lib/ (from filter.cfg)

# Priority 2: Use --path (no filter.cfg)
clang-call-analyzer --path src/
# Analyzes: src/ only

# Priority 3: Auto-detect (no filter specified)
clang-call-analyzer
# Analyzes: all files

# Mutually exclusive (error)
clang-call-analyzer --filter-cfg filter.cfg --path src/
# Error: argument --path: not allowed with argument --filter-cfg
```

### Backward Compatibility

**Preserving `--path` parameter:**

- The `--path` parameter already exists for filtering
- **No changes to its behavior** when `--filter-cfg` is not specified
- Only change: `--path` is ignored if `--filter-cfg` is also specified

**Breaking changes: NONE**

| Change | Breaking? | Reason |
|--------|-----------|--------|
| Add `--filter-cfg` | No | New parameter, doesn't affect existing code |
| Add `--dump-filtered-db` | No | New parameter, doesn't affect existing code |
| `--path` priority | No | Behavior unchanged when used alone |
| Remove `external_calls` | No | Optional field, parsers should handle missing fields |

**Migration path:**

- Existing scripts using `--path`: Continue to work unchanged
- Existing parsers: Should ignore unknown fields (standard JSON practice)
- No action required for existing users

---

## Configuration Examples

### Example 1: ESP32 Project with filter.cfg

**filter.cfg:**
```ini
# ESP32 Project Filter Configuration

# Main application code
src/
components/my-app/
main/

# Project headers
include/

# Custom components
components/custom-component/
```

**Command:**
```bash
clang-call-analyzer --filter-cfg filter.cfg
```

**Result:**
- Filters 1,000 compilation units to ~50
- Extracts ~150 functions (vs 15,828 without filter)
- Runtime: 6-10s (vs 60-90s without filter)

### Example 2: Single Path with --path

**Command:**
```bash
clang-call-analyzer --path src/
```

**Result:**
- Filters to compilation units with files in `src/`
- Same as filter.cfg with single `src/` entry

### Example 3: Dump Filtered Database

**Command:**
```bash
clang-call-analyzer --filter-cfg filter.cfg --dump-filtered-db compile_commands_simple.json
```

**Result:**
- Analyzes filtered units
- Creates `compile_commands_simple.json` with kept units
- Useful for debugging filter configuration

### Example 4: Auto-Detect (No Filter)

**Command:**
```bash
clang-call-analyzer
```

**Result:**
- Analyzes all compilation units (existing behavior)
- No filter applied

### Example 5: Complex filter.cfg

**filter.cfg:**
```ini
# Multi-directory project structure

# Core application
core/
app/

# Libraries
lib/mylib/
lib/utils/

# Platform-specific code
platform/esp32/
platform/stm32/

# Tests (include tests)
tests/
```

**Command:**
```bash
clang-call-analyzer --filter-cfg filter.cfg --show-skipped
```

**Result:**
- Analyzes all listed directories
- Shows which files are skipped and why
- Includes test files in analysis

---

## Error Handling

### Filter Configuration Errors

**Scenario 1: filter.cfg not found**
```python
FileNotFoundError: Filter config file not found: filter.cfg
```
**Action:** Fatal error, exit with code 1

**Scenario 2: Empty filter.cfg**
```python
WARNING: Filter config file 'filter.cfg' contains no paths
```
**Action:** Continue with no filter (auto-detect mode)

**Scenario 3: Invalid path in filter.cfg**
```python
WARNING: Filter path does not exist: /nonexistent/path/
```
**Action:** Warning logged, but path kept in config

### Compilation Database Filtering Errors

**Scenario 1: No units match filter**
```python
WARNING: Filter configuration matched 0 compilation units
INFO: All 1000 compilation units filtered out
```
**Action:** Continue, but log warning. Output will have 0 functions.

**Scenario 2: Filter path is not a directory**
```python
WARNING: Filter path is not a directory: src/main.cpp
```
**Action:** Warning logged, path kept in config (user may want to match specific file)

### AST Traversal Errors

**Scenario 1: File in scope but parse fails**
```python
WARNING: Failed to parse src/main.cpp: libclang error
```
**Action:** Continue with next file, count as skipped

**Scenario 2: Function outside scope during traversal**
```python
DEBUG: Skipping function 'system_func' (outside filter scope)
```
**Action:** Skip function, continue with next (debug log only)

---

## Testing Strategy

### Unit Tests

**Test `FilterConfigLoader`:**
```python
def test_load_from_cfg():
    """Test parsing filter.cfg file."""
    loader = FilterConfigLoader()
    config = loader._load_from_cfg('test_data/filter.cfg')

    assert config.mode == FilterMode.FILTER_CFG
    assert 'src/' in config.paths
    assert 'include/' in config.paths

def test_load_empty_cfg():
    """Test empty filter.cfg."""
    loader = FilterConfigLoader()
    config = loader._load_from_cfg('test_data/empty.cfg')

    assert config.mode == FilterMode.FILTER_CFG
    assert len(config.paths) == 0

def test_priority_logic():
    """Test CLI argument priority."""
    loader = FilterConfigLoader()

    # Priority 1: filter-cfg
    config = loader.load(filter_cfg_path='filter.cfg', single_path='src/')
    assert config.mode == FilterMode.FILTER_CFG

    # Priority 2: single_path
    config = loader.load(filter_cfg_path=None, single_path='src/')
    assert config.mode == FilterMode.SINGLE_PATH

    # Priority 3: auto-detect
    config = loader.load(filter_cfg_path=None, single_path=None)
    assert config.mode == FilterMode.AUTO_DETECT
```

**Test `FilterConfig.is_in_scope`:**
```python
def test_is_in_scope_absolute():
    """Test scope matching with absolute paths."""
    config = FilterConfig(
        mode=FilterMode.FILTER_CFG,
        paths=['/project/src/', '/project/include/']
    )

    assert config.is_in_scope('/project/src/main.cpp') is True
    assert config.is_in_scope('/project/lib/util.c') is False

def test_is_in_scope_relative():
    """Test scope matching with relative paths."""
    config = FilterConfig(
        mode=FilterMode.FILTER_CFG,
        paths=['src/', 'include/']
    )

    assert config.is_in_scope('src/main.cpp', '/project') is True
    assert config.is_in_scope('lib/util.c', '/project') is False
```

**Test `CompilationDatabaseFilter`:**
```python
def test_filter_compilation_db():
    """Test filtering compilation database."""
    config = FilterConfig(
        mode=FilterMode.FILTER_CFG,
        paths=['src/']
    )

    filter_obj = CompilationDatabaseFilter(
        filter_config=config,
        project_root='/project'
    )

    compile_commands = [
        {'file': 'src/main.cpp', 'command': '...', 'directory': '/project'},
        {'file': 'lib/util.c', 'command': '...', 'directory': '/project'},
    ]

    filtered = filter_obj.filter_compilation_db(compile_commands)

    assert len(filtered) == 1
    assert filtered[0].file == 'src/main.cpp'
    assert filter_obj.stats.filtered_units == 1
    assert filter_obj.stats.kept_units == 1
```

### Integration Tests

**Test full pipeline with filter.cfg:**
```python
def test_full_pipeline_with_filter():
    """Test end-to-end analysis with filter configuration."""
    # Setup
    filter_cfg = create_temp_filter_cfg(['src/', 'include/'])
    compile_db = create_test_compile_db([
        'src/main.cpp', 'src/helper.cpp',
        'lib/util.c', 'include/api.h'
    ])

    # Run analysis
    result = run_analyzer(
        compile_db=compile_db,
        filter_cfg=filter_cfg
    )

    # Verify
    assert len(result.functions) < 4  # Some filtered out
    assert all(f.path.startswith('src/') or f.path.startswith('include/')
               for f in result.functions)
    assert 'external_calls' not in result.functions[0]
```

**Test backward compatibility with --path:**
```python
def test_backward_compatibility_path():
    """Test that --path still works as before."""
    result = run_analyzer(
        compile_db=create_test_compile_db([
            'src/main.cpp', 'lib/util.c'
        ]),
        single_path='src/'
    )

    assert len(result.functions) == 1
    assert result.functions[0].path == 'src/main.cpp'
```

**Test output format (no external_calls):**
```python
def test_output_format_no_external_calls():
    """Test that external_calls field is not in output."""
    result = run_analyzer(compile_db=create_simple_db())
    json_output = parse_output(result.json)

    for func in json_output:
        assert 'external_calls' not in func
```

---

## Development Steps

### Phase 1: Filter Configuration Module (Priority: High)
1. Create `filter_config.py` module
2. Implement `FilterConfig` dataclass
3. Implement `FilterConfigLoader` class
4. Implement INI format parser (simple line-based)
5. Implement scope matching algorithm (`is_in_scope`)
6. Add unit tests for filter configuration

**Milestone:** Load and parse filter.cfg correctly

### Phase 2: Compilation Database Filtering (Priority: High)
1. Create `compilation_db_filter.py` module
2. Implement `CompilationDatabaseFilter` class
3. Implement `filter_compilation_db` method
4. Implement `dump_filtered_db` method
5. Extend existing `CompilationDatabase` class to use filter
6. Add unit tests for database filtering

**Milestone:** Pre-filter compilation units before AST parsing

### Phase 3: CLI Parameter Extensions (Priority: High)
1. Extend `cli.py` with new parameters (`--filter-cfg`, `--dump-filtered-db`)
2. Implement priority logic in main workflow
3. Ensure backward compatibility with `--path`
4. Update help text and documentation
5. Add CLI tests

**Milestone:** CLI accepts and processes new parameters correctly

### Phase 4: AST Traversal Optimization (Priority: High)
1. Extend `FunctionExtractor` with scope checking
2. Integrate `FilterConfig.is_in_scope` in extraction loop
3. Track and log skipped functions
4. Add unit tests for scope-aware extraction

**Milestone:** Skip functions outside filter scope during AST traversal

### Phase 5: Output Format Update (Priority: Medium)
1. Modify `JSONEmitter.emit` to remove `external_calls` field
2. Verify output format matches requirements
3. Add output format tests

**Milestone:** Output JSON without external_calls field

### Phase 6: Integration & Testing (Priority: High)
1. Integrate all modules in main workflow
2. Test with real ESP32 project
3. Verify performance improvements (80-90% reduction)
4. Test backward compatibility
5. Test error handling scenarios

**Milestone:** Full working system with filter configuration

### Phase 7: Documentation (Priority: Medium)
1. Update README with filter.cfg usage
2. Add filter.cfg format documentation
3. Add examples for different scenarios
4. Document CLI parameters
5. Add troubleshooting guide

**Milestone:** Complete documentation for users

---

## File Structure

```
clang-call-analyzer/
├── requirements.txt
├── README.md
├── filter.cfg                      # NEW: Example filter configuration
├── src/
│   ├── __init__.py
│   ├── cli.py                      # MODIFIED: New CLI parameters
│   ├── filter_config.py            # NEW: Filter configuration manager
│   ├── compilation_db_filter.py    # NEW: Database filtering
│   ├── config_loader.py            # MODIFIED: Integration with filter config
│   ├── compilation_db.py           # MODIFIED: Use filter config
│   ├── function_extractor.py       # MODIFIED: Scope checking
│   ├── json_emitter.py            # MODIFIED: Remove external_calls
│   └── ... (existing modules)
├── tests/
│   ├── __init__.py
│   ├── test_filter_config.py       # NEW: Filter config tests
│   ├── test_compilation_db_filter.py # NEW: Database filter tests
│   ├── test_cli_extended.py        # NEW: Extended CLI tests
│   └── ... (existing tests)
└── test_data/
    ├── filter.cfg                  # NEW: Test filter config
    ├── compile_commands.json       # Existing
    └── ... (existing test data)
```

---

## Dependencies

### No new dependencies required

All modules use standard library:
- `pathlib` - Path manipulation
- `json` - JSON parsing/writing
- `argparse` - CLI parsing
- `enum` - Enum for FilterMode
- `dataclasses` - Data structures
- `logging` - Logging

---

## Known Limitations

1. **filter.cfg format:** Simple line-based format, no INI sections support
   - **Rationale:** Keep it simple, no need for complex INI parsing

2. **Path matching:** Prefix matching only (no glob patterns)
   - **Rationale:** Filter paths are directories, prefix matching is sufficient
   - **Workaround:** Use PathFilter's glob/regex modes for advanced patterns

3. **External calls tracking:** Removed to focus on in-scope analysis
   - **Rationale:** Performance optimization, external calls not needed for filter-based analysis

4. **Single filter scope:** Cannot have multiple independent scopes
   - **Rationale:** Not a common use case, filter.cfg can list multiple directories

---

## Open Questions

1. **Should filter.cfg support glob patterns (e.g., `src/**/*.cpp`)?**
   - **Decision:** No, filter.cfg is for directory paths only
   - **Reasoning:** Keeps it simple. Use PathFilter for advanced patterns if needed.

2. **Should we support relative paths from project root vs. working directory?**
   - **Decision:** Relative to working directory (current behavior)
   - **Reasoning:** Consistent with how --path works. Users can use absolute paths if needed.

3. **Should --dump-filtered-db be enabled by default for debugging?**
   - **Decision:** No, must be explicitly requested
   - **Reasoning:** Avoids cluttering output with intermediate files.

4. **Should we log skipped functions in non-debug mode?**
   - **Decision:** No, only with --show-skipped
   - **Reasoning:** Too verbose for normal usage.

5. **Should filter.cfg be auto-detected (like clang-call-analyzer.yml)?**
   - **Decision:** No, must be explicitly specified with --filter-cfg
   - **Reasoning:** Avoids accidental filtering, user must opt-in.

---

## Summary

This plan implements a **filter configuration system** that:

1. ✅ **Parse filter.cfg INI format** with simple line-based parser
2. ✅ **Pre-filter compile_commands.json** before AST parsing (CompilationDatabaseFilter)
3. ✅ **Optimize AST traversal** by skipping functions outside filter scope (FunctionExtractor extension)
4. ✅ **Add CLI parameters** (`--filter-cfg`, `--dump-filtered-db`) with priority logic
5. ✅ **Ensure backward compatibility** with `--path` parameter
6. ✅ **Remove external_calls field** from output
7. ✅ **Achieve 80-90% performance improvement** (from 60-90s to 6-10s)

### Key Design Decisions

1. **Simple filter.cfg format:** One path per line, comments with `#`, no sections
2. **Priority logic:** `--filter-cfg` → `--path` → auto-detect
3. **Two-level filtering:** Pre-filter at compilation DB level + scope check at AST level
4. **No external_calls:** Focus on in-scope analysis for performance
5. **No breaking changes:** Backward compatible with existing `--path` usage

### Expected Impact

- **Parse time:** 60-90s → 6-10s (80-90% reduction)
- **Functions analyzed:** 15,828 → 95-200 (99% reduction)
- **Memory usage:** 80-90% reduction
- **User experience:** Much faster, focused on relevant code
