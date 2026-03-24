"""File-level ECharts HTML generator for function call graphs."""

import json
import logging
import shutil
from pathlib import Path
from string import Template
from typing import Dict, List, Optional, Tuple, Set, Any

from .echarts_templates import CSS_TEMPLATE

# Path to bundled echarts.min.js
ECHARTS_SOURCE = Path(__file__).parent / 'echarts.min.js'


class FileGraphGenerator:
    """Generate HTML with ECharts visualization from file-level call relationships."""

    # HTML template for file-level graph
    HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>File Call Graph</title>
  <script src="./echarts.min.js"></script>
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

  // Get node colors based on categories and target status
  function getNodeColor(node) {
    if (node.isTarget) {
      return '#ff0000';  // Red for target
    }
    if (node.category) {
      const colorMap = {
        'Control': '#ff7f0e',
        'Network': '#2ca02c',
        'Data': '#1f77b4',
        'Utility': '#9467bd',
        'System': '#d62728',
        'Default': '#7f7f7f'
      };
      return colorMap[node.category] || '#7f7f7f';
    }
    return '#7f7f7f';
  }

  // Apply styling to nodes
  const styledNodes = visibleNodes.map(node => ({
    ...node,
    itemStyle: node.isTarget ? {
      color: '#ff0000',
      borderColor: '#000000',
      borderWidth: 3
    } : {
      color: getNodeColor(node)
    }
  }));

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
      layout: 'force',
      data: styledNodes,
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
      force: {
        repulsion: 500,
        edgeLength: 100,
        gravity: 0.1,
        layoutAnimation: true,
        preventOverlap: true
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
}

function tooltipFormatter(params) {
  const data = params.data;

  // Edge tooltip (has tooltip field)
  if (data.tooltip) {
    return data.tooltip;
  }

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
    chart.dispatchAction({ type: 'restore' });
  });

  window.addEventListener('resize', () => {
    chart.resize();
  });
}
"""

    def __init__(self,
                 functions: List[Dict[str, Any]],
                 target_function: Optional[str] = None,
                 logger: Optional[logging.Logger] = None) -> None:
        """
        Initialize file graph generator.

        Args:
            functions: List of function dictionaries from JSON output
                       Each function should have 'parents' and 'children' fields
            target_function: Optional qualified_name of target function to highlight
            logger: Optional logger instance
        """
        self.functions: List[Dict[str, Any]] = functions
        self.target_function: Optional[str] = target_function
        self.logger: logging.Logger = logger or logging.getLogger(__name__)

        # Rebuild relationships from functions data
        # Each function has 'parents' and 'children' fields from JSON
        self.relationships: Dict[int, Tuple[List[int], List[int]]] = {
            func['index']: (func['parents'], func['children'])
            for func in functions
        }

        # Build function name map for target function lookup
        self.name_map: Dict[str, Dict[str, Any]] = {func['self']['qualified_name']: func for func in functions}

    def generate_html(self) -> str:
        """
        Generate complete HTML with embedded data and JavaScript.

        Returns:
            Complete HTML string
        """
        # Transform data to file-level ECharts format
        echarts_data: Dict[str, Any] = self._transform_to_file_graph()

        # Serialize data for embedding
        data_json: str = json.dumps(echarts_data, ensure_ascii=False, indent=2)

        # Use Template to avoid brace escaping issues
        template: Template = Template(self.HTML_TEMPLATE)

        # Generate HTML
        html: str = template.substitute(
            css=CSS_TEMPLATE,
            data=data_json,
            app_script=self.APP_SCRIPT_TEMPLATE
        )

        return html

    def _transform_to_file_graph(self) -> Dict[str, Any]:
        """
        Transform function data to file-level ECharts graph format.

        Returns:
            Dictionary with nodes, edges, and categories
        """
        self.logger.info("Transforming to file-level graph...")

        # Step 1: Aggregate functions by file
        file_functions: Dict[str, List[Dict[str, Any]]] = self._aggregate_by_file()

        # Step 2: Build file-to-file call relationships
        file_relationships: Dict[str, Dict[str, Any]] = self._build_file_relationships(file_functions, self.functions)

        # Step 3: Create file nodes
        nodes: List[Dict[str, Any]] = self._create_file_nodes(file_functions, file_relationships)

        # Step 4: Create file edges with labels
        edges: List[Dict[str, Any]] = self._create_file_edges(file_relationships)

        # Step 5: Assign categories
        nodes = self._assign_categories(nodes)

        # Step 6: Calculate node sizes
        nodes = self._calculate_sizes(nodes)

        # Get category definitions
        categories: List[Dict[str, Any]] = self._get_categories()

        self.logger.info(f"Transformed {len(nodes)} file nodes and {len(edges)} file edges")

        return {
            'nodes': nodes,
            'edges': edges,
            'categories': categories
        }

    def _aggregate_by_file(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Aggregate functions by file path.

        Returns:
            Dictionary mapping file path to list of functions
        """
        file_functions: Dict[str, List[Dict[str, Any]]] = {}

        for func in self.functions:
            file_path: str = func['self']['path']
            if file_path not in file_functions:
                file_functions[file_path] = []
            file_functions[file_path].append(func)

        self.logger.debug(f"Aggregated {len(self.functions)} functions into {len(file_functions)} files")
        return file_functions

    def _build_file_relationships(self,
                                   file_functions: Dict[str, List[Dict[str, Any]]],
                                   functions: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """
        Build file-to-file call relationships.

        Args:
            file_functions: File path to functions mapping
            functions: List of all function data

        Returns:
            Dictionary mapping file paths to relationship info
        """
        file_relationships: Dict[str, Dict[str, Any]] = {}

        # Initialize relationship tracking for each file
        for file_path in file_functions:
            file_relationships[file_path] = {
                'outgoing': {},  # target_file: {function_names, line_ranges, function_indices}
                'incoming': {},  # source_file: {function_names, line_ranges}
                'function_count': len(file_functions[file_path])
            }

        # Build a map from function index to file path
        func_index_to_file: Dict[int, str] = {}
        for func in functions:
            func_index_to_file[func['index']] = func['self']['path']

        # Process each function's calls
        for func in functions:
            func_idx: int = func['index']
            source_file: str = func['self']['path']
            func_name: str = func['self']['name']
            line_range: Tuple[int, int] = func['self']['line']  # Tuple of (start, end)

            # Get children (functions this function calls)
            parents: List[int]
            children: List[int]
            parents, children = self.relationships.get(func_idx, ([], []))

            for child_idx in children:
                if child_idx in func_index_to_file:
                    target_file: str = func_index_to_file[child_idx]

                    # Skip calls within the same file
                    if target_file == source_file:
                        continue

                    # Record file-to-file call with line_range and child function index
                    if target_file not in file_relationships[source_file]['outgoing']:
                        file_relationships[source_file]['outgoing'][target_file] = {
                            'functions': [],
                            'line_ranges': [],  # Source call line ranges
                            'function_indices': []  # Target function indices
                        }

                    file_relationships[source_file]['outgoing'][target_file]['functions'].append(func_name)
                    file_relationships[source_file]['outgoing'][target_file]['line_ranges'].append(line_range)
                    file_relationships[source_file]['outgoing'][target_file]['function_indices'].append(child_idx)

                    # Record incoming for target file
                    if source_file not in file_relationships[target_file]['incoming']:
                        file_relationships[target_file]['incoming'][source_file] = {
                            'functions': [],
                            'line_ranges': []
                        }

                    file_relationships[target_file]['incoming'][source_file]['functions'].append(func_name)
                    file_relationships[target_file]['incoming'][source_file]['line_ranges'].append(line_range)

        return file_relationships

    def _create_file_nodes(self,
                            file_functions: Dict[str, List[Dict[str, Any]]],
                            file_relationships: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Create file nodes.

        Args:
            file_functions: File path to functions mapping
            file_relationships: File relationship mapping

        Returns:
            List of file node dictionaries
        """
        nodes: List[Dict[str, Any]] = []
        file_id: int = 0

        for file_path, funcs in file_functions.items():
            file_name: str = Path(file_path).name

            # Get relationship counts
            outgoing_count: int = len(file_relationships[file_path]['outgoing'])
            incoming_count: int = len(file_relationships[file_path]['incoming'])

            # Build call details for tooltip
            call_details: List[str] = []
            for target_file, info in file_relationships[file_path]['outgoing'].items():
                target_name: str = Path(target_file).name
                func_name: str = info['functions'][0]
                line_range: Tuple[int, int] = info['line_ranges'][0]  # First call's line_range
                call_details.append(f"→ {target_name}: {func_name} @ {line_range[0]}-{line_range[1]}")

            # Check if target function is in this file
            is_target_file: bool = False
            if self.target_function:
                for func in funcs:
                    if func['self']['qualified_name'] == self.target_function:
                        is_target_file = True
                        break

            node: Dict[str, Any] = {
                'id': file_id,
                'name': file_name,
                'path': file_path,
                'functionCount': file_relationships[file_path]['function_count'],
                'outgoingCount': outgoing_count,
                'incomingCount': incoming_count,
                'callDetails': '<br/>'.join(call_details) if call_details else '',
                'isTarget': is_target_file
            }

            nodes.append(node)
            file_id += 1

        return nodes

    def _create_file_edges(self, file_relationships: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Create file edges with call labels.

        Args:
            file_relationships: File relationship mapping

        Returns:
            List of edge dictionaries
        """
        edges: List[Dict[str, Any]] = []

        # Build a map from function index to function definition for quick lookup
        func_index_to_def: Dict[int, Dict[str, Any]] = {func['index']: func for func in self.functions}

        # Create file path to node ID mapping
        file_to_id: Dict[str, int] = {}
        for file_path in file_relationships:
            file_to_id[file_path] = len(file_to_id)

        # Create edges from outgoing relationships
        for source_file, rels in file_relationships.items():
            for target_file, call_info in rels['outgoing'].items():
                # Get source and target file names
                source_name: str = Path(source_file).name
                target_name: str = Path(target_file).name

                # Get first function name and child function index
                func_name: str = call_info['functions'][0]
                child_idx: int = call_info['function_indices'][0]

                # Get target function definition and its line range
                target_line_range: Tuple[int, int]
                target_func_name: str
                if child_idx in func_index_to_def:
                    target_func: Dict[str, Any] = func_index_to_def[child_idx]
                    target_line_range = target_func['self']['line']
                else:
                    # Fallback if function index not found
                    target_line_range = call_info['line_ranges'][0]

                # Format: "@ target_func_name (start, end)" - display called function definition
                # Arrow direction is already shown via edgeSymbol in ECharts config
                if child_idx in func_index_to_def:
                    target_func_name = target_func['self']['name']
                else:
                    target_func_name = func_name
                label: str = f"@ {target_func_name} ({target_line_range[0]}, {target_line_range[1]})"

                # Build tooltip showing all calls with target function definition ranges
                tooltip_lines: List[str] = []
                for i, child_idx in enumerate(call_info['function_indices']):
                    if child_idx in func_index_to_def:
                        loop_target_func: Dict[str, Any] = func_index_to_def[child_idx]
                        loop_target_func_name: str = loop_target_func['self']['name']
                        loop_target_line_range: Tuple[int, int] = loop_target_func['self']['line']
                        # Format: "@ func_name (start, end)" - same as edge label
                        tooltip_lines.append(f"@ {loop_target_func_name} ({loop_target_line_range[0]}, {loop_target_line_range[1]})")

                # Create tooltip HTML
                tooltip: str = '<div style="padding: 8px; font-family: Arial, sans-serif; max-width: 400px;">'
                tooltip += '<strong style="font-size: 14px;">All Calls</strong><br/>'
                tooltip += f'<span style="color: #666; font-size: 12px;">{source_name} → {target_name}</span><br/>'
                tooltip += f'<span style="color: #666; font-size: 12px;">Total: {len(call_info["function_indices"])} calls</span><br/>'
                tooltip += '<hr/><span style="color: #666; font-size: 12px;">Details:</span><br/>'
                tooltip += '<br/>'.join([f'• {line}' for line in tooltip_lines])
                tooltip += '</div>'

                edge: Dict[str, Any] = {
                    'source': file_to_id[source_file],
                    'target': file_to_id[target_file],
                    'label': label,
                    'tooltip': tooltip,
                    'lineStyle': {
                        'width': min(5, 1 + len(call_info['functions']) / 2),
                        'color': '#999',
                        'curveness': 0.1
                    }
                }

                edges.append(edge)

        self.logger.debug(f"Created {len(edges)} file edges")
        return edges

    def _assign_categories(self, nodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
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
        path_lower: str = file_path.lower()

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

    def _calculate_sizes(self, nodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
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
        max_functions: int = max(node['functionCount'] for node in nodes)

        if max_functions == 0:
            max_functions = 1  # Avoid division by zero

        # Calculate sizes: range 30-80 based on function count
        for node in nodes:
            ratio: float = node['functionCount'] / max_functions
            node['symbolSize'] = int(30 + ratio * 50)

        return nodes

    def _get_categories(self) -> List[Dict[str, Any]]:
        """
        Get category definitions for ECharts.

        Returns:
            List of category dictionaries
        """
        categories: List[Dict[str, Any]] = [
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
    Write HTML content to file and copy echarts.min.js if available.

    Args:
        html_content: Complete HTML string
        output_path: Path to output file
    """
    output_file: Path = Path(output_path)
    output_dir: Path = output_file.parent

    # Create parent directory if it doesn't exist
    output_dir.mkdir(parents=True, exist_ok=True)

    # Copy echarts.min.js if bundled version exists
    echarts_dest: Path = output_dir / 'echarts.min.js'
    if ECHARTS_SOURCE.exists() and not echarts_dest.exists():
        try:
            shutil.copy(ECHARTS_SOURCE, echarts_dest)
            logging.info(f"Copied echarts.min.js to {echarts_dest}")
        except Exception as e:
            logging.warning(f"Failed to copy echarts.min.js: {e}")
    elif not ECHARTS_SOURCE.exists():
        # Fall back to CDN if echarts.min.js not bundled
        logging.warning(
            "echarts.min.js not found in package directory. "
            "Update HTML to use CDN fallback."
        )
        html_content = html_content.replace(
            './echarts.min.js',
            'https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js'
        )

    # Write HTML to file
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_content)

    logging.info(f"File graph HTML written to {output_file}")
