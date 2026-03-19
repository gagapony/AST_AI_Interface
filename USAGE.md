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
-i, --input    Path to compile_commands.json
-o, --output   Output file path
-p, --path     Filter: 只分析指定路径下的文件（递归）
-v, --verbose  Logging level (error, warning, info, debug)
```

## 路径过滤示例

```bash
# 只分析 src/ 目录下的文件
./run.sh -p src/

# 只分析某个具体路径
./run.sh -p /path/to/project/specific/dir/

# 组合使用
./run.sh -p components/sensor/ -o sensor_calls.json -v info
```

## 文档

- `REQUIREMENTS.md` - 功能需求
- `PLAN.md` - 技术方案
- `INSTALL.md` - 安装指南
