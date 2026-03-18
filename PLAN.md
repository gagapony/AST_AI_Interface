# clang-call-analyzer - Technical Implementation Plan

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
    │       ├─→ CompilationDatabase (parse compile_commands.json)
    │       │       │
    │       │       └─→ TUIterator (iterate translation units)
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

### Module 1: `cli.py` - Command-Line Interface

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
--input, -i    Path to compile_commands.json (default: auto-detect)
--output, -o   Output file path (default: stdout)
--verbose, -v  Logging level (error, warning, info, debug)
--version      Show version
```

---

### Module 2: `compilation_db.py` - Compilation Database

**Responsibilities:**
- Read and parse `compile_commands.json`
- Extract file paths and compilation flags
- Validate format

**Key Classes/Functions:**
```python
@dataclass
class CompilationUnit:
    directory: str
    command: str
    file: str
    flags: List[str]
    includes: List[str]

class CompilationDatabase:
    def __init__(self, db_path: str)
    def load(self) -> None
    def get_units(self) -> List[CompilationUnit]
    def get_flags_for_file(self, file_path: str) -> List[str]
```

---

### Module 3: `ast_parser.py` - AST Parsing

**Responsibilities:**
- Initialize libclang Index
- Parse translation units with correct flags
- Handle parse errors

**Key Classes/Functions:**
```python
class ASTParser:
    def __init__(self, clang_args: List[str])
    def parse_file(self, file_path: str) -> Optional[clang.TranslationUnit]
    def get_diagnostics(self) -> List[str]
```

**libclang Usage:**
```python
index = clang.cindex.Index.create()
tu = index.parse(file_path, args=flags, options=clang.cindex.TranslationUnit.PARSE_DETAILED_PROCESSING_RECORD)
```

---

### Module 4: `function_extractor.py` - Function Extraction

**Responsibilities:**
- Traverse AST to find function definitions
- Extract function metadata (location, name, signature)
- Distinguish definitions from declarations

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
    def __init__(self, tu: clang.TranslationUnit)
    def extract(self) -> List[FunctionInfo]
    def _is_function_definition(self, cursor: clang.Cursor) -> bool
    def _get_function_signature(self, cursor: clang.Cursor) -> str
```

**AST Traversal:**
```python
def extract(self) -> List[FunctionInfo]:
    functions = []
    for cursor in tu.cursor.walk_preorder():
        if self._is_function_definition(cursor):
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

---

### Module 5: `doxygen_parser.py` - Doxygen Comment Extraction

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

### Module 6: `call_analyzer.py` - Call Relationship Analysis

**Responsibilities:**
- Find function calls within function bodies
- Resolve calls to function definitions
- Build call graph

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

---

### Module 7: `function_registry.py` - Function Indexing

**Responsibilities:**
- Store all discovered functions
- Provide lookup by cursor, name, or qualified name
- Assign sequential indices

**Key Classes/Functions:**
```python
class FunctionRegistry:
    def __init__(self)
    def add_function(self, info: FunctionInfo) -> int
    def get_by_index(self, index: int) -> Optional[FunctionInfo]
    def get_by_qualified_name(self, name: str) -> Optional[int]
    def get_all(self) -> List[FunctionInfo]
    def count(self) -> int
```

**Data Structures:**
```python
self._functions: List[FunctionInfo] = []
self._name_to_indices: Dict[str, List[int]] = {}  # qualified_name -> indices (for overloading)
```

---

### Module 8: `relationship_builder.py` - Relationship Construction

**Responsibilities:**
- Build bidirectional call graph
- Populate `parents` and `children` arrays

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

### Module 9: `json_emitter.py` - JSON Output

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
compile_commands.json
    ↓
CompilationDatabase
    ↓ (CompilationUnit list)
TUIterator
    ↓ (for each unit)
    ├─→ ASTParser.parse()
    │       ↓
    │       FunctionExtractor.extract()
    │               ↓
    │               FunctionInfo (with DoxygenParser)
    │               ↓
    │               FunctionRegistry.add_function()
    │
    ↓ (all functions collected)
CallAnalyzer.analyze_calls() (for each function)
    ↓
RelationshipBuilder.build()
    ↓
JSONEmitter.emit()
    ↓
JSON output
```

---

## Implementation Details

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

### 2. Function-Level Errors
- Handle cases where function info cannot be extracted
- Log with location context
- Skip function, continue with others

### 3. Graceful Degradation
- Missing `@brief`: Use `null`
- Unresolved calls: Omit from relationships
- Macro-defined functions: Skip (libclang limitation)

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
2. Create `requirements.txt` with dependencies
3. Implement `cli.py` - basic CLI skeleton
4. Implement `compilation_db.py` - parse JSON
5. Implement `ast_parser.py` - basic libclang integration
6. **Milestone:** Parse single file and get AST

### Phase 2: Function Extraction (Priority: High)
1. Implement `function_extractor.py`
2. Implement `doxygen_parser.py`
3. Implement `function_registry.py`
4. **Milestone:** Extract function metadata from single file

### Phase 3: Call Analysis (Priority: High)
1. Implement `call_analyzer.py`
2. Implement `relationship_builder.py`
3. **Milestone:** Build call graph for multiple files

### Phase 4: Output & Polish (Priority: Medium)
1. Implement `json_emitter.py`
2. Connect all modules in main pipeline
3. Add comprehensive error handling
4. Add logging
5. **Milestone:** Full working tool

### Phase 5: Testing & Documentation (Priority: Medium)
1. Write unit tests
2. Write integration tests
3. Add README with usage examples
4. Test on real projects

---

## File Structure

```
clang-call-analyzer/
├── requirements.txt
├── README.md
├── src/
│   ├── __init__.py
│   ├── cli.py
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
│   ├── test_compilation_db.py
│   ├── test_function_extractor.py
│   ├── test_doxygen_parser.py
│   └── test_integration.py
└── test_data/
    ├── compile_commands.json
    ├── sample.cpp
    └── expected_output.json
```

---

## Dependencies

### requirements.txt
```
clang>=16.0.0
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
