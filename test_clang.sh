#!/usr/bin/env bash
set -e

echo "Testing if clang command works..."

# Test clang command
if command -v clang >/dev/null 2>&1; then
    echo "✓ clang command available"
    echo "  Version: $(clang --version)"
else
    echo "✗ clang command not found"
    exit 1
fi

# Try to dump AST
echo "Testing AST dump..."
echo 'int main() { return 0; }' | clang -Xclang -ast-dump=-fsyntax-only - 2>&1 | head -20

if [ $? -eq 0 ]; then
    echo "✓ clang AST dump works!"
else
    echo "✗ clang AST dump failed (exit code: $?)"
    exit 1
fi
