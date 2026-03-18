"""Unit tests for function_registry module."""

import unittest

from src.function_registry import FunctionRegistry
from src.function_extractor import FunctionInfo


class MockCursor:
    """Mock cursor for testing."""

    def __init__(self):
        pass


class TestFunctionRegistry(unittest.TestCase):
    """Test cases for FunctionRegistry class."""

    def setUp(self):
        """Set up test fixtures."""
        self.registry = FunctionRegistry()

    def test_add_function(self):
        """Test adding a function to the registry."""
        func = FunctionInfo(
            path="test.cpp",
            line_range=(1, 10),
            name="foo",
            qualified_name="foo()",
            brief="Test function",
            raw_cursor=MockCursor()
        )

        index = self.registry.add_function(func)
        self.assertEqual(index, 0)
        self.assertEqual(self.registry.count(), 1)

    def test_get_by_index(self):
        """Test retrieving function by index."""
        func = FunctionInfo(
            path="test.cpp",
            line_range=(1, 10),
            name="foo",
            qualified_name="foo()",
            brief="Test function",
            raw_cursor=MockCursor()
        )

        self.registry.add_function(func)
        retrieved = self.registry.get_by_index(0)

        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.name, "foo")
        self.assertEqual(retrieved.qualified_name, "foo()")

    def test_get_by_index_invalid(self):
        """Test retrieving with invalid index."""
        result = self.registry.get_by_index(999)
        self.assertIsNone(result)

    def test_get_by_qualified_name(self):
        """Test retrieving functions by qualified name."""
        func1 = FunctionInfo(
            path="test.cpp",
            line_range=(1, 10),
            name="foo",
            qualified_name="foo(int)",
            brief="Test function 1",
            raw_cursor=MockCursor()
        )

        func2 = FunctionInfo(
            path="test.cpp",
            line_range=(11, 20),
            name="foo",
            qualified_name="foo(double)",
            brief="Test function 2",
            raw_cursor=MockCursor()
        )

        self.registry.add_function(func1)
        self.registry.add_function(func2)

        indices = self.registry.get_by_qualified_name("foo(int)")
        self.assertEqual(len(indices), 1)
        self.assertEqual(indices[0], 0)

        indices = self.registry.get_by_qualified_name("foo(double)")
        self.assertEqual(len(indices), 1)
        self.assertEqual(indices[0], 1)

    def test_get_by_qualified_name_not_found(self):
        """Test retrieving non-existent qualified name."""
        indices = self.registry.get_by_qualified_name("nonexistent()")
        self.assertEqual(len(indices), 0)

    def test_get_all(self):
        """Test retrieving all functions."""
        func1 = FunctionInfo(
            path="test1.cpp",
            line_range=(1, 10),
            name="foo",
            qualified_name="foo()",
            brief="Test function 1",
            raw_cursor=MockCursor()
        )

        func2 = FunctionInfo(
            path="test2.cpp",
            line_range=(1, 10),
            name="bar",
            qualified_name="bar()",
            brief="Test function 2",
            raw_cursor=MockCursor()
        )

        self.registry.add_function(func1)
        self.registry.add_function(func2)

        all_funcs = self.registry.get_all()
        self.assertEqual(len(all_funcs), 2)
        self.assertEqual(all_funcs[0].name, "foo")
        self.assertEqual(all_funcs[1].name, "bar")

    def test_count(self):
        """Test counting functions."""
        self.assertEqual(self.registry.count(), 0)

        self.registry.add_function(FunctionInfo(
            path="test.cpp",
            line_range=(1, 10),
            name="foo",
            qualified_name="foo()",
            brief="Test",
            raw_cursor=MockCursor()
        ))

        self.assertEqual(self.registry.count(), 1)

        self.registry.add_function(FunctionInfo(
            path="test.cpp",
            line_range=(11, 20),
            name="bar",
            qualified_name="bar()",
            brief="Test",
            raw_cursor=MockCursor()
        ))

        self.assertEqual(self.registry.count(), 2)

    def test_multiple_overloads(self):
        """Test handling multiple overloaded functions."""
        func1 = FunctionInfo(
            path="test.cpp",
            line_range=(1, 10),
            name="foo",
            qualified_name="foo(int)",
            brief="Int version",
            raw_cursor=MockCursor()
        )

        func2 = FunctionInfo(
            path="test.cpp",
            line_range=(11, 20),
            name="foo",
            qualified_name="foo(double)",
            brief="Double version",
            raw_cursor=MockCursor()
        )

        func3 = FunctionInfo(
            path="test.cpp",
            line_range=(21, 30),
            name="foo",
            qualified_name="foo(const char*)",
            brief="String version",
            raw_cursor=MockCursor()
        )

        self.registry.add_function(func1)
        self.registry.add_function(func2)
        self.registry.add_function(func3)

        # Should get all three indices for foo name with different params
        indices_int = self.registry.get_by_qualified_name("foo(int)")
        self.assertEqual(len(indices_int), 1)
        self.assertEqual(indices_int[0], 0)

        indices_double = self.registry.get_by_qualified_name("foo(double)")
        self.assertEqual(len(indices_double), 1)
        self.assertEqual(indices_double[0], 1)

        indices_str = self.registry.get_by_qualified_name("foo(const char*)")
        self.assertEqual(len(indices_str), 1)
        self.assertEqual(indices_str[0], 2)


if __name__ == '__main__':
    unittest.main()
