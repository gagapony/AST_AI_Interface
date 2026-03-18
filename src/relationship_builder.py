"""Call relationship builder."""

import logging
from typing import Dict, List, Tuple

from .call_analyzer import CallAnalyzer, CallInfo
from .function_extractor import FunctionInfo
from .function_registry import FunctionRegistry


class RelationshipBuilder:
    """Build bidirectional call graph relationships."""

    def __init__(self, registry: FunctionRegistry, analyzer: CallAnalyzer):
        """Initialize builder with registry and analyzer."""
        self._registry = registry
        self._analyzer = analyzer

    def build(self) -> Dict[int, Tuple[List[int], List[int]]]:
        """
        Build call relationships for all functions.

        Returns:
            Dictionary mapping function index to (parents, children) tuples
        """
        relationships: Dict[int, Tuple[List[int], List[int]]] = {}

        # First pass: collect all children (functions called by each function)
        children_map: Dict[int, List[int]] = {}

        logging.info("Building call relationships...")

        for func_idx, func in enumerate(self._registry.get_all()):
            calls = self._analyzer.analyze_calls(func)
            children = []

            for call in calls:
                if call.callee_index is not None:
                    # Avoid self-loops
                    if call.callee_index != func_idx:
                        children.append(call.callee_index)

            # Remove duplicates while preserving order
            unique_children = list(dict.fromkeys(children))
            children_map[func_idx] = unique_children

            logging.debug(f"Function [{func_idx}] calls: {unique_children}")

        # Second pass: build parents (functions that call this function)
        parents_map: Dict[int, List[int]] = {}

        for func_idx, func in enumerate(self._registry.get_all()):
            parents_map[func_idx] = []

            # Find functions that call this one
            for caller_idx, children in children_map.items():
                if func_idx in children:
                    parents_map[func_idx].append(caller_idx)

            logging.debug(f"Function [{func_idx}] called by: {parents_map[func_idx]}")

        # Build final relationships
        for func_idx in range(self._registry.count()):
            relationships[func_idx] = (
                parents_map.get(func_idx, []),
                children_map.get(func_idx, [])
            )

        return relationships
