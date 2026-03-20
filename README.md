# clang-call-analyzer

A Python tool for analyzing C/C++ code and extracting function call relationships with Doxygen `@brief` documentation.

## Features

- Parse `compile_commands.json` for compilation flags
- Extract function definitions using libclang
- Parse Doxygen `@brief` tags from comments
- Build bidirectional call graph (parents/children)
- Output JSON with function metadata and relationships

## Installation

### Requirements

- Python 3.8+
- libclang (from LLVM/Clang)

### Install Dependencies

```bash
# Install Python dependencies
pip install -r requirements.txt

# Install libclang (Ubuntu/Debian)
sudo apt install libclang-dev

# Install libclang (Fedora)
sudo dnf install clang-devel

# Install libclang (macOS)
brew install llvm
```

### Version Compatibility

Ensure Python `clang` package version matches your system libclang:

```bash
# Check system libclang version
llvm-config --version

# Check Python clang package version
python -c "import clang; print(clang.cindex.conf.get_cxx_library_version())"
```

## Usage

### Quick Start (Recommended)

**Option 1: Use the standalone runner script (Python only)**

```bash
# From the project directory
cd /home/gabriel/.openclaw/code/clang-call-analyzer
python run.py -i /path/to/compile_commands.json -o output.json

# Or add to PATH for use anywhere
ln -s $(pwd)/run.py ~/.local/bin/clang-call-analyzer
clang-call-analyzer -i compile_commands.json -o output.json
```

**Option 2: Use Nix shell runner**

```bash
cd /home/gabriel/.openclaw/code/clang-call-analyzer
./clang-call-analyzer -i /path/to/compile_commands.json -o output.json
```

**Option 3: Use Python module directly**

```bash
cd /home/gabriel/.openclaw/code/clang-call-analyzer
python -m src.cli -i compile_commands.json -o output.json
```

See [USAGE.md](USAGE.md) for detailed usage instructions and common issues.

### Output Format

```json
[
  {
    "index": 0,
    "self": {
      "path": "/path/to/file.cpp",
      "lineRange": [1, 10],
      "name": "functionName",
      "qualifiedName": "functionName(int, int)",
      "brief": "Brief description from @brief tag"
    },
    "parents": [2, 3],
    "children": [4, 5]
  }
]
```

## Development

### Running Tests

**⚠️ Important:** Tests require libclang and must be run in nix-shell environment:

```bash
# Run all tests in nix-shell
nix-shell shell.nix --run 'python -m unittest discover tests/'

# Run specific test in nix-shell
nix-shell shell.nix --run 'python -m unittest tests.test_compilation_db'

# Or use pytest if available
nix-shell shell.nix --run 'pytest tests/'
```

If you encounter `ModuleNotFoundError: No module named 'clang'`, ensure you are running tests inside nix-shell.

### Project Structure

```
clang-call-analyzer/
├── src/
│   ├── cli.py              # Command-line interface
│   ├── compilation_db.py   # compile_commands.json parser
│   ├── ast_parser.py       # libclang AST parser
│   ├── function_extractor.py   # Function definition extraction
│   ├── doxygen_parser.py   # Doxygen @brief parser
│   ├── call_analyzer.py    # Call relationship analysis
│   ├── function_registry.py    # Function indexing
│   ├── relationship_builder.py # Call graph builder
│   └── json_emitter.py     # JSON output
├── tests/
│   ├── test_compilation_db.py
│   ├── test_doxygen_parser.py
│   ├── test_function_registry.py
│   └── test_integration.py
└── test_data/
    ├── compile_commands.json
    └── sample.cpp
```

## Limitations

- Macro-defined functions cannot be analyzed
- Function pointer calls are not resolved
- Virtual functions use static analysis only
- Template specializations require careful handling

## License

MIT
