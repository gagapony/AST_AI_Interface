"""Parse compile_commands.json."""

import json
import logging
from pathlib import Path
from typing import List, NamedTuple


class CompilationUnit(NamedTuple):
    """Single compilation unit."""
    directory: str
    command: str
    file: str
    flags: List[str]
    includes: List[str]


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
        includes = self._extract_includes(flags)

        return CompilationUnit(
            directory=directory,
            command=command,
            file=file_path,
            flags=flags,
            includes=includes
        )

    def _extract_flags(self, command: str, directory: str) -> List[str]:
        """Extract clang-compatible flags from compile command."""
        tokens = command.split()
        flags = []

        # Skip compiler executable
        for i, token in enumerate(tokens):
            if token.endswith('++') or token.endswith('gcc') or token.endswith('clang'):
                continue

            # Include directories
            if token.startswith('-I'):
                if token == '-I' and i + 1 < len(tokens):
                    # -I path format
                    path = tokens[i + 1]
                    if not Path(path).is_absolute():
                        path = str(Path(directory) / path)
                    flags.extend(['-I', path])
                elif len(token) > 2:
                    # -Ipath format
                    path = token[2:]
                    if not Path(path).is_absolute():
                        path = str(Path(directory) / path)
                    flags.append(f'-I{path}')

            # System include directories (important for Arduino/ESP32 projects)
            elif token.startswith('-isystem'):
                if token == '-isystem' and i + 1 < len(tokens):
                    # -isystem path format
                    path = tokens[i + 1]
                    if not Path(path).is_absolute():
                        path = str(Path(directory) / path)
                    flags.extend(['-isystem', path])
                elif len(token) > 9:
                    # -isystempath format
                    path = token[9:]
                    if not Path(path).is_absolute():
                        path = str(Path(directory) / path)
                    flags.append(f'-isystem{path}')

            # Define macros
            elif token.startswith('-D'):
                if token == '-D' and i + 1 < len(tokens):
                    flags.extend(['-D', tokens[i + 1]])
                elif len(token) > 2:
                    flags.append(token)

            # Language standard
            elif token.startswith('-std='):
                flags.append(token)

            # Warnings
            elif token.startswith('-W'):
                continue

            # Optimization levels
            elif token.startswith('-O'):
                continue

            # Debug info
            elif token.startswith('-g'):
                continue

            # Source file
            elif token.endswith(('.c', '.cpp', '.cc', '.cxx', '.C', '.h', '.hpp', '.hh', '.hxx')):
                continue

            # Output file
            elif token.startswith('-o'):
                if i + 1 < len(tokens):
                    continue
                else:
                    continue

            # Linker flags (skip)
            elif token.startswith('-l') or token.startswith('-L'):
                continue

            # Other flags (pass through)
            else:
                flags.append(token)

        return flags

    def _extract_includes(self, flags: List[str]) -> List[str]:
        """Extract include paths from flags (including -isystem)."""
        includes = []
        for flag in flags:
            if flag.startswith('-I'):
                if flag == '-I':
                    continue
                includes.append(flag[2:])
            elif flag.startswith('-isystem'):
                if flag == '-isystem':
                    continue
                includes.append(flag[9:])
        return includes

    def get_units(self) -> List[CompilationUnit]:
        """Return all compilation units."""
        return self.entries
