"""Parse Doxygen comments."""

import logging
import re
from typing import Optional


class DoxygenParser:
    """Parse Doxygen comments to extract @brief."""

    def __init__(self):
        """Initialize parser."""
        # Multi-pattern regex for @brief and \brief
        # Updated to properly capture multi-line briefs
        self._brief_patterns = [
            # @brief or \brief followed by text (capture until @tag or end of comment)
            r'[@\\]brief\s+(.*?)(?:\n\s*[@\\](?:param|return|note|warning|see|todo|brief)|\n\s*(?:///|\*/)|$)',
            # @brief on line by itself, text on following lines
            r'[@\\]brief\s*$\s+(.*?)(?:\n\s*[@\\](?:param|return|note|warning|see|todo|brief)|\n\s*(?:///|\*/)|$)',
        ]

    def parse(self, comment: str) -> Optional[str]:
        """
        Parse Doxygen comment and extract @brief text.

        Args:
            comment: Raw comment text

        Returns:
            @brief text or None if not found
        """
        if not comment:
            return None

        brief = self._parse_brief_tag(comment)
        if brief:
            return self._clean_brief(brief)

        return None

    def _parse_brief_tag(self, comment: str) -> Optional[str]:
        """
        Extract @brief tag from comment.

        Args:
            comment: Raw comment text

        Returns:
            Brief text or None
        """
        # Try all patterns
        for pattern in self._brief_patterns:
            match = re.search(pattern, comment, re.DOTALL | re.MULTILINE)
            if match:
                return match.group(1)

        return None

    def _clean_brief(self, brief: str) -> str:
        """
        Clean up brief text.

        Args:
            brief: Raw brief text

        Returns:
            Cleaned brief text
        """
        # Remove leading/trailing whitespace
        brief = brief.strip()

        # Remove comment markers (/// only, preserve *)
        # Remove line-leading /// or \ (for Doxygen tags)
        brief = re.sub(r'^\s*(///|\\)+\s*', '', brief, flags=re.MULTILINE)

        # Normalize whitespace (collapse multiple spaces/newlines)
        brief = re.sub(r'\s+', ' ', brief)

        # Remove trailing comment markers
        brief = brief.strip(' */')

        return brief
