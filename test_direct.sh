#!/usr/bin/env bash
# Direct test script for clang-call-analyzer
# This bypasses module import issues by using proper path setup

cd /home/gabriel/.openclaw/code/clang-call-analyzer

echo "Testing clang-call-analyzer with smart-drying-module data..."
echo ""

echo "Step 1: Using compile_commands.json from smart-drying-module"
echo "  Path: /home/gabriel/projects/smart-drying-module/compile_commands.json"
echo ""

echo "Step 2: Using filter.cfg from smart-drying-module"
echo "  Path: /home/gabriel/projects/smart-drying-module/filter.cfg"
echo ""

echo "Step 3: Running clang-call-analyzer directly (bypassing module issues)"
echo "  Command: python src.cli"
echo "    -i /home/gabriel/projects/smart-drying-module/compile_commands.json"
echo "    -f /home/gabriel/projects/smart-drying-module/filter.cfg"
echo "    -o /tmp/filegraph.json"
echo "    --format html"
echo "    -v info"
echo ""

echo "Executing..."
python src/cli \
    -i /home/gabriel/projects/smart-drying-module/compile_commands.json \
    -f /home/gabriel/projects/smart-drying-module/filter.cfg \
    -o /tmp/filegraph.json \
    --format html \
    -v info

echo ""
echo "Done! Check output files:"
ls -lh /tmp/filegraph* 2>/dev/null || echo "No output files found"
EOF
chmod +x /home/gabriel/.openclaw/code/clang-call-analyzer/test_direct.sh
