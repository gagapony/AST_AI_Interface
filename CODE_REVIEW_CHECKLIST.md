# Code Review Execution Checklist

**Generated:** 2026-03-20
**Purpose:** Quick reference for executing code review recommendations

---

## 🚀 Priority 1: Delete Temporary Docs (Do First)

### Delete These 16 Files

```bash
cd /home/gabriel/.openclaw/code/clang-call-analyzer

rm PLAN.md PLAN_FILTER_CFG.md PLAN_GENERIC.md \
   REQUIREMENTS_FILTER_CFG.md REQUIREMENTS_GENERIC.md \
   PHASE1_IMPLEMENTATION_REPORT.md PHASE2_COMPLETE.md PHASE2_REPORT.md PHASE3_REPORT.md \
   ECHARTS_IMPLEMENTATION_REPORT.md ECHARTS_PHASE1_VERIFICATION.md \
   IMPLEMENTATION_COMPLETE.md IMPLEMENTATION_SUMMARY.txt \
   ARCHITECT_FIXES.md ARCHITECT_CHANGE_SUMMARY.md FIX_SUMMARY.md
```

**Estimated Time:** 5 minutes
**Risk:** ⬇️ Low

---

## 🎨 Priority 2: Update to Force-Directed Graph

### Step 1: Modify `echarts_templates.py`

**Location:** `src/echarts_templates.py`

**Find (in `APP_SCRIPT_TEMPLATE`):**
```javascript
const option = {
  series: [{
    type: 'graph',
    layout: 'none',  // ← CHANGE THIS
    // ...
  }]
};

function autoLayout() {
  // ... REMOVE THIS FUNCTION
}
```

**Replace with:**
```javascript
const option = {
  series: [{
    type: 'graph',
    layout: 'force',  // ← FORCE-DIRECTED
    force: {
      repulsion: 500,
      edgeLength: 100,
      gravity: 0.1,
      layoutAnimation: true,
      preventOverlap: true
    },
    draggable: true,
    roam: true,
    // ... rest of config
  }]
};

// autoLayout() function REMOVED
```

**Find (in `initGraph()`):**
```javascript
// Auto-fit layout after render
setTimeout(() => {
  autoLayout();
}, 100);
```

**Replace with:**
```javascript
// No auto-layout needed for force-directed graphs
```

### Step 2: Test ECharts Visualization

```bash
cd /home/gabriel/.openclaw/code/clang-call-analyzer
python -m src.cli -i /path/to/compile_commands.json -o callgraph.html -f html
```

### Step 3: Apply Same Changes to File Graph

**Location:** `src/file_graph_generator.py`

**Apply the exact same changes from Step 1 to the `APP_SCRIPT_TEMPLATE` in `file_graph_generator.py`**

### Step 4: Test File Graph

```bash
cd /home/gabriel/.openclaw/code/clang-call-analyzer
python test_file_graph.py
```

**Estimated Time:** 45 minutes
**Risk:** ⬇️ Low

---

## 🔧 Priority 3: Optional Optimizations (Do Later)

### Task A: Simplify Whitelist System

**Files to modify:**
- `src/flag_whitelist.py`
- `src/adaptive_flag_parser.py`
- `src/flag_filter_manager.py`

**Changes:**
1. Reduce flag categories from 6 to 3
2. Reduce blacklist from 50+ to 20 flags
3. Simplify statistics tracking

**Estimated Time:** 60 minutes
**Risk:** ⬇️ Low (optimization only)

### Task B: Consolidate Documentation

**Tasks:**
1. Review `FILE_GRAPH_IMPLEMENTATION.md`
2. Consolidate key info into `README.md` or `QUICK_START.md`
3. Delete `FILE_GRAPH_IMPLEMENTATION.md` if fully consolidated
4. Review `REQUIREMENTS.md` for outdated content

**Estimated Time:** 30 minutes
**Risk:** ⬇️ Low (documentation only)

### Task C: Add `--layout` CLI Option

**File to modify:** `src/cli.py`

**Add argument:**
```python
parser.add_argument(
    '--layout',
    type=str,
    choices=['tree', 'force'],
    default='force',
    help='Layout algorithm (default: force). Options: tree (hierarchical), force (force-directed)'
)
```

**Pass to generators:** Update `echarts_generator.py` and `file_graph_generator.py` to accept layout parameter

**Estimated Time:** 30 minutes
**Risk:** ⬇️ Low (feature addition)

---

## ✅ Pre-Commit Verification

After completing Priority 1 and 2:

```bash
cd /home/gabriel/.openclaw/code/clang-call-analyzer

# Run tests
python -m pytest tests/ -v

# Check for temporary files
ls -la *.md | grep -E "(PHASE|PLAN|IMPLEMENTATION|ARCHITECT|FIX)"

# Verify visualization works
xdg-open callgraph.html
xdg-open filegraph.html
```

---

## 📝 Commit Message Template

```
Code review cleanup: remove temporary docs, update visualization to force-directed graph

Changes:
- Deleted 16 temporary implementation reports (PLAN_*, PHASE_*, IMPLEMENTATION_*, etc.)
- Updated echarts_templates.py to use force-directed layout (layout: 'force')
- Updated file_graph_generator.py to use force-directed layout
- Removed autoLayout() functions (no longer needed with force layout)
- Added force configuration: repulsion=500, edgeLength=100, gravity=0.1

Benefits:
- Cleaned up documentation (removed ~150KB of temporary files)
- Improved visualization with organic, interactive force-directed graphs
- Better handling of complex relationships and cycles

See CODE_REVIEW_REPORT.md for full analysis.
```

---

## 📊 Summary

| Priority | Task | Time | Risk | Status |
|----------|------|------|------|--------|
| 1 | Delete 16 temporary docs | 5 min | ⬇️ Low | ⏳ Pending |
| 2 | Update to force-directed graph | 45 min | ⬇️ Low | ⏳ Pending |
| 3A | Simplify whitelist system | 60 min | ⬇️ Low | ⏳ Pending |
| 3B | Consolidate documentation | 30 min | ⬇️ Low | ⏳ Pending |
| 3C | Add --layout CLI option | 30 min | ⬇️ Low | ⏳ Pending |

**Total Priority 1-2:** 50 minutes
**Total All Tasks:** 170 minutes (2h 50m)

---

## 📚 Key Findings Summary

### Whitelist System: ✅ KEEP
- Not redundant - serves different purpose than preprocessing filter
- File-level filtering vs. flag-level filtering
- Essential for libclang compatibility
- Can be simplified (optional optimization)

### Documentation: 🗑️ DELETE 16 FILES
- Too many temporary implementation reports
- Keep 4 core docs: README, INSTALL, QUICK_START, USAGE
- Savings: ~150KB

### Visualization: 🎨 UPDATE TO FORCE-DIRECTED
- Simple config change in ECharts
- Better for complex relationships
- Organic, interactive layouts
- Estimated 45 minutes

---

**Full details in CODE_REVIEW_REPORT.md**
