#!/usr/bin/env python3
"""
Final comprehensive test for ECharts HTML generator fix.

This test verifies that the template fix resolves the formatting issues:
- Placeholders are correctly replaced
- JavaScript syntax is valid
- No malformed braces (triple/quad)
- ECharts functionality preserved
"""

import json
import sys
from string import Template

sys.path.insert(0, 'src')

from echarts_templates import HTML_TEMPLATE, CSS_TEMPLATE, APP_SCRIPT_TEMPLATE


def run_tests():
    """Run all tests."""
    print("\n" + "="*70)
    print("ECHARTS HTML GENERATOR - FINAL COMPREHENSIVE TEST")
    print("="*70)

    html = None

    # Test 1
    if not test_template_syntax():
        return False

    # Test 2 - returns html for subsequent tests
    html = test_substitution()
    if not html:
        return False

    # Tests 3-5 use html from test 2
    tests = [
        (test_javascript_syntax, "JavaScript syntax"),
        (test_echarts_preserved, "ECharts features"),
        (test_complete_html, "Complete HTML"),
    ]

    passed = 2  # tests 1 and 2 already passed
    failed = 0

    for test, name in tests:
        try:
            if test(html):
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"\n❌ Test {name} raised exception: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print("\n" + "="*70)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("="*70)

    if failed == 0:
        print("\n✅ ALL TESTS PASSED! The fix is working correctly.")
        print("\n📄 Generated file: test_output.html")
        print("   Open this file in your browser to verify the ECharts graph.")
        return True
    else:
        print(f"\n❌ {failed} test(s) failed. Please review the output above.")
        return False


def test_template_syntax():
    """Test 1: Template uses correct placeholder syntax."""
    print("\n[1] Testing template placeholder syntax...")

    success = True

    if '$css' in HTML_TEMPLATE:
        print("   ✅ HTML_TEMPLATE uses $css placeholder")
    else:
        print("   ❌ HTML_TEMPLATE missing $css placeholder")
        success = False

    if '$data' in HTML_TEMPLATE:
        print("   ✅ HTML_TEMPLATE uses $data placeholder")
    else:
        print("   ❌ HTML_TEMPLATE missing $data placeholder")
        success = False

    if '$app_script' in HTML_TEMPLATE:
        print("   ✅ HTML_TEMPLATE uses $app_script placeholder")
    else:
        print("   ❌ HTML_TEMPLATE missing $app_script placeholder")
        success = False

    if '{{' not in APP_SCRIPT_TEMPLATE:
        print("   ✅ APP_SCRIPT_TEMPLATE has no double braces")
    else:
        print(f"   ❌ APP_SCRIPT_TEMPLATE has {APP_SCRIPT_TEMPLATE.count('{{')} double braces")
        success = False

    return success


def test_substitution():
    """Test 2: Template substitution works."""
    print("\n[2] Testing template substitution...")

    test_data = {
        "nodes": [{"id": 0, "name": "test", "category": "Default"}],
        "edges": [],
        "categories": [{"name": "Default", "itemStyle": {"color": "#7f7f7f"}}]
    }
    data_json = json.dumps(test_data, ensure_ascii=False, indent=2)

    try:
        template = Template(HTML_TEMPLATE)
        html = template.substitute(
            css=CSS_TEMPLATE,
            data=data_json,
            app_script=APP_SCRIPT_TEMPLATE
        )
        print("   ✅ Template substitution succeeded")
        return html
    except KeyError as e:
        print(f"   ❌ KeyError: {e}")
        return None
    except Exception as e:
        print(f"   ❌ Error: {type(e).__name__}: {e}")
        return None


def test_javascript_syntax(html):
    """Test 3: JavaScript syntax is correct."""
    print("\n[3] Testing JavaScript syntax...")

    if not html:
        print("   ❌ No HTML to test")
        return False

    success = True

    # Check for malformed braces
    triple_count = html.count('{{{')
    quad_count = html.count('{{{{')

    if triple_count == 0:
        print(f"   ✅ No triple braces")
    else:
        print(f"   ❌ Found {triple_count} triple braces")
        success = False

    if quad_count == 0:
        print(f"   ✅ No quad braces")
    else:
        print(f"   ❌ Found {quad_count} quad braces")
        success = False

    # Check function syntax
    if 'function initGraph() {' in html:
        print("   ✅ Function syntax correct")
    else:
        print("   ❌ Function syntax incorrect")
        success = False

    # Check object syntax
    if 'const option = {' in html:
        print("   ✅ Object syntax correct")
    else:
        print("   ❌ Object syntax incorrect")
        success = False

    return success


def test_echarts_preserved(html):
    """Test 4: ECharts features are preserved."""
    print("\n[4] Testing ECharts features...")

    if not html:
        print("   ❌ No HTML to test")
        return False

    success = True

    features = [
        ('echarts.init', 'ECharts initialization'),
        ('chart.setOption', 'Chart configuration'),
        ('tooltipFormatter', 'Tooltip function'),
        ('handleSearch', 'Search handler'),
        ('handleGroupChange', 'Group mode handler'),
        ('handleExportPNG', 'PNG export'),
        ('handleExportSVG', 'SVG export'),
    ]

    for feature, desc in features:
        if feature in html:
            print(f"   ✅ {desc} present")
        else:
            print(f"   ❌ {desc} missing")
            success = False

    # Check ES6 template strings
    if '${data.name}' in html or '${' in html:
        print("   ✅ ES6 template strings preserved")
    else:
        print("   ⚠️  Warning: ES6 template strings not found")

    return success


def test_complete_html(html):
    """Test 5: Complete HTML structure and file output."""
    print("\n[5] Testing complete HTML and file output...")

    if not html:
        print("   ❌ No HTML to test")
        return False

    success = True

    # Check HTML structure
    if '<!DOCTYPE html>' in html and '</html>' in html:
        print("   ✅ HTML5 structure valid")
    else:
        print("   ❌ HTML structure invalid")
        success = False

    # Check all placeholders replaced
    if '$css' not in html and '$data' not in html and '$app_script' not in html:
        print("   ✅ All placeholders replaced")
    else:
        print("   ❌ Some placeholders not replaced")
        success = False

    # Check embedded data
    if 'const GRAPH_DATA = {' in html and '"nodes"' in html:
        print("   ✅ Graph data embedded correctly")
    else:
        print("   ❌ Graph data not embedded")
        success = False

    # Write to file
    output_file = 'test_output.html'
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html)
        size_kb = len(html) / 1024
        print(f"   ✅ Written to {output_file} ({size_kb:.1f} KB)")
    except Exception as e:
        print(f"   ❌ Failed to write file: {e}")
        success = False

    return success


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
