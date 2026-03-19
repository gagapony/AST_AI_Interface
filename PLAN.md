# clang-call-analyzer - Technical Implementation Plan

## Architecture Fixes Summary

**Version:** 2.0 (Post-Linus Review)
**Status:** Redesigned to eliminate all 8 critical issues

### Critical Fixes Applied

| Issue | Problem | Fix |
|-------|---------|-----|
| **1. Hardcoded paths** | Predefined `SYSTEM_PATH_PATTERNS` list | Removed all hardcoded paths; system paths detected ONLY from `-isystem` flags |
| **2. NixOS logic error** | All `/nix/store/` paths filtered | Only `/nix/store/` paths from `-isystem` flags filtered; project dependencies analyzed |
| **3. Default whitelist** | Empty whitelist = analyze everything | Empty whitelist = use default `["src/", "lib/", "include/", "app/"]` unless `--no-whitelist` |
| **4. Matching modes** | Only string patterns supported | Support `prefix`, `glob`, `regex` modes via object format |
| **5. Path semantics** | Absolute path matching | All whitelist/blacklist use relative paths from project root |
| **6. Auto-detection** | Only `-I` flags detected | Detect all include flags: `-isystem`, `-I`, `-idirafter`, `-iquote`, `-F` |

### Key Design Principles

1. **No Hardcoding:** All system paths from compiler flags or user config
2. **Relative Paths:** Whitelist/blacklist based on relative paths from project root
3. **Configuration-Driven:** Users control analysis scope via whitelist/blacklist
4. **Minimal Assumptions:** No assumptions about project structure or platform

### NixOS Behavior (Critical Fix)

**Before:**
```python
# ❌ WRONG: All /nix/store/ filtered
if path.startswith('/nix/store/'):
    return False  # Filter
```

**After:**
```python
# ✅ CORRECT: Only -isystem paths filtered
system_paths = [p for p in include_paths if p.type == "system"]
# Only paths from -isystem flags are in system_paths
```

**Result:**
- `/nix/store/abc123-glibc/include` (from `-isystem`) → Filtered ✅
- `/nix/store/def456-mylib/include` (from `-I`) → Analyzed ✅

---

## Technology Stack

### Core Dependencies
- **Python:** 3.8+
- **libclang binding:** `clang` package (official libclang Python binding)
- **System requirement:** libclang shared library (typically from LLVM/Clang installation)

### Why `clang` Package?
- Official libclang Python binding
- Provides direct access to clang AST API
- Supports modern C++ standards
- Well-maintained and stable

---

## Architecture Overview

```
clang-call-analyzer (CLI)
    │
    ├─→ main.py (CLI entry point)
    │       │
    │       ├─→ ConfigLoader (load YAML config)
    │       │       │
    │       │       └─→ PathFilter (whitelist/blacklist)
    │       │               │
    │       │               └─→ FileFilter (apply filtering rules)
    │       │
    │       ├─→ CompilationDatabase (parse compile_commands.json)
    │       │       │
    │       │       ├─→ PathExtractor (extract include paths)
    │       │       │
    │       │       └─→ TUIterator (iterate translation units)
    │       │               │
    │       │               ├─→ FileFilter (filter by path)
    │       │               │
    │       │               ├─→ ASTParser (parse with libclang)
    │       │               │       │
    │       │               │       ├─→ FunctionExtractor (find definitions)
    │       │               │       │       │
    │       │               │       │       ├─→ DoxygenParser (extract @brief)
    │       │               │       │       │
    │       │               │       │       └─→ CallAnalyzer (find calls)
    │       │               │       │
    │       │               │       └─→ MetadataCollector
    │       │               │
    │       │               └─→ FunctionRegistry (index functions)
    │                       │
    │                       └─→ RelationshipBuilder (build parents/children)
    │
    └─→ JSONEmitter (output)
```

---

## Module Design

### Module 1: `config_loader.py` - Configuration Management

**Responsibilities:**
- Load YAML configuration file from project root
- Parse whitelist/blacklist settings (support string and object formats)
- Apply default whitelist when appropriate
- Merge with CLI arguments (CLI takes precedence)
- Provide default configuration

**Key Classes/Functions:**
```python
from dataclasses import dataclass, field
from typing import List, Optional, Any
import argparse

@dataclass
class PathPattern:
    pattern: str
    mode: str  # "prefix", "glob", "regex"

@dataclass
class Config:
    whitelist: List[PathPattern]
    blacklist: List[PathPattern]
    auto_detect_system_paths: bool
    log_level: str  # error, warning, info, debug
    show_skipped: bool
    use_default_whitelist: bool  # Use default whitelist if config whitelist is empty

class ConfigLoader:
    DEFAULT_WHITELIST = [
        PathPattern(pattern="src/", mode="prefix"),
        PathPattern(pattern="lib/", mode="prefix"),
        PathPattern(pattern="include/", mode="prefix"),
        PathPattern(pattern="app/", mode="prefix"),
    ]

    def __init__(self, config_path: Optional[str] = None, project_root: str)
    def load(self, args: Optional[argparse.Namespace] = None) -> Config
    def _load_yaml(self, path: str) -> Dict
    def _parse_patterns(self, patterns: List[Any], default_mode: str = "prefix") -> List[PathPattern]
    def _apply_defaults(self, config: Config) -> Config
    def _merge_with_cli(self, config: Config, args: argparse.Namespace) -> Config
```

**Pattern Parsing:**
```python
def _parse_patterns(self, patterns: List[Any], default_mode: str = "prefix") -> List[PathPattern]:
    """Parse patterns from config (support string and object formats)."""
    result = []
    for p in patterns:
        if isinstance(p, str):
            result.append(PathPattern(pattern=p, mode=default_mode))
        elif isinstance(p, dict):
            result.append(PathPattern(
                pattern=p["pattern"],
                mode=p.get("mode", default_mode)
            ))
        else:
            raise ValueError(f"Invalid pattern format: {p}")
    return result
```

**Default Whitelist Logic:**
```python
def _apply_defaults(self, config: Config) -> Config:
    """Apply default whitelist when appropriate."""
    # Only use default whitelist if:
    # 1. Config whitelist is empty
    # 2. use_default_whitelist is True (not using --no-whitelist)
    if not config.whitelist and config.use_default_whitelist:
        config.whitelist = self.DEFAULT_WHITELIST.copy()
    return config
```

**CLI Merging:**
```python
def _merge_with_cli(self, config: Config, args: argparse.Namespace) -> Config:
    """Merge CLI arguments with config (CLI takes precedence)."""
    if args.no_whitelist:
        config.use_default_whitelist = False
        config.whitelist = []

    if args.whitelist:
        # CLI whitelist overrides config whitelist
        # CLI format: comma-separated strings (default mode: prefix)
        patterns = [p.strip() for p in args.whitelist.split(',')]
        config.whitelist = self._parse_patterns(patterns, default_mode="prefix")

    if args.blacklist:
        # CLI blacklist overrides config blacklist
        patterns = [p.strip() for p in args.blacklist.split(',')]
        config.blacklist = self._parse_patterns(patterns, default_mode="prefix")

    if hasattr(args, 'no_auto_detect') and args.no_auto_detect:
        config.auto_detect_system_paths = False

    if hasattr(args, 'show_skipped') and args.show_skipped:
        config.show_skipped = True

    return config
```

**CLI Options (in cli.py):**
```python
parser.add_argument('--whitelist', type=str,
                    help='Paths to analyze (comma-separated, overrides config)')
parser.add_argument('--blacklist', type=str,
                    help='Paths to exclude (comma-separated, overrides config)')
parser.add_argument('--no-whitelist', action='store_true',
                    help='Disable default whitelist (analyze everything not blacklisted)')
parser.add_argument('--no-auto-detect', action='store_true',
                    help='Disable auto-detection of system paths')
parser.add_argument('--show-skipped', action='store_true',
                    help='Show skipped files and reasons')
```

**Configuration File Format (clang-call-analyzer.yml):**
```yaml
# Paths to analyze (relative to project root)
# Mode options: "prefix", "glob", "regex"
whitelist:
  - pattern: "src/"
    mode: "prefix"
  - pattern: "lib/"
    mode: "prefix"
  - pattern: "include/"
    mode: "prefix"

# Paths to exclude (higher priority than whitelist)
blacklist:
  - pattern: "generated/"
    mode: "prefix"
  - pattern: "vendor/**/*.h"
    mode: "glob"
  - pattern: "third_party/opencv/"
    mode: "prefix"

# Auto-detect system library paths from compiler flags
# System paths are detected from -isystem, -I, -idirafter flags
auto_detect_system_paths: true

# Logging level: error, warning, info, debug
log_level: "info"

# Show skipped files and reasons
show_skipped: true
```

**Default Whitelist Behavior:**
- If whitelist is empty in config AND not using `--no-whitelist`, default to common source directories:
  ```python
  DEFAULT_WHITELIST = ["src/", "lib/", "include/", "app/"]
  ```
- If using `--no-whitelist` CLI flag, whitelist is truly empty (analyze everything not blacklisted)

**CLI Options:**
```
--config, -c         Path to config file (default: clang-call-analyzer.yml)
--whitelist          Paths to analyze (comma-separated, overrides config)
--blacklist          Paths to exclude (comma-separated, overrides config)
--no-whitelist       Disable default whitelist (analyze everything not blacklisted)
--no-auto-detect     Disable auto-detection of system paths
--show-skipped       Show skipped files and reasons
```

---

### Module 2: `path_filter.py` - Path Filtering Logic

**Responsibilities:**
- Apply whitelist/blacklist to file paths (using relative paths from project root)
- Support multiple matching modes (prefix, glob, regex)
- Determine if a path should be analyzed

**Key Classes/Functions:**
```python
@dataclass
class PathPattern:
    pattern: str
    mode: str  # "prefix", "glob", "regex"

class PathFilter:
    def __init__(self, whitelist: List[PathPattern], blacklist: List[PathPattern],
                 project_root: str)
    def should_analyze(self, file_path: str) -> bool
    def get_skip_reason(self, file_path: str) -> Optional[str]
    def _to_relative_path(self, abs_path: str) -> str

class PathMatcher:
    @staticmethod
    def matches(pattern: str, path: str, mode: str = "prefix") -> bool
```

**Path Conversion Strategy:**
All file paths are converted to relative paths before matching:
```python
def _to_relative_path(self, abs_path: str) -> str:
    """Convert absolute path to relative path from project root."""
    try:
        return os.path.relpath(abs_path, self.project_root)
    except ValueError:
        # Path on different drive (Windows) - keep absolute
        return abs_path
```

**Matching Modes:**
- `prefix`: Path starts with pattern (e.g., `"src/"` matches `"src/main.cpp"`)
- `glob`: Unix glob pattern (e.g., `"*.cpp"`, `"src/**/*.h"`)
- `regex`: Regular expression (e.g., `"^src/.*\.cpp$"`)

**Algorithm:**
```python
def should_analyze(self, file_path: str) -> bool:
    # Convert to relative path for matching
    rel_path = self._to_relative_path(file_path)

    # Blacklist first (higher priority)
    for pattern in self.blacklist:
        if PathMatcher.matches(pattern.pattern, rel_path, pattern.mode):
            return False

    # If whitelist is empty, analyze everything not blacklisted
    if not self.whitelist:
        return True

    # Check whitelist
    for pattern in self.whitelist:
        if PathMatcher.matches(pattern.pattern, rel_path, pattern.mode):
            return True

    return False
```

**Pattern Parsing:**
Support both string format (default mode) and object format:
```python
def parse_patterns(patterns: List[Any], default_mode: str = "prefix") -> List[PathPattern]:
    """Parse patterns from config (string or object format)."""
    result = []
    for p in patterns:
        if isinstance(p, str):
            result.append(PathPattern(pattern=p, mode=default_mode))
        elif isinstance(p, dict):
            result.append(PathPattern(
                pattern=p["pattern"],
                mode=p.get("mode", default_mode)
            ))
    return result
```

---

### Module 3: `file_filter.py` - File Filtering with System Path Detection

**Responsibilities:**
- Auto-detect system library paths from compilation flags (NO hardcoded paths)
- Combine with PathFilter for comprehensive filtering
- Provide detailed skip reasons for logging
- Use relative paths from project root for whitelist/blacklist matching

**Key Classes/Functions:**
```python
@dataclass
class FileFilterResult:
    should_analyze: bool
    reason: Optional[str]  # "system_lib", "external_lib", "not_in_whitelist", etc.

class FileFilter:
    def __init__(self, path_filter: PathFilter, auto_detect: bool = True,
                 project_root: str)
    def set_system_paths(self, paths: List[str]) -> None
    def should_analyze(self, file_path: str) -> FileFilterResult
```

**System Path Detection (NO Hardcoded Paths):**
System paths are detected ONLY from compiler flags that explicitly mark them as system includes.

**Supported Include Flags:**
- `-isystem <path>`: System include directory (highest priority)
- `-I <path>`: User include directory
- `-idirafter <path>`: Include directory after system directories
- `-iquote <path>`: Include directory for #quote
- `-F <path>`: Framework directory (macOS)

```python
@dataclass
class IncludePath:
    path: str
    type: str  # "system", "user", "after", "quote", "framework"

def extract_include_paths(flags: List[str]) -> List[IncludePath]:
    """Extract all include paths from compilation flags with their types."""
    include_paths = []
    i = 0
    while i < len(flags):
        flag = flags[i]

        # -isystem <path> (system include)
        if flag == '-isystem' and i + 1 < len(flags):
            include_paths.append(IncludePath(path=flags[i + 1], type="system"))
            i += 2
            continue

        # -I<path> (user include)
        elif flag.startswith('-I') and flag != '-I':
            include_paths.append(IncludePath(path=flag[2:], type="user"))
            i += 1
            continue

        # -I <path> (user include, space-separated)
        elif flag == '-I' and i + 1 < len(flags):
            include_paths.append(IncludePath(path=flags[i + 1], type="user"))
            i += 2
            continue

        # -idirafter <path> (include after system)
        elif flag == '-idirafter' and i + 1 < len(flags):
            include_paths.append(IncludePath(path=flags[i + 1], type="after"))
            i += 2
            continue

        # -iquote <path> (quote include)
        elif flag == '-iquote' and i + 1 < len(flags):
            include_paths.append(IncludePath(path=flags[i + 1], type="quote"))
            i += 2
            continue

        # -F<path> (framework directory, macOS)
        elif flag.startswith('-F') and flag != '-F':
            include_paths.append(IncludePath(path=flag[2:], type="framework"))
            i += 1
            continue

        i += 1

    return include_paths

def get_system_paths(include_paths: List[IncludePath]) -> List[str]:
    """Filter only system-type include paths."""
    return [ip.path for ip in include_paths if ip.type == "system"]

def is_system_file(file_path: str, system_paths: List[str]) -> bool:
    """Check if a file belongs to a system include directory."""
    # Normalize paths for comparison
    file_path = os.path.normpath(file_path)
    for sys_path in system_paths:
        sys_path = os.path.normpath(sys_path)
        if file_path.startswith(sys_path):
            return True
    return False
```

**Key Design Decisions:**

1. **No Hardcoded Path Lists:** All system paths come from `-isystem` flags
2. **NixOS Handling:** `/nix/store/` paths are NOT automatically filtered.
   - Only paths from `-isystem` flags are marked as system libraries
   - Project dependencies in `/nix/store/` will be analyzed (not blacklisted)
3. **Relative Path Matching:** Whitelist/blacklist always use relative paths from project root
4. **Configuration-Driven:** Users explicitly control what to analyze via whitelist/blacklist

**Filtering Logic:**
```python
def should_analyze(self, file_path: str) -> FileFilterResult:
    # Check system paths first (if auto_detect is enabled)
    if self.auto_detect:
        if is_system_file(file_path, self.system_paths):
            return FileFilterResult(should_analyze=False, reason="system_lib")

    # Use PathFilter for whitelist/blacklist (relative paths)
    result = self.path_filter.should_analyze(file_path)

    if not result:
        reason = self.path_filter.get_skip_reason(file_path)
        return FileFilterResult(should_analyze=False, reason=reason)

    return FileFilterResult(should_analyze=True, reason=None)
```

---

### Module 4: `path_extractor.py` - Path Extraction from Compilation Flags

**Responsibilities:**
- Extract include paths from compilation flags with type information
- Extract library paths from compilation flags
- Support cross-compiler flags (e.g., ARM, RISC-V)

**Key Classes/Functions:**
```python
@dataclass
class IncludePath:
    path: str
    type: str  # "system", "user", "after", "quote", "framework"

@dataclass
class ExtractedPaths:
    include_paths: List[IncludePath]
    library_paths: List[str]
    framework_paths: List[str]

class PathExtractor:
    def __init__(self)
    def extract(self, flags: List[str]) -> ExtractedPaths
    def extract_include_paths(self, flags: List[str]) -> List[IncludePath]
    def extract_library_paths(self, flags: List[str]) -> List[str]
    def extract_framework_paths(self, flags: List[str]) -> List[str]
    def get_system_paths(self) -> List[str]
```

**Supported Include Flag Formats:**
- `-isystem <path>`: System include (marked as system library)
- `-I <path>`: User include (not system)
- `-I<path>`: User include (no space)
- `-idirafter <path>`: Include after system directories
- `-iquote <path>`: Include directory for #quote
- `-F <path>`: Framework directory (macOS)
- `-F<path>`: Framework directory (macOS, no space)

**Implementation:**
```python
def extract_include_paths(self, flags: List[str]) -> List[IncludePath]:
    """Extract all include paths with their types."""
    include_paths = []
    i = 0
    while i < len(flags):
        flag = flags[i]

        # -isystem <path> (system include)
        if flag == '-isystem' and i + 1 < len(flags):
            include_paths.append(IncludePath(path=flags[i + 1], type="system"))
            i += 2

        # -I<path> (user include)
        elif flag.startswith('-I') and len(flag) > 2:
            include_paths.append(IncludePath(path=flag[2:], type="user"))
            i += 1

        # -I <path> (user include, space-separated)
        elif flag == '-I' and i + 1 < len(flags):
            include_paths.append(IncludePath(path=flags[i + 1], type="user"))
            i += 2

        # -idirafter <path> (include after system)
        elif flag == '-idirafter' and i + 1 < len(flags):
            include_paths.append(IncludePath(path=flags[i + 1], type="after"))
            i += 2

        # -iquote <path> (quote include)
        elif flag == '-iquote' and i + 1 < len(flags):
            include_paths.append(IncludePath(path=flags[i + 1], type="quote"))
            i += 2

        # -F<path> (framework directory, macOS)
        elif flag.startswith('-F') and len(flag) > 2:
            include_paths.append(IncludePath(path=flag[2:], type="framework"))
            i += 1

        # -F <path> (framework directory, macOS, space-separated)
        elif flag == '-F' and i + 1 < len(flags):
            include_paths.append(IncludePath(path=flags[i + 1], type="framework"))
            i += 2

        else:
            i += 1

    return include_paths

def get_system_paths(self) -> List[str]:
    """Get only system-type include paths."""
    return [ip.path for ip in self.include_paths if ip.type == "system"]
```

---

### Module 5: `cli.py` - Command-Line Interface

**Responsibilities:**
- Parse command-line arguments
- Set up logging
- Coordinate main workflow
- Handle errors

**Key Functions:**
```python
def parse_args() -> argparse.Namespace
def main() -> int
```

**CLI Options:**
```
--input, -i         Path to compile_commands.json (default: auto-detect)
--output, -o        Output file path (default: stdout)
--verbose, -v       Logging level (error, warning, info, debug)
--config, -c        Path to config file (default: clang-call-analyzer.yml)
--whitelist         Paths to analyze (comma-separated, overrides config)
--blacklist         Paths to exclude (comma-separated, overrides config)
--no-whitelist      Disable default whitelist (analyze everything not blacklisted)
--no-auto-detect    Disable auto-detection of system paths
--show-skipped      Show skipped files and reasons
--version           Show version
```

---

### Module 6: `compilation_db.py` - Compilation Database

**Responsibilities:**
- Read and parse `compile_commands.json`
- Extract file paths and compilation flags
- Validate format
- Extract include and library paths for system detection

**Key Classes/Functions:**
```python
@dataclass
class CompilationUnit:
    directory: str
    command: str
    file: str
    flags: List[str]

class CompilationDatabase:
    def __init__(self, db_path: str)
    def load(self) -> None
    def get_units(self) -> List[CompilationUnit]
    def get_flags_for_file(self, file_path: str) -> List[str]
    def get_all_include_paths(self) -> List[str]  # New: collect all -I paths
    def get_all_library_paths(self) -> List[str]  # New: collect all -L paths
```

---

### Module 7: `ast_parser.py` - AST Parsing

**Responsibilities:**
- Initialize libclang Index
- Parse translation units with correct flags
- Handle parse errors with graceful degradation
- Support cross-platform compilation (ARM, RISC-V, etc.)

**Key Classes/Functions:**
```python
class ASTParser:
    def __init__(self, clang_args: List[str])
    def parse_file(self, file_path: str) -> Optional[clang.TranslationUnit]
    def get_diagnostics(self) -> List[str]

class ParseResult:
    success: bool
    translation_unit: Optional[clang.TranslationUnit]
    error_message: Optional[str]
```

**libclang Usage:**
```python
index = clang.cindex.Index.create()
try:
    tu = index.parse(file_path, args=flags, options=clang.cindex.TranslationUnit.PARSE_DETAILED_PROCESSING_RECORD)
except Exception as e:
    return ParseResult(success=False, translation_unit=None, error_message=str(e))
```

**Cross-Platform Support:**
- Pass all compiler flags from compile_commands.json to libclang
- Let libclang handle architecture-specific includes and defines
- No platform-specific assumptions

---

### Module 8: `function_extractor.py` - Function Extraction

**Responsibilities:**
- Traverse AST to find function definitions
- Extract function metadata (location, name, signature)
- Distinguish definitions from declarations
- Only extract from files that pass the filter

**Key Classes/Functions:**
```python
@dataclass
class FunctionInfo:
    path: str
    line_range: Tuple[int, int]
    name: str
    qualified_name: str
    brief: Optional[str]
    raw_cursor: clang.cindex.Cursor

class FunctionExtractor:
    def __init__(self, tu: clang.TranslationUnit, file_filter: FileFilter)
    def extract(self) -> List[FunctionInfo]
    def _is_function_definition(self, cursor: clang.Cursor) -> bool
    def _get_function_signature(self, cursor: clang.Cursor) -> str
    def _should_extract_from_file(self, file_path: str) -> bool
```

**AST Traversal:**
```python
def extract(self) -> List[FunctionInfo]:
    functions = []
    for cursor in tu.cursor.walk_preorder():
        if self._is_function_definition(cursor):
            file_path = str(cursor.location.file)
            if not self._should_extract_from_file(file_path):
                continue
            info = self._extract_info(cursor)
            functions.append(info)
    return functions
```

**Cursor Kinds:**
- `CursorKind.FUNCTION_DECL`
- `CursorKind.CXX_METHOD`
- `CursorKind.CONSTRUCTOR`
- `CursorKind.DESTRUCTOR`

**Check Definition vs Declaration:**
```python
def _is_function_definition(self, cursor: clang.Cursor) -> bool:
    return cursor.is_definition() and cursor.location.file
```

**File Filtering:**
```python
def _should_extract_from_file(self, file_path: str) -> bool:
    # FileFilter handles relative path conversion internally
    result = self.file_filter.should_analyze(file_path)
    if not result.should_analyze and self.config.show_skipped:
        rel_path = self.file_filter.path_filter._to_relative_path(file_path)
        self.logger.info(f"Skipping {rel_path}: {result.reason}")
    return result.should_analyze
```

---

### Module 9: `doxygen_parser.py` - Doxygen Comment Extraction

**Responsibilities:**
- Extract Doxygen comments preceding functions
- Parse `@brief` tags
- Handle both `/** */` and `///` styles

**Key Classes/Functions:**
```python
class DoxygenParser:
    def __init__(self)
    def extract_brief(self, cursor: clang.Cursor) -> Optional[str]
    def _parse_brief_tag(self, comment: str) -> Optional[str]
    def _extract_comment_text(self, cursor: clang.Cursor) -> Optional[str]
```

**Comment Extraction:**
```python
def extract_brief(self, cursor: clang.Cursor) -> Optional[str]:
    raw_comment = cursor.raw_comment
    if not raw_comment:
        return None
    return self._parse_brief_tag(raw_comment)
```

**Brief Tag Parsing:**
```python
def _parse_brief_tag(self, comment: str) -> Optional[str]:
    # 更健壮的正则表达式
    # 支持 @brief 和 \brief，支持行首、行尾、多行
    patterns = [
        r'@brief\s+(.*?)(?:\n\s*@|\n\s*(?:///|\*/)|$)',
        r'\\brief\s+(.*?)(?:\n\s*@|\n\s*(?:///|\*/)|$)',
        r'@brief\s*$\s+(.*?)(?:\n\s*@|\n\s*(?:///|\*/)|$)',  # @brief 在行首
    ]

    for pattern in patterns:
        match = re.search(pattern, comment, re.DOTALL | re.MULTILINE)
        if match:
            return match.group(1).strip()
    return None
```

---

### Module 10: `call_analyzer.py` - Call Relationship Analysis

**Responsibilities:**
- Find function calls within function bodies
- Resolve calls to function definitions
- Build call graph
- Only resolve calls to functions in analyzed files

**Key Classes/Functions:**
```python
@dataclass
class CallInfo:
    caller_cursor: clang.Cursor
    callee_name: str
    callee_location: Tuple[str, int]

class CallAnalyzer:
    def __init__(self, function_registry: 'FunctionRegistry')
    def analyze_calls(self, function: FunctionInfo) -> List[CallInfo]
    def _resolve_callee(self, call_cursor: clang.Cursor) -> Optional[FunctionInfo]
```

**Call Detection:**
```python
def analyze_calls(self, function: FunctionInfo) -> List[CallInfo]:
    calls = []
    for cursor in function.raw_cursor.walk_preorder():
        if cursor.kind == clang.cindex.CursorKind.CALL_EXPR:
            callee_name = cursor.spelling
            resolved = self._resolve_callee(cursor)
            if resolved:
                calls.append(CallInfo(function.raw_cursor, callee_name, (resolved.path, resolved.line_range[0])))
    return calls
```

**Resolution Strategy:**
1. Use `cursor.referenced` to get the called function cursor
2. Always lookup by `qualified_name` (supports cross-file calls)
3. Only resolve if the target function is in analyzed files (not filtered)

---

### Module 11: `function_registry.py` - Function Indexing

**Responsibilities:**
- Store all discovered functions
- Provide lookup by cursor, name, or qualified name
- Assign sequential indices
- Track which functions are in analyzed files

**Key Classes/Functions:**
```python
class FunctionRegistry:
    def __init__(self)
    def add_function(self, info: FunctionInfo) -> int
    def get_by_index(self, index: int) -> Optional[FunctionInfo]
    def get_by_qualified_name(self, name: str) -> Optional[int]
    def get_all(self) -> List[FunctionInfo]
    def count(self) -> int
    def is_analyzed_function(self, path: str, qualified_name: str) -> bool
```

**Data Structures:**
```python
self._functions: List[FunctionInfo] = []
self._name_to_indices: Dict[str, List[int]] = {}  # qualified_name -> indices (for overloading)
self._analyzed_paths: Set[str] = set()  # Track analyzed file paths
```

---

### Module 12: `relationship_builder.py` - Relationship Construction

**Responsibilities:**
- Build bidirectional call graph
- Populate `parents` and `children` arrays
- Only include relationships between analyzed functions

**Key Classes/Functions:**
```python
class RelationshipBuilder:
    def __init__(self, registry: FunctionRegistry, analyzer: CallAnalyzer)
    def build(self) -> Dict[int, Tuple[List[int], List[int]]]
    def _build_parents(self, calls: List[CallInfo]) -> List[int]
    def _build_children(self, calls: List[CallInfo]) -> List[int]
```

**Algorithm:**
```python
def build(self) -> Dict[int, Tuple[List[int], List[int]]]:
    relationships = {}
    for func_idx, func in enumerate(self.registry.get_all()):
        calls = self.analyzer.analyze_calls(func)
        parents = self._build_parents(calls)
        children = self._build_children(calls)
        relationships[func_idx] = (parents, children)
    return relationships
```

---

### Module 13: `json_emitter.py` - JSON Output

**Responsibilities:**
- Serialize data to required JSON format
- Handle output to file or stdout

**Key Classes/Functions:**
```python
@dataclass
class FunctionOutput:
    index: int
    self: Dict[str, Any]
    parents: List[int]
    children: List[int]

class JSONEmitter:
    def __init__(self, output_file: Optional[str] = None)
    def emit(self, functions: List[FunctionInfo],
             relationships: Dict[int, Tuple[List[int], List[int]]]) -> None
    def _format_function(self, index: int,
                         func: FunctionInfo,
                         parents: List[int],
                         children: List[int]) -> FunctionOutput
```

---

## Data Flow

```
clang-call-analyzer.yml (optional)
    ↓
ConfigLoader.load()
    ↓
Config (whitelist, blacklist with PathPattern objects, auto_detect_system_paths)

compile_commands.json
    ↓
CompilationDatabase.load()
    ├─→ PathExtractor.extract() → ExtractedPaths (with type: system/user/after/quote/framework)
    ├─→ PathExtractor.get_system_paths() → List[str] (only -isystem paths)
    ├─→ FileFilter.set_system_paths() (if auto_detect_system_paths)
    └─→ TUIterator
            ↓ (for each unit)
            FileFilter.should_analyze()
            ├─→ Convert to relative path (from project root)
            ├─→ Check system paths (if auto_detect_system_paths)
            └─→ Check whitelist/blacklist (with matching modes: prefix/glob/regex)
            ↓ (if passes filter)
            ├─→ ASTParser.parse()
            │       ↓
            │       FunctionExtractor.extract() → FunctionInfo (with DoxygenParser)
            │               ↓
            │               FunctionRegistry.add_function()
            │
            ↓ (if parse fails or filtered)
            Log warning/reason (if show_skipped), continue with next file

    ↓ (all functions collected from analyzed files)
CallAnalyzer.analyze_calls() (for each function)
    ↓
RelationshipBuilder.build()
    ↓
JSONEmitter.emit()
    ↓
JSON output
```

**Key Changes in Data Flow:**

1. **PathExtractor:** Returns `IncludePath` objects with type information
2. **System Paths:** Only `-isystem` paths (type="system") are filtered
3. **FileFilter:** Converts absolute paths to relative paths before matching
4. **Pattern Matching:** Supports prefix, glob, and regex modes via `PathPattern` objects

---

## Implementation Details

### Cross-Platform Support Strategy

**Key Principles:**
1. **No Hardcoded Paths:** All system paths are detected ONLY from compiler flags (`-isystem`, `-I`, etc.)
2. **Pass-Through Compilation Flags:** All flags are passed to libclang without modification
3. **Graceful Degradation:** If a file fails to parse, log warning and continue
4. **Relative Path Matching:** Whitelist/blacklist use relative paths from project root
5. **Configuration-Driven:** Users control analysis scope via whitelist/blacklist

**Supported Platforms:**

| Platform | Compiler | Architecture | System Path Detection |
|----------|----------|--------------|------------------------|
| Linux Embedded | gcc/clang | ARM, x86 | From `-isystem` flags only |
| MCU Embedded | arm-none-eabi-gcc | ARM Cortex-M | From `-isystem` flags only |
| ESP32 | xtensa-esp32-elf-gcc | Xtensa | From `-isystem` flags only |
| ESP32-S3 | riscv32-esp-elf-gcc | RISC-V | From `-isystem` flags only |
| NixOS | gcc/clang | x86_64 | From `-isystem` flags only (NOT all /nix/store/) |
| macOS | clang | x86_64, arm64 | From `-isystem` flags only |

**NO Hardcoded Path Detection:**

```python
# ✅ CORRECT: System paths from compiler flags ONLY
system_paths = get_system_paths(include_paths)  # Only -isystem flags

# ❌ WRONG: No hardcoded patterns like this
# SYSTEM_PATH_PATTERNS = ['/usr/include/', '/nix/store/', ...]  # DO NOT USE
```

**Example: ESP32 Project with Explicit System Flags**

compile_commands.json:
```json
[
  {
    "directory": "/home/user/esp32-project",
    "command": "xtensa-esp32-elf-g++ -c src/main.cpp -isystem /home/user/.platformio/packages/framework-arduinoespressif32/cores/esp32 -Isrc/include",
    "file": "src/main.cpp"
  }
]
```

Auto-detected system paths:
- `/home/user/.platformio/packages/framework-arduinoespressif32/cores/esp32` (from `-isystem`)

Analysis result:
- ✅ `src/main.cpp` (analyzed - relative path "src/main.cpp" matches default whitelist)
- ✅ `src/include/helper.h` (analyzed - relative path matches default whitelist)
- ❌ Framework headers (filtered - system library from `-isystem` flag)

**Example: NixOS Project with Proper System Flags**

compile_commands.json:
```json
[
  {
    "directory": "/home/user/nixos-project",
    "command": "clang++ -c src/main.cpp -isystem /nix/store/abc123-glibc-2.35/include -I/nix/store/def456-mylib/include -Isrc/include",
    "file": "src/main.cpp"
  }
]
```

Auto-detected system paths:
- `/nix/store/abc123-glibc-2.35/include` (from `-isystem` - system library)

Analysis result:
- ✅ `src/main.cpp` (analyzed - relative path "src/main.cpp" matches default whitelist)
- ✅ `/nix/store/def456-mylib/include/lib.h` (analyzed - NOT from `-isystem`, so not system lib)
- ❌ `/nix/store/abc123-glibc-2.35/include/stdio.h` (filtered - system library from `-isystem`)

**Key NixOS Fix:**
- `/nix/store/abc123-glibc-2.35/include` → Filtered (from `-isystem`)
- `/nix/store/def456-mylib/include` → Analyzed (from `-I`, not `-isystem`)
- This allows project dependencies in `/nix/store/` to be analyzed while filtering actual system libraries

**Example: Project with Custom Whitelist**

clang-call-analyzer.yml:
```yaml
whitelist:
  - pattern: "core/"
    mode: "prefix"
  - pattern: "utils/**/*.h"
    mode: "glob"
blacklist:
  - pattern: "core/generated/"
    mode: "prefix"
```

File: `/home/user/myproject/core/main.cpp`
- Relative path: `core/main.cpp`
- Matches whitelist: `core/` (prefix)
- **Result:** ✅ Analyzed

File: `/home/user/myproject/core/generated/code.h`
- Relative path: `core/generated/code.h`
- Matches blacklist: `core/generated/` (prefix)
- **Result:** ❌ Filtered

File: `/home/user/myproject/utils/helpers/helper.h`
- Relative path: `utils/helpers/helper.h`
- Matches whitelist: `utils/**/*.h` (glob)
- **Result:** ✅ Analyzed

File: `/home/user/myproject/tests/test.cpp`
- Relative path: `tests/test.cpp`
- No whitelist match
- **Result:** ❌ Filtered (not in whitelist)

---

### libclang Setup

```python
import clang.cindex

# Set libclang library path if needed
# clang.cindex.Config.set_library_path('/usr/lib/llvm-14/lib')

index = clang.cindex.Index.create()
```

### Compilation Flags Processing

```python
def extract_flags(command: str) -> List[str]:
    """Extract clang-compatible flags from compile command."""
    tokens = command.split()
    flags = []
    for token in tokens:
        if token.startswith('-I'):
            flags.append(token)
        elif token.startswith('-D'):
            flags.append(token)
        elif token in ('-std=c++11', '-std=c++14', '-std=c++17', '-std=c++20'):
            flags.append(token)
    return flags
```

### Function Signature Construction

```python
def get_function_signature(self, cursor: clang.Cursor) -> str:
    """Build qualified name with parameters."""
    result_parts = []

    # Get scope (namespace/class)
    if cursor.semantic_parent:
        scope = self._get_qualified_scope(cursor.semantic_parent)
        if scope:
            result_parts.append(scope + "::")

    # Function name
    result_parts.append(cursor.spelling)

    # Parameters
    params = []
    for arg in cursor.get_arguments():
        param_type = arg.type.spelling
        params.append(param_type)

    result_parts.append(f"({', '.join(params)})")

    return ''.join(result_parts)
```

### Line Range Calculation

```python
def get_line_range(self, cursor: clang.Cursor) -> Tuple[int, int]:
    """Get start and end line of function definition."""
    extent = cursor.extent
    start = extent.start.line
    end = extent.end.line
    return (start, end)
```

### Call Graph Resolution

```python
def _resolve_callee(self, call_cursor: clang.Cursor) -> Optional[int]:
    """Resolve function call to definition index."""
    referenced = call_cursor.referenced
    if not referenced:
        return None

    # 完全依赖 qualified_name 查找（支持跨文件）
    qualified_name = self._get_qualified_name(referenced)
    indices = self.registry.get_by_qualified_name(qualified_name)

    if not indices:
        return None

    # 对于重载，尝试匹配参数类型
    if len(indices) > 1:
        return self._match_overload(call_cursor, indices)

    return indices[0]
```

---

## Error Handling Strategy

### 1. File-Level Errors
- Log warning for files that fail to parse
- Skip file, continue with others
- Collect diagnostics for error reporting
- Distinguish between parse errors and filtered files

### 2. Filter-Level Handling
- Log each filtered file with reason (system lib, external lib, not in whitelist)
- Provide option to show/hide filtered files (--show-skipped)
- Count filtered files for summary report

### 3. Function-Level Errors
- Handle cases where function info cannot be extracted
- Log with location context
- Skip function, continue with others

### 4. Graceful Degradation
- Missing `@brief`: Use `null`
- Unresolved calls: Omit from relationships
- Macro-defined functions: Skip (libclang limitation)
- Platform-specific features not supported: Log warning, skip
- Include files not found: Log warning, continue

### 5. Error Recovery
- If a file fails to parse, log the error and continue with next file
- If libclang is not available, provide clear error message
- If config file is malformed, use defaults and log warning

**Example Logging:**

```
INFO: Loading config from clang-call-analyzer.yml
INFO: Auto-detected 5 system library paths
INFO: Processing 12 translation units
  src/main.cpp: ✓ (42 functions extracted)
  lib/helper.cpp: ✓ (18 functions extracted)
  /usr/include/stdio.h: ✗ (filtered: system library)
  third_party/opencv/imgproc.cpp: ✗ (filtered: external library)
  test/legacy.c: ✗ (parse error: missing header file)
WARN: /nix/store/abc123-glibc/include/stdio.h: filtered (system library)
WARN: src/missing.cpp: parse failed (clang error: 'missing.h' file not found)
INFO: Analysis complete: 60 functions from 2 files
```

---

## Testing Strategy

### Unit Tests
- Test each module independently
- Mock libclang cursors where possible
- Test edge cases (empty comments, templates, etc.)

### Integration Tests
- Test full pipeline with sample `compile_commands.json`
- Verify output JSON structure
- Validate call relationships

### Sample Test Cases
1. Simple C function with @brief
2. C++ method in class
3. Template function
4. Function with no Doxygen comment
5. Function calling multiple other functions
6. Recursive function call
7. Overloaded functions

---

## Development Steps

### Phase 1: Core Infrastructure (Priority: High)
1. Set up project structure
2. Create `requirements.txt` with dependencies (add pyyaml)
3. Implement `cli.py` - basic CLI skeleton with new options
4. Implement `config_loader.py` - YAML configuration
5. Implement `path_filter.py` - path filtering logic
6. Implement `file_filter.py` - comprehensive filtering with system detection
7. Implement `path_extractor.py` - extract include/library paths
8. Implement `compilation_db.py` - parse JSON + extract paths
9. Implement `ast_parser.py` - basic libclang integration
10. **Milestone:** Parse single file and get AST with filtering

### Phase 2: Function Extraction (Priority: High)
1. Implement `function_extractor.py` (with file filtering)
2. Implement `doxygen_parser.py`
3. Implement `function_registry.py`
4. **Milestone:** Extract function metadata from filtered files

### Phase 3: Call Analysis (Priority: High)
1. Implement `call_analyzer.py`
2. Implement `relationship_builder.py`
3. **Milestone:** Build call graph for multiple filtered files

### Phase 4: Output & Polish (Priority: Medium)
1. Implement `json_emitter.py`
2. Connect all modules in main pipeline
3. Add comprehensive error handling
4. Add logging for skipped files
5. **Milestone:** Full working tool with filtering

### Phase 5: Cross-Platform Testing (Priority: High)
1. Test on Linux embedded project (ARM)
2. Test on MCU embedded project (ARM Cortex-M)
3. Test on ESP32 project (Xtensa/RISC-V)
4. Test on NixOS environment
5. Test on standard Linux project
6. **Milestone:** Verify cross-platform compatibility

### Phase 6: Testing & Documentation (Priority: Medium)
1. Write unit tests for new modules
2. Write integration tests with filtering scenarios
3. Add README with usage examples
4. Add filtering guide to documentation
5. Test on real projects

---

## File Structure

```
clang-call-analyzer/
├── requirements.txt
├── README.md
├── clang-call-analyzer.yml  # Example config file (optional)
├── src/
│   ├── __init__.py
│   ├── cli.py
│   ├── config_loader.py          # NEW: Load YAML configuration
│   ├── path_filter.py            # NEW: Path filtering logic
│   ├── file_filter.py            # NEW: Comprehensive file filtering
│   ├── path_extractor.py         # NEW: Extract include/library paths
│   ├── compilation_db.py
│   ├── ast_parser.py
│   ├── function_extractor.py
│   ├── doxygen_parser.py
│   ├── call_analyzer.py
│   ├── function_registry.py
│   ├── relationship_builder.py
│   └── json_emitter.py
├── tests/
│   ├── __init__.py
│   ├── test_config_loader.py     # NEW
│   ├── test_path_filter.py       # NEW
│   ├── test_file_filter.py       # NEW
│   ├── test_compilation_db.py
│   ├── test_function_extractor.py
│   ├── test_doxygen_parser.py
│   └── test_integration.py
└── test_data/
    ├── compile_commands.json
    ├── sample.cpp
    ├── expected_output.json
    ├── clang-call-analyzer.yml   # NEW: Example config
    └── platforms/                 # NEW: Test data for different platforms
        ├── esp32/
        ├── mcu/
        └── nixos/
```

---

## Dependencies

### requirements.txt
```
clang>=16.0.0
pyyaml>=6.0  # For configuration file parsing
```

### System Dependencies
- `libclang` (from LLVM/Clang package)
  - On Ubuntu/Debian: `sudo apt install libclang-dev`
  - On Fedora: `sudo dnf install clang-devel`
  - On macOS: `brew install llvm`

### 版本兼容性说明

Python `clang` 包版本必须与系统 libclang 版本匹配。

| 系统 | 建议的 libclang 版本 | Python clang 包版本 |
|------|---------------------|-------------------|
| Ubuntu 20.04 | 10.0 | clang>=10.0.0 |
| Ubuntu 22.04 | 14.0 | clang>=14.0.0 |
| Ubuntu 24.04 | 18.0 | clang>=18.0.0 |
| Fedora 40 | 18.0 | clang>=18.0.0 |
| macOS (Homebrew) | 19.0 | clang>=19.0.0 |

检查版本：
```bash
# 检查系统 libclang 版本
llvm-config --version

# 检查 Python clang 包版本
python -c "import clang; print(clang.cindex.conf.get_cxx_library_version())"
```

如果版本不匹配，安装正确的版本：
```bash
pip install clang==<版本号>
```

---

## Performance Considerations

1. **Memory:** Process one translation unit at a time, free AST after extraction
2. **Caching:** Function registry builds incrementally
3. **Parallelism:** Could parallelize file parsing (future optimization)
4. **I/O:** Stream JSON output for large result sets

---

## Configuration Examples

### Example 1: Default Configuration (Minimal)

```yaml
# clang-call-analyzer.yml - Minimal config
# Use auto-detection for system paths + default whitelist

log_level: "info"
show_skipped: true
auto_detect_system_paths: true

# Whitelist is empty = default whitelist (src/, lib/, include/, app/) will be used
# Use --no-whitelist CLI flag to disable default whitelist
whitelist: []

# Blacklist is empty = only auto-detected system paths (from -isystem flags) are filtered
blacklist: []
```

**Behavior:**
- Default whitelist applies: `["src/", "lib/", "include/", "app/"]`
- System paths detected from `-isystem` flags
- All `/nix/store/` paths are analyzed UNLESS they come from `-isystem`

### Example 2: ESP32 Project with Explicit System Flag

```yaml
# clang-call-analyzer.yml - ESP32 Project

# Analyze only source code
whitelist:
  - pattern: "src/"
    mode: "prefix"
  - pattern: "components/my-component/"
    mode: "prefix"
  - pattern: "main/"
    mode: "prefix"

# Filter specific directories
blacklist:
  - pattern: "components/esp-*"
    mode: "glob"
  - pattern: "managed_components/"
    mode: "prefix"
  - pattern: ".platformio/"
    mode: "prefix"

log_level: "info"
show_skipped: true
auto_detect_system_paths: true
```

**Assume compile_commands.json has:**
```json
{
  "command": "xtensa-esp32-elf-g++ -isystem /home/user/.platformio/packages/framework-arduinoespressif32/cores/esp32 -Isrc/include -c src/main.cpp"
}
```

**Filtering behavior:**
- ✅ `src/main.cpp` (whitelist: `src/` prefix)
- ✅ `src/include/helper.h` (whitelist: `src/` prefix)
- ❌ Framework headers (system path from `-isystem`)
- ❌ `components/esp-idf/system.h` (blacklist: `components/esp-*` glob)

### Example 3: NixOS Project (Critical Fix)

```yaml
# clang-call-analyzer.yml - NixOS Project

# Explicit whitelist
whitelist:
  - pattern: "src/"
    mode: "prefix"
  - pattern: "lib/"
    mode: "prefix"
  - pattern: "include/"
    mode: "prefix"
  - pattern: "tests/"
    mode: "prefix"

# Blacklist specific subdirectories
blacklist:
  - pattern: "lib/generated/"
    mode: "prefix"

log_level: "debug"  # Show detailed filtering info
show_skipped: true
auto_detect_system_paths: true
```

**Assume compile_commands.json has:**
```json
{
  "command": "clang++ -isystem /nix/store/abc123-glibc-2.35/include -I/nix/store/def456-mylib/include -Isrc/include -c src/main.cpp"
}
```

**Filtering behavior (CRITICAL FIX):**
- ✅ `src/main.cpp` (whitelist: `src/` prefix)
- ✅ `/nix/store/def456-mylib/include/lib.h` (NOT from `-isystem`, so analyzed)
- ❌ `/nix/store/abc123-glibc-2.35/include/stdio.h` (system path from `-isystem`, filtered)

**Key Fix:**
- Before: All `/nix/store/` paths were filtered ❌
- After: Only `/nix/store/` paths from `-isystem` flags are filtered ✅

### Example 4: MCU Embedded Project

```yaml
# clang-call-analyzer.yml - ARM Cortex-M Project

# Analyze application code only
whitelist:
  - pattern: "src/"
    mode: "prefix"
  - pattern: "lib/"
    mode: "prefix"
  - pattern: "inc/"
    mode: "prefix"

# Exclude STM32 HAL and external libraries
blacklist:
  - pattern: "Drivers/STM32*HAL_Driver/"
    mode: "glob"
  - pattern: "Drivers/CMSIS/"
    mode: "prefix"
  - pattern: "Middlewares/"
    mode: "prefix"
  - pattern: "third_party/"
    mode: "prefix"

log_level: "info"
show_skipped: true
auto_detect_system_paths: true
```

**Assume compile_commands.json has:**
```json
{
  "command": "arm-none-eabi-gcc -isystem /opt/arm-none-eabi/include -Isrc/inc -Ilib -c src/main.c"
}
```

**Filtering behavior:**
- ✅ `src/main.c` (whitelist: `src/` prefix)
- ✅ `lib/helper.c` (whitelist: `lib/` prefix)
- ❌ `Drivers/STM32F4xx_HAL_Driver/stm32f4xx_hal.c` (blacklist: `Drivers/STM32*HAL_Driver/` glob)
- ❌ `/opt/arm-none-eabi/include/stdint.h` (system path from `-isystem`)

### Example 5: Complex Pattern Matching

```yaml
# clang-call-analyzer.yml - Complex patterns

# Mix of prefix, glob, and regex
whitelist:
  - pattern: "core/"
    mode: "prefix"
  - pattern: "utils/**/*.h"
    mode: "glob"
  - pattern: "^src/.*\\.cpp$"
    mode: "regex"

# Multiple blacklist patterns
blacklist:
  - pattern: "core/generated/"
    mode: "prefix"
  - pattern: "**/*_test.cpp"
    mode: "glob"
  - pattern: "vendor/"
    mode: "prefix"

log_level: "info"
show_skipped: true
auto_detect_system_paths: true
```

**Filtering examples:**
- ✅ `core/main.cpp` (whitelist: `core/` prefix)
- ✅ `utils/helpers/helper.h` (whitelist: `utils/**/*.h` glob)
- ✅ `src/app.cpp` (whitelist: `^src/.*\.cpp$` regex)
- ❌ `core/generated/code.h` (blacklist: `core/generated/` prefix)
- ❌ `utils/helpers/helper_test.cpp` (blacklist: `**/*_test.cpp` glob)

### Example 6: No Whitelist (Analyze Everything Not Blacklisted)

```yaml
# clang-call-analyzer.yml - No whitelist

# Empty whitelist + --no-whitelist CLI flag = analyze everything
whitelist: []

# Only filter specific directories
blacklist:
  - pattern: "generated/"
    mode: "prefix"
  - pattern: "vendor/"
    mode: "prefix"

log_level: "info"
show_skipped: true
auto_detect_system_paths: true
```

**Run with:**
```bash
clang-call-analyzer --no-whitelist --show-skipped
```

**Behavior:**
- Analyzes ALL files not in blacklist AND not system paths
- Default whitelist is NOT applied (due to `--no-whitelist`)
- Only `generated/` and `vendor/` directories are filtered

---

## Known Limitations

1. **Macro-defined functions:** libclang cannot analyze macros
2. **Function pointers:** Indirect calls cannot be resolved statically
3. **Virtual functions:** Resolved based on static analysis only
4. **Template specializations:** Need to handle carefully
5. **Preprocessor conditionals:** All branches analyzed

---

## Open Questions

1. Should we include standard library functions in the analysis?
   - Decision: No, only analyze project source files
2. How to handle inline functions in headers?
   - Decision: Include if they appear in compilation database
3. Should we support custom Doxygen tags beyond @brief?
   - Decision: No, only @brief as per requirements

---

## Appendix: Migration Guide (Post-Linus Review)

### Changes from v1.0 to v2.0

#### 1. Configuration File Format

**v1.0 (String-only):**
```yaml
whitelist:
  - "src/"
  - "lib/"
blacklist:
  - "/usr/include/"
```

**v2.0 (Object format with modes):**
```yaml
whitelist:
  - pattern: "src/"
    mode: "prefix"
  - pattern: "lib/"
    mode: "prefix"
blacklist:
  - pattern: "vendor/"
    mode: "prefix"
```

#### 2. Path Matching Semantics

**v1.0:** Absolute path matching
```python
# Blacklist: ["/usr/include/"]
# File: /usr/include/stdio.h → Filtered (absolute match)
```

**v2.0:** Relative path matching
```python
# Blacklist: [{"pattern": "vendor/", "mode": "prefix"}]
# File: /project/vendor/lib.h → Filtered (relative: vendor/lib.h)
# File: /usr/include/stdio.h → Not matched (outside project root)
```

#### 3. System Path Detection

**v1.0:** Hardcoded patterns
```python
SYSTEM_PATH_PATTERNS = ['/usr/include/', '/nix/store/', ...]
if any(path.startswith(p) for p in SYSTEM_PATH_PATTERNS):
    return False  # Filter
```

**v2.0:** Compiler flags only
```python
# Detect from -isystem, -I, -idirafter, -iquote, -F
include_paths = extract_include_paths(flags)
system_paths = [p for p in include_paths if p.type == "system"]
if file_path in system_paths:
    return False  # Filter
```

#### 4. NixOS Handling

**v1.0:**
- All `/nix/store/` paths filtered
- Project dependencies in `/nix/store/` not analyzed ❌

**v2.0:**
- Only `-isystem` paths in `/nix/store/` filtered
- Project dependencies in `/nix/store/` (from `-I`) analyzed ✅

#### 5. Default Whitelist Behavior

**v1.0:**
- Empty whitelist = analyze everything ❌

**v2.0:**
- Empty whitelist = use default `["src/", "lib/", "include/", "app/"]` ✅
- Use `--no-whitelist` to disable default whitelist

### CLI Usage Changes

**v1.0:**
```bash
# Default: analyze everything (empty whitelist)
clang-call-analyzer

# No way to disable auto-detection
```

**v2.0:**
```bash
# Default: use default whitelist + auto-detect system paths
clang-call-analyzer

# Analyze everything not blacklisted (no default whitelist)
clang-call-analyzer --no-whitelist

# Disable auto-detection (no system path filtering)
clang-call-analyzer --no-auto-detect

# Show detailed filtering info
clang-call-analyzer --show-skipped
```

### Testing Checklist for v2.0

- [ ] Test with default whitelist (empty config)
- [ ] Test with `--no-whitelist` (analyze everything)
- [ ] Test with custom whitelist/blacklist (prefix, glob, regex modes)
- [ ] Test NixOS project (verify only `-isystem` paths filtered)
- [ ] Test ESP32 project (verify system paths from `-isystem` filtered)
- [ ] Test relative path matching (verify whitelist uses relative paths)
- [ ] Test without auto-detection (verify no hardcoded paths used)
