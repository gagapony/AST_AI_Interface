# clang-call-analyzer - Implementation Plan

## Overview

This plan addresses three main issues:
1. **Bug:** AttributeError in `echarts_generator.py` when generating HTML from JSON
2. **Feature:** Add preprocessing step to create `compile_commands_simple.json`
3. **Cleanup:** Remove deprecated `--format all` option

---

## Phase 1: Fix EChartsGenerator Bug

### 1.1 Problem Analysis

**Current Code (`src/echarts_generator.py`):**
```python
def __init__(self,
             functions: List[FunctionInfo],
             relationships: Dict[int, Tuple[List[int], List[int]]],
             logger: Optional[logging.Logger] = None):
    self.functions = functions  # Expects List[FunctionInfo]
    self.relationships = relationships

def _create_nodes(self) -> List[Dict]:
    nodes = []
    for func in self.functions:
        parents, children = self.relationships.get(func.index, ([], []))  # FAILS HERE
```

**Issue:** When generating HTML, CLI passes a list of dicts (from JSON):
```python
with open(json_path, 'r', encoding='utf-8') as f:
    functions_dict = json_lib.load(f)  # This is a list of dicts

echarts_gen = EChartsGenerator(
    functions=functions_dict,  # List[Dict], not List[FunctionInfo]
    relationships=relationships_to_emit,
    logger=logger
)
```

**Error:** `AttributeError: 'dict' object has no attribute 'index'`

### 1.2 Solution Design

**Option A: Convert dicts to FunctionInfo objects (REJECTED)**
- Creates unnecessary objects
- Loses performance benefit of using JSON directly
- More complex code

**Option B: Make EChartsGenerator work with both types (ACCEPTED)**
- Check input type at runtime
- Handle both dict and FunctionInfo inputs
- Minimal code changes
- Maintains compatibility

### 1.3 Implementation Steps

**Step 1.1:** Update `_create_nodes()` to handle both dict and FunctionInfo

```python
def _create_nodes(self) -> List[Dict]:
    """
    Create ECharts node objects from function data.

    Supports both FunctionInfo objects and dict (from JSON).
    """
    nodes = []

    for func in self.functions:
        # Handle both dict and FunctionInfo inputs
        if isinstance(func, dict):
            # From JSON: dict has 'self' dict with fields
            func_index = func.get('index')
            self_dict = func.get('self', {})
            func_name = self_dict.get('name', '')
            func_path = self_dict.get('path', '')
            func_line_range = self_dict.get('line', [])
            func_brief = self_dict.get('brief', '')
        else:
            # FunctionInfo object
            func_index = func.index
            func_name = func.name
            func_path = func.path
            func_line_range = list(func.line_range)
            func_brief = func.brief or ''

        # Get relationships
        parents, children = self.relationships.get(func_index, ([], []))

        node = {
            'id': func_index,
            'name': func_name,
            'path': func_path,
            'line_range': func_line_range,
            'brief': func_brief,
            'parents': parents,
            'children': children,
            'value': len(parents) + len(children)
        }

        nodes.append(node)

    return nodes
```

**Step 1.2:** Update type hints to reflect dual support

```python
from typing import List, Dict, Tuple, Optional, Union

def __init__(self,
             functions: Union[List[FunctionInfo], List[Dict]],
             relationships: Dict[int, Tuple[List[int], List[int]]],
             logger: Optional[logging.Logger] = None):
    """
    Initialize ECharts generator.

    Args:
        functions: List of FunctionInfo objects or list of dicts (from JSON)
        relationships: Dict mapping function index to (parents, children) tuples
        logger: Optional logger instance
    """
    self.functions = functions
    self.relationships = relationships
    self.logger = logger or logging.getLogger(__name__)
```

**Step 1.3:** Update docstrings to document dual support

### 1.4 Testing Strategy

**Test 1.1:** Generate HTML from FunctionInfo objects
- Create test with FunctionInfo list
- Verify HTML generation works

**Test 1.2:** Generate HTML from dict list (from JSON)
- Load test JSON file
- Pass dict list to EChartsGenerator
- Verify HTML generation works

**Test 1.3:** Integration test
- Run full CLI workflow with `--format html`
- Verify no AttributeError

---

## Phase 2: Add compile_commands_simple.json Preprocessing

### 2.1 Problem Analysis

**Current State:**
- Standalone script `dump_simple_db.py` exists but is not integrated
- Main CLI does not create simplified compile_commands
- Simplified DB is only created manually when needed

**Requirements:**
- Create simplified `compile_commands_simple.json` as preprocessing step
- Simplified DB filters out unnecessary flags
- Add `--dump-simple-db` flag to optionally export
- Automatically use simplified DB when filtering is active

### 2.2 Solution Design

**Approach:** Integrate simplified DB generation into main CLI flow

**Flow:**
1. When filtering is active (--filter-cfg or --path), create simplified DB
2. If --dump-simple-db is specified, write to file
3. Use simplified DB for parsing (if created)

### 2.3 Implementation Steps

**Step 2.1:** Create new module `src/compile_commands_simplifier.py`

```python
"""Compile commands simplifier for performance optimization."""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .compilation_db import CompilationUnit


class CompileCommandsSimplifier:
    """Simplify compile_commands.json by filtering flags."""

    def __init__(self, filter_paths: List[str], logger: Optional[logging.Logger] = None):
        """
        Initialize simplifier.

        Args:
            filter_paths: List of normalized filter paths
            logger: Optional logger instance
        """
        self.filter_paths = [p.rstrip('/') for p in filter_paths]
        self.logger = logger or logging.getLogger(__name__)

    def simplify_units(self, units: List[CompilationUnit]) -> Tuple[List[CompilationUnit], Dict]:
        """
        Simplify compilation units by filtering flags.

        Keeps:
        - All -D flags (macro definitions)
        - Only -I flags matching filter paths
        - Only files matching filter paths

        Removes:
        - All -I flags not matching filter paths
        - All other compiler flags (-std, -O, -Wall, etc.)

        Args:
            units: List of CompilationUnit objects

        Returns:
            Tuple of (simplified_units, stats_dict)
        """
        stats = {
            'original_units': len(units),
            'kept_units': 0,
            'removed_units': 0,
            'kept_D_flags': 0,
            'kept_I_flags': 0,
            'removed_I_flags': 0,
            'removed_other_flags': 0
        }

        simplified_units = []

        for unit in units:
            # Check if file is in filter paths
            if not self._is_allowed_path(unit.file):
                stats['removed_units'] += 1
                self.logger.debug(f"Simplifier: Removed file {unit.file}")
                continue

            # Filter flags
            filtered_flags, unit_stats = self._filter_flags(unit.flags)
            stats['kept_units'] += 1

            # Accumulate stats
            for key in ['kept_D_flags', 'kept_I_flags', 'removed_I_flags', 'removed_other_flags']:
                stats[key] += unit_stats[key]

            # Reconstruct command
            filtered_command = self._reconstruct_command(unit.command, filtered_flags)

            # Create simplified unit
            simplified_unit = CompilationUnit(
                directory=unit.directory,
                command=filtered_command,
                file=unit.file,
                flags=filtered_flags
            )

            simplified_units.append(simplified_unit)

        return simplified_units, stats

    def _is_allowed_path(self, path: str) -> bool:
        """Check if path matches any filter path."""
        path = path.rstrip('/')
        for filter_path in self.filter_paths:
            if path == filter_path or path.startswith(filter_path + '/'):
                return True
        return False

    def _filter_flags(self, flags: List[str]) -> Tuple[List[str], Dict]:
        """Filter flags, keeping only -D and matching -I."""
        stats = {
            'kept_D_flags': 0,
            'kept_I_flags': 0,
            'removed_I_flags': 0,
            'removed_other_flags': 0
        }

        filtered_flags = []
        i = 0

        while i < len(flags):
            flag = flags[i]

            # Keep all -D flags
            if flag == '-D' and i + 1 < len(flags):
                filtered_flags.extend(['-D', flags[i + 1]])
                stats['kept_D_flags'] += 1
                i += 2
                continue
            elif flag.startswith('-D'):
                filtered_flags.append(flag)
                stats['kept_D_flags'] += 1
                i += 1
                continue

            # Keep -I flags only if they match filter paths
            if flag == '-I' and i + 1 < len(flags):
                path = flags[i + 1]
                if self._is_allowed_path(path):
                    filtered_flags.extend(['-I', path])
                    stats['kept_I_flags'] += 1
                else:
                    stats['removed_I_flags'] += 1
                i += 2
                continue
            elif flag.startswith('-I'):
                path = flag[2:]
                if self._is_allowed_path(path):
                    filtered_flags.append(flag)
                    stats['kept_I_flags'] += 1
                else:
                    stats['removed_I_flags'] += 1
                i += 1
                continue

            # Keep -isystem flags only if they match filter paths
            if flag == '-isystem' and i + 1 < len(flags):
                path = flags[i + 1]
                if self._is_allowed_path(path):
                    filtered_flags.extend(['-isystem', path])
                    stats['kept_I_flags'] += 1
                else:
                    stats['removed_I_flags'] += 1
                i += 2
                continue
            elif flag.startswith('-isystem'):
                path = flag[9:]
                if self._is_allowed_path(path):
                    filtered_flags.append(flag)
                    stats['kept_I_flags'] += 1
                else:
                    stats['removed_I_flags'] += 1
                i += 1
                continue

            # Remove all other flags
            stats['removed_other_flags'] += 1
            i += 1

        return filtered_flags, stats

    def _reconstruct_command(self, original_command: str, filtered_flags: List[str]) -> str:
        """Reconstruct command with filtered flags."""
        # Parse original command to get compiler executable
        import shlex
        tokens = shlex.split(original_command)

        if not tokens:
            return original_command

        # Keep first token (compiler)
        compiler = tokens[0]

        # Reconstruct command: compiler + filtered_flags + source file
        # Note: This is a simplified reconstruction
        parts = [compiler] + filtered_flags

        # Add source file if present in original
        for token in tokens:
            if token.endswith(('.c', '.cpp', '.cc', '.cxx', '.C')):
                parts.append(token)
                break

        return ' '.join(parts)

    def dump_to_file(self, units: List[CompilationUnit], output_path: str) -> None:
        """
        Dump simplified compilation units to JSON file.

        Args:
            units: List of CompilationUnit objects
            output_path: Path to output JSON file
        """
        # Convert to dict format
        output_data = [
            {
                'directory': unit.directory,
                'command': unit.command,
                'file': unit.file
            }
            for unit in units
        ]

        # Write to file
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2)

        self.logger.info(f"Simplified compile_commands written to {output_path}")
```

**Step 2.2:** Update CLI to add `--dump-simple-db` option

```python
parser.add_argument(
    '--dump-simple-db',
    type=str,
    default=None,
    metavar='FILE',
    help='Dump simplified compile_commands.json to specified file. '
         'Only applies when filtering is active (--filter-cfg or --path). '
         'Simplified version contains only -D flags and -I flags matching filter paths.'
)
```

**Step 2.3:** Integrate simplifier into main CLI flow

```python
# In main() function, after filter_config is loaded:

# Step A: Simplify compile_commands when filtering is active
simplified_units = units
simple_db_stats = None

if filter_config.mode != FilterMode.AUTO_DETECT:
    logging.info("Creating simplified compile_commands.json for performance optimization")

    # Initialize simplifier
    from .compile_commands_simplifier import CompileCommandsSimplifier
    simplifier = CompileCommandsSimplifier(
        filter_paths=filter_config.normalized_paths,
        logger=logger
    )

    # Simplify units
    simplified_units, simple_db_stats = simplifier.simplify_units(units)

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

    # Dump to file if requested
    if args.dump_simple_db:
        simplifier.dump_to_file(simplified_units, args.dump_simple_db)

    # Use simplified units for parsing
    units = simplified_units

# Step B: Continue with existing parsing logic using simplified units
# ... rest of existing code ...
```

**Step 2.4:** Remove aggressive filter (replace with simplifier)

The existing `_apply_aggressive_filter()` function in cli.py duplicates the simplifier logic. Replace it with the new `CompileCommandsSimplifier`.

**Step 2.5:** Update import statements

Add import for `CompileCommandsSimplifier` at top of cli.py.

### 2.4 Testing Strategy

**Test 2.1:** Simplification with filter.cfg
- Run CLI with --filter-cfg
- Verify simplified DB is created in memory
- Verify stats are logged correctly

**Test 2.2:** Simplification with --path
- Run CLI with --path
- Verify simplified DB is created
- Verify only matching files are kept

**Test 2.3:** Dump to file
- Run CLI with --dump-simple-db
- Verify file is created
- Verify file content is valid JSON
- Verify file contains only filtered data

**Test 2.4:** No simplification without filter
- Run CLI without filter options
- Verify no simplification occurs
- Verify all original units are used

**Test 2.5:** Performance comparison
- Measure parsing time with vs without simplification
- Verify performance improvement on large projects

---

## Phase 3: Remove Deprecated --format all Option

### 3.1 Problem Analysis

**Current State:**
- CLI supports `--format all` which generates both JSON and HTML
- This option is redundant since HTML generation already includes all data
- Users can use `--format json` and `--format html` separately

### 3.2 Implementation Steps

**Step 3.1:** Remove 'all' from format choices

```python
# Before:
parser.add_argument(
    '--format', '-F',
    type=str,
    choices=['json', 'html', 'all'],
    default='json',
    ...
)

# After:
parser.add_argument(
    '--format', '-F',
    type=str,
    choices=['json', 'html'],
    default='json',
    ...
)
```

**Step 3.2:** Remove 'all' format handling in main()

```python
# Remove this block:
elif args.format == 'all':
    # All format: generate JSON + HTML
    paths['json'] = base_path if base_path.suffix == '.json' else base_path.with_suffix('.json')
    paths['html'] = base_path.with_suffix('.html')

# Update _determine_output_paths() to handle only json and html
```

**Step 3.3:** Update help text

Remove mention of 'all' option from help description.

**Step 3.4:** Update documentation

Update USAGE.md and README.md to remove references to `--format all`.

### 3.3 Testing Strategy

**Test 3.1:** Verify 'all' option is rejected
- Try to run with `--format all`
- Verify error message

**Test 3.2:** Verify JSON output works
- Run with `--format json`
- Verify JSON is generated

**Test 3.3:** Verify HTML output works
- Run with `--format html`
- Verify HTML is generated

**Test 3.4:** Verify default format is JSON
- Run without --format
- Verify JSON is generated

---

## Implementation Order

**Priority 1 (Bug Fix - Critical):**
- Phase 1: Fix EChartsGenerator bug
- This blocks HTML generation functionality

**Priority 2 (Feature Enhancement):**
- Phase 2: Add compile_commands_simple.json preprocessing
- This improves performance for large projects

**Priority 3 (Cleanup):**
- Phase 3: Remove deprecated --format all option
- This is low priority, nice-to-have cleanup

**Recommended Order:**
1. Phase 1 (Bug Fix) → Phase 2 (Feature) → Phase 3 (Cleanup)

---

## File Changes Summary

### New Files
- `src/compile_commands_simplifier.py` - New module for simplifying compile_commands.json

### Modified Files
- `src/echarts_generator.py`
  - Update `__init__()` to accept both List[FunctionInfo] and List[Dict]
  - Update `_create_nodes()` to handle both dict and FunctionInfo inputs
  - Update type hints and docstrings

- `src/cli.py`
  - Add `--dump-simple-db` argument
  - Remove 'all' from `--format` choices
  - Import `CompileCommandsSimplifier`
  - Integrate simplifier into main flow
  - Remove `_apply_aggressive_filter()` function (replaced by simplifier)
  - Update `_determine_output_paths()` to handle only json/html formats

- `REQUIREMENTS.md`
  - Add requirements for simplification feature
  - Add bug fix requirements
  - Update format requirements

- `USAGE.md`
  - Document `--dump-simple-db` option
  - Remove references to `--format all`
  - Update performance comparison with simplification

- `README.md`
  - Remove references to `--format all`

---

## Backward Compatibility

### Breaking Changes
- **Phase 3:** `--format all` option removed (low impact, rarely used)
  - Migration: Use `--format json` and `--format html` separately

### Non-Breaking Changes
- **Phase 1:** EChartsGenerator now accepts both dicts and objects
  - Fully backward compatible with existing code

- **Phase 2:** Simplified DB creation is internal optimization
  - Does not affect API or output format
  - New `--dump-simple-db` flag is optional

---

## Testing Plan

### Unit Tests
1. Test `echarts_generator.py` with dict inputs
2. Test `echarts_generator.py` with FunctionInfo inputs
3. Test `CompileCommandsSimplifier.simplify_units()`
4. Test `CompileCommandsSimplifier._is_allowed_path()`
5. Test `CompileCommandsSimplifier._filter_flags()`

### Integration Tests
1. Full CLI workflow with `--format html`
2. Full CLI workflow with `--format json`
3. Full CLI workflow with `--filter-cfg` and simplification
4. Full CLI workflow with `--path` and simplification
5. Full CLI workflow with `--dump-simple-db`

### Regression Tests
1. Run existing test suite
2. Verify all existing functionality still works
3. Verify output format unchanged (except for deprecated option)

---

## Rollback Plan

If issues arise after implementation:

**Phase 1 Rollback:**
- Revert `echarts_generator.py` changes
- Keep original code path for HTML generation

**Phase 2 Rollback:**
- Revert CLI integration of simplifier
- Keep `CompileCommandsSimplifier` module but don't use it
- Keep `--dump-simple-db` flag but make it no-op

**Phase 3 Rollback:**
- Restore `--format all` option
- Restore 'all' format handling

---

## Success Criteria

Implementation is successful when:

1. ✅ HTML generation works without AttributeError
2. ✅ Simplified compile_commands is created when filtering is active
3. ✅ `--dump-simple-db` flag works and outputs valid JSON
4. ✅ Performance improvement observed on large projects
5. ✅ `--format all` option removed and error raised if used
6. ✅ All existing tests pass
7. ✅ Documentation updated and accurate
8. ✅ No breaking changes to existing functionality (except deprecated option)

---

## Phase 4: Code Quality Fixes (Post-Audit)

### 4.1 Remove Temporary Files

**Problem:** `cli_new.py` and `cli_output_gen.py` are untracked files with incomplete code.

**Action:** Delete these temporary files
- Remove `src/cli_new.py`
- Remove `src/cli_output_gen.py`

**Reason:** These files appear to be partial copies of code sections during development and are not part of the production codebase.

### 4.2 Fix Type Hint in CompileCommandsSimplifier

**Problem:** Line 15 in `compile_commands_simplifier.py` has incorrect type hint:
```python
def __init__(self, filter_paths: List[str], logger: logging.Logger = None):
```

**Issue:** Type hint should be `Optional[logging.Logger]` to allow `None`.

**Action:** Update type hint:
```python
from typing import Optional

def __init__(self, filter_paths: List[str], logger: Optional[logging.Logger] = None):
```

**Files Modified:**
- `src/compile_commands_simplifier.py`

### 4.3 Fix None Handling in EChartsGenerator

**Problem:** Lines 110-122 in `echarts_generator.py` - `func_index` can be `None` and is used as dict key.

**Current Code:**
```python
if isinstance(func, dict):
    func_index = func.get('index')  # Can be None!
    ...
else:
    func_index = func.index
    ...
# Get relationships
parents, children = self.relationships.get(func_index, ([], []))  # None as key!
```

**Action:** Add None validation before using `func_index`:
```python
if isinstance(func, dict):
    func_index = func.get('index')
    ...
else:
    func_index = func.index
    ...

# Validate func_index before using
if func_index is None:
    self.logger.warning(f"Function has no index: {func}")
    continue

# Get relationships
parents, children = self.relationships.get(func_index, ([], []))
```

**Files Modified:**
- `src/echarts_generator.py`

### 4.4 Fix Undocumented CLI Option

**Problem:** Line 248 in `cli.py` uses `args.no_aggressive_filter` but this argument is not defined in the argument parser.

**Current Code:**
```python
if not args.no_aggressive_filter and filter_config.mode != FilterMode.AUTO_DETECT:
```

**Issue:** `no_aggressive_filter` is not defined anywhere in `parse_args()`.

**Action Options:**

**Option A: Remove the check (RECOMMENDED)**
- Since aggressive filter was replaced by `CompileCommandsSimplifier`, this check is obsolete
- Remove line 248 entirely
- Update related code if any

**Option B: Add the argument to parser (NOT RECOMMENDED)**
- Add `--no-aggressive-filter` to argument parser
- This perpetuates obsolete functionality

**Decision:** Remove the check (Option A)

**Files Modified:**
- `src/cli.py`

### 4.5 Document Test Environment Requirement

**Problem:** Tests cannot run outside nix-shell due to missing clang module.

**Action:** Update documentation to specify nix-shell requirement:

**Files to Update:**
- `INSTALL.md` - Add nix-shell setup instructions
- `README.md` - Note about nix-shell for testing
- `REQUIREMENTS.md` - Already updated with C5.1-C5.4

**Example addition to INSTALL.md:**
```markdown
## Running Tests

Tests require the clang module from libclang. Run tests in nix-shell:

```bash
nix-shell shell.nix --run 'pytest tests/'
```

If you encounter "ModuleNotFoundError: No module named 'clang'", ensure you are running inside nix-shell.
```

### 4.6 Implementation Order

**Priority 1 (Type Safety - Critical):**
- Fix type hint in `compile_commands_simplifier.py`
- Fix None handling in `echarts_generator.py`

**Priority 2 (Code Hygiene - High):**
- Remove temporary files (`cli_new.py`, `cli_output_gen.py`)
- Fix undocumented CLI option in `cli.py`

**Priority 3 (Documentation - Medium):**
- Document nix-shell test environment requirement

**Recommended Order:**
1. Type safety fixes (prevent runtime errors)
2. Remove temporary files (clean up)
3. Fix CLI option (remove obsolete code)
4. Update documentation

### 4.7 Testing Strategy

**Test 4.1:** Verify type hints are correct
- Run mypy or similar type checker
- Verify no type warnings

**Test 4.2:** Verify None handling
- Test with JSON missing 'index' field
- Verify graceful handling (skip or warning)

**Test 4.3:** Verify CLI works after option removal
- Run all CLI commands
- Verify no reference to `no_aggressive_filter`

**Test 4.4:** Verify tests run in nix-shell
- Run `nix-shell shell.nix --run 'pytest tests/'`
- Verify all tests pass

### 4.8 Rollback Plan

If issues arise after implementation:

**Type Hint Fix Rollback:**
- Revert type hint to `logger: logging.Logger = None`
- Functionality unchanged, only type hint affected

**None Handling Fix Rollback:**
- Revert to original code
- May cause KeyError if JSON is malformed

**CLI Option Fix Rollback:**
- Add `--no-aggressive-filter` argument to parser
- Add back line 248 check

**Documentation Rollback:**
- Remove nix-shell requirement notes
- Tests may fail outside nix-shell (expected behavior)

### 4.9 Additional Quality Checks

After implementing fixes:

1. Run mypy type checker: `mypy src/`
2. Run flake8 linter: `flake8 src/`
3. Run all tests: `nix-shell shell.nix --run 'pytest tests/'`
4. Check for remaining temporary files: `find src/ -name '*_new.py' -o -name '*_temp.py'`
5. Verify all CLI options are documented: `python -m src.cli --help` and compare with `parse_args()`

### 4.10 Success Criteria for Phase 4

Phase 4 is successful when:

1. ✅ No temporary files remain in src/
2. ✅ All type hints are correct and pass mypy
3. ✅ None values are handled safely
4. ✅ All CLI arguments are properly defined
5. ✅ Tests run successfully in nix-shell
6. ✅ Documentation includes nix-shell requirement
7. ✅ No linting errors
8. ✅ Code review passes
