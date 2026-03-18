"""AST parsing using libclang."""

import logging
from pathlib import Path
from typing import List, Optional

import clang.cindex


class ASTParser:
    """Parse C/C++ source files using libclang."""

    def __init__(self, clang_args: List[str]):
        """Initialize parser with compilation flags."""
        self._clang_args = clang_args
        self._diagnostics: List[str] = []

        # Create libclang index
        self._index = clang.cindex.Index.create()

    def parse_file(self, file_path: str) -> Optional[clang.cindex.TranslationUnit]:
        """Parse a source file and return TranslationUnit."""
        self._diagnostics = []

        try:
            # Parse options suitable for incomplete code (Arduino projects)
            parse_options = (
                clang.cindex.TranslationUnit.PARSE_DETAILED_PROCESSING_RECORD |
                clang.cindex.TranslationUnit.PARSE_INCOMPLETE |
                clang.cindex.TranslationUnit.PARSE_SKIP_FUNCTION_BODIES
            )

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
            for diag in tu.diagnostics:
                self._diagnostics.append(self._format_diagnostic(diag))

            # Check for fatal errors
            if any(diag.severity >= clang.cindex.Diagnostic.Error for diag in tu.diagnostics):
                logging.warning(f"Parse errors in {file_path}")

            return tu

        except Exception as e:
            logging.error(f"Failed to parse {file_path}: {e}")
            return None

    def _format_diagnostic(self, diag: clang.cindex.Diagnostic) -> str:
        """Format diagnostic message."""
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
