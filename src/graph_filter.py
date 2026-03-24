"""Graph filtering functionality for function call graphs."""

import logging
from typing import Dict, List, Optional, Set, Tuple, Any
from collections import deque


class GraphFilter:
    """
    Filter function call graph using path slice approach.

    Path slice includes:
    - Upward: all callers in the call chain (who calls this, who calls them, etc.)
    - Downward: all callees in the call chain (functions called, functions they call, etc.)

    Unlike BFS subgraph expansion, this only includes nodes on the call paths,
    not siblings/cousins of those paths.
    """

    def __init__(self, functions: List[Dict[str, Any]]) -> None:
        """
        Initialize filter with full graph data.

        Args:
            functions: List of function dictionaries from JSON output
                       Each has 'index', 'self', 'parents', 'children' fields
        """
        self.functions: List[Dict[str, Any]] = functions
        # Build quick lookup map: qualified_name -> list of function indices
        self.name_to_indices: Dict[str, List[int]] = self._build_name_map()
        # Build adjacency map for fast traversal
        self.adjacency: Dict[int, Tuple[List[int], List[int]]] = self._build_adjacency_map()
        self.logger: logging.Logger = logging.getLogger(__name__)

    def filter_by_function(self, target_name: str) -> List[Dict[str, Any]]:
        """
        Filter graph to include only nodes on call paths from target function.

        This uses a path slice approach:
        - Upward: trace callers (who calls this function, who calls them, etc.)
        - Downward: trace callees (functions called, functions they call, etc.)
        - Result: union of both directions (no depth limit)

        Args:
            target_name: qualified_name of target function

        Returns:
            Filtered list of function dictionaries with re-indexed nodes

        Raises:
            ValueError: If target function not found
        """
        self.logger.info(f"Filtering graph by function (path slice): {target_name}")

        # 1. Find target function indices
        target_indices: Optional[List[int]] = self.name_to_indices.get(target_name)

        if not target_indices:
            raise ValueError(f"Function '{target_name}' not found in graph")

        self.logger.info(f"Found {len(target_indices)} target function(s)")

        # 2. Trace upward (callers) and downward (callees)
        upward_nodes: Set[int] = self._trace_upward(target_indices)
        self.logger.info(f"Upward trace: {len(upward_nodes)} nodes")

        downward_nodes: Set[int] = self._trace_downward(target_indices)
        self.logger.info(f"Downward trace: {len(downward_nodes)} nodes")

        # 3. Merge both directions
        all_nodes: Set[int] = upward_nodes | downward_nodes
        self.logger.info(f"Total path slice: {len(all_nodes)} nodes")

        # 4. Filter and re-index nodes
        filtered_functions: List[Dict[str, Any]] = self._filter_and_reindex(all_nodes)

        self.logger.info(f"Filtered graph: {len(filtered_functions)} nodes "
                        f"(from {len(self.functions)} total)")

        return filtered_functions

    def _build_name_map(self) -> Dict[str, List[int]]:
        """Build map from qualified_name to function indices."""
        name_map: Dict[str, List[int]] = {}
        for func in self.functions:
            qname: str = func['self']['qualified_name']
            if qname not in name_map:
                name_map[qname] = []
            name_map[qname].append(func['index'])
        return name_map

    def _build_adjacency_map(self) -> Dict[int, Tuple[List[int], List[int]]]:
        """Build adjacency map for fast graph traversal."""
        adjacency: Dict[int, Tuple[List[int], List[int]]] = {}
        for func in self.functions:
            idx: int = func['index']
            adjacency[idx] = (func['parents'], func['children'])
        return adjacency

    def _trace_upward(self, start_indices: List[int]) -> Set[int]:
        """
        Trace upward along caller chains (who calls these functions).

        Args:
            start_indices: List of starting node indices

        Returns:
            Set of all nodes on caller chains
        """
        nodes: Set[int] = set(start_indices)
        queue: deque[int] = deque(start_indices)

        while queue:
            current: int = queue.popleft()

            # Get parents (who calls this function)
            parents: List[int] = self.adjacency.get(current, ([], []))[0]

            for parent in parents:
                if parent not in nodes:
                    nodes.add(parent)
                    queue.append(parent)

        return nodes

    def _trace_downward(self, start_indices: List[int]) -> Set[int]:
        """
        Trace downward along callee chains (functions called by these).

        Args:
            start_indices: List of starting node indices

        Returns:
            Set of all nodes on callee chains
        """
        nodes: Set[int] = set(start_indices)
        queue: deque[int] = deque(start_indices)

        while queue:
            current: int = queue.popleft()

            # Get children (functions called by this function)
            children: List[int] = self.adjacency.get(current, ([], []))[1]

            for child in children:
                if child not in nodes:
                    nodes.add(child)
                    queue.append(child)

        return nodes

    def _filter_and_reindex(self, keep_indices: Set[int]) -> List[Dict[str, Any]]:
        """
        Filter functions to keep only those in keep_indices and re-index them.

        Args:
            keep_indices: Set of function indices to keep

        Returns:
            List of filtered function dictionaries with new indices
        """
        # Create old_index -> new_index mapping
        index_mapping: Dict[int, int] = {
            old_idx: new_idx
            for new_idx, old_idx in enumerate(sorted(keep_indices))
        }

        filtered: List[Dict[str, Any]] = []

        for func in self.functions:
            old_idx: int = func['index']
            if old_idx not in keep_indices:
                continue

            # Create new function entry
            new_func: Dict[str, Any] = {
                'index': index_mapping[old_idx],
                'self': func['self'],
                'parents': [index_mapping[p] for p in func['parents'] if p in keep_indices],
                'children': [index_mapping[c] for c in func['children'] if c in keep_indices]
            }

            filtered.append(new_func)

        # Sort by new index
        filtered.sort(key=lambda f: f['index'])

        return filtered
