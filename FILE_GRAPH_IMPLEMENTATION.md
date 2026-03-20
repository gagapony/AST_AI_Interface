# File-Level Graph Implementation Report

## Overview

Successfully implemented a pure file-level relationship graph for the clang-call-analyzer project. The graph displays files as nodes and file-to-file call relationships as edges.

## Implementation Details

### Core Files Created

1. **`src/file_graph_generator.py`** (595 lines)
   - New generator class for file-level graphs
   - Aggregates functions by file path
   - Builds file-to-file call relationships
   - Creates file nodes and edges with proper labels

2. **`test_file_graph.py`**
   - Test script to generate file-level graph
   - Loads output.json and generates filegraph.html

3. **`verify_file_graph.py`**
   - Verification script that checks all requirements
   - Validates nodes, edges, and labels
   - Confirms requirement compliance

### Generated Output

**`filegraph.html`** (779 lines, 18KB)
- Interactive ECharts visualization
- File nodes with function count info
- File-to-file edges with call labels
- Search functionality
- Theme switching (default, dark, light)
- Export to PNG/SVG
- Auto-layout (tree-style from left to right)

## Features

### Nodes
- **10 file nodes** generated from ESP32 project
- Each node displays:
  - File name (e.g., `ControlSystem.cpp`)
  - Function count
  - Outgoing call count
  - Incoming call count
- Node size based on function count (30-80px range)
- Categories assigned based on file path:
  - Control (2 files)
  - Network (1 file)
  - System (4 files)
  - Default (3 files)

### Edges
- **14 file-to-file relationships**
- Edge labels format: `functionName @ sourceFile:lineNumber`
- Example: `init @ ControlSystem.cpp:50`
- Edge width based on call frequency

### Interactive Features
- **Search**: Filter files by name
- **Themes**: Default, dark, light
- **Export**: PNG and SVG formats
- **Auto-layout**: Tree-style arrangement
- **Draggable nodes**: Manual positioning
- **Tooltips**: Detailed file and call information

## Requirements Verification

✅ **REQUIREMENT 1**: Only file nodes (no function nodes)
- All 10 nodes are file nodes (.cpp files)

✅ **REQUIREMENT 2**: All edges are between file nodes
- All 14 edges connect file nodes

✅ **REQUIREMENT 3**: Edge labels have correct format
- Format: `funcName @ sourceFile:line`
- Example: `runControlCycle @ ControlSystem.cpp:77`

✅ **REQUIREMENT 4**: No subfunction groups
- No group/module/category nodes created

✅ **REQUIREMENT 5**: Nodes have symbolSize based on function count
- Ranges from 37px (4 functions) to 80px (27 functions)

## Data Structure

### File Node Example
```json
{
  "id": 1,
  "name": "ControlSystem.cpp",
  "path": "/home/gabriel/.openclaw/code/projects/smart-drying-module/src/ControlSystem.cpp",
  "functionCount": 23,
  "outgoingCount": 2,
  "incomingCount": 3,
  "callDetails": "→ PIDController.cpp: init @ 50<br/>→ PWMDriver.cpp: runControlCycle @ 77",
  "category": "Control",
  "symbolSize": 72
}
```

### Edge Example
```json
{
  "source": 1,
  "target": 6,
  "label": "init @ ControlSystem.cpp:50",
  "lineStyle": {
    "width": 3.0,
    "color": "#999",
    "curveness": 0.1
  }
}
```

## Usage

### Generate File-Level Graph

```bash
cd /home/gabriel/.openclaw/code/clang-call-analyzer
python test_file_graph.py
```

### Verify Implementation

```bash
python verify_file_graph.py
```

### View in Browser

Open `filegraph.html` in any modern web browser.

## Technical Details

### File Aggregation Logic
1. Groups all functions by file path
2. Tracks which files call functions in other files
3. Builds outgoing/incoming relationship maps
4. Generates unique file nodes

### Edge Label Format
- **Format**: `functionName @ sourceFile:lineNumber`
- **Example**: `init @ ControlSystem.cpp:50`
- Shows the first function call between two files
- Line number indicates where the call originates

### Layout Algorithm
- BFS-based level assignment from root nodes
- Horizontal spacing: 180px
- Vertical spacing: 120px
- Root nodes: Files with no incoming edges
- Auto-calculates positions on load

## Comparison with Function-Level Graph

| Feature | Function-Level | File-Level |
|---------|---------------|------------|
| Node Type | Functions | Files |
| Node Count | 95 | 10 |
| Edge Count | Many (~100+) | 14 |
| Labels | Function names | Function @ File:Line |
| Layout | Force-directed | Tree (auto-layout) |
| Complexity | High | Low |
| Overview | Difficult | Clear |

## Benefits

1. **High-Level Overview**: See file dependencies at a glance
2. **Clear Structure**: Tree layout shows call hierarchy
3. **Interactive**: Search, zoom, drag nodes
4. **Exportable**: Save as PNG/SVG for documentation
5. **Scalable**: Handles large codebases better than function-level

## Files Modified

- **Created**: `src/file_graph_generator.py`
- **Created**: `test_file_graph.py`
- **Created**: `verify_file_graph.py`
- **Generated**: `filegraph.html`

## Next Steps

- Integrate file-graph option into CLI
- Add configuration options for edge labels (show all calls vs first call)
- Implement hierarchical file grouping (by directory)
- Add cycle detection for circular dependencies
- Export to other formats (DOT, GraphML)

## Conclusion

The file-level graph implementation successfully meets all requirements:
- ✅ Nodes = Files
- ✅ Edges = File-to-file call relationships
- ✅ Edge labels = "functionName @ sourceFile:lineNumber"
- ✅ No function nodes
- ✅ No subfunction groups

The generated graph provides a clear, interactive visualization of file-level dependencies in the ESP32 smart drying module project.
