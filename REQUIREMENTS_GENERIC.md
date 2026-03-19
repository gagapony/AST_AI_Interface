# REQUIREMENTS_GENERIC.md - Generalized Flag Handling

## Overview

**Problem:** Current implementation filters specific flags for ESP32/RISC-V projects (e.g., `-march=rv32imc`, `-nostartfiles`), which is project-specific and not maintainable.

**Goal:** Make clang-call-analyzer **universal** - automatically skip unsupported flags, focus on extracting call relationships and function metadata.

---

## Functional Requirements

### G1: Robust Flag Filtering
- **G1.1:** Parse compilation command flags and pass them to libclang
- **G1.2:** If libclang rejects a flag during parsing, detect and log it
- **G1.3:** Re-parse with filtered flags (remove problematic flags)
- **G1.4:** Use whitelist-based approach: only pass known-compatible flags by default
- **G1.5:** Provide "best effort" parsing: extract what's possible, skip what fails

### G2: Known-Safe Flag Whitelist
Default whitelist of flags that libclang supports:
- **G2.1:** Include paths: `-I`, `-isystem`
- **G2.2:** Macro definitions: `-D`
- **G2.3:** Language standard: `-std=c++11`, `-std=gnu++11`, etc.
- **G2.4:** Warning suppressions: `-Wno-*` (some of them)
- **G2.5:** Target-specific flags: `-target` (if specified)

### G3: Blacklist (Always Skip)
Flags that libclang NEVER supports:
- **G3.1:** Output files: `-o`
- **G3.2:** Compilation stages: `-c`
- **G3.3:** Linker flags: `-l`, `-L`
- **G3.4:** Architecture flags: `-march=`, `-mtune=`, `-mabi=`
- **G3.5:** Linker options: `-nostartfiles`, `-shared`, `-static`
- **G3.6:** Build artifacts: `.o` files
- **G3.7:** Optimization flags: `-O`, `-Os`, `-O2`, `-O3`

### G4: Adaptive Retry Strategy
When parsing fails:
- **G4.1:** Log the error with specific flag if identifiable
- **G4.2:** Try parsing again with minimal flags (only include paths and macros)
- **G4.3:** If still fails, try with no flags (just the file itself)
- **G4.4:** Track which flags cause failures and skip them for subsequent files

### G5: Focus on Core Functionality
- **G5.1:** Prioritize extracting function definitions
- **G5.2:** Prioritize building call relationships
- **G5.3:** Doxygen comment extraction is secondary (can fail gracefully)
- **G5.4:** Missing headers should not prevent function extraction from main file

---

## Non-Functional Requirements

### NG1: Platform Agnostic
- **NG1.1:** Work for any C/C++ project (x86, ARM, RISC-V, ESP32, Arduino, etc.)
- **NG1.2:** No hard-coded project-specific logic
- **NG1.3:** No assumptions about toolchain paths

### NG2: Configurable Whitelist/Blacklist
- **NG2.1:** Users can override default whitelist via config file
- **NG2.2:** Users can add custom flags to whitelist
- **NG2.3:** Default configuration works for 90% of projects

### NG3: Progressive Enhancement
- **NG3.1:** First pass: try with all compatible flags
- **NG3.2:** Second pass: try with minimal flags
- **NG3.3:** Third pass: try with no flags
- **NG3.4:** Extract as much as possible at each stage

---

## Acceptance Criteria

1. **AC1:** Works on ESP32/RISC-V projects WITHOUT hardcoding project-specific flags
2. **AC2:** Works on standard Linux C/C++ projects
3. **AC3:** Works on Arduino projects
4. **AC4:** Works on embedded ARM Cortex-M projects
5. **AC5:** When a flag causes parsing failure, automatically retry without it
6. **AC6:** Logs which flags were skipped and why
7. **AC7:** Extracts function calls and definitions even if some headers fail to parse
8. **AC8:** No project-specific code in compilation_db.py
