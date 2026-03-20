#!/usr/bin/env python3
"""Phase 1 unit tests for filter configuration."""

import sys
import os
from pathlib import Path

# Add parent directory to path for importing from src
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.filter_config import FilterConfigLoader, FilterConfig, FilterMode
from src.compilation_db_filter import CompilationDatabaseFilter, FilterStats


def test_filter_mode():
    """Test FilterMode enum values."""
    print("Testing FilterMode enum...")
    assert FilterMode.FILTER_CFG.value == 1
    assert FilterMode.SINGLE_PATH.value == 2
    assert FilterMode.AUTO_DETECT.value == 3
    print("  ✅ FilterMode enum values correct")


def test_filter_config_auto_detect():
    """Test FilterConfig in AUTO_DETECT mode."""
    print("Testing FilterConfig AUTO_DETECT mode...")
    config = FilterConfig(
        mode=FilterMode.AUTO_DETECT,
        paths=[],
        config_file=None
    )
    assert config.mode == FilterMode.AUTO_DETECT
    assert len(config.paths) == 0
    assert config.is_in_scope('/any/file/path') is True  # Always true in AUTO_DETECT mode
    print("  ✅ AUTO_DETECT mode works correctly")


def test_filter_config_single_path():
    """Test FilterConfig in SINGLE_PATH mode."""
    print("Testing FilterConfig SINGLE_PATH mode...")
    # Use absolute path for testing
    test_path = os.path.abspath('src/')

    config = FilterConfig(
        mode=FilterMode.SINGLE_PATH,
        paths=[test_path],
        config_file=None
    )
    assert config.mode == FilterMode.SINGLE_PATH
    assert len(config.paths) == 1
    assert test_path in config.paths

    # Test scope matching with absolute paths
    assert config.is_in_scope(os.path.join(test_path, 'main.cpp')) is True
    assert config.is_in_scope('/tmp/lib/util.c') is False
    assert config.is_in_scope(os.path.join(test_path, 'include', 'helper.h')) is True
    print("  ✅ SINGLE_PATH mode and scope matching work correctly")


def test_filter_config_filter_cfg():
    """Test FilterConfig in FILTER_CFG mode."""
    print("Testing FilterConfig FILTER_CFG mode...")
    # Use absolute paths for testing
    test_dir = os.path.dirname(os.path.abspath(__file__))
    paths = [
        os.path.join(test_dir, 'src'),
        os.path.join(test_dir, 'include'),
        os.path.join(test_dir, 'tests')
    ]

    config = FilterConfig(
        mode=FilterMode.FILTER_CFG,
        paths=paths,
        config_file='test.cfg'
    )
    assert config.mode == FilterMode.FILTER_CFG
    assert len(config.paths) == 3

    # Test scope matching with absolute paths
    assert config.is_in_scope(os.path.join(test_dir, 'src', 'main.cpp')) is True
    assert config.is_in_scope(os.path.join(test_dir, 'include', 'api.h')) is True
    assert config.is_in_scope(os.path.join(test_dir, 'tests', 'test.cpp')) is True
    assert config.is_in_scope(os.path.join(test_dir, 'lib', 'util.c')) is False
    print("  ✅ FILTER_CFG mode and scope matching work correctly")


def test_filter_config_loader_auto_detect():
    """Test FilterConfigLoader with auto-detect mode."""
    print("Testing FilterConfigLoader auto-detect...")
    loader = FilterConfigLoader()
    config = loader.load(filter_cfg_path=None, single_path=None)

    assert config.mode == FilterMode.AUTO_DETECT
    assert len(config.paths) == 0
    print("  ✅ Auto-detect mode works correctly")


def test_filter_config_loader_single_path():
    """Test FilterConfigLoader with single path."""
    print("Testing FilterConfigLoader single path...")
    loader = FilterConfigLoader()
    config = loader.load(filter_cfg_path=None, single_path='src/')

    assert config.mode == FilterMode.SINGLE_PATH
    assert len(config.paths) == 1
    assert 'src/' in config.paths
    print("  ✅ Single path loading works correctly")


def test_filter_config_loader_from_cfg():
    """Test FilterConfigLoader from config file."""
    print("Testing FilterConfigLoader from config file...")
    loader = FilterConfigLoader()
    config_path = Path(__file__).parent / 'test_filter.cfg'

    if not config_path.exists():
        print(f"  ⚠️  Config file not found: {config_path}")
        return

    config = loader._load_from_cfg(str(config_path))

    assert config.mode == FilterMode.FILTER_CFG
    assert config.config_file == str(config_path)
    assert len(config.paths) >= 3  # Should have at least src/, include/, tests/
    print(f"  ✅ Config file loading works correctly (loaded {len(config.paths)} paths)")


def test_filter_config_loader_priority():
    """Test FilterConfigLoader priority logic."""
    print("Testing FilterConfigLoader priority logic...")
    loader = FilterConfigLoader()

    # Priority 1: filter_cfg > single_path
    # Use existing test config file
    config_path = Path(__file__).parent / 'test_filter.cfg'
    if config_path.exists():
        config = loader.load(filter_cfg_path=str(config_path), single_path='src/')
        assert config.mode == FilterMode.FILTER_CFG

    # Priority 2: single_path
    config = loader.load(filter_cfg_path=None, single_path='src/')
    assert config.mode == FilterMode.SINGLE_PATH

    # Priority 3: auto-detect
    config = loader.load(filter_cfg_path=None, single_path=None)
    assert config.mode == FilterMode.AUTO_DETECT
    print("  ✅ Priority logic works correctly")


def test_compilation_db_filter():
    """Test CompilationDatabaseFilter."""
    print("Testing CompilationDatabaseFilter...")

    # Use a temp directory structure for testing
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        src_dir = os.path.join(tmpdir, 'src')
        lib_dir = os.path.join(tmpdir, 'lib')
        os.makedirs(src_dir)
        os.makedirs(lib_dir)

        config = FilterConfig(
            mode=FilterMode.SINGLE_PATH,
            paths=[src_dir],
            config_file=None
        )

        db_filter = CompilationDatabaseFilter(filter_config=config, project_root=tmpdir)

        compile_commands = [
            {'file': os.path.join(src_dir, 'main.cpp'), 'command': 'gcc -c main.cpp', 'directory': tmpdir},
            {'file': os.path.join(src_dir, 'helper.cpp'), 'command': 'gcc -c helper.cpp', 'directory': tmpdir},
            {'file': os.path.join(lib_dir, 'util.c'), 'command': 'gcc -c util.c', 'directory': tmpdir},
        ]

        filtered_units = db_filter.filter_compilation_db(compile_commands)

        assert len(filtered_units) == 2, f"Expected 2 filtered units, got {len(filtered_units)}"
        assert filtered_units[0].file == os.path.join(src_dir, 'main.cpp')
        assert filtered_units[1].file == os.path.join(src_dir, 'helper.cpp')

        stats = db_filter.get_stats()
        assert stats.total_units == 3
        assert stats.kept_units == 2
        assert stats.filtered_units == 1

        summary = db_filter.get_summary()
        assert '2 kept' in summary
        assert '1 filtered' in summary
        print("  ✅ Compilation database filtering works correctly")


def test_compilation_db_filter_dump():
    """Test CompilationDatabaseFilter dump functionality."""
    print("Testing CompilationDatabaseFilter dump...")

    # Use a temp directory structure for testing
    import tempfile
    import json

    with tempfile.TemporaryDirectory() as tmpdir:
        src_dir = os.path.join(tmpdir, 'src')
        lib_dir = os.path.join(tmpdir, 'lib')
        os.makedirs(src_dir)
        os.makedirs(lib_dir)

        config = FilterConfig(
            mode=FilterMode.SINGLE_PATH,
            paths=[src_dir],
            config_file=None
        )

        db_filter = CompilationDatabaseFilter(filter_config=config)

        compile_commands = [
            {'file': os.path.join(src_dir, 'main.cpp'), 'command': 'gcc -c main.cpp', 'directory': tmpdir},
            {'file': os.path.join(lib_dir, 'util.c'), 'command': 'gcc -c util.c', 'directory': tmpdir},
        ]

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            output_path = f.name

        try:
            db_filter.dump_filtered_db(compile_commands, output_path)

            # Verify output
            with open(output_path, 'r') as f:
                output_data = json.load(f)

            assert len(output_data) == 1  # Only src/main.cpp should be kept
            assert output_data[0]['file'] == os.path.join(src_dir, 'main.cpp')
            print("  ✅ Dump filtered DB works correctly")
        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)


def test_filter_config_relative_paths():
    """Test FilterConfig with relative paths."""
    print("Testing FilterConfig with relative paths...")

    # Save current directory
    cwd = os.getcwd()

    # Use a temp directory to test relative paths
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            # Change to temp directory
            os.chdir(tmpdir)

            # Create test directories
            os.makedirs('src')
            os.makedirs('lib')

            config = FilterConfig(
                mode=FilterMode.FILTER_CFG,
                paths=['src/', 'lib/'],
                config_file=None
            )

            # Check that paths are normalized
            assert len(config.normalized_paths) == 2
            # All paths should be absolute after normalization
            for path in config.normalized_paths:
                assert os.path.isabs(path)

            # Test relative path matching - provide project_root for relative file paths
            assert config.is_in_scope('src/main.cpp', tmpdir) is True
            assert config.is_in_scope('src/subdir/helper.c', tmpdir) is True
            assert config.is_in_scope('lib/util.c', tmpdir) is True
            assert config.is_in_scope('tests/test.cpp', tmpdir) is False

            # Test absolute path matching
            abs_src_file = os.path.join(tmpdir, 'src', 'main.cpp')
            assert config.is_in_scope(abs_src_file) is True

            abs_lib_file = os.path.join(tmpdir, 'lib', 'util.c')
            assert config.is_in_scope(abs_lib_file) is True

            abs_test_file = os.path.join(tmpdir, 'tests', 'test.cpp')
            assert config.is_in_scope(abs_test_file) is False

            print("  ✅ Relative path handling works correctly")
        finally:
            # Restore original directory
            os.chdir(cwd)


def run_all_tests():
    """Run all Phase 1 tests."""
    print("=" * 60)
    print("Phase 1 Unit Tests for Filter Configuration")
    print("=" * 60)

    tests = [
        test_filter_mode,
        test_filter_config_auto_detect,
        test_filter_config_single_path,
        test_filter_config_filter_cfg,
        test_filter_config_loader_auto_detect,
        test_filter_config_loader_single_path,
        test_filter_config_loader_from_cfg,
        test_filter_config_loader_priority,
        test_compilation_db_filter,
        test_compilation_db_filter_dump,
        test_filter_config_relative_paths,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"  ❌ FAILED: {e}")
            failed += 1
        except Exception as e:
            print(f"  ❌ ERROR: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
        print()

    print("=" * 60)
    print(f"Test Results: {passed} passed, {failed} failed")
    print("=" * 60)

    return 0 if failed == 0 else 1


if __name__ == '__main__':
    sys.exit(run_all_tests())
