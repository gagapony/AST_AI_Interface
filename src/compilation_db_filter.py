"""Compilation database filtering for clang-call-analyzer."""

import json
import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .filter_config import FilterConfig, FilterMode


@dataclass
class FilterStats:
    """Statistics about database filtering."""
    total_units: int = 0
    filtered_units: int = 0
    kept_units: int = 0


@dataclass
class FilteredCompilationUnit:
    """Compilation unit after filtering."""
    directory: str
    command: str
    file: str
    original_index: int  # Index in original compile_commands.json


class CompilationDatabaseFilter:
    """
    Filter compilation database entries based on filter configuration.

    This reduces the number of files parsed by libclang, improving performance.
    """

    def __init__(self,
                 filter_config: FilterConfig,
                 project_root: str = None,
                 logger: Optional[logging.Logger] = None):
        """
        Initialize compilation database filter.

        Args:
            filter_config: FilterConfig instance
            project_root: Project root directory for path resolution
            logger: Optional logger instance
        """
        self.filter_config = filter_config
        self.project_root = project_root or os.getcwd()
        self.logger = logger or logging.getLogger(__name__)
        self.stats = FilterStats()

    def filter_compilation_db(self,
                               compile_commands: List[Dict[str, Any]]) -> List[FilteredCompilationUnit]:
        """
        Filter compilation units based on filter configuration.

        Args:
            compile_commands: List of compilation units from compile_commands.json

        Returns:
            List of filtered compilation units (kept units only)
        """
        self.stats = FilterStats(total_units=len(compile_commands))
        filtered_units = []

        for idx, unit in enumerate(compile_commands):
            file_path = unit['file']
            directory = unit.get('directory', '')

            # Resolve absolute file path
            if not os.path.isabs(file_path):
                abs_file_path = os.path.join(directory, file_path)
            else:
                abs_file_path = file_path

            # Check if in filter scope
            if self.filter_config.is_in_scope(abs_file_path, self.project_root):
                # Keep this unit
                filtered_units.append(FilteredCompilationUnit(
                    directory=directory,
                    command=unit['command'],
                    file=abs_file_path,
                    original_index=idx
                ))
                self.stats.kept_units += 1
            else:
                # Filter out this unit
                self.stats.filtered_units += 1
                if self.filter_config.mode != FilterMode.AUTO_DETECT:
                    self.logger.debug(f"Filtered compilation unit: {file_path}")

        return filtered_units

    def dump_filtered_db(self,
                         compile_commands: List[Dict[str, Any]],
                         output_path: str) -> None:
        """
        Dump filtered compilation database to JSON file.

        Args:
            compile_commands: Original compilation commands
            output_path: Path to output JSON file
        """
        # Get filtered units
        filtered_units = self.filter_compilation_db(compile_commands)

        # Convert to dict format for JSON output
        output_units = []
        for unit in filtered_units:
            output_units.append({
                'directory': unit.directory,
                'command': unit.command,
                'file': unit.file
            })

        # Write to file
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output_units, f, indent=2)

        self.logger.info(
            f"Dumped {len(output_units)} compilation units to {output_path}"
        )

    def get_stats(self) -> FilterStats:
        """Get filtering statistics."""
        return self.stats

    def get_summary(self) -> str:
        """Get human-readable summary of filtering."""
        if self.stats.total_units == 0:
            return "No compilation units to filter"

        if self.filter_config.mode == FilterMode.AUTO_DETECT:
            return f"All {self.stats.total_units} compilation units (no filter)"

        kept_pct = (self.stats.kept_units / self.stats.total_units) * 100
        return (
            f"Filtered {self.stats.total_units} compilation units: "
            f"{self.stats.kept_units} kept ({kept_pct:.1f}%), "
            f"{self.stats.filtered_units} filtered"
        )
