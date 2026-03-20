"""Flag filter manager coordinating whitelist and adaptive parsing."""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

from .flag_whitelist import FlagWhitelist
from .adaptive_flag_parser import AdaptiveFlagParser, ParseResult


@dataclass
class FilterStats:
    """Statistics about flag filtering."""
    files_processed: int = 0
    files_succeeded_full: int = 0
    files_succeeded_minimal: int = 0
    files_succeeded_no_flags: int = 0
    files_failed: int = 0
    total_flags_filtered: int = 0
    problematic_flags: Set[str] = field(default_factory=set)


class FlagFilterManager:
    """
    Manages flag filtering and adaptive parsing.

    Usage:
        manager = FlagFilterManager.from_config(config)
        result = manager.parse_file(file_path, flags, libclang_index)
    """

    def __init__(self,
                 whitelist: FlagWhitelist,
                 max_retries: int = 3,
                 enable_retry: bool = True,
                 logger: Optional[logging.Logger] = None):
        """
        Initialize filter manager.

        Args:
            whitelist: FlagWhitelist instance
            max_retries: Maximum retry attempts
            enable_retry: Enable adaptive retry strategy
            logger: Optional logger
        """
        self.whitelist = whitelist
        self.max_retries = max_retries
        self.enable_retry = enable_retry
        self.logger = logger or logging.getLogger(__name__)
        self.parser = AdaptiveFlagParser(whitelist, max_retries, logger)
        self.stats = FilterStats()

    @classmethod
    def from_config(cls,
                   config: Dict,
                   logger: Optional[logging.Logger] = None) -> 'FlagFilterManager':
        """
        Create manager from configuration dictionary.

        Args:
            config: Configuration dictionary (from YAML)
            logger: Optional logger

        Returns:
            FlagFilterManager instance
        """
        flag_filter_config = config.get('flag_filter', {})

        # Get custom whitelist
        custom_whitelist = flag_filter_config.get('custom_whitelist', {})

        # Create whitelist
        whitelist = FlagWhitelist(custom_whitelist=custom_whitelist)

        # Get retry settings
        max_retries = flag_filter_config.get('max_retries', 3)
        enable_retry = flag_filter_config.get('enable_retry', True)

        logger.info(f"FlagFilterManager initialized: retry={enable_retry}, "
                   f"max_retries={max_retries}")

        return cls(
            whitelist=whitelist,
            max_retries=max_retries,
            enable_retry=enable_retry,
            logger=logger
        )

    def parse_file(self,
                   file_path: str,
                   original_flags: List[str],
                   libclang_index: 'object') -> ParseResult:
        """
        Parse file with adaptive flag filtering.

        Args:
            file_path: Path to source file
            original_flags: Original compiler flags
            libclang_index: libclang Index instance

        Returns:
            ParseResult with outcome
        """
        self.stats.files_processed += 1

        # Track how many flags were filtered
        whitelisted_flags = self.whitelist.filter_flags(original_flags)
        filtered_count = len(original_flags) - len(whitelisted_flags)
        self.stats.total_flags_filtered += filtered_count

        # Log if flags were filtered
        if filtered_count > 0:
            self.logger.debug(f"Filtered {filtered_count} flags for {file_path} "
                            f"(kept {len(whitelisted_flags)} of {len(original_flags)})")

        # Parse with retry strategy
        if self.enable_retry:
            result = self.parser.parse_with_retry(file_path, original_flags,
                                                 libclang_index)
        else:
            # Single attempt: try whitelisted flags only
            result = self._single_attempt_parse(file_path, original_flags,
                                               libclang_index)

        # Update statistics
        self._update_stats(result)

        return result

    def _single_attempt_parse(self,
                              file_path: str,
                              original_flags: List[str],
                              libclang_index: 'object') -> ParseResult:
        """
        Parse file with single attempt (no retry).

        Used when adaptive retry is disabled.
        """
        from adaptive_flag_parser import ParseAttempt

        whitelisted_flags = self.whitelist.filter_flags(original_flags)

        try:
            import clang.cindex

            # Parse options
            parse_options = (
                clang.cindex.TranslationUnit.PARSE_DETAILED_PROCESSING_RECORD |
                clang.cindex.TranslationUnit.PARSE_INCOMPLETE
            )

            tu = libclang_index.parse(
                file_path,
                args=whitelisted_flags,
                options=parse_options
            )

            # Count functions
            function_count = 0
            for cursor in tu.cursor.walk_preorder():
                if cursor.kind.is_declaration():
                    if cursor.location.file:
                        function_count += 1

            attempt = ParseAttempt(
                attempt_number=1,
                flags_used=whitelisted_flags,
                success=True,
                error_message=None,
                functions_extracted=function_count,
                translation_unit=tu
            )

            self.stats.files_succeeded_full += 1

            return ParseResult(
                success=True,
                translation_unit=tu,
                attempt=attempt,
                all_attempts=[attempt],
                problematic_flags=set(),
                degraded_mode=False
            )

        except Exception as e:
            attempt = ParseAttempt(
                attempt_number=1,
                flags_used=whitelisted_flags,
                success=False,
                error_message=str(e),
                functions_extracted=0
            )

            self.stats.files_failed += 1

            return ParseResult(
                success=False,
                translation_unit=None,
                attempt=attempt,
                all_attempts=[attempt],
                problematic_flags=set(),
                degraded_mode=False
            )

    def _update_stats(self, result: ParseResult):
        """Update statistics based on parse result."""
        if result.success:
            if result.degraded_mode:
                # Check which attempt succeeded
                if result.attempt.attempt_number == 2:
                    self.stats.files_succeeded_minimal += 1
                elif result.attempt.attempt_number >= 3:
                    self.stats.files_succeeded_no_flags += 1
            else:
                self.stats.files_succeeded_full += 1

            # Track problematic flags
            self.stats.problematic_flags.update(result.problematic_flags)
        else:
            self.stats.files_failed += 1

    def get_stats(self) -> FilterStats:
        """Get filtering statistics."""
        return self.stats

    def print_summary(self):
        """Print summary of filtering statistics."""
        self.logger.info("=" * 50)
        self.logger.info("Flag Filtering Summary:")
        self.logger.info(f"  Files processed: {self.stats.files_processed}")
        self.logger.info(f"  Succeeded (full flags): {self.stats.files_succeeded_full}")
        self.logger.info(f"  Succeeded (minimal flags): {self.stats.files_succeeded_minimal}")
        self.logger.info(f"  Succeeded (no flags): {self.stats.files_succeeded_no_flags}")
        self.logger.info(f"  Failed: {self.stats.files_failed}")
        self.logger.info(f"  Total flags filtered: {self.stats.total_flags_filtered}")

        if self.stats.problematic_flags:
            self.logger.info("  Problematic flags:")
            for flag in sorted(self.stats.problematic_flags):
                failure_count = self.parser.get_flag_failure_history().get(flag, 0)
                self.logger.info(f"    {flag} ({failure_count} failures)")
        self.logger.info("=" * 50)
