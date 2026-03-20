"""Unit tests for filter configuration."""

import os
import tempfile
import unittest
from pathlib import Path

from src.filter_config import FilterConfig, FilterConfigLoader, FilterMode


class TestFilterConfig(unittest.TestCase):
    """Test FilterConfig class."""

    def test_normalize_absolute_path(self):
        """Test that absolute paths are normalized correctly."""
        config = FilterConfig(
            mode=FilterMode.SINGLE_PATH,
            paths=['/absolute/path/'],
            project_root='/tmp'
        )
        self.assertEqual(config.normalized_paths, ['/absolute/path'])

    def test_normalize_relative_path(self):
        """Test that relative paths are resolved to project root."""
        config = FilterConfig(
            mode=FilterMode.SINGLE_PATH,
            paths=['src/'],
            project_root='/project/root'
        )
        self.assertEqual(config.normalized_paths, ['/project/root/src'])

    def test_is_in_scope_no_filter(self):
        """Test that all files are in scope when no filter is active."""
        config = FilterConfig(
            mode=FilterMode.AUTO_DETECT,
            paths=[],
            project_root='/project'
        )
        self.assertTrue(config.is_in_scope('/any/file.c', '/project'))
        self.assertTrue(config.is_in_scope('/other/file.cpp', '/project'))

    def test_is_in_scope_absolute_path(self):
        """Test scope checking with absolute filter path."""
        config = FilterConfig(
            mode=FilterMode.SINGLE_PATH,
            paths=['/project/src/'],
            project_root='/project'
        )
        self.assertTrue(config.is_in_scope('/project/src/main.cpp', '/project'))
        self.assertTrue(config.is_in_scope('/project/src/utils/helper.c', '/project'))
        self.assertFalse(config.is_in_scope('/project/test/test.cpp', '/project'))

    def test_is_in_scope_relative_path(self):
        """Test scope checking with relative filter path."""
        config = FilterConfig(
            mode=FilterMode.SINGLE_PATH,
            paths=['src/'],
            project_root='/project'
        )
        self.assertTrue(config.is_in_scope('/project/src/main.cpp', '/project'))
        self.assertTrue(config.is_in_scope('src/main.cpp', '/project'))
        self.assertFalse(config.is_in_scope('/project/test/test.cpp', '/project'))

    def test_is_in_scope_exact_match(self):
        """Test that exact directory matches are included."""
        config = FilterConfig(
            mode=FilterMode.SINGLE_PATH,
            paths=['/project/src'],
            project_root='/project'
        )
        self.assertTrue(config.is_in_scope('/project/src', '/project'))
        self.assertTrue(config.is_in_scope('/project/src/file.c', '/project'))

    def test_is_in_scope_no_partial_match(self):
        """Test that partial directory names don't match."""
        config = FilterConfig(
            mode=FilterMode.SINGLE_PATH,
            paths=['/project/src'],
            project_root='/project'
        )
        self.assertFalse(config.is_in_scope('/project/src2/file.c', '/project'))
        self.assertFalse(config.is_in_scope('/project/mysrc/file.c', '/project'))

    def test_get_scope_summary_auto_detect(self):
        """Test scope summary for auto-detect mode."""
        config = FilterConfig(
            mode=FilterMode.AUTO_DETECT,
            paths=[],
            project_root='/project'
        )
        self.assertEqual(config.get_scope_summary(), "All files (no filter)")

    def test_get_scope_summary_single_path(self):
        """Test scope summary for single path mode."""
        config = FilterConfig(
            mode=FilterMode.SINGLE_PATH,
            paths=['src/'],
            project_root='/project'
        )
        self.assertIn('src/', config.get_scope_summary())

    def test_get_scope_summary_filter_cfg(self):
        """Test scope summary for filter config mode."""
        config = FilterConfig(
            mode=FilterMode.FILTER_CFG,
            paths=['src/', 'include/'],
            config_file='/project/filter.cfg',
            project_root='/project'
        )
        summary = config.get_scope_summary()
        self.assertIn('filter.cfg', summary)
        self.assertIn('2 paths', summary)


class TestFilterConfigLoader(unittest.TestCase):
    """Test FilterConfigLoader class."""

    def test_load_with_filter_cfg(self):
        """Test loading filter configuration from file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.cfg', delete=False) as f:
            f.write('# Filter config\n')
            f.write('src/\n')
            f.write('include/\n')
            f.write('# Comment line\n')
            f.write('\n')  # Empty line
            f.write('tests/\n')
            config_path = f.name

        try:
            loader = FilterConfigLoader(project_root='/project')
            config = loader.load(filter_cfg_path=config_path)

            self.assertEqual(config.mode, FilterMode.FILTER_CFG)
            self.assertEqual(len(config.paths), 3)  # src/, include/, tests/
            self.assertEqual(config.config_file, config_path)
        finally:
            os.unlink(config_path)

    def test_load_with_single_path(self):
        """Test loading filter configuration with single path."""
        loader = FilterConfigLoader(project_root='/project')
        config = loader.load(single_path='src/')

        self.assertEqual(config.mode, FilterMode.SINGLE_PATH)
        self.assertEqual(len(config.paths), 1)
        self.assertEqual(config.paths[0], 'src/')

    def test_load_auto_detect(self):
        """Test auto-detect mode (no filter)."""
        loader = FilterConfigLoader(project_root='/project')
        config = loader.load()

        self.assertEqual(config.mode, FilterMode.AUTO_DETECT)
        self.assertEqual(len(config.paths), 0)

    def test_load_with_empty_filter_cfg(self):
        """Test loading empty filter config file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.cfg', delete=False) as f:
            f.write('# Only comments\n')
            f.write('\n')
            config_path = f.name

        try:
            loader = FilterConfigLoader(project_root='/project')
            config = loader.load(filter_cfg_path=config_path)

            self.assertEqual(config.mode, FilterMode.FILTER_CFG)
            self.assertEqual(len(config.paths), 0)
        finally:
            os.unlink(config_path)

    def test_validate_paths_warning(self):
        """Test that validate_paths warns about non-existent paths."""
        loader = FilterConfigLoader(project_root='/project')
        config = FilterConfig(
            mode=FilterMode.SINGLE_PATH,
            paths=['/nonexistent/path/'],
            project_root='/project'
        )

        # validate_paths should not raise an error, just log warnings
        result = loader.validate_paths(config)
        self.assertTrue(result)  # Always returns True (warning-only)

    def test_load_nonexistent_filter_cfg(self):
        """Test loading non-existent filter config file."""
        loader = FilterConfigLoader(project_root='/project')

        with self.assertRaises(FileNotFoundError):
            loader.load(filter_cfg_path='/nonexistent/filter.cfg')


if __name__ == '__main__':
    unittest.main()
