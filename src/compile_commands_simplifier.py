"""Compile commands simplifier for performance optimization."""

import json
import logging
import shlex
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .compilation_db import CompilationUnit


class CompileCommandsSimplifier:
    """Simplify compile_commands.json by filtering flags."""

    def __init__(self, filter_paths: List[str], logger: Optional[logging.Logger] = None):
        """
        Initialize simplifier.

        Args:
            filter_paths: List of normalized filter paths
            logger: Optional logger instance
        """
        self.filter_paths = [p.rstrip('/') for p in filter_paths]
        self.logger = logger or logging.getLogger(__name__)

    def simplify_units(self, units: List[CompilationUnit]) -> Tuple[List[CompilationUnit], Dict]:
        """
        Simplify compilation units by filtering flags.

        Keeps:
        - All -D flags (macro definitions)
        - Only -I flags matching filter paths
        - Only files matching filter paths

        Removes:
        - All -I flags not matching filter paths
        - All other compiler flags (-std, -O, -Wall, etc.)

        Args:
            units: List of CompilationUnit objects

        Returns:
            Tuple of (simplified_units, stats_dict)
        """
        stats = {
            'original_units': len(units),
            'kept_units': 0,
            'removed_units': 0,
            'kept_D_flags': 0,
            'kept_I_flags': 0,
            'removed_I_flags': 0,
            'removed_other_flags': 0
        }

        simplified_units = []

        for unit in units:
            # Check if file is in filter paths
            if not self._is_allowed_path(unit.file):
                stats['removed_units'] += 1
                self.logger.debug(f"Simplifier: Removed file {unit.file}")
                continue

            # Filter flags
            filtered_flags, unit_stats = self._filter_flags(unit.flags)
            stats['kept_units'] += 1

            # Accumulate stats
            for key in ['kept_D_flags', 'kept_I_flags', 'removed_I_flags', 'removed_other_flags']:
                stats[key] += unit_stats[key]

            # Reconstruct command
            filtered_command = self._reconstruct_command(unit.command, filtered_flags)

            # Create simplified unit
            simplified_unit = CompilationUnit(
                directory=unit.directory,
                command=filtered_command,
                file=unit.file,
                flags=filtered_flags
            )

            simplified_units.append(simplified_unit)

        return simplified_units, stats

    def _is_allowed_path(self, path: str) -> bool:
        """Check if path matches any filter path."""
        path = path.rstrip('/')
        for filter_path in self.filter_paths:
            if path == filter_path or path.startswith(filter_path + '/'):
                return True
        return False

    def _filter_flags(self, flags: List[str]) -> Tuple[List[str], Dict]:
        """Filter flags, keeping only -D and matching -I."""
        stats = {
            'kept_D_flags': 0,
            'kept_I_flags': 0,
            'removed_I_flags': 0,
            'removed_other_flags': 0
        }

        filtered_flags = []
        i = 0

        while i < len(flags):
            flag = flags[i]

            # Keep all -D flags
            if flag == '-D' and i + 1 < len(flags):
                filtered_flags.extend(['-D', flags[i + 1]])
                stats['kept_D_flags'] += 1
                i += 2
                continue
            elif flag.startswith('-D'):
                filtered_flags.append(flag)
                stats['kept_D_flags'] += 1
                i += 1
                continue

            # Keep -I flags only if they match filter paths
            if flag == '-I' and i + 1 < len(flags):
                path = flags[i + 1]
                if self._is_allowed_path(path):
                    filtered_flags.extend(['-I', path])
                    stats['kept_I_flags'] += 1
                else:
                    stats['removed_I_flags'] += 1
                i += 2
                continue
            elif flag.startswith('-I'):
                path = flag[2:]
                if self._is_allowed_path(path):
                    filtered_flags.append(flag)
                    stats['kept_I_flags'] += 1
                else:
                    stats['removed_I_flags'] += 1
                i += 1
                continue

            # Keep -isystem flags only if they match filter paths
            if flag == '-isystem' and i + 1 < len(flags):
                path = flags[i + 1]
                if self._is_allowed_path(path):
                    filtered_flags.extend(['-isystem', path])
                    stats['kept_I_flags'] += 1
                else:
                    stats['removed_I_flags'] += 1
                i += 2
                continue
            elif flag.startswith('-isystem'):
                path = flag[9:]
                if self._is_allowed_path(path):
                    filtered_flags.append(flag)
                    stats['kept_I_flags'] += 1
                else:
                    stats['removed_I_flags'] += 1
                i += 1
                continue

            # Remove all other flags
            stats['removed_other_flags'] += 1
            i += 1

        return filtered_flags, stats

    def _reconstruct_command(self, original_command: str, filtered_flags: List[str]) -> str:
        """Reconstruct command with filtered flags."""
        # Parse original command to get compiler executable
        tokens = shlex.split(original_command)

        if not tokens:
            return original_command

        # Keep first token (compiler)
        compiler = tokens[0]

        # Reconstruct command: compiler + filtered_flags + source file
        parts = [compiler] + filtered_flags

        # Add source file if present in original
        for token in tokens:
            if token.endswith(('.c', '.cpp', '.cc', '.cxx', '.C')):
                parts.append(token)
                break

        return ' '.join(parts)

    def dump_to_file(self, units: List[CompilationUnit], output_path: str) -> None:
        """
        Dump simplified compilation units to JSON file.

        Args:
            units: List of CompilationUnit objects
            output_path: Path to output JSON file
        """
        # Convert to dict format
        output_data = [
            {
                'directory': unit.directory,
                'command': unit.command,
                'file': unit.file
            }
            for unit in units
        ]

        # Write to file
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2)

        self.logger.info(f"Simplified compile_commands written to {output_path}")
