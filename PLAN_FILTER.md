# Clang Call Analyzer - Filter Feature Implementation Plan

## Overview

Implement a graph filtering feature that allows users to generate a subgraph starting from a specific function. The implementation follows a phased approach: modify CLI, implement graph traversal, generate filtered output, and update HTML visualization.

---

## 🚨 强制要求：类型注解规范 (Mandatory: Type Annotation Standards)

**所有代码必须通过 `mypy --strict` 检查，无例外。**

### 核心规则 (Core Rules)

1. **所有使用的 typing 类型必须显式导入**
   ```python
   # ❌ 错误：使用了未导入的类型
   def process_data(data: Optional[List[str]]) -> Dict[str, int]:
       ...

   # ✅ 正确：显式导入所有使用的类型
   from typing import Optional, List, Dict, Set, Tuple, Any, Union
   from collections.abc import Mapping

   def process_data(data: Optional[List[str]]) -> Dict[str, int]:
       ...
   ```

2. **避免同一作用域内变量重复声明**
   ```python
   # ❌ 错误：同一作用域内多次声明同名变量
   def setup_paths(config: Dict[str, str]) -> None:
       db_path: Path = Path(config.get('db_path', '/var/lib/db'))
       # ... 一些处理 ...
       db_path: Path = Path(config.get('alt_db_path', '/tmp/db'))  # 重复声明！

   # ✅ 正确方案 1：使用条件赋值
   def setup_paths(config: Dict[str, str]) -> None:
       db_path: Path = Path(config.get('db_path', '/var/lib/db'))
       # ... 一些处理 ...
       if some_condition:
           db_path = Path(config.get('alt_db_path', '/tmp/db'))  # 只赋值，不重新声明类型

   # ✅ 正确方案 2：使用不同变量名
   def setup_paths(config: Dict[str, str]) -> None:
       primary_db_path: Path = Path(config.get('db_path', '/var/lib/db'))
       # ... 一些处理 ...
       fallback_db_path: Path = Path(config.get('alt_db_path', '/tmp/db'))
   ```

3. **所有函数必须有完整的返回类型注解**
   ```python
   # ❌ 错误：缺少返回类型
   def parse_args():
       ...

   # ❌ 错误：缺少返回类型
   def setup_logging(verbose: bool):
       ...

   # ❌ 错误：返回类型不完整
   def init_database(path: str):
       return Database(path)

   # ✅ 正确：显式返回 None
   def parse_args() -> argparse.Namespace:
       ...

   def setup_logging(verbose: bool) -> None:
       ...

   # ✅ 正确：返回具体类型
   def init_database(path: str) -> Database:
       return Database(path)
   ```

4. **所有局部变量必须显式类型注解**
   ```python
   # ❌ 错误
   name_map = {}
   file_functions = {}
   file_to_id = {}

   # ✅ 正确
   name_map: Dict[str, List[int]] = {}
   file_functions: Dict[str, List[Dict[str, Any]]] = {}
   file_to_id: Dict[str, int] = {}
   ```

2. **返回类型必须具体，不能是模糊类型**
   ```python
   # ❌ 错误：过于模糊
   def get_data() -> Dict[str, Dict]:
       ...

   # ✅ 正确：具体类型
   def get_data() -> Dict[str, Dict[str, Any]]:
       ...

   # ✅ 最佳实践：使用 TypedDict 明确结构
   class FunctionSelfInfo(TypedDict):
       qualified_name: str
       path: str
       line: List[int]

   def get_data() -> Dict[str, FunctionSelfInfo]:
       ...
   ```

3. **所有泛型类型必须指定完整参数**
   ```python
   # ❌ 错误
   my_dict: Dict = {}
   my_list: List = []
   my_tuple: Tuple = ()

   # ✅ 正确
   my_dict: Dict[str, int] = {}
   my_list: List[int] = []
   my_tuple: Tuple[int, str, bool] = (1, "foo", True)
   ```

4. **所有函数/方法必须注解参数和返回值**
   ```python
   # ❌ 错误
   def process(self, data: List[int]):
       ...

   # ✅ 正确
   def process(self, data: List[int]) -> List[int]:
       ...

   # ✅ 无返回值时使用 None
   def log_message(self, message: str) -> None:
       ...
   ```

### 常见反例模式 (Anti-patterns to Avoid)

```python
# ❌ 问题 1: 使用未导入的类型
def process(items: List[str]) -> Dict[str, int]:
    result = {}
    for item in items:
        result[item] = len(item)
    return result
# ✅ 修复：添加导入
from typing import List, Dict

def process(items: List[str]) -> Dict[str, int]:
    result: Dict[str, int] = {}
    for item in items:
        result[item] = len(item)
    return result

# ❌ 问题 2: 空字典初始化缺少类型
name_map = {}
# ✅ 修复
name_map: Dict[str, List[int]] = {}

# ❌ 问题 2: 返回类型过于模糊
def build_file_graph() -> Dict[str, Dict]:
    ...
# ✅ 修复
def build_file_graph() -> Dict[str, Dict[str, Any]]:
    ...

# ❌ 问题 3: 同一作用域内变量重复声明
def initialize(config: Dict[str, Any]) -> None:
    db_path: Path = Path(config['primary_db'])
    # ... 一些处理 ...
    db_path: Path = Path(config['secondary_db'])  # 错误！重复声明
# ✅ 修复：只赋值，不重新声明类型
def initialize(config: Dict[str, Any]) -> None:
    db_path: Path = Path(config['primary_db'])
    # ... 一些处理 ...
    if need_switch:
        db_path = Path(config['secondary_db'])  # 只赋值

# ❌ 问题 4: 函数缺少返回类型
def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--verbose', action='store_true')
    return parser.parse_args()

def setup_logging(verbose: bool):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level)
# ✅ 修复：添加完整返回类型
def parse_args() -> argparse.Namespace:
    parser: argparse.ArgumentParser = argparse.ArgumentParser()
    parser.add_argument('--verbose', action='store_true')
    return parser.parse_args()

def setup_logging(verbose: bool) -> None:
    level: int = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level)

# ❌ 问题 5: 循环变量缺少类型注解
for func in functions:
    qname = func['self']['qualified_name']
# ✅ 修复
for func in functions:
    qname: str = func['self']['qualified_name']
```

### 推荐实践 (Recommended Practices)

```python
# 1. 显式导入所有使用的 typing 类型
from typing import Dict, List, Set, Tuple, Optional, Any, TypedDict, Union
from collections import deque
import argparse
import logging
from pathlib import Path

# 2. 使用 TypedDict 定义数据结构
class FunctionSelfInfo(TypedDict):
    qualified_name: str
    path: str
    line: List[int]

class FunctionDict(TypedDict):
    index: int
    self: FunctionSelfInfo
    parents: List[int]
    children: List[int]

# 2. 在函数签名中使用类型别名和完整返回类型
def __init__(self, functions: List[FunctionDict]) -> None:
    self.functions: List[FunctionDict] = functions

def parse_args() -> argparse.Namespace:
    """Parse command-line arguments with complete return type."""
    parser: argparse.ArgumentParser = argparse.ArgumentParser()
    parser.add_argument('--verbose', action='store_true', default=False)
    parser.add_argument('--output', type=str, default='output.json')
    return parser.parse_args()

def setup_logging(verbose: bool) -> logging.Logger:
    """Setup logging and return logger instance."""
    logger: logging.Logger = logging.getLogger(__name__)
    level: int = logging.DEBUG if verbose else logging.INFO
    logger.setLevel(level)
    return logger

# 3. 所有变量显式类型注解
def process_data(self) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    temp_map: Dict[str, int] = {}
    index: int = 0

    for item in self.functions:
        item_id: int = item['index']
        temp_map[str(item_id)] = index
        result.append(item)
        index += 1

    return result

# 4. 避免同一作用域内变量重复声明
def initialize_paths(config: Dict[str, str]) -> Tuple[Path, Path]:
    """
    Initialize paths from configuration.

    Returns:
        Tuple of (db_path, log_path)
    """
    # 方案 A: 使用条件赋值
    db_path: Path = Path(config.get('db_path', '/var/lib/db'))
    if config.get('use_temp_db') == 'true':
        db_path = Path('/tmp/db')  # 只赋值，不重复声明类型

    # 方案 B: 使用不同变量名
    primary_db_path: Path = Path(config.get('db_path', '/var/lib/db'))
    fallback_db_path: Path = Path('/tmp/db')
    final_db_path: Path = fallback_db_path if config.get('use_temp_db') == 'true' else primary_db_path

    log_path: Path = Path(config.get('log_path', '/var/log/app.log'))

    return final_db_path, log_path

def process_with_retry(config: Dict[str, Any]) -> Dict[str, Any]:
    """Process data with retry logic using distinct variable names."""
    max_retries: int = config.get('max_retries', 3)

    # 第一次尝试
    attempt: int = 1
    result: Optional[Dict[str, Any]] = try_operation(attempt)

    # 如果失败，重试
    while result is None and attempt <= max_retries:
        attempt += 1
        result = try_operation(attempt)  # 只赋值给 result，不重复声明

    final_result: Dict[str, Any] = result or {'status': 'failed'}
    return final_result

# 5. 使用类型注解的可选参数
def find_function(
    self,
    name: str,
    exact_match: bool = True,
    logger: Optional[logging.Logger] = None
) -> Optional[FunctionDict]:
    ...
```

### 验证命令 (Validation Commands)

```bash
# 运行 mypy strict 模式检查
mypy --strict src/graph_filter.py src/file_graph_generator.py

# 修复类型注解后应该无输出（通过）
# 有错误则必须修复后再提交
```

---

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         CLI Entry Point                         │
│                          (cli.py:main)                          │
└─────────────────────┬───────────────────────────────────────────┘
                      │
                      ├─→ Parse args (check --filter-func)
                      │
                      ├─→ Full graph generation (existing flow)
                      │   └─→ JSONEmitter → FileGraphGenerator → HTML
                      │
                      └─→ Filter graph (new flow)
                          │
                          ├─→ Find target function
                          │
                          ├─→ Traverse graph (BFS/DFS)
                          │
                          ├─→ Filter and re-index nodes
                          │
                          └─→ Generate filtered output
                              ├─→ filegraph_<func>.json
                              └─→ filegraph_<func>.html
```

---

## Phase 1: CLI Modifications

### Step 1.1: Add Command-Line Argument
**File:** `src/cli.py`

**Changes:**
```python
# In parse_args() function, add after line 85:
parser.add_argument(
    '--filter-func',
    type=str,
    default=None,
    metavar='FUNCTION',
    help='Filter graph to show only functions reachable from FUNCTION. '
         'Use qualified_name (e.g., "Namespace::function_name(int, int)"). '
         'Generates filegraph_<FUNCTION>.json and .html.'
)
```

**Rationale:**
- Follows existing pattern (see `--filter-cfg` and `--simple-db-path`)
- Provides clear help text with example
- Default is None (disabled by default)

---

## Phase 2: Filter Logic Implementation

### 编码要求 (Coding Requirements)

**类型注解规则 (Type Annotation Rules)**

所有代码必须通过 `mypy --strict` 检查，遵循以下规则：

1. **所有局部变量必须显式类型注解**
   ```python
   # ❌ 错误：缺少类型注解
   name_map = {}
   file_functions = {}
   file_to_id = {}

   # ✅ 正确：显式类型注解
   name_map: Dict[str, List[int]] = {}
   file_functions: Dict[str, List[Dict[str, Any]]] = {}
   file_to_id: Dict[str, int] = {}
   ```

2. **返回类型必须具体，不能是模糊类型**
   ```python
   # ❌ 错误：过于模糊
   def get_data() -> Dict[str, Dict]:
       ...

   # ✅ 正确：具体类型
   def get_data() -> Dict[str, Dict[str, Any]]:
       ...

   # ✅ 更好：明确结构
   FunctionDict = Dict[str, Any]  # 'index', 'self', 'parents', 'children'
   def get_data() -> Dict[str, FunctionDict]:
       ...
   ```

3. **所有泛型类型必须指定完整参数**
   ```python
   # ❌ 错误：缺少泛型参数
   from typing import Dict, List
   my_dict: Dict = {}
   my_list: List = []

   # ✅ 正确：完整泛型参数
   from typing import Dict, List, Set, Tuple
   my_dict: Dict[str, int] = {}
   my_list: List[int] = []
   my_set: Set[str] = set()
   my_tuple: Tuple[int, str, bool] = (1, "foo", True)
   ```

4. **使用类型别名提高可读性**
   ```python
   from typing import Dict, List, TypedDict

   # 定义明确的类型结构
   class FunctionSelfInfo(TypedDict):
       qualified_name: str
       path: str
       line: List[int]

   class FunctionDict(TypedDict):
       index: int
       self: FunctionSelfInfo
       parents: List[int]
       children: List[int]

   # 在函数签名中使用类型别名
   def __init__(self, functions: List[FunctionDict]) -> None:
       ...

   def filter_by_function(self, target_name: str) -> List[FunctionDict]:
       ...
   ```

5. **所有方法必须注解参数和返回值**
   ```python
   # ❌ 错误：缺少返回类型注解
   def process(self, data: List[int]):
       ...

   # ✅ 正确：完整的类型注解
   def process(self, data: List[int]) -> List[int]:
       ...

   # ✅ 无返回值时使用 None
   def log_message(self, message: str) -> None:
       ...
   ```

### Step 2.1: Create Graph Filter Class
**File:** `src/graph_filter.py` (new file)

**Purpose:** Encapsulate graph filtering logic

**Class Design:**
```python
from typing import Dict, List, Set, Tuple, Any
from collections import deque


class GraphFilter:
    """Filter function call graph to include only reachable nodes from a target function."""

    def __init__(self, functions: List[Dict[str, Any]]) -> None:
        """
        Initialize filter with full graph data.

        Args:
            functions: List of function dictionaries from JSON output
                       Each has 'index', 'self', 'parents', 'children' fields
        """
        self.functions: List[Dict[str, Any]] = functions
        # Build quick lookup map: qualified_name -> list of function indices
        self.name_to_indices: Dict[str, List[int]] = self._build_name_map()
        # Build adjacency map for fast traversal
        self.adjacency: Dict[int, Tuple[List[int], List[int]]] = self._build_adjacency_map()

    def filter_by_function(self, target_name: str) -> List[Dict[str, Any]]:
        """
        Filter graph to include only nodes reachable from target function.

        Args:
            target_name: qualified_name of target function

        Returns:
            Filtered list of function dictionaries with re-indexed nodes

        Raises:
            ValueError: If target function not found
        """
        # 1. Find target function indices
        target_indices: List[int] | None = self.name_to_indices.get(target_name)

        if not target_indices:
            raise ValueError(f"Function '{target_name}' not found in graph")

        # 2. Collect all reachable nodes (BFS traversal)
        reachable_indices: Set[int] = self._collect_reachable_nodes(target_indices)

        # 3. Filter and re-index nodes
        filtered_functions: List[Dict[str, Any]] = self._filter_and_reindex(reachable_indices)

        logging.info(f"Filtered graph: {len(filtered_functions)} nodes "
                     f"(from {len(self.functions)} total)")

        return filtered_functions

    def _build_name_map(self) -> Dict[str, List[int]]:
        """Build map from qualified_name to function indices."""
        name_map: Dict[str, List[int]] = {}
        for func in self.functions:
            qname: str = func['self']['qualified_name']
            if qname not in name_map:
                name_map[qname] = []
            name_map[qname].append(func['index'])
        return name_map

    def _build_adjacency_map(self) -> Dict[int, Tuple[List[int], List[int]]]:
        """Build adjacency map for fast graph traversal."""
        adjacency: Dict[int, Tuple[List[int], List[int]]] = {}
        for func in self.functions:
            idx: int = func['index']
            adjacency[idx] = (func['parents'], func['children'])
        return adjacency

    def _collect_reachable_nodes(self, start_indices: List[int]) -> Set[int]:
        """
        Collect all nodes reachable from start indices (both directions).

        Args:
            start_indices: List of starting node indices

        Returns:
            Set of all reachable node indices
        """
        reachable: Set[int] = set()
        queue: deque[int] = deque(start_indices)

        while queue:
            current: int = queue.popleft()

            if current in reachable:
                continue

            reachable.add(current)

            # Get parents and children
            parents: List[int]
            children: List[int]
            parents, children = self.adjacency.get(current, ([], []))

            # Add parents (who calls this function)
            for parent in parents:
                if parent not in reachable:
                    queue.append(parent)

            # Add children (functions called by this function)
            for child in children:
                if child not in reachable:
                    queue.append(child)

        return reachable

    def _filter_and_reindex(self, keep_indices: Set[int]) -> List[Dict[str, Any]]:
        """
        Filter functions to keep only those in keep_indices and re-index them.

        Args:
            keep_indices: Set of function indices to keep

        Returns:
            List of filtered function dictionaries with new indices
        """
        # Create old_index -> new_index mapping
        index_mapping: Dict[int, int] = {
            old_idx: new_idx
            for new_idx, old_idx in enumerate(sorted(keep_indices))
        }

        filtered: List[Dict[str, Any]] = []

        for func in self.functions:
            old_idx: int = func['index']
            if old_idx not in keep_indices:
                continue

            # Create new function entry
            new_func: Dict[str, Any] = {
                'index': index_mapping[old_idx],
                'self': func['self'],
                'parents': [index_mapping[p] for p in func['parents'] if p in keep_indices],
                'children': [index_mapping[c] for c in func['children'] if c in keep_indices]
            }

            filtered.append(new_func)

        # Sort by new index
        filtered.sort(key=lambda f: f['index'])

        return filtered
```

**Rationale:**
- Encapsulates filter logic in a separate class (Single Responsibility Principle)
- Uses BFS traversal (iterative, no recursion stack issues)
- Builds lookup maps for O(1) performance
- Re-indexes nodes to maintain JSON structure consistency

---

## Phase 3: CLI Integration

### Step 3.1: Modify main() Flow
**File:** `src/cli.py`

**Changes:**
```python
# After JSON emission (around line 260), add filter logic:

# Step 4: Apply filter if --filter-func is specified
if args.filter_func:
    logging.info(f"Filtering graph by function: {args.filter_func}")

    # Load JSON if not already in memory
    if not functions_dict:
        with open(json_path, 'r', encoding='utf-8') as f:
            functions_dict = json_lib.load(f)

    # Apply filter
    from .graph_filter import GraphFilter
    filter_obj = GraphFilter(functions_dict)
    try:
        filtered_functions = filter_obj.filter_by_function(args.filter_func)

        # Generate filtered output files
        filter_base_name = _sanitize_function_name(args.filter_func)
        if args.format == 'json':
            filter_json_path = output_paths['json']  # Use specified output
        else:
            filter_json_path = Path(f"filegraph_{filter_base_name}.json")

        logging.info(f"Writing filtered JSON to {filter_json_path}")
        with open(filter_json_path, 'w', encoding='utf-8') as f:
            json_lib.dump(filtered_functions, f, indent=2, ensure_ascii=False)

        # Generate filtered HTML
        file_gen = FileGraphGenerator(
            functions=filtered_functions,
            target_function=args.filter_func,  # New parameter
            logger=logger
        )
        filter_html_path = filter_json_path.with_suffix('.html')
        html_content = file_gen.generate_html()
        write_html_file(html_content, str(filter_html_path))
        logging.info(f"Filtered HTML output: {filter_html_path}")

        # Update output paths for summary
        output_paths['json'] = filter_json_path
        output_paths['html'] = filter_html_path

    except ValueError as e:
        logging.error(str(e))
        return 1
```

**Helper Function:**
```python
def _sanitize_function_name(func_name: str) -> str:
    """
    Sanitize function name for use in filename.

    Args:
        func_name: Function qualified_name

    Returns:
        Sanitized string safe for filename
    """
    # Replace unsafe characters
    unsafe = ['/', '\\', ':', '*', '?', '"', '<', '>', '|', '(', ')', ',', ' ']
    sanitized = func_name
    for char in unsafe:
        sanitized = sanitized.replace(char, '_')
    return sanitized
```

**Rationale:**
- Minimal changes to existing flow
- Reuses existing FileGraphGenerator with new parameter
- Proper error handling for missing function
- Sanitizes function names for filename safety

---

## Phase 4: HTML Visualization Updates

### Step 4.1: Add Target Function Parameter
**File:** `src/file_graph_generator.py`

**Changes:**
```python
from typing import Dict, List, Optional, Any
import logging


def __init__(self,
             functions: List[Dict[str, Any]],
             target_function: Optional[str] = None,  # New parameter
             logger: Optional[logging.Logger] = None) -> None:
    """
    Initialize file graph generator.

    Args:
        functions: List of function dictionaries
        target_function: Optional qualified_name of target function to highlight
        logger: Optional logger instance
    """
    self.functions: List[Dict[str, Any]] = functions
    self.target_function: Optional[str] = target_function  # Store target function
    self.logger: logging.Logger = logger or logging.getLogger(__name__)

    # Rebuild relationships
    self.relationships: Dict[int, Tuple[List[int], List[int]]] = {
        func['index']: (func['parents'], func['children'])
        for func in functions
    }

    # Build function name map
    self.name_map: Dict[str, Dict[str, Any]] = {
        func['self']['qualified_name']: func
        for func in functions
    }
```

### Step 4.2: Add Target Indicator to Nodes
**File:** `src/file_graph_generator.py`

**Changes:**
```python
from pathlib import Path
from typing import Dict, List, Set

# In _create_file_nodes method, add target check:
def _create_file_nodes(self) -> List[Dict[str, Any]]:
    """Create file nodes from function data."""
    # Group functions by file path
    file_functions: Dict[str, List[Dict[str, Any]]] = {}

    for func in self.functions:
        file_path: str = func['self']['path']
        if file_path not in file_functions:
            file_functions[file_path] = []
        file_functions[file_path].append(func)

    # Build file relationships
    file_relationships: Dict[str, Dict[str, Any]] = self._build_file_relationships()

    # Assign file IDs
    file_to_id: Dict[str, int] = {}
    current_id: int = 0

    nodes: List[Dict[str, Any]] = []

    for file_path, funcs in file_functions.items():
        file_id: int = current_id
        current_id += 1
        file_to_id[file_path] = file_id

        file_name: str = Path(file_path).name

        # ... existing code ...

        # Check if target function is in this file
        is_target_file: bool = False
        if self.target_function:
            for func in funcs:
                if func['self']['qualified_name'] == self.target_function:
                    is_target_file = True
                    break

        node: Dict[str, Any] = {
            'id': file_id,
            'name': file_name,
            'path': file_path,
            'functionCount': file_relationships[file_path]['function_count'],
            'outgoingCount': outgoing_count,
            'incomingCount': incoming_count,
            'callDetails': '<br/>'.join(call_details) if call_details else '',
            'isTarget': is_target_file  # New field
        }

        nodes.append(node)

    return nodes
```

### Step 4.3: Update JavaScript to Highlight Target
**File:** `src/file_graph_generator.py`

**Changes:**
```python
# In APP_SCRIPT_TEMPLATE, modify initGraph function:
function initGraph() {
  const container = document.getElementById('graph-container');
  chart = echarts.init(container);

  // Store original data
  originalNodes = [...GRAPH_DATA.nodes];
  originalEdges = [...GRAPH_DATA.edges];
  visibleNodes = [...originalNodes];
  visibleEdges = [...originalEdges];

  // Highlight target nodes
  const option = {
    title: {
      text: 'File Call Graph',
      left: 'center',
      top: 10
    },
    tooltip: {
      formatter: tooltipFormatter
    },
    series: [{
      type: 'graph',
      layout: 'force',
      data: visibleNodes.map(node => ({
        ...node,
        itemStyle: node.isTarget ? {
          color: '#ff0000',  // Red for target
          borderColor: '#000000',
          borderWidth: 3
        } : {
          color: node.category ? getNodeColor(node.category) : '#7f7f7f'
        }
      })),
      // ... rest of existing config ...
    }]
  };

  chart.setOption(option);
}
```

**Helper Function:**
```javascript
function getNodeColor(category) {
  const colorMap = {
    'Control': '#ff7f0e',
    'Network': '#2ca02c',
    'Data': '#1f77b4',
    'Utility': '#9467bd',
    'System': '#d62728',
    'Default': '#7f7f7f'
  };
  return colorMap[category] || '#7f7f7f';
}
```

**Rationale:**
- Minimal changes to HTML generation
- Uses `isTarget` flag for styling
- Visual highlight (red color + border) makes target obvious

---

## Phase 5: Testing

### Step 5.1: Unit Tests
**File:** `tests/test_graph_filter.py` (new file)

**Test Cases:**
```python
import pytest
from src.graph_filter import GraphFilter


def test_filter_by_function():
    """Test basic filtering functionality."""
    # Test data setup
    functions = [
        {
            'index': 0,
            'self': {'qualified_name': 'main', 'path': '/a/main.cpp', 'line': [1, 10]},
            'parents': [],
            'children': [1, 2]
        },
        {
            'index': 1,
            'self': {'qualified_name': 'foo', 'path': '/b/foo.cpp', 'line': [1, 5]},
            'parents': [0],
            'children': [2]
        },
        {
            'index': 2,
            'self': {'qualified_name': 'bar', 'path': '/c/bar.cpp', 'line': [1, 5]},
            'parents': [0, 1],
            'children': []
        }
    ]

    filter_obj = GraphFilter(functions)

    # Filter from main
    result = filter_obj.filter_by_function('main')

    # All nodes should be included (main -> foo, bar; foo -> bar)
    assert len(result) == 3

    # Check re-indexing
    assert result[0]['index'] == 0
    assert result[1]['index'] == 1
    assert result[2]['index'] == 2


def test_filter_not_found():
    """Test error when function not found."""
    functions = [
        {
            'index': 0,
            'self': {'qualified_name': 'foo', 'path': '/a/foo.cpp', 'line': [1, 5]},
            'parents': [],
            'children': []
        }
    ]

    filter_obj = GraphFilter(functions)

    with pytest.raises(ValueError, match="Function 'nonexistent' not found"):
        filter_obj.filter_by_function('nonexistent')


def test_filter_single_node():
    """Test filtering from isolated node."""
    functions = [
        {
            'index': 0,
            'self': {'qualified_name': 'isolated', 'path': '/a/iso.cpp', 'line': [1, 5]},
            'parents': [],
            'children': []
        }
    ]

    filter_obj = GraphFilter(functions)
    result = filter_obj.filter_by_function('isolated')

    assert len(result) == 1
    assert result[0]['self']['qualified_name'] == 'isolated'


def test_filter_reindexing():
    """Test that indices are correctly re-indexed."""
    functions = [
        {
            'index': 5,  # Non-zero start
            'self': {'qualified_name': 'start', 'path': '/a/start.cpp', 'line': [1, 5]},
            'parents': [],
            'children': [10]
        },
        {
            'index': 10,
            'self': {'qualified_name': 'end', 'path': '/b/end.cpp', 'line': [1, 5]},
            'parents': [5],
            'children': []
        }
    ]

    filter_obj = GraphFilter(functions)
    result = filter_obj.filter_by_function('start')

    # Should be re-indexed to 0, 1
    assert result[0]['index'] == 0
    assert result[1]['index'] == 1
    assert result[0]['children'] == [1]
    assert result[1]['parents'] == [0]
```

### Step 5.2: Integration Tests
**File:** `tests/test_cli_filter.py` (new file)

**Test Cases:**
```python
import pytest
import subprocess
import json
from pathlib import Path


def test_filter_cli_argument():
    """Test that --filter-func is recognized."""
    result = subprocess.run(
        ['python', '-m', 'src.cli', '--help'],
        capture_output=True,
        text=True
    )
    assert '--filter-func' in result.stdout


@pytest.mark.integration
def test_filter_with_real_project():
    """Test filtering with a real project (requires compile_commands.json)."""
    # This test requires a real project in /path/to/project
    result = subprocess.run(
        [
            'python', '-m', 'src.cli',
            '--input', '/path/to/project/compile_commands.json',
            '--format', 'json',
            '--filter-func', 'main',
            '--output', '/tmp/test_filter.json'
        ],
        capture_output=True,
        text=True
    )

    assert result.returncode == 0
    assert Path('/tmp/test_filter.json').exists()

    # Verify output is valid JSON
    with open('/tmp/test_filter.json') as f:
        data = json.load(f)
        assert isinstance(data, list)
```

### Step 5.3: Manual Testing Checklist
- [ ] Run with `--filter-func "main"` on sample project
- [ ] Verify output files exist
- [ ] Open HTML and check visualization
- [ ] Verify target function is highlighted (red)
- [ ] Test with non-existent function (should error)
- [ ] Test without `--filter-func` (full graph, backward compatible)
- [ ] Test with `--format json` only
- [ ] Test with `--format html`
- [ ] Test with custom `--output` path

---

## Phase 6: Documentation

### Step 6.1: Update README.md
**File:** `README.md`

**Add Section:**
```markdown
## Filtering the Graph

To generate a subgraph containing only functions reachable from a specific function:

```bash
python -m src.cli --filter-func "Namespace::function_name(int, int)" --format html
```

This generates two files:
- `filegraph_Namespace__function_name_int__int_.json` - Filtered JSON data
- `filegraph_Namespace__function_name_int__int_.html` - Interactive HTML visualization

The subgraph includes:
- The target function
- All functions that call the target function (upward traversal)
- All functions called by the target function (downward traversal)
- All functions reachable through these connections (recursive)

### Example

```bash
# Analyze code with a filter on main function
python -m src.cli --filter-func "main" --format html

# Output files:
# - filegraph_main.json
# - filegraph_main.html
```
```

### Step 6.2: Update USAGE.md
**File:** `USAGE.md`

**Add Example:**
```markdown
## Advanced Usage: Function-Level Filtering

### View Call Graph for Specific Function

Generate a subgraph showing only functions related to a specific function:

```bash
python -m src.cli \
  --filter-func "ButtonDriver::init" \
  --format html \
  --output button_driver_graph
```

This helps focus on a specific feature or component.

### Notes
- Use the full qualified name (namespace included)
- The subgraph includes all caller and callee functions
- Target function is highlighted in red in the visualization
```

---

## Implementation Order

### Sprint 1: Core Logic (Week 1)
1. ✅ Phase 1: CLI argument
2. ✅ Phase 2: GraphFilter class
3. ✅ Phase 3: CLI integration
4. ✅ Phase 5.1: Unit tests

### Sprint 2: Visualization (Week 1-2)
5. ✅ Phase 4: HTML updates
6. ✅ Phase 5.2: Integration tests
7. ✅ Phase 6: Documentation

### Sprint 3: Testing & Polish (Week 2)
8. ✅ Phase 5.3: Manual testing
9. ✅ Fix bugs and edge cases
10. ✅ Code review and cleanup

---

## Risk Assessment

### High Risk Items
1. **Performance on Large Graphs**
   - Risk: BFS traversal may be slow for 1000+ nodes
   - Mitigation: Use iterative BFS (not recursive), build lookup maps upfront
   - Test: Benchmark with real-world projects

2. **HTML Rendering Complexity**
   - Risk: Target highlighting may break existing visualization
   - Mitigation: Minimal changes, test thoroughly
   - Rollback: Keep original logic as fallback

### Medium Risk Items
3. **Backward Compatibility**
   - Risk: Changes may break existing workflows
   - Mitigation: Default behavior unchanged, add tests
   - Validation: Run existing test suite

4. **Edge Cases**
   - Risk: Empty filtered graph, circular dependencies
   - Mitigation: Add proper error handling, test edge cases
   - Validation: Unit tests for edge cases

### Low Risk Items
5. **Documentation Updates**
   - Risk: Outdated examples
   - Mitigation: Test all examples before publishing

---

## Success Metrics

### Functional Metrics
- [ ] `--filter-func` argument works as specified
- [ ] Filtered graphs are correct (verified with unit tests)
- [ ] HTML visualization highlights target function
- [ ] No regressions in existing functionality
- [ ] All tests pass (new and existing)

### Performance Metrics
- [ ] Filter operation completes in < 5 seconds for 1000-node graphs
- [ ] Memory usage increase < 20% compared to full graph generation

### Quality Metrics
- [ ] Code coverage > 80% for new code
- [ ] No lint errors or warnings
- [ ] Documentation is clear and complete

---

## Future Enhancements (Out of Scope for V1)

### Potential Improvements
1. Support regex pattern matching for function names
2. Support multiple target functions (comma-separated)
3. Add depth limit option (`--max-depth`)
4. Add direction filter (`--direction up|down|both`)
5. Export filtered graph to other formats (Graphviz DOT)
6. Add web UI for interactive filtering

### Backlog Items
- Implement fuzzy matching for function names
- Add visualization of traversal depth
- Support filtering by file path
- Add statistics page for filtered graph

---

## Rollout Plan

### Phase 1: Development
- Implement core features (Sprints 1-2)
- Run tests locally
- Fix bugs and edge cases

### Phase 2: Code Review
- Submit for review
- Address feedback
- Finalize implementation

### Phase 3: Release
- Update version number
- Update CHANGELOG.md
- Release as patch/minor version (depending on impact)

### Phase 4: Monitoring
- Watch for bug reports
- Gather user feedback
- Plan future enhancements

---

## Notes

- All new code should follow PEP 8 style guidelines
- **Type annotations must pass `mypy --strict` - no exceptions**
- All local variables must have explicit type annotations (e.g., `var: Type = value`)
- Return types must be specific, not vague (e.g., `Dict[str, Dict[str, Any]]` not `Dict[str, Dict]`)
- All generic types must specify full parameters (e.g., `Dict[str, int]` not `Dict`)
- Add docstrings following Google style
- Keep functions small and focused (< 50 lines)
- Avoid premature optimization; measure first
- Test with real-world projects before release

### Type Annotation Checklist

Before submitting any code:

- [ ] All local variables have explicit type annotations
- [ ] All function/method signatures include parameter and return types
- [ ] All used typing types are explicitly imported (Optional, List, Dict, Tuple, Set, Any, etc.)
- [ ] No variable re-declaration in the same scope - use conditional assignment or different names
- [ ] No bare `Dict`, `List`, `Set`, `Tuple` - all have type parameters
- [ ] No `Dict[str, Dict]` or similar vague types - use specific types or TypedDict
- [ ] Code passes `mypy --strict` with zero errors
- [ ] Optional types use `Optional[T]` or `T | None` (Python 3.10+)
