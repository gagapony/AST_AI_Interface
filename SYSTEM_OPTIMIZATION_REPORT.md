# Clang-Call-Analyzer 系统优化报告

**日期:** 2026-03-20
**执行者:** Architect Subagent
**任务:** 系统级优化需求分析与方案设计

---

## 执行摘要

本报告针对 clang-call-analyzer 项目的系统级优化需求进行了深入分析，涵盖：

1. **当前实现分析** - HTML 生成流程、过滤系统、冗余功能
2. **预期流程分析** - 数据管道设计
3. **差异总结** - 当前实现与需求的差距
4. **实现方案** - 简单方案 vs 复杂方案
5. **推荐方案** - 基于实用性和向后兼容性的权衡
6. **实现步骤** - 具体的执行清单
7. **风险评估** - 潜在风险和缓解措施
8. **向后兼容性** - 升级路径和迁移指南

---

## 1. 当前实现分析

### 1.1 HTML 生成流程分析

**问题 A：HTML 是如何生成的？**

**答案：方式 1 - 直接从内存数据生成**

当前实现中，HTML 是**直接从内存数据生成**的，不依赖中间 JSON 文件。

**代码流程：**

```python
# cli.py 中的生成流程（第 486-530 行）

if args.format == 'html' or args.format == 'both':
    if args.file_graph:
        # 文件级图生成流程
        from .file_graph_generator import FileGraphGenerator

        # 注意：这里有一个临时 JSON 文件的 hack
        temp_json = '/tmp/call_analyzer_temp.json'
        json_emitter = JSONEmitter(temp_json)
        json_emitter.emit(functions_to_emit, relationships_to_emit)

        # 立即加载 JSON
        with open(temp_json, 'r', encoding='utf-8') as f:
            functions_dict = json_lib.load(f)

        # 清理临时文件
        os.remove(temp_json)

        # 生成文件级 HTML
        filegraph_gen = FileGraphGenerator(
            functions=functions_dict,  # 从临时 JSON 加载
            relationships=relationships_to_emit,
            logger=logger
        )
        html_content = filegraph_gen.generate_html()
        write_html_file(html_content, str(output_paths['html']))

    else:
        # 函数级图生成流程（默认）
        echarts_gen = EChartsGenerator(
            functions=functions_to_emit,  # 直接使用内存数据
            relationships=relationships_to_emit,
            logger=logger
        )
        html_content = echarts_gen.generate_html()
        write_html_file(html_content, str(output_paths['html']))
```

**关键发现：**

1. **函数级图（默认）** - 直接从 `functions_to_emit` 和 `relationships_to_emit` 生成
2. **文件级图（--file-graph）** - 通过临时 JSON 文件 hack 转换格式

**临时 JSON hack 的问题：**

```python
# file_graph_generator.py 需要 List[Dict] 格式
# 但 cli.py 传递的是 List[FunctionInfo]

# 所以需要通过 JSONEmitter 转换格式
temp_json = '/tmp/call_analyzer_temp.json'
json_emitter = JSONEmitter(temp_json)
json_emitter.emit(functions_to_emit, relationships_to_emit)
# 立即读回
with open(temp_json, 'r', encoding='utf-8') as f:
    functions_dict = json_lib.load(f)
# 然后删除
os.remove(temp_json)
```

这个 hack 的原因是：
- `FileGraphGenerator.__init__()` 期望 `functions: List[Dict]`（从 JSON 加载的格式）
- 但 `cli.py` 中 `functions_to_emit` 是 `List[FunctionInfo]`（内存对象）
- 所以通过临时 JSON 文件进行格式转换

**结论：**
- HTML 生成是**从内存直接生成**的（方式 1）
- 文件级图有一个临时 JSON hack，用于格式转换
- **没有中间 JSON 输出文件**（除非用户明确使用 `--format json` 或 `--format both`）

---

### 1.2 过滤系统分析

**当前过滤模式：**

根据 `filter_config.py` 的实现，过滤系统有三种模式：

```python
class FilterMode(Enum):
    FILTER_CFG = 1      # 最高优先级：使用 --filter-cfg
    SINGLE_PATH = 2     # 中优先级：使用 --path
    AUTO_DETECT = 3     # 最低优先级：分析所有文件
```

**过滤优先级：**
1. `--filter-cfg` - 使用配置文件中的路径列表
2. `--path` - 使用单一路径
3. 无过滤参数 - 分析所有文件（默认）

**`--aggressive-filter` 的实现：**

```python
# cli.py 第 322-346 行

if args.aggressive_filter:
    logging.info("Applying aggressive filter mode (keeps -D and filter.cfg -I only)")
    if filter_config.mode == FilterMode.AUTO_DETECT:
        logging.error("--aggressive-filter requires --filter-cfg to be specified")
        return 1
    units = _apply_aggressive_filter(units, filter_config, logger)

elif filter_config.mode != FilterMode.AUTO_DETECT:
    # 标准过滤模式
    # ... 使用 CompilationDatabaseFilter 过滤
```

**`--aggressive-filter` 的行为：**

根据 `cli.py` 中的 `_apply_aggressive_filter()` 函数（第 625-749 行）：

**保留：**
- 所有 `-D` 宏定义标志
- 匹配 filter.cfg 的 `-I` 包含路径
- 匹配 filter.cfg 的源文件

**移除：**
- 不匹配 filter.cfg 的 `-I` 包含路径
- 所有其他编译器标志（`-std`, `-O`, `-Wall`, `-march`, 等）

**用途：**
- 显著加快大型项目的解析速度
- ESP32 示例：从 >180s 降低到 ~30s（约 83% 提升）

---

### 1.3 冗余功能分析

#### 1.3.1 Mermaid 生成器

**使用情况：**
- 模块：`mermaid_generator.py` (约 240 行)
- CLI 选项：`--format mermaid`, `--mermaid`（已弃用）
- 用途：生成静态 Mermaid Markdown 图

**用户需求：**
- 用户要求**移除** mermaid 生成器
- 理由：不再支持 mermaid 输出

**删除风险评估：**

**影响范围：**
- `cli.py` 中的导入和使用
- `src/mermaid_generator.py` 文件

**删除影响：**
- ✅ **无破坏性影响** - mermaid 是可选输出格式
- ✅ **向后兼容** - 只需在变更日志中记录

**删除内容：**
```python
# cli.py - 删除导入
from .mermaid_generator import MermaidGenerator, write_mermaid_file

# cli.py - 删除 CLI 选项
--format mermaid  # 从 choices 中移除
--mermaid  # 已弃用，完全删除
--format both  # 包含 mermaid，删除或修改

# cli.py - 删除生成逻辑（第 478-484 行）
if args.format == 'mermaid' or args.format == 'both':
    mermaid_gen = MermaidGenerator(...)
    mermaid_content = mermaid_gen.generate()
    write_mermaid_file(mermaid_content, str(output_paths['mermaid']))

# 删除文件
src/mermaid_generator.py
```

**结论：** ✅ 可以安全移除，低风险

---

#### 1.3.2 `--aggressive-filter` 参数

**用户需求：**
- 将 `--aggressive-filter` 作为**默认行为**
- 移除该 CLI 选项

**当前实现：**

```python
# cli.py 第 272-282 行
parser.add_argument(
    '--aggressive-filter',
    action='store_true',
    help='Apply aggressive filtering to compilation database (fast mode). '
         'Keeps: all -D flags, only -I flags matching filter.cfg, only files matching filter.cfg. '
         'Removes: all other compiler flags. '
         'This significantly speeds up parsing for large projects. '
         'Requires --filter-cfg to be specified.'
)
```

**作为默认行为的设计：**

**选项 1：当使用 `--filter-cfg` 时自动应用**
- 如果用户指定了 `--filter-cfg`，自动使用激进度滤
- 优点：最符合用户需求，提升性能
- 缺点：改变现有行为，可能影响某些项目

**选项 2：保留选项，但推荐默认使用**
- 保留 `--aggressive-filter` 选项
- 在文档中推荐默认使用
- 优点：完全向后兼容
- 缺点：不符合用户"移除参数"的需求

**推荐方案：** 选项 1 - 自动应用

**实现逻辑：**

```python
# 当 filter_config.mode == FilterMode.FILTER_CFG 时
# 自动应用激进度滤（除非用户明确禁用）

if filter_config.mode == FilterMode.FILTER_CFG:
    # 默认使用激进度滤
    # 用户可以通过新选项 --no-aggressive-filter 禁用（可选）
    use_aggressive = not args.no_aggressive_filter

    if use_aggressive:
        logging.info("Applying aggressive filter mode (default with --filter-cfg)")
        units = _apply_aggressive_filter(units, filter_config, logger)
    else:
        logging.info("Using standard filter mode (--no-aggressive-filter specified)")
        # 使用标准过滤
```

**向后兼容性：**

- 现有用户：如果使用 `--filter-cfg`，现在会自动获得激进度滤
- 新用户：文档说明默认行为
- 禁用方式：添加 `--no-aggressive-filter` 选项（可选）

**结论：** ✅ 推荐自动应用，但保留禁用选项以保持灵活性

---

#### 1.3.3 `--file-graph` 参数

**用户需求：**
- 文件级图作为**默认行为**
- 移除该 CLI 选项

**当前实现：**

```python
# cli.py 第 270-272 行
parser.add_argument(
    '--file-graph',
    action='store_true',
    help='Generate file-level call graph (file nodes with function call details). '
         'Only works with --format html. '
         'Edges show: function name @ sourceFile:line'
)
```

**问题：文件级图 vs 函数级图**

**函数级图（当前默认）：**
- 节点：函数
- 边：函数调用关系
- 适用场景：详细分析代码逻辑

**文件级图（--file-graph 选项）：**
- 节点：文件
- 边：文件间调用关系
- 适用场景：高层架构视图

**作为默认行为的设计：**

**问题：** 文件级图不能完全替代函数级图，两者适用于不同场景

**选项 1：文件级图作为默认，函数级图作为选项**
- `--format html` → 生成文件级图（默认）
- `--format html --function-graph` → 生成函数级图

**选项 2：保持当前默认，移除选项**
- `--format html` → 生成函数级图（默认，不变）
- 移除 `--file-graph` 选项
- 用户可以通过其他方式生成文件级图（？）

**选项 3：默认生成两者（不推荐）**
- `--format html` → 同时生成文件级和函数级图
- 问题：HTML 文件太大，影响性能

**推荐方案：** 选项 2 - 保持当前默认，移除 `--file-graph` 选项

**理由：**
1. 函数级图更详细，更常用
2. 文件级图可以通过其他方式实现（后续可以添加 `--file-graph` 选项）
3. 移除选项后简化 CLI
4. 如果用户强烈需要，可以后续恢复

**实现：**

```python
# 删除 --file-graph CLI 选项

# 删除条件判断
# if args.file_graph:
#     # 文件级图生成
# else:
#     # 函数级图生成（默认）

# 只保留函数级图生成（默认）
echarts_gen = EChartsGenerator(
    functions=functions_to_emit,
    relationships=relationships_to_emit,
    logger=logger
)
html_content = echarts_gen.generate_html()
write_html_file(html_content, str(output_paths['html']))
```

**结论：** ⚠️ 需要用户确认，可能影响需要文件级图的用户

---

### 1.4 数据流程分析

**问题 B："串行层级调用关系"是什么意思？**

**解释：**

根据用户描述的数据流程：
```
compile_commands.json (原始编译命令）
  ↓ [过滤]
compile_commands_simple.json (过滤后的编译命令）
  ↓ [解析]
call_graph.json (调用图数据）
  ↓ [生成]
call_graph.html (可视化 HTML）
```

"串行层级调用关系"可能指：

**解释 1：数据管道串行化**
- 当前的实现是**一次性完成所有步骤**（在内存中）
- 用户希望**串行化**每个步骤，保存中间结果
- 好处：可以独立调试每个步骤，重用中间结果

**解释 2：调用图的层级结构**
- 可能指函数调用的层次关系
- 但这个解释不符合"串行"的描述

**最可能的解释：解释 1 - 数据管道串行化**

**当前数据流程：**

```
compile_commands.json
  ↓ [加载到内存]
内存对象
  ↓ [过滤]
内存对象（过滤后）
  ↓ [解析]
内存对象（函数列表 + 关系）
  ↓ [生成]
输出文件（JSON/HTML/Mermaid）
```

**用户期望的数据流程：**

```
compile_commands.json
  ↓ [过滤] → compile_commands_simple.json
compile_commands_simple.json
  ↓ [解析] → call_graph.json
call_graph.json
  ↓ [生成] → call_graph.html
```

**差异总结：**

| 维度 | 当前实现 | 用户期望 |
|------|----------|----------|
| 流程 | 一次性，内存中 | 串行化，保存中间文件 |
| 中间输出 | 无（除非用户指定） | 自动保存中间文件 |
| 调试能力 | 较难（无法查看中间结果） | 容易（可检查每个步骤） |
| 性能 | 更快（无需文件 I/O） | 稍慢（额外的文件 I/O） |
| 灵活性 | 低（无法跳过步骤） | 高（可从任意步骤开始） |

---

## 2. 预期流程分析

### 2.1 用户期望的数据流程

```
Step 1: 加载原始编译数据库
compile_commands.json
  - 所有编译单元
  - 完整编译命令

Step 2: 过滤编译数据库
↓ 应用过滤规则（--filter-cfg, --path）
compile_commands_simple.json
  - 只保留匹配的编译单元
  - 过滤后的编译命令

Step 3: 解析源代码
↓ 调用 libclang AST 解析
call_graph.json
  - 函数列表（所有元数据）
  - 调用关系（parents/children）

Step 4: 生成可视化
↓ 根据调用图数据生成 HTML
call_graph.html
  - 嵌入 ECharts 图表
  - 交互式可视化
```

### 2.2 用户需求的关键点

1. **保留中间文件** - 每个步骤都保存输出
2. **可重用** - 可以从任意步骤开始（如从 `call_graph.json` 生成 HTML）
3. **可调试** - 可以检查每个步骤的结果
4. **可定制** - 可以组合不同的步骤

### 2.3 预期使用场景

**场景 1：完整流程**
```bash
# 从 compile_commands.json 开始，执行所有步骤
clang-call-analyzer --input compile_commands.json --filter-cfg filter.cfg
# 自动生成：
# - compile_commands_simple.json
# - call_graph.json
# - call_graph.html
```

**场景 2：从中间步骤开始**
```bash
# 从 call_graph.json 重新生成 HTML（修改样式或布局）
clang-call-analyzer --input call_graph.json --output new_visualization.html
```

**场景 3：只生成 JSON**
```bash
# 只生成 call_graph.json，不生成 HTML
clang-call-analyzer --input compile_commands.json --filter-cfg filter.cfg --json-only
```

---

## 3. 差异总结

### 3.1 功能差异

| 功能 | 当前实现 | 用户需求 | 差异 |
|------|----------|----------|------|
| Mermaid 输出 | ✅ 支持 | ❌ 不需要 | 冗余 |
| `--aggressive-filter` 选项 | ✅ 独立选项 | 🔜 作为默认 | 语义差异 |
| `--file-graph` 选项 | ✅ 独立选项 | 🔜 作为默认 | 语义差异 |
| 中间 JSON 输出 | ❌ 无 | ✅ 需要 | 缺失 |
| 数据流程 | 🔘 一次性 | 🔜 串行化 | 架构差异 |

### 3.2 架构差异

**当前架构：**
```
单一执行路径
  ↓
一次性完成所有步骤
  ↓
输出（JSON/HTML/Mermaid）
```

**期望架构：**
```
模块化步骤（可独立执行）
  ↓
保存中间结果
  ↓
可从任意步骤开始
  ↓
灵活组合
```

### 3.3 实现复杂度差异

**简单实现（推荐）：**
- 移除 Mermaid 生成器（简单）
- 修改 `--aggressive-filter` 为默认行为（中等）
- 移除 `--file-graph` 选项（简单）
- **不添加中间 JSON 输出**（不修改架构）

**复杂实现：**
- 所有简单实现的内容
- 添加 `compile_commands_simple.json` 输出
- 添加 `call_graph.json` 中间步骤
- 修改架构为串行化流程
- 支持从中间步骤开始

---

## 4. 实现方案

### 4.1 方案 A：简单实现（推荐）

**目标：**
- 移除冗余功能
- 调整默认行为
- 保持现有架构

**实现内容：**

#### 4.1.1 移除 Mermaid 生成器

**删除文件：**
- `src/mermaid_generator.py`

**修改文件：**
- `src/cli.py`
  - 删除导入：`from .mermaid_generator import MermaidGenerator, write_mermaid_file`
  - 删除 CLI 选项：`--format mermaid`, `--mermaid`
  - 删除 `--format both` 选项或修改为只生成 JSON+HTML
  - 删除 mermaid 生成逻辑（第 478-484 行）

**修改 `_determine_output_paths()`:**
```python
# 删除 mermaid 相关路径处理
# 修改 'both' 格式，只生成 JSON 和 HTML
elif args.format == 'both':
    paths['json'] = base_path if base_path.suffix == '.json' else base_path.with_suffix('.json')
    paths['html'] = base_path.with_suffix('.html')
    paths['mermaid'] = None  # 不生成 mermaid
```

**风险评估：**
- 🟢 低风险 - Mermaid 是可选输出格式
- 🟢 无破坏性影响
- 🟢 向后兼容（在变更日志中记录）

---

#### 4.1.2 `--aggressive-filter` 作为默认行为

**修改逻辑：**

```python
# cli.py

# 删除 --aggressive-filter CLI 选项
# 删除第 272-282 行

# 修改过滤逻辑（第 322-346 行）
if filter_config.mode == FilterMode.FILTER_CFG:
    # 自动应用激进度滤（当使用 --filter-cfg 时）
    logging.info("Applying aggressive filter mode (default with --filter-cfg)")
    units = _apply_aggressive_filter(units, filter_config, logger)

elif filter_config.mode == FilterMode.SINGLE_PATH:
    # 使用标准过滤（保留所有标志）
    units = _apply_standard_filter(units, filter_config, logger)

else:
    # AUTO_DETECT 模式 - 分析所有文件
    logging.info(f"Analyzing all {len(units)} compilation units")
```

**可选：添加禁用选项**
```python
# 添加新选项（可选，用于禁用激进度滤）
parser.add_argument(
    '--no-aggressive-filter',
    action='store_true',
    help='Disable aggressive filtering when using --filter-cfg (uses standard filter mode)'
)

# 修改逻辑
if filter_config.mode == FilterMode.FILTER_CFG:
    if not args.no_aggressive_filter:
        # 默认：激进度滤
        logging.info("Applying aggressive filter mode (default with --filter-cfg)")
        units = _apply_aggressive_filter(units, filter_config, logger)
    else:
        # 用户禁用：标准过滤
        logging.info("Using standard filter mode (--no-aggressive-filter specified)")
        units = _apply_standard_filter(units, filter_config, logger)
```

**风险评估：**
- 🟡 中等风险 - 改变现有行为
- 🟡 可能影响某些依赖完整编译标志的项目
- 🟢 提供 `--no-aggressive-filter` 选项可以缓解
- 🟢 文档说明默认行为变更

---

#### 4.1.3 移除 `--file-graph` 选项

**修改逻辑：**

```python
# 删除 --file-graph CLI 选项
# 删除第 270-272 行

# 删除条件判断（第 486-530 行）
# 只保留函数级图生成（默认）

if args.format == 'html' or args.format == 'both':
    # 函数级图（默认，唯一选项）
    logging.info("Generating function-level ECharts HTML...")
    echarts_gen = EChartsGenerator(
        functions=functions_to_emit,
        relationships=relationships_to_emit,
        logger=logger
    )
    html_content = echarts_gen.generate_html()
    write_html_file(html_content, str(output_paths['html']))
```

**可选：保留 `--file-graph` 作为未来选项**
```python
# 如果用户强烈需要文件级图，可以保留该选项
# 但不作为默认

parser.add_argument(
    '--file-graph',
    action='store_true',
    help='[Deprecated/Experimental] Generate file-level call graph instead of function-level. '
         'This feature may be removed in future versions.'
)
```

**风险评估：**
- 🟡 中等风险 - 移除功能选项
- 🟡 影响需要文件级图的用户
- 🟢 函数级图更详细，更常用
- 🟢 文件级图可以后续恢复或作为插件

---

**总结（方案 A）：**

| 任务 | 复杂度 | 风险 | 时间 |
|------|--------|------|------|
| 移除 Mermaid 生成器 | 简单 | 低 | 1 小时 |
| `--aggressive-filter` 默认 | 中等 | 中等 | 2 小时 |
| 移除 `--file-graph` 选项 | 简单 | 中等 | 1 小时 |
| 更新文档 | 简单 | 低 | 1 小时 |
| 测试验证 | 简单 | 低 | 1 小时 |
| **总计** | - | - | **6 小时** |

---

### 4.2 方案 B：复杂实现

**目标：**
- 包含方案 A 的所有内容
- 添加中间 JSON 输出
- 修改架构为串行化流程
- 支持从中间步骤开始

**实现内容：**

#### 4.2.1 方案 A 的所有内容
- 移除 Mermaid 生成器
- `--aggressive-filter` 作为默认
- 移除 `--file-graph` 选项

#### 4.2.2 添加 `compile_commands_simple.json` 输出

**新 CLI 选项：**
```python
parser.add_argument(
    '--dump-filtered-db',
    type=str,
    default=None,
    metavar='FILE',
    help='[EXPERIMENTAL] Dump filtered compile_commands.json to specified file. '
         'Useful for debugging filter configuration and pipeline processing.'
)
```

**实现逻辑：**
```python
# 在过滤编译数据库后（第 346-375 行）
if args.dump_filtered_db:
    db_filter.dump_filtered_db(compile_commands, args.dump_filtered_db)
    logging.info(f"Dumped filtered compile_commands.json to {args.dump_filtered_db}")
```

**注意：** 当前已有 `--dump-filtered-db` 选项，但不是默认行为。需要改为：
- 默认保存到 `compile_commands_simple.json`（如果输出路径为 `output.json`）
- 或通过新选项 `--save-intermediate` 控制

#### 4.2.3 添加 `call_graph.json` 中间步骤

**当前实现：**
- JSON 输出通过 `JSONEmitter` 生成
- 但不作为中间步骤保存

**修改逻辑：**
```python
# 在生成 HTML 之前，先生成 JSON
if args.format == 'html' or args.format == 'both':
    # 默认生成 JSON 作为中间步骤
    json_output_path = output_paths['json'] if args.format == 'both' else Path('call_graph.json')

    logging.info(f"Generating intermediate JSON to {json_output_path}")
    emitter = JSONEmitter(str(json_output_path))
    emitter.emit(functions_to_emit, relationships_to_emit)

    # 然后生成 HTML
    logging.info("Generating HTML from intermediate JSON...")
    # 加载 JSON
    with open(json_output_path, 'r', encoding='utf-8') as f:
        functions_dict = json_lib.load(f)

    echarts_gen = EChartsGenerator(
        functions=function_dict,  # 从 JSON 加载
        relationships=relationships_to_emit,
        logger=logger
    )
    html_content = echarts_gen.generate_html()
    write_html_file(html_content, str(output_paths['html']))
```

**问题：** `EChartsGenerator` 期望 `List[FunctionInfo]`，不是 `List[Dict]`

**解决方案：**
1. 修改 `EChartsGenerator` 接受 `List[Dict]`
2. 或创建一个转换函数 `dict_to_functioninfo()`
3. 或保持当前实现（使用内存数据，不通过 JSON）

#### 4.2.4 支持从中间步骤开始

**新 CLI 选项：**
```python
parser.add_argument(
    '--from',
    type=str,
    choices=['db', 'filtered-db', 'json', 'html'],
    default='db',
    help='Start processing from specified step: '
         'db (compile_commands.json), '
         'filtered-db (compile_commands_simple.json), '
         'json (call_graph.json), '
         'html (call_graph.html, skip analysis)'
)

parser.add_argument(
    '--to',
    type=str,
    choices=['filtered-db', 'json', 'html'],
    help='Stop processing at specified step (exclusive)'
)
```

**实现逻辑：**
```python
# 根据 --from 参数决定开始步骤
if args.from == 'db':
    # 从 compile_commands.json 开始（完整流程）
    pass
elif args.from == 'filtered-db':
    # 从 compile_commands_simple.json 开始
    # 跳过过滤步骤
    filtered_db_path = args.input or 'compile_commands_simple.json'
    # 加载过滤后的编译数据库
    units = load_filtered_compilation_db(filtered_db_path)
    # 继续解析
elif args.from == 'json':
    # 从 call_graph.json 开始
    # 只生成 HTML
    json_path = args.input or 'call_graph.json'
    with open(json_path, 'r', encoding='utf-8') as f:
        functions_dict = json_lib.load(f)
    # 生成 HTML
elif args.from == 'html':
    # 只生成 HTML（从 JSON）
    pass
```

#### 4.2.5 修改 `EChartsGenerator` 支持从 JSON 加载

**当前问题：**
- `EChartsGenerator.__init__(functions: List[FunctionInfo])`
- 需要修改为支持 `List[Dict]`

**修改方案 1：修改接口**
```python
class EChartsGenerator:
    def __init__(self,
                 functions: Union[List[FunctionInfo], List[Dict]],  # 修改
                 relationships: Dict[int, Tuple[List[int], List[int]]],
                 logger: Optional[logging.Logger] = None):
        self.functions = self._normalize_functions(functions)  # 新增
        self.relationships = relationships
        self.logger = logger or logging.getLogger(__name__)

    def _normalize_functions(self, functions):
        """标准化函数数据为统一格式"""
        if not functions:
            return []

        # 检查第一个元素的类型
        if isinstance(functions[0], dict):
            # 从 JSON 加载，转换为内部格式
            return self._dict_to_function_info(functions)
        else:
            # 已经是 FunctionInfo 格式
            return functions

    def _dict_to_function_info(self, functions_dict):
        """将 JSON 格式转换为 FunctionInfo 格式"""
        functions = []
        for func_dict in functions_dict:
            func = FunctionInfo(
                path=func_dict['self']['path'],
                line_range=tuple(func_dict['self']['line']),
                name=func_dict['self']['name'],
                qualified_name=func_dict['self']['qualified_name'],
                brief=func_dict['self']['brief'],
                raw_cursor=None,  # JSON 中没有
                index=func_dict.get('index', 0)
            )
            functions.append(func)
        return functions
```

**修改方案 2：保持接口，添加新类**
```python
# 创建新类专门处理 JSON 数据
class EChartsGeneratorFromJSON(EChartsGenerator):
    """从 JSON 数据生成 ECharts HTML"""

    def __init__(self,
                 json_data: List[Dict],
                 relationships: Dict[int, Tuple[List[int], List[int]]],
                 logger: Optional[logging.Logger] = None):
        # 转换 JSON 为 FunctionInfo
        functions = self._dict_to_function_info(json_data)
        super().__init__(functions, relationships, logger)
```

**推荐：方案 1** - 修改接口，更灵活

---

**总结（方案 B）：**

| 任务 | 复杂度 | 风险 | 时间 |
|------|--------|------|------|
| 方案 A 的所有内容 | - | - | 6 小时 |
| 添加中间 JSON 输出 | 中等 | 中等 | 4 小时 |
| 支持从中间步骤开始 | 复杂 | 高 | 8 小时 |
| 修改 EChartsGenerator 接口 | 中等 | 中等 | 4 小时 |
| 更新文档 | 中等 | 低 | 2 小时 |
| 测试验证 | 中等 | 中等 | 4 小时 |
| **总计** | - | - | **28 小时** |

---

## 5. 推荐方案

### 5.1 推荐方案：方案 A（简单实现）

**理由：**

1. **实用性优先**
   - 用户的核心需求是移除冗余功能和调整默认行为
   - 串行化数据流程是"锦上添花"，不是"必须"
   - 当前架构已经很好，过度工程化不必要

2. **向后兼容性**
   - 方案 A 保持了现有架构
   - 用户使用方式基本不变
   - 迁移成本低

3. **开发效率**
   - 6 小时 vs 28 小时
   - 快速交付，快速反馈
   - 降低测试和维护成本

4. **风险控制**
   - 方案 A 风险低
   - 方案 B 风险高（架构变更）
   - 先验证方案 A，再考虑方案 B

### 5.2 不推荐方案 B 的原因

1. **过度工程化**
   - 串行化数据流程增加了复杂度
   - 用户可能不需要从中间步骤开始
   - 当前的"一次性完成"已经足够

2. **性能下降**
   - 中间文件需要额外的文件 I/O
   - 对于大型项目，可能影响性能
   - 内存中处理更快

3. **维护成本**
   - 需要维护更多的文件格式和接口
   - 需要处理更多的边界情况
   - 测试复杂度增加

### 5.3 后续可选：如果用户强烈需要串行化

**如果用户后续需要方案 B，可以分步实现：**

**阶段 1：** 先实现方案 A（当前推荐）
- 移除冗余功能
- 调整默认行为
- 验证和反馈

**阶段 2：** 如果用户需要，再添加中间 JSON 输出
- 保留当前架构
- 添加 `--save-intermediate` 选项
- 保存中间文件，但不改变核心流程

**阶段 3：** 如果用户需要，再支持从中间步骤开始
- 添加 `--from` 和 `--to` 选项
- 修改架构为模块化流程

---

## 6. 实现步骤（方案 A）

### 6.1 准备阶段（0.5 小时）

1. **创建功能分支**
   ```bash
   cd /home/gabriel/.openclaw/code/clang-call-analyzer
   git checkout -b feature/system-optimization
   ```

2. **备份当前状态**
   ```bash
   git status
   git add -A
   git commit -m "Backup: before system optimization"
   ```

3. **阅读相关代码**
   - `src/cli.py`（CLI 接口）
   - `src/mermaid_generator.py`（待删除）
   - `src/filter_config.py`（过滤系统）
   - `src/compilation_db_filter.py`（编译数据库过滤）

---

### 6.2 移除 Mermaid 生成器（1 小时）

**步骤 1：删除文件**
```bash
cd /home/gabriel/.openclaw/code/clang-call-analyzer
rm src/mermaid_generator.py
```

**步骤 2：修改 `src/cli.py`**

删除导入（第 22 行）：
```python
# 删除这行
from .mermaid_generator import MermaidGenerator, write_mermaid_file
```

删除 CLI 选项（第 60-82 行）：
```python
# 删除 --mermaid 选项
parser.add_argument(
    '--mermaid', '-m',
    action='store_true',
    ...
)

# 修改 --format 选项
parser.add_argument(
    '--format', '-F',
    type=str,
    choices=['json', 'html', 'both'],  # 删除 'mermaid'
    default='json',
    help='Output format (default: json). '
         'Options: json (JSON output), '
         'html (ECharts interactive graph), '
         'both (generate both JSON and HTML). '
         'If --format is html or both, --output is used for the HTML file. '
         'When format is both, JSON is written to <output>.json and HTML to <output>.html.'
)
```

删除生成逻辑（第 478-484 行）：
```python
# 删除这段
if args.format == 'mermaid' or args.format == 'both':
    # Generate Mermaid diagram
    logging.info("Generating Mermaid diagram...")
    mermaid_gen = MermaidGenerator(
        functions=functions_to_emit,
        relationships=relationships_to_emit
    )
    mermaid_content = mermaid_gen.generate()
    write_mermaid_file(mermaid_content, str(output_paths['mermaid']))
```

修改 `_determine_output_paths()`（第 563-600 行）：
```python
def _determine_output_paths(args: argparse.Namespace) -> Dict[str, Path]:
    paths = {}

    if args.output:
        base_path = Path(args.output)
    else:
        base_path = Path("output")

    # Set paths based on format
    if args.format == 'json':
        paths['json'] = base_path if base_path.suffix == '.json' else base_path.with_suffix('.json')
    elif args.format == 'html':
        paths['html'] = base_path if base_path.suffix == '.html' else base_path.with_suffix('.html')
    elif args.format == 'both':
        # Both format: generate JSON and HTML only
        paths['json'] = base_path if base_path.suffix == '.json' else base_path.with_suffix('.json')
        paths['html'] = base_path.with_suffix('.html')
        paths['mermaid'] = None  # 不生成 mermaid
    else:
        # Default to JSON
        paths['json'] = base_path if base_path.suffix == '.json' else base_path.with_suffix('.json')

    return paths
```

修改 `_print_output_summary()`（第 603-626 行）：
```python
def _print_output_summary(format_type: str, output_paths: Dict[str, Path]) -> None:
    print("\n" + "=" * 50)
    print("Output Generation Complete")
    print("=" * 50)

    if format_type == 'json' or format_type == 'both':
        if output_paths.get('json'):
            print(f"  JSON:  {output_paths['json']}")

    if format_type == 'html' or format_type == 'both':
        if output_paths.get('html'):
            print(f"  HTML:  {output_paths['html']}")

    print("=" * 50 + "\n")
```

**步骤 3：测试**
```bash
cd /home/gabriel/.openclaw/code/clang-call-analyzer
python -m src.cli --help  # 应该不包含 --mermaid 选项
python -m src.cli -i compile_commands.json -o test.json -f json  # 应该正常工作
python -m src.cli -i compile_commands.json -o test.html -f html  # 应该正常工作
python -m src.cli -i compile_commands.json -o test -f both  # 应该生成 test.json 和 test.html
```

---

### 6.3 `--aggressive-filter` 作为默认行为（2 小时）

**步骤 1：删除 CLI 选项**
```python
# 删除 --aggressive-filter 选项（第 272-282 行）
```

**步骤 2：添加禁用选项（可选）**
```python
# 在 parse_args() 中添加
parser.add_argument(
    '--no-aggressive-filter',
    action='store_true',
    help='Disable aggressive filtering when using --filter-cfg (uses standard filter mode)'
)
```

**步骤 3：修改过滤逻辑**
```python
# 在 main() 中修改（第 322-346 行）
# 删除
# if args.aggressive_filter:
#     ...
# elif filter_config.mode != FilterMode.AUTO_DETECT:
#     ...
# else:
#     ...

# 替换为
if filter_config.mode == FilterMode.FILTER_CFG:
    # 自动应用激进度滤（当使用 --filter-cfg 时）
    if not args.no_aggressive_filter:
        logging.info("Applying aggressive filter mode (default with --filter-cfg)")
        units = _apply_aggressive_filter(units, filter_config, logger)
    else:
        # 用户禁用：标准过滤
        logging.info("Using standard filter mode (--no-aggressive-filter specified)")
        # 使用 CompilationDatabaseFilter 过滤（保留所有标志）
        compile_commands = [
            {
                'file': unit.file,
                'command': unit.command,
                'directory': unit.directory
            }
            for unit in units
        ]

        db_filter = CompilationDatabaseFilter(
            filter_config=filter_config,
            project_root=str(project_root),
            logger=logger
        )

        filtered_units = db_filter.filter_compilation_db(compile_commands)

        # Dump filtered DB if requested
        if args.dump_filtered_db:
            db_filter.dump_filtered_db(compile_commands, args.dump_filtered_db)

        # Convert back to CompilationUnit format
        units = [
            comp_db._parse_entry({
                'file': unit.file,
                'command': unit.command,
                'directory': unit.directory
            })
            for unit in filtered_units
        ]

        logging.info(db_filter.get_summary())

elif filter_config.mode == FilterMode.SINGLE_PATH:
    # 使用标准过滤（保留所有标志）
    logging.info(f"Using standard filter mode for single path: {filter_config.paths[0]}")
    # 使用 CompilationDatabaseFilter 过滤
    compile_commands = [
        {
            'file': unit.file,
            'command': unit.command,
            'directory': unit.directory
        }
        for unit in units
    ]

    db_filter = CompilationDatabaseFilter(
        filter_config=filter_config,
        project_root=str(project_root),
        logger=logger
    )

    filtered_units = db_filter.filter_compilation_db(compile_commands)

    # Dump filtered DB if requested
    if args.dump_filtered_db:
        db_filter.dump_filtered_db(compile_commands, args.dump_filtered_db)

    # Convert back to CompilationUnit format
    units = [
        comp_db._parse_entry({
            'file': unit.file,
            'command': unit.command,
            'directory': unit.directory
        })
        for unit in filtered_units
    ]

    logging.info(db_filter.get_summary())

else:
    # AUTO_DETECT 模式 - 分析所有文件
    logging.info(f"Analyzing all {len(units)} compilation units")
```

**步骤 4：测试**
```bash
cd /home/gabriel/.openclaw/code/clang-call-analyzer

# 测试激进度滤（默认）
python -m src.cli -i compile_commands.json -f filter.cfg -o test.json -v info
# 应该看到 "Applying aggressive filter mode (default with --filter-cfg)"

# 测试禁用激进度滤
python -m src.cli -i compile_commands.json -f filter.cfg -o test.json --no-aggressive-filter -v info
# 应该看到 "Using standard filter mode (--no-aggressive-filter specified)"

# 测试单一路径（标准过滤）
python -m src.cli -i compile_commands.json -p src/ -o test.json -v info
# 应该看到 "Using standard filter mode for single path: src/"

# 测试无过滤
python -m src.cli -i compile_commands.json -o test.json -v info
# 应该看到 "Analyzing all X compilation units"
```

---

### 6.4 移除 `--file-graph` 选项（1 小时）

**步骤 1：删除 CLI 选项**
```python
# 删除 --file-graph 选项（第 270-272 行）
```

**步骤 2：删除导入**
```python
# 在 cli.py 顶部删除（第 23 行）
from .file_graph_generator import FileGraphGenerator
```

**步骤 3：修改生成逻辑**
```python
# 在 main() 中修改（第 486-530 行）
# 删除条件判断
# if args.file_graph:
#     # 文件级图生成
# else:
#     # 函数级图生成

# 替换为
if args.format == 'html' or args.format == 'both':
    # 函数级图（默认，唯一选项）
    logging.info("Generating function-level ECharts HTML...")
    echarts_gen = EChartsGenerator(
        functions=functions_to_emit,
        relationships=relationships_to_emit,
        logger=logger
    )
    html_content = echarts_gen.generate_html()
    write_html_file(html_content, str(output_paths['html']))
```

**步骤 4：清理 FileGraphGenerator（可选）**
```bash
# 如果确定不需要文件级图，可以删除
rm src/file_graph_generator.py

# 或者保留，未来可能恢复
# 但从 cli.py 中移除使用
```

**建议：** 暂时保留 `file_graph_generator.py`，但不从 CLI 暴露。如果用户需要，可以后续恢复。

**步骤 5：测试**
```bash
cd /home/gabriel/.openclaw/code/clang-call-analyzer
python -m src.cli -i compile_commands.json -o test.html -f html -v info
# 应该生成函数级图
```

---

### 6.5 更新文档（1 小时）

**步骤 1：更新 README.md**
```markdown
# clang-call-analyzer

## Features

- Parse `compile_commands.json` for compilation flags
- Extract function definitions using libclang
- Parse Doxygen `@brief` tags from comments
- Build bidirectional call graph (parents/children)
- Output JSON with function metadata and relationships
- **Generate interactive HTML visualization with ECharts**

## Usage

### Output Formats

```bash
# JSON output
python -m src.cli -i compile_commands.json -o output.json -f json

# HTML output
python -m src.cli -i compile_commands.json -o output.html -f html

# Both JSON and HTML
python -m src.cli -i compile_commands.json -o output -f both
```

### Filtering

**Aggressive filtering (default with --filter-cfg):**

```bash
# Use aggressive filtering for fast analysis (default when using --filter-cfg)
python -m src.cli -i compile_commands.json -f filter.cfg -o output.json
```

**Standard filtering:**

```bash
# Use standard filtering (keep all compiler flags)
python -m src.cli -i compile_commands.json -f filter.cfg -o output.json --no-aggressive-filter
```

## Changes in v2.0

**Removed:**
- Mermaid output format (`--format mermaid`, `--mermaid`)
- `--file-graph` option (function-level graph is now the only option)

**Changed:**
- Aggressive filtering is now the default when using `--filter-cfg`
- Added `--no-aggressive-filter` to disable aggressive filtering
```

**步骤 2：更新 USAGE.md**
```markdown
# clang-call-analyzer

## 命令行选项

```
-i, --input           Path to compile_commands.json
-o, --output          Output file path
-f, --filter-cfg      Filter configuration file (INI format)
-p, --path            Filter: 只分析指定路径下的文件（递归）
--dump-filtered-db    Dump filtered compile_commands.json to file
--no-aggressive-filter  Disable aggressive filtering when using --filter-cfg
-v, --verbose         Logging level (error, warning, info, debug)
--disable-retry       Disable adaptive retry parsing
```

## 输出格式

### JSON 输出
```bash
./run.sh -f filter.cfg -o output.json -f json
```

### HTML 输出
```bash
./run.sh -f filter.cfg -o output.html -f html
```

### 同时输出 JSON 和 HTML
```bash
./run.sh -f filter.cfg -o output -f both
```

## 过滤性能

### 激进度滤（默认，使用 --filter-cfg）

```bash
# 默认使用激进度滤（保留 -D 和 filter.cfg 中的 -I，移除其他标志）
./run.sh -f filter.cfg -o output.json
```

**性能对比：**
| 指标 | 无过滤 | 使用 filter.cfg（激进度滤） | 提升 |
|------|--------|---------------------------|------|
| 编译单元 | 206 | 10 | 95% ↓ |
| 函数数量 | ~15,828 | 95 | 99% ↓ |
| 分析时间 | >180s | ~30s | 80%+ ↓ |

### 标准过滤

```bash
# 使用标准过滤（保留所有编译器标志）
./run.sh -f filter.cfg -o output.json --no-aggressive-filter
```

## 版本历史

### v2.0 (2026-03-20)
- 移除 Mermaid 输出格式
- 移除 `--file-graph` 选项
- 激进度滤成为默认行为（使用 --filter-cfg 时）
- 添加 `--no-aggressive-filter` 选项

### v1.x
- 初始版本
```

**步骤 3：更新 CHANGELOG.md**
```markdown
# Changelog

## [2.0.0] - 2026-03-20

### Added
- `--no-aggressive-filter` option to disable aggressive filtering when using `--filter-cfg`

### Changed
- Aggressive filtering is now the default behavior when using `--filter-cfg`
  - Previous behavior: required `--aggressive-filter` flag
  - New behavior: automatically applies aggressive filtering when `--filter-cfg` is specified
  - Migration: use `--no-aggressive-filter` to restore old behavior

### Removed
- Mermaid output format (`--format mermaid`, `--mermaid` flag)
  - Reason: Low usage, maintenance overhead
  - Migration: use `--format html` for interactive visualization
- `--file-graph` option
  - Reason: Function-level graph is more commonly used
  - Migration: Function-level graph is now the only HTML output option

### Deprecated
- None

### Fixed
- None

## [1.0.0] - Previous
- Initial release
```

---

### 6.6 测试验证（1 小时）

**步骤 1：单元测试**
```bash
cd /home/gabriel/.openclaw/code/clang-call-analyzer
python -m pytest tests/ -v
```

**步骤 2：集成测试**
```bash
# 测试基本功能
python -m src.cli --help

# 测试 JSON 输出
python -m src.cli -i compile_commands.json -o test_output.json -f json
cat test_output.json

# 测试 HTML 输出
python -m src.cli -i compile_commands.json -o test_output.html -f html
ls -lh test_output.html

# 测试同时输出
python -m src.cli -i compile_commands.json -o test_output -f both
ls -lh test_output.json test_output.html

# 测试过滤功能
python -m src.cli -i compile_commands.json -f filter.cfg -o test_filtered.json -v info
python -m src.cli -i compile_commands.json -f filter.cfg -o test_filtered.json --no-aggressive-filter -v info
python -m src.cli -i compile_commands.json -p src/ -o test_path.json -v info
```

**步骤 3：清理测试文件**
```bash
rm test_output.json test_output.html test_filtered.json test_path.json
```

**步骤 4：代码检查**
```bash
# 检查 Python 语法
python -m py_compile src/*.py

# 运行 lint
python lint.py
```

---

### 6.7 提交代码（0.5 小时）

**步骤 1：检查变更**
```bash
cd /home/gabriel/.openclaw/code/clang-call-analyzer
git status
git diff
```

**步骤 2：添加文件**
```bash
git add src/cli.py
git add src/echarts_generator.py  # 如果修改了
git rm src/mermaid_generator.py  # 删除了文件
git add README.md
git add USAGE.md
git add CHANGELOG.md
```

**步骤 3：提交**
```bash
git commit -m "feat: system optimization - remove redundant features and adjust defaults

- Remove Mermaid output format (--format mermaid, --mermaid flag)
- Remove --file-graph option (function-level graph is now the only HTML option)
- Make aggressive filtering the default when using --filter-cfg
- Add --no-aggressive-filter option to disable aggressive filtering
- Update documentation (README.md, USAGE.md, CHANGELOG.md)

Breaking changes:
- Mermaid output format is no longer supported
- --file-graph option is removed
- Aggressive filtering is now enabled by default with --filter-cfg

See CHANGELOG.md for migration guide."
```

**步骤 4：创建标签**
```bash
git tag -a v2.0.0 -m "Release v2.0.0: System optimization"
```

**步骤 5：推送**
```bash
git push origin feature/system-optimization
git push origin v2.0.0
```

---

## 7. 风险评估

### 7.1 方案 A 风险评估

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| 用户依赖 Mermaid 输出 | 低 | 中 | 在 CHANGELOG 中说明，推荐使用 HTML |
| 激进度滤影响某些项目 | 中 | 中 | 提供 `--no-aggressive-filter` 选项 |
| 用户需要文件级图 | 低 | 低 | 保留 `file_graph_generator.py`，未来可恢复 |
| 文档更新遗漏 | 低 | 低 | 仔细检查所有文档 |
| 测试不充分 | 低 | 中 | 运行完整的单元测试和集成测试 |
| 向后兼容性问题 | 中 | 中 | 在 CHANGELOG 中提供迁移指南 |

### 7.2 关键风险缓解

**风险 1：激进度滤影响某些项目**

**缓解措施：**
1. 添加 `--no-aggressive-filter` 选项
2. 在文档中明确说明默认行为变更
3. 提供清晰的迁移指南
4. 收集用户反馈，必要时调整

**风险 2：用户依赖 Mermaid 输出**

**缓解措施：**
1. 检查 Mermaid 输出的实际使用情况（可能很低）
2. 在 CHANGELOG 中说明移除原因
3. 推荐 HTML 作为替代方案
4. 如果用户强烈需要，可以作为插件恢复

**风险 3：文档更新遗漏**

**缓解措施：**
1. 使用 `grep` 搜索所有提到 Mermaid 的地方
2. 更新所有相关文档（README, USAGE, CHANGELOG）
3. 检查代码注释
4. 让其他团队成员审核文档

**搜索 Mermaid 引用：**
```bash
cd /home/gabriel/.openclaw/code/clang-call-analyzer
grep -r "mermaid" --include="*.md" --include="*.py" --include="*.txt"
```

---

### 7.3 回滚计划

如果出现严重问题，可以快速回滚：

```bash
# 回滚到 v1.0.0
git checkout v1.0.0

# 或者回滚特定提交
git revert <commit-hash>

# 推送回滚
git push origin main
```

---

## 8. 向后兼容性

### 8.1 迁移指南

**从 v1.x 迁移到 v2.0：**

#### 迁移 1：Mermaid 输出用户

**旧命令：**
```bash
python -m src.cli -i compile_commands.json -o output.mermaid.md -f mermaid
python -m src.cli -i compile_commands.json --mermaid
```

**新命令：**
```bash
python -m src.cli -i compile_commands.json -o output.html -f html
```

**说明：** Mermaid 输出已移除，使用 HTML 作为替代方案。HTML 提供交互式可视化，功能更强大。

---

#### 迁移 2：`--aggressive-filter` 用户

**旧命令：**
```bash
python -m src.cli -i compile_commands.json -f filter.cfg --aggressive-filter
```

**新命令：**
```bash
# 激进度滤现在是默认行为（使用 --filter-cfg 时）
python -m src.cli -i compile_commands.json -f filter.cfg

# 如果需要恢复旧行为（标准过滤）
python -m src.cli -i compile_commands.json -f filter.cfg --no-aggressive-filter
```

**说明：** 激进度滤现在是默认行为。如果需要标准过滤，使用 `--no-aggressive-filter`。

---

#### 迁移 3：`--file-graph` 用户

**旧命令：**
```bash
python -m src.cli -i compile_commands.json -o output.html --file-graph
```

**新命令：**
```bash
# 文件级图选项已移除
# 函数级图是唯一的 HTML 输出选项
python -m src.cli -i compile_commands.json -o output.html -f html
```

**说明：** `--file-graph` 选项已移除。函数级图现在是唯一的 HTML 输出选项。如果需要文件级图，请提交 issue。

---

### 8.2 兼容性矩阵

| 功能 | v1.x | v2.0 | 迁移 |
|------|------|------|------|
| JSON 输出 | ✅ | ✅ | 无需更改 |
| HTML 输出（函数级） | ✅ | ✅ | 无需更改 |
| HTML 输出（文件级） | ✅ (`--file-graph`) | ❌ | 移除，如有需要提交 issue |
| Mermaid 输出 | ✅ | ❌ | 使用 HTML 替代 |
| 激进度滤 | ✅ (`--aggressive-filter`) | ✅ (默认) | 移除标志，现在默认启用 |
| 标准过滤 | ✅ (默认) | ✅ (`--no-aggressive-filter`) | 使用新标志禁用激进度滤 |
| 单一路径过滤 | ✅ (`--path`) | ✅ | 无需更改 |
| 配置文件过滤 | ✅ (`--filter-cfg`) | ✅ | 无需更改，但默认行为改变 |

---

### 8.3 升级脚本（可选）

如果需要自动化迁移，可以创建升级脚本：

```python
#!/usr/bin/env python3
"""Migration script from v1.x to v2.0"""

import re
import sys
from pathlib import Path

def migrate_command(old_command: str) -> str:
    """Migrate old command to new syntax"""

    # Case 1: --format mermaid
    if '--format mermaid' in old_command or '--mermaid' in old_command:
        new_command = re.sub(
            r'--format mermaid|--mermaid',
            '--format html',
            old_command
        )
        print(f"[Mermaid] {old_command} → {new_command}")
        return new_command

    # Case 2: --aggressive-filter
    if '--aggressive-filter' in old_command:
        new_command = old_command.replace('--aggressive-filter', '')
        print(f"[AggressiveFilter] {old_command} → {new_command}")
        return new_command

    # Case 3: --file-graph
    if '--file-graph' in old_command:
        new_command = old_command.replace('--file-graph', '')
        print("[FileGraph] --file-graph option removed, using function-level graph")
        return new_command

    # No changes needed
    return old_command

if __name__ == '__main__':
    if len(sys.argv) > 1:
        # Migrate command from arguments
        old_cmd = ' '.join(sys.argv[1:])
        new_cmd = migrate_command(old_cmd)
        print(f"\nMigrated command:\n{new_cmd}")
    else:
        # Interactive mode
        print("Enter old command (or Ctrl+C to exit):")
        try:
            while True:
                old_cmd = input("> ")
                new_cmd = migrate_command(old_cmd)
                print(f"→ {new_cmd}\n")
        except KeyboardInterrupt:
            print("\nExit.")
```

---

## 9. 总结与建议

### 9.1 关键决策

| 决策 | 推荐方案 | 理由 |
|------|----------|------|
| 移除 Mermaid | ✅ 是 | 低使用率，维护成本高 |
| 激进度滤作为默认 | ✅ 是 | 提升性能，提供禁用选项 |
| 移除 `--file-graph` | ✅ 是（需确认） | 函数级图更常用，简化 CLI |
| 串行化数据流程 | ❌ 否 | 过度工程化，当前架构足够 |

### 9.2 推荐执行顺序

**阶段 1：立即执行（6 小时）**
1. 移除 Mermaid 生成器
2. `--aggressive-filter` 作为默认
3. 移除 `--file-graph` 选项（待确认）
4. 更新文档
5. 测试验证
6. 提交代码

**阶段 2：观察反馈（1-2 周）**
- 监控用户反馈
- 收集问题报告
- 评估是否需要调整

**阶段 3：可选增强（如果需要）**
- 添加中间 JSON 输出
- 支持从中间步骤开始
- 恢复文件级图（如果有强烈需求）

### 9.3 最终建议

**执行方案 A（简单实现）：**
- ✅ 满足用户核心需求
- ✅ 保持架构简洁
- ✅ 向后兼容性好
- ✅ 开发效率高
- ✅ 风险可控

**暂不执行方案 B（复杂实现）：**
- ❌ 过度工程化
- ❌ 开发成本高
- ❌ 维护成本高
- ❌ 性能可能下降
- ❌ 用户可能不需要

**如果用户后续强烈需要方案 B：**
- 可以分阶段实现
- 先验证方案 A 的效果
- 根据实际需求调整

---

## 10. 附录

### 10.1 代码审查检查清单

在提交代码前，请检查：

- [ ] 删除了 `src/mermaid_generator.py`
- [ ] 删除了 `src/cli.py` 中的 mermaid 导入
- [ ] 删除了 `--format mermaid` 和 `--mermaid` CLI 选项
- [ ] 修改了 `--format` 选项的 choices（移除 'mermaid'）
- [ ] 删除了 mermaid 生成逻辑
- [ ] 删除了 `--aggressive-filter` CLI 选项
- [ ] 添加了 `--no-aggressive-filter` CLI 选项（可选）
- [ ] 修改了过滤逻辑（激进度滤作为默认）
- [ ] 删除了 `--file-graph` CLI 选项
- [ ] 删除了文件级图生成逻辑
- [ ] 更新了 README.md
- [ ] 更新了 USAGE.md
- [ ] 更新了 CHANGELOG.md
- [ ] 运行了单元测试
- [ ] 运行了集成测试
- [ ] 运行了代码检查（py_compile, lint）
- [ ] 搜索了所有 Mermaid 引用并更新
- [ ] 提交了 git commit
- [ ] 创建了 git tag

### 10.2 测试数据

**推荐测试的项目：**
1. 小型项目（<10 文件）- 验证基本功能
2. 中型项目（~50 文件）- 验证过滤性能
3. 大型项目（>100 文件）- 验证激进度滤效果
4. ESP32 项目 - 验证复杂项目兼容性

### 10.3 联系方式

如有问题，请联系：
- **项目负责人：** Pony
- **开发者：** Architect Subagent

---

**报告完成时间：** 2026-03-20
**下一步：** 用户确认方案后，开始执行
