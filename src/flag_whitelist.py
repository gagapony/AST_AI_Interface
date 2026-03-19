"""Flag whitelist management for libclang compatibility."""

import logging
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Set


@dataclass
class FlagCategory:
    """Flag category for grouping similar flags."""
    name: str
    description: str
    patterns: List[str]  # Regex patterns for matching flags in this category


class FlagWhitelist:
    """Manages whitelisted flags for libclang compatibility."""

    # Default whitelist: flags known to work with libclang
    DEFAULT_WHITELIST: Dict[str, FlagCategory] = {
        "include_paths": FlagCategory(
            name="include_paths",
            description="Include directory paths",
            patterns=[
                r'^-I\S+',  # -I/path or -I/path
                r'^-I$',
                r'^-isystem$',  # Followed by path
                r'^-isystem\S+',  # -isystem/path (rare)
                r'^-idirafter$',
                r'^-idirafter\S+',
                r'^-iquote$',
                r'^-iquote\S+',
                r'^-F\S+',  # Framework paths (macOS)
            ]
        ),
        "macros": FlagCategory(
            name="macros",
            description="Macro definitions",
            patterns=[
                r'^-D\S+',  # -DNAME or -DNAME=value
                r'^-D$',
                r'^-U\S+',  # Undefine macro
                r'^-U$',
            ]
        ),
        "language": FlagCategory(
            name="language",
            description="Language standard flags",
            patterns=[
                r'^-std=c\+\+\d+',  # -std=c++11, c++14, c++17, c++20
                r'^-std=gnu\+\+\d+',  # -std=gnu++11, etc.
                r'^-std=c\d+',  # -std=c11, c99, etc.
                r'^-std=gnu\d+',  # -std=gnu11, etc.
                r'^-x\s+(c|c\+\+)$',  # Language specification
                r'^-x(c|c\+\+)$',
            ]
        ),
        "target": FlagCategory(
            name="target",
            description="Target architecture flags (libclang supports some)",
            patterns=[
                r'^-target\s+\S+$',  # -target triple
                r'^-target\S+$',
                r'^--target=\S+$',  # --target=triple (GCC style, may work)
            ]
        ),
        "warnings": FlagCategory(
            name="warnings",
            description="Warning control flags",
            patterns=[
                r'^-W(no-)?\S+',  # -Wall, -Wno-error, -Wno-unknown
                r'^-w$',  # Disable all warnings
            ]
        ),
        "compatibility": FlagCategory(
            name="compatibility",
            description="Compatibility mode flags",
            patterns=[
                r'^-f(no-)?\S+',  # -fno-exceptions, etc. (libclang supports some)
                r'^-m(no-)?\S+',  # -m32, -m64 (architecture)
            ]
        ),
    }

    # Blacklist: flags libclang NEVER supports
    BLACKLIST: Set[str] = {
        # Output control
        '-o',  # Output file
        '-c',  # Compile only
        '-S',  # Assemble only
        '-E',  # Preprocess only

        # Linker flags
        '-l',  # Link library
        '-L',  # Library path
        '-Wl,',  # Linker options
        '-shared',  # Shared library
        '-static',  # Static linking
        '-nostartfiles',  # No startup files
        '-nodefaultlibs',  # No default libraries
        '-nostdlib',  # No standard library
        '-e',  # Entry point

        # Build artifacts
        '-MF',  # Dependency file
        '-MT',  # Dependency target
        '-MMD',  # Generate dependencies

        # Architecture flags (libclang doesn't support)
        '-march=',
        '-mtune=',
        '-mabi=',
        '-mfloat-abi=',
        '-mfpu=',
        '-mthumb',
        '-marm',
        '-mcpu=',

        # Other unsupported
        '-pipe',  # Pipe compilation
        '-g',  # Debug info (libclang ignores, but safe)
        '-ggdb',  # Debug format
        '-O', '-O0', '-O1', '-O2', '-O3', '-Os', '-Oz',  # Optimization
        '-flto',  # Link-time optimization
        '-fvisibility=',
    }

    def __init__(self, custom_whitelist: Optional[Dict[str, List[str]]] = None):
        """
        Initialize whitelist with defaults and merge custom overrides.

        Args:
            custom_whitelist: Optional user-defined whitelist categories
                             Format: {category_name: [flag_patterns]}
        """
        self.logger = logging.getLogger(__name__)
        self.whitelist = self._deep_copy_defaults()
        if custom_whitelist:
            self._merge_custom_whitelist(custom_whitelist)

    def is_whitelisted(self, flag: str) -> bool:
        """
        Check if a flag is in the whitelist.

        Args:
            flag: Compiler flag to check

        Returns:
            True if flag matches any whitelist pattern, False otherwise
        """
        # Check blacklist first (highest priority)
        if self._is_blacklisted(flag):
            return False

        # Check whitelist patterns
        return self._matches_whitelist_pattern(flag)

    def filter_flags(self, flags: List[str]) -> List[str]:
        """
        Filter a list of flags, returning only whitelisted ones.

        Args:
            flags: List of compiler flags

        Returns:
            List of whitelisted flags
        """
        filtered = []
        i = 0
        while i < len(flags):
            flag = flags[i]

            # Handle flags with separate arguments (e.g., -D NAME)
            if self._has_separate_arg(flag):
                if self.is_whitelisted(flag):
                    if i + 1 < len(flags):
                        filtered.append(flag)
                        filtered.append(flags[i + 1])
                        i += 2
                        self.logger.debug(f"  Kept flag with arg: {flag} {flags[i-1]}")
                        continue
                    else:
                        # Flag without argument, skip
                        i += 1
                        self.logger.debug(f"  Skipped flag without arg: {flag}")
                        continue
            else:
                if self.is_whitelisted(flag):
                    filtered.append(flag)
                    self.logger.debug(f"  Kept flag: {flag}")
                else:
                    self.logger.debug(f"  Filtered out flag: {flag}")
                i += 1
                continue

            i += 1

        return filtered

    def get_minimal_flags(self, flags: List[str]) -> List[str]:
        """
        Get minimal essential flags (include paths + macros only).

        Args:
            flags: Original compiler flags

        Returns:
            Minimal set of flags for second-pass parsing
        """
        minimal_categories = ['include_paths', 'macros']
        result = []

        i = 0
        while i < len(flags):
            flag = flags[i]

            # Check if flag matches minimal categories
            category = self._get_flag_category(flag)
            if category and category.name in minimal_categories:
                if self._has_separate_arg(flag) and i + 1 < len(flags):
                    result.append(flag)
                    result.append(flags[i + 1])
                    i += 2
                else:
                    result.append(flag)
                    i += 1
            else:
                i += 1

        return result

    def get_categories(self) -> Dict[str, FlagCategory]:
        """Get all flag categories (for debugging/config export)."""
        return self.whitelist

    def _is_blacklisted(self, flag: str) -> bool:
        """Check if flag is in blacklist."""
        # Exact match
        if flag in self.BLACKLIST:
            self.logger.debug(f"  Blacklisted (exact): {flag}")
            return True

        # Prefix match (e.g., -march=rv32imc)
        for blacklisted in self.BLACKLIST:
            if blacklisted.endswith('=') and flag.startswith(blacklisted):
                self.logger.debug(f"  Blacklisted (prefix): {flag}")
                return True

        return False

    def _matches_whitelist_pattern(self, flag: str) -> bool:
        """Check if flag matches any whitelist pattern."""
        for category in self.whitelist.values():
            for pattern in category.patterns:
                if re.match(pattern, flag):
                    return True
        return False

    def _get_flag_category(self, flag: str) -> Optional[FlagCategory]:
        """Get the category a flag belongs to (if any)."""
        for category in self.whitelist.values():
            for pattern in category.patterns:
                if re.match(pattern, flag):
                    return category
        return None

    def _has_separate_arg(self, flag: str) -> bool:
        """
        Check if flag expects a separate argument.

        Examples:
            -D NAME    -> True
            -DNAME     -> False
            -isystem /path -> True
            -isystem/path -> False (rare)
        """
        return flag in ('-D', '-U', '-I', '-isystem', '-idirafter', '-iquote',
                       '-L', '-l', '-o', '-MF', '-MT', '-target', '-x')

    def _deep_copy_defaults(self) -> Dict[str, FlagCategory]:
        """Create deep copy of default whitelist."""
        return {
            name: FlagCategory(
                name=cat.name,
                description=cat.description,
                patterns=cat.patterns.copy()
            )
            for name, cat in self.DEFAULT_WHITELIST.items()
        }

    def _merge_custom_whitelist(self, custom: Dict[str, List[str]]):
        """Merge user-defined whitelist with defaults."""
        for category_name, patterns in custom.items():
            if category_name in self.whitelist:
                # Extend existing category
                self.whitelist[category_name].patterns.extend(patterns)
                self.logger.info(f"Extended category '{category_name}' with {len(patterns)} patterns")
            else:
                # Create new category
                self.whitelist[category_name] = FlagCategory(
                    name=category_name,
                    description=f"Custom category: {category_name}",
                    patterns=patterns
                )
                self.logger.info(f"Created new category '{category_name}' with {len(patterns)} patterns")
