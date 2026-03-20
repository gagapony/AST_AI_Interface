"""ECharts HTML generator for function call graphs."""

import json
import logging
from pathlib import Path
from string import Template
from typing import Dict, List, Tuple, Optional, Union

from .function_extractor import FunctionInfo
from .echarts_templates import CSS_TEMPLATE, HTML_TEMPLATE, APP_SCRIPT_TEMPLATE


class EChartsGenerator:
    """Generate HTML with ECharts visualization from function call relationships."""

    def __init__(self,
                 functions: Union[List[FunctionInfo], List[Dict]],
                 relationships: Dict[int, Tuple[List[int], List[int]]],
                 logger: Optional[logging.Logger] = None):
        """
        Initialize ECharts generator.

        Args:
            functions: List of FunctionInfo objects or list of dicts (from JSON)
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
        # Transform data to ECharts format
        echarts_data = self._transform_to_echarts()

        # Serialize data for embedding
        data_json = json.dumps(echarts_data, ensure_ascii=False, indent=2)

        # Use Template to avoid brace escaping issues
        template = Template(HTML_TEMPLATE)

        # Generate HTML
        html = template.substitute(
            css=CSS_TEMPLATE,
            data=data_json,
            app_script=APP_SCRIPT_TEMPLATE
        )

        return html

    def _transform_to_echarts(self) -> Dict:
        """
        Transform function data to ECharts graph format.

        Returns:
            Dictionary with nodes, edges, and categories
        """
        self.logger.info("Transforming data to ECharts format...")

        # Create nodes
        nodes = self._create_nodes()

        # Create edges
        edges = self._create_edges()

        # Assign categories
        nodes = self._assign_categories(nodes)

        # Calculate node sizes
        nodes = self._calculate_sizes(nodes)

        # Get category definitions
        categories = self._get_categories()

        self.logger.info(f"Transformed {len(nodes)} nodes and {len(edges)} edges")

        return {
            'nodes': nodes,
            'edges': edges,
            'categories': categories
        }

    def _create_nodes(self) -> List[Dict]:
        """
        Create ECharts node objects from function data.

        Supports both FunctionInfo objects and dict (from JSON).

        Returns:
            List of node dictionaries
        """
        nodes = []

        for func in self.functions:
            # Handle both dict and FunctionInfo inputs
            if isinstance(func, dict):
                # From JSON: dict has 'index' and 'self' dict with fields
                func_index = func.get('index')
                self_dict = func.get('self', {})
                func_name = self_dict.get('name', '')
                func_path = self_dict.get('path', '')
                func_line_range = self_dict.get('line', [])
                func_brief = self_dict.get('brief', '')
            else:
                # FunctionInfo object
                func_index = func.index
                func_name = func.name
                func_path = func.path
                func_line_range = list(func.line_range)
                func_brief = func.brief or ''

            # Validate func_index before using
            if func_index is None:
                self.logger.warning(f"Function has no index: {func}")
                continue

            # Get relationships
            parents, children = self.relationships.get(func_index, ([], []))

            node = {
                'id': func_index,
                'name': func_name,
                'path': func_path,
                'line_range': func_line_range,
                'brief': func_brief,
                'parents': parents,
                'children': children,
                'value': len(parents) + len(children)
            }

            nodes.append(node)

        return nodes

    def _create_edges(self) -> List[Dict]:
        """
        Create ECharts edge objects from relationship data.

        Returns:
            List of edge dictionaries
        """
        edges = []

        for func_idx, (parents, children) in self.relationships.items():
            for child_idx in children:
                # Create edge from parent to child
                if child_idx < len(self.functions):
                    edge = {
                        'source': func_idx,
                        'target': child_idx,
                        'lineStyle': {
                            'width': self._calculate_edge_width(children),
                            'color': '#999'
                        }
                    }
                    edges.append(edge)

        self.logger.debug(f"Created {len(edges)} edges")
        return edges

    def _calculate_edge_width(self, children: List[int]) -> float:
        """
        Calculate edge width based on number of children.

        Args:
            children: List of child indices

        Returns:
            Edge width
        """
        # Logarithmic scaling: more children = thicker edges
        count = len(children)
        return min(5, max(1, 1 + (count / 10)))

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

        if '/control/' in path_lower:
            return 'Control'
        elif '/network/' in path_lower:
            return 'Network'
        elif '/data/' in path_lower:
            return 'Data'
        elif '/utils/' in path_lower or '/util/' in path_lower:
            return 'Utility'
        elif '/lib/' in path_lower or '/sys/' in path_lower:
            return 'System'
        else:
            return 'Default'

    def _calculate_sizes(self, nodes: List[Dict]) -> List[Dict]:
        """
        Calculate symbol sizes for nodes based on call count.

        Args:
            nodes: List of node dictionaries

        Returns:
            List of nodes with symbolSize field added
        """
        if not nodes:
            return nodes

        # Find maximum call count
        max_calls = max(node['value'] for node in nodes)

        if max_calls == 0:
            max_calls = 1  # Avoid division by zero

        # Calculate sizes: range 10-50
        for node in nodes:
            ratio = node['value'] / max_calls
            node['symbolSize'] = int(10 + ratio * 40)

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

    logging.info(f"ECharts HTML written to {output_path}")
