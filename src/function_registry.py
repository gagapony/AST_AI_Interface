"""Function registry for indexing discovered functions."""

import logging
from typing import Dict, List, Optional

from .function_extractor import FunctionInfo


class FunctionRegistry:
    """Index and lookup functions by various keys."""

    def __init__(self) -> None:
        """Initialize empty registry."""
        self._functions: List[FunctionInfo] = []
        self._qualified_name_to_indices: Dict[str, List[int]] = {}

    def add_function(self, info: FunctionInfo) -> int:
        """
        Add a function to the registry.

        Args:
            info: FunctionInfo object

        Returns:
            Index assigned to this function
        """
        index = len(self._functions)
        self._functions.append(info)

        # Index by qualified name
        qname = info.qualified_name
        if qname not in self._qualified_name_to_indices:
            self._qualified_name_to_indices[qname] = []
        self._qualified_name_to_indices[qname].append(index)

        logging.debug(f"Registered function [{index}]: {info.qualified_name}")
        return index

    def get_by_index(self, index: int) -> Optional[FunctionInfo]:
        """
        Get function by index.

        Args:
            index: Function index

        Returns:
            FunctionInfo or None if not found
        """
        if 0 <= index < len(self._functions):
            return self._functions[index]
        return None

    def get_by_qualified_name(self, name: str) -> List[int]:
        """
        Get function indices by qualified name.

        Args:
            name: Qualified function name

        Returns:
            List of indices (may have multiple for overloaded functions)
        """
        return self._qualified_name_to_indices.get(name, [])

    def get_all(self) -> List[FunctionInfo]:
        """
        Get all registered functions.

        Returns:
            List of all FunctionInfo objects
        """
        return self._functions

    def count(self) -> int:
        """
        Get total number of registered functions.

        Returns:
            Number of functions
        """
        return len(self._functions)
