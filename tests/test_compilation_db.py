"""Unit tests for compilation_db module."""

import json
import os
import tempfile
import unittest

from src.compilation_db import CompilationDatabase, CompilationUnit


class TestCompilationDatabase(unittest.TestCase):
    """Test cases for CompilationDatabase class."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, 'compile_commands.json')

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir)

    def test_load_valid_database(self):
        """Test loading a valid compile_commands.json."""
        test_data = [
            {
                "directory": "/test/dir",
                "command": "/usr/bin/c++ -I/test/include -std=c++17 -c test.cpp",
                "file": "test.cpp"
            }
        ]

        with open(self.db_path, 'w') as f:
            json.dump(test_data, f)

        db = CompilationDatabase(self.db_path)
        db.load()

        units = db.get_units()
        self.assertEqual(len(units), 1)

        unit = units[0]
        self.assertEqual(unit.directory, "/test/dir")
        self.assertEqual(unit.file, "test.cpp")
        self.assertIn("-I/test/include", unit.flags)
        self.assertIn("-std=c++17", unit.flags)

    def test_flag_extraction(self):
        """Test extraction of clang-compatible flags."""
        test_data = [
            {
                "directory": "/test",
                "command": "/usr/bin/c++ -O2 -g -Wall -I/include1 -DDEBUG -std=c++17 test.cpp -o test",
                "file": "test.cpp"
            }
        ]

        with open(self.db_path, 'w') as f:
            json.dump(test_data, f)

        db = CompilationDatabase(self.db_path)
        db.load()

        unit = db.get_units()[0]
        self.assertIn("-I/include1", unit.flags)
        self.assertIn("-DDEBUG", unit.flags)
        self.assertIn("-std=c++17", unit.flags)

        # Check that optimization, debug, and warning flags are excluded
        self.assertNotIn("-O2", unit.flags)
        self.assertNotIn("-g", unit.flags)
        self.assertNotIn("-Wall", unit.flags)
        self.assertNotIn("-o", unit.flags)

    def test_include_path_resolution(self):
        """Test that relative include paths are resolved correctly."""
        test_data = [
            {
                "directory": "/base/dir",
                "command": "/usr/bin/c++ -Iinclude -std=c++17 test.cpp",
                "file": "test.cpp"
            }
        ]

        with open(self.db_path, 'w') as f:
            json.dump(test_data, f)

        db = CompilationDatabase(self.db_path)
        db.load()

        unit = db.get_units()[0]
        # Check that relative path is resolved
        self.assertTrue(any("-I" in flag and "/base/dir" in flag for flag in unit.flags))

    def test_get_flags_for_file(self):
        """Test retrieving flags for a specific file."""
        test_data = [
            {
                "directory": "/test",
                "command": "/usr/bin/c++ -I/include -std=c++17 test1.cpp",
                "file": "test1.cpp"
            },
            {
                "directory": "/test",
                "command": "/usr/bin/c++ -I/include2 -std=c++20 test2.cpp",
                "file": "test2.cpp"
            }
        ]

        with open(self.db_path, 'w') as f:
            json.dump(test_data, f)

        db = CompilationDatabase(self.db_path)
        db.load()

        flags1 = db.get_flags_for_file("test1.cpp")
        self.assertIn("-I/include", flags1)

        flags2 = db.get_flags_for_file("test2.cpp")
        self.assertIn("-I/include2", flags2)
        self.assertIn("-std=c++20", flags2)

    def test_missing_database(self):
        """Test handling of missing database file."""
        db = CompilationDatabase("/nonexistent/path")
        with self.assertRaises(FileNotFoundError):
            db.load()


if __name__ == '__main__':
    unittest.main()
