"""Call relationship builder."""

import logging
from typing import Dict, List, Tuple, Any, Union

from .call_analyzer import CallAnalyzer, CallInfo
from .function_extractor import FunctionInfo
from .function_registry import FunctionRegistry


class RelationshipBuilder:
    """Build bidirectional call graph relationships."""

    def __init__(self, registry: FunctionRegistry, analyzer: CallAnalyzer):
        """Initialize builder with registry and analyzer."""
        self._registry = registry
        self._analyzer = analyzer

    def _normalize_entry(self, entry: Union[int, Dict[str, Any]]) -> Dict[str, Any]:
        """Convert entry to dict for consistent comparison."""
        if isinstance(entry, dict):
            return entry
        return {"index": entry, "type": "direct"}

    def build(self) -> Dict[int, Tuple[List[Union[int, Dict[str, Any]]], List[Union[int, Dict[str, Any]]]]]:
        """
        Build call relationships for all functions.

        Returns:
            Dictionary mapping function index to (parents, children) tuples
        """
        relationships: Dict[int, Tuple[List[Union[int, Dict[str, Any]]], List[Union[int, Dict[str, Any]]]]] = {}

        # First pass: collect all children (functions called by each function)
        children_map: Dict[int, List[Union[int, Dict[str, Any]]]] = {}

        logging.info("Building call relationships...")

        for func_idx, func in enumerate(self._registry.get_all()):
            calls = self._analyzer.analyze_calls(func)
            children: List[Union[int, Dict[str, Any]]] = []

            for call in calls:
                # Handle different call types
                if call.callee_index is not None:
                    # Avoid self-loops
                    if call.callee_index != func_idx:
                        # Always use dict format
                        direct_entry: Dict[str, Any] = {
                            "index": call.callee_index,
                            "type": "direct"
                        }
                        children.append(direct_entry)
                elif call.possible_targets:
                    # Handle multiple possible targets (indirect/virtual calls)
                    for target_idx in call.possible_targets:
                        if target_idx != func_idx:
                            # Create relationship entry with type markers
                            target_entry: Dict[str, Any] = {
                                "index": target_idx,
                                "type": "indirect" if call.is_indirect else "virtual" if call.is_virtual else "direct"
                            }
                            if len(call.possible_targets) > 1:
                                target_entry["possible_targets"] = call.possible_targets
                            children.append(target_entry)
                elif call.is_macro:
                    # Macro calls don't have a specific function index
                    # Add a special entry to mark macro usage
                    macro_entry: Dict[str, Any] = {
                        "type": "macro",
                        "name": call.callee_name
                    }
                    if call.macro_info:
                        macro_entry["arguments"] = call.macro_info.arguments
                    children.append(macro_entry)

            # Remove duplicates using frozenset as hashable key
            normalized_children = [self._normalize_entry(c) for c in children]
            # Map frozenset items back to original dict for deduplication
            entry_map: Dict[frozenset[Tuple[str, Any]], Dict[str, Any]] = {
                frozenset(entry.items()): entry for entry in normalized_children
            }
            unique_children: List[Union[int, Dict[str, Any]]] = list(entry_map.values())
            children_map[func_idx] = unique_children

            logging.debug(f"Function [{func_idx}] calls: {unique_children}")

        # Second pass: build parents (functions that call this function)
        parents_map: Dict[int, List[Union[int, Dict[str, Any]]]] = {}

        for func_idx, func in enumerate(self._registry.get_all()):
            parents_map[func_idx] = []

            # Find functions that call this one
            for caller_idx, children in children_map.items():
                for child in children:
                    # Handle both direct int and dict entries
                    if isinstance(child, int):
                        child_idx = child
                    else:
                        # Only process entries with an "index" key
                        if "index" not in child:
                            continue
                        child_idx = child["index"]

                    if child_idx == func_idx:
                        parents_map[func_idx].append(caller_idx)
                        break

            logging.debug(f"Function [{func_idx}] called by: {parents_map[func_idx]}")

        # Build final relationships
        for func_idx in range(self._registry.count()):
            relationships[func_idx] = (
                parents_map.get(func_idx, []),
                children_map.get(func_idx, [])
            )

        return relationships
