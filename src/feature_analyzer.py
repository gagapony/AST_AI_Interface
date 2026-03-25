"""Feature extraction from AST (macros, function pointers, virtual functions)."""

import logging
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Set, Dict, Any, Union

try:
    import clang.cindex  # type: ignore
    CLANG_AVAILABLE = True
except ImportError:
    CLANG_AVAILABLE = False


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class MacroInfo:
    """Information about a macro definition."""
    name: str
    parameters: List[str]
    definition: str
    path: str
    line_range: Tuple[int, int]
    is_function_like: bool
    is_variadic: bool
    index: Optional[int] = None


@dataclass
class MacroInvocation:
    """Information about a macro invocation."""
    macro_name: str
    invocation_location: Tuple[str, int]
    arguments: List[str]
    caller_index: Optional[int] = None


@dataclass
class FunctionPointerType:
    """Type signature of a function pointer."""
    return_type: str
    parameter_types: List[str]
    is_variadic: bool


@dataclass
class FunctionPointerInfo:
    """Information about a function pointer variable."""
    name: str
    qualified_name: str
    type_signature: FunctionPointerType
    path: str
    line: int
    possible_targets: Set[int]
    index: Optional[int] = None


@dataclass
class ClassInfo:
    """Information about a class/struct."""
    name: str
    qualified_name: str
    path: str
    line: int
    base_classes: List[str]
    derived_classes: List[str]
    virtual_methods: Set[str]
    index: Optional[int] = None


@dataclass
class VirtualMethodInfo:
    """Information about a virtual method."""
    name: str
    qualified_name: str
    class_name: str
    is_pure_virtual: bool
    overrides: Optional[str]
    overrides_index: Optional[int]
    index: Optional[int] = None


# =============================================================================
# Unified Registry
# =============================================================================

class FeatureRegistry:
    """Unified registry for macros, function pointers, and classes."""

    def __init__(self) -> None:
        """Initialize empty registry."""
        # Macros
        self._macros: List[MacroInfo] = []
        self._macro_name_to_index: Dict[str, Optional[int]] = {}

        # Function pointers
        self._pointers: List[FunctionPointerInfo] = []
        self._pointer_name_to_index: Dict[str, Optional[int]] = {}
        self._pointer_assignments: List[Tuple[int, Optional[int], Tuple[str, int]]] = []

        # Classes
        self._classes: List[ClassInfo] = []
        self._class_name_to_index: Dict[str, Optional[int]] = {}
        self._virtual_methods: List[VirtualMethodInfo] = []
        self._virtual_method_name_to_index: Dict[str, Optional[int]] = {}

    # ========== Macro Methods ==========
    def add_macro(self, info: MacroInfo) -> int:
        """Add a macro to the registry."""
        index: int = len(self._macros)
        info.index = index
        self._macros.append(info)
        self._macro_name_to_index[info.name] = index
        logging.debug(f"Registered macro [{index}]: {info.name}")
        return index

    def get_macro_by_index(self, index: int) -> Optional[MacroInfo]:
        """Get macro by index."""
        if 0 <= index < len(self._macros):
            return self._macros[index]
        return None

    def get_macro_by_name(self, name: str) -> Optional[MacroInfo]:
        """Get macro by name."""
        index: Optional[int] = self._macro_name_to_index.get(name)
        if index is not None:
            return self._macros[index]
        return None

    # ========== Function Pointer Methods ==========
    def add_pointer(self, info: FunctionPointerInfo) -> int:
        """Add a function pointer to the registry."""
        index: int = len(self._pointers)
        info.index = index
        self._pointers.append(info)
        self._pointer_name_to_index[info.qualified_name] = index
        logging.debug(f"Registered function pointer [{index}]: {info.qualified_name}")
        return index

    def add_pointer_assignment(
        self,
        pointer_index: int,
        assigned_function_index: Optional[int],
        location: Tuple[str, int]
    ) -> None:
        """Add an assignment to the registry."""
        self._pointer_assignments.append((pointer_index, assigned_function_index, location))

        # Update possible targets
        if 0 <= pointer_index < len(self._pointers):
            if assigned_function_index is not None:
                self._pointers[pointer_index].possible_targets.add(assigned_function_index)
                logging.debug(f"Pointer '{self._pointers[pointer_index].name}' may point to function [{assigned_function_index}]")

    def get_pointer_by_index(self, index: int) -> Optional[FunctionPointerInfo]:
        """Get function pointer by index."""
        if 0 <= index < len(self._pointers):
            return self._pointers[index]
        return None

    def get_pointer_by_name(self, name: str) -> Optional[FunctionPointerInfo]:
        """Get function pointer by qualified name."""
        index: Optional[int] = self._pointer_name_to_index.get(name)
        if index is not None:
            return self._pointers[index]
        return None

    # ========== Class Methods ==========
    def add_class(self, info: ClassInfo) -> int:
        """Add a class to the registry."""
        index: int = len(self._classes)
        info.index = index
        self._classes.append(info)
        self._class_name_to_index[info.qualified_name] = index
        logging.debug(f"Registered class [{index}]: {info.qualified_name}")
        return index

    def add_virtual_method(self, info: VirtualMethodInfo) -> int:
        """Add a virtual method to the registry."""
        index: int = len(self._virtual_methods)
        info.index = index
        self._virtual_methods.append(info)
        self._virtual_method_name_to_index[info.qualified_name] = index

        # Add to class's virtual methods set
        class_info = self.get_class_by_name(info.class_name)
        if class_info:
            class_info.virtual_methods.add(info.qualified_name)

        logging.debug(f"Registered virtual method [{index}]: {info.qualified_name}")
        return index

    def get_class_by_index(self, index: int) -> Optional[ClassInfo]:
        """Get class by index."""
        if 0 <= index < len(self._classes):
            return self._classes[index]
        return None

    def get_class_by_name(self, name: str) -> Optional[ClassInfo]:
        """Get class by qualified name."""
        index: Optional[int] = self._class_name_to_index.get(name)
        if index is not None:
            return self._classes[index]
        return None

    def build_derived_relationships(self) -> None:
        """Build derived class relationships from base class information."""
        # Clear existing derived lists
        for cls in self._classes:
            cls.derived_classes = []

        # Build relationships
        for cls in self._classes:
            for base_name in cls.base_classes:
                base = self.get_class_by_name(base_name)
                if base:
                    base.derived_classes.append(cls.qualified_name)

    def get_all_derived(self, class_name: str) -> List[str]:
        """Get all classes derived from the given class (transitive)."""
        result: Set[str] = set()
        queue: List[str] = [class_name]

        while queue:
            current = queue.pop(0)
            cls = self.get_class_by_name(current)
            if not cls:
                continue

            for derived in cls.derived_classes:
                if derived not in result:
                    result.add(derived)
                    queue.append(derived)

        return list(result)


# =============================================================================
# Feature Analyzer
# =============================================================================

class FeatureAnalyzer:
    """Extract macro, function pointer, and virtual function information from AST."""

    if CLANG_AVAILABLE:
        # Cursor kinds
        MACRO_DEF_KIND = clang.cindex.CursorKind.MACRO_DEFINITION
        MACRO_INSTANTIATION_KIND = clang.cindex.CursorKind.MACRO_INSTANTIATION
        VAR_DECL_KIND = clang.cindex.CursorKind.VAR_DECL
        FIELD_DECL_KIND = clang.cindex.CursorKind.FIELD_DECL
        PARM_DECL_KIND = clang.cindex.CursorKind.PARM_DECL
        METHOD_KIND = clang.cindex.CursorKind.CXX_METHOD
        BASE_SPECIFIER_KIND = clang.cindex.CursorKind.CXX_BASE_SPECIFIER

    def __init__(self, tu: 'clang.cindex.TranslationUnit', function_registry: Any) -> None:
        """
        Initialize analyzer with translation unit and function registry.

        Args:
            tu: Translation unit from libclang
            function_registry: FunctionRegistry for resolving function names
        """
        if not CLANG_AVAILABLE:
            raise RuntimeError("libclang not available")

        self._tu: 'clang.cindex.TranslationUnit' = tu
        self._function_registry: Any = function_registry
        self._logger = logging.getLogger(__name__)
        self._registry: FeatureRegistry = FeatureRegistry()

    @property
    def registry(self) -> FeatureRegistry:
        """Get the feature registry."""
        return self._registry

    # ========== Macro Extraction ==========
    def extract_macros(self) -> List[MacroInfo]:
        """
        Extract all macro definitions from AST.

        Returns:
            List of MacroInfo objects
        """
        macros: List[MacroInfo] = []
        cursor_count = 0
        macro_def_count = 0

        # Get top-level declarations (macros are at translation unit level)
        for cursor in self._tu.cursor.get_children():
            cursor_count += 1
            logging.debug(f"Top-level cursor {cursor_count}: kind={cursor.kind}, spelling='{cursor.spelling}'")
            if self._is_macro_definition(cursor):
                macro_def_count += 1
                logging.debug(f"Found macro definition cursor: {cursor.spelling}, kind: {cursor.kind}")
                try:
                    info = self._extract_macro_definition(cursor)
                    if info and info.is_function_like:
                        macros.append(info)
                        self._registry.add_macro(info)
                    elif info:
                        logging.debug(f"Macro '{cursor.spelling}' is not function-like (has {len(info.parameters)} parameters)")
                except Exception as e:
                    logging.warning(f"Failed to extract macro {cursor.spelling}: {e}")
                    continue

        logging.debug(f"Processed {cursor_count} top-level cursors, found {macro_def_count} macro definitions, extracted {len(macros)} function-like macros")

        self._logger.debug(f"Extracted {len(macros)} function-like macros")
        return macros

    def extract_macro_invocations(self, function_cursor: 'clang.cindex.Cursor') -> List[MacroInvocation]:
        """
        Extract macro invocations within a function.

        Args:
            function_cursor: libclang Cursor for a function

        Returns:
            List of MacroInvocation objects
        """
        invocations: List[MacroInvocation] = []

        # Walk function body to find macro instantiations
        for cursor in function_cursor.walk_preorder():
            if cursor.kind == self.MACRO_INSTANTIATION_KIND:
                try:
                    invocation = self._extract_macro_invocation(cursor)
                    if invocation:
                        invocations.append(invocation)
                except Exception as e:
                    logging.debug(f"Failed to extract macro invocation: {e}")
                    continue

        return invocations

    def _is_macro_definition(self, cursor: 'clang.cindex.Cursor') -> bool:
        """Check if cursor is a macro definition."""
        if not CLANG_AVAILABLE:
            return False

        if cursor.kind != self.MACRO_DEF_KIND:
            return False

        # Check location safely
        location = cursor.location
        if not location or not location.file:
            return False

        # Skip system headers
        if hasattr(cursor, 'is_in_system_header') and cursor.is_in_system_header:
            return False

        return True

    def _extract_macro_definition(self, cursor: 'clang.cindex.Cursor') -> Optional[MacroInfo]:
        """
        Extract macro information from a cursor.

        Args:
            cursor: libclang Cursor for MACRO_DEFINITION

        Returns:
            MacroInfo object or None
        """
        # Get name
        name: str = cursor.spelling
        if not name:
            return None

        # Get path (with error handling)
        path: str = ""
        location = cursor.location
        if location and location.file:
            path = str(location.file.name)

        # Get line range
        line_range: Tuple[int, int] = self._safe_get_line_range(cursor)

        # Get parameters and type info (libclang only, NO regex)
        parameters: List[str] = []
        is_function_like: bool = False
        is_variadic: bool = False

        try:
            tokens: List['clang.cindex.Token'] = list(cursor.get_tokens())
            if tokens:
                # Find opening parenthesis after macro name
                param_start: int = -1
                for i, token in enumerate(tokens):
                    if i == 0:
                        continue  # Skip macro name
                    if token.spelling == '(':
                        param_start = i
                        is_function_like = True
                        break

                # Extract parameters
                if is_function_like and param_start > 0:
                    param_tokens: List[str] = []
                    i = param_start + 1
                    while i < len(tokens):
                        current_token = tokens[i]
                        if current_token.spelling == ')':
                            break
                        if current_token.spelling == '...':
                            is_variadic = True
                        elif current_token.spelling not in (',', ' ', '\t', '\n'):
                            param_tokens.append(current_token.spelling)
                        i += 1
                    parameters = param_tokens

            # Get full definition
            definition: str = self._safe_get_definition_text(tokens)

        except Exception as e:
            logging.warning(f"Failed to parse macro tokens for {name}: {e}")
            definition = ""

        return MacroInfo(
            name=name,
            parameters=parameters,
            definition=definition,
            path=path,
            line_range=line_range,
            is_function_like=is_function_like,
            is_variadic=is_variadic
        )

    def _extract_macro_invocation(self, cursor: 'clang.cindex.Cursor') -> Optional[MacroInvocation]:
        """
        Extract macro invocation information.

        Args:
            cursor: libclang Cursor for MACRO_INSTANTIATION

        Returns:
            MacroInvocation object or None
        """
        macro_name: str = cursor.spelling
        if not macro_name:
            return None

        # Get location (with error handling)
        path: str = ""
        line: int = 0
        location = cursor.location
        if location:
            if location.file:
                path = str(location.file.name)
            line = location.line

        # Extract arguments
        arguments: List[str] = []
        try:
            tokens: List['clang.cindex.Token'] = list(cursor.get_tokens())

            # Find opening parenthesis
            paren_start: int = -1
            for i, token in enumerate(tokens):
                if token.spelling == '(':
                    paren_start = i
                    break

            # Extract arguments
            if paren_start >= 0:
                arg_text: str = ""
                paren_depth: int = 0
                for i in range(paren_start + 1, len(tokens)):
                    current_token = tokens[i]
                    if current_token.spelling == '(':
                        paren_depth += 1
                        arg_text += current_token.spelling
                    elif current_token.spelling == ')':
                        if paren_depth == 0:
                            break
                        paren_depth -= 1
                        arg_text += current_token.spelling
                    elif current_token.spelling == ',' and paren_depth == 0:
                        arguments.append(arg_text.strip())
                        arg_text = ""
                    else:
                        arg_text += current_token.spelling

                if arg_text.strip():
                    arguments.append(arg_text.strip())

        except Exception as e:
            logging.debug(f"Failed to extract macro invocation arguments: {e}")

        return MacroInvocation(
            macro_name=macro_name,
            invocation_location=(path, line),
            arguments=arguments
        )

    def _safe_get_line_range(self, cursor: 'clang.cindex.Cursor') -> Tuple[int, int]:
        """
        Safely get start and end line numbers.

        Args:
            cursor: libclang Cursor

        Returns:
            Tuple of (start_line, end_line)
        """
        if not CLANG_AVAILABLE:
            return (0, 0)

        try:
            extent = cursor.extent
            start: int = extent.start.line
            end: int = extent.end.line
            return (start, end)
        except Exception as e:
            logging.debug(f"Failed to get line range: {e}")
            return (0, 0)

    def _safe_get_definition_text(self, tokens: List['clang.cindex.Token']) -> str:
        """
        Safely get full macro definition text.

        Args:
            tokens: List of tokens

        Returns:
            Definition text
        """
        if not tokens:
            return ""

        parts: List[str] = []
        for token in tokens:
            parts.append(token.spelling)
        return " ".join(parts)

    # ========== Function Pointer Extraction ==========
    def extract_function_pointers(self) -> List[FunctionPointerInfo]:
        """
        Extract all function pointer declarations.

        Returns:
            List of FunctionPointerInfo objects
        """
        pointers: List[FunctionPointerInfo] = []

        for cursor in self._tu.cursor.walk_preorder():
            if self._is_function_pointer_decl(cursor):
                try:
                    info = self._extract_pointer_info(cursor)
                    if info:
                        pointers.append(info)
                        self._registry.add_pointer(info)
                except Exception as e:
                    logging.debug(f"Failed to extract function pointer at {cursor.location}: {e}")
                    continue

        self._logger.debug(f"Extracted {len(pointers)} function pointer declarations")
        return pointers

    def _is_function_pointer_decl(self, cursor: 'clang.cindex.Cursor') -> bool:
        """
        Check if cursor is a function pointer declaration.

        Args:
            cursor: libclang Cursor

        Returns:
            True if function pointer declaration, False otherwise
        """
        if not CLANG_AVAILABLE:
            return False

        # Check cursor kind
        if cursor.kind not in (self.VAR_DECL_KIND, self.FIELD_DECL_KIND, self.PARM_DECL_KIND):
            return False

        # Check type: pointer to function (with error handling)
        try:
            cursor_type = cursor.type
            if cursor_type.kind != clang.cindex.TypeKind.POINTER:
                return False

            # Check pointee type: function prototype (with error handling)
            pointee_type = cursor_type.get_pointee()
            if pointee_type.kind != clang.cindex.TypeKind.FUNCTIONPROTO:
                return False

        except Exception as e:
            logging.debug(f"Failed to check function pointer type: {e}")
            return False

        # Check location
        location = cursor.location
        if not location or not location.file:
            return False

        # Skip system headers
        if hasattr(cursor, 'is_in_system_header') and cursor.is_in_system_header:
            return False

        return True

    def _extract_pointer_info(self, cursor: 'clang.cindex.Cursor') -> Optional[FunctionPointerInfo]:
        """
        Extract function pointer information.

        Args:
            cursor: libclang Cursor for function pointer declaration

        Returns:
            FunctionPointerInfo object or None
        """
        # Get name
        name: str = cursor.spelling
        if not name:
            return None

        # Get qualified name
        qualified_name: str = self._safe_get_qualified_name(cursor)

        # Get location
        path: str = ""
        line: int = 0
        location = cursor.location
        if location:
            if location.file:
                path = str(location.file.name)
            line = location.line

        # Extract type signature (with error handling)
        type_signature: Optional[FunctionPointerType] = self._safe_extract_type_signature(cursor)
        if not type_signature:
            return None

        return FunctionPointerInfo(
            name=name,
            qualified_name=qualified_name,
            type_signature=type_signature,
            path=path,
            line=line,
            possible_targets=set()
        )

    def _safe_extract_type_signature(self, cursor: 'clang.cindex.Cursor') -> Optional[FunctionPointerType]:
        """
        Safely extract type signature from function pointer cursor.

        Args:
            cursor: libclang Cursor

        Returns:
            FunctionPointerType object or None
        """
        try:
            cursor_type = cursor.type
            pointee_type = cursor_type.get_pointee()

            # Get return type
            return_type: str = pointee_type.get_result().spelling

            # Get parameter types
            parameter_types: List[str] = []
            for arg in pointee_type.get_arguments():
                parameter_types.append(arg.type.spelling)

            # Check if variadic
            is_variadic: bool = pointee_type.is_function_variadic()

            return FunctionPointerType(
                return_type=return_type,
                parameter_types=parameter_types,
                is_variadic=is_variadic
            )

        except Exception as e:
            logging.debug(f"Failed to extract type signature: {e}")
            return None

    def _safe_get_qualified_name(self, cursor: 'clang.cindex.Cursor') -> str:
        """
        Safely build qualified name from cursor.

        Args:
            cursor: libclang Cursor

        Returns:
            Qualified name string
        """
        if not CLANG_AVAILABLE:
            return cursor.spelling  # type: ignore[no-any-return]

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

    # ========== Virtual Function Extraction ==========
    def extract_classes(self) -> List[ClassInfo]:
        """
        Extract all class/struct definitions.

        Returns:
            List of ClassInfo objects
        """
        classes: List[ClassInfo] = []

        for cursor in self._tu.cursor.walk_preorder():
            if self._is_class_decl(cursor):
                try:
                    info = self._extract_class_info(cursor)
                    if info:
                        classes.append(info)
                        self._registry.add_class(info)
                except Exception as e:
                    logging.debug(f"Failed to extract class {cursor.spelling}: {e}")
                    continue

        # Build derived relationships
        self._registry.build_derived_relationships()

        self._logger.debug(f"Extracted {len(classes)} classes")
        return classes

    def extract_virtual_methods(self) -> List[VirtualMethodInfo]:
        """
        Extract all virtual method definitions.

        Returns:
            List of VirtualMethodInfo objects
        """
        methods: List[VirtualMethodInfo] = []

        for cursor in self._tu.cursor.walk_preorder():
            if self._is_virtual_method(cursor):
                try:
                    info = self._extract_virtual_method_info(cursor)
                    if info:
                        methods.append(info)
                        self._registry.add_virtual_method(info)
                except Exception as e:
                    logging.debug(f"Failed to extract virtual method {cursor.spelling}: {e}")
                    continue

        self._logger.debug(f"Extracted {len(methods)} virtual methods")
        return methods

    def _is_class_decl(self, cursor: 'clang.cindex.Cursor') -> bool:
        """Check if cursor is a class/struct declaration."""
        if not CLANG_AVAILABLE:
            return False

        CLASS_KINDS = {
            clang.cindex.CursorKind.CLASS_DECL,
            clang.cindex.CursorKind.STRUCT_DECL,
            clang.cindex.CursorKind.CLASS_TEMPLATE,
        }

        if cursor.kind not in CLASS_KINDS:
            return False

        # Must be a definition
        if not cursor.is_definition():
            return False

        # Check location
        location = cursor.location
        if not location or not location.file:
            return False

        # Skip system headers
        if hasattr(cursor, 'is_in_system_header') and cursor.is_in_system_header:
            return False

        return True

    def _is_virtual_method(self, cursor: 'clang.cindex.Cursor') -> bool:
        """Check if cursor is a virtual method."""
        if not CLANG_AVAILABLE:
            return False

        if cursor.kind != self.METHOD_KIND:
            return False

        try:
            return cursor.is_virtual_method()  # type: ignore[no-any-return]
        except Exception:
            return False

    def _extract_class_info(self, cursor: 'clang.cindex.Cursor') -> Optional[ClassInfo]:
        """Extract class information."""
        # Get name
        name: str = cursor.spelling
        if not name:
            return None

        # Get qualified name
        qualified_name: str = self._safe_get_qualified_name(cursor)

        # Get location
        path: str = ""
        line: int = 0
        location = cursor.location
        if location:
            if location.file:
                path = str(location.file.name)
            line = location.line

        # Extract base classes (with error handling)
        base_classes: List[str] = []
        try:
            for child in cursor.get_children():
                if child.kind == self.BASE_SPECIFIER_KIND:
                    try:
                        base_class = child.type.get_declaration()
                        if base_class:
                            base_qualified_name = self._safe_get_qualified_name(base_class)
                            base_classes.append(base_qualified_name)
                    except Exception as e:
                        logging.debug(f"Failed to get base class: {e}")
                        continue
        except Exception as e:
            logging.debug(f"Failed to extract base classes: {e}")

        return ClassInfo(
            name=name,
            qualified_name=qualified_name,
            path=path,
            line=line,
            base_classes=base_classes,
            derived_classes=[],
            virtual_methods=set()
        )

    def _extract_virtual_method_info(self, cursor: 'clang.cindex.Cursor') -> Optional[VirtualMethodInfo]:
        """Extract virtual method information."""
        # Get name
        name: str = cursor.spelling
        if not name:
            return None

        # Get qualified name
        qualified_name: str = self._safe_get_qualified_name(cursor)

        # Get class name
        class_name: Optional[str] = self._safe_get_method_class(cursor)
        if not class_name:
            return None

        # Check if pure virtual (with error handling)
        is_pure_virtual: bool = False
        try:
            is_pure_virtual = cursor.is_pure_virtual_method()
        except Exception:
            pass

        # Check if this is an override (look in base classes)
        overrides: Optional[str] = self._find_overridden_method(cursor, class_name)

        return VirtualMethodInfo(
            name=name,
            qualified_name=qualified_name,
            class_name=class_name,
            is_pure_virtual=is_pure_virtual,
            overrides=overrides,
            overrides_index=None
        )

    def _safe_get_method_class(self, cursor: 'clang.cindex.Cursor') -> Optional[str]:
        """Get the qualified name of the method's class."""
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

    def _find_overridden_method(self, cursor: 'clang.cindex.Cursor', class_name: str) -> Optional[str]:
        """Find the base method this overrides."""
        # Get class info
        class_info = self._registry.get_class_by_name(class_name)
        if not class_info:
            return None

        # For each base class, check if it has a method with the same name
        for base_name in class_info.base_classes:
            base_class = self._registry.get_class_by_name(base_name)
            if not base_class:
                continue

            # Look for method with same name in base class
            base_method_name = f"{base_name}::{cursor.spelling}"
            indices = self._function_registry.get_by_qualified_name(base_method_name)
            if indices:
                return base_method_name

        return None
