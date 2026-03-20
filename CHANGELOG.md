# Changelog

All notable changes to clang-call-analyzer will be documented in this file.

## [Unreleased]

### Added

#### Code Quality Improvements
- **Type safety:** Fixed type hints in `compile_commands_simplifier.py` to use `Optional[logging.Logger]`
- **None handling:** Added validation in `echarts_generator.py` to prevent using `None` as dict key
- **Documentation:** Added nix-shell requirement for running tests

### Changed

#### Filter Configuration System
- **New CLI parameter:** `--filter-cfg` (-f) - Load filter configuration from INI file
- **New CLI parameter:** `--dump-filtered-db` - Dump filtered compile_commands.json to specified file
- **filter.cfg support:** Simple INI format file for specifying multiple filter paths
- **Compilation database pre-filtering:** Filter compilation units before AST parsing
- **Scope-aware AST traversal:** Skip functions outside filter scope during analysis
- **Performance improvements:** 80-90% reduction in analysis time for large projects

### Changed

#### Path Resolution
- Filter paths are now resolved relative to compile_commands.json directory (project root)
- Previously resolved relative to current working directory

### Fixed

#### Bug Fixes
- Fixed import statements in `ast_parser.py`, `flag_filter_manager.py`, and `adaptive_flag_parser.py` to use relative imports
- Fixed FilterMode references in `cli.py` to use imported enum instead of nested attribute
- Fixed path normalization to respect project root for relative paths in filter.cfg
- Fixed type hint in `compile_commands_simplifier.py` line 15 to properly declare optional logger parameter
- Fixed None handling in `echarts_generator.py` to validate `func_index` before using as dict key
- Removed obsolete `--no-aggressive-filter` check in `cli.py` (replaced by CompileCommandsSimplifier)
- Removed temporary files `cli_new.py` and `cli_output_gen.py` from source tree

## [1.0.0] - 2024-03-19

### Initial Release

### Features
- Extract function definitions from C/C++ codebase using compile_commands.json
- Parse Doxygen `@brief` comments
- Build function call relationships (parents/children)
- Output standard JSON format
- Support cross-file call analysis
- Adaptive flag filtering for libclang compatibility
- Path filtering with `--path` parameter

---

## Filter Configuration Usage Examples

### Using filter.cfg

Create a `filter.cfg` file in your project:

```ini
# Filter Configuration
# Lines starting with # are comments

# Main application source code
src/
include/

# Custom components
components/custom-component/
```

Run analysis:

```bash
clang-call-analyzer --filter-cfg filter.cfg
```

### Using single path filter

```bash
clang-call-analyzer --path src/
```

### Dump filtered database

```bash
clang-call-analyzer --filter-cfg filter.cfg --dump-filtered-db compile_commands_simple.json
```

### Performance Comparison (ESP32 Project)

| Metric | Without Filter | With Filter | Improvement |
|--------|----------------|-------------|-------------|
| Compilation units | 206 | 10 | 95% reduction |
| Functions analyzed | ~15828 | 95 | 99% reduction |
| Analysis time | >180s | ~30s | 80%+ faster |

---

## Upgrade Notes

### Version 1.0.0 → Unreleased

**Breaking Changes:** None

**Migration Guide:**

If you were using `--path` for filtering, it continues to work unchanged:

```bash
# Before (still works)
clang-call-analyzer --path src/

# New alternative (multiple paths)
clang-call-analyzer --filter-cfg filter.cfg
```

**Filter path resolution changed:**

- **Before:** Relative paths in filter.cfg resolved to current working directory
- **After:** Relative paths resolved to compile_commands.json directory (project root)

This change ensures consistent behavior regardless of where you run the command.
