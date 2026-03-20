"""Mermaid tree diagram generator for call relationships."""

import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set

from .function_extractor import FunctionInfo


class MermaidGenerator:
    """Generate Mermaid tree diagrams from function call relationships."""

    def __init__(self,
                 functions: List[FunctionInfo],
                 relationships: Dict[int, Tuple[List[int], List[int]]],
                 max_depth: Optional[int] = None):
        """
        Initialize Mermaid generator.

        Args:
            functions: List of FunctionInfo objects
            relationships: Dict mapping function index to (parents, children) tuples
            max_depth: Optional maximum depth for tree traversal
        """
        self.functions = functions
        self.relationships = relationships
        self.max_depth = max_depth
        self.logger = logging.getLogger(__name__)
        self._visited: Set[int] = set()

    def generate(self, start_indices: Optional[List[int]] = None) -> str:
        """
        Generate Mermaid graph syntax.

        Args:
            start_indices: Optional list of root function indices to start from.
                          If None, uses functions with no parents.

        Returns:
            Mermaid graph string
        """
        # Find root nodes (functions with no parents)
        if start_indices is None:
            start_indices = self._find_root_nodes()

        # Generate graph
        lines = ["graph BT"]  # Bottom-to-top graph

        # Track visited nodes to avoid infinite recursion
        self._visited = set()

        # Generate edges
        edges = self._generate_edges(start_indices, depth=0)

        # If no root nodes (all nodes in cycles), still process edges by starting from all nodes
        if not edges and not start_indices and self.functions:
            # Add all function indices to process
            all_indices = list(range(len(self.functions)))
            edges = self._generate_edges(all_indices, depth=0)

        # Add style definitions
        lines.extend(self._generate_styles())

        # Add edges (if any)
        lines.extend(edges)

        return "\n".join(lines)

    def _find_root_nodes(self) -> List[int]:
        """Find functions with no parents (root nodes)."""
        roots = []
        for idx, (parents, _) in self.relationships.items():
            if not parents:
                roots.append(idx)
        return roots

    def _generate_edges(self, indices: List[int], depth: int) -> List[str]:
        """
        Generate edges recursively, avoiding cycles.

        Args:
            indices: List of function indices to process
            depth: Current depth in tree

        Returns:
            List of edge definitions
        """
        edges = []

        for idx in indices:
            # Skip if already visited (avoid cycles)
            if idx in self._visited:
                continue

            # Mark as visited
            self._visited.add(idx)

            # Check depth limit
            if self.max_depth and depth > self.max_depth:
                continue

            # Get children
            _, children = self.relationships.get(idx, ([], []))

            # Generate edges to children
            func_name = self._sanitize_function_name(self.functions[idx].name)
            node_id = f"node_{idx}"

            for child_idx in children:
                if child_idx >= len(self.functions):
                    # Skip invalid references
                    continue

                # Check if child is visited - this indicates a cycle
                if child_idx in self._visited:
                    # Still create the edge, but don't recurse
                    child_name = self._sanitize_function_name(self.functions[child_idx].name)
                    child_id = f"node_{child_idx}"

                    edge_label = self._get_edge_label(self.functions[child_idx])

                    if edge_label:
                        sanitized_label = self._sanitize_edge_label(edge_label)
                        edge_def = f'    {child_id}["{child_name}"] -->|"{sanitized_label}"| {node_id}["{func_name}"]'
                    else:
                        edge_def = f'    {child_id}["{child_name}"] --> {node_id}["{func_name}"]'

                    edges.append(edge_def)
                    continue

                child_name = self._sanitize_function_name(self.functions[child_idx].name)
                child_id = f"node_{child_idx}"

                # Get edge label (filename + line range)
                edge_label = self._get_edge_label(self.functions[child_idx])

                # Create edge definition
                if edge_label:
                    sanitized_label = self._sanitize_edge_label(edge_label)
                    edge_def = f'    {child_id}["{child_name}"] -->|"{sanitized_label}"| {node_id}["{func_name}"]'
                else:
                    edge_def = f'    {child_id}["{child_name}"] --> {node_id}["{func_name}"]'

                edges.append(edge_def)

            # Recursively process children
            if children:
                child_edges = self._generate_edges(children, depth + 1)
                edges.extend(child_edges)

        return edges

    def _get_edge_label(self, func: FunctionInfo) -> str:
        """
        Generate edge label with filename and line range.

        Args:
            func: FunctionInfo object

        Returns:
            Edge label string (e.g., "main.cpp:270-275")
        """
        filename = Path(func.path).name
        line_start, line_end = func.line_range

        if line_start == line_end:
            return f"{filename}:{line_start}"
        else:
            return f"{filename}:{line_start}-{line_end}"

    def _sanitize_edge_label(self, label: str) -> str:
        """
        Sanitize edge label for Mermaid syntax.

        Args:
            label: Edge label string

        Returns:
            Sanitized label
        """
        # Escape special characters in edge labels
        label = label.replace('"', '&quot;')
        return label

    def _generate_styles(self) -> List[str]:
        """
        Generate style definitions for nodes.

        Returns:
            List of style definitions
        """
        styles = [
            "    %% Node styles",
            "    classDef default fill:#FFFFFF,stroke:#000000,stroke-width:2px,color:#000000,font-size:12px;",
        ]
        return styles

    def _sanitize_function_name(self, name: str) -> str:
        """
        Sanitize function name for Mermaid syntax.

        Args:
            name: Function name

        Returns:
            Sanitized name
        """
        # Replace problematic characters with underscores
        # This is a simple sanitization; may need refinement for complex names
        return name.replace('<', '&lt;').replace('>', '&gt;')


def write_mermaid_file(mermaid_content: str, output_path: str) -> None:
    """
    Write Mermaid content to file.

    Args:
        mermaid_content: Mermaid graph string
        output_path: Path to output file
    """
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(mermaid_content)

    logging.info(f"Mermaid diagram written to {output_path}")
