#!/usr/bin/env python3
"""Test script to verify template replacement fix."""

import json
import sys
sys.path.insert(0, 'src')

from echarts_templates import HTML_TEMPLATE, CSS_TEMPLATE, APP_SCRIPT_TEMPLATE


def test_template_replacement():
    """Test that placeholder replacement works correctly."""
    print("Testing template replacement...")

    # Prepare test data
    test_data = {
        "nodes": [{"id": 0, "name": "test", "category": "Default"}],
        "edges": [],
        "categories": [{"name": "Default", "itemStyle": {"color": "#7f7f7f"}}]
    }
    data_json = json.dumps(test_data, ensure_ascii=False, indent=2)

    print(f"\n1. Checking HTML_TEMPLATE placeholder...")
    print(f"   Looking for: '$app_script' (Template syntax)")
    if '$app_script' in HTML_TEMPLATE:
        print("   ✅ PASS: Template-style placeholder found")
    else:
        print("   ❌ FAIL: Template placeholder not found")
        return False

    print(f"\n2. Checking no escaping needed...")
    print(f"   APP_SCRIPT_TEMPLATE length: {len(APP_SCRIPT_TEMPLATE)}")

    # Check that braces are NOT escaped (since we're using Template)
    double_brace_count = APP_SCRIPT_TEMPLATE.count('{{')
    if double_brace_count == 0:
        print("   ✅ PASS: No double braces in APP_SCRIPT_TEMPLATE")
    else:
        print(f"   ⚠️  WARN: Found {double_brace_count} double braces (should be 0)")

    print(f"\n3. Testing Template.substitute() replacement...")

    from string import Template

    try:
        template = Template(HTML_TEMPLATE)
        html = template.substitute(
            css=CSS_TEMPLATE,
            data=data_json,
            app_script=APP_SCRIPT_TEMPLATE
        )
        print("   ✅ PASS: substitute() succeeded")

    except KeyError as e:
        print(f"   ❌ FAIL: KeyError - {e}")
        return False

    except Exception as e:
        print(f"   ❌ FAIL: {type(e).__name__} - {e}")
        return False

    print(f"\n4. Verifying replacement in generated HTML...")

    # Check that the literal "$app_script" is NOT in the output
    if '$app_script' in html:
        print("   ❌ FAIL: Literal '$app_script' found in output")
        return False
    else:
        print("   ✅ PASS: No literal '$app_script' in output")

    # Check that JavaScript code is present
    if 'let chart;' in html and 'document.addEventListener' in html:
        print("   ✅ PASS: JavaScript code is present in output")
    else:
        print("   ❌ FAIL: JavaScript code missing")
        return False

    # Check that data is embedded
    if '"nodes"' in html and '"edges"' in html:
        print("   ✅ PASS: Graph data is embedded")
    else:
        print("   ❌ FAIL: Graph data missing")
        return False

    print(f"\n5. Checking JavaScript syntax...")

    # Check for malformed JavaScript (quad braces)
    quad_count = html.count('{{{{')
    if quad_count == 0:
        print("   ✅ PASS: No quad braces (malformed JavaScript)")
    else:
        print(f"   ❌ FAIL: Found {quad_count} quad braces - will break JavaScript")
        return False

    # Check for triple braces
    triple_count = html.count('{{{')
    if triple_count == 0:
        print("   ✅ PASS: No triple braces")
    else:
        print(f"   ⚠️  WARN: Found {triple_count} triple braces")

    # Check that function braces are correct
    if 'function initGraph() {' in html:
        print("   ✅ PASS: Function braces are correct")
    else:
        print("   ❌ FAIL: Function braces are malformed")
        return False

    print(f"\n6. Writing test HTML file...")

    with open('test_fixed_template.html', 'w', encoding='utf-8') as f:
        f.write(html)

    print("   ✅ PASS: Written to test_fixed_template.html")

    return True


if __name__ == '__main__':
    success = test_template_replacement()

    if success:
        print("\n" + "="*50)
        print("✅ ALL TESTS PASSED!")
        print("="*50)
        print("\nThe template fix is working correctly.")
        print("Open test_fixed_template.html in your browser to verify.")
        sys.exit(0)
    else:
        print("\n" + "="*50)
        print("❌ TESTS FAILED!")
        print("="*50)
        sys.exit(1)
