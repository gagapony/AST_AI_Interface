"""File-level ECharts HTML generator for function call graphs."""

import json
import logging
from pathlib import Path
from string import Template
from typing import Dict, List, Tuple, Optional, Set

from echarts_templates import CSS_TEMPLATE


class FileGraphGenerator:
    """Generate HTML with ECharts visualization from file-level call relationships."""

    # HTML template for file-level graph
    HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>File Call Graph</title>
  <script src="https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"></script>
  <style>
$css
  </style>
</head>
<body>
  <div id="controls">
    <div class="search-box">
      <input type="text" id="search-input" placeholder="Search files..." />
      <span id="match-count"></span>
    </div>
    <div class="toolbar">
      <select id="theme-select">
        <option value="default">Default Theme</option>
        <option value="dark">Dark Theme</option>
        <option value="light">Light Theme</option>
      </select>
      <button id="export-png">Export PNG</button>
      <button id="export-svg">Export SVG</button>
      <button id="reset-view">Reset View</button>
    </div>
  </div>
  <div id="graph-container"></div>
  <script>
    const GRAPH_DATA = $data;
$app_script
  </script>
</body>
</html>
"""

    # JavaScript app script for file-level graph
    APP_SCRIPT_TEMPLATE = """
let chart;
let originalNodes = [];
let originalEdges = [];
let visibleNodes = [];
let visibleEdges = [];

document.addEventListener('DOMContentLoaded', function() {
  initGraph();
  setupEventListeners();
});

function initGraph() {
  const container = document.getElementById('graph-container');
  chart = echarts.init(container);

  // Store original data for filtering
  originalNodes = [...GRAPH_DATA.nodes];
  originalEdges = [...GRAPH_DATA.edges];
  visibleNodes = [...originalNodes];
  visibleEdges = [...originalEdges];

  const option = {
    title: {
      text: 'File Call Graph',
      left: 'center',
      top: 10
    },
    tooltip: {
      formatter: tooltipFormatter
    },
    series: [{
      type: 'graph',
      layout: 'none',
      data: visibleNodes,
      links: visibleEdges,
      categories: GRAPH_DATA.categories,
      roam: true,
      draggable: true,
      label: {
        show: true,
        position: 'inside',
        formatter: function(params) {
          return params.data.name;
        },
        color: '#fff',
        fontSize: 12,
        fontWeight: 'bold'
      },
      edgeLabel: {
        show: true,
        position: 'middle',
        formatter: function(params) {
          return params.data.label || '';
        },
        fontSize: 10,
        color: '#666'
      },
      edgeSymbol: ['circle', 'arrow'],
      edgeSymbolSize: [4, 8],
      lineStyle: {
        width: 2,
        curveness: 0.1
      },
      emphasis: {
        focus: 'adjacency'
      }
    }]
  };

  chart.setOption(option);

  // Auto-fit layout after render
  setTimeout(() => {
    autoLayout();
  }, 100);
}

function tooltipFormatter(params) {
  const data = params.data;

  // File node tooltip
  return `
    <div style="padding: 8px; font-family: Arial, sans-serif; max-width: 300px;">
      <strong style="font-size: 14px;">${data.name}</strong><br/>
      <span style="color: #666;">Functions:</span> ${data.functionCount}<br/>
      <span style="color: #666;">Outgoing calls:</span> ${data.outgoingCount}<br/>
      <span style="color: #666;">Incoming calls:</span> ${data.incomingCount}
      ${data.callDetails ? `<br/><hr/><span style="color: #666; font-size: 12px;">Calls:</span><br/>${data.callDetails}` : ''}
    </div>
  `;
}

function handleSearch(query) {
  const lowerQuery = query.toLowerCase().trim();

  if (!query || query.trim() === '') {
    visibleNodes = [...originalNodes];
    visibleEdges = [...originalEdges];
    updateChartData(visibleNodes, visibleEdges);
    document.getElementById('match-count').textContent = '';
    return;
  }

  // Search nodes
  const matchingNodes = originalNodes.filter(node =>
    node.name.toLowerCase().includes(lowerQuery)
  );

  if (matchingNodes.length === 0) {
    visibleNodes = [];
    visibleEdges = [];
    updateChartData(visibleNodes, visibleEdges);
    document.getElementById('match-count').textContent = '0 matches';
    return;
  }

  // Get matching node IDs and their neighbors
  const matchingIds = new Set(matchingNodes.map(n => n.id));
  const neighborIds = new Set();

  matchingNodes.forEach(node => {
    originalEdges.forEach(edge => {
      if (edge.source === node.id) {
        neighborIds.add(edge.target);
      } else if (edge.target === node.id) {
        neighborIds.add(edge.source);
      }
    });
  });

  // Build visible set
  const visibleIds = new Set([...matchingIds, ...neighborIds]);

  // Filter nodes
  visibleNodes = originalNodes.filter(node => visibleIds.has(node.id));

  // Filter edges
  visibleEdges = originalEdges.filter(edge =>
    visibleIds.has(edge.source) && visibleIds.has(edge.target)
  );

  updateChartData(visibleNodes, visibleEdges);
  document.getElementById('match-count').textContent = `${matchingNodes.length} 个文件匹配`;
}

function updateChartData(nodes, edges) {
  chart.setOption({
    series: [{
      data: nodes,
      links: edges
    }]
  });
}

function autoLayout() {
  // Simple tree layout from left to right
  const nodes = [...visibleNodes];
  const edges = [...visibleEdges];

  // Find root nodes (nodes with no incoming edges)
  const hasIncoming = new Set();
  edges.forEach(edge => {
    hasIncoming.add(edge.target);
  });

  const rootNodes = nodes.filter(n => !hasIncoming.has(n.id));

  // If no roots, use first node
  const roots = rootNodes.length > 0 ? rootNodes : [nodes[0]];

  // Assign levels using BFS
  const levels = new Map();
  const visited = new Set();
  const queue = [];

  roots.forEach(root => {
    levels.set(root.id, 0);
    visited.add(root.id);
    queue.push(root.id);
  });

  while (queue.length > 0) {
    const nodeId = queue.shift();
    const level = levels.get(nodeId);

    edges.forEach(edge => {
      if (edge.source === nodeId && !visited.has(edge.target)) {
        levels.set(edge.target, level + 1);
        visited.add(edge.target);
        queue.push(edge.target);
      }
    });
  }

  // Assign nodes to levels that haven't been visited
  nodes.forEach(node => {
    if (!visited.has(node.id)) {
      levels.set(node.id, 0);
    }
  });

  // Group nodes by level
  const levelGroups = new Map();
  levels.forEach((level, nodeId) => {
    if (!levelGroups.has(level)) {
      levelGroups.set(level, []);
    }
    levelGroups.get(level).push(nodeId);
  });

  // Calculate positions
  const nodePositions = new Map();
  const maxLevel = Math.max(...levels.values());
  const nodeSize = 60;
  const horizontalSpacing = 180;
  const verticalSpacing = 120;

  levelGroups.forEach((nodeIds, level) => {
    const x = 100 + level * horizontalSpacing;
    const count = nodeIds.length;
    const totalHeight = (count - 1) * verticalSpacing;
    const startY = Math.max(50, (600 - totalHeight) / 2);

    nodeIds.forEach((nodeId, index) => {
      nodePositions.set(nodeId, {
        x: x,
        y: startY + index * verticalSpacing
      });
    });
  });

  // Apply positions
  const positionedNodes = nodes.map(node => {
    const pos = nodePositions.get(node.id);
    if (pos) {
      return {
        ...node,
        x: pos.x,
        y: pos.y
      };
    }
    return node;
  });

  chart.setOption({
    series: [{
      data: positionedNodes
    }]
  });
}

function handleThemeChange(theme) {
  const body = document.body;

  body.classList.remove('dark-theme', 'light-theme');

  switch (theme) {
    case 'dark':
      body.classList.add('dark-theme');
      chart.setOption({
        backgroundColor: '#1a1a1a',
        textStyle: { color: '#ffffff' }
      });
      break;
    case 'light':
      body.classList.add('light-theme');
      chart.setOption({
        backgroundColor: '#ffffff',
        textStyle: { color: '#333333' }
      });
      break;
    default:
      chart.setOption({
        backgroundColor: 'transparent',
        textStyle: { color: '#333333' }
      });
  }
}

function handleExportPNG() {
  const url = chart.getDataURL({
    type: 'png',
    pixelRatio: 2,
    backgroundColor: '#fff'
  });

  const link = document.createElement('a');
  link.href = url;
  link.download = `filegraph_${getTimestamp()}.png`;
  link.click();
}

function handleExportSVG() {
  const svgElement = chart.getDom().querySelector('svg');
  const serializer = new XMLSerializer();
  const svgString = serializer.serializeToString(svgElement);

  const blob = new Blob([svgString], { type: 'image/svg+xml' });
  const url = URL.createObjectURL(blob);

  const link = document.createElement('a');
  link.href = url;
  link.download = `filegraph_${getTimestamp()}.svg`;
  link.click();

  URL.revokeObjectURL(url);
}

function getTimestamp() {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, '0');
  const day = String(now.getDate()).padStart(2, '0');
  const hour = String(now.getHours()).padStart(2, '0');
  const minute = String(now.getMinutes()).padStart(2, '0');
  const second = String(now.getSeconds()).padStart(2, '0');
  return `${year}${month}${day}_${hour}${minute}${second}`;
}

function setupEventListeners() {
  const searchInput = document.getElementById('search-input');
  let searchTimeout;

  searchInput.addEventListener('input', (e) => {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => {
      handleSearch(e.target.value);
    }, 300);
  });

  document.getElementById('theme-select').addEventListener('change', (e) => {
    handleThemeChange(e.target.value);
  });

  document.getElementById('export-png').addEventListener('click', handleExportPNG);
  document.getElementById('export-svg').addEventListener('click', handleExportSVG);
  document.getElementById('reset-view').addEventListener('click', () => {
    autoLayout();
  });

  window.addEventListener('resize', () => {
    chart.resize();
  });
}
"""

    def __init__(self,
                 functions: List[Dict],
                 relationships: Dict[int, Tuple[List[int], List[int]]],
                 logger: Optional[logging.Logger] = None):
        """
        Initialize file graph generator.

        Args:
            functions: List of function dictionaries from JSON output
            relationships: Dict mapping function index to (parents, children) tuples
            logger: Optional logger instance
        """
        self.functions = functions
        self.relationships = relationships
        self.logger = logger or logging.getLogger(__name__)

    def generate_html(self) -> str:
        """
        Generate complete HTML with embedded data and JavaScript.

        Returns:
            Complete HTML string
        """
        # Transform data to file-level ECharts format
        echarts_data = self._transform_to_file_graph()

        # Serialize data for embedding
        data_json = json.dumps(echarts_data, ensure_ascii=False, indent=2)

        # Use Template to avoid brace escaping issues
        template = Template(self.HTML_TEMPLATE)

        # Generate HTML
        html = template.substitute(
            css=CSS_TEMPLATE,
            data=data_json,
            app_script=self.APP_SCRIPT_TEMPLATE
        )

        return html

    def _transform_to_file_graph(self) -> Dict:
        """
        Transform function data to file-level ECharts graph format.

        Returns:
            Dictionary with nodes, edges, and categories
        """
        self.logger.info("Transforming to file-level graph...")

        # Step 1: Aggregate functions by file
        file_functions = self._aggregate_by_file()

        # Step 2: Build file-to-file call relationships
        file_relationships = self._build_file_relationships(file_functions, self.functions)

        # Step 3: Create file nodes
        nodes = self._create_file_nodes(file_functions, file_relationships)

        # Step 4: Create file edges with labels
        edges = self._create_file_edges(file_relationships)

        # Step 5: Assign categories
        nodes = self._assign_categories(nodes)

        # Step 6: Calculate node sizes
        nodes = self._calculate_sizes(nodes)

        # Get category definitions
        categories = self._get_categories()

        self.logger.info(f"Transformed {len(nodes)} file nodes and {len(edges)} file edges")

        return {
            'nodes': nodes,
            'edges': edges,
            'categories': categories
        }

    def _aggregate_by_file(self) -> Dict[str, List[Dict]]:
        """
        Aggregate functions by file path.

        Returns:
            Dictionary mapping file path to list of functions
        """
        file_functions = {}

        for func in self.functions:
            file_path = func['self']['path']
            if file_path not in file_functions:
                file_functions[file_path] = []
            file_functions[file_path].append(func)

        self.logger.debug(f"Aggregated {len(self.functions)} functions into {len(file_functions)} files")
        return file_functions

    def _build_file_relationships(self,
                                   file_functions: Dict[str, List[Dict]],
                                   functions: List[Dict]) -> Dict[str, Dict]:
        """
        Build file-to-file call relationships.

        Args:
            file_functions: File path to functions mapping
            functions: List of all function data

        Returns:
            Dictionary mapping file paths to relationship info
        """
        file_relationships = {}

        # Initialize relationship tracking for each file
        for file_path in file_functions:
            file_relationships[file_path] = {
                'outgoing': {},  # target_file: {function_names, line_ranges}
                'incoming': {},  # source_file: {function_names, line_ranges}
                'function_count': len(file_functions[file_path])
            }

        # Build a map from function index to file path
        func_index_to_file = {}
        for func in functions:
            func_index_to_file[func['index']] = func['self']['path']

        # Process each function's calls
        for func in functions:
            func_idx = func['index']
            source_file = func['self']['path']
            func_name = func['self']['name']
            func_line = func['self']['line'][0]

            # Get children (functions this function calls)
            parents, children = self.relationships.get(func_idx, ([], []))

            for child_idx in children:
                if child_idx in func_index_to_file:
                    target_file = func_index_to_file[child_idx]

                    # Skip calls within the same file
                    if target_file == source_file:
                        continue

                    # Record file-to-file call
                    if target_file not in file_relationships[source_file]['outgoing']:
                        file_relationships[source_file]['outgoing'][target_file] = {
                            'functions': [],
                            'lines': []
                        }

                    file_relationships[source_file]['outgoing'][target_file]['functions'].append(func_name)
                    file_relationships[source_file]['outgoing'][target_file]['lines'].append(func_line)

                    # Record incoming for target file
                    if source_file not in file_relationships[target_file]['incoming']:
                        file_relationships[target_file]['incoming'][source_file] = {
                            'functions': [],
                            'lines': []
                        }

                    file_relationships[target_file]['incoming'][source_file]['functions'].append(func_name)
                    file_relationships[target_file]['incoming'][source_file]['lines'].append(func_line)

        return file_relationships

    def _create_file_nodes(self,
                            file_functions: Dict[str, List[Dict]],
                            file_relationships: Dict[str, Dict]) -> List[Dict]:
        """
        Create file nodes.

        Args:
            file_functions: File path to functions mapping
            file_relationships: File relationship mapping

        Returns:
            List of file node dictionaries
        """
        nodes = []
        file_id = 0

        for file_path, funcs in file_functions.items():
            file_name = file_path.split('/')[-1]

            # Get relationship counts
            outgoing_count = len(file_relationships[file_path]['outgoing'])
            incoming_count = len(file_relationships[file_path]['incoming'])

            # Build call details for tooltip
            call_details = []
            for target_file, info in file_relationships[file_path]['outgoing'].items():
                target_name = target_file.split('/')[-1]
                func_name = info['functions'][0]
                line = info['lines'][0]
                call_details.append(f"→ {target_name}: {func_name} @ {line}")

            node = {
                'id': file_id,
                'name': file_name,
                'path': file_path,
                'functionCount': file_relationships[file_path]['function_count'],
                'outgoingCount': outgoing_count,
                'incomingCount': incoming_count,
                'callDetails': '<br/>'.join(call_details) if call_details else ''
            }

            nodes.append(node)
            file_id += 1

        return nodes

    def _create_file_edges(self, file_relationships: Dict[str, Dict]) -> List[Dict]:
        """
        Create file edges with call labels.

        Args:
            file_relationships: File relationship mapping

        Returns:
            List of edge dictionaries
        """
        edges = []

        # Create file path to node ID mapping
        file_to_id = {}
        for file_path in file_relationships:
            file_to_id[file_path] = len(file_to_id)

        # Create edges from outgoing relationships
        for source_file, rels in file_relationships.items():
            for target_file, call_info in rels['outgoing'].items():
                # Create edge label: "funcName @ sourceFile"
                func_name = call_info['functions'][0]
                source_name = source_file.split('/')[-1]
                target_name = target_file.split('/')[-1]
                line = call_info['lines'][0]

                label = f"{func_name} @ {source_name}:{line}"

                edge = {
                    'source': file_to_id[source_file],
                    'target': file_to_id[target_file],
                    'label': label,
                    'lineStyle': {
                        'width': min(5, 1 + len(call_info['functions']) / 2),
                        'color': '#999',
                        'curveness': 0.1
                    }
                }

                edges.append(edge)

        self.logger.debug(f"Created {len(edges)} file edges")
        return edges

    def _assign_categories(self, nodes: List[Dict]) -> List[Dict]:
        """
        Assign categories to nodes based on file path.

        Args:
            nodes: List of node dictionaries

        Returns:
            List of nodes with category field added
        """
        for node in nodes:
            node['category'] = self._get_category_for_path(node['path'])

        return nodes

    def _get_category_for_path(self, file_path: str) -> str:
        """
        Determine category based on file path.

        Args:
            file_path: File path string

        Returns:
            Category name
        """
        path_lower = file_path.lower()

        if '/control/' in path_lower or 'control' in path_lower:
            return 'Control'
        elif '/network/' in path_lower or 'network' in path_lower or 'wifi' in path_lower or 'mqtt' in path_lower:
            return 'Network'
        elif '/data/' in path_lower or 'data' in path_lower or 'storage' in path_lower:
            return 'Data'
        elif '/utils/' in path_lower or '/util/' in path_lower or 'util' in path_lower or 'helper' in path_lower:
            return 'Utility'
        elif '/lib/' in path_lower or '/sys/' in path_lower or 'system' in path_lower or 'driver' in path_lower:
            return 'System'
        else:
            return 'Default'

    def _calculate_sizes(self, nodes: List[Dict]) -> List[Dict]:
        """
        Calculate symbol sizes for nodes based on function count.

        Args:
            nodes: List of node dictionaries

        Returns:
            List of nodes with symbolSize field added
        """
        if not nodes:
            return nodes

        # Find maximum function count
        max_functions = max(node['functionCount'] for node in nodes)

        if max_functions == 0:
            max_functions = 1  # Avoid division by zero

        # Calculate sizes: range 30-80 based on function count
        for node in nodes:
            ratio = node['functionCount'] / max_functions
            node['symbolSize'] = int(30 + ratio * 50)

        return nodes

    def _get_categories(self) -> List[Dict]:
        """
        Get category definitions for ECharts.

        Returns:
            List of category dictionaries
        """
        categories = [
            {
                'name': 'Control',
                'itemStyle': {'color': '#ff7f0e'}
            },
            {
                'name': 'Network',
                'itemStyle': {'color': '#2ca02c'}
            },
            {
                'name': 'Data',
                'itemStyle': {'color': '#1f77b4'}
            },
            {
                'name': 'Utility',
                'itemStyle': {'color': '#9467bd'}
            },
            {
                'name': 'System',
                'itemStyle': {'color': '#d62728'}
            },
            {
                'name': 'Default',
                'itemStyle': {'color': '#7f7f7f'}
            }
        ]

        return categories


def write_html_file(html_content: str, output_path: str) -> None:
    """
    Write HTML content to file.

    Args:
        html_content: Complete HTML string
        output_path: Path to output file
    """
    output_file = Path(output_path)

    # Create parent directory if it doesn't exist
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # Write HTML to file
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_content)

    logging.info(f"File graph HTML written to {output_path}")
