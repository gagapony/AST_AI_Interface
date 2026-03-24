# Changelog

## [Unreleased]

### New Features

#### 1. Local ECharts Support
- HTML files now use local `echarts.min.js` instead of CDN
- ECharts library is bundled with the package (`src/echarts.min.js`)
- Automatically copied to output directory when generating HTML
- Falls back to CDN if bundled file is missing (requires internet)

**Benefits:**
- Faster loading (no network dependency)
- Works offline
- Self-contained HTML files

**Usage:**
```bash
# HTML generation automatically uses local echarts.min.js
./run.sh --format html -o output
# Output: output/output.html + output/echarts.min.js
```

---

#### 2. --filter-func: Exact Match with Fallback

**Matching Strategy (Strict Two-Tier):**
1. **Tier 1**: Exact match on `qualified_name` (highest priority)
2. **Tier 2**: Exact match on `name` (fallback only if Tier 1 fails)

**No fuzzy matching** - only exact matches accepted.

**Example:**

Function in graph:
```json
{
  "name": "print_result",
  "qualified_name": "print_result::(const char *, int)"
}
```

Matching behavior:
```bash
# Tier 1: Exact qualified_name match
./run.sh --filter-func "print_result::(const char *, int)"
# ✅ Matches exactly

# Tier 2: Exact name match (fallback)
./run.sh --filter-func "print_result"
# ✅ Matches name field

# No match
./run.sh --filter-func "print"
# ❌ Error: Function 'print' not found
```

**Notes:**
- For overloaded functions, use full `qualified_name` to be specific
- When multiple functions share the same `name`, the first match is returned
- No multi-match warnings (unlike fuzzy matching approach)

---

### Improvements

#### Path Slice Algorithm
- Replaced BFS subgraph expansion with path slice approach
- Only includes nodes on call paths, not siblings/cousins
- Significantly reduces filtered graph size

**Before (BFS):**
```
Input: filter for "Target" (which is called by Root with 99 siblings)
Output: 5000+ nodes (entire graph)
```

**After (Path Slice):**
```
Input: filter for "Target"
Output: 50 nodes (only call paths)
```

---

## [v1.0.0] - Initial Release

### Core Features
- C/C++ function call graph analysis
- JSON and HTML output formats
- File-level graph visualization with ECharts
- Interactive HTML with search, themes, export features
