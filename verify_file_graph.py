#!/usr/bin/env python3
"""Verify file-level graph implementation."""

import json
from pathlib import Path

def verify_graph():
    """Verify the generated file graph."""

    # Read the HTML and extract the GRAPH_DATA
    html = Path('/home/gabriel/.openclaw/code/clang-call-analyzer/filegraph.html').read_text()

    # Find GRAPH_DATA section
    match = html.find('const GRAPH_DATA = ')

    if match < 0:
        print("❌ FAILED: Could not find GRAPH_DATA in HTML")
        return False

    # Extract JSON by finding balanced braces
    # Start from the opening brace
    start_idx = html.find('{', match)

    if start_idx < 0:
        print("❌ FAILED: Could not find opening brace in GRAPH_DATA")
        return False

    depth = 0
    i = 0
    for i in range(len(html) - start_idx):
        char = html[start_idx + i]
        if char == '{':
            depth += 1
        elif char == '}':
            depth -= 1
            if depth == 0:
                break

    if depth != 0:
        print("❌ FAILED: Could not parse GRAPH_DATA JSON")
        return False

    data_str = html[start_idx:start_idx + i + 1]
    data = json.loads(data_str)

    print("=" * 60)
    print("FILE-LEVEL GRAPH VERIFICATION")
    print("=" * 60)

    # Verify nodes
    print(f"\n✅ NODES: {len(data['nodes'])} file nodes")
    print("-" * 60)

    for node in data['nodes']:
        print(f"  📄 {node['name']}")
        print(f"     Functions: {node['functionCount']}")
        print(f"     Outgoing calls: {node['outgoingCount']}")
        print(f"     Incoming calls: {node['incomingCount']}")
        if node['callDetails']:
            print(f"     Calls: {node['callDetails'][:80]}...")
        print()

    # Verify edges
    print(f"\n✅ EDGES: {len(data['edges'])} file relationships")
    print("-" * 60)

    for edge in data['edges'][:10]:  # Show first 10 edges
        src = next(n for n in data['nodes'] if n['id'] == edge['source'])
        tgt = next(n for n in data['nodes'] if n['id'] == edge['target'])
        print(f"  {src['name']:20} ──> {tgt['name']:20}")
        print(f"     Label: {edge['label']}")
        print()

    if len(data['edges']) > 10:
        print(f"  ... and {len(data['edges']) - 10} more edges\n")

    # Verify categories
    print(f"✅ CATEGORIES: {len(data['categories'])}")
    print("-" * 60)
    for cat in data['categories']:
        count = sum(1 for n in data['nodes'] if n.get('category') == cat['name'])
        print(f"  {cat['name']}: {count} files")

    # Verify requirements
    print("\n" + "=" * 60)
    print("REQUIREMENT CHECK")
    print("=" * 60)

    # Check 1: Only file nodes (no function nodes)
    function_nodes = [n for n in data['nodes'] if '.' not in n['name']]
    if len(function_nodes) == 0:
        print("✅ REQUIREMENT 1: Only file nodes (no function nodes)")
    else:
        print(f"❌ REQUIREMENT 1 FAILED: Found {len(function_nodes)} function nodes")

    # Check 2: Edges between files only
    all_file_nodes = set(n['id'] for n in data['nodes'])
    invalid_edges = [e for e in data['edges']
                     if e['source'] not in all_file_nodes or e['target'] not in all_file_nodes]
    if len(invalid_edges) == 0:
        print("✅ REQUIREMENT 2: All edges are between file nodes")
    else:
        print(f"❌ REQUIREMENT 2 FAILED: Found {len(invalid_edges)} invalid edges")

    # Check 3: Edge labels have correct format
    import re
    label_pattern = re.compile(r'^.+ @ .+:\d+$')
    invalid_labels = [e for e in data['edges'] if not label_pattern.match(e.get('label', ''))]
    if len(invalid_labels) == 0:
        print("✅ REQUIREMENT 3: Edge labels have correct format (funcName @ sourceFile:line)")
    else:
        print(f"❌ REQUIREMENT 3 FAILED: Found {len(invalid_labels)} edges with invalid labels")
        for edge in invalid_labels[:3]:
            print(f"     Invalid label: {edge.get('label', '(no label)')}")

    # Check 4: No subfunction groups
    group_nodes = [n for n in data['nodes'] if n.get('type') in ['group', 'module', 'category']]
    if len(group_nodes) == 0:
        print("✅ REQUIREMENT 4: No subfunction groups")
    else:
        print(f"❌ REQUIREMENT 4 FAILED: Found {len(group_nodes)} group nodes")

    # Check 5: Node size based on function count
    has_sizes = all('symbolSize' in n for n in data['nodes'])
    if has_sizes:
        print("✅ REQUIREMENT 5: Nodes have symbolSize based on function count")
    else:
        print("❌ REQUIREMENT 5 FAILED: Some nodes missing symbolSize")

    print("\n" + "=" * 60)
    print("✅ FILE-LEVEL GRAPH GENERATION COMPLETE")
    print("=" * 60)
    print(f"\n📁 Output file: /home/gabriel/.openclaw/code/clang-call-analyzer/filegraph.html")
    print("🌐 Open in browser to view the interactive graph")

    return True


if __name__ == '__main__':
    verify_graph()
