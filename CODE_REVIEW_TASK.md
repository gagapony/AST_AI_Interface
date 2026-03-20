# Clang-Call-Analyzer Code Review Task

## User Requirements

1. **Visualization**: Change tree diagram to force-directed graph
2. **Cleanup**: Project is messy - identify what to delete/simplify
3. **Whitelist question**: Now using preprocessing compile_commands.json logic (filter.cfg / --path), is the flag whitelist still needed?
4. **Documentation**: Delete useless documentation
5. **Deep review**: Read source code carefully, create feature table, identify keep/delete items
6. **After review**: User will commit code

## Analysis Instructions

### Step 1: Create Feature Table

Analyze ALL modules and create a table with:

| Module/Component | Purpose | Current Status | Keep? | Delete? | Notes |
|-------------------|---------|----------------|-------|--------|-------|
| ... | ... | ... | ... | ... | ... |

### Step 2: Whitelist Analysis

Analyze the flag whitelist system:
- `flag_whitelist.py` - filters compiler FLAGS for libclang compatibility
- `adaptive_flag_parser.py` - adaptive retry (full → minimal → no flags)
- `flag_filter_manager.py` - coordinates flag filtering

**Question**: Is this system still needed given:
- We now use `filter.cfg` / `--path` to pre-filter compile_commands.json entries
- Adaptive parser already tries multiple approaches

### Step 3: Documentation Cleanup

Analyze ALL .md files and categorize:
- Keep: README, INSTALL, QUICK_START, USAGE (user-facing docs)
- Review: PLAN, REQUIREMENTS (architecture docs - check if outdated)
- Delete: PHASE1_REPORT.md, PHASE2_REPORT.md, etc. (temporary implementation reports)

### Step 4: Visualization Update

Current visualizations:
- `mermaid_generator.py` - tree diagram (BT direction)
- `echarts_generator.py` - HTML with ECharts

Task: Change from tree to force-directed graph

## Expected Output

1. **Feature table** with clear keep/delete recommendations
2. **Whitelist analysis** - keep, simplify, or delete?
3. **Documentation cleanup list** - files to delete
4. **Visualization plan** - how to change to force-directed graph

## Output Format

Create a Markdown report with clear sections:
- Feature Analysis Table
- Whitelist System Analysis
- Documentation Cleanup Recommendations
- Visualization Update Plan
- Summary of Actions

