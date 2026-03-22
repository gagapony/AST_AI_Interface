# clang-call-analyzer 数据流架构分析报告

**项目**: clang-call-analyzer
**作者**: Architect (Leo)
**日期**: 2026-03-21
**任务**: 分析数据流是否符合严格的阶段链要求

---

## 执行摘要

**结论**: 当前实现**不符合**严格的阶段链要求。

**核心问题**:
1. ❌ **compile_commands.json → compile_commands_simple.json**: 断链
2. ⚠️ **compile_commands_simple.json → callgraph.json**: 数据流不清晰
3. ✅ **callgraph.json → callgraph.html**: 正常

**关键发现**:
- `compile_commands_simple.json` 生成是**可选的**（需要 `--dump-simple-db` 参数）
- AST 解析使用**内存中的 simplified_units**，而不是从文件读取
- 无法支持真正的分阶段运行（每个阶段独立运行并读取上一阶段输出）

---

## 1. 严格数据流链要求

根据需求，正确的数据流应该是：

```
compile_commands.json
    ↓ (Stage 1: 简化编译数据库)
    ↓ 仅读取 compile_commands.json
    ↓
compile_commands_simple.json
    ↓ (Stage 2: 生成调用关系)
    ↓ 仅读取 compile_commands_simple.json
    ↓
callgraph.json
    ↓ (Stage 3: 生成可视化)
    ↓ 仅读取 callgraph.json
    ↓
callgraph.html
```

**每个阶段的限制**:
- Stage 1: **只能读取** `compile_commands.json`，**必须输出** `compile_commands_simple.json`
- Stage 2: **只能读取** `compile_commands_simple.json`，**必须输出** `callgraph.json`
- Stage 3: **只能读取** `callgraph.json`，**必须输出** `callgraph.html`

---

## 2. 当前实现分析

### 2.1 cli.py 主流程

**代码位置**: `src/cli.py` (main 函数，第 113-242 行)

**当前数据流**:

```python
# Step 1: 加载原始 compile_commands.json
comp_db = CompilationDatabase(str(db_path))
units = comp_db.get_units()

# Step 2: 生成 simplified_units (内存中)
simplifier = CompileCommandsSimplifier(filter_paths=filter_paths, logger=logger)
simplified_units, simple_db_stats = simplifier.simplify_units(units)

# Step 2.1: 可选导出到文件 (仅在 --dump-simple-db 时)
if args.dump_simple_db:
    simplifier.dump_to_file(simplified_units, args.dump_simple_db)

# Step 3: 使用内存中的 simplified_units 进行解析
units_to_parse = simplified_units  # ← 关键：使用内存数据，而非文件

for unit in units_to_parse:
    # ... AST 解析 ...

# Step 4: 生成 callgraph.json
if args.format == 'json':
    emitter = JSONEmitter(str(output_paths['json']))
    emitter.emit(functions_to_emit, relationships_to_emit)

# Step 5: 如果 format=html，从 callgraph.json 生成 HTML
if args.format == 'html':
    # 先生成 JSON
    json_path = Path(...)
    emitter = JSONEmitter(str(json_path))
    emitter.emit(functions_to_emit, relationships_to_emit)

    # 再从 JSON 生成 HTML
    with open(json_path, 'r', encoding='utf-8') as f:
        functions_dict = json_lib.load(f)

    file_gen = FileGraphGenerator(
        functions=functions_dict,
        relationships=relationships_to_emit,
        logger=logger
    )
    html_content = file_gen.generate_html()
    write_html_file(html_content, str(output_paths['html']))
```

### 2.2 关键问题详细分析

#### 问题 1: compile_commands_simple.json 不是强制输出

**位置**: `src/cli.py` 第 156-161 行

```python
# Export simplified DB if --dump-simple-db is specified
if args.dump_simple_db:
    logging.info(f"Exporting simplified compile commands to {args.dump_simple_db}")
    simplifier.dump_to_file(simplified_units, args.dump_simple_db)
```

**问题**:
- `compile_commands_simple.json` 文件只有在 `--dump-simple-db` 参数时才写入
- 默认情况下，simplified_units 只存在于内存中
- 无法直接使用 `compile_commands_simple.json` 作为下一阶段的输入

**影响**:
- ❌ 无法分阶段运行
- ❌ 无法调试中间结果
- ❌ 违反"必须输出"的要求

---

#### 问题 2: AST 解析使用内存数据而非文件

**位置**: `src/cli.py` 第 163-164 行

```python
# Parse with simplified units
units_to_parse = simplified_units  # ← 关键：使用内存数据
logging.info(f"Parsing {len(units_to_parse)} simplified compilation units")
```

**问题**:
- AST 解析直接使用 `simplified_units`（内存中的对象列表）
- 没有代码从 `compile_commands_simple.json` 文件读取并重新创建 `CompilationUnit` 对象
- 即使 `compile_commands_simple.json` 存在，也不会被使用

**影响**:
- ❌ 无法独立运行 Stage 2（需要先运行 Stage 1 并保持内存状态）
- ❌ 无法支持管道模式（文件级数据流）
- ❌ 违反"只能读取前一个阶段的输出"的要求

**证据**:
查看 `src/cli.py`，没有任何代码从 `compile_commands_simple.json` 读取数据。
唯一的文件读取是：
1. `compile_commands.json` (line 124)
2. `filter.cfg` (line 139)
3. `callgraph.json` (line 211, 用于 HTML 生成)

没有读取 `compile_commands_simple.json` 的代码。

---

#### 问题 3: 依赖关系混乱

**当前依赖关系**:

```
compile_commands.json (读取)
    ↓
simplified_units (内存对象)
    ├─→ compile_commands_simple.json (可选写入)
    └─→ AST 解析 (使用内存对象)
           ↓
       callgraph.json (写入)
           ↓
       callgraph.html (从 callgraph.json 读取)
```

**正确的依赖关系**:

```
compile_commands.json (读取)
    ↓
compile_commands_simple.json (写入)
    ↓ (读取)
AST 解析
    ↓
callgraph.json (写入)
    ↓ (读取)
HTML 生成
    ↓
callgraph.html (写入)
```

**问题**:
- Stage 2 (AST 解析) 依赖内存中的 `simplified_units`，而不是文件 `compile_commands_simple.json`
- 这破坏了严格的阶段链

---

### 2.3 Stage 3 (HTML 生成) 分析

**位置**: `src/cli.py` 第 204-227 行

```python
# Step 3: Generate HTML (always from JSON file)
if args.format == 'html':
    logging.info("Generating file-level HTML graph from JSON...")
    if not json_path:
        logging.error("JSON path not available for HTML generation")
        return 1

    # Load JSON
    with open(json_path, 'r', encoding='utf-8') as f:
        functions_dict = json_lib.load(f)

    # Remove temporary JSON file if it was temporary
    if 'call_graph_temp.json' in str(json_path):
        os.remove(json_path)
        logging.info(f"Removed temporary JSON file: {json_path}")

    # Generate HTML from JSON using FileGraphGenerator
    file_gen = FileGraphGenerator(
        functions=functions_dict,  # ← 从 JSON 读取
        relationships=relationships_to_emit,  # ← 但 relationships 来自内存！
        logger=logger
    )
    html_content = file_gen.generate_html()
    write_html_file(html_content, str(output_paths['html']))
```

**问题**:
- `functions_dict` 从 JSON 文件读取 ✅
- `relationships_to_emit` 从内存传递 ❌

这是一个**混用问题**：
- HTML 生成同时使用了文件数据 (`functions_dict`) 和内存数据 (`relationships_to_emit`)
- 如果要独立运行 Stage 3，需要 `callgraph.json` 同时包含 `functions` 和 `relationships`

**查看 callgraph.json 格式**:

```python
# src/json_emitter.py (emit 方法)
for func in functions:
    parents, children = relationships.get(func_index, ([], []))

    output_entry = FunctionOutput(
        index=func_index,
        self=self_data,
        parents=parents,  # ← 包含在 JSON 中
        children=children  # ← 包含在 JSON 中
    )
```

✅ `callgraph.json` 确实包含 `parents` 和 `children`（relationships）

**但 FileGraphGenerator 的问题**:

```python
# src/file_graph_generator.py (构造函数)
def __init__(self,
             functions: List[Dict],
             relationships: Dict[int, Tuple[List[int], List[int]]],
             logger: Optional[logging.Logger] = None):
    self.functions = functions
    self.relationships = relationships  # ← 为什么需要这个？
```

查看 `_build_file_relationships` 方法：

```python
def _build_file_relationships(self,
                               file_functions: Dict[str, List[Dict]],
                               functions: List[Dict]) -> Dict[str, Dict]:
    # ...

    # Process each function's calls
    for func in functions:
        func_idx = func['index']
        source_file = func['self']['path']
        func_name = func['self']['name']
        line_range = func['self']['line']

        # Get children (functions this function calls)
        parents, children = self.relationships.get(func_idx, ([], []))  # ← 使用 relationships

        for child_idx in children:
            # ...
```

**发现**:
- `FileGraphGenerator` 需要从 `relationships` 构建文件级调用关系
- 但这个 `relationships` 应该可以从 `functions` 数据中重建（每个 function 都有 `parents` 和 `children`）
- 当前实现传入内存中的 `relationships_to_emit`，而不是从 JSON 重建

**问题**:
- 如果只传入 `functions`（来自 JSON），`FileGraphGenerator` 应该能够自行重建 `relationships`
- 当前混用了 JSON 数据和内存数据
- 违反"仅读取前一个阶段的输出"的要求

---

## 3. 阶段跳过检查

### 3.1 是否存在阶段跳过？

**检查**: Stage 2 是否跳过了 `compile_commands_simple.json`？

**答案**: ✅ **是的，存在阶段跳过**

**证据**:
1. Stage 2 (AST 解析) 直接使用内存中的 `simplified_units`
2. 不需要 `compile_commands_simple.json` 文件存在
3. 即使文件不存在，解析仍然正常工作

**代码路径**:
```python
# src/cli.py
# 读取 compile_commands.json
comp_db = CompilationDatabase(str(db_path))

# 生成 simplified_units (内存)
simplified_units = simplifier.simplify_units(units)

# 直接使用内存数据进行 AST 解析
units_to_parse = simplified_units
for unit in units_to_parse:
    # ... 解析 ...
```

**违反要求**:
- 要求: Stage 2 只能读取 `compile_commands_simple.json`
- 实际: Stage 2 读取的是内存中的 `simplified_units`（来自 Stage 1）

---

### 3.2 是否存在直接跳到 Stage 2？

**检查**: 是否有代码直接从 `compile_commands.json` 跳到生成 `callgraph.json`？

**答案**: ❌ **不存在直接跳过**

**分析**:
- 代码总是先生成 `simplified_units`
- 没有代码跳过简化步骤
- 但这不是真正的分阶段，而是在一次运行中完成

**问题**:
- 虽然没有完全跳过简化步骤，但数据流不是文件级的
- 无法在不运行 Stage 1 的情况下运行 Stage 2

---

## 4. 阶段混用检查

### 4.1 Stage 3 是否混用了 Stage 2 的数据？

**答案**: ✅ **是的，存在阶段混用**

**证据**:

```python
# src/cli.py (HTML 生成)
# 从 JSON 读取 functions
with open(json_path, 'r', encoding='utf-8') as f:
    functions_dict = json_lib.load(f)

# 但从内存传入 relationships
file_gen = FileGraphGenerator(
    functions=functions_dict,  # ← 来自 JSON (Stage 2 输出)
    relationships=relationships_to_emit,  # ← 来自内存 (Stage 2 内部状态)
    logger=logger
)
```

**问题**:
- Stage 3 应该只读取 `callgraph.json`
- 当前同时使用了 `callgraph.json` 数据和内存中的 `relationships`
- 这意味着无法独立运行 Stage 3（需要 Stage 2 的内存状态）

---

### 4.2 生成 HTML 时是否重新分析？

**检查**: HTML 生成时是否重新调用 AST 解析或调用分析？

**答案**: ❌ **没有重新分析**

**分析**:
- HTML 生成从 JSON 读取数据
- 没有重新调用 `ASTParser`、`FunctionExtractor`、`CallAnalyzer` 等
- 只是进行数据转换（function → file-level graph）

**但问题**:
- `FileGraphGenerator` 仍然依赖内存中的 `relationships` 参数
- 应该能够从 JSON 中的 `parents`/`children` 字段重建这个数据结构

---

## 5. 数据流链对比

### 5.1 要求的数据流链

```
Stage 1: simplify
  输入: compile_commands.json
  输出: compile_commands_simple.json
  限制: 只能读取 compile_commands.json

Stage 2: analyze
  输入: compile_commands_simple.json
  输出: callgraph.json
  限制: 只能读取 compile_commands_simple.json

Stage 3: visualize
  输入: callgraph.json
  输出: callgraph.html
  限制: 只能读取 callgraph.json
```

### 5.2 当前的数据流链

```
Stage 1 + 2 + 3 (混合运行)
  输入: compile_commands.json
  内部数据: simplified_units (内存)
  内部数据: functions + relationships (内存)
  输出: callgraph.json (如果 format=json)
  输出: callgraph.html (如果 format=html，使用部分 JSON + 部分内存数据)
```

**关键差异**:
1. ❌ `compile_commands_simple.json` 不是强制输出
2. ❌ Stage 2 不读取文件，而是使用内存数据
3. ❌ Stage 3 混用了文件和内存数据

---

## 6. 详细问题清单

### 6.1 Stage 1 → Stage 2

| 检查项 | 要求 | 实际 | 状态 |
|--------|------|------|------|
| Stage 1 输入 | 读取 compile_commands.json | ✅ 读取 | ✅ |
| Stage 1 输出 | 写入 compile_commands_simple.json | ❌ 可选 (--dump-simple-db) | ❌ |
| Stage 2 输入 | 读取 compile_commands_simple.json | ❌ 读取内存中的 simplified_units | ❌ |
| Stage 2 输出 | 写入 callgraph.json | ✅ 写入 | ✅ |

### 6.2 Stage 2 → Stage 3

| 检查项 | 要求 | 实际 | 状态 |
|--------|------|------|------|
| Stage 3 输入 | 读取 callgraph.json | ⚠️ 部分读取 (functions) | ⚠️ |
| Stage 3 额外输入 | ❌ 不应依赖内存数据 | ❌ 依赖内存中的 relationships | ❌ |
| Stage 3 输出 | 写入 callgraph.html | ✅ 写入 | ✅ |

### 6.3 文件读取检查

**Stage 1 读取**:
- ✅ `compile_commands.json` (line 124)

**Stage 2 读取**:
- ❌ **没有读取任何文件** (使用内存中的 `simplified_units`)

**Stage 3 读取**:
- ✅ `callgraph.json` (line 211)
- ⚠️ **额外依赖**: 内存中的 `relationships_to_emit` (line 219)

---

## 7. 根本原因分析

### 7.1 为什么 compile_commands_simple.json 不是强制输出？

**原因**:
- 设计意图是性能优化，而不是独立的阶段
- `--dump-simple-db` 被视为调试工具
- 主流程假设所有阶段在同一运行中完成

**影响**:
- 无法支持真正的管道模式
- 无法调试中间结果
- 违反严格的阶段链要求

### 7.2 为什么 Stage 2 不读取文件？

**原因**:
- `CompileCommandsSimplifier.simplify_units()` 返回 `CompilationUnit` 对象列表
- 这些对象可以直接传递给 `ASTParser`
- 没有序列化和反序列化的需求

**影响**:
- Stage 1 和 Stage 2 耦合紧密
- 无法独立运行 Stage 2
- 违反"只能读取前一个阶段的输出"的要求

### 7.3 为什么 Stage 3 混用数据？

**原因**:
- `FileGraphGenerator` 需要 `relationships` 来构建文件级调用图
- 虽然可以从 JSON 的 `parents`/`children` 重建，但当前实现选择直接传入
- 可能是为了性能（避免重建）

**影响**:
- Stage 3 不是完全独立的
- 无法只使用 `callgraph.json` 运行 Stage 3
- 违反"仅读取前一个阶段的输出"的要求

---

## 8. 建议修复方案

### 8.1 短期修复（最小改动）

**目标**: 使数据流符合严格要求，但保持现有代码结构

#### 修复 1: 强制输出 compile_commands_simple.json

**修改**: `src/cli.py`

```python
# 添加参数
parser.add_argument(
    '--stage',
    type=str,
    choices=['simplify', 'analyze', 'visualize', 'all'],
    default='all',
    help='Run specific stage only (default: all)'
)

# 修改 main 函数
def main() -> int:
    # ...

    # Stage 1: 简化编译数据库
    if args.stage in ['simplify', 'all']:
        logging.info("Stage 1: Simplifying compile commands")

        simplifier = CompileCommandsSimplifier(filter_paths=filter_paths, logger=logger)
        simplified_units, simple_db_stats = simplifier.simplify_units(units)

        # 强制输出到文件
        simple_db_path = Path(args.output or 'compile_commands_simple.json')
        logging.info(f"Writing compile_commands_simple.json to {simple_db_path}")
        simplifier.dump_to_file(simplified_units, str(simple_db_path))

        if args.stage == 'simplify':
            return 0  # 只运行 Stage 1
    else:
        # Stage 2 或 3: 从文件读取
        simple_db_path = Path(args.input or 'compile_commands_simple.json')
        if not simple_db_path.exists():
            logging.error(f"compile_commands_simple.json not found at {simple_db_path}")
            return 1

        # 读取简化后的编译数据库
        with open(simple_db_path, 'r', encoding='utf-8') as f:
            simplified_data = json_lib.load(f)

        # 重建 CompilationUnit 对象
        simplified_units = [
            CompilationUnit(
                directory=unit['directory'],
                command=unit['command'],
                file=unit['file'],
                # 需要解析 command 获取 flags
                flags=shlex.split(unit['command'])[1:]  # 简单实现
            )
            for unit in simplified_data
        ]
```

#### 修复 2: 修改 FileGraphGenerator 从 JSON 重建 relationships

**修改**: `src/file_graph_generator.py`

```python
def __init__(self,
             functions: List[Dict],  # 只需要这一个参数
             logger: Optional[logging.Logger] = None):
    """
    Initialize file graph generator.

    Args:
        functions: List of function dictionaries from JSON output
                   Each should have 'parents' and 'children' fields
        logger: Optional logger instance
    """
    self.functions = functions
    self.logger = logger or logging.getLogger(__name__)

    # 从 functions 重建 relationships
    self.relationships = {
        func['index']: (func['parents'], func['children'])
        for func in functions
    }
```

**修改**: `src/cli.py` (HTML 生成部分)

```python
# Step 3: Generate HTML (only from JSON file)
if args.format == 'html':
    logging.info("Generating file-level HTML graph from JSON...")
    if not json_path:
        logging.error("JSON path not available for HTML generation")
        return 1

    # Load JSON
    with open(json_path, 'r', encoding='utf-8') as f:
        functions_dict = json_lib.load(f)

    # 只传入 functions，让 FileGraphGenerator 自行重建 relationships
    file_gen = FileGraphGenerator(
        functions=functions_dict,  # ← 只传入这一个参数
        logger=logger
    )
    html_content = file_gen.generate_html()
    write_html_file(html_content, str(output_paths['html']))
```

---

### 8.2 中期修复（重构数据流）

**目标**: 实现真正的管道模式，支持独立运行每个阶段

#### 设计:

```
# Stage 1: 简化
$ clang-call-analyzer --stage simplify --input compile_commands.json --output compile_commands_simple.json

# Stage 2: 分析
$ clang-call-analyzer --stage analyze --input compile_commands_simple.json --output callgraph.json

# Stage 3: 可视化
$ clang-call-analyzer --stage visualize --input callgraph.json --output callgraph.html

# 或一次性运行所有阶段
$ clang-call-analyzer --stage all --input compile_commands.json --output callgraph.html
```

#### 实现要点:

1. **每个阶段都是独立的可执行单元**
2. **每个阶段只能读取指定的输入文件**
3. **每个阶段必须输出指定的输出文件**
4. **使用 JSON 作为标准中间格式**

---

### 8.3 长期修复（架构重构）

**参考**: `LAYERED_ARCHITECTURE_REPORT.md`

**推荐方案**: 方案 C（统一数据层 + 适配器模式）

**核心改进**:
1. 定义清晰的层间接口
2. 使用适配器模式消除重复代码
3. 支持管道模式和内存模式
4. 保证数据一致性

---

## 9. 测试验证

### 9.1 验证方法

为了验证数据流是否符合严格要求，执行以下测试：

#### 测试 1: 独立运行 Stage 1

```bash
$ clang-call-analyzer --stage simplify --input compile_commands.json --output compile_commands_simple.json

# 验证:
# 1. compile_commands_simple.json 存在
# 2. 内容只包含 -D 和匹配的 -I 标志
# 3. 文件路径已过滤
```

#### 测试 2: 独立运行 Stage 2

```bash
$ clang-call-analyzer --stage analyze --input compile_commands_simple.json --output callgraph.json

# 验证:
# 1. callgraph.json 存在
# 2. 包含所有函数信息和调用关系
# 3. 没有读取任何其他文件
```

#### 测试 3: 独立运行 Stage 3

```bash
$ clang-call-analyzer --stage visualize --input callgraph.json --output callgraph.html

# 验证:
# 1. callgraph.html 存在
# 2. 只读取了 callgraph.json
# 3. 没有访问任何其他数据
```

#### 测试 4: 验证一致性

```bash
# 一次性运行
$ clang-call-analyzer --stage all --input compile_commands.json --output callgraph.html

# 分阶段运行
$ clang-call-analyzer --stage simplify --input compile_commands.json --output simple1.json
$ clang-call-analyzer --stage analyze --input simple1.json --output graph1.json
$ clang-call-analyzer --stage visualize --input graph1.json --output html1.html

# 验证: html1.html 与 callgraph.html 相同
$ diff html1.html callgraph.html
```

### 9.2 当前状态

**测试 1**: ❌ 无法独立运行 Stage 1（没有 `--stage simplify` 选项）

**测试 2**: ❌ 无法独立运行 Stage 2（没有读取 `compile_commands_simple.json` 的代码）

**测试 3**: ⚠️ 部分可运行（但混用了内存数据）

**测试 4**: ❌ 无法验证一致性（无法分阶段运行）

---

## 10. 总结

### 10.1 关键发现

1. **数据流链断链**:
   - ❌ `compile_commands_simple.json` 不是强制输出
   - ❌ Stage 2 不读取文件，而是使用内存数据

2. **阶段混用**:
   - ❌ Stage 3 混用了 JSON 文件和内存数据
   - ❌ 无法独立运行任何阶段

3. **不符合严格要求**:
   - ❌ 违反"每个阶段只能读取前一个阶段的输出"
   - ❌ 违反"每个阶段必须输出到文件"

### 10.2 建议优先级

**高优先级**:
1. 修复 `FileGraphGenerator` 从 JSON 重建 relationships
2. 添加 `--stage` 参数支持独立运行各阶段
3. 强制输出 `compile_commands_simple.json`

**中优先级**:
4. 重构数据流，支持管道模式
5. 添加测试验证数据流正确性
6. 更新文档说明分阶段运行方式

**低优先级**:
7. 考虑长期架构重构（参考 `LAYERED_ARCHITECTURE_REPORT.md`）

---

## 11. 附录

### 11.1 相关文件清单

**核心文件**:
- `src/cli.py`: 主入口，包含数据流逻辑
- `src/compile_commands_simplifier.py`: 编译命令简化
- `src/file_graph_generator.py`: HTML 生成
- `src/json_emitter.py`: JSON 输出

**文档文件**:
- `REQUIREMENTS.md`: 功能需求
- `LAYERED_ARCHITECTURE_REPORT.md`: 分层架构设计建议

### 11.2 数据流对比表

| 阶段 | 要求输入 | 要求输出 | 实际输入 | 实际输出 | 状态 |
|------|----------|----------|----------|----------|------|
| Stage 1 | compile_commands.json | compile_commands_simple.json | compile_commands.json | compile_commands_simple.json (可选) | ❌ |
| Stage 2 | compile_commands_simple.json | callgraph.json | simplified_units (内存) | callgraph.json | ❌ |
| Stage 3 | callgraph.json | callgraph.html | callgraph.json + relationships (内存) | callgraph.html | ⚠️ |

### 11.3 问题严重性评估

| 问题 | 严重性 | 影响范围 | 修复难度 |
|------|--------|----------|----------|
| Stage 1 输出不是强制的 | 高 | 无法分阶段运行 | 低 |
| Stage 2 不读取文件 | 高 | 无法独立运行 Stage 2 | 中 |
| Stage 3 混用数据 | 中 | 无法独立运行 Stage 3 | 低 |
| 缺少 `--stage` 参数 | 中 | 无法选择运行阶段 | 中 |

---

## 12. 签署

**Author**: Leo (Architect)
**Date**: 2026-03-21
**Status**: ✅ Analysis Complete

---

## 下一步行动

请 Linus Reviewer 审阅本报告，确认：

1. ✅ 分析是否准确
2. ✅ 问题是否严重
3. ✅ 建议是否合理
4. ✅ 优先级是否正确

如需补充分析，Architect 将进一步调查。
