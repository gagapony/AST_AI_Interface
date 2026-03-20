#!/usr/bin/env python3
"""Test filter paths logic (without clang dependency)."""

import os
from pathlib import Path


def is_in_scope(file_path: str, filter_paths):
    """
    Check if a file path is within the filter scope.
    This is the same logic as in FunctionExtractor._is_in_scope().
    """
    # If no filter paths specified, analyze everything
    if not filter_paths:
        return True

    # Normalize file path
    file_path = os.path.normpath(file_path)

    # Check each filter path
    for filter_path in filter_paths:
        # Convert filter_path to string and normalize
        norm_filter = os.path.normpath(str(filter_path))

        # Ensure filter path ends with os.sep for directory matching
        # This ensures 'src' matches 'src/file' but not 'src2/file'
        filter_with_sep = norm_filter if norm_filter.endswith(os.sep) else norm_filter + os.sep

        # Check if file_path is exactly the filter path (the filter path itself)
        if file_path == norm_filter:
            return True

        # Check if file_path starts with filter_path (with separator)
        if file_path.startswith(filter_with_sep):
            return True

    return False


def test_is_in_scope():
    """Test the filter paths logic."""
    # Test 1: No filter paths (should return True for all files)
    print("Test 1: No filter paths")
    assert is_in_scope("src/main.cpp", None) is True
    assert is_in_scope("/absolute/path/lib/util.c", None) is True
    assert is_in_scope("any/file.txt", None) is True
    print("  ✓ All files pass when no filter specified")

    # Test 2: Single filter path (relative)
    print("\nTest 2: Single filter path (relative)")
    filter_paths = [Path("src")]
    assert is_in_scope("src/main.cpp", filter_paths) is True
    assert is_in_scope("src/include/helper.h", filter_paths) is True
    assert is_in_scope("src", filter_paths) is True
    assert is_in_scope("src/", filter_paths) is True
    assert is_in_scope("src/./main.cpp", filter_paths) is True
    assert is_in_scope("lib/util.c", filter_paths) is False
    assert is_in_scope("src2/main.cpp", filter_paths) is False
    print("  ✓ Correctly filters by relative path")

    # Test 3: Multiple filter paths
    print("\nTest 3: Multiple filter paths")
    filter_paths = [Path("src"), Path("include")]
    assert is_in_scope("src/main.cpp", filter_paths) is True
    assert is_in_scope("src/subdir/helper.cpp", filter_paths) is True
    assert is_in_scope("include/api.h", filter_paths) is True
    assert is_in_scope("include/sub/inner.h", filter_paths) is True
    assert is_in_scope("lib/util.c", filter_paths) is False
    assert is_in_scope("tests/test.cpp", filter_paths) is False
    print("  ✓ Correctly filters by multiple paths")

    # Test 4: Absolute filter paths
    print("\nTest 4: Absolute filter paths")
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        abs_path = os.path.abspath(tmpdir)
        filter_paths = [Path(abs_path)]
        assert is_in_scope(abs_path + "/main.cpp", filter_paths) is True
        assert is_in_scope(abs_path + "/subdir/helper.h", filter_paths) is True
        assert is_in_scope("/other/path/file.cpp", filter_paths) is False
    print("  ✓ Correctly filters by absolute paths")

    # Test 5: Path with trailing slash
    print("\nTest 5: Path with trailing slash")
    filter_paths = [Path("src/")]
    assert is_in_scope("src/main.cpp", filter_paths) is True
    assert is_in_scope("src/include/helper.h", filter_paths) is True
    assert is_in_scope("lib/util.c", filter_paths) is False
    print("  ✓ Trailing slash handled correctly")

    # Test 6: Path normalization
    print("\nTest 6: Path normalization")
    filter_paths = [Path("src/./include")]
    assert is_in_scope("src/include/helper.h", filter_paths) is True
    assert is_in_scope("src/include/sub/file.h", filter_paths) is True
    assert is_in_scope("src/lib/util.c", filter_paths) is False
    print("  ✓ Path normalization works correctly")

    # Test 7: Edge cases
    print("\nTest 7: Edge cases")
    filter_paths = [Path("src")]
    # Empty string should not match
    assert is_in_scope("", filter_paths) is False
    # Exact match should work
    assert is_in_scope("src", filter_paths) is True
    # Ensure 'src2' doesn't match 'src'
    assert is_in_scope("src2/main.cpp", filter_paths) is False
    print("  ✓ Edge cases handled correctly")

    print("\n✅ All tests passed!")


if __name__ == "__main__":
    test_is_in_scope()
