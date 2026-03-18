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

### R2: AST Traversal
- **R2.1:** Use libclang to parse C/C++ source files with correct compilation flags
- **R2.2:** Traverse the Abstract Syntax Tree (AST) to find function/method definitions
- **R2.3:** Ignore declarations (only definitions count)
- **R2.4:** Support functions, methods (including templates), and lambdas

### R3: Function Metadata Extraction
For each function definition, extract:
- **R3.1:** `path`: Absolute file path
- **R3.2:** `line`: `[start_line, end_line]` (inclusive, 1-indexed)
- **R3.3:** `type`: Always `"function"`
- **R3.4:** `name`: Unqualified function name
- **R3.5:** `qualified_name`: Full signature including namespace and parameters (e.g., `Namespace::function_name(int, double)`)
- **R3.6:** `brief`: Doxygen `@brief` content or `null` if not present

### R4: Doxygen Comment Extraction
- **R4.1:** Locate Doxygen comments preceding function definitions
- **R4.2:** Parse `@brief` tag and extract its content
- **R4.3:** Handle multi-line brief descriptions
- **R4.4:** Support both `/** ... */` and `/// ...` comment styles
- **R4.5:** Return `null` if no `@brief` found

### R5: Call Relationship Building
- **R5.1:** Identify function calls within each function body
- **R5.2:** Resolve calls to actual function definitions when possible
- **R5.3:** Build bidirectional index:
  - `parents`: List of indices of functions that call this function
  - `children`: List of indices of functions called by this function
- **R5.4:** Handle calls to functions outside the analysis scope (ignore)
- **R5.5:** Handle indirect calls through function pointers (best effort)

### R6: JSON Output
- **R6.1:** Output JSON array where each element represents one function
- **R6.2:** Each element has:
  - `index`: Sequential integer starting from 0
  - `self`: Object containing function metadata (R3)
  - `parents`: Array of integers (R5.3)
  - `children`: Array of integers (R5.3)
- **R6.3:** Ensure deterministic ordering (e.g., by file path, then line number)
- **R6.4:** Output to stdout or specified file path

---

## Non-Functional Requirements

### N1: Python Implementation
- **N1.1:** All code must be Python 3.8+ compatible
- **N1.2:** No C++ compilation required
- **N1.3:** Use official `clang` Python binding from libclang

### N2: Dependencies
- **N2.1:** `clang` package (official libclang Python binding)
- **N2.2:** Python standard library only for other needs
- **N2.3:** Optional: Use `libcst` only for comment extraction if needed (not AST parsing)

### N3: Performance
- **N3.1:** Handle typical projects (up to 1000 source files) within reasonable time
- **N3.2:** Memory usage should be reasonable (avoid loading entire project AST into memory simultaneously)
- **N3.3:** Process one translation unit at a time, extract info, then free

### N4: Correctness
- **N4.1:** Must use libclang for parsing (NO regex-based parsing)
- **N4.2:** Respect compilation database (correct flags, includes, macros)
- **N4.3:** Handle edge cases:
  - Template instantiations
  - Function overloading
  - Operator overloads
  - C++11/14/17/20 features

### N5: Error Handling
- **N5.1:** Skip files that fail to parse with warning
- **N5.2:** Report parse errors to stderr
- **N5.3:** Continue processing other files
- **N5.4:** Validate input JSON format and provide clear error messages

### N6: Usability
- **N6.1:** CLI interface with clear help text
- **N6.2:** Options for input path (auto-detect compile_commands.json)
- **N6.3:** Options for output file (default: stdout)
- **N6.4:** Verbosity levels (error, warning, info, debug)

---

## Constraints

### C1: No C++ Code
- Entire tool must be implemented in Python
- Use libclang Python bindings exclusively

### C2: Simple Architecture
- Avoid over-engineering
- Prefer straightforward Python scripts over complex frameworks
- Single-pass analysis where possible

### C3: libclang Only for Parsing
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
