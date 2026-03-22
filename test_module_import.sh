#!/usr/bin/env bash
# Test in correct directory

echo "Testing module import from correct directory..."
cd /home/gabriel/.openclaw/code/clang-call-analyzer

python -c "
import sys
import os

# Add correct directory to path
sys.path.insert(0, os.getcwd())

# Try to import
try:
    from src.cli import main
    print('SUCCESS: src.cli module imported successfully')
    sys.exit(0)
except Exception as e:
    print(f'ERROR: {e}')
    sys.exit(1)
"
