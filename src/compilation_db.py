"""Parse compile_commands.json."""

import json
import logging
import shlex
from pathlib import Path
from typing import List, NamedTuple, Optional, Tuple


class CompilationUnit(NamedTuple):
    """Single compilation unit."""
    directory: str
    command: str
    file: str
    flags: List[str]


class CompilationDatabase:
    """Parse compile_commands.json."""

    def __init__(self, db_path: str):
        """Initialize from compile_commands.json path."""
        self.db_path = db_path
        self.entries: List[CompilationUnit] = []

        self._load()

    def _load(self) -> None:
        """Load and parse compile_commands.json."""
        try:
            with open(self.db_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            if not isinstance(data, list):
                raise ValueError("compile_commands.json must be a list")

            self.entries = []
            for entry in data:
                try:
                    unit = self._parse_entry(entry)
                    if unit is not None:
                        self.entries.append(unit)
                except Exception as e:
                    logging.warning(f"Failed to parse entry {entry.get('file', 'unknown')}: {e}")
                    continue

            logging.info(f"Loaded {len(self.entries)} compilation units")

        except Exception as e:
            logging.error(f"Failed to load compile_commands.json: {e}")
            raise

    def _parse_entry(self, entry: dict) -> Optional[CompilationUnit]:
        """Parse a single compile_commands.json entry.

        Args:
            entry: Dictionary containing compilation database entry

        Returns:
            CompilationUnit if successful, None if entry should be skipped
        """
        directory = entry.get('directory', '')
        raw_file_path = entry.get('file', '')

        if not raw_file_path:
            raise ValueError("Missing 'file' field in compilation database entry")

        # Handle both absolute and relative file paths
        file_path_obj = Path(raw_file_path)
        if file_path_obj.is_absolute():
            file_path = str(file_path_obj)
        else:
            # Relative path: resolve against directory field
            if not directory:
                raise ValueError("Relative file path requires 'directory' field")
            file_path = str(Path(directory) / raw_file_path)

        # Handle both 'arguments' and 'command' fields
        arguments = entry.get('arguments')
        command = entry.get('command', '')

        if arguments is not None:
            # arguments has priority over command
            if not isinstance(arguments, list):
                logging.warning(f"Invalid 'arguments' type (expected list): {type(arguments)} for file {file_path}")
                return None
            command, flags = self._extract_from_arguments(arguments, directory)
        elif command:
            # Use command field (backward compatibility)
            flags = self._extract_flags(command, directory)
        else:
            logging.warning(f"Entry missing both 'arguments' and 'command' fields: {file_path}")
            return None

        return CompilationUnit(
            directory=directory,
            command=command,
            file=file_path,
            flags=flags
        )

    def _extract_flags(self, command: str, directory: str) -> List[str]:
        """
        Extract -D and -I compiler flags from compile command.

        Only extracts -D (macro definitions) and -I (include paths) flags.
        All other flags are skipped as they will be filtered out later.

        Args:
            command: Compile command string
            directory: Working directory for resolving relative paths

        Returns:
            List of -D and -I flags
        """
        # Use shlex.split to handle quoted arguments correctly
        tokens = shlex.split(command)
        flags = []

        i = 0
        while i < len(tokens):
            token = tokens[i]

            # Include paths (handle both -Ipath and -I path formats)
            if token.startswith('-I'):
                if token == '-I' and i + 1 < len(tokens):
                    # -I path format
                    path = tokens[i + 1]
                    if not Path(path).is_absolute():
                        path = str(Path(directory) / path)
                    flags.extend(['-I', path])
                    i += 2
                elif len(token) > 2:
                    # -Ipath format
                    path = token[2:]
                    if not Path(path).is_absolute():
                        path = str(Path(directory) / path)
                    flags.append(f'-I{path}')
                    i += 1
                else:
                    i += 1
                continue

            # Define macros (handle both -DNAME and -D NAME formats)
            if token.startswith('-D'):
                if token == '-D' and i + 1 < len(tokens):
                    flags.extend(['-D', tokens[i + 1]])
                    i += 2
                elif len(token) > 2:
                    flags.append(token)
                    i += 1
                else:
                    i += 1
                continue

            # Skip everything else
            i += 1

        return flags

    def _extract_from_arguments(self, arguments: List[str], directory: str) -> Tuple[str, List[str]]:
        """
        Extract command string and -D/-I flags from arguments array.

        Only extracts -D (macro definitions) and -I (include paths) flags.
        All other flags are skipped as they will be filtered out later.

        Args:
            arguments: List of command-line arguments
            directory: Working directory for resolving relative paths

        Returns:
            Tuple of (command_string, flags_list)

        Raises:
            ValueError: If arguments list is empty
        """
        if not arguments:
            raise ValueError("Empty arguments list")

        # First argument is the compiler executable
        compiler = arguments[0]

        flags = []
        i = 1  # Skip compiler

        while i < len(arguments):
            arg = arguments[i]

            # Include paths (handle both -Ipath and -I path formats)
            if arg == '-I' and i + 1 < len(arguments):
                path = arguments[i + 1]
                if not Path(path).is_absolute():
                    path = str(Path(directory) / path)
                flags.extend(['-I', path])
                i += 2
            elif arg.startswith('-I') and len(arg) > 2:
                path = arg[2:]
                if not Path(path).is_absolute():
                    path = str(Path(directory) / path)
                flags.append(f'-I{path}')
                i += 1
            # Define macros (handle both -DNAME and -D NAME formats)
            elif arg == '-D' and i + 1 < len(arguments):
                flags.extend(['-D', arguments[i + 1]])
                i += 2
            elif arg.startswith('-D') and len(arg) > 2:
                flags.append(arg)
                i += 1
            # Skip everything else
            else:
                i += 1

        # Reconstruct command string
        command = ' '.join([compiler] + flags)
        # We'll add the source file later during output

        return command, flags

    def get_units(self) -> List[CompilationUnit]:
        """Return all compilation units."""
        return self.entries
