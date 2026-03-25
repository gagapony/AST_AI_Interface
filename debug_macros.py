import sys
sys.path.insert(0, 'src')
from ast_parser import ASTParser
from feature_analyzer import FeatureAnalyzer
import logging

logging.basicConfig(level=logging.DEBUG)

# Parse test_macros.cpp
parser = ASTParser(['-c', '-std=c++17', '/home/gabriel/.openclaw/code/clang-call-analyzer/test_macros.cpp'])
tu = parser.parse_file('/home/gabriel/.openclaw/code/clang-call-analyzer/test_macros.cpp')

if tu:
    print(f"Parsed successfully")
    print(f"Translation unit: {tu}")
    
    # Check all cursors
    print("\n=== All top-level cursors ===")
    for cursor in tu.cursor.get_children():
        print(f"Kind: {cursor.kind}, Spelling: {cursor.spelling}")
        if hasattr(cursor, 'location') and cursor.location:
            print(f"  Location: {cursor.location.file}:{cursor.location.line}")
    
    # Try FeatureAnalyzer
    analyzer = FeatureAnalyzer(tu, None)
    macros = analyzer.extract_macros()
    print(f"\n=== Extracted {len(macros)} macros ===")
    for macro in macros:
        print(f"  {macro.name}: {macro.parameters}")
else:
    print("Failed to parse")
