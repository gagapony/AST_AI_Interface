"""Filter configuration manager for clang-call-analyzer."""

import logging
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class FilterMode(Enum):
    """Filter configuration mode priority."""
    FILTER_CFG = 1      # Highest: --filter-cfg specified
    SINGLE_PATH = 2     # Medium: --path specified
    AUTO_DETECT = 3     # Lowest: analyze all (no filter)


@dataclass
class FilterConfig:
    """Filter configuration with paths and mode."""
    mode: FilterMode
    paths: List[str]
    config_file: Optional[str] = None  # Path to filter.cfg if mode=FILTER_CFG
    normalized_paths: List[str] = field(default_factory=list)
    logger: Optional[logging.Logger] = None
    project_root: Optional[str] = None  # Project root for relative path resolution

    def __post_init__(self):
        """Normalize all filter paths to absolute paths."""
        self.normalized_paths = self._normalize_paths(self.paths)

    def _normalize_paths(self, paths: List[str]) -> List[str]:
        """
        Normalize filter paths to absolute paths.

        Args:
            paths: List of filter paths (relative or absolute)

        Returns:
            List of normalized absolute paths
        """
        normalized = []
        for p in paths:
            if os.path.isabs(p):
                # Already absolute
                norm = os.path.normpath(p)
            else:
                # Relative to project root (if available) or current directory
                if self.project_root:
                    norm = os.path.abspath(os.path.join(self.project_root, os.path.normpath(p)))
                else:
                    norm = os.path.abspath(os.path.normpath(p))

            normalized.append(norm)
        return normalized

    def is_in_scope(self, file_path: str, project_root: str = None) -> bool:
        """
        Check if a file path is within filter scope.

        Args:
            file_path: Path to check
            project_root: Optional project root for relative path calculation

        Returns:
            True if file is in filter scope, False otherwise
        """
        # If no filter active (auto-detect mode), analyze everything
        if self.mode == FilterMode.AUTO_DETECT:
            return True

        # Normalize file path
        file_path = os.path.normpath(file_path)

        # Determine if we should work with relative paths
        use_relative_paths = False
        if project_root and not os.path.isabs(file_path):
            # File path is relative, use relative paths for comparison
            use_relative_paths = True

        # Check each filter path
        for filter_path in self.normalized_paths:
            norm_filter = os.path.normpath(filter_path)

            # Convert filter path to relative if needed
            if use_relative_paths and os.path.isabs(norm_filter):
                try:
                    norm_filter = os.path.relpath(norm_filter, project_root)
                except ValueError:
                    # Filter path is on different drive, skip
                    continue

            # Normalize the filter path again after conversion
            norm_filter = os.path.normpath(norm_filter)

            # Ensure filter path ends with os.sep for directory matching
            # This ensures 'src' matches 'src/file' but not 'src2/file'
            filter_with_sep = norm_filter if norm_filter.endswith(os.sep) else norm_filter + os.sep

            # Check if file_path is exactly the filter path (the filter path itself)
            if file_path == norm_filter:
                return True

            # Check if file_path starts with filter_path (with separator)
            if file_path.startswith(filter_with_sep):
                return True

        return False

    def get_scope_summary(self) -> str:
        """Get human-readable summary of filter scope."""
        if self.mode == FilterMode.AUTO_DETECT:
            return "All files (no filter)"
        elif self.mode == FilterMode.SINGLE_PATH:
            return f"Single path: {self.paths[0]}"
        elif self.mode == FilterMode.FILTER_CFG:
            return f"Filter config: {self.config_file} ({len(self.paths)} paths)"
        else:
            return "Unknown mode"


class FilterConfigLoader:
    """Load and parse filter configuration."""

    def __init__(self, project_root: str = None, logger: Optional[logging.Logger] = None):
        """
        Initialize filter config loader.

        Args:
            project_root: Optional project root directory for relative path resolution
            logger: Optional logger instance
        """
        self.project_root = project_root or os.getcwd()
        self.logger = logger or logging.getLogger(__name__)

    def load(self,
             filter_cfg_path: Optional[str] = None,
             single_path: Optional[str] = None) -> FilterConfig:
        """
        Load filter configuration with priority logic.

        Priority: filter_cfg > single_path > auto-detect

        Args:
            filter_cfg_path: Path to filter.cfg file (from --filter-cfg)
            single_path: Single filter path (from --path)

        Returns:
            FilterConfig instance
        """
        # Priority 1: --filter-cfg
        if filter_cfg_path:
            return self._load_from_cfg(filter_cfg_path)

        # Priority 2: --path
        if single_path:
            return FilterConfig(
                mode=FilterMode.SINGLE_PATH,
                paths=[single_path],
                config_file=None,
                logger=self.logger,
                project_root=self.project_root
            )

        # Priority 3: Auto-detect (no filter)
        return FilterConfig(
            mode=FilterMode.AUTO_DETECT,
            paths=[],
            config_file=None,
            logger=self.logger,
            project_root=self.project_root
        )

    def _load_from_cfg(self, cfg_path: str) -> FilterConfig:
        """
        Load filter configuration from INI file.

        Args:
            cfg_path: Path to filter.cfg file

        Returns:
            FilterConfig instance

        Raises:
            FileNotFoundError: If config file doesn't exist
            ValueError: If config file is invalid
        """
        if not os.path.exists(cfg_path):
            raise FileNotFoundError(f"Filter config file not found: {cfg_path}")

        # Parse INI format (simple line-based parser, no sections)
        paths = []
        with open(cfg_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()

                # Skip empty lines
                if not line:
                    continue

                # Skip comments (lines starting with #)
                if line.startswith('#'):
                    continue

                # Treat as filter path
                paths.append(line)

        if not paths:
            self.logger.warning(f"Filter config file '{cfg_path}' contains no paths")

        return FilterConfig(
            mode=FilterMode.FILTER_CFG,
            paths=paths,
            config_file=cfg_path,
            logger=self.logger,
            project_root=self.project_root
        )

    def validate_paths(self, config: FilterConfig) -> bool:
        """
        Validate that filter paths exist (warning only, not error).

        Args:
            config: FilterConfig instance

        Returns:
            True (always, validation is warning-only)
        """
        if config.mode == FilterMode.AUTO_DETECT:
            return True

        for path in config.normalized_paths:
            if not os.path.exists(path):
                self.logger.warning(f"Filter path does not exist: {path}")
            elif not os.path.isdir(path):
                self.logger.warning(f"Filter path is not a directory: {path}")

        return True
