"""Call relationship analysis."""

import logging
from dataclasses import dataclass
from typing import List, Optional, Tuple, Any, Set

import clang.cindex  # type: ignore

from .function_extractor import FunctionInfo
from .function_registry import FunctionRegistry


@dataclass
class CallInfo:
    """Information about a function call."""
    caller_cursor: clang.cindex.Cursor
    callee_name: str
    callee_index: Optional[int]
    is_macro: bool = False
    is_indirect: bool = False
    is_virtual: bool = False
    possible_targets: Optional[List[int]] = None
    macro_info: Optional[Any] = None


class CallAnalyzer:
    """Analyze function calls within function bodies."""

    def __init__(self,
                 function_registry: FunctionRegistry,
                 feature_registry: Optional[Any] = None):
        """
        Initialize analyzer with registries.

        Args:
            function_registry: FunctionRegistry instance
            feature_registry: Optional FeatureRegistry instance
        """
        self._registry = function_registry
        self._feature_registry = feature_registry

    def analyze_calls(self, function: FunctionInfo) -> List[CallInfo]:
        """
        Find all function calls within a function.

        Args:
            function: FunctionInfo to analyze

        Returns:
            List of CallInfo objects
        """
        calls: List[CallInfo] = []

        if function.raw_cursor is None:
            return calls

        for cursor in function.raw_cursor.walk_preorder():
            # Skip the function itself and its direct children (parameters, etc.)
            if cursor == function.raw_cursor:
                continue

            if cursor.kind == clang.cindex.CursorKind.CALL_EXPR:
                call_info = self._analyze_call(cursor)
                if call_info:
                    calls.append(call_info)

        # Analyze macro invocations if feature registry available
        if self._feature_registry and function.raw_cursor is not None:
            from .feature_analyzer import FeatureAnalyzer
            feature_analyzer = FeatureAnalyzer(function.raw_cursor.translation_unit, self._registry)
            macro_invocations = feature_analyzer.extract_macro_invocations(function.raw_cursor)

            for invocation in macro_invocations:
                macro_call = self._analyze_macro_call(invocation, function)
                if macro_call:
                    calls.append(macro_call)

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
        try:
            referenced = call_cursor.referenced
        except Exception as e:
            logging.debug(f"Failed to get referenced cursor: {e}")
            return None

        # Check if this is a call through a function pointer
        if referenced and referenced.kind in (
            clang.cindex.CursorKind.VAR_DECL,
            clang.cindex.CursorKind.PARM_DECL
        ):
            return self._analyze_function_pointer_call(call_cursor, referenced)

        # Check for virtual function call
        if referenced and referenced.kind == clang.cindex.CursorKind.CXX_METHOD:
            if self._is_virtual_method(referenced):
                return self._analyze_virtual_call(call_cursor, referenced)

        # Direct call analysis
        if not referenced:
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
        callee_index: int
        if len(callee_indices) == 1:
            callee_index = callee_indices[0]
        else:
            # Try to match overload by comparing arguments
            matched_index = self._match_overload(call_cursor, callee_indices)
            if matched_index is None:
                logging.debug(f"Cannot resolve overload for {callee_qualified_name}")
                return None
            callee_index = matched_index

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
        scope_parts: List[str] = []
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

    # ========== Feature Analysis Methods ==========

    def _analyze_function_pointer_call(
        self,
        call_cursor: clang.cindex.Cursor,
        var_cursor: clang.cindex.Cursor
    ) -> Optional[CallInfo]:
        """
        Analyze a call through a function pointer.

        Args:
            call_cursor: libclang Cursor for CALL_EXPR
            var_cursor: libclang Cursor for the variable being called

        Returns:
            CallInfo with multiple possible targets or None
        """
        if not self._feature_registry:
            return None

        # Look up in registry
        pointer_info = self._feature_registry.get_pointer_by_name(var_cursor.spelling)
        if not pointer_info:
            logging.debug(f"Function pointer not in registry: {var_cursor.spelling}")
            return None

        # Return possible targets
        if pointer_info.possible_targets:
            possible_targets: List[int] = list(pointer_info.possible_targets)
            callee_idx: Optional[int] = possible_targets[0] if len(possible_targets) == 1 else None
            return CallInfo(
                caller_cursor=call_cursor,
                callee_name=var_cursor.spelling,
                callee_index=callee_idx,
                is_indirect=True,
                possible_targets=possible_targets
            )

        return None

    def _analyze_virtual_call(
        self,
        call_cursor: clang.cindex.Cursor,
        method_cursor: clang.cindex.Cursor
    ) -> Optional[CallInfo]:
        """
        Analyze a virtual function call.

        Args:
            call_cursor: libclang Cursor for CALL_EXPR
            method_cursor: libclang Cursor for the virtual method

        Returns:
            CallInfo with multiple possible targets or None
        """
        if not self._feature_registry:
            return None

        # Get qualified name of called method
        called_method_name: str = self._safe_get_qualified_name(method_cursor)

        # Get class of the called method
        called_class: Optional[str] = self._safe_get_method_class(method_cursor)
        if not called_class:
            return None

        # Find all derived classes that override this method
        derived_classes: List[str] = self._feature_registry.get_all_derived(called_class)

        # Collect all overriding methods
        possible_indices: Set[int] = set()

        # Add the base method itself
        base_indices = self._registry.get_by_qualified_name(called_method_name)
        possible_indices.update(base_indices)

        # Add overrides from derived classes
        for derived_class_name in derived_classes:
            derived_class = self._feature_registry.get_class_by_name(derived_class_name)
            if not derived_class:
                continue

            # Look for overriding method in derived class
            override_name = f"{derived_class_name}::{method_cursor.spelling}"
            override_indices = self._registry.get_by_qualified_name(override_name)
            possible_indices.update(override_indices)

        if possible_indices:
            possible_targets: List[int] = list(possible_indices)
            return CallInfo(
                caller_cursor=call_cursor,
                callee_name=call_cursor.spelling,
                callee_index=possible_targets[0] if len(possible_targets) == 1 else None,
                is_virtual=True,
                possible_targets=possible_targets
            )

        return None

    def _analyze_macro_call(
        self,
        invocation: Any,
        function: FunctionInfo
    ) -> Optional[CallInfo]:
        """
        Analyze a macro invocation as a potential function call.

        Args:
            invocation: MacroInvocation object
            function: FunctionInfo containing this invocation

        Returns:
            CallInfo or None if macro not found
        """
        if not self._feature_registry:
            return None

        # Look up macro in registry
        macro = self._feature_registry.get_macro_by_name(invocation.macro_name)
        if not macro:
            logging.debug(f"Macro not in registry: {invocation.macro_name}")
            return None

        # NO heuristic resolution - just mark as macro call
        return CallInfo(
            caller_cursor=function.raw_cursor,
            callee_name=invocation.macro_name,
            callee_index=None,  # No specific function
            is_macro=True,
            macro_info=invocation
        )

    def _is_virtual_method(self, cursor: clang.cindex.Cursor) -> bool:
        """
        Check if cursor is a virtual method.

        Args:
            cursor: libclang Cursor

        Returns:
            True if virtual method, False otherwise
        """
        try:
            return cursor.is_virtual_method()  # type: ignore[no-any-return]
        except Exception as e:
            logging.debug(f"Failed to check if method is virtual: {e}")
            return False

    def _safe_get_qualified_name(self, cursor: clang.cindex.Cursor) -> str:
        """
        Safely build qualified name from cursor.

        Args:
            cursor: libclang Cursor

        Returns:
            Qualified name string
        """
        parts: List[str] = []

        # Collect scope
        scope_parts: List[str] = []
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

            try:
                parent = parent.semantic_parent
            except Exception:
                break

        if scope_parts:
            parts.extend(scope_parts)

        parts.append(cursor.spelling)

        return "::".join(parts)

    def _safe_get_method_class(self, cursor: clang.cindex.Cursor) -> Optional[str]:
        """
        Get the qualified name of the method's class.

        Args:
            cursor: libclang Cursor

        Returns:
            Qualified name of class or None
        """
        try:
            parent = cursor.semantic_parent
            if parent and parent.kind in {
                clang.cindex.CursorKind.CLASS_DECL,
                clang.cindex.CursorKind.STRUCT_DECL,
                clang.cindex.CursorKind.CLASS_TEMPLATE,
            }:
                return self._safe_get_qualified_name(parent)
        except Exception as e:
            logging.debug(f"Failed to get method class: {e}")
        return None
