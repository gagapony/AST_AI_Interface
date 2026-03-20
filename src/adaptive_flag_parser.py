"""Adaptive flag parsing with retry mechanism."""

import logging
import re
from dataclasses import dataclass
from typing import List, Optional, Set

try:
    import clang.cindex
except ImportError:
    clang = None

from .flag_whitelist import FlagWhitelist


@dataclass
class ParseAttempt:
    """Represents a single parsing attempt."""
    attempt_number: int
    flags_used: List[str]
    success: bool
    error_message: Optional[str] = None
    functions_extracted: int = 0
    translation_unit: Optional['clang.cindex.TranslationUnit'] = None  # type: ignore


@dataclass
class ParseResult:
    """Final result of adaptive parsing."""
    success: bool
    translation_unit: Optional['clang.cindex.TranslationUnit']  # type: ignore
    attempt: ParseAttempt  # The successful attempt
    all_attempts: List[ParseAttempt]
    problematic_flags: Set[str]  # Flags that caused failures
    degraded_mode: bool  # True if final attempt was minimal/no flags


class AdaptiveFlagParser:
    """
    Parser with adaptive retry strategy for flag compatibility.

    Strategy:
    - Pass 1: Try all whitelisted flags
    - Pass 2: Try minimal flags (include paths + macros only)
    - Pass 3: Try no flags (just the file)
    - Pass 4: Return graceful degradation if all fail
    """

    def __init__(self,
                 whitelist: FlagWhitelist,
                 max_retries: int = 3,
                 logger: Optional[logging.Logger] = None):
        """
        Initialize adaptive parser.

        Args:
            whitelist: FlagWhitelist instance
            max_retries: Maximum retry attempts (default: 3)
            logger: Optional logger for diagnostics
        """
        self.whitelist = whitelist
        self.max_retries = max_retries
        self.logger = logger or logging.getLogger(__name__)
        self.flag_failure_history: dict[str, int] = {}  # flag -> failure count

    def parse_with_retry(self,
                         file_path: str,
                         original_flags: List[str],
                         libclang_index: 'clang.cindex.Index') -> ParseResult:
        """
        Parse file with adaptive retry strategy.

        Args:
            file_path: Path to source file
            original_flags: Original compiler flags
            libclang_index: libclang Index instance

        Returns:
            ParseResult with outcome and diagnostic information
        """
        attempts = []
        problematic_flags = set()

        self.logger.info(f"Parsing {file_path} with adaptive retry strategy")

        # Attempt 1: Whitelisted flags
        whitelisted_flags = self.whitelist.filter_flags(original_flags)
        self.logger.debug(f"Attempt 1: {len(whitelisted_flags)} whitelisted flags")

        attempt1 = self._try_parse(file_path, whitelisted_flags,
                                   libclang_index, attempt_number=1)
        attempts.append(attempt1)

        if attempt1.success:
            self.logger.debug(f"Parse succeeded on attempt 1 with {len(whitelisted_flags)} flags")
            return ParseResult(
                success=True,
                translation_unit=attempt1.translation_unit,
                attempt=attempt1,
                all_attempts=attempts,
                problematic_flags=problematic_flags,
                degraded_mode=False
            )

        # Identify problematic flags (if error message indicates specific flag)
        self._identify_problematic_flags(attempt1.error_message, whitelisted_flags,
                                       problematic_flags)

        # Attempt 2: Minimal flags (include paths + macros only)
        minimal_flags = self.whitelist.get_minimal_flags(original_flags)
        self.logger.debug(f"Attempt 2: {len(minimal_flags)} minimal flags (include paths + macros)")

        attempt2 = self._try_parse(file_path, minimal_flags,
                                   libclang_index, attempt_number=2)
        attempts.append(attempt2)

        if attempt2.success:
            self.logger.info(f"Parse succeeded on attempt 2 (minimal flags) after "
                           f"attempt 1 failed: {attempt1.error_message}")
            return ParseResult(
                success=True,
                translation_unit=attempt2.translation_unit,
                attempt=attempt2,
                all_attempts=attempts,
                problematic_flags=problematic_flags,
                degraded_mode=True
            )

        # Identify more problematic flags from attempt 2
        self._identify_problematic_flags(attempt2.error_message, minimal_flags,
                                       problematic_flags)

        # Attempt 3: No flags (just the file)
        self.logger.debug("Attempt 3: No flags")
        attempt3 = self._try_parse(file_path, [],
                                   libclang_index, attempt_number=3)
        attempts.append(attempt3)

        if attempt3.success:
            self.logger.warning(f"Parse succeeded on attempt 3 (no flags) after "
                              f"attempts 1 and 2 failed")
            return ParseResult(
                success=True,
                translation_unit=attempt3.translation_unit,
                attempt=attempt3,
                all_attempts=attempts,
                problematic_flags=problematic_flags,
                degraded_mode=True
            )

        # All attempts failed
        self.logger.error(f"Parse failed for {file_path} after {len(attempts)} attempts")
        for i, attempt in enumerate(attempts, 1):
            self.logger.error(f"  Attempt {i}: Failed - {attempt.error_message}")

        return ParseResult(
            success=False,
            translation_unit=None,
            attempt=attempt3,  # Last attempt
            all_attempts=attempts,
            problematic_flags=problematic_flags,
            degraded_mode=True
        )

        # All attempts failed
        self.logger.error(f"Parse failed for {file_path} after {len(attempts)} attempts")
        for i, attempt in enumerate(attempts, 1):
            self.logger.error(f"  Attempt {i}: Failed - {attempt.error_message}")

        return ParseResult(
            success=False,
            translation_unit=None,
            attempt=attempt3,  # Last attempt
            all_attempts=attempts,
            problematic_flags=problematic_flags,
            degraded_mode=True
        )

    def _try_parse(self,
                   file_path: str,
                   flags: List[str],
                   libclang_index: 'clang.cindex.Index',
                   attempt_number: int) -> ParseAttempt:
        """
        Attempt to parse a file with given flags.

        Args:
            file_path: Path to source file
            flags: Flags to use for parsing
            libclang_index: libclang Index instance
            attempt_number: Attempt number for logging

        Returns:
            ParseAttempt with result
        """
        try:
            self.logger.debug(f"  Attempt {attempt_number}: Parsing with {len(flags)} flags")
            if flags:
                self.logger.debug(f"  Attempt {attempt_number} flags: {' '.join(flags)}")

            # Parse options suitable for parsing
            parse_options = (
                clang.cindex.TranslationUnit.PARSE_DETAILED_PROCESSING_RECORD |
                clang.cindex.TranslationUnit.PARSE_INCOMPLETE
            )

            tu = libclang_index.parse(
                file_path,
                args=flags,
                options=parse_options
            )

            # Check for fatal diagnostics
            fatal_diags = []
            for diag in tu.diagnostics:
                if diag.severity >= clang.cindex.Diagnostic.Error:
                    self.logger.warning(f"  Diagnostic (attempt {attempt_number}): {diag.spelling}")
                    fatal_diags.append(diag.spelling)

            # Count extracted functions
            function_count = self._count_functions(tu)

            self.logger.debug(f"  Attempt {attempt_number}: Success ({function_count} functions)")

            return ParseAttempt(
                attempt_number=attempt_number,
                flags_used=flags.copy(),
                success=True,
                error_message=None,
                functions_extracted=function_count,
                translation_unit=tu
            )

        except Exception as e:
            error_msg = str(e)
            self.logger.debug(f"  Attempt {attempt_number}: Failed - {error_msg}")

            return ParseAttempt(
                attempt_number=attempt_number,
                flags_used=flags.copy(),
                success=False,
                error_message=error_msg,
                functions_extracted=0
            )

    def _count_functions(self, translation_unit: 'clang.cindex.TranslationUnit') -> int:
        """Count function definitions in translation unit."""
        count = 0
        for cursor in translation_unit.cursor.walk_preorder():
            if cursor.kind.is_declaration():
                if cursor.location.file:
                    count += 1
        return count

    def _identify_problematic_flags(self,
                                   error_message: Optional[str],
                                   flags: List[str],
                                   problematic_set: set):
        """
        Attempt to identify which flag caused the parse failure.

        This is heuristic-based; libclang doesn't always indicate specific flags.

        Args:
            error_message: Error message from libclang
            flags: Flags used in the failed attempt
            problematic_set: Set to populate with identified problematic flags
        """
        if not error_message:
            return

        # Try to extract flag from error message
        flag = self._extract_flag_from_error(error_message)
        if flag and flag in flags:
            problematic_set.add(flag)
            self.flag_failure_history[flag] = self.flag_failure_history.get(flag, 0) + 1
            self.logger.debug(f"  Identified problematic flag: {flag}")

    def _extract_flag_from_error(self, error_message: str) -> Optional[str]:
        """
        Extract flag name from error message.

        Examples:
            "unknown argument '-march=rv32imc'" -> "-march=rv32imc"
            "unrecognized option '-fno-rtti'" -> "-fno-rtti"
        """
        # Try to match quoted flag
        match = re.search(r"['\"](-[\w=-]+)['\"]", error_message)
        if match:
            return match.group(1)

        # Try to match flag pattern
        match = re.search(r"(-[\w=-]+)", error_message)
        if match:
            return match.group(1)

        return None

    def get_flag_failure_history(self) -> dict[str, int]:
        """Get history of flag failures (for analysis/optimization)."""
        return self.flag_failure_history.copy()
