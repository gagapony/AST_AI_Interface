# REQUIREMENTS_FILTER_CFG.md - Filter Configuration Support

## Overview

**Goal:** Add flexible filter configuration via `filter.cfg` (INI format) to improve preprocessing efficiency.

---

## Functional Requirements

### R1: Filter Configuration File
- **R1.1:** Support `filter.cfg` in INI format
- **R1.2:** Multiple filter paths supported (one per line)
- **R1.3:** Support both relative and absolute paths
- **R1.4:** Support comments (lines starting with `#`)
- **R1.5:** Empty lines are ignored

### R2: Compile Database Filtering
- **R2.1:** Read `compile_commands.json`
- **R2.2:** Filter compilation units to those within filter paths
- **R2.3:** Only analyze files in filter scope
- **R2.4:** Skip files outside filter scope (don't parse)
- **R2.5:** Generate simplified compile_commands_simple.json (debug output)

### R3: AST Traversal Optimization
- **R3.1:** During AST traversal, check if cursor is in filter scope
- **R3.2:** Skip AST nodes from outside filter scope
- **R3.3:** Only extract function definitions from within filter scope
- **R3.4:** Do not record external function calls (no `external_calls` field)

### R4: CLI Parameters
- **R4.1:** Preserve `--path, -p` parameter (backward compatible)
- **R4.2:** Add `--filter-cfg, -f` parameter to read filter.cfg
- **R4.3:** Add `--dump-filtered-db` parameter to dump compile_commands_simple.json
- **R4.4:** Priority: `--filter-cfg` → `--path` → auto-detect

---

## Configuration Format

### filter.cfg Example

```ini
# Filter Configuration
# Each line is a filter path (relative or absolute)
# Lines starting with # are comments

src/
include/
/home/user/project/lib/
```

### Priority Order

1. If `--filter-cfg` specified: use paths from filter.cfg
2. If `--path` specified: use single path
3. If neither specified: analyze all files (no filtering)

---

## Output Format

### compile_commands_simple.json (Debug Output)

Same format as compile_commands.json, but with filtered entries.

### Final JSON Output

No `external_calls` field. Same format as before.

---

## Non-Functional Requirements

### N1: Backward Compatibility
- **N1.1:** Existing `--path` parameter still works
- **N1.2:** No breaking changes to output JSON format
- **N1.3:** Existing scripts continue to work

### N2: Performance
- **N2.1:** Parse time reduced by 80-90%
- **N2.2:** Memory usage reduced by 80-90%
- **N2.3:** Function count in output: ~95-200 (vs 15,828)

### N3: Debugging
- **N3.1:** `--dump-filtered-db` dumps filtered compilation database
- **N3.2:** Logging shows number of filtered units
- **N3.3:** Logging shows files skipped during AST traversal

---

## Acceptance Criteria

1. **AC1:** filter.cfg in INI format works correctly
2. **AC2:** Multiple filter paths supported
3. **AC3:** `--path` parameter preserved and works
4. **AC4:** AST traversal skips files outside filter scope
5. **AC5:** Output contains only functions in filter scope
6. **AC6:** No `external_calls` field in output
7. **AC7:** `--dump-filtered-db` dumps compile_commands_simple.json
8. **AC8:** Performance improved (parse time < 10s for ESP32 project)
9. **AC9:** Backward compatible (existing scripts work)
10. **AC10:** Debug interface works (can view filtered database)
