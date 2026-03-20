# Quick Start: File-Level Graph

## What Was Implemented

A pure file-level relationship graph that shows:
- **Nodes** = Files (.cpp files)
- **Edges** = File-to-file call relationships
- **Labels** = "functionName @ sourceFile:lineNumber"

## Requirements - ALL PASS ✅

1. ✅ Only file nodes (no function nodes)
2. ✅ Edges only between files
3. ✅ Edge labels: `functionName @ sourceFile:lineNumber`
4. ✅ No subfunction groups
5. ✅ Node sizes based on function count

## Test Results

- **File Nodes**: 10 files
- **Edges**: 14 file relationships
- **Categories**: 6 (Control, Network, System, Default, etc.)
- **Largest File**: NetworkManager.cpp (27 functions)
- **Most Connected**: main.cpp (8 outgoing calls)

## How to Use

### Generate the graph:
```bash
cd /home/gabriel/.openclaw/code/clang-call-analyzer
python test_file_graph.py
```

### Verify it works:
```bash
python verify_file_graph.py
```

### View in browser:
```bash
# Option 1: Open directly
xdg-open filegraph.html

# Option 2: Simple HTTP server
python -m http.server 8000
# Then open http://localhost:8000/filegraph.html
```

## Example Output

**Node: ControlSystem.cpp**
- Functions: 23
- Outgoing calls: 2
- Incoming calls: 3

**Edge: ControlSystem.cpp → PIDController.cpp**
- Label: `init @ ControlSystem.cpp:50`

## Files Created

1. `src/file_graph_generator.py` - Generator class
2. `test_file_graph.py` - Test script
3. `verify_file_graph.py` - Verification script
4. `filegraph.html` - Interactive graph (18KB)
5. `FILE_GRAPH_IMPLEMENTATION.md` - Full documentation

## Interactive Features

- **Search**: Filter files by name
- **Themes**: Default / Dark / Light
- **Export**: PNG / SVG
- **Layout**: Auto tree-style
- **Drag**: Move nodes manually
- **Tooltips**: Hover for details

## Output Location

```
/home/gabriel/.openclaw/code/clang-call-analyzer/filegraph.html
```

Open this file in your browser to see the interactive graph!
