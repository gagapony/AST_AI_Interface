# Fix Summary

This document summarizes the fixes implemented for two issues in clang-call-analyzer.

## Issue 1: compile_commands_simple.json Filtering Failure

### Problem
The `CompileCommandsSimplifier` was not correctly filtering files based on relative filter paths (e.g., `src/`, `include/`). When the filter paths were relative, the path matching logic failed to properly resolve them against the project root, resulting in incorrect filtering behavior.

### Root Cause
The `_is_allowed_path()` method was trying to match absolute file paths against relative filter paths without first resolving the filter paths to absolute paths. This caused files that should have been filtered out to be included, or vice versa.

### Solution
Modified three components:

#### 1. `src/compile_commands_simplifier.py`
- Added `project_root` parameter to `__init__` method
- Added `_resolve_filter_paths()` method that:
  - Resolves relative filter paths to absolute paths based on project_root
  - Keeps absolute filter paths as-is
- Rewrote `_is_allowed_path()` to:
  - Resolve input paths to absolute paths
  - Compare against resolved absolute filter paths
  - Perform direct string comparison with path prefixes

#### 2. `src/cli.py`
- Extract project root from compile_commands.json location: `project_root = str(db_path.parent)`
- Pass project root to `CompileCommandsSimplifier` constructor

### Testing Results
```
✓ ALLOWED: /home/gabriel/projects/smart-drying-module/src/main.cpp
✓ ALLOWED: /home/gabriel/projects/smart-drying-module/include/utils.h
✗ REJECTED: /home/gabriel/projects/smart-drying-module/tests/test_main.cpp
✗ REJECTED: /usr/include/stdio.h
```

The filtering now correctly includes only files under `src/` and `include/` directories.

---

## Issue 2: Edge Label Format in File Graph

### Problem
The edge labels in the file-level call graph did not match the required format. The labels needed to show the target function's definition line range, not the source call's line range.

### Requirements
- Edge label format: `source_file ---- @ func (start, end) --> target_file`
  - `func`: Name of the called function
  - `(start, end)`: Line range where the function is defined in the target file
  - Edge direction: source file → target file (calling file → called file)
- Tooltip: Show all call information (optional/implicit)

### Solution
Modified `src/file_graph_generator.py`:

#### 1. `_build_file_relationships()` method
- Updated to store `function_indices` (child function indices) in addition to `functions` and `line_ranges`
- This allows tracking which target function is being called

#### 2. `_create_file_edges()` method
- Build a map from function index to function definition for quick lookup
- For each edge:
  1. Get the child function index from `call_info['function_indices'][0]`
  2. Find the target function definition in `self.functions` using the index
  3. Extract the line range from the target function's definition (`target_func['self']['line']`)
  4. Format the label as: `source_name ---- @ func_name (start, end) --> target_name`

### Example Output
Before: `call_func @ main.cpp(10-20)`
After: `main.cpp ---- @ call_func (30, 40) --> utils.h`

Where:
- `main.cpp` is the source file (calling file)
- `call_func` is the name of the called function
- `(30, 40)` is the line range where `call_func` is defined in `utils.h`
- `utils.h` is the target file (called file)

### Testing Results
```
Source file: main.cpp
Target file: utils.h
Called function: call_func
Target function definition line range: (30, 40)
Edge label: main.cpp ---- @ call_func (30, 40) --> utils.h

✓ Edge label format is CORRECT
```

---

## Files Modified

1. `src/compile_commands_simplifier.py`
   - Added `project_root` parameter to constructor
   - Added `_resolve_filter_paths()` method
   - Rewrote `_is_allowed_path()` method

2. `src/cli.py`
   - Extract project root from compile_commands.json path
   - Pass project root to `CompileCommandsSimplifier`

3. `src/file_graph_generator.py`
   - Updated `_build_file_relationships()` to store `function_indices`
   - Updated `_create_file_edges()` to use target function definitions for line ranges
   - Updated edge label format to match requirements

## Verification

All modified files compile successfully without errors:
```bash
python -m py_compile src/compile_commands_simplifier.py src/cli.py src/file_graph_generator.py
✓ All files compile successfully
```

Unit test `test_fixes.py` passes:
- Path filtering correctly includes/excludes files based on relative filter paths
- Edge label format matches the required specification
