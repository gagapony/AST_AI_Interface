#!/usr/bin/env bash
# Simple flow test - bypasses module import issues

cd /home/gabriel/.openclaw/code/clang-call-analyzer

echo "=== Simple Flow Test ==="
echo ""

echo "Test 1: Check if Python module system works"
echo ""

# Try to import main CLI module directly
python -c "
import sys
import os

# Add current directory to path
sys.path.insert(0, os.getcwd())

# Try to import and print result
try:
    from src.cli import main
    print('SUCCESS: src.cli module imported successfully')
    print(f'Available functions: {[f for f in dir(main) if not f.startswith(\"_\")]}')
    exit(0)
except Exception as e:
    print(f'ERROR: {e}')
    exit(1)
"

if [ $? -eq 0 ]; then
    echo "✅ Test 1 PASSED"
else
    echo "❌ Test 1 FAILED"
fi

echo ""
echo "Test 2: Check if core modules can be imported"
echo ""

python -c "
from compilation_db import CompilationDatabase
from ast_parser import ASTParser
from function_extractor import FunctionExtractor
from function_registry import FunctionRegistry
from call_analyzer import CallAnalyzer
from relationship_builder import RelationshipBuilder
from json_emitter import JSONEmitter

print('SUCCESS: All core modules imported')
exit(0)
"

if [ $? -eq 0 ]; then
    echo "✅ Test 2 PASSED"
else
    echo "❌ Test 2 FAILED"
fi
EOF
chmod +x /home/gabriel/.openclaw/code/clang-call-analyzer/test_simple_flow.sh
