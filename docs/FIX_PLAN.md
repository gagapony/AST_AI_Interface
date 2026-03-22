# Fix Plan: Path Filtering and Edge Label Format Issues

**Date:** 2026-03-21  
**Priority:** High  
**Status:** Analysis Complete

---

## Problem 1: `compile_commands_simple.json` Filtering Failure

### Issue Description

The `filter.cfg` file contains:
```
src/
include/
```

However, `compile_commands_simple.json` incorrectly includes files from external packages:

```json
{
  "file": "/home/gabriel/.platformio/packages/framework-arduinoespressif32/libraries/Wire/src/Wire.cpp",
  "command": "..."
}
```

**Root Cause:** The filter `src/` matches the `src` directory component in `.platformio/.../Wire/src/Wire.cpp`, even though this file is NOT in the project's `src/` directory.

### Technical Analysis

**File:** `src/compile_commands_simplifier.py`  
**Method:** `_is_allowed_path()`

The current implementation (lines 75-97) treats relative filter paths as "directory components" that can appear anywhere in the path:

```python
# Current problematic logic
for i in range(len(path_parts) - len(filter_parts) + 1):
    if path_parts[i:i+len(filter_parts)] == tuple(filter_parts):
        self.logger.debug(f"Matched component: {path_parts} contains {filter_parts} at position {i}")
        return True
```

This causes:
- `filter.cfg: src/` matches ANY path containing a `src` component
- Project file: `/project/src/main.cpp` → **Correct match**
- External file: `.platformio/.../Wire/src/Wire.cpp` → **False positive** ❌

### Solution Design

**Approach 1: Project Root Resolution (Recommended)**

1. Add a `project_root` parameter to `CompileCommandsSimplifier`
2. Resolve relative filter paths against the project root
3. Check exact matches (file or directory)

**Implementation Changes:**

```python
# Modified __init__ method
def __init__(self, 
             filter_paths: List[str], 
             project_root: Optional[str] = None,
             logger: Optional[logging.Logger] = None):
    """
    Initialize simplifier.

    Args:
        filter_paths: List of normalized filter paths
        project_root: Project root directory (defaults to cwd)
        logger: Optional logger instance
    """
    self.filter_paths = self._resolve_filter_paths(filter_paths, project_root)
    self.logger = logger or logging.getLogger(__name__)

def _resolve_filter_paths(self, 
                          filter_paths: List[str], 
                          project_root: Optional[str]) -> List[str]:
    """Resolve relative filter paths against project root."""
    resolved = []
    root = Path(project_root) if project_root else Path.cwd()
    
    for path in filter_paths:
        path = path.rstrip('/')
        filter_obj = Path(path)
        
        # Resolve relative paths against project root
        if not filter_obj.is_absolute():
            resolved_path = (root / filter_obj).resolve()
            self.logger.debug(f"Resolved filter '{path}' -> '{resolved_path}'")
            resolved.append(str(resolved_path))
        else:
            resolved.append(path)
    
    return resolved

# Modified _is_allowed_path method
def _is_allowed_path(self, path: str) -> bool:
    """Check if path matches any filter path.

    Filters are now resolved to absolute paths and check exact matches.
    """
    path = path.rstrip('/')
    path_obj = Path(path).resolve()  # Normalize path
    
    for filter_path in self.filter_paths:
        filter_path = filter_path.rstrip('/')
        filter_obj = Path(filter_path).resolve()
        
        # Direct file match
        if path_obj == filter_obj:
            self.logger.debug(f"Exact file match: {path} == {filter_path}")
            return True
        
        # Directory match (path is under filter directory)
        # Use str() for prefix check to handle symlinks correctly
        try:
            # Check if path is under the filter directory
            # Normalize both to absolute paths
            path_str = str(path_obj)
            filter_str = str(filter_obj)
            
            if path_str == filter_str or path_str.startswith(filter_str + '/'):
                self.logger.debug(f"Directory match: {path} under {filter_path}")
                return True
        except (OSError, RuntimeError):
            # Handle path resolution errors
            continue
    
    self.logger.debug(f"No match for path: {path}")
    return False
```

**CLI Changes Required:**

In `src/cli.py`, pass the project root to `CompileCommandsSimplifier`:

```python
# Determine project root (compile_commands directory)
project_root = db_path.parent.absolute()

# Simplify compilation units with project root
simplifier = CompileCommandsSimplifier(
    filter_paths=filter_paths,
    project_root=str(project_root),
    logger=logger
)
```

**Benefits:**
- ✅ Correctly filters only project files
- ✅ Handles both absolute and relative filters
- ✅ Clear semantics (filters are relative to project root)
- ✅ Backward compatible with absolute filters

**Test Cases:**

```python
# Given filter.cfg: src/
# Given project_root: /project

filter_paths = ["src/"]
project_root = "/project"
resolved_filters = ["/project/src"]

# Test cases
assert is_allowed_path("/project/src/main.cpp") == True      # ✅ Match
assert is_allowed_path("/project/src/util.cpp") == True       # ✅ Match
assert is_allowed_path("/project/include/header.h") == False  # ❌ No match
assert is_allowed_path("/external/src/file.cpp") == False     # ❌ No match
assert is_allowed_path("/project/src/subdir/file.cpp") == True # ✅ Match
```

---

## Problem 2: Callgraph.html Edge Label Format

### Issue Description

**User Requirement:** `func @ file (start_line, end_line)`

**Current Implementation:**
```python
# In _create_file_edges method
label = f"{func_name} @ {source_name}({line_range[0]}-{line_range[1]})"
```

Produces: `func_name @ source_name(start-end)`

**Problems:**
1. ❌ Format is `(start-end)` instead of `(start, end)`
2. ❌ Only shows the **first** calling function from multiple calls
3. ❌ `source_name` is the source file (caller), not the target file

### Technical Analysis

**File:** `src/file_graph_generator.py`  
**Method:** `_create_file_edges()` (lines 353-385)

```python
# Current implementation
def _create_file_edges(self, file_relationships: Dict[str, Dict]) -> List[Dict]:
    edges = []

    file_to_id = {}
    for file_path in file_relationships:
        file_to_id[file_path] = len(file_to_id)

    for source_file, rels in file_relationships.items():
        for target_file, call_info in rels['outgoing'].items():
            # Problem 1: Only uses first function
            func_name = call_info['functions'][0]
            line_range = call_info['line_ranges'][0]
            source_name = Path(source_file).name  # Problem 3: Source file

            # Problem 1: Wrong format (start-end)
            label = f"{func_name} @ {source_name}({line_range[0]}-{line_range[1]})"

            edge = {
                'source': file_to_id[source_file],
                'target': file_to_id[target_file],
                'label': label,
                ...
            }
```

**Understanding User Intent:**

The edge goes from `source_file` → `target_file`. The label should show:
- Which function is being called (in target file)
- At which line numbers it appears
- Using comma format: `(start, end)`

### Solution Design

**Clarification Needed:**

Before implementing, we need to clarify what the user wants:

**Option A: Show called function (in target file)**
```
func @ file (start_line, end_line)
```
Example: `setup @ main.cpp (10, 15)`
- `setup`: Function name in target file
- `main.cpp`: Target file name
- `(10, 15)`: Line range in source file where it's called

**Option B: Show calling function (in source file)**
```
func @ file (start_line, end_line)
```
Example: `main @ main.cpp (10, 15)`
- `main`: Function name in source file that makes the call
- `main.cpp`: Source file name (caller)
- `(10, 15)`: Line range in source file

**Recommended Implementation (Option A):**

```python
def _create_file_edges(self, file_relationships: Dict[str, Dict]) -> List[Dict]:
    """Create file edges with call labels.

    Edge label format: func @ file (start_line, end_line)
    - func: First called function name (in target file)
    - file: Target file name
    - start_line, end_line: Line range in source file
    """
    edges = []

    file_to_id = {}
    for file_path in file_relationships:
        file_to_id[file_path] = len(file_to_id)

    # Build reverse lookup: function index -> function data
    func_data_by_index = {}
    for func in self.functions:
        func_data_by_index[func['index']] = func

    for source_file, rels in file_relationships.items():
        for target_file, call_info in rels['outgoing'].items():
            # Get first call's information
            func_idx = call_info['function_indices'][0]  # Need to track this
            line_range = call_info['line_ranges'][0]
            target_name = Path(target_file).name
            
            # Get function name from function data
            func_name = func_data_by_index[func_idx]['self']['name']
            
            # Format: "func @ file (start_line, end_line)"
            label = f"{func_name} @ {target_name}({line_range[0]}, {line_range[1]})"

            edge = {
                'source': file_to_id[source_file],
                'target': file_to_id[target_file],
                'label': label,
                'lineStyle': {
                    'width': min(5, 1 + len(call_info['functions']) / 2),
                    'color': '#999',
                    'curveness': 0.1
                }
            }

            edges.append(edge)

    return edges
```

**Alternative Implementation (Option B - Show calling function):**

```python
def _create_file_edges(self, file_relationships: Dict[str, Dict]) -> List[Dict]:
    """Create file edges with call labels.

    Edge label format: func @ file (start_line, end_line)
    - func: First calling function name (in source file)
    - file: Source file name (caller)
    - start_line, end_line: Line range where call occurs
    """
    edges = []

    file_to_id = {}
    for file_path in file_relationships:
        file_to_id[file_path] = len(file_to_id)

    for source_file, rels in file_relationships.items():
        for target_file, call_info in rels['outgoing'].items():
            # Get first call's information
            func_name = call_info['functions'][0]  # Calling function
            line_range = call_info['line_ranges'][0]
            source_name = Path(source_file).name
            
            # Format: "func @ file (start_line, end_line)"
            label = f"{func_name} @ {source_name}({line_range[0]}, {line_range[1]})"

            edge = {
                'source': file_to_id[source_file],
                'target': file_to_id[target_file],
                'label': label,
                'lineStyle': {
                    'width': min(5, 1 + len(call_info['functions']) / 2),
                    'color': '#999',
                    'curveness': 0.1
                }
            }

            edges.append(edge)

    return edges
```

**Data Structure Change Required:**

Currently, `file_relationships` stores only function names and line ranges. To support Option A, we need to also store function indices:

```python
# In _build_file_relationships method
file_relationships[source_file]['outgoing'][target_file] = {
    'functions': [],
    'function_indices': [],  # Add this field
    'line_ranges': []
}

# Then:
file_relationships[source_file]['outgoing'][target_file]['function_indices'].append(child_idx)
```

### Summary of Changes

**For Problem 1:**
1. Modify `CompileCommandsSimplifier.__init__()` to accept `project_root`
2. Add `_resolve_filter_paths()` method
3. Rewrite `_is_allowed_path()` to use resolved absolute paths
4. Update `cli.py` to pass project root

**For Problem 2:**
1. Modify `_create_file_edges()` label format: `(start, end)` instead of `(start-end)`
2. Update data structure to track function indices if showing called functions
3. Clarify whether to show calling or called function names

---

## Implementation Priority

1. **HIGH:** Problem 1 - Path filtering fix (blocks correct analysis)
2. **MEDIUM:** Problem 2 - Edge label format (UX improvement)

---

## Questions for Review

1. **Problem 2:** Should the edge label show the **calling** function or the **called** function?
2. **Problem 2:** Should we show multiple functions if there are multiple calls, or always just the first one?
3. **Problem 2:** For multiple calls, should the line range show the first call's range, or a merged range (min-start to max-end)?

---

**End of Fix Plan**
