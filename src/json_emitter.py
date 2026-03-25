"""JSON output emitter."""

import json
import sys
from typing import Any, Dict, List, Optional, Tuple, Union

from .function_extractor import FunctionInfo


class JSONEmitter:
    """Emit function call relationships as JSON."""

    def __init__(self, output_file: Optional[str] = None):
        """Initialize emitter with optional output file path."""
        self._output_file = output_file

    def _serialize_relationships(self, rels: List[Union[int, Dict[str, Any]]]) -> List[Union[int, Dict[str, Any]]]:
        """Serialize relationship entries, preserving type markers."""
        serialized: List[Union[int, Dict[str, Any]]] = []
        for rel in rels:
            if isinstance(rel, dict):
                serialized.append(dict(rel))  # Copy to ensure serializable
            else:
                serialized.append(rel)
        return serialized

    def emit(
        self,
        functions: List[FunctionInfo],
        relationships: Dict[int, Tuple[List[Union[int, Dict[str, Any]]], List[Union[int, Dict[str, Any]]]]]
    ) -> None:
        """
        Emit JSON output to file or stdout.

        Args:
            functions: List of all functions
            relationships: Dictionary mapping index to (parents, children)
        """
        output_data = []

        for func in functions:
            # Find this function's index
            func_index = None
            for idx, f in enumerate(functions):
                if f == func:
                    func_index = idx
                    break

            if func_index is None:
                continue

            # Get relationships
            parents, children = relationships.get(func_index, ([], []))

            # Format function self data
            self_data = {
                "path": func.path,
                "line": list(func.line_range),
                "type": "function",
                "name": func.name,
                "qualified_name": func.qualified_name,
                "brief": func.brief
            }

            # Create output entry using dict literal
            output_entry = {
                "index": func_index,
                "self": self_data,
                "parents": self._serialize_relationships(parents),
                "children": self._serialize_relationships(children)
            }

            output_data.append(output_entry)

        # Write output
        json_output = json.dumps(output_data, indent=2, ensure_ascii=False)

        if self._output_file:
            with open(self._output_file, 'w', encoding='utf-8') as output_file_handle:
                output_file_handle.write(json_output)
        else:
            print(json_output)
