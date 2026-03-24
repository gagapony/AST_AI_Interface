"""AST parsing using libclang."""

import logging
from typing import List, Optional

try:
    import clang.cindex
    CLANG_AVAILABLE = True
except ImportError:
    CLANG_AVAILABLE = False
    logging.error("libclang Python binding not available")


class ASTParser:
    """Parse C/C++ source files using libclang."""

    def __init__(self, clang_args: List[str]):
        """
        Initialize parser with compilation flags.

        Args:
            clang_args: Original compiler flags (from compile_commands.json)
        """
        self._clang_args = list(clang_args)  # Make a copy
        self._diagnostics: List[str] = []

        # Performance optimization flags for clang
        optimization_flags = [
            '-nostdlibinc',           # Don't search system include paths
            '-nostdinc++',            # Don't search standard C++ include paths
            '-fsyntax-only',          # Only parse for syntax, don't generate code
            '-fno-error-limit',       # Don't limit error display (faster)
            '-fno-caret-diagnostics', # Don't show caret in diagnostics (faster)
        ]

        # Add optimization flags if not already present
        for flag in optimization_flags:
            if flag not in self._clang_args:
                self._clang_args.append(flag)

        logging.info("Added clang optimization flags for faster parsing")

        # Create libclang index
        if CLANG_AVAILABLE:
            self._index = clang.cindex.Index.create()
        else:
            self._index = None
            logging.error("Cannot create AST parser: libclang not available")

    def parse_file(self, file_path: str) -> Optional:
        """
        Parse a source file and return TranslationUnit.

        Args:
            file_path: Path to source file

        Returns:
            TranslationUnit if successful, None otherwise
        """
        if not CLANG_AVAILABLE:
            logging.error(f"Cannot parse {file_path}: libclang not available")
            return None

        self._diagnostics = []

        return self._parse_direct(file_path)

    def _parse_direct(self, file_path: str) -> Optional:
        """
        Parse file directly with flags.

        Args:
            file_path: Path to source file

        Returns:
            TranslationUnit if successful, None otherwise
        """
        if not CLANG_AVAILABLE:
            return None

        try:
            # Parse options - optimized for speed
            # PARSE_INCOMPLETE: Allow parsing to succeed even with errors (faster)
            # Use minimal options to reduce overhead
            parse_options = clang.cindex.TranslationUnit.PARSE_INCOMPLETE

            # Parse file
            tu = self._index.parse(
                file_path,
                args=self._clang_args,
                options=parse_options
            )

            # Check if parsing succeeded
            if not tu:
                logging.error(f"TranslationUnit is None for {file_path}")
                return None

            # Collect diagnostics
            self._collect_diagnostics(tu)

            # Check for fatal errors and output detailed diagnostics
            # Use debug level to suppress warnings in normal output
            error_diags = [diag for diag in tu.diagnostics if diag.severity >= clang.cindex.Diagnostic.Error]
            if error_diags:
                logging.debug(f"Parse errors in {file_path}:")
                for diag in error_diags:
                    logging.debug(f"  {self._format_diagnostic(diag)}")

            return tu

        except Exception as e:
            logging.error(f"Failed to parse {file_path}: {e}")
            return None

    def _collect_diagnostics(self, tu) -> None:
        """Collect diagnostic messages from translation unit."""
        if not CLANG_AVAILABLE:
            return
        for diag in tu.diagnostics:
            self._diagnostics.append(self._format_diagnostic(diag))

    def _format_diagnostic(self, diag) -> str:
        """Format diagnostic message."""
        if not CLANG_AVAILABLE:
            return f"Unknown diagnostic: {diag}"

        location = diag.location
        if location.file:
            loc_str = f"{location.file.name}:{location.line}:{location.column}"
        else:
            loc_str = "<unknown>"

        severity_name = {
            0: "Ignored",
            1: "Note",
            2: "Warning",
            3: "Error",
            4: "Fatal"
        }.get(diag.severity, "Unknown")

        return f"{severity_name}: {loc_str}: {diag.spelling}"

    def get_diagnostics(self) -> List[str]:
        """Return collected diagnostics."""
        return self._diagnostics

    def has_errors(self) -> bool:
        """Check if parsing produced errors."""
        return "Error" in " ".join(self._diagnostics) or "Fatal" in " ".join(self._diagnostics)
