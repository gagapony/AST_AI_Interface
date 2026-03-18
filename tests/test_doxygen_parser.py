"""Unit tests for doxygen_parser module."""

import unittest

from src.doxygen_parser import DoxygenParser


class MockCursor:
    """Mock cursor for testing."""

    def __init__(self, raw_comment=None):
        self.raw_comment = raw_comment


class TestDoxygenParser(unittest.TestCase):
    """Test cases for DoxygenParser class."""

    def setUp(self):
        """Set up test fixtures."""
        self.parser = DoxygenParser()

    def test_extract_brief_atbrief(self):
        """Test extracting @brief tag."""
        cursor = MockCursor("/** @brief This is a brief description */")
        result = self.parser.extract_brief(cursor)
        self.assertEqual(result, "This is a brief description")

    def test_extract_brief_backslash_brief(self):
        """Test extracting \\brief tag."""
        cursor = MockCursor("/** \\brief This is a brief description */")
        result = self.parser.extract_brief(cursor)
        self.assertEqual(result, "This is a brief description")

    def test_extract_brief_multiline(self):
        """Test extracting brief with multiline comment."""
        cursor = MockCursor(
            "/**\n"
            " * @brief This is a brief\n"
            " * description spanning multiple lines\n"
            " */"
        )
        result = self.parser.extract_brief(cursor)
        self.assertEqual(result, "This is a brief description spanning multiple lines")

    def test_extract_brief_line_by_itself(self):
        """Test extracting brief when tag is on line by itself."""
        cursor = MockCursor(
            "/**\n"
            " * @brief\n"
            " * This text is on next line\n"
            " */"
        )
        result = self.parser.extract_brief(cursor)
        self.assertEqual(result, "This text is on next line")

    def test_extract_brief_triple_slash(self):
        """Test extracting brief with triple-slash style."""
        cursor = MockCursor("/// @brief Brief description")
        result = self.parser.extract_brief(cursor)
        self.assertEqual(result, "Brief description")

    def test_extract_brief_with_asterisks(self):
        """Test that asterisks are properly cleaned."""
        cursor = MockCursor(
            "/**\n"
            " * @brief *Important* note\n"
            " */"
        )
        result = self.parser.extract_brief(cursor)
        self.assertEqual(result, "*Important* note")

    def test_extract_brief_no_brief_tag(self):
        """Test handling of comment without @brief tag."""
        cursor = MockCursor("/** Just a regular comment */")
        result = self.parser.extract_brief(cursor)
        self.assertIsNone(result)

    def test_extract_brief_no_comment(self):
        """Test handling of cursor with no comment."""
        cursor = MockCursor(None)
        result = self.parser.extract_brief(cursor)
        self.assertIsNone(result)

    def test_extract_brief_with_other_tags(self):
        """Test extracting brief when other @ tags are present."""
        cursor = MockCursor(
            "/**\n"
            " * @brief Brief description\n"
            " * @param x Parameter\n"
            " * @return Result\n"
            " */"
        )
        result = self.parser.extract_brief(cursor)
        self.assertEqual(result, "Brief description")

    def test_extract_brief_whitespace_normalization(self):
        """Test that whitespace is normalized."""
        cursor = MockCursor(
            "/**\n"
            " * @brief   Multiple   spaces   here\n"
            " */"
        )
        result = self.parser.extract_brief(cursor)
        self.assertEqual(result, "Multiple spaces here")


if __name__ == '__main__':
    unittest.main()
