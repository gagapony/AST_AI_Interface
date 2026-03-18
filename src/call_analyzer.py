"""Call relationship analysis."""

import logging
from dataclasses import dataclass
from typing import List, Optional, Tuple

import clang.cindex

from .function_extractor import FunctionInfo
from .function_registry import FunctionRegistry


@dataclass
class CallInfo:
    """Information about a function call."""
    caller_cursor: clang.cindex.Cursor
    callee_name: str
    callee_index: Optional[int]


class CallAnalyzer:
    """Analyze function calls within function bodies."""

    def __init__(self, function_registry: FunctionRegistry):
        """Initialize analyzer with function registry."""
        self._registry = function_registry

    def analyze_calls(self, function: FunctionInfo) -> List[CallInfo]:
        """
        Find all function calls within a function.

        Args:
            function: FunctionInfo to analyze

        Returns:
            List of CallInfo objects
        """
        calls = []

        for cursor in function.raw_cursor.walk_preorder():
            # Skip the function itself and its direct children (parameters, etc.)
            if cursor == function.raw_cursor:
                continue

            if cursor.kind == clang.cindex.CursorKind.CALL_EXPR:
                call_info = self._analyze_call(cursor)
                if call_info:
                    calls.append(call_info)

        return calls

    def _analyze_call(self, call_cursor: clang.cindex.Cursor) -> Optional[CallInfo]:
        """
        Analyze a single call expression.

        Args:
            call_cursor: libclang Cursor for CALL_EXPR

        Returns:
            CallInfo or None if callee cannot be resolved
        """
        callee_name = call_cursor.spelling
        if not callee_name:
            return None

        # Get the referenced cursor (the function being called)
        referenced = call_cursor.referenced
        if not referenced:
            # Could be a function pointer or indirect call
            logging.debug(f"Cannot resolve call to {callee_name}: no reference")
            return None

        # Get qualified name of callee
        callee_qualified_name = self._get_qualified_name(referenced)

        # Resolve to function index
        callee_indices = self._registry.get_by_qualified_name(callee_qualified_name)

        if not callee_indices:
            logging.debug(f"Callee not found in registry: {callee_qualified_name}")
            return None

        # Handle overloading
        if len(callee_indices) == 1:
            callee_index = callee_indices[0]
        else:
            # Try to match overload by comparing arguments
            callee_index = self._match_overload(call_cursor, callee_indices)
            if callee_index is None:
                logging.debug(f"Cannot resolve overload for {callee_qualified_name}")
                return None

        return CallInfo(
            caller_cursor=call_cursor,
            callee_name=callee_name,
            callee_index=callee_index
        )

    def _get_qualified_name(self, cursor: clang.cindex.Cursor) -> str:
        """
        Build qualified name from cursor.

        Args:
            cursor: libclang Cursor

        Returns:
            Qualified name string
        """
        parts = []

        # Collect scope
        scope = self._collect_scope(cursor)
        if scope:
            parts.append(scope)

        # Add name
        parts.append(cursor.spelling)

        # Add parameters if this is a function/method
        if cursor.kind in (
            clang.cindex.CursorKind.FUNCTION_DECL,
            clang.cindex.CursorKind.CXX_METHOD,
            clang.cindex.CursorKind.CONSTRUCTOR,
            clang.cindex.CursorKind.DESTRUCTOR,
            clang.cindex.CursorKind.CONVERSION_FUNCTION,
        ):
            params = self._get_parameters(cursor)
            if params:
                parts.append(f"({params})")

        return "::".join(parts)

    def _collect_scope(self, cursor: clang.cindex.Cursor) -> str:
        """
        Collect namespace and class scope.

        Args:
            cursor: libclang Cursor

        Returns:
            Scope string
        """
        scope_parts = []
        parent = cursor.semantic_parent

        while parent:
            if parent.kind == clang.cindex.CursorKind.NAMESPACE:
                scope_parts.insert(0, parent.spelling)
            elif parent.kind in (
                clang.cindex.CursorKind.CLASS_DECL,
                clang.cindex.CursorKind.STRUCT_DECL,
                clang.cindex.CursorKind.CLASS_TEMPLATE,
            ):
                scope_parts.insert(0, parent.spelling)
            elif parent.kind == clang.cindex.CursorKind.TRANSLATION_UNIT:
                break

            parent = parent.semantic_parent

        return "::".join(scope_parts)

    def _get_parameters(self, cursor: clang.cindex.Cursor) -> str:
        """
        Get parameter types from cursor.

        Args:
            cursor: libclang Cursor

        Returns:
            Comma-separated parameter types
        """
        params = []
        for arg in cursor.get_arguments():
            param_type = arg.type.spelling
            params.append(param_type)
        return ", ".join(params)

    def _match_overload(self, call_cursor: clang.cindex.Cursor, indices: List[int]) -> Optional[int]:
        """
        Match an overloaded function call by comparing argument types.

        Args:
            call_cursor: libclang Cursor for CALL_EXPR
            indices: List of candidate function indices

        Returns:
            Best matching index or None
        """
        # Get argument types from call
        call_arg_types = self._get_call_arg_types(call_cursor)

        # For each candidate, compare parameter types
        best_match = None
        best_score = -1

        for idx in indices:
            func = self._registry.get_by_index(idx)
            if not func:
                continue

            # Get parameter types from function definition
            func_param_types = self._get_function_param_types(func.raw_cursor)

            # Compare types
            score = self._compare_types(call_arg_types, func_param_types)

            if score > best_score:
                best_score = score
                best_match = idx

        # Accept match if at least 50% of parameters match
        if best_score >= len(call_arg_types) * 0.5:
            return best_match

        return None

    def _get_call_arg_types(self, call_cursor: clang.cindex.Cursor) -> List[str]:
        """
        Get types of arguments in a call expression.

        Args:
            call_cursor: libclang Cursor for CALL_EXPR

        Returns:
            List of argument type strings
        """
        arg_types = []
        for arg in call_cursor.get_arguments():
            arg_type = arg.type.spelling
            arg_types.append(arg_type)
        return arg_types

    def _get_function_param_types(self, func_cursor: clang.cindex.Cursor) -> List[str]:
        """
        Get types of parameters in a function definition.

        Args:
            func_cursor: libclang Cursor for function

        Returns:
            List of parameter type strings
        """
        param_types = []
        for param in func_cursor.get_arguments():
            param_type = param.type.spelling
            param_types.append(param_type)
        return param_types

    def _compare_types(self, call_types: List[str], param_types: List[str]) -> int:
        """
        Compare two lists of types and return match count.

        Args:
            call_types: List of call argument types
            param_types: List of function parameter types

        Returns:
            Number of matching types
        """
        # Exact match required for now
        matches = 0
        for call_type, param_type in zip(call_types, param_types):
            if call_type == param_type:
                matches += 1

        return matches
