# Architecture Redesign Summary

## Purpose
Re-architect clang-call-analyzer to support library filtering and cross-platform compatibility for embedded systems (Linux embedded, MCU, ESP32, NixOS).

## Key Changes

### 1. New Functional Requirements (REQUIREMENTS.md)

#### R2: Library and File Filtering
- Filter system libraries (e.g., `/usr/include/`, `/usr/lib/`, `/nix/store/`)
- Filter kernel libraries (Linux kernel source code)
- Filter external/third-party libraries (e.g., opencv, esp-idf, framework-arduinoespressif32)
- Auto-detect system library paths from compilation flags
- Support user-configurable whitelist/blacklist via configuration file
- Support command-line overrides for whitelist/blacklist
- Provide flexible path matching (prefix, glob, regex patterns)

#### R4: File Filtering and Validation
- Apply whitelist before analyzing files
- Apply blacklist to exclude filtered paths
- Auto-detect project root from compile_commands.json directory
- Default to common source directories (src/, lib/, include/, app/)
- Log skipped files with reason (system lib, external lib, not in whitelist)

#### R9: Cross-Platform Compatibility
- Support Linux embedded development environments
- Support MCU embedded development (ARM Cortex-M, etc.)
- Support ESP32 development (RISC-V architecture, Arduino framework)
- Support NixOS environment with nix store paths
- Auto-detect compiler environment from compile_commands.json flags
- No hardcoded paths or platform-specific assumptions
- Graceful degradation: continue processing if a file fails to parse

### 2. New Non-Functional Requirements (REQUIREMENTS.md)

#### N6: Filtering and Configuration
- Support YAML configuration file (`clang-call-analyzer.yml`) in project root
- Configuration options: whitelist, blacklist, auto_detect_paths, log_level
- Command-line options override configuration file
- Provide sensible defaults for common project structures
- Auto-detect system library paths from compiler flags

### 3. New Constraints (REQUIREMENTS.md)

#### C3: Platform Independence
- No hardcoded platform-specific paths (except for common defaults)
- Detect system paths dynamically from compile_commands.json
- Work across Linux, macOS, and Windows (if applicable)

#### C4: Minimal Dependencies
- Only libclang (via `clang` Python package) and standard library
- Avoid external YAML parsers if possible (use `pyyaml` only for config)
- Keep footprint small for embedded environments

### 4. New Modules (PLAN.md)

#### Module 1: `config_loader.py` - Configuration Management
- Load YAML configuration file from project root
- Parse whitelist/blacklist settings
- Merge with CLI arguments (CLI takes precedence)
- Provide default configuration

#### Module 2: `path_filter.py` - Path Filtering Logic
- Apply whitelist/blacklist to file paths
- Support multiple matching modes (prefix, glob, regex)
- Determine if a path should be analyzed

#### Module 3: `file_filter.py` - File Filtering with System Path Detection
- Auto-detect system library paths from compilation flags
- Combine with PathFilter for comprehensive filtering
- Provide detailed skip reasons for logging

#### Module 4: `path_extractor.py` - Path Extraction from Compilation Flags
- Extract include paths from compilation flags
- Extract library paths from compilation flags
- Support cross-compiler flags (e.g., ARM, RISC-V)

### 5. Updated Modules (PLAN.md)

#### Module 6: `compilation_db.py` - Enhanced
- Added `get_all_include_paths()` to collect all -I paths
- Added `get_all_library_paths()` to collect all -L paths

#### Module 7: `ast_parser.py` - Enhanced
- Added `ParseResult` class for better error handling
- Added try-catch for graceful degradation
- Support cross-platform compilation (ARM, RISC-V, etc.)

#### Module 8: `function_extractor.py` - Enhanced
- Added `file_filter` parameter
- Added `_should_extract_from_file()` method
- Only extract from files that pass the filter

### 6. Enhanced CLI Options (PLAN.md)

```
--config, -c   Path to config file (default: clang-call-analyzer.yml)
--whitelist    Paths to analyze (comma-separated)
--blacklist    Paths to exclude (comma-separated)
--no-auto-detect   Disable auto-detection of system paths
--show-skipped     Show skipped files and reasons
```

### 7. Cross-Platform Support Strategy (PLAN.md)

#### Supported Platforms
| Platform | Compiler | Architecture | Specific Handling |
|----------|----------|--------------|-------------------|
| Linux Embedded | gcc/clang | ARM, x86 | Auto-detect /usr/include, /usr/lib |
| MCU Embedded | arm-none-eabi-gcc | ARM Cortex-M | Pass all -I and -D flags as-is |
| ESP32 | xtensa-esp32-elf-gcc | Xtensa | Pass all Arduino framework flags |
| ESP32-S3 | riscv32-esp-elf-gcc | RISC-V | Pass all ESP-IDF flags |
| NixOS | gcc/clang | x86_64 | Auto-detect /nix/store/ paths |
| macOS | clang | x86_64, arm64 | Auto-detect /System/Library/Frameworks |

#### Auto-Detection Logic
- System library paths: `/usr/include/`, `/usr/lib/`, `/nix/store/`, etc.
- External library patterns: `third_party/`, `external/`, `vendor/`, `deps/`, `.arduino/`, `components/`

### 8. Updated Error Handling (PLAN.md)

#### Filter-Level Handling
- Log each filtered file with reason (system lib, external lib, not in whitelist)
- Provide option to show/hide filtered files (--show-skipped)
- Count filtered files for summary report

#### Error Recovery
- If a file fails to parse, log the error and continue with next file
- If libclang is not available, provide clear error message
- If config file is malformed, use defaults and log warning

### 9. Configuration Examples (PLAN.md)

Added 5 example configurations:
1. Default Configuration (Minimal)
2. ESP32 Project
3. NixOS Project
4. MCU Embedded Project
5. Custom Whitelist Only (No Auto-Detection)

### 10. Updated Dependencies (PLAN.md)

Added `pyyaml>=6.0` for configuration file parsing.

### 11. Updated File Structure (PLAN.md)

Added new files:
- `clang-call-analyzer.yml` (Example config file)
- `src/config_loader.py`
- `src/path_filter.py`
- `src/file_filter.py`
- `src/path_extractor.py`
- `tests/test_config_loader.py`
- `tests/test_path_filter.py`
- `tests/test_file_filter.py`
- `test_data/clang-call-analyzer.yml`
- `test_data/platforms/esp32/`
- `test_data/platforms/mcu/`
- `test_data/platforms/nixos/`

### 12. Updated Development Steps (PLAN.md)

Added Phase 5: Cross-Platform Testing
- Test on Linux embedded project (ARM)
- Test on MCU embedded project (ARM Cortex-M)
- Test on ESP32 project (Xtensa/RISC-V)
- Test on NixOS environment
- Test on standard Linux project

### 13. Updated Acceptance Criteria (REQUIREMENTS.md)

Added 6 new acceptance criteria (AC8-AC13):
- AC8: Filters system libraries and external libraries correctly
- AC9: Supports YAML configuration file with whitelist/blacklist
- AC10: Works on multiple platforms (Linux embedded, MCU, ESP32, NixOS)
- AC11: Auto-detects system library paths from compiler flags
- AC12: Gracefully handles files that fail to parse or are filtered
- AC13: Provides clear logging for skipped files and reasons

## Design Decisions

1. **Separation of Concerns:** Created separate modules for configuration, path filtering, file filtering, and path extraction.
2. **Auto-Detection First:** Auto-detect system paths from compile_commands.json, with manual overrides available.
3. **Graceful Degradation:** If a file fails to parse or is filtered, log the reason and continue.
4. **Platform Independence:** No hardcoded paths; all paths detected dynamically from compilation flags.
5. **User Control:** Configuration file + CLI overrides give users full control over what is analyzed.
6. **Minimal Dependencies:** Only libclang and Python standard library (plus pyyaml for config).

## Next Steps

1. Linus Reviewer reviews the updated REQUIREMENTS.md and PLAN.md
2. Architect makes any necessary adjustments based on feedback
3. Developer implements the new modules and updates existing modules
4. Auditor tests cross-platform compatibility
5. Integration testing on real projects (ESP32, NixOS, MCU, etc.)
