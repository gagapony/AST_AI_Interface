"""Function extraction from AST."""

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, List, Optional, Tuple

if TYPE_CHECKING:
    try:
        import clang.cindex  # type: ignore
    except ImportError:
        pass

try:
    import clang.cindex
    CLANG_AVAILABLE = True
except ImportError:
    CLANG_AVAILABLE = False

from .doxygen_parser import DoxygenParser


@dataclass
class FunctionInfo:
    """Information about a function definition."""
    path: str
    line_range: Tuple[int, int]
    name: str
    qualified_name: str
    brief: Optional[str]
    raw_cursor: Optional['clang.cindex.Cursor'] = None  # Use Optional when clang not available
    index: Optional[int] = None  # ECharts requires index


class FunctionExtractor:
    """Extract function definitions from AST."""

    if CLANG_AVAILABLE:
        # Cursor kinds that represent functions
        FUNCTION_KINDS = {
            clang.cindex.CursorKind.FUNCTION_DECL,
            clang.cindex.CursorKind.CXX_METHOD,
            clang.cindex.CursorKind.CONSTRUCTOR,
            clang.cindex.CursorKind.DESTRUCTOR,
            clang.cindex.CursorKind.CONVERSION_FUNCTION,
        }

    def __init__(self, tu: 'clang.cindex.TranslationUnit') -> None:
        """
        Initialize extractor with a translation unit.

        Args:
            tu: Translation unit from libclang
        """
        if not CLANG_AVAILABLE:
            raise RuntimeError("libclang not available")

        self._tu = tu
        self._logger = logging.getLogger(__name__)

    def extract(self) -> List[FunctionInfo]:
        """
        Extract all function definitions from AST.
        """
        functions = []

        for cursor in self._tu.cursor.walk_preorder():
            if self._is_function_definition(cursor):
                try:
                    info = self._extract_info(cursor)
                    if info:
                        functions.append(info)
                except Exception as e:
                    logging.warning(f"Failed to extract function info at {cursor.location}: {e}")
                    import traceback
                    logging.debug(traceback.format_exc())
                    continue

        self._logger.debug(f"Extracted {len(functions)} functions")
        return functions

    def _is_function_definition(self, cursor: 'clang.cindex.Cursor') -> bool:
        """
        Check if cursor is a function definition (not just declaration).

        Args:
            cursor: libclang Cursor

        Returns:
            True if function definition, False otherwise
        """
        if not CLANG_AVAILABLE:
            return False

        # Check cursor kind
        if cursor.kind not in self.FUNCTION_KINDS:
            return False

        # Must have a body (is_definition)
        if not cursor.is_definition():
            return False

        # Must be in a source file (not system header)
        location = cursor.location
        if not location.file:
            return False

        # Skip system headers - check cursor attribute, not location
        if hasattr(cursor, 'is_in_system_header') and cursor.is_in_system_header:
            return False

        return True

    def _extract_info(self, cursor: 'clang.cindex.Cursor') -> Optional[FunctionInfo]:
        """
        Extract function information from a cursor.

        Args:
            cursor: libclang Cursor for a function definition

        Returns:
            FunctionInfo object or None
        """
        # Get path
        path = str(cursor.location.file.name)

        # Get line range
        line_range = self._get_line_range(cursor)

        # Get name
        name = cursor.spelling

        # Get qualified name
        qualified_name = self._get_qualified_name(cursor)

        # Get brief (optional)
        brief = self._get_brief(cursor)

        return FunctionInfo(
            path=path,
            line_range=line_range,
            name=name,
            qualified_name=qualified_name,
            brief=brief,
            raw_cursor=cursor
        )

    def _get_qualified_name(self, cursor: 'clang.cindex.Cursor') -> str:
        """
        Build fully qualified name including namespace/class scope.

        Args:
            cursor: libclang Cursor

        Returns:
            Qualified name string
        """
        if not CLANG_AVAILABLE:
            return "unknown"

        parts = []

        # Collect scope
        scope = self._collect_scope(cursor)
        if scope:
            parts.append(scope)

        # Add function name
        parts.append(cursor.spelling)

        # Add parameters for overloading distinction
        params = self._get_parameters(cursor)
        if params:
            parts.append(f"({params})")

        return "::".join(parts)

    def _collect_scope(self, cursor: 'clang.cindex.Cursor') -> str:
        """
        Collect namespace and class scope.

        Args:
            cursor: libclang Cursor

        Returns:
            Scope string (e.g., "ns::Class")
        """
        if not CLANG_AVAILABLE:
            return ""

        scope_parts: List[str] = []
        parent = cursor.semantic_parent

        while parent:
            if parent.kind == clang.cindex.CursorKind.NAMESPACE:
                # Add namespace
                scope_parts.insert(0, parent.spelling)
            elif parent.kind in (
                clang.cindex.CursorKind.CLASS_DECL,
                clang.cindex.CursorKind.STRUCT_DECL,
                clang.cindex.CursorKind.CLASS_TEMPLATE,
            ):
                # Add class/struct
                scope_parts.insert(0, parent.spelling)
            elif parent.kind == clang.cindex.CursorKind.TRANSLATION_UNIT:
                # Reached top level
                break

            parent = parent.semantic_parent

        return "::".join(scope_parts)

    def _get_parameters(self, cursor: 'clang.cindex.Cursor') -> str:
        """
        Get parameter types as a comma-separated string.

        Args:
            cursor: libclang Cursor

        Returns:
            Parameter types string
        """
        if not CLANG_AVAILABLE:
            return ""

        params = []
        for arg in cursor.get_arguments():
            param_type = arg.type.spelling
            params.append(param_type)
        return ", ".join(params)

    def _get_line_range(self, cursor: 'clang.cindex.Cursor') -> Tuple[int, int]:
        """
        Get start and end line numbers.

        Args:
            cursor: libclang Cursor

        Returns:
            Tuple of (start_line, end_line)
        """
        if not CLANG_AVAILABLE:
            return (0, 0)

        extent = cursor.extent
        start = extent.start.line
        end = extent.end.line
        return (start, end)

    def _get_brief(self, cursor: 'clang.cindex.Cursor') -> Optional[str]:
        """
        Extract Doxygen brief from cursor's raw comment.

        Args:
            cursor: libclang Cursor

        Returns:
            Brief text or None if not found
        """
        # Get raw comment
        raw_comment = cursor.raw_comment
        if not raw_comment:
            return None

        # Parse with DoxygenParser
        parser: DoxygenParser = DoxygenParser()
        return parser.parse(raw_comment)
