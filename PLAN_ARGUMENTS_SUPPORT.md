# PLAN: Support arguments field in compile_commands.json

## Requirements

Add support for both `command` and `arguments` fields in compile_commands.json to prevent data loss during conversion.

### User Confirmed Decisions

1. **Field Priority**: Use `arguments` if present (more standard format), fallback to `command`
2. **Relative Paths**: Resolve to absolute paths (consistent with current behavior)
3. **Output Format**: Always output `command` field (string format) in compile_commands_simple.json
4. **Error Handling**: Skip entry and log warning if neither field exists

---

## Current Implementation Analysis

### compilation_db.py

**Current `_parse_entry` method:**
- Only reads `command` field
- Extracts flags using `_extract_flags` which parses the command string

**Current `_extract_flags` method:**
- Parses command string using `shlex.split()`
- Extracts various flags (-D, -I, -isystem, etc.)
- Handles relative paths by resolving against `directory`

### compile_commands_simplifier.py

**Current implementation:**
- Receives `CompilationUnit` with `flags` list
- Filters flags based on allowed paths
- Reconstructs command using `_reconstruct_command`

---

## Changes Required

### 1. compilation_db.py

#### 1.1 Modify `_parse_entry` method

**Current:**
```python
def _parse_entry(self, entry: dict) -> CompilationUnit:
    directory = entry.get('directory', '')
    command = entry.get('command', '')
    # ...
    flags = self._extract_flags(command, directory)
```

**New:**
```python
def _parse_entry(self, entry: dict) -> CompilationUnit:
    directory = entry.get('directory', '')
    raw_file_path = entry.get('file', '')

    if not raw_file_path:
        raise ValueError("Missing 'file' field in compilation database entry")

    # Handle both 'arguments' and 'command' fields
    arguments = entry.get('arguments')
    command = entry.get('command', '')

    if arguments is not None:
        # arguments has priority over command
        if not isinstance(arguments, list):
            self.logger.warning(f"Invalid 'arguments' type (expected list): {type(arguments)}")
            return None
        command, flags = self._extract_from_arguments(arguments, directory)
    elif command:
        # Use command field (backward compatibility)
        flags = self._extract_flags(command, directory)
    else:
        self.logger.warning(f"Entry missing both 'arguments' and 'command' fields: {entry.get('file', 'unknown')}")
        return None

    # ... rest of the method
```

#### 1.2 Add new method `_extract_from_arguments`

```python
def _extract_from_arguments(self, arguments: List[str], directory: str) -> Tuple[str, List[str]]:
    """
    Extract command string and flags from arguments array.

    Args:
        arguments: List of command-line arguments
        directory: Working directory for resolving relative paths

    Returns:
        Tuple of (command_string, flags_list)
    """
    if not arguments:
        raise ValueError("Empty arguments list")

    # First argument is the compiler executable
    compiler = arguments[0]

    flags = []
    i = 1  # Skip compiler

    while i < len(arguments):
        arg = arguments[i]

        # Skip output file option
        if arg == '-o':
            if i + 1 < len(arguments):
                i += 2
            continue
        elif arg.startswith('-o'):
            i += 1
            continue

        # Skip source files
        if arg.endswith(('.c', '.cpp', '.cc', '.cxx', '.C', '.h', '.hpp', '.hh', '.hxx')):
            i += 1
            continue

        # Skip object files and build artifacts
        if arg.endswith('.o') or '.pio/build/' in arg:
            i += 1
            continue

        # Include paths (handle both -Ipath and -I path formats)
        if arg == '-I' and i + 1 < len(arguments):
            path = arguments[i + 1]
            if not Path(path).is_absolute():
                path = str(Path(directory) / path)
            flags.extend(['-I', path])
            i += 2
        elif arg.startswith('-I'):
            path = arg[2:]
            if not Path(path).is_absolute():
                path = str(Path(directory) / path)
            flags.append(f'-I{path}')
            i += 1

        # System include directories (handle both -isystempath and -isystem path formats)
        elif arg == '-isystem' and i + 1 < len(arguments):
            path = arguments[i + 1]
            if not Path(path).is_absolute():
                path = str(Path(directory) / path)
            flags.extend(['-isystem', path])
            i += 2
        elif arg.startswith('-isystem'):
            path = arg[9:]
            if not Path(path).is_absolute():
                path = str(Path(directory) / path)
            flags.append(f'-isystem{path}')
            i += 1

        # Define macros (handle both -DNAME and -D NAME formats)
        elif arg == '-D' and i + 1 < len(arguments):
            flags.extend(['-D', arguments[i + 1]])
            i += 2
        elif arg.startswith('-D'):
            flags.append(arg)
            i += 1

        # Undefine macros (handle both -UNAME and -U NAME formats)
        elif arg == '-U' and i + 1 < len(arguments):
            flags.extend(['-U', arguments[i + 1]])
            i += 2
        elif arg.startswith('-U'):
            flags.append(arg)
            i += 1

        # Keep all other flags as-is
        else:
            flags.append(arg)
            i += 1

    # Reconstruct command string
    command = ' '.join([compiler] + flags)
    # We'll add the source file later during output

    return command, flags
```

#### 1.3 Modify `_load` method

Handle `None` return from `_parse_entry`:

```python
def _load(self):
    """Load and parse compile_commands.json."""
    try:
        with open(self.db_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if not isinstance(data, list):
            raise ValueError("compile_commands.json must be a list")

        self.entries = []
        for entry in data:
            try:
                unit = self._parse_entry(entry)
                if unit is not None:
                    self.entries.append(unit)
            except Exception as e:
                self.logger.warning(f"Failed to parse entry {entry.get('file', 'unknown')}: {e}")
                continue

        logging.info(f"Loaded {len(self.entries)} compilation units")

    except Exception as e:
        logging.error(f"Failed to load compile_commands.json: {e}")
        raise
```

#### 1.4 Update return type hint

Change:
```python
def _parse_entry(self, entry: dict) -> CompilationUnit:
```

To:
```python
def _parse_entry(self, entry: dict) -> Optional[CompilationUnit]:
```

Add import:
```python
from typing import List, NamedTuple, Optional, Tuple
```

---

### 2. compile_commands_simplifier.py

**No changes required** - The simplifier already works with `CompilationUnit.flags` list, which is populated correctly by the modified `compilation_db.py`.

However, ensure `_reconstruct_command` handles edge cases properly:

#### 2.1 Enhance `_reconstruct_command` method

**Current implementation is already correct** - it reconstructs from compiler + filtered flags + source file.

---

## Test Cases

### 3.1 Create test data files

**test_data/compile_commands_arguments.json:**
```json
[
  {
    "directory": "/home/user/project",
    "file": "src/main.cpp",
    "arguments": [
      "/usr/bin/c++",
      "-c",
      "-o",
      "build/main.o",
      "-I./include",
      "-I/opt/external/include",
      "-DDEBUG",
      "-std=c++17",
      "-Wall",
      "src/main.cpp"
    ]
  },
  {
    "directory": "/home/user/project",
    "file": "src/util.cpp",
    "arguments": [
      "/usr/bin/c++",
      "-c",
      "-o",
      "build/util.o",
      "-isystem",
      "/usr/include/c++/11",
      "-DVERSION=1.0",
      "src/util.cpp"
    ]
  }
]
```

**test_data/compile_commands_command.json (existing format):**
```json
[
  {
    "directory": "/home/user/project",
    "file": "src/main.cpp",
    "command": "/usr/bin/c++ -c -o build/main.o -I./include -I/opt/external/include -DDEBUG -std=c++17 -Wall src/main.cpp"
  }
]
```

**test_data/compile_commands_mixed.json:**
```json
[
  {
    "directory": "/home/user/project",
    "file": "src/main.cpp",
    "arguments": [
      "/usr/bin/c++",
      "-c",
      "-I./include",
      "-DDEBUG",
      "src/main.cpp"
    ],
    "command": "/usr/bin/gcc -c src/main.cpp -DOLD"
  }
]
```

**test_data/compile_commands_invalid.json:**
```json
[
  {
    "directory": "/home/user/project",
    "file": "src/bad.cpp"
  }
]
```

### 3.2 Add test methods to test_compilation_db.py

```python
def test_arguments_field(self):
    """Test parsing compile_commands.json with arguments field."""
    db_path = "test_data/compile_commands_arguments.json"
    db = CompilationDatabase(db_path)

    self.assertGreater(len(db.get_units()), 0)

    # Check that relative paths are resolved
    for unit in db.get_units():
        for flag in unit.flags:
            if flag.startswith('-I'):
                # Extract path from flag
                if flag.startswith('-I') and len(flag) > 2 and flag[2] != ' ':
                    path = flag[2:]
                else:
                    continue
                # Check if absolute or relative resolved
                self.assertTrue(Path(path).is_absolute())

def test_arguments_priority(self):
    """Test that arguments has priority over command."""
    db_path = "test_data/compile_commands_mixed.json"
    db = CompilationDatabase(db_path)

    self.assertEqual(len(db.get_units()), 1)

    unit = db.get_units()[0]

    # Should have used arguments (contains -DDEBUG), not command (contains -DOLD)
    self.assertIn('-DDEBUG', unit.flags)
    self.assertNotIn('-DOLD', unit.flags)

def test_missing_fields(self):
    """Test handling of entries with neither arguments nor command."""
    db_path = "test_data/compile_commands_invalid.json"
    db = CompilationDatabase(db_path)

    # Should skip invalid entry
    self.assertEqual(len(db.get_units()), 0)

def test_backward_compatibility(self):
    """Test that command field still works."""
    db_path = "test_data/compile_commands_command.json"
    db = CompilationDatabase(db_path)

    self.assertGreater(len(db.get_units()), 0)

    # Check command-based parsing still works
    unit = db.get_units()[0]
    self.assertIn('-I', ' '.join(unit.flags))
```

---

## Implementation Order

1. **Step 1**: Modify `compilation_db.py`
   - Add import for `Tuple` and `Optional`
   - Add `_extract_from_arguments` method
   - Modify `_parse_entry` method
   - Modify `_load` method to handle `None` returns
   - Add logging for warnings

2. **Step 2**: Create test data files

3. **Step 3**: Add test cases to `test_compilation_db.py`

4. **Step 4**: Run tests to verify both formats work

5. **Step 5**: Test with real compile_commands.json files

---

## Backward Compatibility

✅ **Fully backward compatible**
- Existing `command` field support remains unchanged
- Only adds new `arguments` field support
- No API changes to external interfaces

---

## Edge Cases Handled

1. ✅ Both `arguments` and `command` present → use `arguments`
2. ✅ Only `arguments` present → use `arguments`
3. ✅ Only `command` present → use `command`
4. ✅ Neither present → skip with warning
5. ✅ Invalid `arguments` type (not list) → skip with warning
6. ✅ Empty `arguments` list → raise error
7. ✅ Relative paths in `arguments` → resolve to absolute
8. ✅ Mixed flag formats (`-Ipath` vs `-I path`) → handle both

---

## Summary

This plan adds support for the `arguments` field while maintaining full backward compatibility with the existing `command` field implementation. The changes are minimal and focused on `compilation_db.py`, with no changes needed to `compile_commands_simplifier.py`.
