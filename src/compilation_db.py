"""Parse compile_commands.json."""

import json
import logging
import shlex
from pathlib import Path
from typing import List, NamedTuple


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

    def _load(self):
        """Load and parse compile_commands.json."""
        try:
            with open(self.db_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            if not isinstance(data, list):
                raise ValueError("compile_commands.json must be a list")

            self.entries = [self._parse_entry(entry) for entry in data]

            logging.info(f"Loaded {len(self.entries)} compilation units")

        except Exception as e:
            logging.error(f"Failed to load compile_commands.json: {e}")
            raise

    def _parse_entry(self, entry: dict) -> CompilationUnit:
        """Parse a single compile_commands.json entry."""
        directory = entry.get('directory', '')
        command = entry.get('command', '')
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

        flags = self._extract_flags(command, directory)

        return CompilationUnit(
            directory=directory,
            command=command,
            file=file_path,
            flags=flags
        )

    def _extract_flags(self, command: str, directory: str) -> List[str]:
        """
        Extract compiler flags from compile command.

        Note: This method extracts all flags without filtering.
        Filtering is handled by FlagFilterManager later.
        """
        # Use shlex.split to handle quoted arguments correctly
        tokens = shlex.split(command)
        flags = []

        # Skip compiler executable and output files
        i = 0
        while i < len(tokens):
            token = tokens[i]

            # Skip compiler executable
            if token.endswith('++') or token.endswith('gcc') or token.endswith('clang'):
                i += 1
                continue

            # Skip output file option
            if token == '-o':
                if i + 1 < len(tokens):
                    i += 2
                    continue
                else:
                    i += 1
                    continue

            # Skip if it's an output file
            if token.startswith('-o'):
                i += 1
                continue

            # Skip source files
            if token.endswith(('.c', '.cpp', '.cc', '.cxx', '.C', '.h', '.hpp', '.hh', '.hxx')):
                i += 1
                continue

            # Skip object files and build artifacts
            if token.endswith('.o') or '.pio/build/' in token:
                i += 1
                continue

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

            # System include directories (handle both -isystempath and -isystem path formats)
            if token.startswith('-isystem'):
                if token == '-isystem' and i + 1 < len(tokens):
                    # -isystem path format
                    path = tokens[i + 1]
                    if not Path(path).is_absolute():
                        path = str(Path(directory) / path)
                    flags.extend(['-isystem', path])
                    i += 2
                elif len(token) > 9:
                    # -isystempath format
                    path = token[9:]
                    if not Path(path).is_absolute():
                        path = str(Path(directory) / path)
                    flags.append(f'-isystem{path}')
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

            # Undefine macros (handle both -UNAME and -U NAME formats)
            if token.startswith('-U'):
                if token == '-U' and i + 1 < len(tokens):
                    flags.extend(['-U', tokens[i + 1]])
                    i += 2
                elif len(token) > 2:
                    flags.append(token)
                    i += 1
                else:
                    i += 1
                continue

            # Keep all other flags as-is (filtering will happen later)
            flags.append(token)
            i += 1

        return flags

    def get_units(self) -> List[CompilationUnit]:
        """Return all compilation units."""
        return self.entries
