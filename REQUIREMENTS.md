# clang-call-analyzer - Requirements

## Project Overview

**Name:** clang-call-analyzer
**Language:** Python
**Target:** C/C++ code analysis
**Input:** `compile_commands.json` (Clang compilation database)
**Output:** JSON containing function definitions, call relationships, location info, and Doxygen comments

---

## Functional Requirements

### R1: Parse Compilation Database
- **R1.1:** Read and parse `compile_commands.json` from project root
- **R1.2:** Extract file paths and compilation flags for each translation unit
- **R1.3:** Handle include paths, defines, and other compiler options
- **R1.4:** Extract include paths from compilation flags for library detection
- **R1.5:** Support custom configuration file (`clang-call-analyzer.yml`) for filtering rules
- **R1.6:** Create simplified `compile_commands_simple.json` as preprocessing step (optional dump)

### R2: Library and File Filtering
- **R2.1:** Filter system libraries (e.g., `/usr/include/`, `/usr/lib/`, `/nix/store/`)
- **R2.2:** Filter kernel libraries (Linux kernel source code)
- **R2.3:** Filter external/third-party libraries (e.g., opencv, esp-idf, framework-arduinoespressif32)
- **R2.4:** Auto-detect system library paths from compilation flags
- **R2.5:** Support user-configurable whitelist/blacklist via configuration file
- **R2.6:** Support command-line overrides for whitelist/blacklist
- **R2.7:** Provide flexible path matching (prefix, glob, regex patterns)

### R3: AST Traversal
- **R3.1:** Use libclang to parse C/C++ source files with correct compilation flags
- **R3.2:** Traverse the Abstract Syntax Tree (AST) to find function/method definitions
- **R3.3:** Ignore declarations (only definitions count)
- **R3.4:** Support functions, methods (including templates), and lambdas
- **R3.5:** Gracefully handle files that fail to parse (continue with other files)
- **R3.6:** Support cross-platform architectures (x86, ARM, RISC-V, etc.)

### R4: File Filtering and Validation
- **R4.1:** Apply whitelist before analyzing files
- **R4.2:** Apply blacklist to exclude filtered paths
- **R4.3:** Auto-detect project root from compile_commands.json directory
- **R4.4:** Default to common source directories (src/, lib/, include/, app/)
- **R4.5:** Log skipped files with reason (system lib, external lib, not in whitelist)

### R5: Function Metadata Extraction
For each function definition, extract:
- **R5.1:** `path`: Absolute file path
- **R5.2:** `line`: `[start_line, end_line]` (inclusive, 1-indexed)
- **R5.3:** `type`: Always `"function"`
- **R5.4:** `name`: Unqualified function name
- **R5.5:** `qualified_name`: Full signature including namespace and parameters (e.g., `Namespace::function_name(int, double)`)
- **R5.6:** `brief`: Doxygen `@brief` content or `null` if not present

### R6: Doxygen Comment Extraction
- **R6.1:** Locate Doxygen comments preceding function definitions
- **R6.2:** Parse `@brief` tag and extract its content
- **R6.3:** Handle multi-line brief descriptions
- **R6.4:** Support both `/** ... */` and `/// ...` comment styles
- **R6.5:** Return `null` if no `@brief` found

### R7: Call Relationship Building
- **R7.1:** Identify function calls within each function body
- **R7.2:** Resolve calls to actual function definitions when possible
- **R7.3:** Build bidirectional index:
  - `parents`: List of indices of functions that call this function
  - `children`: List of indices of functions called by this function
- **R7.4:** Handle calls to functions outside the analysis scope (ignore)
- **R7.5:** Handle indirect calls through function pointers (best effort)

### R8: Path-Based Filtering
- **R8.1:** Support `--path` command-line option to filter compilation units
- **R8.2:** If `--path` is specified, only analyze compilation units whose file path is within the specified path
- **R8.3:** Path filtering should be recursive (include all subdirectories)
- **R8.4:** Support both source files (.c, .cpp, .cc, .cxx) and header files (.h, .hpp, .hh, .hxx)
- **R8.5:** Log number of filtered vs. analyzed compilation units
- **R8.6:** Path should be resolved to absolute path for reliable matching
- **R8.7:** If `--path` is not specified, analyze all compilation units (default behavior)

### R9: JSON Output
- **R9.1:** Output JSON array where each element represents one function
- **R9.2:** Each element has:
  - `index`: Sequential integer starting from 0
  - `self`: Object containing function metadata (R5)
  - `parents`: Array of integers (R7.3)
  - `children`: Array of integers (R7.3)
- **R9.3:** Ensure deterministic ordering (e.g., by file path, then line number)
- **R9.4:** Output to stdout or specified file path

### R10: HTML Output (ECharts Visualization)
- **R10.1:** Generate HTML with embedded ECharts visualization
- **R10.2:** Always generate HTML from JSON (no direct code-to-HTML)
- **R10.3:** Support generating HTML from previously generated JSON
- **R10.4:** Handle both dict-based (from JSON) and object-based function data
- **R10.5:** Include interactive graph with call relationships

### R11: Simplified Compile Commands (NEW)
- **R11.1:** Create simplified `compile_commands_simple.json` as preprocessing step
- **R11.2:** Simplified version should contain:
  - Only -D flags (all macro definitions)
  - Only -I flags matching filter paths
  - Only file paths matching filter paths
  - All other compiler flags removed
- **R11.3:** Preprocessing step should run automatically when filtering is active
- **R11.4:** Add `--dump-simple-db` flag to optionally write simplified DB to file
- **R11.5:** Use simplified DB for parsing when available (performance optimization)

### R12: Output Format Options
- **R12.1:** Support `--format json` for JSON output only
- **R12.2:** Support `--format html` for HTML output only
- **R12.3:** Remove `--format all` option (deprecated, use individual formats)

### R13: Cross-Platform Compatibility
- **R13.1:** Support Linux embedded development environments
- **R13.2:** Support MCU embedded development (ARM Cortex-M, etc.)
- **R13.3:** Support ESP32 development (RISC-V architecture, Arduino framework)
- **R13.4:** Support NixOS environment with nix store paths
- **R13.5:** Auto-detect compiler environment from compile_commands.json flags
- **R13.6:** No hardcoded paths or platform-specific assumptions
- **R13.7:** Graceful degradation: continue processing if a file fails to parse

---

## Non-Functional Requirements

### N14: Python Implementation
- **N14.1:** All code must be Python 3.8+ compatible
- **N14.2:** No C++ compilation required
- **N14.3:** Use official `clang` Python binding from libclang

### N15: Dependencies
- **N15.1:** `clang` package (official libclang Python binding)
- **N15.2:** Python standard library only for other needs
- **N15.3:** Optional: Use `libcst` only for comment extraction if needed (not AST parsing)

### N16: Performance
- **N16.1:** Handle typical projects (up to 1000 source files) within reasonable time
- **N16.2:** Memory usage should be reasonable (avoid loading entire project AST into memory simultaneously)
- **N16.3:** Process one translation unit at a time, extract info, then free
- **N16.4:** Use simplified compile_commands when available to reduce parsing overhead

### N17: Correctness
- **N17.1:** Must use libclang for parsing (NO regex-based parsing)
- **N17.2:** Respect compilation database (correct flags, includes, macros)
- **N17.3:** Handle edge cases:
  - Template instantiations
  - Function overloading
  - Operator overloads
  - C++11/14/17/20 features

### N18: Error Handling
- **N18.1:** Skip files that fail to parse with warning
- **N18.2:** Report parse errors to stderr
- **N18.3:** Continue processing other files
- **N18.4:** Validate input JSON format and provide clear error messages
- **N18.5:** Log skipped files with reason (filtered, parse error, etc.)

### N19: Filtering and Configuration
- **N19.1:** Support YAML configuration file (`clang-call-analyzer.yml`) in project root
- **N19.2:** Configuration options: whitelist, blacklist, auto_detect_paths, log_level
- **N19.3:** Command-line options override configuration file
- **N19.4:** Provide sensible defaults for common project structures
- **N19.5:** Auto-detect system library paths from compiler flags

### N20: Usability
- **N20.1:** CLI interface with clear help text
- **N20.2:** Options for input path (auto-detect compile_commands.json)
- **N20.3:** Options for output file (default: stdout)
- **N20.4:** Verbosity levels (error, warning, info, debug)
- **N20.5:** Options for whitelist/blacklist
- **N20.6:** Option to enable/disable auto-detection of system paths
- **N20.7:** Option to show skipped files and reasons
- **N20.8:** Option to dump simplified compile_commands for debugging

---

## Bug Fix Requirements

### B1: Fix EChartsGenerator AttributeError
- **B1.1:** `echarts_generator.py` line 99 fails when `functions` parameter is a list of dicts (from JSON)
- **B1.2:** Error: `AttributeError: 'dict' object has no attribute 'index'`
- **B1.3:** Root cause: Code expects `FunctionInfo` objects but receives dicts
- **B1.4:** Fix: Update `EChartsGenerator` to handle both dict and object inputs

### B2: Add compile_commands_simple.json Preprocessing
- **B2.1:** Create simplified compile_commands during preprocessing phase
- **B2.2:** Simplified DB reduces parsing time by filtering unnecessary flags
- **B2.3:** Integrate `dump_simple_db.py` logic into main CLI flow
- **B2.4:** Make dump optional with `--dump-simple-db` flag
- **B2.5:** Automatically use simplified DB when filtering is active

### B3: Remove Deprecated --format all
- **B3.1:** Remove `--format all` option from CLI
- **B3.2:** HTML output is essentially "all" (includes all necessary data)
- **B3.3:** Users should use individual formats as needed

---

## Constraints

### C1: No C++ Code
- Entire tool must be implemented in Python
- Use libclang Python bindings exclusively

### C2: Type Safety
- **C2.1:** All optional parameters must use proper type hints (`Optional[Type] = None`)
- **C2.2:** Functions accepting optional types must handle `None` values safely
- **C2.3:** No usage of `None` as dictionary key without validation
- **C2.4:** All type hints must match actual parameter types in implementation

### C3: CLI Argument Consistency
- **C3.1:** All command-line arguments must be defined in the argument parser
- **C3.2:** No undocumented or implicit CLI options
- **C3.3:** All arguments used in code must have corresponding `add_argument()` calls
- **C3.4:** Help text must accurately describe all available options

### C4: Code Hygiene
- **C4.1:** No temporary or test files committed to repository
- **C4.2:** All Python files must be syntactically valid
- **C4.3:** Dead code and unused imports must be removed
- **C4.4:** All public APIs must be documented with docstrings

### C5: Test Environment
- **C5.1:** Tests must be run in nix-shell environment for proper libclang access
- **C5.2:** nix-shell provides clang module and required dependencies
- **C5.3:** Test execution requires: `nix-shell shell.nix --run 'pytest tests/'`
- **C5.4:** Documentation must specify nix-shell requirement for testing

### C2: Simple Architecture
- Avoid over-engineering
- Prefer straightforward Python scripts over complex frameworks
- Single-pass analysis where possible

### C3: Platform Independence
- No hardcoded platform-specific paths (except for common defaults)
- Detect system paths dynamically from compile_commands.json
- Work across Linux, macOS, and Windows (if applicable)

### C4: Minimal Dependencies
- Only libclang (via `clang` Python package) and standard library
- Avoid external YAML parsers if possible (use `pyyaml` only for config)
- Keep footprint small for embedded environments

### C5: libclang Only for Parsing
- AST traversal via libclang
- Do not use regex, grep, or other heuristics for code structure
- May use regex only for Doxygen tag extraction within comments

---

## Input/Output Specification

### Input
```json
[
  {
    "directory": "/path/to/project",
    "command": "clang++ -c file.cpp -Iinclude -DDEBUG",
    "file": "file.cpp"
  }
]
```

### Output (Call Graph JSON)
```json
[
  {
    "index": 0,
    "self": {
      "path": "/absolute/path/to/file.c",
      "line": [42, 56],
      "type": "function",
      "name": "function_name",
      "qualified_name": "Namespace::function_name(int, double)",
      "brief": "Doxygen @brief content or null"
    },
    "parents": [1, 5, 9],
    "children": [2, 3, 7]
  }
]
```

### Output (Simplified Compile Commands)
```json
[
  {
    "directory": "/path/to/project",
    "command": "clang++ -c file.cpp -Iinclude -DDEBUG",
    "file": "file.cpp"
  }
]
```
Note: The simplified version has flags filtered to only include:
- All -D flags
- Only -I flags matching filter paths
- All other flags removed

---

## Acceptance Criteria

A tool is accepted if:
1. **AC1:** Successfully parses `compile_commands.json` from a real project
2. **AC2:** Extracts all function definitions with correct metadata
3. **AC3:** Correctly identifies `@brief` content in Doxygen comments
4. **AC4:** Builds accurate `parents`/`children` relationships
5. **AC5:** Outputs valid JSON matching the specification
6. **AC6:** Handles edge cases (templates, overloads, missing comments) gracefully
7. **AC7:** No C++ code is present in the implementation
8. **AC8:** Filters system libraries and external libraries correctly
9. **AC9:** Supports YAML configuration file with whitelist/blacklist
10. **AC10:** Works on multiple platforms (Linux embedded, MCU, ESP32, NixOS)
11. **AC11:** Auto-detects system library paths from compiler flags
12. **AC12:** Gracefully handles files that fail to parse or are filtered
13. **AC13:** Provides clear logging for skipped files and reasons
14. **AC14:** Supports `--path` option to filter compilation units by directory path (recursive)
15. **AC15:** When `--path` is specified, only analyzes files within the specified path
16. **AC16:** HTML generation works correctly from JSON input (fixes AttributeError)
17. **AC17:** Creates simplified `compile_commands_simple.json` when filtering is active
18. **AC18:** Supports `--dump-simple-db` flag to export simplified DB
19. **AC19:** `--format all` option removed (deprecated)
20. **AC20:** EChartsGenerator handles both dict and FunctionInfo inputs correctly
