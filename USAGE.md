# clang-call-analyzer

基于 `compile_commands.json` 的 C/C++ 函数调用关系分析工具。

## 快速开始

```bash
# 使用 run.sh（推荐，自动激活 nix-shell）
cd /home/gabriel/.openclaw/code/clang-call-analyzer
./run.sh -i /path/to/compile_commands.json -o output.json

# 详细日志
./run.sh -i compile_commands.json -o output.json -v info

# 直接使用 Python 模块（需要已安装依赖）
cd /home/gabriel/.openclaw/code/clang-call-analyzer
python -m src.cli -i /path/to/compile_commands.json -o output.json
```

## 功能

- ✅ 提取函数定义（所有 C/C++ 函数类型）
- ✅ 解析 Doxygen `@brief` 注释
- ✅ 构建函数调用关系（parents/children）
- ✅ 输出标准格式 JSON
- ✅ 支持跨文件调用

## 依赖

```bash
pip install clang>=16.0.0
```

## 输出格式

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

## 命令行选项

```
-i, --input           Path to compile_commands.json
-o, --output          Output file path
-f, --filter-cfg      Filter configuration file (INI format)
-p, --path            Filter: 只分析指定路径下的文件（递归）
--dump-filtered-db    Dump filtered compile_commands.json to file
--filter-func         Function name to filter graph by (qualified name)
-v, --verbose         Logging level (error, warning, info, debug)
--disable-retry       Disable adaptive retry parsing
```

## 路径过滤

### 单一路径过滤 (--path)

```bash
# 只分析 src/ 目录下的文件
./run.sh -p src/

# 只分析某个具体路径
./run.sh -p /path/to/project/specific/dir/

# 组合使用
./run.sh -p components/sensor/ -o sensor_calls.json -v info
```

### 多路径过滤 (--filter-cfg)

创建 `filter.cfg` 文件：

```ini
# Filter Configuration
# 每行一个过滤路径
# 以 # 开头的行是注释（忽略）

# 相对路径（相对于 compile_commands.json 所在目录）
src/
include/
lib/

# 绝对路径（也可以使用绝对路径）
# /home/user/project/vendor/mylib/

# 空行会被忽略

# 添加更多路径
tests/
components/
```

使用 filter.cfg：

```bash
# 使用 filter.cfg 进行过滤
./run.sh -f filter.cfg -o output.json -v info

# 组合使用：导出过滤后的编译数据库
./run.sh -f filter.cfg --dump-filtered-db compile_commands_simple.json

# 指定输入和输出
./run.sh -i /path/to/compile_commands.json -f filter.cfg -o output.json
```

### 优先级规则

过滤参数的优先级（从高到低）：

1. `--filter-cfg` (-f) - 使用配置文件中的路径列表
2. `--path` (-p) - 使用单一路径
3. 无过滤参数 - 分析所有文件

**注意：** `--filter-cfg` 和 `--path` 不能同时使用（互斥参数）。

### 性能对比

在 ESP32 项目上的性能提升：

| 指标 | 无过滤 | 使用 filter.cfg | 提升 |
|------|--------|----------------|------|
| 编译单元 | 206 | 10 | 95% ↓ |
| 函数数量 | ~15,828 | 95 | 99% ↓ |
| 分析时间 | >180s | ~30s | 80%+ ↓ |

### 导出过滤后的数据库

```bash
# 导出过滤后的 compile_commands.json 用于调试
./run.sh -f filter.cfg --dump-filtered-db filtered_db.json

# filtered_db.json 只包含过滤后的编译单元
# 可以检查过滤配置是否正确
```

## 高级用法：函数级过滤

### 查看特定函数的调用图

使用 `--filter-func` 选项生成只包含与特定函数相关的函数的子图：

```bash
python -m src.cli \
  --filter-func "ButtonDriver::init" \
  --format html \
  --output button_driver_graph
```

这有助于专注于特定的功能或组件。

### 工作原理

过滤功能会：

1. 查找目标函数（使用完整的限定名称）
2. 执行双向图遍历：
   - **向上遍历**：包含所有调用目标函数的函数（父函数）
   - **向下遍历**：包含所有被目标函数调用的函数（子函数）
3. 递归包含所有通过这些连接可达的函数
4. 重新索引节点以保持 JSON 结构一致性

### 示例场景

#### 场景 1：分析 main 函数

```bash
# 分析从 main 函数开始的整个调用树
python -m src.cli -i compile_commands.json --filter-func "main" --format html

# 输出：
# - filegraph_main.json
# - filegraph_main.html
```

#### 场景 2：分析带命名空间的函数

```bash
# 分析 C++ 命名空间中的特定函数
python -m src.cli --filter-func "SensorManager::calibrate()" --format html
```

#### 场景 3：分析重载函数

```bash
# 对于重载函数，使用完整的限定名称（包括参数类型）
python -m src.cli --filter-func "processData(int)" --format html
```

### 可视化特性

生成的 HTML 可视化具有以下特性：

- **目标高亮**：目标函数节点用红色高亮显示，便于识别
- **交互式图形**：可以使用鼠标拖动节点、缩放和平移
- **工具提示**：悬停显示函数详细信息（名称、路径、调用计数）
- **双向关系**：同时显示调用者（parents）和被调用者（children）

### 组合使用

#### 与路径过滤组合

```bash
# 结合路径过滤和函数过滤
# 只分析 src/ 目录中与 "main" 函数相关的函数
python -m src.cli \
  --filter-cfg filter.cfg \
  --filter-func "main" \
  --format html
```

#### 与自定义输出路径组合

```bash
# 指定自定义输出路径
python -m src.cli \
  --filter-func "NetworkManager::connect" \
  --output network_graph \
  --format html

# 输出：
# - network_graph.json
# - network_graph.html
```

### 错误处理

如果指定的函数不存在：

```bash
$ python -m src.cli --filter-func "nonexistent_function" --format html

ERROR: Function 'nonexistent_function' not found in graph
```

在这种情况下，不会生成任何输出文件。

### 性能考虑

对于大型项目：

- **图遍历**：使用广度优先搜索（BFS）进行高效遍历
- **查找映射**：预构建名称到索引的映射以实现 O(1) 查找
- **内存使用**：过滤操作的内存开销通常 < 20% 相比于完整图生成

### 最佳实践

1. **使用完整的限定名称**：包含命名空间和参数类型（对于重载函数）
2. **先验证函数名称**：使用 `--verbose debug` 查找准确的函数名称
3. **保存输出文件**：为不同的分析使用不同的输出路径
4. **检查可视化**：在 HTML 可视化中验证过滤结果

### 调试技巧

#### 查找准确的函数名称

```bash
# 使用详细日志查看所有函数名称
python -m src.cli -i compile_commands.json --verbose debug --format json > output.json

# 然后搜索 JSON 文件以查找目标函数
grep "qualified_name" output.json
```

#### 验证过滤结果

```bash
# 检查过滤后的 JSON 文件中的函数数量
python -c "import json; print(len(json.load(open('filegraph_main.json'))))"

# 与完整图进行比较
python -c "import json; print(len(json.load(open('output.json'))))"
```

### 常见问题

**Q: 为什么函数名称在输出文件中被修改？**
A: 特殊字符（如 `/`、`:`、`(`、`)`、`,`）会被下划线替换以创建安全的文件名。

**Q: 可以过滤多个函数吗？**
A: 当前版本不支持。一次只能指定一个目标函数。

**Q: 过滤是否支持模板函数？**
A: 是的，使用完整的模板名称，包括模板参数。

**Q: 如何只查看调用者或只查看被调用者？**
A: 当前版本执行双向遍历。在可视化中，您可以根据需要关注 parents 或 children。

## 文档

- `REQUIREMENTS.md` - 功能需求
- `PLAN.md` - 技术方案
- `INSTALL.md` - 安装指南
