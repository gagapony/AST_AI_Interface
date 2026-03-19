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

### R8: Path-Based Filtering (NEW)
- **R8.1:** Support `--path` command-line option to filter compilation units
- **R8.2:** If `--path` is specified, only analyze compilation units whose file path is within the specified path
- **R8.3:** Path filtering should be recursive (include all subdirectories)
- **R8.4:** Support both source files (.c, .cpp, .cc, .cxx) and header files (.h, .hpp, .hh, .hxx)
- **R8.5:** Log number of filtered vs. analyzed compilation units
- **R8.6:** Path should be resolved to absolute path for reliable matching
- **R8.7:** If `--path` is not specified, analyze all compilation units (default behavior)

### R9: JSON Output
- **R9.1:** Output JSON array where each element represents one function
- **R8.2:** Each element has:
  - `index`: Sequential integer starting from 0
  - `self`: Object containing function metadata (R5)
  - `parents`: Array of integers (R7.3)
  - `children`: Array of integers (R7.3)
- **R8.3:** Ensure deterministic ordering (e.g., by file path, then line number)
- **R8.4:** Output to stdout or specified file path

### R10: Cross-Platform Compatibility
- **R10.1:** Support Linux embedded development environments
- **R10.2:** Support MCU embedded development (ARM Cortex-M, etc.)
- **R10.3:** Support ESP32 development (RISC-V architecture, Arduino framework)
- **R10.4:** Support NixOS environment with nix store paths
- **R10.5:** Auto-detect compiler environment from compile_commands.json flags
- **R10.6:** No hardcoded paths or platform-specific assumptions
- **R10.7:** Graceful degradation: continue processing if a file fails to parse

---

## Non-Functional Requirements

### N11: Python Implementation
- **N11.1:** All code must be Python 3.8+ compatible
- **N11.2:** No C++ compilation required
- **N11.3:** Use official `clang` Python binding from libclang

### N12: Dependencies
- **N12.1:** `clang` package (official libclang Python binding)
- **N12.2:** Python standard library only for other needs
- **N12.3:** Optional: Use `libcst` only for comment extraction if needed (not AST parsing)

### N13: Performance
- **N13.1:** Handle typical projects (up to 1000 source files) within reasonable time
- **N13.2:** Memory usage should be reasonable (avoid loading entire project AST into memory simultaneously)
- **N13.3:** Process one translation unit at a time, extract info, then free

### N14: Correctness
- **N14.1:** Must use libclang for parsing (NO regex-based parsing)
- **N14.2:** Respect compilation database (correct flags, includes, macros)
- **N14.3:** Handle edge cases:
  - Template instantiations
  - Function overloading
  - Operator overloads
  - C++11/14/17/20 features

### N15: Error Handling
- **N15.1:** Skip files that fail to parse with warning
- **N15.2:** Report parse errors to stderr
- **N15.3:** Continue processing other files
- **N15.4:** Validate input JSON format and provide clear error messages
- **N15.5:** Log skipped files with reason (filtered, parse error, etc.)

### N16: Filtering and Configuration
- **N16.1:** Support YAML configuration file (`clang-call-analyzer.yml`) in project root
- **N16.2:** Configuration options: whitelist, blacklist, auto_detect_paths, log_level
- **N16.3:** Command-line options override configuration file
- **N16.4:** Provide sensible defaults for common project structures
- **N16.5:** Auto-detect system library paths from compiler flags

### N17: Usability
- **N17.1:** CLI interface with clear help text
- **N17.2:** Options for input path (auto-detect compile_commands.json)
- **N17.3:** Options for output file (default: stdout)
- **N17.4:** Verbosity levels (error, warning, info, debug)
- **N17.5:** Options for whitelist/blacklist
- **N17.6:** Option to enable/disable auto-detection of system paths
- **N17.7:** Option to show skipped files and reasons

---

## Constraints

### C11: No C++ Code
- Entire tool must be implemented in Python
- Use libclang Python bindings exclusively

### C12: Simple Architecture
- Avoid over-engineering
- Prefer straightforward Python scripts over complex frameworks
- Single-pass analysis where possible

### C13: Platform Independence
- No hardcoded platform-specific paths (except for common defaults)
- Detect system paths dynamically from compile_commands.json
- Work across Linux, macOS, and Windows (if applicable)

### C14: Minimal Dependencies
- Only libclang (via `clang` Python package) and standard library
- Avoid external YAML parsers if possible (use `pyyaml` only for config)
- Keep footprint small for embedded environments

### C15: libclang Only for Parsing
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

### Output
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
