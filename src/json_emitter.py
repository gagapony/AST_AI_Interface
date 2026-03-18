"""JSON output emitter."""

import json
import sys
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional, Tuple

from .function_extractor import FunctionInfo


@dataclass
class FunctionOutput:
    """Output format for a single function."""
    index: int
    self: Dict[str, Any]
    parents: List[int]
    children: List[int]


class JSONEmitter:
    """Emit function call relationships as JSON."""

    def __init__(self, output_file: Optional[str] = None):
        """Initialize emitter with optional output file path."""
        self._output_file = output_file

    def emit(
        self,
        functions: List[FunctionInfo],
        relationships: Dict[int, Tuple[List[int], List[int]]]
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

            # Create output entry
            output_entry = FunctionOutput(
                index=func_index,
                self=self_data,
                parents=parents,
                children=children
            )

            output_data.append(asdict(output_entry))

        # Write output
        json_output = json.dumps(output_data, indent=2, ensure_ascii=False)

        if self._output_file:
            with open(self._output_file, 'w', encoding='utf-8') as f:
                f.write(json_output)
        else:
            print(json_output)
