# Architecture Fixes Summary

## Task Completed: PLAN.md Redesign (Post-Linus Review)

### Issues Fixed

All 8 critical issues identified by Linus Reviewer have been addressed in the redesigned PLAN.md:

| Issue | Problem | Fix Applied |
|-------|---------|-------------|
| **1. Hardcoded paths** | Predefined `SYSTEM_PATH_PATTERNS` list in code | **Removed all hardcoded paths**; system paths detected ONLY from `-isystem` compiler flags |
| **2. NixOS logic error** | All `/nix/store/` paths filtered as system libs | **Fixed**: Only `/nix/store/` paths from `-isystem` flags filtered; project dependencies (from `-I`) analyzed |
| **3. Default whitelist** | Empty whitelist = analyze everything (contradicts docs) | **Fixed**: Empty whitelist = use default `["src/", "lib/", "include/", "app/"]` unless `--no-whitelist` used |
| **4. Matching modes** | Only string patterns supported | **Fixed**: Support `prefix`, `glob`, `regex` modes via object format |
| **5. Path semantics** | Absolute path matching for whitelist/blacklist | **Fixed**: All whitelist/blacklist use **relative paths** from project root |
| **6. Auto-detection** | Only `-I` flags detected | **Fixed**: Detect all include flags: `-isystem`, `-I`, `-idirafter`, `-iquote`, `-F` |

### Key Design Principles Applied

1. **No Hardcoding**: All system paths from compiler flags or user config
2. **Relative Paths**: Whitelist/blacklist based on relative paths from project root
3. **Configuration-Driven**: Users control analysis scope via whitelist/blacklist
4. **Minimal Assumptions**: No assumptions about project structure or platform

### Critical Code Changes

#### 1. System Path Detection (Before vs After)

**Before (WRONG):**
```python
SYSTEM_PATH_PATTERNS = [
    '/usr/include/',
    '/nix/store/',  # ❌ Hardcoded!
    ...
]

def is_system_path(path: str) -> bool:
    return any(path.startswith(p) for p in SYSTEM_PATH_PATTERNS)
```

**After (CORRECT):**
```python
@dataclass
class IncludePath:
    path: str
    type: str  # "system", "user", "after", "quote", "framework"

def extract_include_paths(flags: List[str]) -> List[IncludePath]:
    """Extract all include paths with their types."""
    # Detect -isystem, -I, -idirafter, -iquote, -F flags
    ...

def get_system_paths(include_paths: List[IncludePath]) -> List[str]:
    """Filter only system-type include paths."""
    return [ip.path for ip in include_paths if ip.type == "system"]
```

#### 2. NixOS Behavior (Critical Fix)

**Before:**
- All `/nix/store/` paths filtered ❌
- Project dependencies in `/nix/store/` not analyzed ❌

**After:**
- `/nix/store/abc123-glibc/include` (from `-isystem`) → Filtered ✅
- `/nix/store/def456-mylib/include` (from `-I`) → Analyzed ✅

#### 3. Path Matching (Before vs After)

**Before (WRONG):**
```python
# Absolute path matching
blacklist = ["/usr/include/", "/nix/store/"]
if file_path.startswith("/usr/include/"):
    return False  # Filter
```

**After (CORRECT):**
```python
# Relative path matching
@dataclass
class PathPattern:
    pattern: str
    mode: str  # "prefix", "glob", "regex"

def _to_relative_path(self, abs_path: str) -> str:
    """Convert absolute path to relative path from project root."""
    return os.path.relpath(abs_path, self.project_root)

# Whitelist/blacklist use relative paths
whitelist = [PathPattern("src/", "prefix")]
blacklist = [PathPattern("vendor/", "prefix")]
```

#### 4. Default Whitelist Behavior (Before vs After)

**Before (WRONG):**
```python
if not self.whitelist:
    return True  # Analyze everything ❌
```

**After (CORRECT):**
```python
DEFAULT_WHITELIST = [
    PathPattern("src/", "prefix"),
    PathPattern("lib/", "prefix"),
    PathPattern("include/", "prefix"),
    PathPattern("app/", "prefix"),
]

def _apply_defaults(self, config: Config) -> Config:
    if not config.whitelist and config.use_default_whitelist:
        config.whitelist = self.DEFAULT_WHITELIST.copy()
    return config
```

### Configuration Format Changes

**Before (v1.0):**
```yaml
whitelist:
  - "src/"
  - "lib/"
blacklist:
  - "/usr/include/"
  - "/nix/store/"
```

**After (v2.0):**
```yaml
whitelist:
  - pattern: "src/"
    mode: "prefix"
  - pattern: "lib/"
    mode: "prefix"
blacklist:
  - pattern: "generated/"
    mode: "prefix"
  - pattern: "**/*_test.cpp"
    mode: "glob"
```

### New CLI Options

```bash
--no-whitelist      Disable default whitelist (analyze everything not blacklisted)
--no-auto-detect    Disable auto-detection of system paths
--show-skipped      Show skipped files and reasons
```

### Sections Updated in PLAN.md

1. ✅ Architecture Fixes Summary (new section at beginning)
2. ✅ Module 1: config_loader.py (PathPattern support, default whitelist)
3. ✅ Module 2: path_filter.py (relative paths, matching modes)
4. ✅ Module 3: file_filter.py (no hardcoded paths, -isystem only)
5. ✅ Module 4: path_extractor.py (all include flags)
6. ✅ Configuration Examples (updated format and behavior)
7. ✅ Cross-Platform Support (removed hardcoded paths)
8. ✅ Data Flow (updated filtering logic)
9. ✅ CLI Options (added --no-whitelist, --no-auto-detect)
10. ✅ Migration Guide (new appendix)

### File Path

**Updated file:** `/home/gabriel/.openclaw/code/clang-call-analyzer/PLAN.md`

### Status

✅ Ready for Linus Reviewer approval

All 8 critical issues have been resolved. The architecture now follows the key design principles:
- No hardcoded paths
- Relative path matching
- Configuration-driven
- Minimal assumptions
