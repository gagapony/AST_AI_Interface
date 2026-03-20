"""HTML/JavaScript templates for ECharts visualization."""

CSS_TEMPLATE = """
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
  overflow: hidden;
}

#controls {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  background: #f5f5f5;
  padding: 10px 20px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1);
  z-index: 1000;
}

.search-box {
  display: flex;
  align-items: center;
  gap: 10px;
}

#search-input {
  padding: 8px 12px;
  border: 1px solid #ccc;
  border-radius: 4px;
  width: 300px;
  font-size: 14px;
}

#match-count {
  font-size: 12px;
  color: #666;
}

.toolbar {
  display: flex;
  gap: 10px;
}

select, button {
  padding: 8px 12px;
  border: 1px solid #ccc;
  border-radius: 4px;
  background: white;
  cursor: pointer;
  font-size: 14px;
}

button:hover {
  background: #e0e0e0;
}

#graph-container {
  position: absolute;
  top: 50px;
  left: 0;
  right: 0;
  bottom: 0;
}

/* Dark theme */
body.dark-theme {
  background: #1a1a1a;
}

body.dark-theme #controls {
  background: #2a2a2a;
  border-bottom: 1px solid #444;
}

body.dark-theme #search-input,
body.dark-theme select,
body.dark-theme button {
  background: #333;
  border-color: #555;
  color: #fff;
}

body.dark-theme button:hover {
  background: #444;
}

body.dark-theme #match-count {
  color: #aaa;
}

/* Light theme */
body.light-theme {
  background: #fafafa;
}

body.light-theme #controls {
  background: #ffffff;
  border-bottom: 1px solid #e0e0e0;
}
"""

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Function Call Graph</title>
  <script src="https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"></script>
  <style>
$css
  </style>
</head>
<body>
  <div id="controls">
    <div class="search-box">
      <input type="text" id="search-input" placeholder="Search functions..." />
      <span id="match-count"></span>
    </div>
    <div class="toolbar">
      <select id="group-mode">
        <option value="none">No Grouping</option>
        <option value="file">Group by File</option>
        <option value="module">Group by Module</option>
        <option value="category">Group by Category</option>
      </select>
      <select id="theme-select">
        <option value="default">Default Theme</option>
        <option value="dark">Dark Theme</option>
        <option value="light">Light Theme</option>
      </select>
      <button id="export-png">Export PNG</button>
      <button id="export-svg">Export SVG</button>
      <button id="zoom-in">+</button>
      <button id="zoom-out">-</button>
      <button id="reset-zoom">Reset</button>
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

APP_SCRIPT_TEMPLATE = """
let chart;
let originalNodes = [];
let originalEdges = [];
let visibleNodes = [];
let visibleEdges = [];
let currentGroupMode = 'none';
let groupNodes = [];
let groupMap = new Map();
let nodeToGroupMap = new Map();
let preSearchCollapsedGroups = new Map();
let isSearching = false;

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
      text: 'Function Call Graph',
      left: 'center'
    },
    tooltip: {
      formatter: tooltipFormatter
    },
    legend: {
      data: GRAPH_DATA.categories.map(c => c.name),
      top: 'bottom'
    },
    series: [{
      type: 'graph',
      layout: 'force',
      data: visibleNodes,
      links: visibleEdges,
      categories: GRAPH_DATA.categories,
      roam: true,
      label: {
        show: true,
        position: 'right',
        formatter: '{b}'
      },
      force: {
        repulsion: 1000,
        edgeLength: 150,
        gravity: 0.1
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

  // Group node tooltip
  if (data.type) {
    return `
      <div style="padding: 8px; font-family: Arial, sans-serif;">
        <strong style="font-size: 14px;">${data.name}</strong><br/>
        <span style="color: #666;">Type:</span> ${data.type}<br/>
        <span style="color: #666;">Functions:</span> ${data.nodeCount}<br/>
        <span style="color: #666;">Status:</span> ${data.collapsed ? 'Collapsed' : 'Expanded'}<br/>
        <span style="color: #999; font-size: 12px;">Click to toggle</span>
      </div>
    `;
  }

  // Function node tooltip
  return `
    <div style="padding: 8px; font-family: Arial, sans-serif;">
      <strong style="font-size: 14px;">${data.name}</strong><br/>
      <span style="color: #666;">File:</span> ${data.path}<br/>
      <span style="color: #666;">Line:</span> ${data.line_range[0]} - ${data.line_range[1]}<br/>
      ${data.brief ? `<span style="color: #666;">Brief:</span> ${data.brief}<br/>` : ''}
      <span style="color: #666;">Calls:</span> ${data.children.length} / Called by: ${data.parents.length}
    </div>
  `;
}

function handleSearch(query) {
  const lowerQuery = query.toLowerCase().trim();

  // Case 1: Empty query - clear search
  if (!query || query.trim() === '') {
    if (isSearching) {
      // We were searching, now restore pre-search state
      isSearching = false;
      restoreCollapsedState();
    }

    // If in group mode, rebuild with restored state; otherwise restore full graph
    if (currentGroupMode !== 'none') {
      rebuildVisibleNodes();
    } else {
      visibleNodes = [...originalNodes];
      visibleEdges = [...originalEdges];
      updateChartData(visibleNodes, visibleEdges);
    }
    document.getElementById('match-count').textContent = '';
    return;
  }

  // Case 2: New search query
  const wasSearching = isSearching;
  isSearching = true;

  // Step 1: Save current collapsed state if this is the first search
  if (!wasSearching && currentGroupMode !== 'none') {
    saveCollapsedState();
  }

  // Step 2: Search ALL nodes (not just expanded groups)
  const matchingNodes = originalNodes.filter(node =>
    node.name.toLowerCase().includes(lowerQuery) ||
    node.path.toLowerCase().includes(lowerQuery)
  );

  if (matchingNodes.length === 0) {
    // No matches, show empty graph
    visibleNodes = [];
    visibleEdges = [];
    updateChartData(visibleNodes, visibleEdges);
    document.getElementById('match-count').textContent = '0 matches';
    return;
  }

  // Step 3: Get matching node IDs
  const matchingIds = new Set(matchingNodes.map(n => n.id));

  // Step 4: Get neighbor IDs (direct parents and children) for context
  const neighborIds = new Set();
  matchingNodes.forEach(node => {
    node.parents.forEach(parentId => neighborIds.add(parentId));
    node.children.forEach(childId => neighborIds.add(childId));
  });

  // Step 5: In grouped mode, auto-expand groups containing matches or neighbors
  let expandedGroups = 0;
  if (currentGroupMode !== 'none') {
    // Find all groups that contain matching nodes or their neighbors
    const groupsToExpand = new Set();

    // Check matching nodes
    matchingIds.forEach(nodeId => {
      const group = nodeToGroupMap.get(nodeId);
      if (group) {
        groupsToExpand.add(group.id);
      }
    });

    // Check neighbor nodes
    neighborIds.forEach(nodeId => {
      const group = nodeToGroupMap.get(nodeId);
      if (group) {
        groupsToExpand.add(group.id);
      }
    });

    // Auto-expand these groups temporarily
    groupsToExpand.forEach(groupId => {
      const group = groupMap.get(groupId);
      if (group) {
        if (group.collapsed) {
          group.collapsed = false;
          expandedGroups++;
        }
      }
    });
  }

  // Step 6: Build visible node set
  // Start with matches and neighbors
  const visibleIds = new Set([...matchingIds, ...neighborIds]);

  // In grouped mode, also include all nodes from auto-expanded groups
  if (currentGroupMode !== 'none') {
    groupMap.forEach(group => {
      if (!group.collapsed) {
        // Add all children from this expanded group
        group.children.forEach(nodeId => {
          visibleIds.add(nodeId);
        });
      }
    });
  }

  // Step 7: Filter nodes
  visibleNodes = originalNodes.filter(node => visibleIds.has(node.id));

  // Step 8: Filter edges (only edges between visible nodes)
  visibleEdges = originalEdges.filter(edge =>
    visibleIds.has(edge.source) && visibleIds.has(edge.target)
  );

  // Step 9: Update chart and UI
  updateChartData(visibleNodes, visibleEdges);

  // Show match count and expanded group count
  if (currentGroupMode !== 'none' && expandedGroups > 0) {
    document.getElementById('match-count').textContent =
      `${matchingNodes.length} 个节点匹配，${expandedGroups} 个分组已展开`;
  } else {
    document.getElementById('match-count').textContent = `${matchingNodes.length} 个节点匹配`;
  }
}

function saveCollapsedState() {
  preSearchCollapsedGroups.clear();
  groupMap.forEach(group => {
    preSearchCollapsedGroups.set(group.id, group.collapsed);
  });
}

function restoreCollapsedState() {
  groupMap.forEach(group => {
    const savedState = preSearchCollapsedGroups.get(group.id);
    if (savedState !== undefined) {
      group.collapsed = savedState;
    }
  });
}

function updateChartData(nodes, edges) {
  chart.setOption({
    series: [{
      data: nodes,
      links: edges
    }]
  });
}

function handleGroupChange(mode) {
  currentGroupMode = mode;

  // Clear search state when changing group mode
  isSearching = false;
  preSearchCollapsedGroups.clear();
  document.getElementById('search-input').value = '';
  document.getElementById('match-count').textContent = '';

  // Clear previous group state
  groupNodes = [];
  groupMap.clear();
  nodeToGroupMap.clear();

  if (mode === 'none') {
    // Show all nodes, hide group nodes
    visibleNodes = [...originalNodes];
    visibleEdges = [...originalEdges];
    updateChartData(visibleNodes, visibleEdges);
    return;
  }

  // Create groups based on mode
  switch (mode) {
    case 'file':
      groupNodes = groupByFile(originalNodes);
      break;
    case 'module':
      groupNodes = groupByModule(originalNodes);
      break;
    case 'category':
      groupNodes = groupByCategory(originalNodes);
      break;
  }

  // Initialize all groups as expanded
  groupNodes.forEach(group => {
    groupMap.set(group.id, group);
    group.collapsed = false;

    // Map each node to its group
    group.children.forEach(nodeId => {
      nodeToGroupMap.set(nodeId, group);
    });
  });

  // Start with all groups expanded (show all nodes)
  visibleNodes = [...originalNodes];
  visibleEdges = [...originalEdges];
  updateChartData(visibleNodes, visibleEdges);
}

function handleGroupClick(params) {
  if (!params.data || !params.data.type) {
    // Not a group node
    return;
  }

  const group = groupMap.get(params.data.id);
  if (!group) {
    return;
  }

  // Toggle collapse state
  group.collapsed = !group.collapsed;

  // Rebuild visible nodes
  rebuildVisibleNodes();
}

function rebuildVisibleNodes() {
  // Get all groups
  const allGroups = Array.from(groupMap.values());

  // Start with no nodes
  const nodeSet = new Set();

  // Process each group
  allGroups.forEach(group => {
    if (group.collapsed) {
      // Show group node instead of children
      // (Will add group node to visibleNodes separately)
    } else {
      // Show all children
      group.children.forEach(nodeId => {
        nodeSet.add(nodeId);
      });
    }
  });

  // Build visible nodes list
  visibleNodes = [];

  // Add collapsed group nodes
  allGroups.forEach(group => {
    if (group.collapsed) {
      visibleNodes.push(createGroupNode(group));
    }
  });

  // Add expanded child nodes
  originalNodes.forEach(node => {
    if (nodeSet.has(node.id)) {
      visibleNodes.push(node);
    }
  });

  // Build visible edges
  visibleEdges = [];

  originalEdges.forEach(edge => {
    // Check if both source and target are visible
    const sourceVisible = nodeSet.has(edge.source);
    const targetVisible = nodeSet.has(edge.target);

    if (sourceVisible && targetVisible) {
      visibleEdges.push(edge);
    }
  });

  // Add edges between collapsed groups
  addInterGroupEdges();

  updateChartData(visibleNodes, visibleEdges);
}

function createGroupNode(group) {
  // Calculate group node size based on child count
  const size = 20 + Math.min(30, group.nodeCount * 2);

  return {
    id: group.id,
    name: `${group.name} (${group.nodeCount})`,
    type: 'file',
    collapsed: true,
    children: group.children,
    category: group.category,
    symbolSize: size,
    itemStyle: {
      color: getGroupColor(group.category),
      borderColor: '#333',
      borderWidth: 2
    },
    label: {
      show: true,
      formatter: '{b}',
      color: '#000',
      fontWeight: 'bold'
    }
  };
}

function getGroupColor(category) {
  const colors = {
    'Control': '#ff7f0e',
    'Network': '#2ca02c',
    'Data': '#1f77b4',
    'Utility': '#9467bd',
    'System': '#d62728',
    'Default': '#7f7f7f'
  };
  return colors[category] || colors['Default'];
}

function addInterGroupEdges() {
  // Find edges between nodes in different collapsed groups
  const collapsedGroups = Array.from(groupMap.values()).filter(g => g.collapsed);
  const groupIds = new Set(collapsedGroups.map(g => g.id));

  // Track edges already added between groups
  const edgeKeySet = new Set();

  originalEdges.forEach(edge => {
    const sourceGroup = nodeToGroupMap.get(edge.source);
    const targetGroup = nodeToGroupMap.get(edge.target);

    // Check if both groups are collapsed
    if (!sourceGroup || !targetGroup ||
        !sourceGroup.collapsed || !targetGroup.collapsed) {
      return;
    }

    // Check if this is an inter-group edge
    if (sourceGroup.id !== targetGroup.id) {
      // Create edge key to avoid duplicates
      const edgeKey = `${sourceGroup.id}-${targetGroup.id}`;
      const reverseEdgeKey = `${targetGroup.id}-${sourceGroup.id}`;

      if (!edgeKeySet.has(edgeKey) && !edgeKeySet.has(reverseEdgeKey)) {
        // Add inter-group edge
        visibleEdges.push({
          source: sourceGroup.id,
          target: targetGroup.id,
          lineStyle: {
            width: Math.min(5, 1 + Math.log2(10)),
            color: '#999',
            curveness: 0.3
          }
        });

        edgeKeySet.add(edgeKey);
      }
    }
  });
}

function groupByFile(nodes) {
  const groups = {};
  nodes.forEach(node => {
    const key = node.path;
    if (!groups[key]) {
      groups[key] = {
        id: `group_file_${key.replace(/[^a-zA-Z0-9]/g, '_')}`,
        name: node.path.split('/').pop(),
        type: 'file',
        children: [],
        collapsed: false,
        nodeCount: 0,
        category: getDominantCategory(nodes.filter(n => n.path === key))
      };
    }
    groups[key].children.push(node.id);
    groups[key].nodeCount++;
  });
  return Object.values(groups);
}

function groupByModule(nodes) {
  const groups = {};
  nodes.forEach(node => {
    const parts = node.path.split('/');
    const module = parts.slice(0, -1).join('/') || 'root';
    if (!groups[module]) {
      groups[module] = {
        id: `group_module_${module.replace(/[^a-zA-Z0-9]/g, '_')}`,
        name: module.split('/').pop(),
        type: 'module',
        children: [],
        collapsed: false,
        nodeCount: 0,
        category: getDominantCategory(nodes.filter(n => {
          const nodeParts = n.path.split('/');
          return nodeParts.slice(0, -1).join('/') === module;
        }))
      };
    }
    groups[module].children.push(node.id);
    groups[module].nodeCount++;
  });
  return Object.values(groups);
}

function groupByCategory(nodes) {
  const groups = {};
  nodes.forEach(node => {
    const key = node.category;
    if (!groups[key]) {
      groups[key] = {
        id: `group_category_${key}`,
        name: key,
        type: 'category',
        children: [],
        collapsed: false,
        nodeCount: 0,
        category: key
      };
    }
    groups[key].children.push(node.id);
    groups[key].nodeCount++;
  });
  return Object.values(groups);
}

function getDominantCategory(nodes) {
  if (nodes.length === 0) return 'Default';

  const categoryCount = {};
  nodes.forEach(node => {
    categoryCount[node.category] = (categoryCount[node.category] || 0) + 1;
  });

  let maxCount = 0;
  let dominantCategory = 'Default';

  for (const [category, count] of Object.entries(categoryCount)) {
    if (count > maxCount) {
      maxCount = count;
      dominantCategory = category;
    }
  }

  return dominantCategory;
}

function handleThemeChange(theme) {
  const body = document.body;

  // Remove all theme classes
  body.classList.remove('dark-theme', 'light-theme');

  // Apply selected theme
  switch (theme) {
    case 'dark':
      body.classList.add('dark-theme');
      break;
    case 'light':
      body.classList.add('light-theme');
      break;
    default:
      // Default theme - no class
      break;
  }

  // Update chart colors if needed
  if (theme === 'dark') {
    chart.setOption({
      backgroundColor: '#1a1a1a',
      textStyle: { color: '#ffffff' }
    });
  } else if (theme === 'light') {
    chart.setOption({
      backgroundColor: '#ffffff',
      textStyle: { color: '#333333' }
    });
  } else {
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
  link.download = `callgraph_${getTimestamp()}.png`;
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
  link.download = `callgraph_${getTimestamp()}.svg`;
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
  // Search (debounced)
  const searchInput = document.getElementById('search-input');
  let searchTimeout;

  searchInput.addEventListener('input', (e) => {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => {
      handleSearch(e.target.value);
    }, 300);
  });

  // Group mode
  document.getElementById('group-mode').addEventListener('change', (e) => {
    handleGroupChange(e.target.value);
  });

  // Group click handler
  chart.on('click', handleGroupClick);

  // Theme
  document.getElementById('theme-select').addEventListener('change', (e) => {
    handleThemeChange(e.target.value);
  });

  // Export
  document.getElementById('export-png').addEventListener('click', handleExportPNG);
  document.getElementById('export-svg').addEventListener('click', handleExportSVG);

  // Zoom
  document.getElementById('zoom-in').addEventListener('click', () => {
    chart.dispatchAction({ type: 'dataZoom', start: 0, end: 90 });
  });
  document.getElementById('zoom-out').addEventListener('click', () => {
    chart.dispatchAction({ type: 'dataZoom', start: 10, end: 100 });
  });
  document.getElementById('reset-zoom').addEventListener('click', () => {
    chart.dispatchAction({ type: 'dataZoom', start: 0, end: 100 });
  });

  // Window resize
  window.addEventListener('resize', () => {
    chart.resize();
  });
}
"""
