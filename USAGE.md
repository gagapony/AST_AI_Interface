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

## 文档

- `REQUIREMENTS.md` - 功能需求
- `PLAN.md` - 技术方案
- `INSTALL.md` - 安装指南
