"""AST parsing using libclang with adaptive flag filtering."""

import logging
from pathlib import Path
from typing import List, Optional

try:
    import clang.cindex
except ImportError:
    clang = None

from .flag_filter_manager import FlagFilterManager, ParseResult


class ASTParser:
    """Parse C/C++ source files using libclang with adaptive flag filtering."""

    def __init__(self,
                 clang_args: List[str],
                 flag_filter_manager: Optional[FlagFilterManager] = None):
        """
        Initialize parser with compilation flags and optional filter manager.

        Args:
            clang_args: Original compiler flags (from compile_commands.json)
            flag_filter_manager: Optional FlagFilterManager for adaptive parsing
        """
        self._clang_args = clang_args
        self._flag_filter_manager = flag_filter_manager
        self._diagnostics: List[str] = []
        self._last_parse_result: Optional[ParseResult] = None

        # Create libclang index
        self._index = clang.cindex.Index.create()

    def parse_file(self, file_path: str) -> Optional[clang.cindex.TranslationUnit]:
        """
        Parse a source file and return TranslationUnit.

        Uses adaptive flag filtering if FlagFilterManager is configured.

        Args:
            file_path: Path to source file

        Returns:
            TranslationUnit if successful, None otherwise
        """
        self._diagnostics = []

        if self._flag_filter_manager:
            # Use adaptive parsing with retry
            result = self._flag_filter_manager.parse_file(
                file_path,
                self._clang_args,
                self._index
            )
            self._last_parse_result = result

            if result.success:
                self._collect_diagnostics(result.translation_unit)
                if result.degraded_mode:
                    logging.warning(f"Parsed {file_path} in degraded mode "
                                  f"(attempt {result.attempt.attempt_number})")
                return result.translation_unit
            else:
                logging.error(f"Failed to parse {file_path} after all attempts")
                return None
        else:
            # Original behavior: parse directly with flags
            return self._parse_direct(file_path)

    def _parse_direct(self, file_path: str) -> Optional[clang.cindex.TranslationUnit]:
        """
        Parse file directly without adaptive retry (original behavior).

        Args:
            file_path: Path to source file

        Returns:
            TranslationUnit if successful, None otherwise
        """
        try:
            # Parse options
            parse_options = (
                clang.cindex.TranslationUnit.PARSE_DETAILED_PROCESSING_RECORD |
                clang.cindex.TranslationUnit.PARSE_INCOMPLETE
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
            self._collect_diagnostics(tu)

            # Check for fatal errors
            if any(diag.severity >= clang.cindex.Diagnostic.Error for diag in tu.diagnostics):
                logging.warning(f"Parse errors in {file_path}")

            return tu

        except Exception as e:
            logging.error(f"Failed to parse {file_path}: {e}")
            return None

    def _collect_diagnostics(self, tu: clang.cindex.TranslationUnit):
        """Collect diagnostic messages from translation unit."""
        for diag in tu.diagnostics:
            self._diagnostics.append(self._format_diagnostic(diag))

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

    def get_last_parse_result(self) -> Optional[ParseResult]:
        """Get the last parse result (from adaptive parsing)."""
        return self._last_parse_result
